"""Domain objects shared by the organizer core and storage adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional


class ErrorKind(str, Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    CONFLICT = "conflict"
    CONFIGURATION = "configuration"


class OperationStatus(str, Enum):
    DISCOVERED = "discovered"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"
    COPIED = "copied"
    MOVED = "moved"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    FAILED = "failed"


@dataclass(frozen=True)
class StorageCapabilities:
    atomic_move: bool = False
    server_side_move: bool = False
    random_read: bool = False
    streaming_read: bool = True
    local_filesystem: bool = False
    object_storage: bool = False
    resumable_transfer: bool = False


@dataclass(frozen=True)
class MediaObject:
    adapter_id: str
    object_id: str
    path: str
    name: str
    size: int
    modified_time: Optional[datetime] = None
    content_type: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DateResult:
    value: datetime
    source: str
    timezone: Optional[str] = None
    confidence: str = "normal"


@dataclass(frozen=True)
class OperationResult:
    status: OperationStatus
    source: str
    destination: Optional[str] = None
    date_result: Optional[DateResult] = None
    detail: Optional[str] = None
    verified: bool = False


class OrganizerError(RuntimeError):
    def __init__(self, message: str, kind: ErrorKind) -> None:
        super().__init__(message)
        self.kind = kind
