from typing import Any
from custom_types import StreamType


def get_format(
    info: dict[str, str | list[Any]],
    stream_type: StreamType,
) -> dict[str, str]:
    all_formats = info.get("requested_formats")
    if type(all_formats) is not list:
        raise ValueError("requested_formats is garbage", all_formats)

    if not len(all_formats):
        raise ValueError("No formats found")

    match stream_type:
        case StreamType.audio:
            filtered = list(
                filter(
                    lambda x: x.get("resolution") == "audio only",
                    all_formats,
                )
            )
        case StreamType.video:
            filtered = list(
                filter(
                    lambda x: x.get("resolution") != "audio only",
                    all_formats,
                )
            )

    if len(filtered) < 0:
        raise ValueError("No formats of the requested type found")

    return filtered[0]
