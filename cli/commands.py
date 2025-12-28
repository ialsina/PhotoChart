"""
CLI command implementations for Django backend.

All commands use Django ORM.
"""

from __future__ import annotations

import argparse
import os
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
from photofinder.resolution import get_resolution_presets


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


def cmd_convert(args: argparse.Namespace) -> int:
    """Convert an image file to a standard format."""
    from photofinder.convert import convert_image

    src = args.source
    output_format = getattr(args, "format", "JPEG").upper()

    # Check if source file exists
    src_path = Path(src)
    if not src_path.exists():
        print(f"Error: Source file does not exist: {src}", file=sys.stderr)
        return 1

    # Determine output path extension based on format
    if output_format == "JPEG":
        ext = ".jpg"
    elif output_format == "PNG":
        ext = ".png"
    else:
        ext = src_path.suffix

    # Determine output path
    if args.output:
        output_str = args.output
        output_path = Path(output_str)

        # Check if output is a directory (ends with / or is an existing directory)
        if (
            output_path.is_dir()
            or output_str.endswith(os.sep)
            or output_str.endswith("/")
        ):
            # Output is a directory: use input filename with appropriate extension
            dst = str(output_path / src_path.with_suffix(ext).name)
        else:
            # Output is a file path (may be just a name or a full path)
            # If it has no suffix, add the appropriate extension
            # If it has a suffix, replace it with the appropriate extension
            if not output_path.suffix:
                # No extension: add it
                dst = str(output_path.with_suffix(ext))
            else:
                # Has extension: replace it with the correct one for the format
                dst = str(output_path.with_suffix(ext))
    else:
        # Default to same path as input, but change extension based on output format
        dst = str(src_path.with_suffix(ext))

    # Convert the image
    success = convert_image(
        src=src,
        dst=dst,
        resolution=getattr(args, "resolution", None),
        output_format=output_format,
    )

    if success:
        print(f"Successfully converted '{src}' to '{dst}'.")
        return 0
    else:
        print(f"Error: Failed to convert '{src}' to '{dst}'.", file=sys.stderr)
        return 1


def cmd_list_resolutions(args: argparse.Namespace) -> int:
    """List all available resolution presets."""
    presets = get_resolution_presets()

    if not HAS_RICH:
        # Plain text output
        print("Available resolution presets:")
        print("=" * 50)
        for name, (width, height) in sorted(presets.items()):
            print(f"  {name:20s} {width}x{height}")
        return 0

    # Rich table output
    table = Table(title="[bold cyan]Available Resolution Presets[/]")
    table.add_column("[bold]Preset Name[/]", style="bold yellow", justify="left")
    table.add_column("[bold]Resolution[/]", style="cyan", justify="center")
    table.add_column("[bold]Description[/]", style="white", justify="left")

    # Sort presets by resolution (width * height) for better readability
    sorted_presets = sorted(presets.items(), key=lambda x: x[1][0] * x[1][1])

    for name, (width, height) in sorted_presets:
        # Add some helpful descriptions for common presets
        description = ""
        if name in ("8k", "xlarge"):
            description = "8K Ultra HD"
        elif name in ("4k", "2160p", "high", "large"):
            description = "4K Ultra HD"
        elif name in ("1440p", "qhd"):
            description = "Quad HD / 1440p"
        elif name in ("1080p", "fhd", "medium", "landscape"):
            description = "Full HD / 1080p"
        elif name in ("720p", "hd"):
            description = "HD / 720p"
        elif name == "square":
            description = "Square (1:1)"
        elif name == "instagram":
            description = "Instagram square"
        elif name == "instagram-story":
            description = "Instagram story"
        elif name == "portrait":
            description = "Portrait orientation"

        table.add_row(name, f"{width}x{height}", description)

    _console.print(Panel.fit(table, title="[bold green]Resolution Presets[/]"))
    _console.print("\n[dim]You can also use explicit resolutions like '1920x1080'[/]")
    return 0
