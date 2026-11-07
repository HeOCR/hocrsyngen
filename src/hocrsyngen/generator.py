from __future__ import annotations

import json
import math
import random
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
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


GENERATOR_VERSION = "s14a-ledger-wrap-v1"
# Earlier generator versions whose batches still validate. d4a-realism-v2 drew
# the same pages but left stamp, signature-caption and marginal text out of
# logical_order (S10c). s11b-ledger-fit-v1 dropped most wrapped ledger detail
# rows past the 10-row table (S14a).
PREVIOUS_GENERATOR_VERSIONS = ("d4a-realism-v2", "s10c-gold-complete-v1", "s11b-ledger-fit-v1")
CANVAS_SIZE = (1200, 1600)
PAPER_MARGIN = 96
DEFAULT_TEMPLATE_IDS = ["printed_letter", "handwritten_note"]
GOVERNED_TEMPLATE_IDS = [
    *DEFAULT_TEMPLATE_IDS,
    "archive_card",
    "ledger",
    "printed_letter_heavy_scan",
    "handwritten_note_heavy_wear",
    "archive_card_faded_scan",
]

# S16b: templates composed from a real-glyph bank by ``hocrsyngen
# compose-glyph-pages`` (``glyph_compose.py``), not rendered from fonts. They
# are governed for validation but are not ``generate`` templates, and the
# ``templates`` command lists them only with ``--include-composed``.
GLYPH_COMPOSER_VERSION = "s16b-glyph-compose-v1"
PRINTED_BOOK_GLYPH_TEMPLATE_ID = "printed_book_glyph_page"
COMPOSED_TEMPLATE_IDS = [PRINTED_BOOK_GLYPH_TEMPLATE_ID]

STAMP_TEXT = "נבדק"
SIGNATURE_CAPTION = "אישור"
SIGNATURE_CAPTION_COUNT = 3
PRINTED_TITLES = ["מכתב מנהלי", "דו\"ח קבלה", "רישום ארכיוני"]
HANDWRITTEN_TITLES = ["פנקס הערות", "רישום קצר", "הודעה פנימית"]
ARCHIVE_CARD_TITLES = ["כרטיס ארכיון", "רישום כרטסת", "תיק מסווג"]
LEDGER_TITLES = ["פנקס חשבונות", "רישום תנועות", "יומן גבייה"]
FOOTER_LABELS = ["סימן", "רישום", "עמוד"]


@dataclass(frozen=True)
class TemplateCapabilityMetadata:
    document_family: str
    base_family: str
    page_regions: tuple[str, ...]
    annotation_types: tuple[str, ...]
    identifier_types: tuple[str, ...]
    layout_density: str
    review_features: tuple[str, ...]


@dataclass(frozen=True)
class SyntheticRecipe:
    template_id: str
    render_template_id: str
    recipe_id: str
    layout_style: str
    font_style: str
    degradation_preset: str
    paper_tone: str
    line_count: int
    capability_metadata: TemplateCapabilityMetadata


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
    # Final-page line geometry; populated only when generation records it.
    lines: tuple[LineGeometry, ...] | None = None
    regions: tuple[RegionGeometry, ...] | None = None
    truncated_segments: int | None = None
    paired_asset: dict | None = None


@dataclass(frozen=True)
class TemplateCatalogEntry:
    template_id: str
    recipe_id: str
    layout_style: str
    font_style: str
    font_id: str
    degradation_preset: str


@dataclass(frozen=True)
class RichTemplateCatalogEntry(TemplateCatalogEntry):
    capability_metadata: TemplateCapabilityMetadata


@dataclass(frozen=True)
class DegradationPreset:
    angle_range: float
    blur_range: tuple[float, float]
    contrast: float
    brightness: float
    grain_passes: int
    jpeg_quality: int


@dataclass(frozen=True)
class StyleBundle:
    persona_id: str
    printed_line_height: int
    printed_x_jitter: int
    printed_y_jitter: tuple[int, int]
    handwritten_line_height: int
    handwritten_x_jitter: int
    handwritten_y_jitter: tuple[int, int]
    archive_line_height: int
    archive_y_jitter: tuple[int, int]
    ink_delta: int


@dataclass(frozen=True)
class ConditionBundle:
    condition_id: str
    line_height_scale: float
    ink_delta: int
    blur_delta: float
    contrast_scale: float
    brightness_scale: float
    grain_alpha_scale: float


@dataclass(frozen=True)
class ArchiveCardRender:
    image: Image.Image
    rendered_body_lines: list[str]
    footer_text: str
    logical_lines: list[str]


@dataclass(frozen=True)
class LedgerRender:
    image: Image.Image
    rendered_body_lines: list[str]
    footer_text: str
    logical_lines: list[str]


@dataclass(frozen=True)
class DocumentRender:
    image: Image.Image
    # Drawn body text per source line (wrapped segments rejoined).
    rendered_body_lines: list[str]
    logical_lines: list[str]


LINE_POLYGON_PADDING = 4
# Region polygons pad their pre-rotation box by twice the line padding, so
# every line polygon sits at least 4 px inside its region polygon.
REGION_POLYGON_PADDING = 8
OVERLAY_TEXT_REGIONS = frozenset({"stamp_area", "margin", "signature_area"})
LOGICAL_JOIN_SPACE = "space"
LOGICAL_JOIN_CELL = "cell"
_ARC_SEGMENTS = 16
_ELLIPSE_SEGMENTS = 64

Box = tuple[float, float, float, float]
Point = tuple[float, float]


@dataclass(frozen=True)
class LineGeometry:
    """One rendered text line in final-page pixel coordinates.

    ``polygon`` is clockwise from the top-left corner and ``baseline`` runs
    left-to-right in pixel x, independent of the RTL reading direction.
    ``logical_line_index`` is ``None`` for drawn text that ``logical_order``
    does not contain (stamp words, signature captions, marginal notes).
    """

    region: str
    text: str
    logical_line_index: int | None
    logical_join: str | None
    polygon: tuple[tuple[int, int], ...]
    baseline: tuple[tuple[int, int], ...]
    occluded: bool
    # True when the unclamped polygon left the page and was clamped to it.
    clipped: bool = False
    region_index: int | None = None


@dataclass(frozen=True)
class RegionGeometry:
    """One laid-out text region in final-page pixel coordinates.

    ``polygon`` is the pre-rotation box around the region's line text boxes
    and its drawn furniture (stamp ring, ledger frame, signature rule,
    marginal underline), padded and mapped through the page rotation like line
    polygons. ``line_indices`` index the reading-ordered ``lines``.
    """

    region_index: int
    region_type: str
    polygon: tuple[tuple[int, int], ...]
    reading_order_index: int | None
    line_indices: tuple[int, ...]


@dataclass(frozen=True)
class _RecordedLine:
    region: str
    text: str
    logical_line_index: int | None
    logical_join: str | None
    box: Box
    baseline_y: float
    # Lines sharing a key form one region; the key defaults to the region
    # type, so only separate blocks of one type (signature columns) set it.
    region_key: str


@dataclass
class _LineRecorder:
    """Collects pre-degradation text geometry without touching the randomizer.

    ``marks`` are stroked overlay polylines (stamp rings, correction strokes,
    ticks, marginal strokes) as ``(points, stroke_width, owner)``, where
    ``owner`` is the index of a line the mark decorates (an underline does not
    occlude its own text).
    """

    lines: list[_RecordedLine] = field(default_factory=list)
    marks: list[tuple[tuple[Point, ...], float, int | None]] = field(default_factory=list)
    # Drawn region furniture as (box, owner line index); it widens the owner's
    # region polygon.
    region_boxes: list[tuple[Box, int]] = field(default_factory=list)
    rotation_degrees: float = 0.0
    plain_evaluation: bool = False
    text_draws: list = field(default_factory=list)
    # Wrapped body segments a capped renderer never drew (and so never put
    # into logical_order).
    truncated_segments: int = 0

    def record(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        text: str,
        *,
        font: ImageFont.FreeTypeFont,
        anchor: str,
        region: str,
        logical_line_index: int | None,
        logical_join: str | None,
        region_key: str | None = None,
    ) -> None:
        if anchor != "ra":
            raise ValueError(f"Line geometry recording supports anchor 'ra' only, got {anchor!r}")
        box = draw.textbbox(xy, _rtl_display_text(text), font=font, anchor=anchor, direction="rtl")
        baseline_y = xy[1] + font.getmetrics()[0]
        self.lines.append(
            _RecordedLine(region, text, logical_line_index, logical_join, box, baseline_y, region_key or region)
        )

    def add_region_box(self, box: Box, *, owner: int) -> None:
        self.region_boxes.append((box, owner))

    def mark_polyline(self, points: Sequence[Point], width: float, *, owner: int | None = None) -> None:
        self.marks.append((tuple(points), width, owner))

    def last_line_index(self) -> int:
        return len(self.lines) - 1

    def mark_ellipse(self, box: Box, width: float) -> None:
        self.mark_polyline(_ellipse_points(box, 0, 360, _ELLIPSE_SEGMENTS), width)

    def mark_arc(self, box: Box, start: float, end: float, width: float) -> None:
        self.mark_polyline(_ellipse_points(box, start, end, _ARC_SEGMENTS), width)

    def _occluded(self, index: int) -> bool:
        line = self.lines[index]
        for points, width, owner in self.marks:
            if owner == index:
                continue
            if any(
                _segment_hits_box(start, end, _grown_box(line.box, width / 2))
                for start, end in zip(points, points[1:])
            ):
                return True
        # Overlay text (stamp, margin and signature regions) occludes, and is
        # occluded by, any text it overlaps; main-flow lines never occlude
        # each other.
        for other_index, other in enumerate(self.lines):
            if other_index == index:
                continue
            if not self.plain_evaluation and line.region not in OVERLAY_TEXT_REGIONS and other.region not in OVERLAY_TEXT_REGIONS:
                continue
            if _boxes_overlap(line.box, other.box):
                return True
        return False

    def _reading_order(self) -> list[int]:
        # Logical (reading) order; drawing order differs where an annotation
        # such as a stamp is drawn before the text it follows.
        return sorted(
            range(len(self.lines)),
            key=lambda index: (
                self.lines[index].logical_line_index is None,
                self.lines[index].logical_line_index or 0,
            ),
        )

    def _region_keys(self) -> list[str]:
        """Region keys in region_index order: by each region's first line in reading order."""

        return list(dict.fromkeys(self.lines[index].region_key for index in self._reading_order()))

    def final_lines(self, size: tuple[int, int]) -> tuple[LineGeometry, ...]:
        width, height = size
        region_index = {key: position for position, key in enumerate(self._region_keys())}
        lines: list[LineGeometry] = []
        for index, line in enumerate(self.lines):
            left, top, right, bottom = line.box
            pad = LINE_POLYGON_PADDING
            corners = (
                (left - pad, top - pad),
                (right + pad, top - pad),
                (right + pad, bottom + pad),
                (left - pad, bottom + pad),
            )
            baseline = ((left, line.baseline_y), (right, line.baseline_y))
            rotated = [_rotated_point(point, self.rotation_degrees, size) for point in (*corners, *baseline)]
            clipped = any(x < 0 or y < 0 or x > width - 1 or y > height - 1 for x, y in rotated)
            if self.plain_evaluation:
                # Pixels clipped before rotation cannot reappear when the page rotates.
                clipped = clipped or any(x < 0 or y < 0 or x > width - 1 or y > height - 1 for x, y in corners)
            lines.append(
                LineGeometry(
                    region=line.region,
                    text=unicodedata.normalize("NFC", line.text),
                    logical_line_index=line.logical_line_index,
                    logical_join=line.logical_join,
                    polygon=tuple(_clamped_point(point, size) for point in rotated[:4]),
                    baseline=tuple(_clamped_point(point, size) for point in rotated[4:]),
                    occluded=self._occluded(index) or (self.plain_evaluation and clipped),
                    clipped=clipped,
                    region_index=region_index[line.region_key],
                )
            )
        return tuple(lines[index] for index in self._reading_order())

    def final_regions(self, size: tuple[int, int]) -> tuple[RegionGeometry, ...]:
        order = self._reading_order()
        regions: list[RegionGeometry] = []
        next_reading_order_index = 0
        for region_index, key in enumerate(self._region_keys()):
            members = [index for index in order if self.lines[index].region_key == key]
            boxes = [self.lines[index].box for index in members]
            boxes.extend(box for box, owner in self.region_boxes if owner in members)
            pad = REGION_POLYGON_PADDING
            left = min(box[0] for box in boxes) - pad
            top = min(box[1] for box in boxes) - pad
            right = max(box[2] for box in boxes) + pad
            bottom = max(box[3] for box in boxes) + pad
            corners = ((left, top), (right, top), (right, bottom), (left, bottom))
            reading_order_index: int | None = None
            if any(self.lines[index].logical_line_index is not None for index in members):
                reading_order_index = next_reading_order_index
                next_reading_order_index += 1
            regions.append(
                RegionGeometry(
                    region_index=region_index,
                    region_type=self.lines[members[0]].region,
                    polygon=tuple(
                        _clamped_point(_rotated_point(point, self.rotation_degrees, size), size) for point in corners
                    ),
                    reading_order_index=reading_order_index,
                    line_indices=tuple(order.index(index) for index in members),
                )
            )
        return tuple(regions)


def _ellipse_points(box: Box, start: float, end: float, segments: int) -> tuple[Point, ...]:
    # Same angle convention as ImageDraw.arc: degrees clockwise from 3 o'clock.
    left, top, right, bottom = box
    center_x, center_y = (left + right) / 2, (top + bottom) / 2
    radius_x, radius_y = (right - left) / 2, (bottom - top) / 2
    return tuple(
        (
            center_x + radius_x * math.cos(math.radians(start + (end - start) * step / segments)),
            center_y + radius_y * math.sin(math.radians(start + (end - start) * step / segments)),
        )
        for step in range(segments + 1)
    )


def _grown_box(box: Box, amount: float) -> Box:
    return (box[0] - amount, box[1] - amount, box[2] + amount, box[3] + amount)


def _boxes_overlap(first: Box, second: Box) -> bool:
    return first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]


def _segment_hits_box(start: Point, end: Point, box: Box) -> bool:
    """Liang-Barsky clip test: does segment ``start``-``end`` touch ``box``?"""

    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    low, high = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            low = max(low, t)
        else:
            high = min(high, t)
        if low > high:
            return False
    return True


def _rotated_point(point: tuple[float, float], angle_degrees: float, size: tuple[int, int]) -> tuple[float, float]:
    """Map a canvas point through ``Image.rotate(angle, expand=False)``.

    Pillow rotates counter-clockwise about the canvas centre ``(w/2, h/2)``
    in continuous pixel coordinates.
    """

    radians = math.radians(angle_degrees)
    center_x, center_y = size[0] / 2, size[1] / 2
    dx, dy = point[0] - center_x, point[1] - center_y
    return (
        center_x + dx * math.cos(radians) + dy * math.sin(radians),
        center_y - dx * math.sin(radians) + dy * math.cos(radians),
    )


def _clamped_point(point: tuple[float, float], size: tuple[int, int]) -> tuple[int, int]:
    x, y = point
    return (min(max(round(x), 0), size[0] - 1), min(max(round(y), 0), size[1] - 1))


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
    recorder: _LineRecorder | None = None,
    region: str | None = None,
    logical_line_index: int | None = None,
    logical_join: str | None = None,
    region_key: str | None = None,
) -> None:
    _require_raqm()
    if recorder is not None and region is not None:
        recorder.record(
            draw,
            xy,
            text,
            font=font,
            anchor=anchor,
            region=region,
            logical_line_index=logical_line_index,
            logical_join=logical_join,
            region_key=region_key,
        )
    if recorder is not None and recorder.plain_evaluation:
        if region is None or logical_line_index is None:
            raise ValueError("plain evaluation requires every visible text line in the reference")
        recorder.text_draws.append((xy, text, font, fill, anchor))
    draw.text(xy, _rtl_display_text(text), font=font, fill=fill, anchor=anchor, direction="rtl")


def _paper_background(randomizer: random.Random, size: tuple[int, int], tone: str) -> Image.Image:
    base = (246, 241, 230) if tone == "printed" else (243, 235, 220)
    image = Image.new("RGB", size, base)
    noise = Image.frombytes("L", size, randomizer.randbytes(size[0] * size[1]))
    noise = noise.point(lambda value: int(128 + ((value - 128) * 0.08)))
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    textured = ImageChops.add(image, noise_rgb, scale=1.0, offset=-128)
    return Image.blend(image, textured, alpha=0.05)


def _apply_grain(image: Image.Image, randomizer: random.Random, *, alpha: float = 0.08) -> Image.Image:
    noise = Image.frombytes("L", image.size, randomizer.randbytes(image.size[0] * image.size[1]))
    noise = noise.point(lambda value: int(96 + ((value - 128) * 0.22)))
    textured = ImageChops.add_modulo(image.convert("RGB"), Image.merge("RGB", (noise, noise, noise)))
    return Image.blend(image, textured, alpha=alpha)


DEGRADATION_PRESETS: dict[str, DegradationPreset] = {
    "office_scan_soft": DegradationPreset(
        angle_range=0.85,
        blur_range=(0.15, 0.45),
        contrast=0.96,
        brightness=0.99,
        grain_passes=1,
        jpeg_quality=82,
    ),
    "notebook_scan_worn": DegradationPreset(
        angle_range=1.5,
        blur_range=(0.25, 0.75),
        contrast=0.92,
        brightness=0.97,
        grain_passes=2,
        jpeg_quality=78,
    ),
    "office_scan_heavy": DegradationPreset(
        angle_range=1.35,
        blur_range=(0.45, 0.95),
        contrast=0.88,
        brightness=0.93,
        grain_passes=3,
        jpeg_quality=78,
    ),
    "notebook_scan_heavy_wear": DegradationPreset(
        angle_range=1.85,
        blur_range=(0.35, 0.85),
        contrast=0.88,
        brightness=0.94,
        grain_passes=3,
        jpeg_quality=74,
    ),
    "archive_scan_faded": DegradationPreset(
        angle_range=1.1,
        blur_range=(0.35, 0.85),
        contrast=0.78,
        brightness=1.06,
        grain_passes=3,
        jpeg_quality=78,
    ),
}


def _degradation_preset(preset: str) -> DegradationPreset:
    try:
        return DEGRADATION_PRESETS[preset]
    except KeyError as exc:
        raise ValueError(f"Unsupported synthetic degradation_preset: {preset}") from exc


STYLE_BUNDLES: dict[str, StyleBundle] = {
    "style_standard_v1": StyleBundle(
        persona_id="style_standard_v1",
        printed_line_height=68,
        printed_x_jitter=6,
        printed_y_jitter=(-2, 2),
        handwritten_line_height=76,
        handwritten_x_jitter=28,
        handwritten_y_jitter=(-10, 8),
        archive_line_height=78,
        archive_y_jitter=(-2, 2),
        ink_delta=0,
    ),
    "style_open_drift_v1": StyleBundle(
        persona_id="style_open_drift_v1",
        printed_line_height=82,
        printed_x_jitter=18,
        printed_y_jitter=(-7, 7),
        handwritten_line_height=94,
        handwritten_x_jitter=46,
        handwritten_y_jitter=(-18, 16),
        archive_line_height=92,
        archive_y_jitter=(-7, 7),
        ink_delta=15,
    ),
    "style_compact_steady_v1": StyleBundle(
        persona_id="style_compact_steady_v1",
        printed_line_height=58,
        printed_x_jitter=2,
        printed_y_jitter=(-1, 1),
        handwritten_line_height=64,
        handwritten_x_jitter=12,
        handwritten_y_jitter=(-4, 4),
        archive_line_height=66,
        archive_y_jitter=(-1, 1),
        ink_delta=-8,
    ),
}
SUPPORTED_STYLE_BUNDLE_IDS = tuple(STYLE_BUNDLES)


def _style_bundle(persona: str | None) -> StyleBundle:
    if persona is None:
        return STYLE_BUNDLES["style_standard_v1"]
    try:
        return STYLE_BUNDLES[persona]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_STYLE_BUNDLE_IDS)
        raise ValueError(
            f"Unsupported synthetic persona style bundle: {persona}. "
            f"Supported style bundles: {supported}"
        ) from exc


CONDITION_BUNDLES: dict[str, ConditionBundle] = {
    "condition_standard_v1": ConditionBundle(
        condition_id="condition_standard_v1",
        line_height_scale=1.0,
        ink_delta=0,
        blur_delta=0.0,
        contrast_scale=1.0,
        brightness_scale=1.0,
        grain_alpha_scale=1.0,
    ),
    "condition_low_contrast_v1": ConditionBundle(
        condition_id="condition_low_contrast_v1",
        line_height_scale=1.0,
        ink_delta=18,
        blur_delta=0.22,
        contrast_scale=0.82,
        brightness_scale=1.14,
        grain_alpha_scale=1.0,
    ),
    "condition_dense_spacing_v1": ConditionBundle(
        condition_id="condition_dense_spacing_v1",
        line_height_scale=0.82,
        ink_delta=0,
        blur_delta=0.0,
        contrast_scale=1.0,
        brightness_scale=1.0,
        grain_alpha_scale=1.0,
    ),
}
SUPPORTED_CONDITION_BUNDLE_IDS = tuple(CONDITION_BUNDLES)


PRINTED_LETTER_CAPABILITY = TemplateCapabilityMetadata(
    document_family="letter",
    base_family="printed_letter",
    page_regions=(
        "title",
        "body",
        "footer",
        "form_rows",
        "stamp_area",
        "signature_area",
    ),
    annotation_types=("synthetic_stamp",),
    identifier_types=("footer_label",),
    layout_density="moderate",
    review_features=(
        "has_stable_regions",
        "has_visible_stamp",
        "has_signature_lines",
    ),
)
HANDWRITTEN_NOTE_CAPABILITY = TemplateCapabilityMetadata(
    document_family="notebook_note",
    base_family="handwritten_note",
    page_regions=("title", "body", "footer", "margin"),
    annotation_types=("marginal_note", "underline", "correction"),
    identifier_types=("footer_label",),
    layout_density="sparse",
    review_features=(
        "has_reviewable_annotations",
        "has_ruled_guides",
        "has_margin_marks",
    ),
)
ARCHIVE_CARD_CAPABILITY = TemplateCapabilityMetadata(
    document_family="archive_card",
    base_family="archive_card",
    page_regions=(
        "title",
        "body",
        "footer",
        "table_cells",
        "stamp_area",
        "identifier_area",
    ),
    annotation_types=("synthetic_stamp",),
    identifier_types=("archive_id", "date", "footer_label"),
    layout_density="dense",
    review_features=(
        "has_stable_regions",
        "has_visible_identifier",
        "has_visible_stamp",
    ),
)
LEDGER_CAPABILITY = TemplateCapabilityMetadata(
    document_family="ledger",
    base_family="ledger",
    page_regions=(
        "title",
        "body",
        "footer",
        "table_cells",
        "identifier_area",
    ),
    annotation_types=("tick", "correction"),
    identifier_types=("ledger_id", "date", "page_number", "footer_label"),
    layout_density="dense",
    review_features=(
        "has_stable_regions",
        "has_visible_identifier",
        "has_reviewable_table",
    ),
)


PRINTED_BOOK_GLYPH_CAPABILITY = TemplateCapabilityMetadata(
    document_family="book_page",
    base_family="printed_book_glyph_page",
    page_regions=("title", "body", "footer"),
    annotation_types=(),
    identifier_types=("page_number",),
    layout_density="dense",
    review_features=(
        "has_stable_regions",
        "has_real_glyph_provenance",
    ),
)
COMPOSED_TEMPLATE_CATALOG = (
    RichTemplateCatalogEntry(
        template_id=PRINTED_BOOK_GLYPH_TEMPLATE_ID,
        recipe_id="printed_book_glyph_page_v1",
        layout_style="printed_book_page",
        font_style="real_glyph",
        font_id="real_glyph_bank",
        degradation_preset="book_scan_glyph_v1",
        capability_metadata=PRINTED_BOOK_GLYPH_CAPABILITY,
    ),
)


def composed_template_entry(template_id: str) -> RichTemplateCatalogEntry:
    for entry in COMPOSED_TEMPLATE_CATALOG:
        if entry.template_id == template_id:
            return entry
    raise ValueError(f"Unsupported composed template_id: {template_id}")


def _condition_bundle(condition: str | None) -> ConditionBundle:
    if condition is None:
        return CONDITION_BUNDLES["condition_standard_v1"]
    try:
        return CONDITION_BUNDLES[condition]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_CONDITION_BUNDLE_IDS)
        raise ValueError(
            f"Unsupported synthetic condition rendering bundle: {condition}. "
            f"Supported condition bundles: {supported}"
        ) from exc


def _map_jitter(
    value: int,
    source: tuple[int, int],
    target: tuple[int, int],
) -> int:
    if source == target:
        return value
    source_min, source_max = source
    target_min, target_max = target
    if source_min == source_max:
        return target_min
    ratio = (value - source_min) / (source_max - source_min)
    return round(target_min + (ratio * (target_max - target_min)))


def _conditioned_line_height(line_height: int, condition_bundle: ConditionBundle) -> int:
    return max(1, round(line_height * condition_bundle.line_height_scale))


def _degrade(
    image: Image.Image,
    randomizer: random.Random,
    background: tuple[int, int, int],
    preset: str,
    condition_bundle: ConditionBundle,
    recorder: _LineRecorder | None = None,
    pair_capture: dict | None = None,
) -> Image.Image:
    parameters = _degradation_preset(preset)
    if recorder is not None and recorder.plain_evaluation:
        # Repaint the actual text at its original positions, without furniture.
        image = Image.new("RGB", image.size, background)
        clean_draw = ImageDraw.Draw(image)
        for xy, text, font, fill, anchor in recorder.text_draws:
            clean_draw.text(xy, _rtl_display_text(text), font=font, fill=fill[:3], anchor=anchor, direction="rtl")
        recorder.marks.clear()
        recorder.region_boxes.clear()
    angle = randomizer.uniform(-parameters.angle_range, parameters.angle_range)
    if recorder is not None:
        # Rotation is the only geometric degradation; blur, grain, contrast and
        # brightness keep pixel positions.
        recorder.rotation_degrees = angle
    degraded = image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=background)
    radius = randomizer.uniform(*parameters.blur_range) + condition_bundle.blur_delta
    if pair_capture is not None:
        pair_capture.update(image=degraded.copy(), rotation_degrees=angle, blur_radius=radius,
            grain_passes=parameters.grain_passes, grain_alpha=0.08 * condition_bundle.grain_alpha_scale,
            contrast=parameters.contrast * condition_bundle.contrast_scale,
            brightness=parameters.brightness * condition_bundle.brightness_scale,
            jpeg_quality=parameters.jpeg_quality)
    degraded = degraded.filter(ImageFilter.GaussianBlur(radius=radius))
    for _ in range(parameters.grain_passes):
        degraded = _apply_grain(degraded, randomizer, alpha=0.08 * condition_bundle.grain_alpha_scale)
    degraded = ImageEnhance.Contrast(degraded).enhance(parameters.contrast * condition_bundle.contrast_scale)
    degraded = ImageEnhance.Brightness(degraded).enhance(parameters.brightness * condition_bundle.brightness_scale)
    return degraded


def _recipe_for_template(template_id: str) -> SyntheticRecipe:
    if template_id == "printed_letter":
        return SyntheticRecipe(
            template_id=template_id,
            render_template_id="printed_letter",
            recipe_id="printed_letter_form_v1",
            layout_style="printed_form",
            font_style="printed",
            degradation_preset="office_scan_soft",
            paper_tone="printed",
            line_count=4,
            capability_metadata=PRINTED_LETTER_CAPABILITY,
        )
    if template_id == "handwritten_note":
        return SyntheticRecipe(
            template_id=template_id,
            render_template_id="handwritten_note",
            recipe_id="handwritten_note_marginalia_v1",
            layout_style="handwritten_note",
            font_style="handwritten_like",
            degradation_preset="notebook_scan_worn",
            paper_tone="handwritten",
            line_count=3,
            capability_metadata=HANDWRITTEN_NOTE_CAPABILITY,
        )
    if template_id == "archive_card":
        return SyntheticRecipe(
            template_id=template_id,
            render_template_id="archive_card",
            recipe_id="archive_card_identifier_v1",
            layout_style="multi_region_page",
            font_style="printed",
            degradation_preset="office_scan_soft",
            paper_tone="printed",
            line_count=3,
            capability_metadata=ARCHIVE_CARD_CAPABILITY,
        )
    if template_id == "ledger":
        return SyntheticRecipe(
            template_id=template_id,
            render_template_id="ledger",
            recipe_id="ledger_table_v1",
            layout_style="tabular",
            font_style="printed",
            degradation_preset="office_scan_soft",
            paper_tone="printed",
            line_count=5,
            capability_metadata=LEDGER_CAPABILITY,
        )
    if template_id == "printed_letter_heavy_scan":
        return SyntheticRecipe(
            template_id=template_id,
            render_template_id="printed_letter",
            recipe_id="printed_letter_form_heavy_scan_v1",
            layout_style="printed_form",
            font_style="printed",
            degradation_preset="office_scan_heavy",
            paper_tone="printed",
            line_count=4,
            capability_metadata=PRINTED_LETTER_CAPABILITY,
        )
    if template_id == "handwritten_note_heavy_wear":
        return SyntheticRecipe(
            template_id=template_id,
            render_template_id="handwritten_note",
            recipe_id="handwritten_note_marginalia_heavy_wear_v1",
            layout_style="handwritten_note",
            font_style="handwritten_like",
            degradation_preset="notebook_scan_heavy_wear",
            paper_tone="handwritten",
            line_count=3,
            capability_metadata=HANDWRITTEN_NOTE_CAPABILITY,
        )
    if template_id == "archive_card_faded_scan":
        return SyntheticRecipe(
            template_id=template_id,
            render_template_id="archive_card",
            recipe_id="archive_card_identifier_faded_scan_v1",
            layout_style="multi_region_page",
            font_style="printed",
            degradation_preset="archive_scan_faded",
            paper_tone="printed",
            line_count=3,
            capability_metadata=ARCHIVE_CARD_CAPABILITY,
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
    include_composed: bool = False,
) -> list[TemplateCatalogEntry]:
    template_ids = GOVERNED_TEMPLATE_IDS if template_ids is None else template_ids
    font_manifest_path = font_manifest_path or default_font_manifest_path()
    recipes = recipe_catalog(template_ids)
    fonts = _load_font_entries(font_manifest_path)
    catalog: list[TemplateCatalogEntry] = []
    for template_id in template_ids:
        recipe = recipes[template_id]
        font_entry = _select_font(fonts, template_id)
        font_path = _font_path(font_manifest_path, font_entry)
        _validate_font(font_path)
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
    if include_composed:
        catalog.extend(
            TemplateCatalogEntry(
                template_id=entry.template_id,
                recipe_id=entry.recipe_id,
                layout_style=entry.layout_style,
                font_style=entry.font_style,
                font_id=entry.font_id,
                degradation_preset=entry.degradation_preset,
            )
            for entry in COMPOSED_TEMPLATE_CATALOG
        )
    return catalog


def rich_template_catalog(
    template_ids: list[str] | None = None,
    *,
    font_manifest_path: Path | None = None,
    include_composed: bool = False,
) -> list[RichTemplateCatalogEntry]:
    template_ids = GOVERNED_TEMPLATE_IDS if template_ids is None else template_ids
    catalog = template_catalog(template_ids, font_manifest_path=font_manifest_path)
    recipes = recipe_catalog(template_ids)
    rich_catalog: list[RichTemplateCatalogEntry] = []
    for entry in catalog:
        rich_catalog.append(
            RichTemplateCatalogEntry(
                template_id=entry.template_id,
                recipe_id=entry.recipe_id,
                layout_style=entry.layout_style,
                font_style=entry.font_style,
                font_id=entry.font_id,
                degradation_preset=entry.degradation_preset,
                capability_metadata=recipes[entry.template_id].capability_metadata,
            )
        )
    if include_composed:
        rich_catalog.extend(COMPOSED_TEMPLATE_CATALOG)
    return rich_catalog


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


def _draw_stamp(
    draw: ImageDraw.ImageDraw,
    randomizer: random.Random,
    font: ImageFont.FreeTypeFont,
    recorder: _LineRecorder | None = None,
    logical_line_index: int | None = None,
) -> str:
    center_x = PAPER_MARGIN + randomizer.randint(150, 260)
    center_y = PAPER_MARGIN + randomizer.randint(135, 245)
    radius_x = randomizer.randint(92, 118)
    radius_y = randomizer.randint(44, 58)
    color = (129, 47, 41)
    ellipse = (center_x - radius_x, center_y - radius_y, center_x + radius_x, center_y + radius_y)
    draw.ellipse(ellipse, outline=color, width=4)
    if recorder is not None:
        recorder.mark_ellipse(ellipse, 4)
    _draw_rtl_text(
        draw, (center_x + 62, center_y - 13), STAMP_TEXT, font=font, fill=color,
        recorder=recorder, region="stamp_area", logical_line_index=logical_line_index,
    )
    if recorder is not None:
        recorder.add_region_box(ellipse, owner=recorder.last_line_index())
    return STAMP_TEXT


def _draw_handwritten_guides(draw: ImageDraw.ImageDraw, randomizer: random.Random) -> None:
    guide = (209, 198, 177)
    for row in range(10):
        y = PAPER_MARGIN + 210 + row * 92 + randomizer.randint(-5, 5)
        draw.line((PAPER_MARGIN + 65, y, CANVAS_SIZE[0] - PAPER_MARGIN - 70, y), fill=guide, width=1)


def _draw_marginalia(
    draw: ImageDraw.ImageDraw,
    randomizer: random.Random,
    font: ImageFont.FreeTypeFont,
    recorder: _LineRecorder | None = None,
    logical_line_index: int | None = None,
) -> str:
    notes = ["נבדק", "להמשך", "עותק"]
    x = PAPER_MARGIN + randomizer.randint(60, 150)
    y = PAPER_MARGIN + randomizer.randint(430, 680)
    note = notes[randomizer.randrange(len(notes))]
    _draw_rtl_text(
        draw, (x + 115, y), note, font=font, fill=(88, 68, 48),
        recorder=recorder, region="margin", logical_line_index=logical_line_index,
    )
    draw.line((x, y + 44, x + 120, y + 32), fill=(88, 68, 48), width=2)
    if recorder is not None:
        # The stroke underlines the note just drawn.
        recorder.mark_polyline(((x, y + 44), (x + 120, y + 32)), 2, owner=recorder.last_line_index())
        recorder.add_region_box((x - 1, y + 31, x + 121, y + 45), owner=recorder.last_line_index())
    for _ in range(2):
        sx = x + randomizer.randint(5, 95)
        sy = y + randomizer.randint(60, 140)
        draw.arc((sx, sy, sx + 70, sy + 32), start=190, end=345, fill=(94, 72, 50), width=2)
        if recorder is not None:
            recorder.mark_arc((sx, sy, sx + 70, sy + 32), 190, 345, 2)
    return note


def _draw_handwritten_underline(draw: ImageDraw.ImageDraw, randomizer: random.Random, x: int, y: int, width: int) -> None:
    points = []
    for step in range(0, width, 24):
        points.append((x - step, y + randomizer.randint(-2, 3)))
    if len(points) > 1:
        draw.line(points, fill=(56, 44, 34), width=2)


def _draw_archive_card(
    randomizer: random.Random,
    title: str,
    body_lines: list[str],
    footer: str,
    font_path: Path,
    template_id: str,
    style_bundle: StyleBundle,
    condition_bundle: ConditionBundle,
    recorder: _LineRecorder | None = None,
    pair_capture: dict | None = None,
) -> ArchiveCardRender:
    recipe = _recipe_for_template(template_id)
    background = (246, 241, 230)
    image = _paper_background(randomizer, CANVAS_SIZE, recipe.paper_tone).convert("RGBA")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(font_path, 58)
    label_font = _load_font(font_path, 30)
    body_font = _load_font(font_path, 38)
    footer_font = _load_font(font_path, 28)
    stamp_font = _load_font(font_path, 32)

    card_left = PAPER_MARGIN + 80 + randomizer.randint(-10, 10)
    card_top = PAPER_MARGIN + 150 + randomizer.randint(-10, 10)
    card_right = CANVAS_SIZE[0] - PAPER_MARGIN - 70 + randomizer.randint(-10, 10)
    card_bottom = CANVAS_SIZE[1] - PAPER_MARGIN - 200 + randomizer.randint(-8, 8)
    edge = (169, 157, 134, 255)
    faint = (214, 204, 183, 255)
    shadow = (225, 217, 199, 255)
    ink = (33, 29, 24, 255)
    label_ink = (92, 80, 65, 255)
    stamp_ink = (126, 45, 39, 255)

    draw.rectangle((card_left + 12, card_top + 14, card_right + 12, card_bottom + 14), outline=shadow, width=3)
    draw.rectangle((card_left, card_top, card_right, card_bottom), outline=edge, width=4)
    draw.line((card_left, card_top + 136, card_right, card_top + 136), fill=faint, width=3)
    draw.line((card_left + 260, card_top + 136, card_left + 260, card_bottom), fill=faint, width=2)
    for row in range(1, 7):
        y = card_top + 136 + row * 92 + randomizer.randint(-2, 2)
        draw.line((card_left, y, card_right, y), fill=faint, width=2)

    title_x = card_right - 46
    title_y = card_top + 40
    _draw_rtl_text(
        draw, (title_x, title_y), title, font=title_font, fill=ink,
        recorder=recorder, region="title", logical_line_index=0,
    )

    archive_id = f"א-{randomizer.randint(1200, 9980)}-{randomizer.randint(10, 99)}"
    archive_date = f"{randomizer.randint(1, 28):02d}/{randomizer.randint(1, 12):02d}/{randomizer.randint(1930, 1978)}"
    archive_id_text = f"מזהה {archive_id}"
    _draw_rtl_text(
        draw, (card_right - 48, card_top + 116), archive_id_text, font=label_font, fill=label_ink,
        recorder=recorder, region="identifier_area", logical_line_index=1,
    )
    _draw_rtl_text(
        draw, (card_left + 224, card_top + 116), archive_date, font=label_font, fill=label_ink,
        recorder=recorder, region="identifier_area", logical_line_index=2,
    )

    wrapped_lines: list[str] = []
    max_width = card_right - card_left - 340
    for line in body_lines:
        segments = _wrap_hebrew_text(draw, line, body_font, max_width)
        for segment in segments:
            _require_segment_fits(draw, segment, body_font, max_width)
        wrapped_lines.extend(segments)
    rendered_body_lines = wrapped_lines[:7]
    if recorder is not None:
        recorder.truncated_segments = len(wrapped_lines) - len(rendered_body_lines)

    for index, line in enumerate(rendered_body_lines):
        standard = STYLE_BUNDLES["style_standard_v1"]
        y_jitter = _map_jitter(
            randomizer.randint(*standard.archive_y_jitter),
            standard.archive_y_jitter,
            style_bundle.archive_y_jitter,
        )
        y = (
            card_top
            + 196
            + index * _conditioned_line_height(style_bundle.archive_line_height, condition_bundle)
            + y_jitter
        )
        ink_value = max(18, min(80, 33 + style_bundle.ink_delta + condition_bundle.ink_delta))
        body_ink = (ink_value, max(16, ink_value - 4), max(12, ink_value - 9), 255)
        _draw_rtl_text(
            draw, (card_right - 48, y), line, font=body_font, fill=body_ink,
            recorder=recorder, region="body", logical_line_index=3 + index,
        )

    labels = ["מקור", "תאריך", "מספר", "הערה"]
    labels_start = 3 + len(rendered_body_lines)
    for index, label in enumerate(labels):
        y = card_top + 218 + index * 118 + randomizer.randint(-2, 2)
        _draw_rtl_text(
            draw, (card_left + 222, y), label, font=label_font, fill=label_ink,
            recorder=recorder, region="table_cells", logical_line_index=labels_start + index,
        )

    stamp_x = card_left + 190
    stamp_y = card_bottom - 128
    draw.ellipse((stamp_x - 92, stamp_y - 42, stamp_x + 92, stamp_y + 42), outline=stamp_ink, width=4)
    if recorder is not None:
        recorder.mark_ellipse((stamp_x - 92, stamp_y - 42, stamp_x + 92, stamp_y + 42), 4)
    _draw_rtl_text(
        draw, (stamp_x + 48, stamp_y - 14), "ארכיון", font=stamp_font, fill=stamp_ink,
        recorder=recorder, region="stamp_area", logical_line_index=labels_start + len(labels),
    )
    if recorder is not None:
        recorder.add_region_box(
            (stamp_x - 92, stamp_y - 42, stamp_x + 92, stamp_y + 42), owner=recorder.last_line_index()
        )

    footer_text = f"{footer} - {archive_id}"
    _draw_rtl_text(
        draw, (card_right - 48, card_bottom - 48), footer_text, font=footer_font, fill=label_ink,
        recorder=recorder, region="footer", logical_line_index=labels_start + len(labels) + 1,
    )
    _draw_stains(image, randomizer, handwritten=False)
    logical_lines = [
        title,
        archive_id_text,
        archive_date,
        *rendered_body_lines,
        *labels,
        "ארכיון",
        footer_text,
    ]
    return ArchiveCardRender(
        image=_degrade(
            image.convert("RGB"), randomizer, background, recipe.degradation_preset, condition_bundle, recorder, pair_capture
        ),
        rendered_body_lines=rendered_body_lines,
        footer_text=footer_text,
        logical_lines=logical_lines,
    )


# Ledger column widths from the left: row number, date, amount, details. The
# balance column takes the rest of the table (144 px, +/- 12 px of table
# jitter). Number, date and amount hold short fixed-format values, so S14a
# gives their spare width to the wrapped details column.
LEDGER_COLUMN_WIDTHS = (130, 140, 110, 360)
# s11b-ledger-fit-v1 widths. They still set how many row draws a ledger page
# takes from the shared random stream; see _draw_ledger.
S11B_LEDGER_COLUMN_WIDTHS = (150, 170, 180, 250)
# A cell's right anchor is inset 22 px and can jitter left by 18 px. Leave
# another 4 px for the annotation padding, even at maximum drift.
LEDGER_CELL_INSET = 22 + 18 + 4


def _ledger_row_draws(randomizer: random.Random, standard: StyleBundle) -> tuple[int, int, int, int, int, int]:
    """Draw one ledger row's jitter and cell values: y, x, amount, balance, day, month."""
    return (
        randomizer.randint(*standard.printed_y_jitter),
        randomizer.randint(0, standard.printed_x_jitter),
        randomizer.randint(12, 980),
        randomizer.randint(100, 4980),
        randomizer.randint(1, 28),
        randomizer.randint(1, 12),
    )


def _draw_ledger_tick(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
    recorder: _LineRecorder | None = None,
) -> None:
    draw.line((x - 22, y + 18, x - 8, y + 32), fill=color, width=3)
    draw.line((x - 8, y + 32, x + 26, y - 4), fill=color, width=3)
    if recorder is not None:
        recorder.mark_polyline(((x - 22, y + 18), (x - 8, y + 32), (x + 26, y - 4)), 3)


def _draw_ledger(
    randomizer: random.Random,
    title: str,
    body_lines: list[str],
    footer: str,
    font_path: Path,
    template_id: str,
    style_bundle: StyleBundle,
    condition_bundle: ConditionBundle,
    recorder: _LineRecorder | None = None,
    pair_capture: dict | None = None,
) -> LedgerRender:
    recipe = _recipe_for_template(template_id)
    background = (246, 241, 230)
    image = _paper_background(randomizer, CANVAS_SIZE, recipe.paper_tone).convert("RGBA")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(font_path, 56)
    label_font = _load_font(font_path, 28)
    body_font = _load_font(font_path, 30)
    footer_font = _load_font(font_path, 26)
    _draw_paper_frame(draw, randomizer, handwritten=False)
    _draw_creased_paper(draw, randomizer, handwritten=False)

    table_left = PAPER_MARGIN + 62 + randomizer.randint(-6, 6)
    table_top = PAPER_MARGIN + 245 + randomizer.randint(-6, 6)
    table_right = CANVAS_SIZE[0] - PAPER_MARGIN - 62 + randomizer.randint(-6, 6)
    table_bottom = CANVAS_SIZE[1] - PAPER_MARGIN - 205 + randomizer.randint(-6, 6)
    edge = (157, 146, 126, 255)
    faint = (211, 201, 181, 255)
    ink = (33, 29, 24, 255)
    label_ink = (88, 76, 60, 255)
    correction_ink = (124, 45, 39, 255)

    title_y = PAPER_MARGIN + 72 + randomizer.randint(-3, 3)
    _draw_rtl_text(
        draw, (CANVAS_SIZE[0] - PAPER_MARGIN - 48, title_y), title, font=title_font, fill=ink,
        recorder=recorder, region="title", logical_line_index=0,
    )

    ledger_id = f"פנקס {randomizer.randint(200, 980)}-{randomizer.randint(10, 99)}"
    ledger_date = f"{randomizer.randint(1, 28):02d}/{randomizer.randint(1, 12):02d}/{randomizer.randint(1948, 1985)}"
    _draw_rtl_text(
        draw, (CANVAS_SIZE[0] - PAPER_MARGIN - 52, title_y + 82), ledger_id, font=label_font, fill=label_ink,
        recorder=recorder, region="identifier_area", logical_line_index=1,
    )
    _draw_rtl_text(
        draw, (PAPER_MARGIN + 300, title_y + 82), ledger_date, font=label_font, fill=label_ink,
        recorder=recorder, region="identifier_area", logical_line_index=2,
    )

    draw.rectangle((table_left, table_top, table_right, table_bottom), outline=edge, width=3)
    header_bottom = table_top + 70
    draw.line((table_left, header_bottom, table_right, header_bottom), fill=edge, width=3)
    column_widths = [*LEDGER_COLUMN_WIDTHS, table_right - table_left - sum(LEDGER_COLUMN_WIDTHS)]
    column_edges = [table_left]
    for width in column_widths:
        column_edges.append(column_edges[-1] + width)
    for x in column_edges[1:-1]:
        draw.line((x, table_top, x + randomizer.randint(-1, 1), table_bottom), fill=faint, width=2)

    row_height = 86
    row_count = 10
    for row in range(1, row_count + 1):
        y = header_bottom + row * row_height + randomizer.randint(-2, 2)
        if y < table_bottom:
            draw.line((table_left, y, table_right, y), fill=faint, width=2)

    headers = ["מס'", "תאריך", "סכום", "פרטים", "יתרה"]
    header_anchors = [
        column_edges[1] - 22,
        column_edges[2] - 22,
        column_edges[3] - 22,
        column_edges[4] - 22,
        column_edges[5] - 22,
    ]
    for header_index, (x, header) in enumerate(zip(header_anchors, headers, strict=True)):
        _draw_rtl_text(
            draw, (x, table_top + 22), header, font=label_font, fill=label_ink,
            recorder=recorder, region="table_cells", logical_line_index=3 + header_index,
        )
        if recorder is not None and header_index == 0:
            recorder.add_region_box((table_left, table_top, table_right, table_bottom), owner=recorder.last_line_index())

    wrapped_lines: list[str] = []
    detail_width = column_widths[3] - LEDGER_CELL_INSET
    for line in body_lines:
        for token in line.split():
            left, _, right, _ = draw.textbbox((0, 0), token, font=body_font, direction="rtl")
            if right - left > detail_width:
                raise ValueError("Ledger detail token exceeds cell width; shorten the corpus token.")
        wrapped_lines.extend(_wrap_hebrew_text(draw, line, body_font, detail_width))
    rendered_body_lines = wrapped_lines[:row_count]
    if recorder is not None:
        recorder.truncated_segments = len(wrapped_lines) - len(rendered_body_lines)

    logical_rows: list[str] = []
    standard = STYLE_BUNDLES["style_standard_v1"]
    for index, line in enumerate(rendered_body_lines):
        y_draw, x_draw, amount_draw, balance_draw, day, month = _ledger_row_draws(randomizer, standard)
        y_offset = _map_jitter(y_draw, standard.printed_y_jitter, style_bundle.printed_y_jitter)
        x_offset = _map_jitter(x_draw, (0, standard.printed_x_jitter), (0, style_bundle.printed_x_jitter))
        y = header_bottom + 24 + index * row_height + y_offset
        amount = f"{amount_draw:,}"
        balance = f"{balance_draw:,}"
        row_date = f"{day:02d}/{month:02d}"
        row_number = f"{index + 1:02d}"
        fill_value = max(18, min(78, 33 + style_bundle.ink_delta + condition_bundle.ink_delta))
        row_ink = (fill_value, max(16, fill_value - 4), max(12, fill_value - 9), 255)
        values = [row_number, row_date, amount, line, balance]
        for cell_index, (x, value) in enumerate(zip(header_anchors, values, strict=True)):
            _draw_rtl_text(
                draw, (x - x_offset, y), value, font=body_font, fill=row_ink,
                recorder=recorder, region="table_cells", logical_line_index=3 + len(headers) + index,
                logical_join=LOGICAL_JOIN_CELL if cell_index else None,
            )
        if index in {1, 6}:
            mark_x = column_edges[1] - 96
            _draw_ledger_tick(draw, mark_x, y + 2, correction_ink, recorder)
        if index == 3:
            draw.line(
                (column_edges[3] + 16, y + 36, column_edges[4] - 26, y + 30),
                fill=correction_ink,
                width=2,
            )
            if recorder is not None:
                recorder.mark_polyline(((column_edges[3] + 16, y + 36), (column_edges[4] - 26, y + 30)), 2)
        logical_rows.append(" | ".join(values))
    # Later pages of a mixed batch draw from the same random stream. Take the
    # row draws s11b took (one per wrapped segment, up to row_count), so the
    # wider details column changes ledger pages only.
    s11b_width = S11B_LEDGER_COLUMN_WIDTHS[3] - LEDGER_CELL_INSET
    s11b_rows = min(row_count, sum(len(_wrap_hebrew_text(draw, line, body_font, s11b_width)) for line in body_lines))
    for _ in range(s11b_rows - len(rendered_body_lines)):
        _ledger_row_draws(randomizer, standard)

    footer_text = f"{footer} - {ledger_id}"
    footer_index = 3 + len(headers) + len(rendered_body_lines)
    _draw_rtl_text(
        draw, (table_right - 8, table_bottom + 42), footer_text, font=footer_font, fill=label_ink,
        recorder=recorder, region="footer", logical_line_index=footer_index,
    )
    _draw_rtl_text(
        draw, (PAPER_MARGIN + 260, table_bottom + 42), "עמוד 1", font=footer_font, fill=label_ink,
        recorder=recorder, region="footer", logical_line_index=footer_index + 1,
    )
    _draw_stains(image, randomizer, handwritten=False)

    logical_lines = [
        title,
        ledger_id,
        ledger_date,
        *headers,
        *logical_rows,
        footer_text,
        "עמוד 1",
    ]
    return LedgerRender(
        image=_degrade(
            image.convert("RGB"), randomizer, background, recipe.degradation_preset, condition_bundle, recorder, pair_capture
        ),
        rendered_body_lines=rendered_body_lines,
        footer_text=footer_text,
        logical_lines=logical_lines,
    )


# Body top is title_y plus this offset; title_y is at most PAPER_MARGIN + 24.
_DOCUMENT_BODY_OFFSET = {True: 132, False: 118}
_DOCUMENT_TITLE_Y_MAX = PAPER_MARGIN + 24
# Lowest y body ink may reach: above the printed signature rules, or above the
# highest possible handwritten footer.
_DOCUMENT_BODY_LIMIT_Y = {
    True: CANVAS_SIZE[1] - PAPER_MARGIN - 160 - 8,
    False: CANVAS_SIZE[1] - PAPER_MARGIN - 24 - 8,
}


def _document_body_capacity(
    form_layout: bool,
    line_height: int,
    max_y_jitter: int,
    body_font: ImageFont.FreeTypeFont,
) -> int:
    """Wrapped body lines that fit above the bottom furniture in the worst case."""

    ascent, descent = body_font.getmetrics()
    body_top = _DOCUMENT_TITLE_Y_MAX + _DOCUMENT_BODY_OFFSET[form_layout]
    room = _DOCUMENT_BODY_LIMIT_Y[form_layout] - body_top - max_y_jitter - (ascent + descent)
    return max(0, room // line_height + 1)


def _require_segment_fits(
    draw: ImageDraw.ImageDraw,
    segment: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> None:
    left, _top, right, _bottom = draw.textbbox((0, 0), segment, font=font, direction="rtl")
    if right - left > max_width:
        raise ValueError(
            f"Synthetic body text has a word wider than the body ({right - left}px > {max_width}px): {segment!r}"
        )


def _draw_document(
    randomizer: random.Random,
    title: str,
    body_lines: list[str],
    footer: str,
    font_path: Path,
    template_id: str,
    style_bundle: StyleBundle,
    condition_bundle: ConditionBundle,
    recorder: _LineRecorder | None = None,
    pair_capture: dict | None = None,
) -> DocumentRender:
    recipe = _recipe_for_template(template_id)
    form_layout = recipe.render_template_id == "printed_letter"
    handwritten_text = recipe.font_style == "handwritten_like"
    background = (246, 241, 230) if form_layout else (243, 235, 220)
    image = _paper_background(randomizer, CANVAS_SIZE, recipe.paper_tone).convert("RGBA")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(font_path, 62 if not handwritten_text else 66)
    body_font = _load_font(font_path, 42 if not handwritten_text else 46)
    footer_font = _load_font(font_path, 28)
    annotation_font = _load_font(font_path, 30 if handwritten_text else 26)

    # Body layout is settled before anything is drawn, without the randomizer,
    # so annotation text drawn first can take its logical_order slot after the
    # body. Reading order: title, body, stamp, margin note, signature captions
    # right to left, footer.
    max_width = CANVAS_SIZE[0] - (2 * PAPER_MARGIN) - 40
    standard = STYLE_BUNDLES["style_standard_v1"]
    base_line_height = style_bundle.handwritten_line_height if handwritten_text else style_bundle.printed_line_height
    line_height = _conditioned_line_height(base_line_height, condition_bundle)
    target_y_jitter = style_bundle.handwritten_y_jitter if handwritten_text else style_bundle.printed_y_jitter
    capacity = _document_body_capacity(form_layout, line_height, target_y_jitter[1], body_font)
    wrapped_lines: list[str] = []
    wrapped_sources: list[int] = []
    for source_index, line in enumerate(body_lines):
        segments = _wrap_hebrew_text(draw, line, body_font, max_width)
        for segment in segments:
            _require_segment_fits(draw, segment, body_font, max_width)
        wrapped_lines.extend(segments)
        wrapped_sources.extend([source_index] * len(segments))
    drawn_lines = wrapped_lines[:capacity]
    if recorder is not None:
        recorder.truncated_segments = len(wrapped_lines) - len(drawn_lines)
    drawn_sources = wrapped_sources[: len(drawn_lines)]
    rendered_body_lines = [
        " ".join(segment for segment, source in zip(drawn_lines, drawn_sources, strict=True) if source == source_index)
        for source_index in dict.fromkeys(drawn_sources)
    ]
    body_logical_index = {source: 1 + position for position, source in enumerate(dict.fromkeys(drawn_sources))}
    annotation_index = 1 + len(rendered_body_lines)

    _draw_paper_frame(draw, randomizer, handwritten=not form_layout)
    _draw_creased_paper(draw, randomizer, handwritten=not form_layout)
    annotation_lines: list[str] = []
    if form_layout:
        _draw_printed_form_guides(draw, randomizer)
        annotation_lines.append(_draw_stamp(draw, randomizer, annotation_font, recorder, annotation_index))
    else:
        _draw_handwritten_guides(draw, randomizer)
        annotation_lines.append(_draw_marginalia(draw, randomizer, annotation_font, recorder, annotation_index))
    if form_layout:
        annotation_lines.extend([SIGNATURE_CAPTION] * SIGNATURE_CAPTION_COUNT)
    footer_index = annotation_index + len(annotation_lines)
    _draw_stains(image, randomizer, handwritten=not form_layout)

    title_x = CANVAS_SIZE[0] - PAPER_MARGIN - randomizer.randint(0, 24)
    title_y = PAPER_MARGIN + randomizer.randint(4, 24)
    _draw_rtl_text(
        draw, (title_x, title_y), title, font=title_font, fill=(34, 29, 24, 255),
        recorder=recorder, region="title", logical_line_index=0,
    )

    body_top = title_y + _DOCUMENT_BODY_OFFSET[form_layout]
    standard_x_jitter = standard.handwritten_x_jitter if handwritten_text else standard.printed_x_jitter
    target_x_jitter = style_bundle.handwritten_x_jitter if handwritten_text else style_bundle.printed_x_jitter
    standard_y_jitter = standard.handwritten_y_jitter if handwritten_text else standard.printed_y_jitter
    start_x = CANVAS_SIZE[0] - PAPER_MARGIN - randomizer.randint(0, 20)
    for index, line in enumerate(drawn_lines):
        x_offset = _map_jitter(
            randomizer.randint(0, standard_x_jitter),
            (0, standard_x_jitter),
            (0, target_x_jitter),
        )
        y_offset = _map_jitter(
            randomizer.randint(*standard_y_jitter),
            standard_y_jitter,
            target_y_jitter,
        )
        x = start_x - x_offset
        y = body_top + index * line_height + y_offset
        ink = randomizer.randint(-8, 7) + style_bundle.ink_delta + condition_bundle.ink_delta
        fill = (max(18, 33 + ink), max(16, 28 + ink), max(12, 23 + ink), 255)
        continues_source = index > 0 and drawn_sources[index - 1] == drawn_sources[index]
        _draw_rtl_text(
            draw, (x, y), line, font=body_font, fill=fill,
            recorder=recorder, region="body", logical_line_index=body_logical_index[drawn_sources[index]],
            logical_join=LOGICAL_JOIN_SPACE if continues_source else None,
        )
        if not form_layout and index in {0, len(drawn_lines) - 1}:
            _draw_handwritten_underline(draw, randomizer, x - 5, y + 52, min(360, max_width // 2))

    footer_x = CANVAS_SIZE[0] - PAPER_MARGIN - randomizer.randint(12, 48)
    footer_y = CANVAS_SIZE[1] - PAPER_MARGIN - randomizer.randint(8, 24)
    _draw_rtl_text(
        draw, (footer_x, footer_y), footer, font=footer_font, fill=(93, 82, 70, 255),
        recorder=recorder, region="footer", logical_line_index=footer_index,
    )

    if not form_layout:
        for _ in range(3):
            x = randomizer.randint(PAPER_MARGIN + 120, CANVAS_SIZE[0] - PAPER_MARGIN - 180)
            y = randomizer.randint(CANVAS_SIZE[1] - PAPER_MARGIN - 220, CANVAS_SIZE[1] - PAPER_MARGIN - 120)
            radius = randomizer.randint(18, 34)
            draw.arc((x, y, x + radius * 3, y + radius), start=180, end=360, fill=(63, 50, 38, 255), width=2)
            if recorder is not None:
                recorder.mark_arc((x, y, x + radius * 3, y + radius), 180, 360, 2)
    else:
        for column in range(3):
            x = CANVAS_SIZE[0] - PAPER_MARGIN - 180 - (column * 220)
            y = CANVAS_SIZE[1] - PAPER_MARGIN - 160
            draw.line((x - 120, y, x, y), fill=(132, 121, 102, 255), width=2)
            _draw_rtl_text(
                draw, (x, y + 12), SIGNATURE_CAPTION, font=annotation_font, fill=(104, 92, 76, 255),
                recorder=recorder, region="signature_area", logical_line_index=annotation_index + 1 + column,
                region_key=f"signature_area:{column}",
            )
            if recorder is not None:
                # Each signature block is its own region: rule plus caption.
                recorder.add_region_box((x - 120, y - 1, x, y + 1), owner=recorder.last_line_index())

    return DocumentRender(
        image=_degrade(
            image.convert("RGB"), randomizer, background, recipe.degradation_preset, condition_bundle, recorder, pair_capture
        ),
        rendered_body_lines=rendered_body_lines,
        logical_lines=[title, *rendered_body_lines, *annotation_lines, footer],
    )


def _select_font(fonts: list[dict[str, str]], template_id: str) -> dict[str, str]:
    target_style = _recipe_for_template(template_id).font_style
    for font in fonts:
        if font.get("style") == target_style:
            return font
    raise ValueError(f"No synthetic font registered for style: {target_style}")


def _select_title(template_id: str, index: int) -> str:
    render_template_id = _recipe_for_template(template_id).render_template_id
    if render_template_id == "handwritten_note":
        titles = HANDWRITTEN_TITLES
    elif render_template_id == "archive_card":
        titles = ARCHIVE_CARD_TITLES
    elif render_template_id == "ledger":
        titles = LEDGER_TITLES
    else:
        titles = PRINTED_TITLES
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
    *,
    persona: str | None = None,
    condition: str | None = None,
    record_line_geometry: bool = False,
    emit_paired_render: bool = False,
    plain_evaluation: bool = False,
) -> list[SyntheticDocument]:
    if seed < 0:
        raise ValueError("Synthetic generation seed must be non-negative.")
    if count < 0:
        raise ValueError("Synthetic generation count must be non-negative.")
    if not template_ids:
        raise ValueError("Synthetic generation requires at least one template_id.")
    recipe_catalog(template_ids)
    style_bundle = _style_bundle(persona)
    condition_bundle = _condition_bundle(condition)
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
        recorder = _LineRecorder(plain_evaluation=plain_evaluation) if record_line_geometry or plain_evaluation else None
        pair_capture = {} if emit_paired_render else None
        if recipe.render_template_id == "archive_card":
            archive_render = _draw_archive_card(
                randomizer,
                title,
                body_lines,
                footer,
                font_path,
                template_id,
                style_bundle,
                condition_bundle,
                recorder,
                pair_capture,
            )
            image = archive_render.image
            logical_text = unicodedata.normalize("NFC", "\n".join(archive_render.logical_lines))
            document_body = "\n".join(archive_render.rendered_body_lines)
            document_footer = archive_render.footer_text
        elif recipe.render_template_id == "ledger":
            ledger_render = _draw_ledger(
                randomizer,
                title,
                body_lines,
                footer,
                font_path,
                template_id,
                style_bundle,
                condition_bundle,
                recorder,
                pair_capture,
            )
            image = ledger_render.image
            logical_text = unicodedata.normalize("NFC", "\n".join(ledger_render.logical_lines))
            document_body = "\n".join(ledger_render.rendered_body_lines)
            document_footer = ledger_render.footer_text
        else:
            document_render = _draw_document(
                randomizer,
                title,
                body_lines,
                footer,
                font_path,
                template_id,
                style_bundle,
                condition_bundle,
                recorder,
                pair_capture,
            )
            image = document_render.image
            logical_text = unicodedata.normalize("NFC", "\n".join(document_render.logical_lines))
            document_body = "\n".join(document_render.rendered_body_lines)
            document_footer = footer
        degradation_preset = _degradation_preset(recipe.degradation_preset)
        image.save(path, format="JPEG", quality=degradation_preset.jpeg_quality, optimize=True)
        paired_asset = None
        if pair_capture is not None:
            pair_path = path.with_name("page_0001_pre_photometric.png")
            pair_capture.pop("image").save(pair_path, format="PNG")
            paired_asset = {"path": pair_path.relative_to(output_dir).as_posix(),
                            "sha256": sha256_file(pair_path), **pair_capture}
        documents.append(
            SyntheticDocument(
                sample_id=sample_id,
                sample_index=index,
                title=title,
                body=document_body,
                footer=document_footer,
                template_id=template_id,
                recipe_id=recipe.recipe_id,
                degradation_preset=recipe.degradation_preset,
                font_id=str(font_entry["id"]),
                path=path,
                asset_path=asset_path,
                sha256=sha256_file(path),
                generator_version=GENERATOR_VERSION,
                logical_text=logical_text,
                lines=recorder.final_lines(image.size) if recorder is not None else None,
                regions=recorder.final_regions(image.size) if recorder is not None else None,
                truncated_segments=recorder.truncated_segments if recorder is not None else None,
                paired_asset=paired_asset,
            )
        )
    return documents


PACKAGED_TEXT_CORPUS_PREFIX = "packaged:synthetic/texts/"


def source_corpus_id(text_corpus_path: Path | None) -> str:
    """Return the manifest v1 ``provenance.source_corpus`` id for a corpus.

    Packaged corpora keep their ``packaged:synthetic/texts/<name>`` id. Any
    other corpus is identified by content as ``external:sha256:<hex>`` so the
    manifest never records a local path.
    """

    if text_corpus_path is None:
        text_corpus_path = default_text_corpus_path()
    packaged_dir = default_text_corpus_path().parent.resolve()
    resolved = text_corpus_path.resolve()
    if resolved.parent == packaged_dir:
        return f"{PACKAGED_TEXT_CORPUS_PREFIX}{resolved.name}"
    return f"external:sha256:{sha256_file(resolved)}"


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
    manifest, _documents = _generate_manifest_and_documents(
        count,
        seed,
        output_dir,
        template_ids,
        font_manifest_path=font_manifest_path,
        text_corpus_path=text_corpus_path,
        persona=persona,
        condition=condition,
    )
    return manifest


def _generate_manifest_and_documents(
    count: int,
    seed: int,
    output_dir: Path,
    template_ids: list[str] | None = None,
    *,
    font_manifest_path: Path | None = None,
    text_corpus_path: Path | None = None,
    persona: str | None = None,
    condition: str | None = None,
    record_line_geometry: bool = False,
    emit_paired_render: bool = False,
    plain_evaluation: bool = False,
) -> tuple[GenerationManifest, list[SyntheticDocument]]:
    template_ids = DEFAULT_TEMPLATE_IDS if template_ids is None else template_ids
    font_manifest_path = font_manifest_path or default_font_manifest_path()
    text_corpus_path = text_corpus_path or default_text_corpus_path()
    source_corpus = source_corpus_id(text_corpus_path)
    documents = generate_documents(
        count,
        seed,
        template_ids,
        font_manifest_path,
        text_corpus_path,
        output_dir,
        persona=persona,
        condition=condition,
        record_line_geometry=record_line_geometry,
        emit_paired_render=emit_paired_render,
        plain_evaluation=plain_evaluation,
    )
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
                source_corpus=source_corpus,
                composition_mode="plain_evaluation" if plain_evaluation else None,
            ),
            controls=SampleControls(persona=persona, condition=condition),
        )
        for document in documents
    ]
    return GenerationManifest(samples=samples), documents


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
    text_corpus_path: Path | None = None,
    emit_line_annotations: bool = False,
    emit_paired_render: bool = False,
    plain_evaluation: bool = False,
) -> GenerationManifest:
    if plain_evaluation and not emit_line_annotations:
        raise ValueError("plain evaluation requires line annotations for quality screening")
    manifest, documents = _generate_manifest_and_documents(
        count,
        seed,
        output_dir,
        template_ids,
        text_corpus_path=text_corpus_path,
        persona=persona,
        condition=condition,
        record_line_geometry=emit_line_annotations,
        emit_paired_render=emit_paired_render,
        plain_evaluation=plain_evaluation,
    )
    manifest_path = write_manifest(manifest, output_dir)
    if emit_line_annotations:
        # Imported lazily: line_annotations imports this module.
        from hocrsyngen.line_annotations import write_line_annotations

        write_line_annotations(manifest, documents, manifest_path)
    if emit_paired_render:
        from hocrsyngen.paired_render import write_paired_render

        write_paired_render(manifest, documents, manifest_path)
    return manifest
