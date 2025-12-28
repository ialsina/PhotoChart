"""
CLI command implementations for Django backend.

All commands use Django ORM.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    HAS_RICH = True
    _console = Console()
except Exception:  # pragma: no cover
    HAS_RICH = False
    _console = None

# Django models - these will be imported after django.setup() in main.py
from photograph.models import PhotoPath


def cmd_ingest(args: argparse.Namespace) -> int:
    """Ingest photos from a directory and persist to database."""
    from photofinder.ingest import ingest_photos

    # Call the ingestion function
    result = ingest_photos(
        path=args.path,
        resolution=getattr(args, "resolution", None),
        calculate_hash=getattr(args, "hash", False),
        recursive=not getattr(args, "no_recursive", False),
        store_images=getattr(args, "store_images", False),
    )

    if not result["success"]:
        for err in result.get("errors", []):
            print(f"Error during ingestion: {err}", file=sys.stderr)
        return 1

    print(f"Ingested {result['count']} photo(s) from '{args.path}'.")
    if result.get("hashes_calculated", 0) > 0:
        print(f"Calculated {result['hashes_calculated']} hash(es).")
    if result.get("images_stored", 0) > 0:
        print(f"Stored {result['images_stored']} image(s) in database.")

    return 0
