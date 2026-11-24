"""Fonts held out for HeOCR evaluation: never used in a training render.

The list is ``data/fonts_excluded.json`` (schema ``heocr_font_exclusion.v1``) and covers the niqqud and PH1
print tests. Every font hocrsyngen loads passes ``check_font``, which rejects excluded families, file names and hashes.

Eval's own gate-set generation may still use these faces; it sets ``HOCRSYNGEN_EVAL_RENDER=1`` for that run only.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

EXCLUSION_PATH = Path(__file__).with_name("data") / "fonts_excluded.json"
EVAL_ENV = "HOCRSYNGEN_EVAL_RENDER"


class HeldOutFontError(ValueError):
    """A held-out font was requested for a training render."""


@lru_cache(maxsize=1)
def _exclusion() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    data = json.loads(EXCLUSION_PATH.read_text(encoding="utf-8"))
    families = frozenset(f["family"].casefold().replace(" ", "") for f in data["families"])
    files = frozenset(x["file"].casefold() for f in data["families"] for x in f["files"])
    shas = frozenset(x["sha256"] for f in data["families"] for x in f["files"])
    return families, files, shas


@lru_cache(maxsize=256)
def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def is_excluded(font: str | os.PathLike[str]) -> bool:
    families, files, shas = _exclusion()
    text = str(font)
    squashed = text.casefold().replace(" ", "").replace("-", "").replace("_", "")
    if Path(text).name.casefold() in files or any(f in squashed for f in families):
        return True
    path = Path(text)
    return path.is_file() and _sha256(str(path.resolve())) in shas


def check_font(font: str | os.PathLike[str]):
    """Return ``font`` unchanged, or raise HeldOutFontError for a held-out face outside an eval render."""
    if os.environ.get(EVAL_ENV) == "1":
        return font
    if is_excluded(font):
        raise HeldOutFontError(f"held-out font refused for a training render: {font} (see {EXCLUSION_PATH.name})")
    return font
