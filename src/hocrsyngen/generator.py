from __future__ import annotations

import json
import random
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, features

from hocrsyngen.assets import default_font_manifest_path, default_text_corpus_path
from hocrsyngen.io import load_simple_font_manifest, sha256_file
from hocrsyngen.manifest import (
    GeneratedSample,
    GenerationManifest,
    PageAsset,
    SampleControls,
    SampleProvenance,
    TextMetadata,
)


GENERATOR_VERSION = "d4a-realism-v2"
CANVAS_SIZE = (1200, 1600)
PAPER_MARGIN = 96
DEFAULT_TEMPLATE_IDS = ["printed_letter", "handwritten_note"]

PRINTED_TITLES = ["מכתב מנהלי", "דו\"ח קבלה", "רישום ארכיוני"]
HANDWRITTEN_TITLES = ["פנקס הערות", "רישום קצר", "הודעה פנימית"]
FOOTER_LABELS = ["סימן", "רישום", "עמוד"]


@dataclass(frozen=True)
class SyntheticRecipe:
    template_id: str
    recipe_id: str
    layout_style: str
    font_style: str
    degradation_preset: str
    paper_tone: str
    line_count: int
    jpeg_quality: int


@dataclass(frozen=True)
class SyntheticDocument:
    sample_id: str
    sample_index: int
    title: str
    body: str
    footer: str
    template_id: str
    recipe_id: str
    degradation_preset: str
    font_id: str
    path: Path
    asset_path: str
    sha256: str
    generator_version: str
    logical_text: str


@dataclass(frozen=True)
class TemplateCatalogEntry:
    template_id: str
    recipe_id: str
    layout_style: str
    font_style: str
    font_id: str
    degradation_preset: str


def load_font_manifest(path: Path) -> dict[str, list[dict[str, str]]]:
    return load_simple_font_manifest(path)


def load_text_corpus(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _font_path(manifest_path: Path, font_entry: dict[str, str]) -> Path:
    file_name = str(font_entry.get("file", "")).strip()
    if not file_name:
        raise ValueError(f"Synthetic font entry is missing a file reference: {font_entry.get('id', '<unknown>')}")
    file_path = PurePosixPath(file_name)
    if file_path.is_absolute() or file_path.name != file_name or "\\" in file_name or ".." in file_path.parts:
        raise ValueError(f"Synthetic font file reference must be a flat relative filename: {file_name}")
    path = (manifest_path.parent / file_name).resolve()
    if not path.exists():
        raise ValueError(f"Synthetic font file is missing: {path}")
    return path


@lru_cache(maxsize=1)
def _pillow_has_raqm() -> bool:
    return bool(features.check("raqm"))


def _require_raqm() -> None:
    if not _pillow_has_raqm():
        raise RuntimeError("hocrsyngen requires Pillow with libraqm support for Hebrew RTL rendering.")


@lru_cache(maxsize=32)
def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path), size)


def _validate_font(font_path: Path) -> None:
    try:
        _load_font(font_path, 16)
    except OSError as exc:
        raise ValueError(f"Synthetic font file is invalid or unreadable: {font_path}") from exc


def _wrap_hebrew_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    _require_raqm()
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        left, _top, right, _bottom = draw.textbbox((0, 0), candidate, font=font, direction="rtl")
        width = right - left
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _rtl_display_text(text: str) -> str:
    # Pillow's direction="rtl" parameter handles BiDi reordering; this
    # pass-through exists as an explicit extension point for any future
    # pre-processing (e.g. Unicode Bidirectional Algorithm overrides).
    return text


def _draw_rtl_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    anchor: str = "ra",
) -> None:
    _require_raqm()
    draw.text(xy, _rtl_display_text(text), font=font, fill=fill, anchor=anchor, direction="rtl")


def _paper_background(randomizer: random.Random, size: tuple[int, int], tone: str) -> Image.Image:
    base = (246, 241, 230) if tone == "printed" else (243, 235, 220)
    image = Image.new("RGB", size, base)
    noise = Image.frombytes("L", size, randomizer.randbytes(size[0] * size[1]))
    noise = noise.point(lambda value: int(128 + ((value - 128) * 0.08)))
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    textured = ImageChops.add(image, noise_rgb, scale=1.0, offset=-128)
    return Image.blend(image, textured, alpha=0.05)


def _apply_grain(image: Image.Image, randomizer: random.Random) -> Image.Image:
    noise = Image.frombytes("L", image.size, randomizer.randbytes(image.size[0] * image.size[1]))
    noise = noise.point(lambda value: int(96 + ((value - 128) * 0.22)))
    textured = ImageChops.add_modulo(image.convert("RGB"), Image.merge("RGB", (noise, noise, noise)))
    return Image.blend(image, textured, alpha=0.08)


def _degrade(image: Image.Image, randomizer: random.Random, background: tuple[int, int, int], preset: str) -> Image.Image:
    if preset == "notebook_scan_worn":
        angle_range = 1.5
        blur_range = (0.25, 0.75)
        contrast = 0.92
        brightness = 0.97
        grain_passes = 2
    else:
        angle_range = 0.85
        blur_range = (0.15, 0.45)
        contrast = 0.96
        brightness = 0.99
        grain_passes = 1

    angle = randomizer.uniform(-angle_range, angle_range)
    degraded = image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=background)
    degraded = degraded.filter(ImageFilter.GaussianBlur(radius=randomizer.uniform(*blur_range)))
    for _ in range(grain_passes):
        degraded = _apply_grain(degraded, randomizer)
    degraded = ImageEnhance.Contrast(degraded).enhance(contrast)
    degraded = ImageEnhance.Brightness(degraded).enhance(brightness)
    return degraded


def _recipe_for_template(template_id: str) -> SyntheticRecipe:
    if template_id == "printed_letter":
        return SyntheticRecipe(
            template_id=template_id,
            recipe_id="printed_letter_form_v1",
            layout_style="printed_form",
            font_style="printed",
            degradation_preset="office_scan_soft",
            paper_tone="printed",
            line_count=4,
            jpeg_quality=82,
        )
    if template_id == "handwritten_note":
        return SyntheticRecipe(
            template_id=template_id,
            recipe_id="handwritten_note_marginalia_v1",
            layout_style="handwritten_note",
            font_style="handwritten_like",
            degradation_preset="notebook_scan_worn",
            paper_tone="handwritten",
            line_count=3,
            jpeg_quality=78,
        )
    raise ValueError(f"Unsupported synthetic template_id: {template_id}")


def recipe_catalog(template_ids: list[str]) -> dict[str, SyntheticRecipe]:
    return {template_id: _recipe_for_template(template_id) for template_id in template_ids}


def _load_font_entries(font_manifest_path: Path) -> list[dict[str, str]]:
    font_manifest = load_font_manifest(font_manifest_path)
    fonts = font_manifest.get("fonts")
    if not isinstance(fonts, list):
        raise ValueError(f"Synthetic font manifest is missing a valid 'fonts' list: {font_manifest_path}")
    if not fonts:
        raise ValueError(f"Synthetic font manifest has no registered fonts: {font_manifest_path}")
    return fonts


def template_catalog(
    template_ids: list[str] | None = None,
    *,
    font_manifest_path: Path | None = None,
) -> list[TemplateCatalogEntry]:
    template_ids = DEFAULT_TEMPLATE_IDS if template_ids is None else template_ids
    font_manifest_path = font_manifest_path or default_font_manifest_path()
    recipes = recipe_catalog(template_ids)
    fonts = _load_font_entries(font_manifest_path)
    catalog: list[TemplateCatalogEntry] = []
    for template_id in template_ids:
        recipe = recipes[template_id]
        font_entry = _select_font(fonts, template_id)
        _font_path(font_manifest_path, font_entry)
        font_id = str(font_entry.get("id", "")).strip()
        if not font_id:
            raise ValueError(f"Synthetic font entry is missing an id for style: {recipe.font_style}")
        catalog.append(
            TemplateCatalogEntry(
                template_id=recipe.template_id,
                recipe_id=recipe.recipe_id,
                layout_style=recipe.layout_style,
                font_style=recipe.font_style,
                font_id=font_id,
                degradation_preset=recipe.degradation_preset,
            )
        )
    return catalog


def _draw_paper_frame(draw: ImageDraw.ImageDraw, randomizer: random.Random, handwritten: bool) -> None:
    edge = (193, 181, 158) if handwritten else (203, 195, 176)
    shadow = (220, 211, 191) if handwritten else (226, 219, 202)
    left = PAPER_MARGIN - randomizer.randint(8, 18)
    top = PAPER_MARGIN - randomizer.randint(4, 16)
    right = CANVAS_SIZE[0] - PAPER_MARGIN + randomizer.randint(8, 16)
    bottom = CANVAS_SIZE[1] - PAPER_MARGIN + randomizer.randint(6, 18)
    draw.rectangle((left + 10, top + 12, right + 10, bottom + 12), outline=shadow, width=3)
    draw.rectangle((left, top, right, bottom), outline=edge, width=2)
    if not handwritten:
        draw.line((left + 36, top, left + 36, bottom), fill=(224, 214, 195), width=2)


def _draw_creased_paper(draw: ImageDraw.ImageDraw, randomizer: random.Random, handwritten: bool) -> None:
    crease_color = (225, 216, 196) if handwritten else (231, 224, 207)
    for _ in range(3 if handwritten else 2):
        x = randomizer.randint(PAPER_MARGIN + 40, CANVAS_SIZE[0] - PAPER_MARGIN - 40)
        wobble = randomizer.randint(-12, 12)
        draw.line((x, PAPER_MARGIN, x + wobble, CANVAS_SIZE[1] - PAPER_MARGIN), fill=crease_color, width=1)
    for _ in range(2):
        y = randomizer.randint(PAPER_MARGIN + 80, CANVAS_SIZE[1] - PAPER_MARGIN - 80)
        draw.line((PAPER_MARGIN, y, CANVAS_SIZE[0] - PAPER_MARGIN, y + randomizer.randint(-8, 8)), fill=crease_color, width=1)


def _draw_stains(image: Image.Image, randomizer: random.Random, handwritten: bool) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    count = 5 if handwritten else 3
    for _ in range(count):
        x = randomizer.randint(PAPER_MARGIN, CANVAS_SIZE[0] - PAPER_MARGIN)
        y = randomizer.randint(PAPER_MARGIN, CANVAS_SIZE[1] - PAPER_MARGIN)
        rx = randomizer.randint(18, 62 if handwritten else 44)
        ry = randomizer.randint(12, 46 if handwritten else 32)
        color = (149, 118, 72, randomizer.randint(14, 28))
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=color)
    image.alpha_composite(overlay)


def _draw_printed_form_guides(draw: ImageDraw.ImageDraw, randomizer: random.Random) -> None:
    guide = (184, 174, 154)
    faint = (215, 207, 188)
    left = PAPER_MARGIN + 56
    right = CANVAS_SIZE[0] - PAPER_MARGIN - 56
    top = PAPER_MARGIN + 250
    row_height = 92
    for row in range(5):
        y = top + row * row_height + randomizer.randint(-2, 2)
        draw.line((left, y, right, y), fill=faint, width=2)
        if row < 4:
            label_x = right - randomizer.randint(6, 18)
            draw.line((label_x - 220, y + 42, label_x, y + 42), fill=guide, width=1)
    box_top = top + 5 * row_height + 54
    draw.rectangle((left, box_top, right, box_top + 220), outline=faint, width=2)
    for offset in (180, 390, 620):
        draw.line((right - offset, box_top, right - offset, box_top + 220), fill=faint, width=1)


def _draw_stamp(draw: ImageDraw.ImageDraw, randomizer: random.Random, font: ImageFont.FreeTypeFont) -> None:
    center_x = PAPER_MARGIN + randomizer.randint(150, 260)
    center_y = PAPER_MARGIN + randomizer.randint(135, 245)
    radius_x = randomizer.randint(92, 118)
    radius_y = randomizer.randint(44, 58)
    color = (129, 47, 41)
    draw.ellipse((center_x - radius_x, center_y - radius_y, center_x + radius_x, center_y + radius_y), outline=color, width=4)
    _draw_rtl_text(draw, (center_x + 62, center_y - 13), "נבדק", font=font, fill=color)


def _draw_handwritten_guides(draw: ImageDraw.ImageDraw, randomizer: random.Random) -> None:
    guide = (209, 198, 177)
    for row in range(10):
        y = PAPER_MARGIN + 210 + row * 92 + randomizer.randint(-5, 5)
        draw.line((PAPER_MARGIN + 65, y, CANVAS_SIZE[0] - PAPER_MARGIN - 70, y), fill=guide, width=1)


def _draw_marginalia(draw: ImageDraw.ImageDraw, randomizer: random.Random, font: ImageFont.FreeTypeFont) -> None:
    notes = ["נבדק", "להמשך", "עותק"]
    x = PAPER_MARGIN + randomizer.randint(60, 150)
    y = PAPER_MARGIN + randomizer.randint(430, 680)
    note = notes[randomizer.randrange(len(notes))]
    _draw_rtl_text(draw, (x + 115, y), note, font=font, fill=(88, 68, 48))
    draw.line((x, y + 44, x + 120, y + 32), fill=(88, 68, 48), width=2)
    for _ in range(2):
        sx = x + randomizer.randint(5, 95)
        sy = y + randomizer.randint(60, 140)
        draw.arc((sx, sy, sx + 70, sy + 32), start=190, end=345, fill=(94, 72, 50), width=2)


def _draw_handwritten_underline(draw: ImageDraw.ImageDraw, randomizer: random.Random, x: int, y: int, width: int) -> None:
    points = []
    for step in range(0, width, 24):
        points.append((x - step, y + randomizer.randint(-2, 3)))
    if len(points) > 1:
        draw.line(points, fill=(56, 44, 34), width=2)


def _draw_document(
    randomizer: random.Random,
    title: str,
    body_lines: list[str],
    footer: str,
    font_path: Path,
    template_id: str,
) -> Image.Image:
    recipe = _recipe_for_template(template_id)
    form_layout = recipe.layout_style == "printed_form"
    handwritten_text = recipe.font_style == "handwritten_like"
    background = (246, 241, 230) if form_layout else (243, 235, 220)
    image = _paper_background(randomizer, CANVAS_SIZE, recipe.paper_tone).convert("RGBA")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(font_path, 62 if not handwritten_text else 66)
    body_font = _load_font(font_path, 42 if not handwritten_text else 46)
    footer_font = _load_font(font_path, 28)
    annotation_font = _load_font(font_path, 30 if handwritten_text else 26)

    _draw_paper_frame(draw, randomizer, handwritten=not form_layout)
    _draw_creased_paper(draw, randomizer, handwritten=not form_layout)
    if form_layout:
        _draw_printed_form_guides(draw, randomizer)
        _draw_stamp(draw, randomizer, annotation_font)
    else:
        _draw_handwritten_guides(draw, randomizer)
        _draw_marginalia(draw, randomizer, annotation_font)
    _draw_stains(image, randomizer, handwritten=not form_layout)

    title_x = CANVAS_SIZE[0] - PAPER_MARGIN - randomizer.randint(0, 24)
    title_y = PAPER_MARGIN + randomizer.randint(4, 24)
    _draw_rtl_text(draw, (title_x, title_y), title, font=title_font, fill=(34, 29, 24, 255))

    body_top = title_y + (132 if form_layout else 118)
    max_width = CANVAS_SIZE[0] - (2 * PAPER_MARGIN) - 40
    wrapped_lines: list[str] = []
    for line in body_lines:
        wrapped_lines.extend(_wrap_hebrew_text(draw, line, body_font, max_width))

    line_height = 76 if handwritten_text else 68
    start_x = CANVAS_SIZE[0] - PAPER_MARGIN - randomizer.randint(0, 20)
    for index, line in enumerate(wrapped_lines):
        x = start_x - randomizer.randint(0, 28 if handwritten_text else 6)
        y = body_top + index * line_height + randomizer.randint(-10 if handwritten_text else -2, 8 if handwritten_text else 2)
        ink = randomizer.randint(-8, 7)
        fill = (max(18, 33 + ink), max(16, 28 + ink), max(12, 23 + ink), 255)
        _draw_rtl_text(draw, (x, y), line, font=body_font, fill=fill)
        if not form_layout and index in {0, len(wrapped_lines) - 1}:
            _draw_handwritten_underline(draw, randomizer, x - 5, y + 52, min(360, max_width // 2))

    footer_x = CANVAS_SIZE[0] - PAPER_MARGIN - randomizer.randint(12, 48)
    footer_y = CANVAS_SIZE[1] - PAPER_MARGIN - randomizer.randint(8, 24)
    _draw_rtl_text(draw, (footer_x, footer_y), footer, font=footer_font, fill=(93, 82, 70, 255))

    if not form_layout:
        for _ in range(3):
            x = randomizer.randint(PAPER_MARGIN + 120, CANVAS_SIZE[0] - PAPER_MARGIN - 180)
            y = randomizer.randint(CANVAS_SIZE[1] - PAPER_MARGIN - 220, CANVAS_SIZE[1] - PAPER_MARGIN - 120)
            radius = randomizer.randint(18, 34)
            draw.arc((x, y, x + radius * 3, y + radius), start=180, end=360, fill=(63, 50, 38, 255), width=2)
    else:
        for column in range(3):
            x = CANVAS_SIZE[0] - PAPER_MARGIN - 180 - (column * 220)
            y = CANVAS_SIZE[1] - PAPER_MARGIN - 160
            draw.line((x - 120, y, x, y), fill=(132, 121, 102, 255), width=2)
            _draw_rtl_text(draw, (x, y + 12), "אישור", font=annotation_font, fill=(104, 92, 76, 255))

    return _degrade(image.convert("RGB"), randomizer, background, recipe.degradation_preset)


def _select_font(fonts: list[dict[str, str]], template_id: str) -> dict[str, str]:
    target_style = _recipe_for_template(template_id).font_style
    for font in fonts:
        if font.get("style") == target_style:
            return font
    raise ValueError(f"No synthetic font registered for style: {target_style}")


def _select_title(template_id: str, index: int) -> str:
    titles = HANDWRITTEN_TITLES if template_id == "handwritten_note" else PRINTED_TITLES
    return titles[index % len(titles)]


def _select_body_lines(randomizer: random.Random, corpus: list[str], template_id: str) -> list[str]:
    line_count = _recipe_for_template(template_id).line_count
    return randomizer.sample(corpus, k=min(line_count, len(corpus)))


def _footer_text(randomizer: random.Random) -> str:
    return f"{FOOTER_LABELS[randomizer.randrange(len(FOOTER_LABELS))]} {randomizer.randint(12, 128)}"


def generate_documents(
    count: int,
    seed: int,
    template_ids: list[str],
    font_manifest_path: Path,
    text_corpus_path: Path,
    output_dir: Path,
) -> list[SyntheticDocument]:
    if seed < 0:
        raise ValueError("Synthetic generation seed must be non-negative.")
    if count < 0:
        raise ValueError("Synthetic generation count must be non-negative.")
    if not template_ids:
        raise ValueError("Synthetic generation requires at least one template_id.")
    recipe_catalog(template_ids)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Synthetic generation output path exists and is not a directory: {output_dir}")

    _require_raqm()
    randomizer = random.Random(seed)
    fonts = _load_font_entries(font_manifest_path)
    corpus = load_text_corpus(text_corpus_path)
    if not corpus:
        raise ValueError(f"Synthetic text corpus is empty: {text_corpus_path}")
    font_entries_by_template: dict[str, dict[str, str]] = {}
    font_paths_by_template: dict[str, Path] = {}
    for template_id in dict.fromkeys(template_ids):
        font_entry = _select_font(fonts, template_id)
        font_path = _font_path(font_manifest_path, font_entry)
        _validate_font(font_path)
        font_entries_by_template[template_id] = font_entry
        font_paths_by_template[template_id] = font_path
    output_dir.mkdir(parents=True, exist_ok=True)

    documents: list[SyntheticDocument] = []
    for index in range(count):
        template_id = template_ids[index % len(template_ids)]
        recipe = _recipe_for_template(template_id)
        font_entry = font_entries_by_template[template_id]
        font_path = font_paths_by_template[template_id]
        title = _select_title(template_id, index)
        body_lines = _select_body_lines(randomizer, corpus, template_id)
        footer = _footer_text(randomizer)
        sample_id = f"hocrsyngen-s{seed:08d}-{index:06d}"
        asset_path = f"assets/{sample_id}/page_0001.jpg"
        path = output_dir / asset_path
        path.parent.mkdir(parents=True, exist_ok=True)
        image = _draw_document(randomizer, title, body_lines, footer, font_path, template_id)
        image.save(path, format="JPEG", quality=recipe.jpeg_quality, optimize=True)
        logical_text = unicodedata.normalize("NFC", "\n".join([title, *body_lines, footer]))
        documents.append(
            SyntheticDocument(
                sample_id=sample_id,
                sample_index=index,
                title=title,
                body="\n".join(body_lines),
                footer=footer,
                template_id=template_id,
                recipe_id=recipe.recipe_id,
                degradation_preset=recipe.degradation_preset,
                font_id=str(font_entry["id"]),
                path=path,
                asset_path=asset_path,
                sha256=sha256_file(path),
                generator_version=GENERATOR_VERSION,
                logical_text=logical_text,
            )
        )
    return documents


def generate_manifest(
    count: int,
    seed: int,
    output_dir: Path,
    template_ids: list[str] | None = None,
    *,
    font_manifest_path: Path | None = None,
    text_corpus_path: Path | None = None,
    persona: str | None = None,
    condition: str | None = None,
) -> GenerationManifest:
    template_ids = DEFAULT_TEMPLATE_IDS if template_ids is None else template_ids
    font_manifest_path = font_manifest_path or default_font_manifest_path()
    text_corpus_path = text_corpus_path or default_text_corpus_path()
    documents = generate_documents(count, seed, template_ids, font_manifest_path, text_corpus_path, output_dir)
    samples = [
        GeneratedSample(
            sample_id=document.sample_id,
            pages=[
                PageAsset(
                    page_id=f"{document.sample_id}-page-0001",
                    asset_path=document.asset_path,
                    media_type="image/jpeg",
                    sha256=document.sha256,
                    width=CANVAS_SIZE[0],
                    height=CANVAS_SIZE[1],
                )
            ],
            text=TextMetadata(logical_order=document.logical_text),
            generator_version=document.generator_version,
            recipe_id=document.recipe_id,
            provenance=SampleProvenance(
                seed=seed,
                sample_index=document.sample_index,
                template_id=document.template_id,
                recipe_id=document.recipe_id,
                degradation_preset=document.degradation_preset,
                font_id=document.font_id,
                source_corpus="packaged:synthetic/texts/hebrew_lines.txt",
            ),
            controls=SampleControls(persona=persona, condition=condition),
        )
        for document in documents
    ]
    return GenerationManifest(samples=samples)


def write_manifest(manifest: GenerationManifest, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "generation_manifest.json"
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def generate_batch(
    count: int,
    seed: int,
    output_dir: Path,
    template_ids: list[str] | None = None,
    *,
    persona: str | None = None,
    condition: str | None = None,
) -> GenerationManifest:
    manifest = generate_manifest(count, seed, output_dir, template_ids, persona=persona, condition=condition)
    write_manifest(manifest, output_dir)
    return manifest
