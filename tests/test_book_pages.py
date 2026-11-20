from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageStat

from hocrsyngen.assets import synthetic_data_path
from hocrsyngen.cli import main
from hocrsyngen.generator import (
    BOOK_TEMPLATE_IDS,
    CANVAS_SIZE,
    DEGRADATION_PRESETS,
    GOVERNED_TEMPLATE_IDS,
    _condition_bundle,
    _degrade,
    _hebrew_numeral,
    template_catalog,
)
from hocrsyngen.line_annotations import LINE_ANNOTATIONS_FILENAME
from hocrsyngen.validation import validate_batch


TRAIN_CORPUS = synthetic_data_path("texts/hebrew_lines_train_v1.txt")


def _batch(tmp_path: Path, templates: list[str], count: int, seed: int = 17) -> tuple[Path, list[dict]]:
    output = tmp_path / "batch"
    args = ["generate", "--count", str(count), "--seed", str(seed), "--output", str(output),
            "--text-corpus", str(TRAIN_CORPUS), "--emit-line-annotations", "--format", "json"]
    for template in templates:
        args += ["--template-id", template]
    assert main(args) == 0
    pages = json.loads((output / LINE_ANNOTATIONS_FILENAME).read_text(encoding="utf-8"))["pages"]
    return output, pages


def _region_lines(page: dict, region_index: int) -> list[dict]:
    return [page["lines"][index] for index in page["regions"][region_index]["line_indices"]]


def _xs(lines: list[dict]) -> tuple[int, int]:
    xs = [x for line in lines for x, _y in line["polygon"]]
    return min(xs), max(xs)


def test_book_templates_are_supported_but_not_governed() -> None:
    assert not set(BOOK_TEMPLATE_IDS) & set(GOVERNED_TEMPLATE_IDS)
    catalog = {entry.template_id: entry for entry in template_catalog(BOOK_TEMPLATE_IDS)}
    assert catalog["book_page"].font_id == "frank-ruhl-libre"
    assert catalog["book_page_thumbnail_scan"].font_id == "david-libre-regular"
    assert catalog["commentary_page"].degradation_preset == "book_scan_soft"
    assert catalog["commentary_page_thumbnail_scan"].degradation_preset == "book_scan_thumbnail"


def test_every_book_template_generates_a_valid_annotated_batch(tmp_path: Path) -> None:
    output, pages = _batch(tmp_path, BOOK_TEMPLATE_IDS, count=len(BOOK_TEMPLATE_IDS))
    assert validate_batch(output).sample_count == len(BOOK_TEMPLATE_IDS)
    manifest = json.loads((output / "generation_manifest.json").read_text(encoding="utf-8"))
    by_template = {sample["provenance"]["template_id"]: page for sample, page in zip(manifest["samples"], pages)}
    for template in BOOK_TEMPLATE_IDS:
        page = by_template[template]
        assert Image.open(output / "assets" / page["sample_id"] / "page_0001.jpg").size == CANVAS_SIZE
        minimum = 4 if template.startswith("book_title_page") else 20
        assert len(page["lines"]) >= minimum, template


def test_prose_lines_are_long_like_book_lines(tmp_path: Path) -> None:
    _output, pages = _batch(tmp_path, ["book_page"], count=4, seed=23)
    widths = sorted(
        (max(x for x, _ in line["polygon"]) - min(x for x, _ in line["polygon"])) / page["width"]
        for page in pages for line in page["lines"] if line["region"] == "body"
    )
    # Book prose lines span most of the text block, unlike form fields (R4d's data: median 0.07 of the page width).
    assert widths[len(widths) // 2] > 0.5


def test_two_columns_are_separate_body_regions_read_right_to_left(tmp_path: Path) -> None:
    _output, pages = _batch(tmp_path, ["book_page_two_column"], count=3, seed=29)
    for page in pages:
        bodies = [region["region_index"] for region in page["regions"] if region["type"] == "body"]
        assert len(bodies) == 2
        first, second = (_region_lines(page, index) for index in bodies)
        assert page["regions"][bodies[0]]["reading_order_index"] < page["regions"][bodies[1]]["reading_order_index"]
        # The first column read is the right one, and the columns do not overlap.
        assert _xs(first)[0] > _xs(second)[1]


def test_commentary_pages_surround_the_main_text_with_margin_blocks(tmp_path: Path) -> None:
    _output, pages = _batch(tmp_path, ["commentary_page"], count=2, seed=31)
    for page in pages:
        types = [region["type"] for region in page["regions"]]
        assert types.count("body") == 1
        assert types.count("margin") >= 2
        body = page["lines"][page["regions"][types.index("body")]["line_indices"][0]]
        margin = [line for line in page["lines"] if line["region"] == "margin"]
        height = lambda line: max(y for _, y in line["polygon"]) - min(y for _, y in line["polygon"])  # noqa: E731
        # Commentary is set smaller than the main text.
        assert max(height(line) for line in margin) < height(body)
        assert all(line["logical_line_index"] is not None for line in page["lines"])


def test_thumbnail_preset_keeps_the_canvas_and_loses_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    def edges(image: Image.Image) -> float:
        return float(ImageStat.Stat(image.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0])

    page = Image.new("RGB", CANVAS_SIZE, (244, 238, 224))
    draw = ImageDraw.Draw(page)
    for row in range(40):
        draw.line((100, 100 + row * 35, 1100, 100 + row * 35), fill=(20, 20, 20), width=2)
    condition = _condition_bundle(None)
    thumbnail = _degrade(page, random.Random(5), (244, 238, 224), "book_scan_thumbnail", condition)
    preset = DEGRADATION_PRESETS["book_scan_thumbnail"]
    monkeypatch.setitem(DEGRADATION_PRESETS, "book_scan_thumbnail", replace(preset, resample_width=None))
    full = _degrade(page, random.Random(5), (244, 238, 224), "book_scan_thumbnail", condition)
    assert thumbnail.size == full.size == CANVAS_SIZE
    # The same degradation without the 960 px round trip keeps more detail.
    assert edges(thumbnail) < edges(full)


@pytest.mark.parametrize(("value", "numeral"), [(1, "א'"), (15, "ט\"ו"), (16, "ט\"ז"), (115, "קט\"ו"), (480, "ת\"פ")])
def test_hebrew_page_numerals(value: int, numeral: str) -> None:
    assert _hebrew_numeral(value) == numeral
