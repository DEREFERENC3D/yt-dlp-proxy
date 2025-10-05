from typing import Annotated
from json import dumps

from fastapi import FastAPI, Header, Path, Query, Response, status
from fastapi.responses import RedirectResponse
import requests
from yt_dlp import YoutubeDL


from custom_types import StreamRequestType, StreamType
from get_format import get_format

app = FastAPI()


def get_link(url: str, stream_type: StreamType | None):
    with YoutubeDL() as ydl:
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
    with YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)

    if type(info) is not dict:
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(dumps(info))

@app.get("/{request_type}")
def stream(
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
    stream_type = stream_type or (
        # default to audio type for MPD
        user_agent is not None
        and user_agent.startswith("Music Player Daemon")
        and StreamType.audio
        or None
    )

    with YoutubeDL() as ydl:
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
