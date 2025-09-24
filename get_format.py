from typing import Any
from custom_types import StreamType


def get_format(
    info: dict[str, str | list[Any]],
    stream_type: StreamType | None,
) -> dict[str, str]:
    all_formats = info.get("requested_formats")
    if type(all_formats) is not list:
        all_formats = info.get("formats")
    if type(all_formats) is not list:
        raise ValueError("requested_formats and all_formats are both garbage", all_formats)

    if not len(all_formats):
        raise ValueError("No formats found")

    if stream_type is None:
        return all_formats[0]

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
