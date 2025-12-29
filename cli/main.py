"""
Main entry point for CLI.
"""

from __future__ import annotations

import sys
import os
from typing import Optional

# Setup Django environment before importing Django models
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Add project root to path first (so photochart can be found)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Also add backend directory to path so Django apps can be found
backend_dir = os.path.join(project_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backend.settings")

import django

django.setup()

from .parser import build_parser, _expand_abbreviations, _print_help_for
from .commands import HAS_RICH


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else argv
    argv = _expand_abbreviations(argv, parser)
    args = parser.parse_args(argv)

    # Django doesn't need database configuration like SQLAlchemy did
    # The database is configured via Django settings

    if not hasattr(args, "func"):
        # Top-level invoked without subcommand: show fancy help if available
        if HAS_RICH:
            _print_help_for(parser)(args)
            return 2
        parser.print_help()
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
