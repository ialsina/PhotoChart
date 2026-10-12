from datetime import datetime

import pytest

from photochart.imaging.filename_time import parse_datetime_from_filename


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
