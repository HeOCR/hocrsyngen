from __future__ import annotations

from importlib import resources
from pathlib import Path


def synthetic_data_path(relative_path: str) -> Path:
    """Return a filesystem path for packaged synthetic data.

    Note: This function requires the package to be installed into a regular
    filesystem directory (not a zip/egg archive). Pillow's FreeType font loader
    requires a real filesystem path for TTF files, making zip-installed
    packages incompatible with this package's font rendering.
    """

    root = resources.files("hocrsyngen") / "data" / "synthetic"
    return Path(str(root / relative_path))


def default_font_manifest_path() -> Path:
    return synthetic_data_path("fonts/manifest.yaml")


def default_text_corpus_path() -> Path:
    return synthetic_data_path("texts/hebrew_lines.txt")
