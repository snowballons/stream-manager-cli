"""
Sphinx configuration for StreamWatch documentation.
"""

import sys
from pathlib import Path

# Add source directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Project information
project = "StreamWatch"
copyright = "2025, Johny Snow"
author = "Johny Snow"
version = "0.4.0"
release = "0.4.0"

# Extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "myst_parser",
]

# Source file suffixes
source_suffix = {
    ".rst": None,
    ".md": None,
}

# Master document
master_doc = "index"

# HTML theme
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Napoleon settings for Google/NumPy docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# Exclude patterns
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
