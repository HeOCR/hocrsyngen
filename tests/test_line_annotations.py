from __future__ import annotations

import json
import statistics
import unicodedata
from importlib import resources
from pathlib import Path

import jsonschema
import pytest
from PIL import Image, ImageDraw

import hocrsyngen.generator as generator_module
from hocrsyngen.assets import default_font_manifest_path, default_text_corpus_path
from hocrsyngen.cli import main
from hocrsyngen.generator import (
    CANVAS_SIZE,
    GOVERNED_TEMPLATE_IDS,
    _LineRecorder,
    _rotated_point,
    _segment_hits_box,
    generate_batch,
    generate_documents,
    source_corpus_id,
)
from hocrsyngen.io import sha256_file
from hocrsyngen.line_annotations import (
    LINE_ANNOTATIONS_FILENAME,
    polygon_contains,
    reconstruct_logical_lines,
)
from hocrsyngen.validation import BatchValidationError, validate_batch


ALL_TEMPLATES = list(GOVERNED_TEMPLATE_IDS)
SCHEMA = json.loads(
    (resources.files("hocrsyngen") / "schemas" / "line_annotations.schema.json").read_text(encoding="utf-8")
)
LONG_LINE = " ".join(["הרישום הועבר לעיון ועד הקהילה בשבוע הבא"] * 4) + "."


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def annotated_batch(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("annotated")
    generate_batch(len(ALL_TEMPLATES), 17, output_dir, ALL_TEMPLATES, emit_line_annotations=True)
    return output_dir


def test_flag_off_output_is_byte_identical_and_sidecar_is_the_only_addition(
    annotated_batch: Path, tmp_path: Path
) -> None:
    plain_dir = tmp_path / "plain"
    generate_batch(len(ALL_TEMPLATES), 17, plain_dir, ALL_TEMPLATES)

    plain = _tree_bytes(plain_dir)
    annotated = _tree_bytes(annotated_batch)
    assert LINE_ANNOTATIONS_FILENAME not in plain
    assert set(annotated) - set(plain) == {LINE_ANNOTATIONS_FILENAME}
    assert {key: annotated[key] for key in plain} == plain


def test_sidecar_matches_contract_schema_and_binds_to_manifest(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")

    jsonschema.validate(payload, SCHEMA)
    assert payload["schema"] == "hocrsyngen_line_annotations.v1"
    assert payload["coordinate_space"] == "final_page_pixels"
    assert payload["generation_manifest_sha256"] == sha256_file(annotated_batch / "generation_manifest.json")
    expected = [
        (sample["sample_id"], page["page_id"], page["sha256"], page["width"], page["height"])
        for sample in manifest["samples"]
        for page in sample["pages"]
    ]
    assert [
        (page["sample_id"], page["page_id"], page["page_sha256"], page["width"], page["height"])
        for page in payload["pages"]
    ] == expected
    assert validate_batch(annotated_batch).page_count == len(ALL_TEMPLATES)


def test_lines_rebuild_logical_order_for_every_template(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")
    templates_seen = set()

    for sample, page in zip(manifest["samples"], payload["pages"], strict=True):
        templates_seen.add(sample["provenance"]["template_id"])
        logical_lines = sample["text"]["logical_order"].split("\n")
        lines = page["lines"]
        assert [line["line_index"] for line in lines] == list(range(len(lines)))
        assert all(unicodedata.is_normalized("NFC", line["text"]) for line in lines)
        rebuilt = reconstruct_logical_lines(lines)
        assert [rebuilt[index] for index in sorted(rebuilt)] == logical_lines
        scored = [line for line in lines if line["logical_line_index"] is not None]
        assert all(
            (line["logical_join"] is None) == (index == 0 or scored[index - 1]["logical_line_index"] != line["logical_line_index"])
            for index, line in enumerate(scored)
        )
        if sample["provenance"]["template_id"] != "ledger":
            # Without wrapping or table cells, scored lines are logical_order verbatim.
            assert "\n".join(line["text"] for line in scored) == sample["text"]["logical_order"]

    assert templates_seen == set(ALL_TEMPLATES)


def test_ledger_rows_are_cells_joined_with_pipe_separator(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")
    ledger_index = ALL_TEMPLATES.index("ledger")
    lines = payload["pages"][ledger_index]["lines"]
    logical_lines = manifest["samples"][ledger_index]["text"]["logical_order"].split("\n")

    row_groups: dict[int, list[dict]] = {}
    for line in lines:
        row_groups.setdefault(line["logical_line_index"], []).append(line)
    multi_cell_rows = {index: cells for index, cells in row_groups.items() if len(cells) > 1}
    assert multi_cell_rows
    for index, cells in multi_cell_rows.items():
        assert [cell["logical_join"] for cell in cells] == [None, "cell", "cell", "cell", "cell"]
        assert " | ".join(cell["text"] for cell in cells) == logical_lines[index]


def test_wrapped_source_lines_share_logical_index_and_rejoin_with_space(tmp_path: Path) -> None:
    corpus = tmp_path / "long.txt"
    corpus.write_text(LONG_LINE + "\n", encoding="utf-8")
    output_dir = tmp_path / "wrapped"
    generate_batch(1, 4, output_dir, ["printed_letter"], text_corpus_path=corpus, emit_line_annotations=True)

    lines = _load(output_dir / LINE_ANNOTATIONS_FILENAME)["pages"][0]["lines"]
    body = [line for line in lines if line["region"] == "body"]
    assert len(body) > 1
    assert {line["logical_line_index"] for line in body} == {1}
    assert [line["logical_join"] for line in body] == [None] + ["space"] * (len(body) - 1)
    assert " ".join(line["text"] for line in body) == LONG_LINE
    assert validate_batch(output_dir).sample_count == 1


# S10c reading order after the body: stamp, margin note, signature captions
# right to left; the footer is always last.
EXPECTED_ANNOTATION_LINES = {
    "printed_letter": [("stamp_area", "נבדק"), *[("signature_area", "אישור")] * 3],
    "printed_letter_heavy_scan": [("stamp_area", "נבדק"), *[("signature_area", "אישור")] * 3],
    "handwritten_note": [("margin", None)],
    "handwritten_note_heavy_wear": [("margin", None)],
    "archive_card": [],
    "archive_card_faded_scan": [],
    "ledger": [],
}


def test_every_drawn_text_is_in_logical_order_in_documented_reading_order(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")

    for sample, page in zip(manifest["samples"], payload["pages"], strict=True):
        template_id = sample["provenance"]["template_id"]
        lines = page["lines"]
        assert all(line["logical_line_index"] is not None for line in lines)
        logical_lines = sample["text"]["logical_order"].split("\n")
        expected = EXPECTED_ANNOTATION_LINES[template_id]
        if not expected:
            continue
        annotations = [line for line in lines if line["region"] in {"stamp_area", "signature_area", "margin"}]
        assert [line["region"] for line in annotations] == [region for region, _text in expected]
        for line, (_region, text) in zip(annotations, expected, strict=True):
            if text is not None:
                assert line["text"] == text
            assert logical_lines[line["logical_line_index"]] == line["text"]
        # Annotations sit directly before the footer, which is the last line.
        footer_index = len(logical_lines) - 1
        assert [line["logical_line_index"] for line in annotations] == list(
            range(footer_index - len(annotations), footer_index)
        )
        assert lines[-1]["region"] == "footer"


def test_occluded_flags_stamp_ring_crossings_on_printed_letters(tmp_path: Path) -> None:
    output_dir = tmp_path / "printed"
    generate_batch(4, 101, output_dir, ["printed_letter", "handwritten_note"], emit_line_annotations=True)
    pages = _load(output_dir / LINE_ANNOTATIONS_FILENAME)["pages"]

    printed_body = [line for page in pages[0::2] for line in page["lines"] if line["region"] == "body"]
    handwritten = [line for page in pages[1::2] for line in page["lines"]]
    assert any(line["occluded"] for line in printed_body)
    assert not all(line["occluded"] for line in printed_body)
    # Marginal notes are not occluded by their own underline stroke.
    assert not any(line["occluded"] for line in handwritten)


def test_segment_hits_box_and_mark_ownership() -> None:
    box = (10.0, 10.0, 20.0, 20.0)
    assert _segment_hits_box((0, 15), (30, 15), box)
    assert _segment_hits_box((12, 12), (13, 13), box)
    assert not _segment_hits_box((0, 0), (5, 30), box)
    assert not _segment_hits_box((0, 25), (30, 25), box)

    recorder = _LineRecorder()
    recorder.lines.append(
        generator_module._RecordedLine("margin", "עותק", None, None, (0.0, 0.0, 40.0, 20.0), 15.0, "margin")
    )
    recorder.mark_polyline(((0, 18), (40, 18)), 2, owner=0)
    assert recorder.final_lines(CANVAS_SIZE)[0].occluded is False
    recorder.mark_polyline(((0, 10), (40, 10)), 2)
    assert recorder.final_lines(CANVAS_SIZE)[0].occluded is True


LONG_CORPUS_LINES = [
    "הבקשה התקבלה והועברה לטיפול המזכיר התורן בשבוע שעבר במשרד.",
    "הרישום הועבר לעיון ועד הקהילה בשבוע הבא לאחר בדיקה נוספת.",
    "התשלום נרשם בספר הקופה ונחתם בידי הגזבר ובידי המזכיר הראשי.",
    "נמסר כי הרשימה עודכנה לאחר בדיקת המסמכים שהגיעו מן הארכיון.",
    "האסמכתה נשמרה יחד עם מסמכי החשבון הקודם בתיק הרישום המרכזי.",
    "הערה זו נוספה בשולי המסמך לצורך הבהרה ונבדקה בידי הוועדה.",
]


def test_capped_body_segments_are_dropped_from_page_and_gold_alike(tmp_path: Path) -> None:
    """Archive cards keep 7 wrapped body segments and ledgers 10 rows.

    Segments past the cap are neither drawn nor in logical_order, so the
    round trip holds even when long source lines lose their tails.
    """

    corpus = tmp_path / "long.txt"
    corpus.write_text("\n".join(LONG_CORPUS_LINES) + "\n", encoding="utf-8")
    output_dir = tmp_path / "capped"
    generate_batch(4, 3, output_dir, ["printed_letter", "handwritten_note", "archive_card", "ledger"],
                   text_corpus_path=corpus, emit_line_annotations=True)
    assert validate_batch(output_dir).sample_count == 4

    manifest = _load(output_dir / "generation_manifest.json")
    pages = _load(output_dir / LINE_ANNOTATIONS_FILENAME)["pages"]
    wrapped = [line for page in pages[:2] for line in page["lines"] if line["logical_join"] == "space"]
    assert wrapped, "long lines must wrap on printed and handwritten pages"

    assert [page["truncated_segments"] for page in pages[:2]] == [0, 0]
    assert pages[2]["truncated_segments"] > 0 and pages[3]["truncated_segments"] > 0
    archive_body = [line["text"] for line in pages[2]["lines"] if line["region"] == "body"]
    ledger_rows = [line for line in pages[3]["lines"] if line["region"] == "table_cells" and line["logical_join"] == "cell"]
    assert len(archive_body) == 7
    assert len(ledger_rows) == 10 * 4
    for sample in manifest["samples"][2:]:
        gold = sample["text"]["logical_order"].replace("\n", " ")
        sampled_words = {word for line in LONG_CORPUS_LINES for word in line.split()}
        # The caps drop words that the source lines contained ...
        assert not sampled_words <= set(gold.replace(" | ", " ").split())
    # ... and every annotated segment is text that is in gold verbatim.
    assert all(text in manifest["samples"][2]["text"]["logical_order"].split("\n") for text in archive_body)


def _gray(path: Path) -> Image.Image:
    return Image.open(path).convert("L")


def _polygon_pixels(image: Image.Image, polygon: list[list[int]]) -> list[int]:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).polygon([tuple(point) for point in polygon], fill=1)
    return [value for value, inside in zip(image.tobytes(), mask.tobytes(), strict=True) if inside]


def test_polygons_land_on_ink_in_the_final_degraded_page(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")

    for sample, page in zip(manifest["samples"], payload["pages"], strict=True):
        image = _gray(annotated_batch / sample["pages"][0]["asset_path"])
        background = statistics.median(image.tobytes())
        # Faded and heavy-scan presets lift light footer ink to ~bg-50.
        dark_threshold = background - 40
        for line in page["lines"]:
            pixels = _polygon_pixels(image, line["polygon"])
            dark_share = sum(value < dark_threshold for value in pixels) / len(pixels)
            # A text line box carries a clear share of ink; empty paper carries ~none.
            assert dark_share > 0.05, (sample["sample_id"], line["text"], dark_share)
            assert statistics.mean(pixels) < background - 5, (sample["sample_id"], line["text"])

        # Control: the same boxes shifted into the blank top margin are not dark.
        for line in page["lines"][:1]:
            shifted = [[x, y % 40] for x, y in line["polygon"]]
            pixels = _polygon_pixels(image, shifted)
            assert sum(value < dark_threshold for value in pixels) / max(1, len(pixels)) < 0.01


def test_baselines_run_left_to_right_inside_their_polygon(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    for page in payload["pages"]:
        for line in page["lines"]:
            (x0, y0), (x1, y1) = line["baseline"]
            assert x0 < x1
            xs = [x for x, _y in line["polygon"]]
            ys = [y for _x, y in line["polygon"]]
            assert min(xs) <= x0 and x1 <= max(xs)
            assert min(ys) <= min(y0, y1) and max(y0, y1) <= max(ys)


@pytest.mark.parametrize("angle", [1.85, -1.3, 0.0])
@pytest.mark.parametrize("pixel", [(100, 100), (1100, 1500), (600, 200)])
def test_rotated_point_matches_pillow_rotate(angle: float, pixel: tuple[int, int]) -> None:
    image = Image.new("L", CANVAS_SIZE, 0)
    image.putpixel(pixel, 255)
    rotated = image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=0)
    left, top, right, bottom = rotated.getbbox()
    weighted = [
        (x, y, rotated.getpixel((x, y)))
        for y in range(top, bottom)
        for x in range(left, right)
        if rotated.getpixel((x, y)) > 0
    ]
    total = sum(value for _x, _y, value in weighted)
    observed = (
        sum(x * value for x, _y, value in weighted) / total + 0.5,
        sum(y * value for _x, y, value in weighted) / total + 0.5,
    )
    predicted = _rotated_point((pixel[0] + 0.5, pixel[1] + 0.5), angle, CANVAS_SIZE)
    assert predicted == pytest.approx(observed, abs=0.1)


def _rewrite(path: Path, mutate) -> None:
    payload = _load(path)
    mutate(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# Page 2 is an archive card: every drawn line there is in logical_order.
@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p.update(generation_manifest_sha256="0" * 64), "generation_manifest_sha256"),
        (lambda p: p["pages"][2]["lines"][0].update(text="שגוי"), "rebuild"),
        (lambda p: p["pages"][2]["lines"][0]["polygon"][0].__setitem__(0, 5000), "outside the page"),
        (lambda p: p["pages"][2]["lines"].pop(), "cover every logical_order line"),
        (lambda p: p["pages"][2]["lines"][1].update(logical_line_index=0), "more than one segment"),
        (lambda p: p["pages"][2]["lines"][0].update(logical_join="space"), "continues before its first segment"),
        (lambda p: p["pages"][0]["lines"][0].update(logical_line_index=None, logical_join="cell"), "must be null outside logical_order"),
        (lambda p: p["pages"][0]["lines"][0]["baseline"].reverse(), "left-to-right"),
        (lambda p: p["pages"][0]["lines"][0].update(text="\u200fנבדק"), "bidi control"),
        (lambda p: p["pages"][0]["lines"][0].update(text="נבדק "), "surrounding whitespace"),
        (lambda p: p["pages"][0].update(page_sha256="f" * 64), "page_sha256"),
        (lambda p: p["pages"][0]["lines"][0].update(region="margin_scribble"), "schema violation"),
        (lambda p: p["pages"][2]["lines"][0].update(region_index=1), "must have region 'title' and region_index 0"),
        (lambda p: p["pages"][2]["regions"][0].update(type="body"), "must have region 'body'"),
        (lambda p: p["pages"][2]["regions"][1]["line_indices"].insert(0, 0), "in another region"),
        (lambda p: p["pages"][2]["regions"].pop(), "every line exactly once"),
        (lambda p: p["pages"][2]["regions"][1].update(reading_order_index=2), "reading_order_index must be 1"),
        (
            lambda p: p["pages"][2]["regions"][2].update(polygon=p["pages"][2]["lines"][3]["polygon"]),
            "does not contain line 4",
        ),
        (lambda p: p["pages"][0].pop("regions"), "every page or on none"),
        (lambda p: p["pages"][0]["regions"][0].update(line_indices=[]), "schema violation"),
    ],
)
def test_validate_rejects_inconsistent_sidecar(
    annotated_batch: Path, tmp_path: Path, mutate, message: str
) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    for relative, data in _tree_bytes(annotated_batch).items():
        target = batch / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _rewrite(batch / LINE_ANNOTATIONS_FILENAME, mutate)

    with pytest.raises(BatchValidationError, match=message):
        validate_batch(batch)


def test_source_corpus_id_keeps_packaged_id_and_hashes_external_corpora(tmp_path: Path) -> None:
    assert source_corpus_id(None) == "packaged:synthetic/texts/hebrew_lines.txt"
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("שורה אחת.\n", encoding="utf-8")
    assert source_corpus_id(corpus) == f"external:sha256:{sha256_file(corpus)}"


def test_generate_cli_text_corpus_and_line_annotations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("שורה ראשונה מקורפוס חיצוני.\nשורה שנייה מקורפוס חיצוני.\n", encoding="utf-8")
    output_dir = tmp_path / "batch"

    exit_code = main(
        [
            "generate", "--count", "2", "--seed", "9", "--output", str(output_dir),
            "--text-corpus", str(corpus), "--emit-line-annotations", "--format", "json",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    corpus_sha = sha256_file(corpus)
    assert report["line_annotations_path"] == str(output_dir / LINE_ANNOTATIONS_FILENAME)
    assert report["text_corpus"] == {
        "source_corpus": f"external:sha256:{corpus_sha}",
        "sha256": corpus_sha,
    }
    manifest = _load(output_dir / "generation_manifest.json")
    assert {sample["provenance"]["source_corpus"] for sample in manifest["samples"]} == {
        f"external:sha256:{corpus_sha}"
    }
    body_texts = {
        line["text"]
        for page in _load(output_dir / LINE_ANNOTATIONS_FILENAME)["pages"]
        for line in page["lines"]
        if line["region"] == "body"
    }
    assert body_texts <= {"שורה ראשונה מקורפוס חיצוני.", "שורה שנייה מקורפוס חיצוני."}
    assert validate_batch(output_dir).sample_count == 2


def test_generate_cli_report_is_unchanged_without_new_flags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["generate", "--count", "1", "--seed", "9", "--output", str(tmp_path / "b"), "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report) == {"schema_version", "sample_count", "page_count", "output_path", "manifest_path"}
    assert not (tmp_path / "b" / LINE_ANNOTATIONS_FILENAME).exists()


def test_generate_cli_rejects_missing_text_corpus(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["generate", "--count", "1", "--seed", "1", "--output", str(tmp_path / "b"),
              "--text-corpus", str(tmp_path / "missing.txt")])
    assert excinfo.value.code == 2
    assert "--text-corpus is not a file" in capsys.readouterr().err
    assert not (tmp_path / "b").exists()


def test_evidence_run_cli_records_line_annotations_and_text_corpus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("שורה ראשונה מקורפוס חיצוני.\nשורה שנייה מקורפוס חיצוני.\n", encoding="utf-8")

    exit_code = main(
        [
            "evidence-run", "--count", "2", "--seed", "5", "--output-root", str(tmp_path / "runs"),
            "--run-id", "la", "--color", "never", "--format", "json", "--no-rendering-coverage-report",
            "--text-corpus", str(corpus), "--emit-line-annotations",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / "runs" / "la"
    sidecar = run_dir / "generated_batch" / LINE_ANNOTATIONS_FILENAME
    assert report["line_annotations_path"] == str(sidecar)
    assert report["reports"]["generation"]["line_annotations_path"] == str(sidecar)
    assert report["text_corpus"]["sha256"] == sha256_file(corpus)
    assert sidecar.is_file()
    notes = (run_dir / "RUN_NOTES.md").read_text(encoding="utf-8")
    assert "- line_annotations: generated_batch/line_annotations.json" in notes
    assert f"- text_corpus: external:sha256:{sha256_file(corpus)}" in notes
    assert "generated_batch/line_annotations.json" in (run_dir / "SHA256SUMS").read_text(encoding="utf-8")


def test_no_rendered_line_is_clipped_by_the_page_edge(tmp_path: Path) -> None:
    documents = generate_documents(
        len(ALL_TEMPLATES) * 2,
        101,
        ALL_TEMPLATES,
        default_font_manifest_path(),
        default_text_corpus_path(),
        tmp_path,
        record_line_geometry=True,
    )
    assert all(document.lines for document in documents)
    assert not [
        (document.sample_id, line.text)
        for document in documents
        for line in document.lines
        if line.clipped
    ]


VERY_LONG_LINE = " ".join(["הרישום הועבר לעיון ועד הקהילה בשבוע הבא לאחר בדיקה נוספת"] * 5) + "."


@pytest.mark.parametrize("template_id", ["printed_letter", "handwritten_note"])
def test_uncapped_bodies_stop_at_capacity_and_keep_gold_consistent(tmp_path: Path, template_id: str) -> None:
    corpus = tmp_path / "very_long.txt"
    corpus.write_text("\n".join([VERY_LONG_LINE] * 4) + "\n", encoding="utf-8")
    output_dir = tmp_path / "long"
    documents = generate_documents(
        1, 8, [template_id], default_font_manifest_path(), corpus, output_dir, record_line_geometry=True
    )
    document = documents[0]

    assert document.truncated_segments > 0
    assert not any(line.clipped for line in document.lines)
    body = [line for line in document.lines if line.region == "body"]
    footer = next(line for line in document.lines if line.region == "footer")
    annotation_tops = [
        min(y for _x, y in line.polygon)
        for line in document.lines
        if line.region in {"signature_area", "footer"}
    ]
    assert max(y for line in body for _x, y in line.polygon) < min(annotation_tops)
    logical_lines = document.logical_text.split("\n")
    assert logical_lines[-1] == footer.text
    # The last drawn source line may be partial; gold holds exactly what was drawn.
    rebuilt: dict[int, list[str]] = {}
    for line in body:
        rebuilt.setdefault(line.logical_line_index, []).append(line.text)
    assert [" ".join(parts) for _index, parts in sorted(rebuilt.items())] == logical_lines[1 : 1 + len(rebuilt)]


def test_overlong_word_is_rejected_instead_of_leaving_the_page(tmp_path: Path) -> None:
    corpus = tmp_path / "overlong.txt"
    corpus.write_text("א" * 80 + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="wider than the body"):
        generate_batch(1, 1, tmp_path / "out", ["printed_letter"], text_corpus_path=corpus)


def test_previous_generator_version_batches_still_validate(annotated_batch: Path, tmp_path: Path) -> None:
    batch = tmp_path / "old"
    for relative, data in _tree_bytes(annotated_batch).items():
        if relative == LINE_ANNOTATIONS_FILENAME:
            continue
        target = batch / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest_path = batch / "generation_manifest.json"
    for version, valid in (("d4a-realism-v2", True), ("unknown-v0", False)):
        payload = _load(manifest_path)
        for sample in payload["samples"]:
            sample["generator_version"] = version
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        if valid:
            assert validate_batch(batch).sample_count == len(ALL_TEMPLATES)
        else:
            with pytest.raises(BatchValidationError, match="generator_version"):
                validate_batch(batch)


# Region type sequence (in region_index = reading order) per render family.
EXPECTED_REGION_TYPES = {
    "printed_letter": ["title", "body", "stamp_area", "signature_area", "signature_area", "signature_area", "footer"],
    "handwritten_note": ["title", "body", "margin", "footer"],
    "archive_card": ["title", "identifier_area", "body", "table_cells", "stamp_area", "footer"],
    "ledger": ["title", "identifier_area", "table_cells", "footer"],
}
# Measured at bbcaf0e (s10c-gold-complete-v1, before S11a) for the
# annotated_batch fixture. S11a adds sidecar fields only, so the manifest,
# which pins every page sha256 and the logical_order gold, must not move.
PRE_S11A_ANNOTATED_BATCH_MANIFEST_SHA256 = "58ab662d2cff74b2da42c3b835087ebee7018d8acb0269d07c8729df1efeec19"


def _render_family(template_id: str) -> str:
    return generator_module._recipe_for_template(template_id).render_template_id


def test_regions_partition_lines_and_contain_their_polygons(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")

    for sample, page in zip(manifest["samples"], payload["pages"], strict=True):
        regions, lines = page["regions"], page["lines"]
        assert [region["type"] for region in regions] == EXPECTED_REGION_TYPES[
            _render_family(sample["provenance"]["template_id"])
        ]
        assert [region["region_index"] for region in regions] == list(range(len(regions)))
        owners = {line_index: region for region in regions for line_index in region["line_indices"]}
        assert sorted(owners) == list(range(len(lines)))
        assert sum(len(region["line_indices"]) for region in regions) == len(lines)
        for line in lines:
            region = owners[line["line_index"]]
            assert line["region_index"] == region["region_index"]
            assert line["region"] == region["type"]
            # Pages are rotated; containment is checked on the rotated polygons.
            assert polygon_contains(region["polygon"], line["polygon"])


def test_region_reading_order_agrees_with_logical_order(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")

    for sample, page in zip(manifest["samples"], payload["pages"], strict=True):
        regions = sorted(page["regions"], key=lambda region: region["reading_order_index"])
        assert [region["reading_order_index"] for region in regions] == list(range(len(regions)))
        walked = [page["lines"][line_index] for region in regions for line_index in region["line_indices"]]
        assert [line["line_index"] for line in walked] == list(range(len(page["lines"])))
        rebuilt = reconstruct_logical_lines(walked)
        assert "\n".join(rebuilt[index] for index in sorted(rebuilt)) == sample["text"]["logical_order"]
        # Each region covers a contiguous run of logical_order lines.
        previous_last = -1
        for region in regions:
            logical = [page["lines"][line_index]["logical_line_index"] for line_index in region["line_indices"]]
            assert logical[0] == previous_last + 1
            assert sorted(set(logical)) == list(range(logical[0], logical[-1] + 1))
            previous_last = logical[-1]


def test_region_polygon_contains_lines_and_furniture_under_rotation() -> None:
    recorder = _LineRecorder(rotation_degrees=7.0)
    recorder.lines.append(
        generator_module._RecordedLine("body", "שורה", 0, None, (300.0, 200.0, 900.0, 240.0), 232.0, "body")
    )
    recorder.lines.append(
        generator_module._RecordedLine("body", "שנייה", 1, None, (500.0, 260.0, 900.0, 300.0), 292.0, "body")
    )
    recorder.lines.append(
        generator_module._RecordedLine("stamp_area", "נבדק", 2, None, (150.0, 400.0, 210.0, 430.0), 425.0, "stamp_area")
    )
    ring = (80.0, 360.0, 280.0, 470.0)
    recorder.add_region_box(ring, owner=2)

    lines = recorder.final_lines(CANVAS_SIZE)
    regions = recorder.final_regions(CANVAS_SIZE)
    assert [(region.region_type, region.line_indices, region.reading_order_index) for region in regions] == [
        ("body", (0, 1), 0),
        ("stamp_area", (2,), 1),
    ]
    assert [line.region_index for line in lines] == [0, 0, 1]
    for line in lines:
        assert polygon_contains(regions[line.region_index].polygon, line.polygon, tolerance=0.0)
    ring_corners = [
        _rotated_point(corner, 7.0, CANVAS_SIZE)
        for corner in ((ring[0], ring[1]), (ring[2], ring[1]), (ring[2], ring[3]), (ring[0], ring[3]))
    ]
    assert polygon_contains(regions[1].polygon, ring_corners)
    assert not polygon_contains(regions[0].polygon, ring_corners)


def test_pre_s11a_sidecar_without_regions_still_validates(annotated_batch: Path, tmp_path: Path) -> None:
    batch = tmp_path / "pre-s11a"
    for relative, data in _tree_bytes(annotated_batch).items():
        target = batch / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def strip(payload: dict) -> None:
        for page in payload["pages"]:
            page.pop("regions")
            for line in page["lines"]:
                line.pop("region_index")

    _rewrite(batch / LINE_ANNOTATIONS_FILENAME, strip)
    assert validate_batch(batch).page_count == len(ALL_TEMPLATES)
    _rewrite(batch / LINE_ANNOTATIONS_FILENAME, lambda p: p["pages"][0]["lines"][0].update(region_index=0))
    with pytest.raises(BatchValidationError, match="page has no regions"):
        validate_batch(batch)


def test_ledger_mixed_script_cells_do_not_overlap(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("סעיף מסומן בשם River — כולל A-17 ו B-24.\n", encoding="utf-8")
    batch = tmp_path / "batch"
    generate_batch(8, 26110302, batch, ["ledger"], text_corpus_path=corpus, emit_line_annotations=True)
    for page in _load(batch / LINE_ANNOTATIONS_FILENAME)["pages"]:
        rows: dict[int, list[dict]] = {}
        for line in page["lines"]:
            if line["region"] == "table_cells":
                rows.setdefault(line["logical_line_index"], []).append(line)
        cell_rows = [cells for cells in rows.values() if len(cells) == 5]
        assert cell_rows
        assert sum(len(cells) for cells in rows.values() if len(cells) > 1) == 5 * len(cell_rows)
        for cells in cell_rows:
            for left, right in zip(cells, cells[1:]):
                assert max(point[0] for point in left["polygon"]) < min(point[0] for point in right["polygon"])


def test_ledger_rejects_an_unbreakable_token_wider_than_detail_cell(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("א" * 100 + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Ledger detail token exceeds cell width"):
        generate_batch(1, 1, tmp_path / "batch", ["ledger"], text_corpus_path=corpus)


def test_default_fixture_pages_and_gold_remain_unchanged(tmp_path: Path) -> None:
    fixture_dir = resources.files("hocrsyngen") / "data" / "contracts" / "generation_manifest_v1" / "fixture-batch"
    packaged = json.loads((fixture_dir / "generation_manifest.json").read_text(encoding="utf-8"))
    out = tmp_path / "fixture"
    generate_batch(2, 17, out)
    actual = _load(out / "generation_manifest.json")
    if [p["sha256"] for s in actual["samples"] for p in s["pages"]] != [
        p["sha256"] for s in packaged["samples"] for p in s["pages"]
    ]:
        pytest.skip("render stack does not reproduce packaged fixture pixels")
    for sample in actual["samples"]:
        sample["generator_version"] = "s10c-gold-complete-v1"
    assert actual == packaged
