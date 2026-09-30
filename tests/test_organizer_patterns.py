from datetime import datetime

import pytest

from photochart.organizer.config import OrganizerConfig, config_from_mapping
from photochart.organizer.patterns import ClassificationPattern


@pytest.mark.parametrize(
    ("month", "quarter"),
    [(1, 1), (3, 1), (4, 2), (6, 2), (7, 3), (9, 3), (10, 4), (12, 4)],
)
def test_quarter_boundaries(month: int, quarter: int) -> None:
    pattern = ClassificationPattern("%YQ%Q/%Y%M%D")

    assert pattern.render(datetime(2026, month, 28)) == (
        f"2026Q{quarter}/2026{month:02d}28"
    )


def test_default_pattern_includes_year() -> None:
    pattern = ClassificationPattern()

    assert pattern.render(datetime(2026, 9, 28)) == "2026/2026Q3/20260928"


@pytest.mark.parametrize("template", ["/%Y", "../%Y", "%Y/%x", "%Y%"])
def test_unsafe_or_unknown_patterns_are_rejected(template: str) -> None:
    with pytest.raises(ValueError):
        ClassificationPattern(template)


def test_configuration_loads_nested_shape() -> None:
    config = config_from_mapping(
        {
            "adapter": {"type": "webdav"},
            "source": {"path": "/PhotoUpload"},
            "destination": {"path": "/Photos", "pattern": "%YQ%Q/%Y%M%D"},
            "stability": {"interval_seconds": 2, "checks": 3},
        }
    )

    assert config.adapter == "webdav"
    assert config.pattern == "%YQ%Q/%Y%M%D"
    assert config.stability.checks == 3


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"workers": 2}, "workers must be 1"),
        (
            {"duplicate_detection": "size_only"},
            "duplicate_detection must be 'size_then_hash'",
        ),
        (
            {"collision": "quarantine"},
            "collision quarantine requires a quarantine path",
        ),
    ],
)
def test_configuration_rejects_unavailable_behavior(overrides, message):
    with pytest.raises(ValueError, match=message):
        OrganizerConfig(source="/in", destination="/out", **overrides)
