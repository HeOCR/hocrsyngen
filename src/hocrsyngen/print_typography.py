"""Opt-in print typography with logical labels and pixel-edge annotations."""

from dataclasses import dataclass
import math
import random
import unicodedata

from PIL import Image, ImageDraw

from .line_render import _font, _require_raqm, face_weight, governed_faces, missing_chars


@dataclass(frozen=True)
class Paragraph:
    role: str
    text: str


@dataclass(frozen=True)
class PrintPage:
    image: Image.Image
    lines: list[dict]


# Role style ranges are design probes in em units relative to the body size.
# Use coherent pools and vary the layout before applying scanner optics.
STYLES = {
    "book": {
        "heading": (("frank-ruhl-libre", "david-libre-regular"), (1.25, 1.40), 580),
        "body": (("frank-ruhl-libre", "david-libre-regular"), (1.0, 1.0), 450),
        "note": (("david-libre-regular", "frank-ruhl-libre"), (0.72, 0.82), 425),
        "label": (("frank-ruhl-libre",), (0.84, 0.94), 520),
    },
    "gazette": {
        "heading": (("tinos-bold", "noto-serif-hebrew"), (1.18, 1.32), 650),
        "body": (("tinos-regular", "noto-serif-hebrew"), (1.0, 1.0), 440),
        "note": (("tinos-regular", "noto-serif-hebrew"), (0.72, 0.82), 420),
        "label": (("tinos-bold", "noto-serif-hebrew"), (0.82, 0.95), 620),
    },
}


def _wrap(draw, text, font, width):
    line = ""
    for word in text.split(" "):
        combined = f"{line} {word}" if line else word
        if line and draw.textlength(combined, font=font, direction="rtl") > width:
            yield line
            line = word
        else:
            line = combined
    yield line


def _line_runs(draw, text, font, left, right, justify):
    """Stretch spaces only when isolated words retain their visual bidi order."""
    words = text.split(" ")
    pure_rtl = all(unicodedata.bidirectional(c) in ("R", "AL", "NSM", "WS")
                   or c in ".,:;?!" for c in text)
    if justify and pure_rtl and len(words) > 1:
        widths = [draw.textlength(word, font=font, direction="rtl") for word in words]
        gap = (right - left - sum(widths)) / (len(words) - 1)
        natural = draw.textlength(" ", font=font, direction="rtl")
        if natural <= gap <= 4 * natural:
            x = right
            runs = []
            for word, width in zip(words, widths, strict=True):
                runs.append((x, word))
                x -= width + gap
            return runs
    # Mixed-script and punctuation-sensitive lines must be shaped together.
    return [(right, text)]


def render_print_page(paragraphs, *, seed, source_type, size=(950, 1260),
                      body_px=32, margin=(95, 100), justify=True):
    """Render authored paragraphs with role sizes and RTL wrapping.

    Paragraph text must be NFC and single-space separated. The output lines
    reconstruct each paragraph exactly when joined with spaces. Text that
    cannot be represented or is too large for the requested page is rejected.
    """
    _require_raqm()
    if source_type not in STYLES or type(seed) is not int or seed < 0:
        raise ValueError("expected a print source type and nonnegative seed")
    width, height = size
    side, top = margin
    if not (12 <= body_px <= 96 and 0 <= side < width / 2 and 0 <= top < height / 2):
        raise ValueError("invalid page geometry or body size")
    rng = random.Random(seed)
    faces = governed_faces()
    styles = {}
    for role, (pool, sizes, wanted_weight) in STYLES[source_type].items():
        face = faces[rng.choice(pool)]
        weight, _ = face_weight(face, wanted_weight)
        font = _font(str(face.path), round(body_px * rng.uniform(*sizes)), weight)
        styles[role] = face, font, weight

    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    right = width - side
    y = top
    records = []
    for index, paragraph in enumerate(paragraphs):
        if paragraph.role not in styles:
            raise ValueError(f"unknown print role {paragraph.role!r}")
        text = paragraph.text
        if (not text or text != " ".join(text.split())
                or not unicodedata.is_normalized("NFC", text)):
            raise ValueError("expected NFC text with single spaces and no surrounding whitespace")
        face, font, weight = styles[paragraph.role]
        if missing_chars(face, text):
            raise ValueError(f"font {face.id} cannot represent the paragraph")
        body = paragraph.role in ("body", "note")
        rows = list(_wrap(draw, text, font, right - side)) if body else [text]
        ascent, descent = font.getmetrics()
        for position, row in enumerate(rows):
            runs = _line_runs(draw, row, font, side, right,
                              justify and body and position < len(rows) - 1)
            baseline = y + ascent
            boxes = [draw.textbbox((x, baseline), word, font=font, anchor="rs", direction="rtl")
                     for x, word in runs]
            box = [math.floor(min(b[0] for b in boxes)), math.floor(min(b[1] for b in boxes)),
                   math.ceil(max(b[2] for b in boxes)), math.ceil(max(b[3] for b in boxes))]
            if not (max(0, side - 1) <= box[0] < box[2] <= min(width, right + 1)
                    and 0 <= box[1] < box[3] <= height - top):
                raise ValueError(f"paragraph {index} does not fit the print frame")
            for x, word in runs:
                draw.text((x, baseline), word, font=font, anchor="rs", direction="rtl", fill="#231e1b")
            records.append({
                "role": paragraph.role, "paragraph": index, "text": row, "box": box,
                "baseline": [[box[2], baseline], [box[0], baseline]],
                "font": face.id, "font_sha256": face.sha256, "font_size_px": font.size,
                "font_weight": weight, "justified": len(runs) > 1,
            })
            y += max(ascent + descent, round(font.size * 1.35))
        y += round(body_px * rng.uniform(0.30, 0.63))
    if not records:
        raise ValueError("expected at least one paragraph")
    return PrintPage(image, records)
