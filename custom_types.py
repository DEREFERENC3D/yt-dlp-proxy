from enum import Enum


class StreamType(str, Enum):
    video = "video"
    audio = "audio"


class RequestType(str, Enum):
    redirect = "redirect"
    stream = "stream"
