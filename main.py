from typing import Annotated

from fastapi import FastAPI, Header, Query, Response, status
from fastapi.responses import RedirectResponse
from yt_dlp import YoutubeDL


from custom_types import StreamType
from get_format import get_format

app = FastAPI()


@app.get("/redirect")
def redirect(
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

    return RedirectResponse(fmt["url"])
