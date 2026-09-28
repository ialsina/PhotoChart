"""Destination collision policies."""

from __future__ import annotations

from pathlib import PurePosixPath

from .storage import StorageAdapter


def streams_equal(
    adapter: StorageAdapter,
    first: str,
    second: str,
    chunk_size: int = 1024 * 1024,
) -> bool:
    if adapter.get_object_info(first).size != adapter.get_object_info(second).size:
        return False
    with adapter.open_read(first) as left, adapter.open_read(second) as right:
        while True:
            left_chunk = left.read(chunk_size)
            right_chunk = right.read(chunk_size)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def resolve_collision(
    adapter: StorageAdapter,
    source: str,
    destination: str,
    policy: str = "suffix",
) -> tuple[str, bool]:
    """Return destination and whether identical content already exists."""
    if not adapter.exists(destination):
        return destination, False
    if streams_equal(adapter, source, destination):
        return destination, True
    if policy != "suffix":
        raise FileExistsError(destination)

    path = PurePosixPath(destination)
    counter = 1
    while True:
        candidate = str(path.with_name(f"{path.stem}_{counter}{path.suffix}"))
        if not adapter.exists(candidate):
            return candidate, False
        if streams_equal(adapter, source, candidate):
            return candidate, True
        counter += 1
