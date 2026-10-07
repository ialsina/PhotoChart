from pathlib import Path

from photochart.ingest.photos import get_image_files, is_image_file
from photochart.media.extensions import normalize_extension, normalize_extensions
from photochart.organizer.adapters import LocalFilesystemAdapter
from photochart.organizer.config import OrganizerConfig, StabilityConfig
from photochart.organizer.service import Organizer


def test_is_image_file_case_insensitive() -> None:
    assert is_image_file(Path("photo.RW2"))
    assert is_image_file(Path("photo.JpEg"))


def test_is_image_file_raw_only() -> None:
    assert is_image_file(Path("photo.NEF"), raw_only=True)
    assert not is_image_file(Path("photo.jpg"), raw_only=True)


def test_get_image_files_raw_only(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"jpeg")
    (tmp_path / "b.cr2").write_bytes(b"raw")
    all_images = get_image_files(str(tmp_path), media_root=tmp_path / "unused")
    assert {p.name for p in all_images} == {"a.jpg", "b.cr2"}
    raw_only = get_image_files(
        str(tmp_path), media_root=tmp_path / "unused", raw_only=True
    )
    assert [p.name for p in raw_only] == ["b.cr2"]


def test_normalize_extension() -> None:
    assert normalize_extension("RW2") == ".rw2"
    assert normalize_extension(".NEF") == ".nef"


def test_organizer_config_normalizes_media_extensions() -> None:
    config = OrganizerConfig(
        source="/in",
        destination="/out",
        media_extensions=(".RW2", ".JPG"),
    )
    assert config.media_extensions == (".rw2", ".jpg")


def test_organizer_discover_case_insensitive_extension(tmp_path: Path) -> None:
    source = tmp_path / "in"
    source.mkdir()
    (source / "panasonic.RW2").write_bytes(b"raw")

    config = OrganizerConfig(
        source=str(source),
        destination=str(tmp_path / "out"),
        media_extensions=(".rw2",),
        stability=StabilityConfig(interval_seconds=0, checks=1),
    )
    discovered = list(Organizer(LocalFilesystemAdapter(), config).discover())
    assert [item.name for item in discovered] == ["panasonic.RW2"]
