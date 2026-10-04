"""Parse human-readable byte sizes for CLI and catalog operations."""

from __future__ import annotations

import re
from typing import Union

_SIZE_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*([kmg])?\s*$",
    re.IGNORECASE,
)

_MULTIPLIERS = {
    "k": 1024,
    "m": 1024**2,
    "g": 1024**3,
}


def parse_byte_size(value: Union[str, int]) -> int:
    """Parse a byte size string into an integer byte count.

    Supports plain integers and suffixes K, M, G (1024-based).

    Args:
        value: Size string (e.g. ``800K``, ``10M``, ``1G``) or integer bytes.

    Returns:
        Size in bytes.

    Raises:
        ValueError: If the value cannot be parsed or is not positive.
    """
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"Byte size must be positive, got {value}")
        return value

    if not value or not str(value).strip():
        raise ValueError("Byte size is empty")

    text = str(value).strip()
    if text.isdigit():
        size = int(text)
        if size <= 0:
            raise ValueError(f"Byte size must be positive, got {text}")
        return size

    match = _SIZE_PATTERN.match(text)
    if not match:
        raise ValueError(
            f"Invalid byte size {value!r}. Use an integer or a value with K, M, or G "
            "(e.g. '800K', '10M', '1G')."
        )

    number = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    if number <= 0:
        raise ValueError(f"Byte size must be positive, got {value!r}")

    if not suffix:
        return int(number)

    multiplier = _MULTIPLIERS[suffix]
    return int(number * multiplier)
