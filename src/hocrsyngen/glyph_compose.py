"""S16b: compose scanned printed book pages from a real-glyph bank.

Each page takes one style (one book's typeface) from a ``printed_glyph_bank.v1``
directory and lays out corpus text as a book page: optional running header,
one or two justified RTL columns of paragraphs, and an optional footer page
number. Every placed glyph is recorded, so the gold text of every line is
exactly the glyph sequence drawn on it (``_check_line_gold``). Only Pillow is
used, and every random draw comes from a per-page ``random.Random`` seeded
from the batch seed and the page index.

See ``docs/glyph_page_composition.md`` for the layout, gold guarantees and
limitations.
"""

from __future__ import annotations

import json
import math
import random
import statistics
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import resources
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import jsonschema
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageStat

from hocrsyngen.assets import synthetic_data_path
from hocrsyngen.generator import (
    GLYPH_COMPOSER_VERSION,
    PRINTED_BOOK_GLYPH_TEMPLATE_ID,
    SyntheticDocument,
    _LineRecorder,
    _RecordedLine,
    composed_template_entry,
    load_text_corpus,
    source_corpus_id,
    write_manifest,
)
from hocrsyngen.glyph_bank import BANK_SCHEMA, GlyphBank, GlyphBankError, GlyphRecord, GlyphStyle, load_glyph_bank
from hocrsyngen.io import sha256_file
from hocrsyngen.manifest import GeneratedSample, GenerationManifest, PageAsset, SampleControls, SampleProvenance, TextMetadata


GLYPH_PROVENANCE_FILENAME = "glyph_provenance.json"
GLYPH_PROVENANCE_SCHEMA = "hocrsyngen_glyph_provenance.v1"
COMPOSITION_REPORT_SCHEMA = "glyph_composition_report.v1"
DEFAULT_GLYPH_TEXT_CORPUS = "texts/hebrew_typographic_lines_train_v1.txt"

# A line keeps glyphs whose source x-height is within this ratio of the band
# target, and scales each to the target by at most GLYPH_SCALE_LIMIT.
SIZE_BAND_TOLERANCE = 0.12
GLYPH_SCALE_LIMIT = 0.08
# A heading band is a cluster of glyphs at least this much larger than body type.
HEADING_BAND_MIN_RATIO = 1.3
HEADING_BAND_MIN_GLYPHS = 60
# Styles with fewer renderable corpus lines are not used: pages would repeat text.
MIN_ELIGIBLE_CORPUS_LINES = 100
# Line pitch never goes below this multiple of the body x-height, whatever the
# bank metric says, so ascenders (ל) and descenders (ק ך ן ף ץ) of adjacent
# lines do not collide.
MIN_PITCH_X_HEIGHTS = 1.6
# Within one band, a glyph whose ink width or height (in x-heights) is outside
# this ratio of its character's median is treated as a mislabelled fragment.
OUTLIER_RATIO = (0.6, 1.6)
OUTLIER_MIN_RECORDS = 6
# Two-part marks whose glyph must span at least this many x-heights: a colon
# or semicolon cut to one dot would draw a period or comma. This holds even
# when every variant of the mark in a style is broken, where the median-based
# outlier test cannot help.
MIN_INK_HEIGHT_X_HEIGHTS = {":": 0.45, ";": 0.45}
# A glyph is rejected when more than this share of the crop's dark pixels
# inside its ink box lies outside its (dilated) mask: the mask lost a stroke,
# for example the detached left leg of ה, and would draw another letter.
MAX_UNCOVERED_INK = 0.06
# A glyph whose ink is not this much darker than its own crop paper is unusable.
MIN_GLYPH_CONTRAST = 16
# Stroke-weight banding: a glyph's apparent stroke weight (2 * ink mass under
# the mask / mask boundary, in x-heights), over the band's median letter weight times its
# character's own factor, must lie in WEIGHT_BAND. A character's factor (its
# median over the band median) is clamped to WEIGHT_CHAR_FACTOR.
WEIGHT_BAND = (0.85, 1.15)
WEIGHT_CHAR_FACTOR = (0.85, 1.15)
# Each page prefers variants near its own weight (a light or heavy printing).
PAGE_WEIGHT_RANGE = (0.95, 1.05)
PAGE_WEIGHT_SPREAD = 0.08
# Paper: only the high-pass texture of a patch (patch - GaussianBlur(patch, r))
# is used, and patches whose low-pass part varies more than this (shadows,
# gradients, stains) are rejected.
PAPER_HIGH_PASS_RADIUS = 8
PAPER_MAX_LOW_STD = 4.0
PAPER_MAX_LOW_RANGE = 24
# Styles whose paper is this light are renders of bitonal scans: white paper,
# no grain, tint or show-through.
BITONAL_PAPER_GRAY = 250
# High-pass grain is rescaled to this standard deviation (grey levels) and
# clipped; a patch with more than PAPER_MAX_GRAIN_OUTLIERS of its pixels beyond
# PAPER_GRAIN_OUTLIER levels holds sharp marks and is rejected.
PAPER_GRAIN_STD = 3.0
PAPER_GRAIN_CLIP = 10
PAPER_GRAIN_OUTLIER = 20
PAPER_MAX_GRAIN_OUTLIERS = 0.002
# Largest allowed deviation of one row's or column's mean high-pass level.
PAPER_MAX_STRIPE = 2
# Style weight is its usable glyph count, capped at this multiple of the median.
STYLE_WEIGHT_CAP_MEDIANS = 3.0
# Gershayim / double quote may be built from two adjacent single marks.
SYNTHESIZED_DOUBLE_MARKS = {"״": ("׳", "'"), '"': ("'", "׳")}
GLYPH_CACHE_SIZE = 20000
# Gold boxes use mask pixels at or above this feathered-mask level.
MASK_VISIBLE_LEVEL = 24

Box = tuple[float, float, float, float]


class GlyphCompositionError(ValueError):
    pass


def default_glyph_text_corpus_path() -> Path:
    return synthetic_data_path(DEFAULT_GLYPH_TEXT_CORPUS)


# ---------------------------------------------------------------- bidi ----


def bidi_levels(text: str) -> list[int] | None:
    """Embedding levels (1 = RTL, 2 = LTR run) for ``text`` in an RTL paragraph.

    A reduced Unicode Bidirectional Algorithm (rules W1-W7, N1-N2, I2) for text
    without explicit embeddings, which is all the corpus loader admits. Returns
    ``None`` for text the composer does not render: an LTR run that crosses a
    space (a multi-word Latin phrase) or a mirrored character inside an LTR run.
    """

    types = [unicodedata.bidirectional(char) or "ON" for char in text]
    # W1: non-spacing marks take the previous type (niqqud is rejected earlier).
    for index, kind in enumerate(types):
        if kind == "NSM":
            types[index] = types[index - 1] if index else "R"
    types = ["R" if kind == "AL" else "EN" if kind == "AN" else kind for kind in types]
    # W4: a single separator between two numbers joins them.
    for index in range(1, len(types) - 1):
        if types[index] in ("ES", "CS") and types[index - 1] == "EN" and types[index + 1] == "EN":
            types[index] = "EN"
    # W5: terminators next to numbers become numbers.
    changed = True
    while changed:
        changed = False
        for index, kind in enumerate(types):
            if kind == "ET" and (
                (index > 0 and types[index - 1] == "EN") or (index + 1 < len(types) and types[index + 1] == "EN")
            ):
                types[index] = "EN"
                changed = True
    # W6: remaining separators and terminators are neutral.
    types = ["ON" if kind in ("ES", "ET", "CS") else kind for kind in types]
    # W7: numbers after a Latin letter are Latin.
    last_strong = "R"
    for index, kind in enumerate(types):
        if kind in ("L", "R"):
            last_strong = kind
        elif kind == "EN" and last_strong == "L":
            types[index] = "L"
    # N1/N2: neutral runs between same-direction strong types take it; else RTL.
    strong = ["R" if kind in ("R", "EN") else "L" if kind == "L" else None for kind in types]
    index = 0
    while index < len(types):
        if strong[index] is not None:
            index += 1
            continue
        end = index
        while end < len(types) and strong[end] is None:
            end += 1
        before = strong[index - 1] if index > 0 else "R"
        after = strong[end] if end < len(types) else "R"
        resolved = before if before == after else "R"
        for position in range(index, end):
            types[position] = resolved
        index = end
    levels = [2 if kind in ("L", "EN") else 1 for kind in types]
    for char, level in zip(text, levels):
        if level == 2 and (char.isspace() or unicodedata.mirrored(char)):
            return None
    return levels


def rtl_placement_order(levels: Sequence[int]) -> list[int]:
    """Indices in right-to-left placement order: logical order with LTR runs reversed."""

    order: list[int] = []
    index = 0
    while index < len(levels):
        if levels[index] == 2:
            end = index
            while end < len(levels) and levels[end] == 2:
                end += 1
            order.extend(range(end - 1, index - 1, -1))
            index = end
        else:
            order.append(index)
            index += 1
    return order


# ------------------------------------------------------------ text prep ----


def _hebrew_mark(char: str) -> bool:
    return unicodedata.category(char).startswith("M")


def corpus_skip_reason(line: str) -> str | None:
    """Style-independent reason the composer cannot render ``line``, or ``None``."""

    if any(_hebrew_mark(char) for char in line):
        return "niqqud_or_combining_mark"
    if any(unicodedata.category(char) in ("Cc", "Cf", "Co", "Cs") for char in line):
        return "control_or_format_char"
    if bidi_levels(line) is None:
        return "unsupported_bidi"
    return None


def renderable_chars(available: frozenset[str] | set[str]) -> set[str]:
    chars = set(available)
    for double, singles in SYNTHESIZED_DOUBLE_MARKS.items():
        if any(single in available for single in singles):
            chars.add(double)
    return chars


def gematria(number: int) -> str:
    """Hebrew letter numeral for 1..999 (טו and טז for 15 and 16), without geresh."""

    if not 1 <= number <= 999:
        raise ValueError(f"gematria supports 1..999, got {number}")
    hundreds = ["", "ק", "ר", "ש", "ת", "תק", "תר", "תש", "תת", "תתק"]
    tens = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"]
    ones = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]
    rest = number % 100
    if rest == 15:
        tail = "טו"
    elif rest == 16:
        tail = "טז"
    else:
        tail = tens[rest // 10] + ones[rest % 10]
    return hundreds[number // 100] + tail


# ------------------------------------------------------------ size bands ----


@dataclass
class SizeBand:
    """Glyphs of one style within ``SIZE_BAND_TOLERANCE`` of a target x-height."""

    target_x_height: float
    by_char: dict[str, list[GlyphRecord]]
    outliers_dropped: int = 0
    mask_rejected: int = 0
    weight_dropped: int = 0
    # glyph_id -> stroke weight relative to the band norm (1.0 = typical).
    weights: dict[str, float] = field(default_factory=dict)

    @property
    def chars(self) -> frozenset[str]:
        return frozenset(self.by_char)

    @property
    def glyph_count(self) -> int:
        return sum(len(records) for records in self.by_char.values())


def _drop_outliers(records: list[GlyphRecord]) -> list[GlyphRecord]:
    records = [
        record
        for record in records
        if (record.ink_box[3] - record.ink_box[1]) >= MIN_INK_HEIGHT_X_HEIGHTS.get(record.char, 0.0) * record.x_height_px
    ]
    if len(records) < OUTLIER_MIN_RECORDS:
        return records
    widths = [record.ink_width / record.x_height_px for record in records]
    heights = [(record.ink_box[3] - record.ink_box[1]) / record.x_height_px for record in records]
    median_width, median_height = statistics.median(widths), statistics.median(heights)
    low, high = OUTLIER_RATIO
    return [
        record
        for record, width, height in zip(records, widths, heights)
        if low <= width / median_width <= high and low <= height / median_height <= high
    ]


def size_band(
    bank: GlyphBank, style_id: str, target: float, images: _GlyphImages | None = None
) -> SizeBand:
    """The style's glyphs near ``target``, without size outliers and (given
    ``images``) without glyphs whose mask lost part of their ink."""

    by_char: dict[str, list[GlyphRecord]] = {}
    dropped = rejected = 0
    for char, records in sorted(bank.by_style_char.get(style_id, {}).items()):
        in_band = [record for record in records if abs(record.x_height_px / target - 1.0) <= SIZE_BAND_TOLERANCE]
        kept = _drop_outliers(in_band)
        dropped += len(in_band) - len(kept)
        if images is not None:
            usable = [record for record in kept if images.usable(record)]
            rejected += len(kept) - len(usable)
            kept = usable
        if kept:
            by_char[char] = kept
    band = SizeBand(target_x_height=target, by_char=by_char, outliers_dropped=dropped, mask_rejected=rejected)
    if images is not None:
        _band_by_weight(band, images)
    return band


def _band_by_weight(band: SizeBand, images: _GlyphImages) -> None:
    """Keep the band's regular-weight glyphs: drop bold (or hairline) variants
    that leaked from headings or emphasis into the same face and size."""

    weights = {
        record.glyph_id: images.stroke_weight(record) for records in band.by_char.values() for record in records
    }
    letters = [weights[record.glyph_id] for char, records in band.by_char.items() if _is_hebrew_letter(char) for record in records]
    norm = statistics.median(letters or list(weights.values()) or [1.0])
    if norm <= 0:
        return
    low_factor, high_factor = WEIGHT_CHAR_FACTOR
    low, high = WEIGHT_BAND
    for char in list(band.by_char):
        records = band.by_char[char]
        # A letter may be a little heavier or lighter by design, but a letter
        # that is bold everywhere cannot set its own norm.
        factor = min(high_factor, max(low_factor, statistics.median(weights[r.glyph_id] for r in records) / norm))
        kept = []
        for record in records:
            relative = weights[record.glyph_id] / (norm * factor)
            if low <= relative <= high:
                band.weights[record.glyph_id] = relative
                kept.append(record)
        band.weight_dropped += len(records) - len(kept)
        if kept:
            band.by_char[char] = kept
        else:
            del band.by_char[char]


def _is_hebrew_letter(char: str) -> bool:
    return "\u05d0" <= char <= "\u05ea"


def _heading_band(bank: GlyphBank, style: GlyphStyle, images: _GlyphImages | None) -> SizeBand | None:
    body = style.metrics.x_height_px
    large = sorted(
        record.x_height_px
        for records in bank.by_style_char.get(style.style_id, {}).values()
        for record in records
        if record.x_height_px >= body * HEADING_BAND_MIN_RATIO
    )
    if len(large) < HEADING_BAND_MIN_GLYPHS:
        return None
    band = size_band(bank, style.style_id, statistics.median(large), images)
    return band if band.glyph_count >= HEADING_BAND_MIN_GLYPHS else None


@dataclass
class StylePlan:
    style: GlyphStyle
    body: SizeBand
    heading: SizeBand | None
    eligible_lines: list[str]
    skipped_missing_glyph: int
    missing_chars: Counter
    weight: float = 0.0


# --------------------------------------------------------- glyph images ----


class _GlyphImages:
    """Lazily loaded, normalised glyph darkness and feathering masks."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[str, tuple[Image.Image, Image.Image]] = {}
        self._paper: dict[str, Image.Image] = {}
        self._verdicts: dict[str, bool] = {}
        self._weights: dict[str, float] = {}
        self.rejected: set[str] = set()

    def stroke_weight(self, record: GlyphRecord) -> float:
        """Apparent stroke weight in x-heights: 2 * ink mass / mask boundary.

        Ink mass is the normalised darkness summed under the mask, so a
        glyph reads heavier when its strokes are thicker or blacker, as bold
        type does.
        """

        weight = self._weights.get(record.glyph_id)
        if weight is None:
            crop, mask = self._read(record)
            weight = self._weights[record.glyph_id] = self._weight_of(record, crop, mask)
        return weight

    @staticmethod
    def _weight_of(record: GlyphRecord, crop: Image.Image, mask: Image.Image) -> float:
        background = max(_percentile(crop.histogram(), 0.92), 64)
        lut = [min(255, round(value * 255 / background)) for value in range(256)]
        darkness = ImageChops.invert(crop.point(lut))
        mass = ImageStat.Stat(darkness, mask).sum[0] / 255
        return _stroke_thickness(mask, mass) / record.x_height_px

    def usable(self, record: GlyphRecord) -> bool:
        """False when the mask misses part of the crop's ink inside the ink box."""

        verdict = self._verdicts.get(record.glyph_id)
        if verdict is None:
            crop, mask = self._read(record)
            # Measured on the same read, for weight banding.
            self._weights.setdefault(record.glyph_id, self._weight_of(record, crop, mask))
            background = _percentile(crop.histogram(), 0.92)
            # The glyph's own ink level: a low percentile of the crop under its mask.
            ink = _percentile(crop.histogram(mask=mask), 0.10)
            verdict = background - ink >= MIN_GLYPH_CONTRAST
            if verdict:
                # "Dark" is relative to this crop, so light ink and grey
                # antialiased edges are judged against their own paper.
                threshold = background - 0.5 * (background - ink)
                box = record.ink_box
                dark = crop.crop(box).point(lambda value: 255 if value < threshold else 0)
                covered = mask.filter(ImageFilter.MaxFilter(3)).crop(box)
                dark_count = dark.histogram()[255]
                uncovered = ImageChops.subtract(dark, covered).histogram()[255]
                verdict = dark_count > 0 and uncovered <= MAX_UNCOVERED_INK * dark_count
            self._verdicts[record.glyph_id] = verdict
            if not verdict:
                self.rejected.add(record.glyph_id)
        return verdict

    def glyph(self, record: GlyphRecord) -> tuple[Image.Image, Image.Image]:
        cached = self._cache.get(record.glyph_id)
        if cached is not None:
            return cached
        if len(self._cache) >= GLYPH_CACHE_SIZE:
            self._cache.clear()
        cached = self._cache[record.glyph_id] = self._load(record)
        return cached

    def _read(self, record: GlyphRecord) -> tuple[Image.Image, Image.Image]:
        """The crop and its binary (0/255) mask, checked against the record."""

        try:
            with Image.open(self.root / record.asset_path) as image:
                crop = image.convert("L")
            with Image.open(self.root / record.mask_path) as image:
                mask_image = image.convert("L")
        except OSError as exc:
            raise GlyphBankError(f"Glyph {record.glyph_id} image is unreadable: {exc}") from exc
        if crop.size != record.size or mask_image.size != record.size:
            raise GlyphBankError(
                f"Glyph {record.glyph_id} crop {crop.size} / mask {mask_image.size} != record size {record.size}."
            )
        mask_image = mask_image.point(lambda value: 255 if value >= 128 else 0)
        if mask_image.getbbox() is None:
            raise GlyphBankError(f"Glyph {record.glyph_id} mask has no ink.")
        return crop, mask_image

    def _load(self, record: GlyphRecord) -> tuple[Image.Image, Image.Image]:
        crop, mask_image = self._read(record)
        # Normalise the crop's own paper to white: divide by a high percentile.
        background = max(_percentile(crop.histogram(), 0.92), 64)
        lut = [min(255, round(value * 255 / background)) for value in range(256)]
        darkness = ImageChops.invert(crop.point(lut))
        # Slight dilation keeps the antialiased stroke edge the binary mask misses.
        mask_image = mask_image.filter(ImageFilter.MaxFilter(3))
        return darkness, mask_image

    def paper_grain(self, relative_path: str) -> Image.Image | None:
        """The patch's high-pass texture around 128, or ``None`` for a patch
        with shadows, gradients or stains (high low-frequency variation)."""

        if relative_path in self._paper:
            return self._paper[relative_path]
        try:
            with Image.open(self.root / relative_path) as image:
                patch = image.convert("L")
        except OSError as exc:
            raise GlyphBankError(f"Paper patch {relative_path} is unreadable: {exc}") from exc
        grain = None
        margin = PAPER_HIGH_PASS_RADIUS
        if min(patch.size) > 2 * margin + 16:
            low = patch.filter(ImageFilter.GaussianBlur(PAPER_HIGH_PASS_RADIUS))
            inner = (margin, margin, patch.width - margin, patch.height - margin)
            low_inner = low.crop(inner)
            low_min, low_max = low_inner.getextrema()
            if (
                ImageStat.Stat(low_inner).stddev[0] <= PAPER_MAX_LOW_STD
                and low_max - low_min <= PAPER_MAX_LOW_RANGE
            ):
                grain = ImageChops.subtract(patch, low, scale=1.0, offset=128).crop(inner)
                histogram = grain.histogram()
                outliers = sum(histogram[: 128 - PAPER_GRAIN_OUTLIER]) + sum(histogram[128 + PAPER_GRAIN_OUTLIER + 1 :])
                deviation = ImageStat.Stat(grain).stddev[0]
                if (
                    outliers > PAPER_MAX_GRAIN_OUTLIERS * sum(histogram)
                    or deviation < 0.25
                    or _has_stripe(grain)
                ):
                    # Sharp features (ink remnants, edges, fold lines) or no texture.
                    grain = None
                else:
                    # Same texture strength for every patch, clipped, so tiles
                    # cannot be told apart by roughness or stray marks.
                    scale = PAPER_GRAIN_STD / deviation
                    limit = PAPER_GRAIN_CLIP
                    grain = grain.point(
                        [round(128 + max(-limit, min(limit, (value - 128) * scale))) for value in range(256)]
                    )
        self._paper[relative_path] = grain
        return grain


def _stroke_thickness(mask: Image.Image, area: float | None = None) -> float:
    """2 * ink area / boundary length of a binary mask: mean stroke width in px.

    ``area`` replaces the mask's pixel count (for example by its ink mass)."""

    if area is None:
        area = mask.histogram()[255]
    # Pad so ink on the crop border still has a boundary.
    padded = Image.new("L", (mask.width + 2, mask.height + 2), 0)
    padded.paste(mask, (1, 1))
    boundary = ImageChops.difference(padded, padded.filter(ImageFilter.MinFilter(3))).histogram()[255]
    return 2 * area / boundary if boundary else 0.0


def _has_stripe(grain: Image.Image) -> bool:
    """True when a row or column of the high-pass texture is consistently
    lighter or darker than the rest: a page edge, rule or fold line."""

    for image in (grain, grain.transpose(Image.Transpose.TRANSPOSE)):
        # Each output pixel is one column's mean.
        means = image.resize((image.width, 1), Image.Resampling.BOX).getdata()
        if any(abs(value - 128) > PAPER_MAX_STRIPE for value in means):
            return True
    return False


def _percentile(histogram: Sequence[int], fraction: float) -> int:
    total = sum(histogram)
    running = 0
    for value, count in enumerate(histogram):
        running += count
        if running >= fraction * total:
            return value
    return len(histogram) - 1


# ------------------------------------------------------------- layout ----


@dataclass
class _PlannedGlyph:
    record: GlyphRecord
    gold_char: str
    offset_in_word: int
    scale: float
    dy: int

    @property
    def ink_width(self) -> float:
        return self.record.ink_width * self.scale


@dataclass
class _Word:
    text: str
    glyphs: list[_PlannedGlyph]  # right-to-left placement order
    gaps: list[float]  # gap after each glyph but the last, leftwards

    @property
    def width(self) -> float:
        return sum(glyph.ink_width for glyph in self.glyphs) + sum(self.gaps)


@dataclass(frozen=True)
class PlacedGlyph:
    glyph_id: str
    bank_char: str
    gold_char: str
    char_index: int
    box: tuple[int, int, int, int]
    source_page_id: str


@dataclass
class ComposedLine:
    region: str
    region_key: str
    text: str
    baseline_y: float
    glyphs: list[PlacedGlyph] = field(default_factory=list)

    def ink_box(self) -> tuple[int, int, int, int]:
        left = min(glyph.box[0] for glyph in self.glyphs)
        top = min(glyph.box[1] for glyph in self.glyphs)
        right = max(glyph.box[2] for glyph in self.glyphs)
        bottom = max(glyph.box[3] for glyph in self.glyphs)
        baseline = round(self.baseline_y)
        return (left, min(top, baseline), right, max(bottom, baseline + 1))


@dataclass
class ComposedPage:
    sample_id: str
    sample_index: int
    style_id: str
    size: tuple[int, int]
    lines: list[ComposedLine]
    rotation_degrees: float
    asset_path: str
    path: Path
    sha256: str
    degradation: dict[str, Any]
    document: SyntheticDocument
    dropped_wide_words: int = 0


def _sample_triple(rng: random.Random, triple: tuple[float, float, float]) -> float:
    low, median, high = triple
    if high <= low:
        return median
    return rng.triangular(low, high, median)


class _PageComposer:
    def __init__(self, plan: StylePlan, images: _GlyphImages, rng: random.Random) -> None:
        self.plan = plan
        self.style = plan.style
        self.metrics = plan.style.metrics
        self.images = images
        self.rng = rng
        self.page_scale = 1.0
        self.weight_target = 1.0
        self.bitonal = plan.style.metrics.paper_gray >= BITONAL_PAPER_GRAY
        self.dropped_wide_words = 0
        self._deck: list[str] = []

    # --- words

    def _choose(self, band: SizeBand, char: str, previous: GlyphRecord | None) -> GlyphRecord:
        records = band.by_char[char]
        if previous is not None and previous.char == char and len(records) > 1:
            records = [record for record in records if record.glyph_id != previous.glyph_id]
        if band.weights:
            target = self.weight_target
            preference = [
                math.exp(-(((band.weights.get(record.glyph_id, 1.0) - target) / PAGE_WEIGHT_SPREAD) ** 2))
                for record in records
            ]
            return self.rng.choices(records, weights=preference)[0]
        return records[self.rng.randrange(len(records))]

    def _glyph_scale(self, band: SizeBand, record: GlyphRecord) -> float:
        ratio = band.target_x_height / record.x_height_px
        ratio = min(1 + GLYPH_SCALE_LIMIT, max(1 - GLYPH_SCALE_LIMIT, ratio))
        return self.page_scale * ratio * self.rng.uniform(0.985, 1.015)

    def build_word(self, word: str, levels: Sequence[int], band: SizeBand) -> _Word:
        glyphs: list[_PlannedGlyph] = []
        gaps: list[float] = []
        previous: GlyphRecord | None = None
        for offset in rtl_placement_order(levels):
            char = word[offset]
            if char in band.by_char:
                parts = [char]
                source_char = char
            else:
                source_char = next(single for single in SYNTHESIZED_DOUBLE_MARKS[char] if single in band.by_char)
                parts = [source_char, source_char]
            for part_index, _part in enumerate(parts):
                record = self._choose(band, source_char, previous)
                if glyphs:
                    if part_index == 1:
                        gap = max(1.0, band.target_x_height * self.page_scale * self.rng.uniform(0.08, 0.16))
                    else:
                        gap = _sample_triple(self.rng, self.metrics.letter_gap_px) * self.page_scale
                        gap += self.rng.uniform(-0.4, 0.4)
                    # Letters may touch or overlap slightly, never by much.
                    gap = max(gap, -0.25 * min(glyphs[-1].ink_width, record.ink_width))
                    gaps.append(gap)
                glyphs.append(
                    _PlannedGlyph(
                        record=record,
                        gold_char=char,
                        offset_in_word=offset,
                        scale=self._glyph_scale(band, record),
                        dy=self.rng.randint(-1, 1),
                    )
                )
                previous = record
        return _Word(text=word, glyphs=glyphs, gaps=gaps)

    def word_gap(self) -> float:
        return max(1.0, _sample_triple(self.rng, self.metrics.word_gap_px) * self.page_scale)

    # --- paragraphs

    def paragraph_words(self, band: SizeBand) -> list[_Word]:
        sentences: list[str] = []
        target = self.rng.randint(3, 10)
        attempts = 0
        while len(sentences) < target and attempts < target * 4:
            attempts += 1
            if not self._deck:
                # Draw sentences without replacement within a page.
                self._deck = list(self.plan.eligible_lines)
                self.rng.shuffle(self._deck)
            candidate = self._deck.pop()
            if bidi_levels(" ".join([*sentences, candidate])) is None:
                continue
            sentences.append(candidate)
        text = " ".join(" ".join(sentences).split())
        levels = bidi_levels(text)
        assert levels is not None
        words: list[_Word] = []
        position = 0
        for word in text.split(" "):
            words.append(self.build_word(word, levels[position : position + len(word)], band))
            position += len(word) + 1
        return words

    def phrase_word(self, text: str, band: SizeBand) -> list[_Word]:
        levels = bidi_levels(text)
        assert levels is not None
        words: list[_Word] = []
        position = 0
        for word in text.split(" "):
            words.append(self.build_word(word, levels[position : position + len(word)], band))
            position += len(word) + 1
        return words


@dataclass
class _LinePlan:
    region: str
    region_key: str
    words: list[_Word]
    gaps: list[float]
    right_x: float
    baseline_y: float

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


def _short_phrase(rng: random.Random, pool: Sequence[str], band_chars: set[str], max_words: int) -> str | None:
    for _ in range(12):
        words = pool[rng.randrange(len(pool))].split()
        count = rng.randint(1, min(max_words, len(words)))
        phrase = " ".join(words[:count])
        phrase = phrase.strip("".join({char for char in phrase if unicodedata.category(char).startswith("P")}))
        phrase = " ".join(phrase.split())
        if phrase and set(phrase.replace(" ", "")) <= band_chars and bidi_levels(phrase) is not None:
            return phrase
    return None


def _page_number_text(rng: random.Random, number: int, band_chars: set[str]) -> str | None:
    digits = str(number)
    hebrew = gematria(number)
    use_digits = set(digits) <= band_chars and (rng.random() < 0.7 or not set(hebrew) <= band_chars)
    if use_digits:
        return digits
    if set(hebrew) <= band_chars:
        return hebrew
    return None


def _layout_page(composer: _PageComposer, width: int, height: int) -> list[_LinePlan]:
    rng = composer.rng
    plan = composer.plan
    metrics = composer.metrics
    scale = composer.page_scale
    x_height = metrics.x_height_px * scale
    pitch = max(metrics.line_pitch_px, MIN_PITCH_X_HEIGHTS * metrics.x_height_px) * scale * rng.uniform(0.98, 1.04)
    column_width = metrics.text_block_width_px * scale * rng.uniform(0.95, 1.03)
    column_gap = x_height * rng.uniform(1.6, 2.6)
    usable = width * rng.uniform(0.8, 0.88)
    columns = max(1, min(2, int((usable + column_gap) // (column_width + column_gap))))
    column_width = min(column_width, (usable - (columns - 1) * column_gap) / columns)
    block_width = columns * column_width + (columns - 1) * column_gap
    page_number = rng.randint(3, 480)
    side_margin = (width - block_width) / 2
    gutter_shift = side_margin * rng.uniform(0.0, 0.2) * (1 if page_number % 2 else -1)
    block_left = side_margin + gutter_shift
    block_right = block_left + block_width
    top = height * rng.uniform(0.05, 0.08)
    bottom_limit = height * (1 - rng.uniform(0.06, 0.09))

    body_chars = renderable_chars(plan.body.chars)
    heading_band = plan.heading or plan.body
    heading_chars = renderable_chars(heading_band.chars)
    lines: list[_LinePlan] = []

    def phrase_line(text: str, band: SizeBand, region_key: str, baseline: float, align: str) -> _LinePlan:
        words = composer.phrase_word(text, band)
        gaps = [composer.word_gap() for _ in words[1:]]
        natural = sum(word.width for word in words) + sum(gaps)
        if align == "center":
            right = (block_left + block_right) / 2 + natural / 2
        elif align == "left":
            right = block_left + natural
        else:
            right = block_right
        return _LinePlan("title" if region_key.startswith("title") else "footer", region_key, words, gaps, right, baseline)

    # Running header: page number at the outer corner and/or a short title.
    baseline = top + x_height * 1.4
    header_kind = rng.choices(["none", "number_and_title", "title", "number"], weights=[0.3, 0.45, 0.1, 0.15])[0]
    header_number = None
    if header_kind in ("number_and_title", "number"):
        header_number = _page_number_text(rng, page_number, body_chars)
    header_title = None
    header_band = heading_band if rng.random() < 0.6 else plan.body
    if header_kind in ("number_and_title", "title"):
        header_title = _short_phrase(rng, plan.eligible_lines, renderable_chars(header_band.chars), 3)
    header_items: list[_LinePlan] = []
    if header_title:
        header_items.append(phrase_line(header_title, header_band, "title:header", baseline, "center"))
    if header_number:
        header_items.append(
            phrase_line(header_number, plan.body, "title:header", baseline, "left" if page_number % 2 else "right")
        )
    if header_items:
        # Right-to-left reading order along the shared baseline.
        header_items.sort(key=lambda item: -item.right_x)
        lines.extend(header_items)
        body_top = baseline + pitch * rng.uniform(1.6, 2.3)
    else:
        body_top = top + x_height * 1.6

    starts_mid_paragraph = rng.random() < 0.6
    if not starts_mid_paragraph and rng.random() < 0.15 and plan.heading is not None:
        heading = _short_phrase(rng, plan.eligible_lines, heading_chars, 4)
        if heading:
            lines.append(phrase_line(heading, plan.heading, "title:heading", body_top, "center"))
            body_top += pitch * rng.uniform(1.6, 2.1)

    footer_number = None
    if header_number is None and rng.random() < 0.6:
        footer_number = _page_number_text(rng, page_number, body_chars)
    body_bottom = bottom_limit - (pitch * 1.6 if footer_number else 0.0)
    lines_per_column = max(1, int((body_bottom - body_top) // pitch) + 1)

    indent = x_height * rng.uniform(1.4, 3.0)
    pending: list[_Word] = []
    paragraph_start = False
    first_paragraph = True
    last_baseline = body_top
    for column in range(columns):
        column_right = block_right - column * (column_width + column_gap)
        for row in range(lines_per_column):
            line_baseline = body_top + row * pitch
            words: list[_Word] = []
            gaps: list[float] = []
            natural = 0.0
            while not words:
                if not pending:
                    pending = composer.paragraph_words(plan.body)
                    # A page may open in the middle of a paragraph (no indent).
                    paragraph_start = not (first_paragraph and starts_mid_paragraph)
                    first_paragraph = False
                available = column_width - (indent if paragraph_start else 0.0)
                while pending:
                    word = pending[0]
                    if not words and word.width > available:
                        # Never drawn and so never in gold.
                        pending.pop(0)
                        composer.dropped_wide_words += 1
                        continue
                    gap = composer.word_gap() if words else 0.0
                    if words and natural + gap + word.width > available:
                        break
                    words.append(pending.pop(0))
                    if len(words) > 1:
                        gaps.append(gap)
                    natural += gap + word.width
            last_of_paragraph = not pending
            right_x = column_right - (indent if paragraph_start else 0.0)
            if not last_of_paragraph and len(words) > 1:
                extra = available - natural
                median_gap = metrics.word_gap_px[1] * scale
                if extra / (len(words) - 1) <= max(4 * median_gap, 2.5 * x_height):
                    weights = [rng.uniform(0.85, 1.15) for _ in gaps]
                    total = sum(weights)
                    gaps = [gap + extra * weight / total for gap, weight in zip(gaps, weights)]
            lines.append(_LinePlan("body", f"body:{column}", words, gaps, right_x, line_baseline))
            last_baseline = max(last_baseline, line_baseline)
            paragraph_start = False

    if footer_number:
        footer_baseline = min(last_baseline + pitch * rng.uniform(1.6, 2.4), height - x_height * 1.5)
        lines.append(phrase_line(footer_number, plan.body, "footer", footer_baseline, "center"))
    return lines


# ---------------------------------------------------------- compositing ----


def _illumination(rng: random.Random, size: tuple[int, int], amplitude: float) -> Image.Image:
    """A smooth multiplicative field (255 = unchanged): a gentle gradient plus a
    few large Gaussian blobs, at most ``amplitude`` darker than its brightest point."""

    width, height = size
    grid_w, grid_h = 48, max(2, round(48 * height / width))
    gradient = (rng.uniform(-1, 1), rng.uniform(-1, 1))
    blobs = [
        (rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0.15, 0.5), rng.uniform(-1, 1))
        for _ in range(rng.randint(2, 5))
    ]
    values = []
    for gy in range(grid_h):
        y = gy / (grid_h - 1)
        for gx in range(grid_w):
            x = gx / (grid_w - 1)
            value = 0.4 * (gradient[0] * (x - 0.5) + gradient[1] * (y - 0.5))
            for bx, by, sigma, weight in blobs:
                value += weight * math.exp(-((x - bx) ** 2 + (y - by) ** 2) / (2 * sigma**2))
            values.append(value)
    low, high = min(values), max(values)
    spread = (high - low) or 1.0
    field = Image.new("L", (grid_w, grid_h))
    field.putdata([round(255 * (1 - amplitude * (high - value) / spread)) for value in values])
    return field.resize(size, Image.Resampling.BICUBIC)


def _paper(composer: _PageComposer, size: tuple[int, int]) -> Image.Image:
    """Smooth base tone x illumination, plus high-pass grain from the patches."""

    rng = composer.rng
    width, height = size
    if composer.bitonal:
        return Image.new("L", size, 255)
    tone = min(255.0, composer.metrics.paper_gray * rng.uniform(0.98, 1.02))
    base = Image.new("L", size, round(tone))
    grains = [grain for path in composer.style.paper_patches if (grain := composer.images.paper_grain(path)) is not None]
    texture = Image.new("L", size, 128)
    if grains:
        # High-pass tiles have the same mean, so hard edges between randomly
        # flipped and offset tiles show no seam.
        tile = min(min(grain.size) for grain in grains)
        for top in range(0, height, tile):
            for left in range(0, width, tile):
                grain = grains[rng.randrange(len(grains))]
                x = rng.randint(0, grain.width - tile)
                y = rng.randint(0, grain.height - tile)
                piece = grain.crop((x, y, x + tile, y + tile))
                if rng.random() < 0.5:
                    piece = piece.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if rng.random() < 0.5:
                    piece = piece.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                texture.paste(piece, (left, top))
        strength = rng.uniform(0.7, 1.1)
    else:
        # No clean patch: synthesise fine grain.
        half = (max(1, width // 2), max(1, height // 2))
        noise = Image.frombytes("L", half, rng.randbytes(half[0] * half[1]))
        texture = noise.point([round(128 + (value - 128) * 0.05) for value in range(256)]).resize(
            size, Image.Resampling.BILINEAR
        )
        strength = 1.0
    if strength != 1.0:
        texture = texture.point([round(128 + (value - 128) * strength) for value in range(256)])
    paper = ImageChops.add(base, texture, scale=1.0, offset=-128)
    paper = ImageChops.multiply(paper, _illumination(rng, size, rng.uniform(0.01, 0.05)))
    # A soft binding shadow along one edge.
    if rng.random() < 0.2:
        shadow_width = max(2, round(width * rng.uniform(0.03, 0.07)))
        depth = rng.uniform(0.04, 0.1)
        values = [255] * width
        left_side = rng.random() < 0.5
        for offset in range(shadow_width):
            value = round(255 * (1 - depth * (1 - offset / shadow_width) ** 2))
            values[offset if left_side else width - 1 - offset] = value
        row = Image.new("L", (width, 1))
        row.putdata(values)
        paper = ImageChops.multiply(paper, row.resize(size, Image.Resampling.NEAREST))
    return paper


def _composite_lines(
    composer: _PageComposer, plans: list[_LinePlan], size: tuple[int, int]
) -> tuple[Image.Image, list[ComposedLine]]:
    rng = composer.rng
    ink = Image.new("L", size, 0)
    ink_factor = rng.uniform(0.86, 1.06)
    composed: list[ComposedLine] = []
    for plan in plans:
        line = ComposedLine(plan.region, plan.region_key, plan.text, plan.baseline_y)
        cursor = plan.right_x
        word_offset = 0
        for word_index, word in enumerate(plan.words):
            if word_index:
                cursor -= plan.gaps[word_index - 1]
            for glyph_index, glyph in enumerate(word.glyphs):
                if glyph_index:
                    cursor -= word.gaps[glyph_index - 1]
                record = glyph.record
                darkness, mask = composer.images.glyph(record)
                scaled = (max(1, round(record.size[0] * glyph.scale)), max(1, round(record.size[1] * glyph.scale)))
                sx = scaled[0] / record.size[0]
                sy = scaled[1] / record.size[1]
                ink_left = cursor - record.ink_width * sx
                x = round(ink_left - record.ink_box[0] * sx)
                y = round(plan.baseline_y - record.baseline_y * sy) + glyph.dy
                cursor = ink_left
                glyph_dark = darkness.resize(scaled, Image.Resampling.BICUBIC)
                glyph_mask = mask.resize(scaled, Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(0.6))
                factor = ink_factor * rng.uniform(0.95, 1.03)
                glyph_dark = ImageChops.multiply(glyph_dark, glyph_mask).point(
                    [min(255, round(value * factor)) for value in range(256)]
                )
                visible = glyph_mask.point(lambda value: 255 if value >= MASK_VISIBLE_LEVEL else 0).getbbox()
                if visible is None:
                    raise GlyphCompositionError(f"Glyph {record.glyph_id} has no visible ink after scaling.")
                box = (x, y, x + scaled[0], y + scaled[1])
                if box[0] < 0 or box[1] < 0 or box[2] > size[0] or box[3] > size[1]:
                    raise GlyphCompositionError(f"Glyph {record.glyph_id} would leave the page at {box}.")
                region = ink.crop(box)
                ink.paste(ImageChops.lighter(region, glyph_dark), box)
                line.glyphs.append(
                    PlacedGlyph(
                        glyph_id=record.glyph_id,
                        bank_char=record.char,
                        gold_char=glyph.gold_char,
                        char_index=word_offset + glyph.offset_in_word,
                        box=(x + visible[0], y + visible[1], x + visible[2], y + visible[3]),
                        source_page_id=record.source_page_id,
                    )
                )
            word_offset += len(word.text) + 1
        _check_line_gold(line)
        composed.append(line)
    return ink, composed


def _check_line_gold(line: ComposedLine) -> None:
    """Gold text must be exactly the placed glyph sequence (spaces are layout)."""

    rendered: dict[int, str] = {}
    counts: Counter = Counter()
    for glyph in line.glyphs:
        if rendered.setdefault(glyph.char_index, glyph.gold_char) != glyph.gold_char:
            raise GlyphCompositionError(f"Line {line.text!r}: two characters at index {glyph.char_index}.")
        counts[glyph.char_index] += 1
        synthesized = glyph.bank_char != glyph.gold_char
        if synthesized and glyph.bank_char not in SYNTHESIZED_DOUBLE_MARKS.get(glyph.gold_char, ()):
            raise GlyphCompositionError(f"Glyph {glyph.glyph_id} ({glyph.bank_char!r}) cannot render {glyph.gold_char!r}.")
    for index, char in enumerate(line.text):
        if char == " ":
            if index in rendered:
                raise GlyphCompositionError(f"Line {line.text!r}: a glyph was placed on a space.")
            continue
        if rendered.get(index) != char:
            raise GlyphCompositionError(f"Line {line.text!r}: character {index} ({char!r}) was not rendered.")
        expected = 2 if any(glyph.char_index == index and glyph.bank_char != char for glyph in line.glyphs) else 1
        if counts[index] != expected:
            raise GlyphCompositionError(f"Line {line.text!r}: character {index} has {counts[index]} glyphs.")
    if len(rendered) != len(line.text.replace(" ", "")):
        raise GlyphCompositionError(f"Line {line.text!r}: rendered glyphs outside the gold text.")


def _finish_page(
    composer: _PageComposer, paper: Image.Image, ink: Image.Image, lines: list[ComposedLine]
) -> tuple[Image.Image, float, dict[str, Any]]:
    rng = composer.rng
    size = paper.size
    params: dict[str, Any] = {}
    bitonal = composer.bitonal
    if not bitonal and rng.random() < 0.45:
        opacity = rng.uniform(0.04, 0.1)
        ghost = ImageChops.offset(
            ink.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
            rng.randint(-20, 20),
            round(composer.metrics.line_pitch_px * composer.page_scale * rng.uniform(0.3, 0.7)),
        ).filter(ImageFilter.GaussianBlur(rng.uniform(1.2, 2.2)))
        ghost = ghost.point([round(value * opacity) for value in range(256)])
        paper = ImageChops.multiply(paper, ImageChops.invert(ghost))
        params["show_through_opacity"] = round(opacity, 4)
    if rng.random() < 0.15:
        amount = rng.uniform(0.3, 0.6)
        ink = Image.blend(ink, ink.filter(ImageFilter.MaxFilter(3)), amount)
        params["ink_bleed"] = round(amount, 3)
    if rng.random() < 0.35:
        draw = ImageDraw.Draw(ink)
        boxes = [line.ink_box() for line in lines]
        count = round(size[0] * size[1] / 1e6 * rng.uniform(10, 50))
        drawn = 0
        for _ in range(count):
            x, y = rng.uniform(0, size[0] - 1), rng.uniform(0, size[1] - 1)
            if any(left - 12 <= x <= right + 12 and top - 12 <= y <= bottom + 12 for left, top, right, bottom in boxes):
                continue
            radius = rng.uniform(0.4, 1.3)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=rng.randint(110, 230))
            drawn += 1
        params["speckles"] = drawn
    page = ImageChops.multiply(paper, ImageChops.invert(ink))
    if not bitonal and rng.random() < 0.55:
        green, blue = rng.uniform(0.965, 0.99), rng.uniform(0.88, 0.95)
        page = Image.merge(
            "RGB",
            (page, page.point([round(v * green) for v in range(256)]), page.point([round(v * blue) for v in range(256)])),
        )
        params["tint"] = [1.0, round(green, 3), round(blue, 3)]
    else:
        page = page.convert("RGB")
    angle = rng.uniform(-0.7, 0.7)
    fill = tuple(round(value) for value in ImageStat.Stat(page.crop((0, 0, size[0], 16))).mean)
    page = page.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=fill)
    blur = rng.uniform(0.15, 0.6)
    page = page.filter(ImageFilter.GaussianBlur(blur))
    # Sensor noise only; paper texture comes from the patches.
    grain = 0.0 if bitonal else rng.uniform(0.01, 0.03)
    if grain:
        half = (max(1, size[0] // 2), max(1, size[1] // 2))
        noise = Image.frombytes("L", half, rng.randbytes(half[0] * half[1]))
        noise = noise.point([round(128 + (value - 128) * grain) for value in range(256)]).resize(
            size, Image.Resampling.BILINEAR
        )
        page = ImageChops.add(page, Image.merge("RGB", (noise, noise, noise)), scale=1.0, offset=-128)
    # A bitonal render keeps white paper: never dim it.
    contrast = rng.uniform(1.0, 1.1) if bitonal else rng.uniform(0.92, 1.1)
    brightness = rng.uniform(1.0, 1.04) if bitonal else rng.uniform(0.96, 1.04)
    page = ImageEnhance.Contrast(page).enhance(contrast)
    page = ImageEnhance.Brightness(page).enhance(brightness)
    params.update(
        rotation_degrees=round(angle, 6),
        blur_radius=round(blur, 4),
        grain=round(grain, 4),
        contrast=round(contrast, 4),
        brightness=round(brightness, 4),
        jpeg_quality=rng.randint(70, 90),
    )
    return page, angle, params


# ------------------------------------------------------------- planning ----


def plan_styles(
    bank: GlyphBank,
    corpus: Sequence[str],
    *,
    style_ids: Sequence[str] | None = None,
    images: _GlyphImages | None = None,
) -> tuple[list[StylePlan], list[dict[str, Any]], Counter, list[str]]:
    """Per-style corpus eligibility and weights.

    Returns ``(plans, excluded, global_skips, admissible_lines)``.
    """

    global_skips: Counter = Counter()
    admissible: list[str] = []
    for raw in corpus:
        line = " ".join(unicodedata.normalize("NFC", raw).split())
        if not line:
            continue
        reason = corpus_skip_reason(line)
        if reason is not None:
            global_skips[reason] += 1
            continue
        admissible.append(line)

    if style_ids:
        unknown = sorted(set(style_ids) - set(bank.styles))
        if unknown:
            raise GlyphCompositionError(f"Unknown --style-id: {', '.join(unknown)}")
        candidates = sorted(set(style_ids))
    else:
        candidates = sorted(bank.styles)

    plans: list[StylePlan] = []
    excluded: list[dict[str, Any]] = []
    for style_id in candidates:
        style = bank.styles[style_id]
        body = size_band(bank, style_id, style.metrics.x_height_px, images)
        chars = renderable_chars(body.chars)
        eligible: list[str] = []
        missing: Counter = Counter()
        skipped = 0
        for line in admissible:
            absent = {char for char in line if char != " " and char not in chars}
            if absent:
                skipped += 1
                missing.update(sorted(absent))
            else:
                eligible.append(line)
        if len(eligible) < MIN_ELIGIBLE_CORPUS_LINES:
            excluded.append(
                {
                    "style_id": style_id,
                    "reason": "too_few_renderable_corpus_lines",
                    "eligible_corpus_lines": len(eligible),
                    "top_missing_chars": [[char, count] for char, count in missing.most_common(8)],
                }
            )
            continue
        plans.append(
            StylePlan(
                style=style,
                body=body,
                heading=_heading_band(bank, style, images),
                eligible_lines=eligible,
                skipped_missing_glyph=skipped,
                missing_chars=missing,
            )
        )
    if plans:
        cap = STYLE_WEIGHT_CAP_MEDIANS * statistics.median(plan.body.glyph_count for plan in plans)
        for plan in plans:
            plan.weight = float(min(plan.body.glyph_count, cap))
    return plans, excluded, global_skips, admissible


def compose_page(
    plans: Sequence[StylePlan],
    images: _GlyphImages,
    *,
    seed: int,
    index: int,
    output_dir: Path,
) -> ComposedPage:
    rng = random.Random(f"hocrsyngen-glyph-page:{seed}:{index}")
    plan = rng.choices(list(plans), weights=[plan.weight for plan in plans])[0]
    composer = _PageComposer(plan, images, rng)
    metrics = plan.style.metrics
    composer.page_scale = rng.uniform(0.9, 1.15)
    composer.weight_target = rng.uniform(*PAGE_WEIGHT_RANGE)
    width = round(metrics.page_size_px[0] * composer.page_scale * rng.uniform(0.98, 1.02))
    height = round(metrics.page_size_px[1] * composer.page_scale * rng.uniform(0.98, 1.02))
    size = (width, height)
    line_plans = _layout_page(composer, width, height)
    paper = _paper(composer, size)
    ink, lines = _composite_lines(composer, line_plans, size)
    page, angle, params = _finish_page(composer, paper, ink, lines)

    sample_id = f"hocrsyngen-s{seed:08d}-{index:06d}"
    asset_path = f"assets/{sample_id}/page_0001.jpg"
    path = output_dir / asset_path
    path.parent.mkdir(parents=True, exist_ok=True)
    page.save(path, format="JPEG", quality=params["jpeg_quality"], optimize=True)

    recorder = _LineRecorder()
    for logical_index, line in enumerate(lines):
        recorder.lines.append(
            _RecordedLine(
                region=line.region,
                text=line.text,
                logical_line_index=logical_index,
                logical_join=None,
                box=line.ink_box(),
                baseline_y=line.baseline_y,
                region_key=line.region_key,
            )
        )
    recorder.rotation_degrees = angle
    logical_text = unicodedata.normalize("NFC", "\n".join(line.text for line in lines))
    entry = composed_template_entry(PRINTED_BOOK_GLYPH_TEMPLATE_ID)
    document = SyntheticDocument(
        sample_id=sample_id,
        sample_index=index,
        title="\n".join(line.text for line in lines if line.region == "title"),
        body="\n".join(line.text for line in lines if line.region == "body"),
        footer="\n".join(line.text for line in lines if line.region == "footer"),
        template_id=entry.template_id,
        recipe_id=entry.recipe_id,
        degradation_preset=entry.degradation_preset,
        font_id=entry.font_id,
        path=path,
        asset_path=asset_path,
        sha256=sha256_file(path),
        generator_version=GLYPH_COMPOSER_VERSION,
        logical_text=logical_text,
        lines=recorder.final_lines(size),
        regions=recorder.final_regions(size),
        truncated_segments=0,
    )
    params["page_scale"] = round(composer.page_scale, 4)
    return ComposedPage(
        sample_id=sample_id,
        sample_index=index,
        style_id=plan.style.style_id,
        size=size,
        lines=lines,
        rotation_degrees=angle,
        asset_path=asset_path,
        path=path,
        sha256=document.sha256,
        degradation=params,
        document=document,
        dropped_wide_words=composer.dropped_wide_words,
    )


# ----------------------------------------------------------- provenance ----


def _provenance_payload(
    bank: GlyphBank,
    pages: Sequence[ComposedPage],
    manifest_path: Path,
    *,
    min_glyph_score: float,
    include_glyph_ids: bool,
) -> dict[str, Any]:
    used_styles = sorted({page.style_id for page in pages})
    page_entries = []
    for page in pages:
        glyphs = [glyph for line in page.lines for glyph in line.glyphs]
        by_source = Counter(glyph.source_page_id for glyph in glyphs)
        entry: dict[str, Any] = {
            "sample_id": page.sample_id,
            "page_id": f"{page.sample_id}-page-0001",
            "page_sha256": page.sha256,
            "style_ids": [page.style_id],
            "glyph_count": len(glyphs),
            "unique_glyph_count": len({glyph.glyph_id for glyph in glyphs}),
            "synthesized_double_marks": sum(1 for glyph in glyphs if glyph.bank_char != glyph.gold_char) // 2,
            "source_pages": [
                {"page_id": source_page, "glyph_count": count} for source_page, count in sorted(by_source.items())
            ],
            "degradation": page.degradation,
        }
        if include_glyph_ids:
            entry["glyph_ids"] = sorted({glyph.glyph_id for glyph in glyphs})
        page_entries.append(entry)
    return {
        "schema": GLYPH_PROVENANCE_SCHEMA,
        "generation_manifest_sha256": sha256_file(manifest_path),
        "bank": {
            "schema": BANK_SCHEMA,
            "bank_id": bank.bank_id,
            "glyphs_sha256": bank.glyphs_sha256,
            "min_glyph_score": min_glyph_score,
        },
        "styles": [
            {
                "style_id": style_id,
                "source_id": bank.styles[style_id].source_id,
                "work_id": bank.styles[style_id].work_id,
                "licence": bank.styles[style_id].licence,
                "attribution": bank.styles[style_id].attribution,
                "born_digital": bank.styles[style_id].born_digital,
            }
            for style_id in used_styles
        ],
        "pages": page_entries,
    }


class GlyphProvenanceError(ValueError):
    pass


def _provenance_schema() -> dict[str, Any]:
    path = resources.files("hocrsyngen") / "schemas" / "glyph_provenance.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_glyph_provenance(batch_dir: Path, manifest_payload: dict[str, Any]) -> None:
    """Check ``glyph_provenance.json`` against the batch it sits in."""

    path = batch_dir / GLYPH_PROVENANCE_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, JSONDecodeError) as exc:
        raise GlyphProvenanceError(f"Glyph provenance is not readable JSON: {exc}") from exc
    try:
        jsonschema.validate(payload, _provenance_schema())
    except jsonschema.ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "<root>"
        raise GlyphProvenanceError(f"Glyph provenance schema violation at {location}: {exc.message}") from exc
    if payload["generation_manifest_sha256"] != sha256_file(batch_dir / "generation_manifest.json"):
        raise GlyphProvenanceError("Glyph provenance generation_manifest_sha256 does not match the manifest file.")
    styles = {style["style_id"]: style for style in payload["styles"]}
    if len(styles) != len(payload["styles"]):
        raise GlyphProvenanceError("Glyph provenance lists a style more than once.")
    for style in styles.values():
        if style["licence"] == "CC-BY-4.0" and not (style["attribution"] or "").strip():
            raise GlyphProvenanceError(f"Glyph provenance style {style['style_id']} is CC-BY-4.0 without attribution.")
    expected = [
        (sample, page)
        for sample in manifest_payload["samples"]
        if sample["provenance"]["template_id"] == PRINTED_BOOK_GLYPH_TEMPLATE_ID
        for page in sample["pages"]
    ]
    if len(expected) != len(payload["pages"]):
        raise GlyphProvenanceError(
            f"Glyph provenance covers {len(payload['pages'])} pages; the manifest has {len(expected)} composed pages."
        )
    used: set[str] = set()
    for position, (entry, (sample, page)) in enumerate(zip(payload["pages"], expected, strict=True)):
        where = f"glyph_provenance pages[{position}]"
        for key, value in (("sample_id", sample["sample_id"]), ("page_id", page["page_id"]), ("page_sha256", page["sha256"])):
            if entry[key] != value:
                raise GlyphProvenanceError(f"{where}.{key} does not match the manifest: {entry[key]!r}")
        unknown = set(entry["style_ids"]) - set(styles)
        if unknown:
            raise GlyphProvenanceError(f"{where} names unlisted styles: {sorted(unknown)}")
        used.update(entry["style_ids"])
        if sum(source["glyph_count"] for source in entry["source_pages"]) != entry["glyph_count"]:
            raise GlyphProvenanceError(f"{where}.source_pages counts do not sum to glyph_count.")
        if "glyph_ids" in entry and len(entry["glyph_ids"]) != entry["unique_glyph_count"]:
            raise GlyphProvenanceError(f"{where}.glyph_ids length does not match unique_glyph_count.")
    if used != set(styles):
        raise GlyphProvenanceError("Glyph provenance lists styles no page uses.")


# ---------------------------------------------------------------- batch ----


@dataclass(frozen=True)
class GlyphBatchResult:
    manifest: GenerationManifest
    pages: list[ComposedPage]
    report: dict[str, Any]


def compose_glyph_batch(
    bank_dir: Path,
    count: int,
    seed: int,
    output_dir: Path,
    *,
    text_corpus_path: Path | None = None,
    min_glyph_score: float = 0.0,
    style_ids: Sequence[str] | None = None,
    include_glyph_ids: bool = False,
) -> GlyphBatchResult:
    if seed < 0:
        raise GlyphCompositionError("Composition seed must be non-negative.")
    if count < 0:
        raise GlyphCompositionError("Composition count must be non-negative.")
    if not 0.0 <= min_glyph_score <= 1.0:
        raise GlyphCompositionError("--min-glyph-score must be within 0..1.")
    if output_dir.exists() and not output_dir.is_dir():
        raise GlyphCompositionError(f"Output path exists and is not a directory: {output_dir}")
    bank = load_glyph_bank(bank_dir)
    if min_glyph_score > 0:
        bank = bank.filtered(min_glyph_score)
    text_corpus_path = text_corpus_path or default_glyph_text_corpus_path()
    corpus = load_text_corpus(text_corpus_path)
    if not corpus:
        raise GlyphCompositionError(f"Text corpus is empty: {text_corpus_path}")
    images = _GlyphImages(bank.root)
    plans, excluded, global_skips, admissible = plan_styles(bank, corpus, style_ids=style_ids, images=images)
    if not plans:
        raise GlyphCompositionError(
            "No style can render enough corpus lines: "
            + json.dumps(excluded, ensure_ascii=False)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = [compose_page(plans, images, seed=seed, index=index, output_dir=output_dir) for index in range(count)]

    source_corpus = source_corpus_id(text_corpus_path)
    entry = composed_template_entry(PRINTED_BOOK_GLYPH_TEMPLATE_ID)
    manifest = GenerationManifest(
        samples=[
            GeneratedSample(
                sample_id=page.sample_id,
                pages=[
                    PageAsset(
                        page_id=f"{page.sample_id}-page-0001",
                        asset_path=page.asset_path,
                        media_type="image/jpeg",
                        sha256=page.sha256,
                        width=page.size[0],
                        height=page.size[1],
                    )
                ],
                text=TextMetadata(logical_order=page.document.logical_text),
                generator_version=GLYPH_COMPOSER_VERSION,
                recipe_id=entry.recipe_id,
                provenance=SampleProvenance(
                    seed=seed,
                    sample_index=page.sample_index,
                    template_id=entry.template_id,
                    recipe_id=entry.recipe_id,
                    degradation_preset=entry.degradation_preset,
                    font_id=entry.font_id,
                    source_corpus=source_corpus,
                ),
                controls=SampleControls(),
            )
            for page in pages
        ]
    )
    manifest_path = write_manifest(manifest, output_dir)
    # Imported lazily: line_annotations imports the generator module.
    from hocrsyngen.line_annotations import write_line_annotations

    line_annotations_path = write_line_annotations(manifest, [page.document for page in pages], manifest_path)
    provenance = _provenance_payload(
        bank, pages, manifest_path, min_glyph_score=min_glyph_score, include_glyph_ids=include_glyph_ids
    )
    provenance_path = output_dir / GLYPH_PROVENANCE_FILENAME
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    style_pages = Counter(page.style_id for page in pages)
    style_lines: Counter = Counter()
    style_chars: Counter = Counter()
    for page in pages:
        for line in page.lines:
            style_lines[page.style_id] += 1
            style_chars[page.style_id] += len(line.text.replace(" ", ""))
    report = {
        "schema_version": COMPOSITION_REPORT_SCHEMA,
        "output_path": str(output_dir),
        "manifest_path": str(manifest_path),
        "line_annotations_path": str(line_annotations_path),
        "glyph_provenance_path": str(provenance_path),
        "bank_id": bank.bank_id,
        "min_glyph_score": min_glyph_score,
        "pages": len(pages),
        "lines": sum(style_lines.values()),
        "chars": sum(style_chars.values()),
        "glyphs": sum(len(line.glyphs) for page in pages for line in page.lines),
        "dropped_wide_words": sum(page.dropped_wide_words for page in pages),
        "glyphs_rejected_mask_coverage": len(images.rejected),
        "text_corpus": {
            "source_corpus": source_corpus,
            "sha256": sha256_file(text_corpus_path),
            "lines": len(corpus),
            "admissible_lines": len(admissible),
            "skipped_lines": dict(sorted(global_skips.items())),
        },
        "styles": [
            {
                "style_id": plan.style.style_id,
                "licence": plan.style.licence,
                "weight": plan.weight,
                "body_x_height_px": plan.body.target_x_height,
                "body_band_glyphs": plan.body.glyph_count,
                "body_band_outliers_dropped": plan.body.outliers_dropped,
                "body_band_mask_rejected": plan.body.mask_rejected,
                "body_band_weight_dropped": plan.body.weight_dropped,
                "heading_band_weight_dropped": plan.heading.weight_dropped if plan.heading else None,
                "heading_x_height_px": plan.heading.target_x_height if plan.heading else None,
                "eligible_corpus_lines": len(plan.eligible_lines),
                "skipped_missing_glyph": plan.skipped_missing_glyph,
                "top_missing_chars": [[char, count] for char, count in plan.missing_chars.most_common(8)],
                "pages": style_pages.get(plan.style.style_id, 0),
                "lines": style_lines.get(plan.style.style_id, 0),
                "chars": style_chars.get(plan.style.style_id, 0),
            }
            for plan in plans
        ],
        "styles_excluded": excluded,
    }
    return GlyphBatchResult(manifest=manifest, pages=pages, report=report)
