#!/usr/bin/env python3
"""Validate version, tag, and changelog agreement before release."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_version() -> str:
    from setuptools_scm import get_version

    return get_version(root=str(ROOT))


def exact_git_tag() -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--exact-match"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected release tag, for example v0.2.0")
    args = parser.parse_args()
    if args.tag:
        expected_tag = args.tag
        version = expected_tag.removeprefix("v")
        checked_out_tag = exact_git_tag()
        if checked_out_tag == expected_tag:
            scm_version = package_version()
            if scm_version != version:
                raise SystemExit(
                    f"Tag {expected_tag!r} does not match package version {scm_version!r}"
                )
    else:
        version = package_version()
        expected_tag = f"v{version}"
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
