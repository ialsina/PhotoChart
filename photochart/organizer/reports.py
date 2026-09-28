"""Duplicate, missing-copy, and storage-waste reports."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .domain import MediaObject
from .storage import StorageAdapter


@dataclass(frozen=True)
class DuplicateGroup:
    checksum: str
    size: int
    paths: tuple[str, ...]

    @property
    def wasted_bytes(self) -> int:
        return self.size * (len(self.paths) - 1)


def checksum(adapter: StorageAdapter, path: str) -> str:
    digest = hashlib.sha256()
    with adapter.open_read(path) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicates(adapter: StorageAdapter, root: str) -> tuple[DuplicateGroup, ...]:
    by_size: dict[int, list[MediaObject]] = defaultdict(list)
    for media in adapter.list_objects(root):
        by_size[media.size].append(media)

    groups: list[DuplicateGroup] = []
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        by_checksum: dict[str, list[str]] = defaultdict(list)
        for candidate in candidates:
            by_checksum[checksum(adapter, candidate.path)].append(candidate.path)
        groups.extend(
            DuplicateGroup(value, size, tuple(sorted(paths)))
            for value, paths in by_checksum.items()
            if len(paths) > 1
        )
    return tuple(sorted(groups, key=lambda group: group.paths))


def find_missing(
    adapter: StorageAdapter, origin: str, destination: str
) -> tuple[str, ...]:
    destination_by_name_size = {
        (media.name, media.size) for media in adapter.list_objects(destination)
    }
    return tuple(
        media.path
        for media in adapter.list_objects(origin)
        if (media.name, media.size) not in destination_by_name_size
    )


def storage_histogram(
    groups: Iterable[DuplicateGroup],
) -> dict[str, int]:
    group_list = list(groups)
    return {
        "duplicate_groups": len(group_list),
        "duplicate_files": sum(len(group.paths) - 1 for group in group_list),
        "wasted_bytes": sum(group.wasted_bytes for group in group_list),
    }
