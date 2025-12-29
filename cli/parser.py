"""
Argument parser for CLI commands.
"""

from __future__ import annotations

import argparse

try:
    from rich.table import Table
    from rich.console import Console
    from rich.panel import Panel

    _console = Console()
except Exception:
    Table = None
    Panel = None
    _console = None

from .commands import (
    cmd_ingest,
    cmd_convert,
    cmd_list_resolutions,
    cmd_info,
    HAS_RICH,
)


def _print_help_for(parser: argparse.ArgumentParser):
    def _f(args: argparse.Namespace) -> int:
        if not HAS_RICH:
            parser.print_help()
            return 2

        # Attempt to render a nicer help using Rich
        prog = parser.prog or "pf"
        desc = parser.description or ""
        table = Table(title=f"[bold cyan]{prog}[/] - {desc}")
        table.add_column("[bold]Command[/]", style="bold yellow")
        table.add_column("[bold]Description[/]", style="white")

        # Iterate subcommands if present
        subparsers_actions = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if subparsers_actions:
            for subparsers_action in subparsers_actions:
                for name, sp in subparsers_action.choices.items():
                    help_text = (
                        getattr(sp, "description", None)
                        or sp.format_help().splitlines()[0]
                    )
                    table.add_row(f"{name}", help_text)
        else:
            # Fallback to plain help
            parser.print_help()
            return 2

        # Render global options
        opts = []
        for action in parser._actions:
            # Exclude help and subparsers
            if isinstance(action, argparse._SubParsersAction):
                continue
            if any(s in ("-h", "--help") for s in action.option_strings):
                continue
            if action.option_strings:
                opt_names = ", ".join(action.option_strings)
                help_text = action.help or ""
                opts.append((opt_names, help_text))

        if opts:
            opt_table = Table(title="[bold magenta]Global options[/]")
            opt_table.add_column("[bold]Option[/]", style="bold cyan")
            opt_table.add_column("[bold]Description[/]", style="white")
            for name, help_text in opts:
                opt_table.add_row(name, help_text)
            _console.print(Panel.fit(opt_table))

        _console.print(Panel.fit(table, title=f"[bold green]{prog} help[/]"))
        return 2

    return _f


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    p = argparse.ArgumentParser(
        prog="pf",
        description="PhotoChart CLI - manage and organize photo collections",
    )
    sub = p.add_subparsers(dest="command")
    try:
        sub.required = False  # ensure no error when no top-level subcommand
    except Exception:
        pass

    # ingest
    p_ing = sub.add_parser(
        "ingest",
        help="Ingest photos from a directory",
        description="Ingest photos from a directory, calculate hashes, and persist to database",
    )
    p_ing.add_argument(
        "path",
        help="Path to directory or file to ingest",
    )
    p_ing.add_argument(
        "--resolution",
        help=(
            "Optional resolution for the image. Can be explicit (e.g., '1920x1080') "
            "or a preset name (e.g., 'low', 'medium', 'high', '4k', '1080p', '720p'). "
            "Use 'pf list-resolutions' to see all available presets."
        ),
    )
    p_ing.add_argument(
        "--hash",
        action="store_true",
        help="Calculate and store hash for each photo",
    )
    p_ing.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not recursively search subdirectories",
    )
    p_ing.add_argument(
        "--store-images",
        action="store_true",
        help="Store image files in the database media directory. If --resolution is specified, images will be resized accordingly.",
    )
    p_ing.set_defaults(func=cmd_ingest)

    # convert
    p_conv = sub.add_parser(
        "convert",
        help="Convert an image to a standard format",
        description="Convert an image file to a standard format (e.g., JPEG) with optional resizing",
    )
    p_conv.add_argument(
        "source",
        help="Path to the source image file",
    )
    p_conv.add_argument(
        "--output",
        "-o",
        help="Path to the output image file (defaults to the same path as input with appropriate extension)",
    )
    p_conv.add_argument(
        "--resolution",
        help=(
            "Optional resolution for the output image. Can be explicit (e.g., '1920x1080') "
            "or a preset name (e.g., 'low', 'medium', 'high', '4k', '1080p', '720p'). "
            "Use 'pf list-resolutions' to see all available presets. "
            "If not specified, original resolution is preserved."
        ),
    )
    p_conv.add_argument(
        "--format",
        default="JPEG",
        choices=["JPEG", "PNG"],
        help="Output format (default: JPEG)",
    )
    p_conv.set_defaults(func=cmd_convert)

    # list-resolutions
    p_res = sub.add_parser(
        "list-resolutions",
        help="List all available resolution presets",
        description="Display all available resolution presets that can be used with --resolution",
    )
    p_res.set_defaults(func=cmd_list_resolutions)

    # info
    p_info = sub.add_parser(
        "info",
        help="Show metadata for a raw image",
        description="Display all available metadata from a raw image file, including EXIF data and RAW-specific information",
    )
    p_info.add_argument(
        "file",
        help="Path to the image file to inspect",
    )
    p_info.set_defaults(func=cmd_info)

    return p


def _expand_abbreviations(
    argv: list[str], parser: argparse.ArgumentParser
) -> list[str]:
    """Expand unique-prefix abbreviations for subcommands (e.g., i->ingest)."""
    if not argv:
        return argv

    # Map top-level subcommands
    sub_actions = [
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    ]
    if sub_actions:
        choices = sub_actions[0].choices
        if len(argv) >= 1:
            token = argv[0]
            if token not in choices:
                matches = [name for name in choices if name.startswith(token)]
                if len(matches) == 1:
                    argv = [matches[0]] + argv[1:]

    return argv
