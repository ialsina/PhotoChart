"""Core one-shot local classification workflow."""

from __future__ import annotations

import posixpath
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Callable, Iterable

from .collision import resolve_collision
from .config import OrganizerConfig
from .domain import DateResult, MediaObject, OperationResult, OperationStatus
from .patterns import ClassificationPattern
from .metadata import MetadataExtractor, resolve_capture_date
from .policies import is_stable, with_retry
from .storage import StorageAdapter
from .verify import verified_transfer


DateResolver = Callable[[MediaObject], DateResult]


class Organizer:
    def __init__(
        self,
        adapter: StorageAdapter,
        config: OrganizerConfig,
        date_resolver: DateResolver | None = None,
        metadata_extractor: MetadataExtractor | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config
        self.pattern = ClassificationPattern(config.pattern)
        self.date_resolver = date_resolver
        self.metadata_extractor = metadata_extractor or MetadataExtractor()
        self._processing: set[str] = set()

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

    def iter_once(
        self,
        dry_run: bool = False,
        media_objects: Iterable[MediaObject] | None = None,
    ) -> Iterable[OperationResult]:
        self.adapter.healthcheck()
        for media in media_objects if media_objects is not None else self.discover():
            yield replace(
                self._process_with_policy(media, dry_run=dry_run),
                object_id=media.object_id,
            )

    def run_once(
        self,
        dry_run: bool = False,
        media_objects: Iterable[MediaObject] | None = None,
    ) -> list[OperationResult]:
        return list(self.iter_once(dry_run=dry_run, media_objects=media_objects))

    def watch(self, dry_run: bool = False) -> Iterable[list[OperationResult]]:
        while True:
            yield self.run_once(dry_run=dry_run)
            time.sleep(self.config.scan_interval_seconds)

    def _process_with_policy(
        self, media: MediaObject, dry_run: bool
    ) -> OperationResult:
        if media.object_id in self._processing:
            return OperationResult(
                OperationStatus.SKIPPED, media.path, detail="already processing"
            )
        self._processing.add(media.object_id)
        try:
            if not is_stable(self.adapter, media, self.config.stability):
                return OperationResult(
                    OperationStatus.SKIPPED, media.path, detail="file is not stable"
                )
            return with_retry(
                lambda: self.process(media, dry_run=dry_run), self.config.retry
            )
        except Exception as error:
            if (
                self.config.quarantine
                and not dry_run
                and self.adapter.exists(media.path)
            ):
                try:
                    return self._quarantine(media, str(error))
                except Exception as quarantine_error:
                    return OperationResult(
                        OperationStatus.FAILED,
                        media.path,
                        detail=(f"{error}; quarantine failed: {quarantine_error}"),
                        verified=False,
                    )
            return OperationResult(
                OperationStatus.FAILED, media.path, detail=str(error), verified=False
            )
        finally:
            self._processing.discard(media.object_id)

    def _quarantine(self, media: MediaObject, detail: str) -> OperationResult:
        directory = posixpath.join(
            self.config.quarantine or "", time.strftime("%Y%m%d")
        )
        destination, _ = resolve_collision(
            self.adapter,
            media.path,
            posixpath.join(directory, media.name),
            "suffix",
        )
        self.adapter.ensure_directory(directory)
        verified_transfer(self.adapter, media.path, destination, delete_source=True)
        return OperationResult(
            OperationStatus.QUARANTINED,
            media.path,
            destination,
            detail=detail,
            verified=True,
        )

    def process(self, media: MediaObject, dry_run: bool = False) -> OperationResult:
        if self.date_resolver is not None:
            date_result = self.date_resolver(media)
        else:
            metadata = self.metadata_extractor.inspect(self.adapter, media)
            date_result = resolve_capture_date(metadata, media, self.config)
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
        moving = self.config.mode == "move"
        verified_transfer(
            self.adapter,
            media.path,
            destination,
            delete_source=moving,
        )
        status = OperationStatus.MOVED if moving else OperationStatus.COPIED
        return OperationResult(
            status,
            media.path,
            destination,
            date_result,
            verified=True,
        )
