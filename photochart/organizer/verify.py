"""Verified transfer helpers shared by organizer workflows."""

from __future__ import annotations

from .collision import streams_equal
from .domain import ErrorKind, OrganizerError
from .storage import StorageAdapter


class VerificationError(OrganizerError):
    """Raised when a destination cannot be proven identical to its source."""

    def __init__(self, message: str) -> None:
        super().__init__(message, ErrorKind.PERMANENT)


def _remove_unverified_destination(adapter: StorageAdapter, destination: str) -> None:
    try:
        if adapter.exists(destination):
            adapter.delete(destination)
    except Exception:
        # Preserve the verification failure as the primary error; callers also
        # retain the source and can reconcile a leftover destination safely.
        return


def verified_transfer(
    adapter: StorageAdapter,
    source: str,
    destination: str,
    *,
    delete_source: bool,
) -> None:
    """Copy, byte-verify, and optionally delete the source.

    Even adapters with server-side move support use copy-first semantics here:
    the source remains recoverable until destination identity is established.
    """

    try:
        adapter.copy(source, destination)
        if not adapter.exists(destination):
            raise VerificationError(f"Destination was not created: {destination}")
        if not streams_equal(adapter, source, destination):
            raise VerificationError(f"Verification failed: {destination}")
    except Exception:
        _remove_unverified_destination(adapter, destination)
        raise

    if delete_source:
        adapter.delete(source)
