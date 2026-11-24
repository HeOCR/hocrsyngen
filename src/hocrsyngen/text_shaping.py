"""Font coverage and logical-text checks shared by native RTL renderers."""

from functools import lru_cache
from os import fspath
import unicodedata

from PIL import ImageFont


class ShapingError(ValueError):
    def __init__(self, reason: str, *, chars=()):
        self.reason = reason
        self.chars = list(chars)
        codes = ", ".join(f"U+{ord(char):04X}" for char in self.chars)
        super().__init__(f"{reason}: {codes}" if codes else reason)


@lru_cache(maxsize=128)
def _coverage_font(path: str):
    return ImageFont.truetype(path, 48, layout_engine=ImageFont.Layout.BASIC)


def _mask_identity(font, char):
    mask = font.getmask(char, mode="L")
    return mask.size, bytes(mask)


@lru_cache(maxsize=128)
def _notdef_identity(path: str):
    # Probe an unencoded code point through the same FreeType face and size
    # as the candidate, without bidi, ligatures or mark attachment.
    return _mask_identity(_coverage_font(path), "\U000F0000")


@lru_cache(maxsize=8192)
def _visible_glyph(path: str, char: str) -> bool:
    return _mask_identity(_coverage_font(path), char) != _notdef_identity(path)


def covers(path, char: str) -> bool:
    return (char.isspace() or unicodedata.category(char) == "Cf"
            or _visible_glyph(fspath(path), char))


def missing_characters(path, text: str) -> list[str]:
    return sorted({char for char in text if not covers(path, char)})


def check_logical_text(text: str) -> None:
    """Reject an override or a combining mark detached by a token boundary."""
    has_base = False
    for char in text:
        if char in ("\u202d", "\u202e"):
            raise ShapingError("bidi_override", chars=[char])
        category = unicodedata.category(char)
        if category.startswith("M"):
            if not has_base:
                raise ShapingError("unattached_mark", chars=[char])
        else:
            has_base = category[0] in "LN"


def check_shaping(path, text: str) -> None:
    check_logical_text(text)
    missing = missing_characters(path, text)
    if missing:
        raise ShapingError("font_missing_chars", chars=missing)


def isolated_words_safe(text: str) -> bool:
    """Whole-line shaping is required when a bidi run can span spaces."""
    return all(unicodedata.bidirectional(char) in ("R", "AL", "NSM", "WS")
               or char in ".,:;?!" for char in text)
