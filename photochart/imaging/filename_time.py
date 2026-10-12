"""Parse capture datetime from common camera/phone filename patterns."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

# IMG_20160406_195654.jpg | IMG_20180319_182141_1.jpg | IMG_20160203_083902178.jpg
# 20160406_195654.jpg | 20160406_195654_burst.jpg
_FILENAME_TIME_RE = re.compile(
    r"^(?:IMG_)?(?P<date>\d{8})_(?P<time>\d{6}|\d{9})(?:_[^./]+)?$",
    re.IGNORECASE,
)


def parse_datetime_from_filename(name: str) -> datetime | None:
    """Return naive datetime from a filename stem, or None if the pattern does not match.

    Supported patterns (extension ignored):
    - IMG_YYYYMMDD_hhmmss[.ext]
    - IMG_YYYYMMDD_hhmmss_xxx[.ext]
    - IMG_YYYYMMDD_hhmmssSSS[.ext] (9-digit time: hhmmss + milliseconds)
    - YYYYMMDD_hhmmss[.ext] and YYYYMMDD_hhmmss_xxx[.ext]
    """
    if not name or not str(name).strip():
        return None
    stem = Path(name).stem
    match = _FILENAME_TIME_RE.match(stem)
    if not match:
        return None
    date_str = match.group("date")
    time_str = match.group("time")
    try:
        year = int(date_str[0:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        hour = int(time_str[0:2])
        minute = int(time_str[2:4])
        second = int(time_str[4:6])
        microsecond = 0
        if len(time_str) == 9:
            millis = int(time_str[6:9])
            microsecond = millis * 1000
        return datetime(year, month, day, hour, minute, second, microsecond=microsecond)
    except (ValueError, OverflowError):
        return None
