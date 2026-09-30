"""Package version derived from git release tags (``v*``)."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _resolve_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("PhotoChart")
    except PackageNotFoundError:
        pass

    from setuptools_scm import get_version

    return get_version(root=str(_ROOT))


__version__ = _resolve_version()
