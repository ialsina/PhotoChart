"""Sphinx configuration for the PhotoChart documentation."""

from __future__ import annotations

import sys
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from photochart._version import __version__

project = "PhotoChart"
author = "PhotoChart contributors"
copyright = "2026, PhotoChart contributors"
release = __version__
version = __version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]
if find_spec("sphinx_autodoc_typehints"):
    extensions.append("sphinx_autodoc_typehints")

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "undoc-members": False,
}
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True
todo_include_todos = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
source_suffix = ".rst"
master_doc = "index"

html_theme = "sphinx_rtd_theme" if find_spec("sphinx_rtd_theme") else "alabaster"
html_static_path = ["_static"]
html_title = "PhotoChart Documentation"

latex_engine = "pdflatex"
latex_documents = [
    (
        master_doc,
        "PhotoChart.tex",
        "PhotoChart and Unified Photo Organizer",
        author,
        "manual",
    )
]
