from __future__ import annotations

import math


def parse_retry_after_header(
    value: str | None,
    *,
    default: int,
) -> int:
    if value is None:
        return max(1, int(default))

    raw = value.strip()
    if not raw:
        return max(1, int(default))

    try:
        seconds = math.ceil(float(raw))
    except (TypeError, ValueError):
        return max(1, int(default))

    return max(1, seconds)


def parse_reset_timestamp_header(
    value: str | None,
    *,
    now_ts: int,
    default: int,
    min_seconds: int = 1,
) -> int:
    fallback = max(min_seconds, int(default))

    if value is None:
        return fallback

    raw = value.strip()
    if not raw:
        return fallback

    try:
        reset_ts = int(float(raw))
    except (TypeError, ValueError):
        return fallback

    return max(min_seconds, reset_ts - int(now_ts))
