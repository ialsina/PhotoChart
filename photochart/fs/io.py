"""Resilient file reads for flaky mounts (e.g. cloud FUSE drivers)."""

from __future__ import annotations

import errno
import os
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ReadRetryConfig:
    """Bounded backoff when reading files from slow or virtual filesystems."""

    attempts: int = 4
    initial_seconds: float = 1.0
    multiplier: float = 2.0
    stability_checks: int = 2
    stability_interval_seconds: float = 0.25


def get_read_retry_config() -> ReadRetryConfig:
    """Load retry settings from Django when available, else use defaults."""
    try:
        from django.conf import settings

        return ReadRetryConfig(
            attempts=int(getattr(settings, "INGEST_READ_RETRY_ATTEMPTS", 4)),
            initial_seconds=float(
                getattr(settings, "INGEST_READ_RETRY_INITIAL_SECONDS", 1.0)
            ),
            multiplier=float(getattr(settings, "INGEST_READ_RETRY_MULTIPLIER", 2.0)),
            stability_checks=int(getattr(settings, "INGEST_READ_STABILITY_CHECKS", 2)),
            stability_interval_seconds=float(
                getattr(settings, "INGEST_READ_STABILITY_INTERVAL_SECONDS", 0.25)
            ),
        )
    except Exception:
        return ReadRetryConfig()


def is_retryable_read_error(exc: BaseException) -> bool:
    """Return True when re-reading the source file may succeed (transient I/O)."""
    if isinstance(exc, PermissionError):
        return False
    if isinstance(exc, BlockingIOError):
        return True
    if isinstance(exc, OSError):
        if exc.errno in (errno.EACCES, errno.ENOTSUP):
            return False
        return True
    try:
        from PIL import UnidentifiedImageError

        if isinstance(exc, UnidentifiedImageError):
            return True
    except ImportError:
        pass
    return False


def _file_size_stable(
    path: str,
    checks: int,
    interval: float,
    sleep_fn: Callable[[float], None],
) -> bool:
    if checks <= 1:
        return True
    try:
        previous = os.stat(path).st_size
    except OSError:
        return False
    for _ in range(checks - 1):
        sleep_fn(interval)
        try:
            current = os.stat(path).st_size
        except OSError:
            return False
        if current != previous:
            return False
        previous = current
    return True


def read_bytes_with_retry(
    path: str,
    config: ReadRetryConfig | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bytes:
    """Read an entire file, retrying transient mount/read failures.

    Verifies the file exists, has non-zero size, optional size stability, and
    that the number of bytes read matches ``st_size`` (guards partial FUSE reads).
    """
    config = config or get_read_retry_config()
    delay = config.initial_seconds
    last_error: BaseException | None = None

    for attempt in range(config.attempts):
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)

            size = os.stat(path).st_size
            if size == 0:
                raise OSError(
                    errno.EAGAIN,
                    "File size is zero (may still be hydrating)",
                    path,
                )

            if not _file_size_stable(
                path,
                config.stability_checks,
                config.stability_interval_seconds,
                sleep_fn,
            ):
                raise OSError(
                    errno.EAGAIN,
                    "File size still changing",
                    path,
                )

            with open(path, "rb") as handle:
                data = handle.read()

            if len(data) != size:
                raise OSError(
                    errno.EIO,
                    f"Incomplete read: got {len(data)} of {size} bytes",
                    path,
                )
            return data
        except Exception as exc:
            last_error = exc
            if not is_retryable_read_error(exc):
                raise
            if attempt + 1 < config.attempts:
                sleep_fn(delay)
                delay *= config.multiplier

    assert last_error is not None
    raise last_error


def with_read_retry(
    operation: Callable[[], T],
    config: ReadRetryConfig | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """Run *operation*, retrying when it raises a retryable read error."""
    config = config or get_read_retry_config()
    delay = config.initial_seconds
    last_error: BaseException | None = None

    for attempt in range(config.attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if not is_retryable_read_error(exc):
                raise
            if attempt + 1 < config.attempts:
                sleep_fn(delay)
                delay *= config.multiplier

    assert last_error is not None
    raise last_error
