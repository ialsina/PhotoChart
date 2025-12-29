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
from photochart.resolution import get_resolution_presets
from photochart.metadata import extract_metadata


def cmd_ingest(args: argparse.Namespace) -> int:
    """Ingest photos from a directory and persist to database."""
    from photochart.ingest import ingest_photos

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
    from photochart.convert import convert_image

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


def cmd_info(args: argparse.Namespace) -> int:
    """Display metadata for an image file."""
    file_path = args.file
    path = Path(file_path)

    if not path.exists():
        print(f"Error: File does not exist: {file_path}", file=sys.stderr)
        return 1

    # Extract metadata
    metadata = extract_metadata(file_path)

    if not HAS_RICH:
        # Plain text output
        print(f"Metadata for: {file_path}")
        print("=" * 80)

        # File information
        if metadata.get("file"):
            print("\n[File Information]")
            file_info = metadata["file"]
            print(f"  Path: {file_info.get('path', 'N/A')}")
            print(f"  Name: {file_info.get('name', 'N/A')}")
            print(f"  Extension: {file_info.get('extension', 'N/A')}")
            print(
                f"  Size: {file_info.get('size_mb', 0)} MB ({file_info.get('size', 0)} bytes)"
            )

        # Image information
        if metadata.get("image"):
            print("\n[Image Properties]")
            img_info = metadata["image"]
            if "size" in img_info:
                print(
                    f"  Dimensions: {img_info['size'].get('width', 'N/A')}x{img_info['size'].get('height', 'N/A')}"
                )
            print(f"  Format: {img_info.get('format', 'N/A')}")
            print(f"  Mode: {img_info.get('mode', 'N/A')}")
            print(f"  Has Transparency: {img_info.get('has_transparency', False)}")

        # EXIF information
        if metadata.get("exif"):
            print("\n[EXIF Data]")
            exif = metadata["exif"]
            for key, value in sorted(exif.items()):
                # Truncate very long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                print(f"  {key}: {value_str}")

        # RAW information
        if metadata.get("raw"):
            print("\n[RAW Metadata]")
            raw_info = metadata["raw"]
            for key, value in sorted(raw_info.items()):
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                print(f"  {key}: {value_str}")

        return 0

    # Rich output
    from rich.text import Text

    panels = []

    # File information panel
    if metadata.get("file"):
        file_info = metadata["file"]
        file_text = Text()
        file_text.append("Path: ", style="bold")
        file_text.append(f"{file_info.get('path', 'N/A')}\n")
        file_text.append("Name: ", style="bold")
        file_text.append(f"{file_info.get('name', 'N/A')}\n")
        file_text.append("Extension: ", style="bold")
        file_text.append(f"{file_info.get('extension', 'N/A')}\n")
        file_text.append("Size: ", style="bold")
        file_text.append(
            f"{file_info.get('size_mb', 0)} MB ({file_info.get('size', 0)} bytes)\n"
        )
        panels.append(
            Panel(
                file_text, title="[bold cyan]File Information[/]", border_style="cyan"
            )
        )

    # Image information panel
    if metadata.get("image"):
        img_info = metadata["image"]
        img_text = Text()
        if "size" in img_info:
            img_text.append("Dimensions: ", style="bold")
            img_text.append(
                f"{img_info['size'].get('width', 'N/A')}x{img_info['size'].get('height', 'N/A')}\n"
            )
        img_text.append("Format: ", style="bold")
        img_text.append(f"{img_info.get('format', 'N/A')}\n")
        img_text.append("Mode: ", style="bold")
        img_text.append(f"{img_info.get('mode', 'N/A')}\n")
        img_text.append("Has Transparency: ", style="bold")
        img_text.append(f"{img_info.get('has_transparency', False)}")
        panels.append(
            Panel(
                img_text, title="[bold green]Image Properties[/]", border_style="green"
            )
        )

    # EXIF information panel
    if metadata.get("exif"):
        exif = metadata["exif"]
        exif_text = Text()
        for key, value in sorted(exif.items()):
            exif_text.append(f"{key}: ", style="bold yellow")
            value_str = str(value)
            # Truncate very long values
            if len(value_str) > 150:
                value_str = value_str[:147] + "..."
            exif_text.append(f"{value_str}\n")
        if exif_text:
            panels.append(
                Panel(
                    exif_text,
                    title="[bold magenta]EXIF Data[/]",
                    border_style="magenta",
                )
            )

    # RAW information panel
    if metadata.get("raw"):
        raw_info = metadata["raw"]
        raw_text = Text()
        for key, value in sorted(raw_info.items()):
            raw_text.append(f"{key}: ", style="bold blue")
            value_str = str(value)
            # Truncate very long values
            if len(value_str) > 150:
                value_str = value_str[:147] + "..."
            raw_text.append(f"{value_str}\n")
        if raw_text:
            panels.append(
                Panel(raw_text, title="[bold blue]RAW Metadata[/]", border_style="blue")
            )

    # Display all panels
    if panels:
        _console.print(f"\n[bold]Metadata for:[/] [cyan]{file_path}[/]\n")
        for panel in panels:
            _console.print(panel)
    else:
        _console.print(f"[yellow]No metadata found for: {file_path}[/]")

    return 0
