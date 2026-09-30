"""Operational stability and retry policies."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from .config import RetryConfig, StabilityConfig
from .domain import ErrorKind, MediaObject, OrganizerError
from .storage import StorageAdapter

T = TypeVar("T")


def is_stable(
    adapter: StorageAdapter,
    media: MediaObject,
    config: StabilityConfig,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    previous = (media.size, media.modified_time)
    for _ in range(config.checks):
        sleep(config.interval_seconds)
        current_object = adapter.get_object_info(media.path)
        current = (current_object.size, current_object.modified_time)
        if current != previous:
            return False
        previous = current
    return True


def with_retry(
    operation: Callable[[], T],
    config: RetryConfig,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    delay = config.initial_seconds
    last_error: OSError | OrganizerError | None = None
    for attempt in range(config.attempts):
        try:
            return operation()
        except (OSError, OrganizerError) as error:
            last_error = error
            retryable = not isinstance(error, FileExistsError) and (
                not isinstance(error, OrganizerError)
                or error.kind == ErrorKind.TRANSIENT
            )
            if not retryable:
                raise
            if attempt + 1 < config.attempts:
                sleep(delay)
                delay *= config.multiplier
    assert last_error is not None
    raise last_error
