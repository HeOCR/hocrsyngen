"""Build a small ``printed_glyph_bank.v1`` at test time from a packaged font.

Glyphs are rendered one character at a time into grayscale crops on a noisy
paper tone, with a thresholded ink mask, so the bank has the shape of a real
harvest without shipping image assets.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from hocrsyngen.assets import synthetic_data_path


HEBREW_LETTERS = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
DIGITS = "0123456789"
PUNCTUATION = ".,:;-()?!׳'\""


@dataclass(frozen=True)
class FixtureStyle:
    style_id: str
    font_file: str
    font_size: int
    chars: str
    variants: int = 3
    page_size: tuple[int, int] = (1500, 2100)
    text_block_width: int = 1100
    licence: str = "PD"
    attribution: str | None = None
    heading_size: int | None = None


DEFAULT_STYLES = (
    FixtureStyle(
        style_id="fx-alef",
        font_file="Alef-Regular.ttf",
        font_size=40,
        chars=HEBREW_LETTERS + DIGITS + PUNCTUATION,
        heading_size=60,
    ),
    FixtureStyle(
        style_id="fx-alef-columns",
        font_file="Alef-Regular.ttf",
        font_size=32,
        chars=HEBREW_LETTERS + ".,:-׳",
        page_size=(1500, 2200),
        text_block_width=560,
        variants=2,
    ),
)


def _paper_patch(rng: random.Random, size: int, tone: int) -> Image.Image:
    noise = Image.frombytes("L", (size // 4, size // 4), rng.randbytes((size // 4) ** 2))
    noise = noise.resize((size, size), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(2))
    return noise.point(lambda value: max(0, min(255, tone + (value - 128) // 10)))


def _render_glyph(
    rng: random.Random, font: ImageFont.FreeTypeFont, char: str, paper: int, ink: int, bold: int = 0
) -> tuple[Image.Image, Image.Image, tuple[int, int, int, int], int]:
    ascent, descent = font.getmetrics()
    pad = 6
    left, _top, right, _bottom = font.getbbox(char, anchor="ls", stroke_width=bold)
    width = max(1, right - left) + 2 * pad
    height = ascent + descent + 2 * pad
    baseline = pad + ascent
    canvas = Image.new("L", (width, height), paper)
    draw = ImageDraw.Draw(canvas)
    draw.text((pad - left, baseline), char, font=font, fill=ink, anchor="ls", stroke_width=bold, stroke_fill=ink)
    if rng.random() < 0.5:
        canvas = canvas.rotate(rng.uniform(-2.0, 2.0), resample=Image.Resampling.BICUBIC, fillcolor=paper)
    grain = Image.frombytes("L", canvas.size, rng.randbytes(width * height))
    canvas = Image.blend(canvas, grain, 0.06)
    threshold = (paper + ink) // 2
    mask = canvas.point(lambda value: 255 if value < threshold else 0)
    box = mask.getbbox()
    if box is None:
        raise AssertionError(f"fixture glyph {char!r} rendered no ink")
    return canvas, mask, box, baseline


def build_fixture_bank(
    root: Path,
    styles: tuple[FixtureStyle, ...] = DEFAULT_STYLES,
    *,
    seed: int = 7,
    paper_gray: int = 226,
    ink_gray: int = 42,
    bold_letters: bool = False,
) -> Path:
    """Write the bank under ``root``. With ``bold_letters`` one extra body-size
    variant of every Hebrew letter is drawn with a 2 px stroke (bold) and its
    record carries ``"fixture_bold": true``."""
    rng = random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    index_styles: list[dict] = []
    for style in styles:
        style_dir = root / "styles" / style.style_id
        (style_dir / "glyphs").mkdir(parents=True, exist_ok=True)
        (style_dir / "paper").mkdir(parents=True, exist_ok=True)
        font_path = synthetic_data_path(f"fonts/{style.font_file}")
        x_height_ratio = None
        sizes = [(style.font_size, style.variants)]
        if style.heading_size:
            sizes.append((style.heading_size, 3))
        counter = 0
        char_counts: dict[str, int] = {}
        for base_size, variants in sizes:
            for char in style.chars:
                extra = 1 if bold_letters and base_size == style.font_size and char in HEBREW_LETTERS else 0
                for variant in range(variants + extra):
                    bold = 2 if variant == variants else 0
                    size = round(base_size * rng.uniform(0.96, 1.04))
                    font = ImageFont.truetype(str(font_path), size)
                    _l, top, _r, bottom = font.getbbox("ה", anchor="ls")
                    x_height = float(bottom - top)
                    if base_size == style.font_size:
                        x_height_ratio = x_height_ratio or x_height / size
                    crop, mask, box, baseline = _render_glyph(
                        rng, font, char, paper_gray + rng.randint(-4, 4), ink_gray + rng.randint(-6, 6), bold
                    )
                    glyph_id = f"{style.style_id}-{counter:06d}"
                    counter += 1
                    asset = f"styles/{style.style_id}/glyphs/{glyph_id}.png"
                    mask_path = f"styles/{style.style_id}/glyphs/{glyph_id}.mask.png"
                    crop.save(root / asset)
                    mask.convert("1").save(root / mask_path)
                    char_counts[char] = char_counts.get(char, 0) + 1
                    records.append(
                        {
                            "glyph_id": glyph_id,
                            "style_id": style.style_id,
                            "char": char,
                            "asset_path": asset,
                            "mask_path": mask_path,
                            "size": list(crop.size),
                            "ink_box": list(box),
                            "baseline_y": baseline,
                            "x_height_px": x_height,
                            "source": {
                                "page_id": f"fixture:{style.style_id}:p{counter % 4:04d}",
                                "box_in_source": [0, 0, crop.size[0], crop.size[1]],
                                "word_index": counter,
                                "position_in_word": 0,
                            },
                            "quality": {"method": "fixture_render", "score": round(rng.uniform(0.5, 1.0), 3)},
                            **({"fixture_bold": True} if bold else {}),
                        }
                    )
        patches = []
        for patch_index in range(3):
            patch_path = f"styles/{style.style_id}/paper/p{patch_index:03d}.png"
            _paper_patch(rng, 160, paper_gray).save(root / patch_path)
            patches.append(patch_path)
        x_height = round((x_height_ratio or 0.5) * style.font_size, 2)
        index_styles.append(
            {
                "style_id": style.style_id,
                "source_id": "fixture_font_render",
                "work_id": style.style_id,
                "licence": style.licence,
                "attribution": style.attribution,
                "born_digital": True,
                "metrics": {
                    "x_height_px": x_height,
                    "line_pitch_px": round(style.font_size * 1.25, 1),
                    "letter_gap_px": [0.0, 1.5, 3.0],
                    "word_gap_px": [round(style.font_size * 0.22, 1), round(style.font_size * 0.28, 1), round(style.font_size * 0.4, 1)],
                    "text_block_width_px": style.text_block_width,
                    "page_size_px": list(style.page_size),
                    "ink_gray": ink_gray,
                    "paper_gray": paper_gray,
                },
                "paper_patches": patches,
                "glyph_count": sum(char_counts.values()),
                "char_counts": char_counts,
            }
        )
    glyphs_bytes = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records).encode()
    (root / "glyphs.jsonl").write_bytes(glyphs_bytes)
    index = {
        "schema": "printed_glyph_bank.v1",
        "bank_id": "pgb-fixture",
        "created_by": {"tool": "tests.glyph_bank_fixture", "version": "1", "config_sha256": "0" * 64},
        "glyph_count": len(records),
        "glyphs_sha256": hashlib.sha256(glyphs_bytes).hexdigest(),
        "sources": [{"source_id": "fixture_font_render", "licence": "PD", "notes": "rendered from a packaged OFL font"}],
        "exclusions": [],
        "styles": index_styles,
    }
    (root / "printed_glyph_bank.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def rewrite_index(root: Path, mutate) -> None:
    path = root / "printed_glyph_bank.json"
    index = json.loads(path.read_text(encoding="utf-8"))
    mutate(index)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def rewrite_glyphs(root: Path, mutate) -> None:
    """Apply ``mutate`` to the glyph record list and refresh the index hash."""

    path = root / "glyphs.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    mutate(records)
    data = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records).encode()
    path.write_bytes(data)
    rewrite_index(root, lambda index: index.update(glyphs_sha256=hashlib.sha256(data).hexdigest()))
