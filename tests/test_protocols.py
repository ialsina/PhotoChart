from pathlib import Path

from photochart.fs.protocols import calculate_checksum, cp, mv


def test_checksum_is_stable(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"photo-data" * 100)

    checksum = calculate_checksum(str(source))

    assert checksum is not None
    assert len(checksum) == 32
    assert checksum == calculate_checksum(str(source))


def test_copy_preserves_content(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"copy me")

    cp(str(source), str(destination))

    assert source.read_bytes() == destination.read_bytes()


def test_verified_move_removes_source(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "nested" / "destination.bin"
    source.write_bytes(b"move me")

    mv(str(source), str(destination))

    assert not source.exists()
    assert destination.read_bytes() == b"move me"
