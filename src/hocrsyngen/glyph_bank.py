"""S16b: load and validate a ``printed_glyph_bank.v1`` directory.

The bank is produced outside this repository (``docs/printed_glyph_bank_v1.md``)
and read here through files only. Loading checks the JSON schema, the
``glyphs.jsonl`` hash, the relative-path rules, that every referenced file
exists under the bank root, single-code-point NFC characters, and the licence
rules (PD, CC0-1.0, or CC-BY-4.0 with attribution). Glyph and paper images are
opened lazily by the composer, which checks each image against its record.
"""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from importlib import resources
from json import JSONDecodeError
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

from hocrsyngen.io import sha256_file


BANK_SCHEMA = "printed_glyph_bank.v1"
INDEX_FILENAME = "printed_glyph_bank.json"
GLYPHS_FILENAME = "glyphs.jsonl"
ALLOWED_LICENCES = ("PD", "CC0-1.0", "CC-BY-4.0")
ATTRIBUTION_LICENCES = frozenset({"CC-BY-4.0"})


class GlyphBankError(ValueError):
    pass


@dataclass(frozen=True)
class StyleMetrics:
    x_height_px: float
    line_pitch_px: float
    letter_gap_px: tuple[float, float, float]
    word_gap_px: tuple[float, float, float]
    text_block_width_px: float
    page_size_px: tuple[int, int]
    ink_gray: float
    paper_gray: float


@dataclass(frozen=True)
class GlyphRecord:
    glyph_id: str
    style_id: str
    char: str
    asset_path: str
    mask_path: str
    size: tuple[int, int]
    ink_box: tuple[int, int, int, int]
    baseline_y: int
    source_page_id: str
    score: float
    # x-height of the source word; the style's median when the record has none.
    x_height_px: float

    @property
    def ink_width(self) -> int:
        return self.ink_box[2] - self.ink_box[0]


@dataclass(frozen=True)
class GlyphStyle:
    style_id: str
    source_id: str
    work_id: str
    licence: str
    attribution: str | None
    born_digital: bool
    metrics: StyleMetrics
    paper_patches: tuple[str, ...]
    glyph_count: int


@dataclass
class GlyphBank:
    root: Path
    bank_id: str
    glyphs_sha256: str
    styles: dict[str, GlyphStyle]
    glyphs: list[GlyphRecord]
    # style_id -> char -> glyph records (in glyphs.jsonl order).
    by_style_char: dict[str, dict[str, list[GlyphRecord]]] = field(default_factory=dict)

    def filtered(self, min_score: float) -> GlyphBank:
        """A view keeping glyphs with ``quality.score >= min_score``."""

        kept = [glyph for glyph in self.glyphs if glyph.score >= min_score]
        return GlyphBank(
            root=self.root,
            bank_id=self.bank_id,
            glyphs_sha256=self.glyphs_sha256,
            styles=self.styles,
            glyphs=kept,
            by_style_char=_index_glyphs(kept),
        )

    def chars(self, style_id: str) -> frozenset[str]:
        return frozenset(self.by_style_char.get(style_id, {}))

    def style_glyph_count(self, style_id: str) -> int:
        return sum(len(records) for records in self.by_style_char.get(style_id, {}).values())


def _index_glyphs(glyphs: list[GlyphRecord]) -> dict[str, dict[str, list[GlyphRecord]]]:
    index: dict[str, dict[str, list[GlyphRecord]]] = defaultdict(lambda: defaultdict(list))
    for glyph in glyphs:
        index[glyph.style_id][glyph.char].append(glyph)
    return {style_id: dict(chars) for style_id, chars in index.items()}


def _schema() -> dict[str, Any]:
    path = resources.files("hocrsyngen") / "schemas" / "printed_glyph_bank.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _check_relative_path(root: Path, value: str, where: str, *, check_files: bool) -> None:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or (len(value) > 1 and value[1] == ":")
    ):
        raise GlyphBankError(f"{where} must be a relative POSIX path under the bank root: {value!r}")
    if check_files:
        resolved = (root / Path(*path.parts)).resolve()
        if not resolved.is_relative_to(root):
            raise GlyphBankError(f"{where} resolves outside the bank root: {value!r}")
        if not resolved.is_file():
            raise GlyphBankError(f"{where} names a missing file: {value!r}")


def _first_schema_error(validator: jsonschema.Draft202012Validator, payload: Any, where: str) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise GlyphBankError(f"{where} schema violation at {location}: {error.message}")


def validate_char(char: str) -> str | None:
    """Return why ``char`` is not a valid bank character, or ``None``."""

    if len(char) != 1:
        return "must be exactly one code point"
    if unicodedata.normalize("NFC", char) != char:
        return "must be NFC"
    category = unicodedata.category(char)
    if category.startswith("M"):
        return "must not be a combining mark (niqqud and cantillation are not glyphs in v1)"
    if category.startswith("Z") or category.startswith("C"):
        return "must not be whitespace or a control character"
    return None


def load_glyph_bank(path: Path, *, check_files: bool = True) -> GlyphBank:
    """Load and validate a bank directory; raise :class:`GlyphBankError` on any violation."""

    if not path.is_dir():
        raise GlyphBankError(f"Glyph bank is not a directory: {path}")
    root = path.resolve()
    index_path = root / INDEX_FILENAME
    glyphs_path = root / GLYPHS_FILENAME
    for required in (index_path, glyphs_path):
        if not required.is_file():
            raise GlyphBankError(f"Glyph bank is missing {required.name}: {path}")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise GlyphBankError(f"{INDEX_FILENAME} is not valid UTF-8 JSON: {exc}") from exc
    schema = _schema()
    _first_schema_error(jsonschema.Draft202012Validator(schema), index, INDEX_FILENAME)

    actual_sha = sha256_file(glyphs_path)
    if actual_sha != index["glyphs_sha256"]:
        raise GlyphBankError(
            f"{INDEX_FILENAME} glyphs_sha256 {index['glyphs_sha256']} does not match {GLYPHS_FILENAME} ({actual_sha})."
        )

    source_licences: dict[str, str] = {}
    for position, source in enumerate(index["sources"]):
        if source["source_id"] in source_licences:
            raise GlyphBankError(f"sources[{position}].source_id is duplicated: {source['source_id']}")
        source_licences[source["source_id"]] = source["licence"]
    declared_char_counts: dict[str, dict[str, int]] = {}

    styles: dict[str, GlyphStyle] = {}
    for position, style in enumerate(index["styles"]):
        where = f"styles[{position}]"
        style_id = style["style_id"]
        if style_id in styles:
            raise GlyphBankError(f"{where}.style_id is duplicated: {style_id}")
        if style["source_id"] not in source_licences:
            raise GlyphBankError(f"{where}.source_id is not a listed source: {style['source_id']}")
        licence = style["licence"]
        attribution = style["attribution"]
        if licence in ATTRIBUTION_LICENCES and not (isinstance(attribution, str) and attribution.strip()):
            raise GlyphBankError(f"{where} has licence {licence} and needs a non-empty attribution.")
        metrics = style["metrics"]
        for key in ("letter_gap_px", "word_gap_px"):
            low, median, high = metrics[key]
            if not low <= median <= high:
                raise GlyphBankError(f"{where}.metrics.{key} must be ordered p10 <= median <= p90.")
        if metrics["word_gap_px"][0] < 0:
            raise GlyphBankError(f"{where}.metrics.word_gap_px must be non-negative.")
        if "char_counts" in style:
            declared_char_counts[style_id] = dict(style["char_counts"])
        for patch_index, patch in enumerate(style["paper_patches"]):
            _check_relative_path(root, patch, f"{where}.paper_patches[{patch_index}]", check_files=check_files)
        styles[style_id] = GlyphStyle(
            style_id=style_id,
            source_id=style["source_id"],
            work_id=str(style["work_id"]),
            licence=licence,
            attribution=attribution,
            born_digital=bool(style["born_digital"]),
            metrics=StyleMetrics(
                x_height_px=float(metrics["x_height_px"]),
                line_pitch_px=float(metrics["line_pitch_px"]),
                letter_gap_px=tuple(float(value) for value in metrics["letter_gap_px"]),
                word_gap_px=tuple(float(value) for value in metrics["word_gap_px"]),
                text_block_width_px=float(metrics["text_block_width_px"]),
                page_size_px=(int(metrics["page_size_px"][0]), int(metrics["page_size_px"][1])),
                ink_gray=float(metrics["ink_gray"]),
                paper_gray=float(metrics["paper_gray"]),
            ),
            paper_patches=tuple(style["paper_patches"]),
            glyph_count=int(style["glyph_count"]),
        )

    glyph_validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/glyph", "$defs": schema["$defs"]})
    glyphs: list[GlyphRecord] = []
    seen_ids: set[str] = set()
    per_style: dict[str, int] = defaultdict(int)
    per_style_char: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with glyphs_path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            where = f"{GLYPHS_FILENAME}:{line_number}"
            try:
                record = json.loads(raw)
            except JSONDecodeError as exc:
                raise GlyphBankError(f"{where} is not valid JSON: {exc.msg}") from exc
            _first_schema_error(glyph_validator, record, where)
            glyph_id = record["glyph_id"]
            if glyph_id in seen_ids:
                raise GlyphBankError(f"{where} glyph_id is duplicated: {glyph_id}")
            seen_ids.add(glyph_id)
            if record["style_id"] not in styles:
                raise GlyphBankError(f"{where} style_id is not a listed style: {record['style_id']}")
            problem = validate_char(record["char"])
            if problem is not None:
                raise GlyphBankError(f"{where} char {record['char']!r} {problem}.")
            width, height = record["size"]
            x0, y0, x1, y1 = record["ink_box"]
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                raise GlyphBankError(f"{where} ink_box {record['ink_box']} must lie inside size {record['size']}.")
            for key in ("asset_path", "mask_path"):
                _check_relative_path(root, record[key], f"{where}.{key}", check_files=check_files)
            per_style[record["style_id"]] += 1
            per_style_char[record["style_id"]][record["char"]] += 1
            glyphs.append(
                GlyphRecord(
                    glyph_id=glyph_id,
                    style_id=record["style_id"],
                    char=record["char"],
                    asset_path=record["asset_path"],
                    mask_path=record["mask_path"],
                    size=(width, height),
                    ink_box=(x0, y0, x1, y1),
                    baseline_y=int(record["baseline_y"]),
                    source_page_id=str(record["source"]["page_id"]),
                    score=float(record["quality"]["score"]),
                    x_height_px=float(record.get("x_height_px", styles[record["style_id"]].metrics.x_height_px)),
                )
            )
    if len(glyphs) != index["glyph_count"]:
        raise GlyphBankError(f"{INDEX_FILENAME} glyph_count {index['glyph_count']} != {len(glyphs)} glyph records.")
    for style_id, style in styles.items():
        if per_style.get(style_id, 0) != style.glyph_count:
            raise GlyphBankError(
                f"Style {style_id} glyph_count {style.glyph_count} != {per_style.get(style_id, 0)} glyph records."
            )
    for style_id, declared in declared_char_counts.items():
        if declared != dict(per_style_char.get(style_id, {})):
            raise GlyphBankError(f"Style {style_id} char_counts do not match its glyph records.")
    return GlyphBank(
        root=root,
        bank_id=index["bank_id"],
        glyphs_sha256=actual_sha,
        styles=styles,
        glyphs=glyphs,
        by_style_char=_index_glyphs(glyphs),
    )
