from __future__ import annotations

import json
import statistics
import unicodedata
from importlib import resources
from pathlib import Path

import jsonschema
import pytest
from PIL import Image, ImageDraw

from hocrsyngen.assets import default_font_manifest_path, default_text_corpus_path
from hocrsyngen.cli import main
from hocrsyngen.generator import (
    CANVAS_SIZE,
    GOVERNED_TEMPLATE_IDS,
    _rotated_point,
    generate_batch,
    generate_documents,
    source_corpus_id,
)
from hocrsyngen.io import sha256_file
from hocrsyngen.line_annotations import (
    LINE_ANNOTATIONS_FILENAME,
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
        if sample["provenance"]["template_id"] != "ledger":
            # Without wrapping or table cells, the lines are logical_order verbatim.
            assert "\n".join(line["text"] for line in lines) == sample["text"]["logical_order"]

    assert templates_seen == set(ALL_TEMPLATES)


def test_ledger_rows_are_cells_joined_with_pipe_separator(annotated_batch: Path) -> None:
    payload = _load(annotated_batch / LINE_ANNOTATIONS_FILENAME)
    manifest = _load(annotated_batch / "generation_manifest.json")
    ledger_index = ALL_TEMPLATES.index("ledger")
    lines = payload["pages"][ledger_index]["lines"]
    logical_lines = manifest["samples"][ledger_index]["text"]["logical_order"].split("\n")

    row_groups: dict[int, list[str]] = {}
    for line in lines:
        row_groups.setdefault(line["logical_line_index"], []).append(line["text"])
    multi_cell_rows = {index: cells for index, cells in row_groups.items() if len(cells) > 1}
    assert multi_cell_rows
    for index, cells in multi_cell_rows.items():
        assert len(cells) == 5
        assert " | ".join(cells) == logical_lines[index]


def test_wrapped_source_lines_share_logical_index_and_rejoin_with_space(tmp_path: Path) -> None:
    corpus = tmp_path / "long.txt"
    corpus.write_text(LONG_LINE + "\n", encoding="utf-8")
    output_dir = tmp_path / "wrapped"
    generate_batch(1, 4, output_dir, ["printed_letter"], text_corpus_path=corpus, emit_line_annotations=True)

    lines = _load(output_dir / LINE_ANNOTATIONS_FILENAME)["pages"][0]["lines"]
    body = [line for line in lines if line["region"] == "body"]
    assert len(body) > 1
    assert {line["logical_line_index"] for line in body} == {1}
    assert " ".join(line["text"] for line in body) == LONG_LINE
    assert validate_batch(output_dir).sample_count == 1


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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p.update(generation_manifest_sha256="0" * 64), "generation_manifest_sha256"),
        (lambda p: p["pages"][0]["lines"][0].update(text="שגוי"), "rebuild"),
        (lambda p: p["pages"][0]["lines"][0]["polygon"][0].__setitem__(0, 5000), "outside the page"),
        (lambda p: p["pages"][0]["lines"].pop(), "cover every logical_order line"),
        (lambda p: p["pages"][0].update(page_sha256="f" * 64), "page_sha256"),
        (lambda p: p["pages"][0]["lines"][0].update(region="margin_scribble"), "schema violation"),
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
