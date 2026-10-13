"""Parse capture datetime from common camera/phone filename patterns."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

# IMG_20160406_195654.jpg | IMG_20180319_182141_1.jpg | IMG_20160203_083902178.jpg
# 20160406_195654.jpg | 20160406_195654_burst.jpg
_FILENAME_TIME_RE = re.compile(
    r"^(?:IMG_)?(?P<date>\d{8})_(?P<time>\d{6}|\d{9})(?:_[^./]+)?$",
    re.IGNORECASE,
)
_EPOCH_STEM_RE = re.compile(r"^\d+$")


def resolve_epoch_time_inferral() -> bool:
    """Return whether numeric-stem epoch filename inference is enabled."""
    try:
        from django.conf import settings

        if settings.configured:
            return bool(getattr(settings, "EPOCH_TIME_INFERRAL", False))
    except Exception:
        pass

    try:
        from decouple import config

        return config("EPOCH_TIME_INFERRAL", default=False, cast=bool)
    except Exception:
        return False


def _plausible_capture_year(dt: datetime) -> bool:
    year = dt.year
    return 1990 <= year <= datetime.now().year + 1


def _parse_pattern_stem(stem: str) -> datetime | None:
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


def _parse_epoch_stem(stem: str) -> datetime | None:
    if not _EPOCH_STEM_RE.match(stem):
        return None
    for divisor in (1, 1_000, 1_000_000, 1_000_000_000):
        ts = int(stem) / divisor
        if ts < 0:
            continue
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        except (OSError, OverflowError, ValueError):
            continue
        if _plausible_capture_year(dt):
            return dt
    return None


def parse_datetime_from_filename(
    name: str, *, allow_epoch: bool | None = None
) -> datetime | None:
    """Return naive datetime from a filename stem, or None if the pattern does not match.

    Supported patterns (extension ignored):
    - IMG_YYYYMMDD_hhmmss[.ext]
    - IMG_YYYYMMDD_hhmmss_xxx[.ext]
    - IMG_YYYYMMDD_hhmmssSSS[.ext] (9-digit time: hhmmss + milliseconds)
    - YYYYMMDD_hhmmss[.ext] and YYYYMMDD_hhmmss_xxx[.ext]

    When ``allow_epoch`` is true (or ``EPOCH_TIME_INFERRAL`` is enabled when
    ``allow_epoch`` is None), a stem of only digits is tried as Unix epoch in
    seconds, milliseconds, microseconds, then nanoseconds (first plausible year).
    """
    if not name or not str(name).strip():
        return None
    stem = Path(name).stem

    parsed = _parse_pattern_stem(stem)
    if parsed is not None:
        return parsed

    if allow_epoch is None:
        allow_epoch = resolve_epoch_time_inferral()
    if allow_epoch:
        return _parse_epoch_stem(stem)
    return None
