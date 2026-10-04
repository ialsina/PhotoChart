from pathlib import Path

from photochart.ingest.photos import is_image_file
from photochart.media.extensions import normalize_extension, normalize_extensions
from photochart.organizer.adapters import LocalFilesystemAdapter
from photochart.organizer.config import OrganizerConfig, StabilityConfig
from photochart.organizer.service import Organizer


def test_is_image_file_case_insensitive() -> None:
    assert is_image_file(Path("photo.RW2"))
    assert is_image_file(Path("photo.JpEg"))


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
