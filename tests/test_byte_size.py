import pytest

from photochart.media.size import parse_byte_size


def test_plain_integer() -> None:
    assert parse_byte_size("1024") == 1024
    assert parse_byte_size(512) == 512


def test_k_m_g_suffixes() -> None:
    assert parse_byte_size("800K") == 800 * 1024
    assert parse_byte_size("10M") == 10 * 1024**2
    assert parse_byte_size("1G") == 1024**3
    assert parse_byte_size("1.5M") == int(1.5 * 1024**2)


def test_case_insensitive() -> None:
    assert parse_byte_size("10m") == parse_byte_size("10M")


def test_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid byte size"):
        parse_byte_size("10MB")
    with pytest.raises(ValueError, match="empty"):
        parse_byte_size("")
    with pytest.raises(ValueError, match="positive"):
        parse_byte_size("0K")
