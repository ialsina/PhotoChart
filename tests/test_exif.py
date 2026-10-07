import importlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from photochart.imaging.exif import (
    ExifTag,
    ExifTagName,
    _serialize_exif_value,
    extract_exif,
    extract_exif_for_info,
)


def test_serialize_exif_value_bytes_and_rational() -> None:
    assert _serialize_exif_value(b"hello") == "hello"
    assert "binary data" in _serialize_exif_value(b"\xff\xfe")
    from fractions import Fraction

    assert _serialize_exif_value(Fraction(3, 2)) == 1.5


def _write_jpeg_with_exif(path: Path) -> None:
    img = Image.new("RGB", (4, 4), color="red")
    exif = img.getexif()
    exif[ExifTag.MODEL] = "TestCam"
    exif[ExifTag.DATETIME] = "2024:01:15 10:20:30"
    exif_ifd = exif.get_ifd(0x8769)
    exif_ifd[ExifTag.DATETIME_ORIGINAL] = "2024:01:15 10:20:31"
    exif_ifd[0x829A] = (1, 125)  # ExposureTime 1/125s
    exif_ifd[0xA434] = "Test Lens 24mm"
    exif[0x8769] = exif_ifd
    img.save(path, exif=exif)


def test_extract_exif_limited_datetime_from_exif_sub_ifd(tmp_path: Path) -> None:
    jpeg = tmp_path / "shot.jpg"
    _write_jpeg_with_exif(jpeg)

    result = extract_exif(str(jpeg))
    assert set(result.keys()) == {"datetime", "model"}
    assert result["model"] == "TestCam"
    assert result["datetime"] == datetime(2024, 1, 15, 10, 20, 31)


def test_extract_exif_for_info_includes_summary_tags(tmp_path: Path) -> None:
    jpeg = tmp_path / "shot.jpg"
    _write_jpeg_with_exif(jpeg)

    info_exif = extract_exif_for_info(str(jpeg), all_exif=False)
    assert info_exif["model"] == "TestCam"
    assert "ExposureTime" in info_exif
    assert info_exif["LensModel"] == "Test Lens 24mm"


def test_extract_exif_full_ignores_tags_and_includes_extra_fields(
    tmp_path: Path,
) -> None:
    jpeg = tmp_path / "shot.jpg"
    _write_jpeg_with_exif(jpeg)

    limited = extract_exif(str(jpeg))
    full = extract_exif(
        str(jpeg),
        tags=[ExifTagName.DATETIME],
        full=True,
    )

    assert "datetime" not in full
    assert "Model" in full or "DateTimeOriginal" in full
    assert len(full) > len(limited)


def test_cmd_info_json_and_all_exif(tmp_path: Path) -> None:
    import io
    import sys
    from argparse import Namespace

    from cli.commands import cmd_info

    jpeg = tmp_path / "shot.jpg"
    _write_jpeg_with_exif(jpeg)

    args = Namespace(file=str(jpeg), all_exif=False, json=True)
    args_all = Namespace(file=str(jpeg), all_exif=True, json=True)

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        assert cmd_info(args) == 0
        payload_limited = json.loads(buf.getvalue())
        buf.seek(0)
        buf.truncate(0)
        assert cmd_info(args_all) == 0
        payload_full = json.loads(buf.getvalue())
    finally:
        sys.stdout = old_stdout

        for key in ("file", "image", "exif", "raw"):
            assert key in payload_limited
        assert "datetime" in payload_limited["exif"]
        assert "ExposureTime" in payload_limited["exif"]
        assert len(payload_full["exif"]) > len(payload_limited["exif"])


def test_cli_info_json_does_not_initialize_django(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jpeg = tmp_path / "shot.jpg"
    _write_jpeg_with_exif(jpeg)

    cli_main = importlib.import_module("cli.main")

    def fail_setup() -> None:
        raise AssertionError("Django should not be initialized")

    monkeypatch.setattr(cli_main, "_setup_django", fail_setup)
    assert cli_main.main(["info", "-j", str(jpeg)]) == 0
