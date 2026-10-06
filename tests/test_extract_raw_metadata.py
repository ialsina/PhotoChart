"""Tests for RAW metadata extraction (rawpy API compatibility)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from photochart.imaging.extract import (
    _extract_raw_metadata,
    _raw_metadata_from_rawpy_object,
)


class _FakeSizes:
    raw_width = 6000
    raw_height = 4000
    top_margin = 8
    left_margin = 8
    iwidth = 5984
    iheight = 3984
    pixel_aspect = 1.0


def _fake_rawpy_raw(**overrides: object) -> SimpleNamespace:
    """Minimal RawPy-like object without legacy ``color_space``."""
    defaults = {
        "raw_type": "RawType.Flat",
        "num_colors": 3,
        "sizes": _FakeSizes(),
        "color_desc": b"RGBG",
        "camera_whitebalance": [1.0, 1.0, 1.0, 1.0],
        "color_matrix": [[1.0, 0.0, 0.0, 0.0]] * 3,
        "white_level": 16383,
        "extract_thumb": MagicMock(side_effect=OSError("no thumb")),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_raw_metadata_from_rawpy_object_modern_api() -> None:
    raw = _fake_rawpy_raw()
    meta = _raw_metadata_from_rawpy_object(raw)

    assert "color_space" not in meta
    assert meta["raw_type"] == "RawType.Flat"
    assert meta["num_colors"] == 3
    assert meta["sizes"]["raw_size"]["width"] == 6000
    assert meta["color_desc"] == "RGBG"
    assert meta["color_matrix"] is not None
    assert "thumbnail" not in meta


def test_raw_metadata_skips_missing_optional_fields() -> None:
    raw = SimpleNamespace(sizes=_FakeSizes())
    meta = _raw_metadata_from_rawpy_object(raw)

    assert meta["sizes"]["raw_size"]["width"] == 6000
    assert "num_colors" not in meta
    assert "color_desc" not in meta


def test_extract_raw_metadata_uses_imread_and_does_not_require_color_space(
    tmp_path,
) -> None:
    fake_file = tmp_path / "shot.nef"
    fake_file.write_bytes(b"not-a-real-raw")

    fake_raw = _fake_rawpy_raw()

    class _Ctx:
        def __enter__(self):
            return fake_raw

        def __exit__(self, *args: object) -> None:
            return None

    mock_imread = MagicMock(return_value=_Ctx())

    fake_rawpy = MagicMock()
    fake_rawpy.imread = mock_imread

    with patch.dict("sys.modules", {"rawpy": fake_rawpy}):
        meta = _extract_raw_metadata(str(fake_file))

    mock_imread.assert_called_once_with(str(fake_file))
    assert meta["num_colors"] == 3
    assert "color_space" not in meta
