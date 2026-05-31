from enum import Enum


class StreamType(str, Enum):
    video = "video"
    audio = "audio"


class StreamRequestType(str, Enum):
    redirect = "redirect"
    proxy_initial = "proxy_initial"
    stream = "stream"
