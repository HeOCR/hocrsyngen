from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_simple_font_manifest(path: Path) -> dict[str, list[dict[str, str]]]:
    """Load the small governed font manifest without a YAML dependency."""

    fonts: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    saw_fonts_key = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "fonts:":
            saw_fonts_key = True
            continue
        if stripped.startswith("- "):
            if current is not None:
                fonts.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped:
                key, value = _split_manifest_pair(stripped)
                current[key] = value
            continue
        if current is None:
            continue
        key, value = _split_manifest_pair(stripped)
        current[key] = value
    if current is not None:
        fonts.append(current)
    if not saw_fonts_key:
        return {}
    return {"fonts": fonts}


def _split_manifest_pair(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ValueError(f"Malformed font manifest line: {line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip().strip('"')
