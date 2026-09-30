#!/usr/bin/env python3
"""Validate version, tag, and changelog agreement before release."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_version() -> str:
    source = (ROOT / "photochart" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', source)
    if not match:
        raise SystemExit("Could not read photochart.__version__")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected release tag, for example v0.2.0")
    args = parser.parse_args()
    version = package_version()
    expected_tag = f"v{version}"
    if args.tag and args.tag != expected_tag:
        raise SystemExit(f"Tag {args.tag!r} does not match package version {version!r}")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{expected_tag}]" not in changelog:
        raise SystemExit(f"CHANGELOG.md has no [{expected_tag}] release")
    if "## [Unreleased]" in changelog:
        unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        if re.search(r"^\s*-", unreleased, flags=re.MULTILINE):
            raise SystemExit(
                "CHANGELOG.md still contains unreleased entries; finalize "
                "them before tagging"
            )
    print(f"Release metadata is consistent for {expected_tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
