from runner_with_api.fastapi.cancellation import cancel_on_disconnect
from typing import Annotated, Any
from json import dumps
import os
import subprocess
from threading import Thread

from fastapi import FastAPI, Header, Path, Query, Request, Response, status
from fastapi.responses import RedirectResponse, StreamingResponse
import requests
from yt_dlp import YoutubeDL, parse_options


from custom_types import StreamRequestType, StreamType
from get_format import get_format
from config import FFMPEG_CHUNK_SIZE

yt_dlp_options = parse_options().ydl_opts
app = FastAPI()


def get_link(url: str, stream_type: StreamType | None):
    with YoutubeDL(yt_dlp_options) as ydl:
        info = ydl.extract_info(
            url,
            download=False,
        )

    if type(info) is not dict:
        raise ValueError("extract_info returned garbage")

    fmt = get_format(info, stream_type)

    return fmt["url"]


@app.get("/info")
def info(
    url: Annotated[
        str, Query(title="Link to the entity (e.g. YouTube video) to get info for")
    ],
):
    with YoutubeDL(yt_dlp_options) as ydl:
        info = ydl.extract_info(url, download=False)

    if type(info) is not dict:
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(dumps(info))


@app.get("/search")
def search(
    q: Annotated[str, Query(title="Terms to search for", min_length=1)],
    result_count: Annotated[int, Query(title="The amount of results to return")] = 10,
):
    with YoutubeDL(yt_dlp_options) as ydl:
        info: Any | dict[str, str | list[Any]] | None = ydl.extract_info(
            f"ytsearch{result_count}:{q}", download=False, process=False
        )

    if type(info) is not dict:
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    info["entries"] = list(info["entries"])

    return Response(dumps(info))


def ffeeder(sem: dict[str, bool], fd: int, res: requests.Response):
    try:
        with os.fdopen(fd, "wb") as f:
            for chunk in res.iter_content(chunk_size=FFMPEG_CHUNK_SIZE):
                if sem["cancelled"]:
                    break
                _ = f.write(chunk)
    except BrokenPipeError:
        pass


@app.get("/{request_type}")
async def stream(
    r: Request,
    request_type: Annotated[
        StreamRequestType,
        Path(
            title="Request type - redirect to the stream's original link or proxy it through this server"
        ),
    ],
    url: Annotated[
        str, Query(title="Link to the entity (e.g. YouTube video) to stream")
    ],
    stream_type: Annotated[
        StreamType | None, Query(title="Stream type - audio or video")
    ] = None,
    user_agent: Annotated[str | None, Header()] = None,
):
    async with cancel_on_disconnect(r):
        stream_type = stream_type or (
            # default to audio type for MPD
            user_agent is not None
            and user_agent.startswith("Music Player Daemon")
            and StreamType.audio
            or None
        )

        with YoutubeDL(yt_dlp_options) as ydl:
            info = ydl.extract_info(
                url,
                download=False,
            )

        if type(info) is not dict:
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            fmt = get_format(info, stream_type)
        except:
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        match request_type:
            case StreamRequestType.redirect:
                return RedirectResponse(fmt["url"])
            case StreamRequestType.proxy_initial:
                res = requests.get(fmt["url"])
                return Response(
                    res.content,
                    headers={
                        "Content-Type": res.headers.get(
                            "Content-Type", "application/octet-stream"
                        )
                    },
                )
            case StreamRequestType.stream:
                upstream = requests.get(fmt["url"], stream=True)
                if stream_type == StreamType.audio:
                    # For audio there is no need to process the data
                    return StreamingResponse(upstream)

                # For video, we want to combine it with the audio track, so fetch that first
                try:
                    audio_fmt = get_format(info, StreamType.audio)
                except:
                    return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                upstream_audio = requests.get(audio_fmt["url"], stream=True)

                # Use ffmpeg to merge the streams. We create pipes manually instead of just using STDIN,
                # as we need two inputs, not one - and if we want more tracks in the future,
                # we will need even more pipes

                video_r, video_w = os.pipe()
                audio_r, audio_w = os.pipe()

                ffprocess = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-i",
                        f"pipe:{video_r}",
                        "-i",
                        f"pipe:{audio_r}",
                        # No transcoding, just remux the streams into one container
                        "-c:v",
                        "copy",
                        "-c:a",
                        "copy",
                        # TODO / FIXME: this parameter is needed for MP4 containers
                        # (fixes "muxer does not support non seekable output" error)
                        # but will likely not work for any other format
                        "-movflags",
                        "frag_keyframe+empty_moov",
                        # since the output is a pipe, ffmpeg can't do
                        # the usual extension guessing from the file name
                        # and needs it specified
                        "-f",
                        fmt["ext"],
                        "pipe:",
                    ],
                    # Don't forget to pass the pipes (lol) used in the args above
                    pass_fds=(video_r, audio_r),
                    stdout=subprocess.PIPE,
                )

                # Set up the input - create threads for writing the data into the pipes.

                # Since there is no (built-in / easy / lazy) way to kill a thread in Python,
                # we use a semaphore and check it in the thread's code, returning when signalled.
                sem = {"cancelled": False}

                t_video = Thread(target=ffeeder, args=(sem, video_w, upstream))
                t_video.daemon = True

                t_audio = Thread(target=ffeeder, args=(sem, audio_w, upstream_audio))
                t_audio.daemon = True

                # Set up the output - wraped in a generator to make it compatible with "StreamingResponse"
                async def stream_generator():
                    while True:
                        if await r.is_disconnected():
                            # Disconnection handling, since this is a long-running request
                            # We do not want to keep processing if the client disconnects

                            # Signal the threads to stop feeding data into ffmpeg
                            sem["cancelled"] = True

                            # Close its output to force it to exit
                            if ffprocess.stdout:
                                ffprocess.stdout.close()

                            # Reap the process. We don't want zombies, do we?
                            _ = ffprocess.wait()

                            # ...And we're done.
                            break

                        if ffprocess.poll() is not None:
                            # Process died. This is unexpected (unless end of stream?), but handle it gracefully.
                            # TODO: Figure out if this happens on end of stream
                            # TODO: Check if threads actually need to be stopped - both here and in the end of stream case (if it is separate after all)

                            # Stop the input threads if they have not already
                            sem["cancelled"] = True
                            break

                        chunk = ffprocess.stdout.read(FFMPEG_CHUNK_SIZE)  # pyright: ignore[reportOptionalMemberAccess]
                        if chunk:
                            yield chunk
                        else:
                            break

                t_video.start()
                t_audio.start()

                return StreamingResponse(stream_generator())
