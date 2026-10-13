from datetime import datetime, timezone

import pytest

from photochart.imaging.filename_time import parse_datetime_from_filename

# 2023-10-12 18:30:56 UTC
_ANCHOR_TS = 1697135456
_ANCHOR_DT = datetime.fromtimestamp(_ANCHOR_TS, tz=timezone.utc).replace(tzinfo=None)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("IMG_20160406_195654.jpg", datetime(2016, 4, 6, 19, 56, 54)),
        ("img_20160406_195654.JPG", datetime(2016, 4, 6, 19, 56, 54)),
        ("IMG_20180319_182141_1.jpg", datetime(2018, 3, 19, 18, 21, 41)),
        ("IMG_20160807_171754_BURST020.jpg", datetime(2016, 8, 7, 17, 17, 54)),
        (
            "IMG_20160203_083902178.jpg",
            datetime(2016, 2, 3, 8, 39, 2, 178000),
        ),
        ("20160406_195654.jpg", datetime(2016, 4, 6, 19, 56, 54)),
        ("20160406_195654_burst.jpg", datetime(2016, 4, 6, 19, 56, 54)),
    ],
)
def test_parse_datetime_from_filename_valid(name: str, expected: datetime) -> None:
    assert parse_datetime_from_filename(name) == expected


def test_parse_datetime_from_filename_invalid() -> None:
    assert parse_datetime_from_filename("vacation.jpg") is None
    assert parse_datetime_from_filename("IMG_20161399_195654.jpg") is None
    assert parse_datetime_from_filename("") is None


def test_epoch_disabled_by_default() -> None:
    assert parse_datetime_from_filename(f"{_ANCHOR_TS}.jpg") is None


@pytest.mark.parametrize(
    "stem",
    [
        str(_ANCHOR_TS),
        str(_ANCHOR_TS * 1_000),
        str(_ANCHOR_TS * 1_000_000),
        str(_ANCHOR_TS * 1_000_000_000),
    ],
)
def test_epoch_units_when_enabled(stem: str) -> None:
    parsed = parse_datetime_from_filename(f"{stem}.jpg", allow_epoch=True)
    assert parsed == _ANCHOR_DT


def test_epoch_rejects_implausible_year() -> None:
    assert parse_datetime_from_filename("1.jpg", allow_epoch=True) is None


def test_pattern_preferred_over_epoch_when_enabled() -> None:
    parsed = parse_datetime_from_filename("IMG_20160406_195654.jpg", allow_epoch=True)
    assert parsed == datetime(2016, 4, 6, 19, 56, 54)
