"""
CLI module for PhotoFinder Django backend.

This module provides command-line interface for managing photo collections.
"""

from .main import main
from .parser import _expand_abbreviations, _print_help_for, build_parser
from .commands import (
    cmd_ingest,
    cmd_convert,
    HAS_RICH,
)

__all__ = [
    "build_parser",
    "main",
    "cmd_ingest",
    "cmd_convert",
    "_expand_abbreviations",
    "_print_help_for",
    "HAS_RICH",
]
