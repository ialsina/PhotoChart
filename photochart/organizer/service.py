"""Core one-shot local classification workflow."""

from __future__ import annotations

import posixpath
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Callable, Iterable

from .collision import resolve_collision, streams_equal
from .config import OrganizerConfig
from .domain import DateResult, MediaObject, OperationResult, OperationStatus
from .patterns import ClassificationPattern
from .storage import StorageAdapter


DateResolver = Callable[[MediaObject], DateResult]


class Organizer:
    def __init__(
        self,
        adapter: StorageAdapter,
        config: OrganizerConfig,
        date_resolver: DateResolver | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config
        self.pattern = ClassificationPattern(config.pattern)
        self.date_resolver = date_resolver or self._filesystem_date

    @staticmethod
    def _filesystem_date(media: MediaObject) -> DateResult:
        if media.modified_time is None:
            raise ValueError(f"No usable date for {media.path}")
        return DateResult(media.modified_time, "filesystem_modified_time")

    def discover(self) -> Iterable[MediaObject]:
        extensions = set(self.config.media_extensions)
        for media in self.adapter.list_objects(self.config.source):
            if PurePosixPath(media.name).suffix.lower() in extensions:
                yield media

    def run_once(self, dry_run: bool = False) -> list[OperationResult]:
        self.adapter.healthcheck()
        return [self.process(media, dry_run=dry_run) for media in self.discover()]

    def process(self, media: MediaObject, dry_run: bool = False) -> OperationResult:
        date_result = self.date_resolver(media)
        classification_date = date_result.value - timedelta(
            hours=self.config.day_starts_at
        )
        if self.config.process_after is not None:
            before = classification_date < self.config.process_after
            same_day_excluded = (
                not self.config.include_first
                and classification_date.date() == self.config.process_after.date()
            )
            if before or same_day_excluded:
                return OperationResult(
                    OperationStatus.SKIPPED,
                    media.path,
                    date_result=date_result,
                    detail="before configured processing window",
                )

        directory = posixpath.join(
            self.config.destination, self.pattern.render(classification_date)
        )
        destination = posixpath.join(directory, media.name)
        destination, duplicate = resolve_collision(
            self.adapter, media.path, destination, self.config.collision
        )
        if dry_run:
            return OperationResult(
                OperationStatus.DRY_RUN,
                media.path,
                destination,
                date_result,
                detail="duplicate" if duplicate else None,
                verified=duplicate,
            )
        if duplicate:
            if self.config.mode == "move":
                self.adapter.delete(media.path)
            return OperationResult(
                OperationStatus.DUPLICATE,
                media.path,
                destination,
                date_result,
                verified=True,
            )

        self.adapter.ensure_directory(directory)
        if self.config.mode == "copy":
            self.adapter.copy(media.path, destination)
            status = OperationStatus.COPIED
        else:
            self.adapter.move(media.path, destination)
            status = OperationStatus.MOVED

        if not self.adapter.exists(destination):
            raise IOError(f"Destination was not created: {destination}")
        if self.config.mode == "copy" and not streams_equal(
            self.adapter, media.path, destination
        ):
            raise IOError(f"Verification failed: {destination}")
        return OperationResult(
            status,
            media.path,
            destination,
            date_result,
            verified=True,
        )
