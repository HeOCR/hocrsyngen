from __future__ import annotations

import json
import unicodedata
from dataclasses import replace
from pathlib import Path, PurePosixPath

import jsonschema

from hocrsyngen.generator import (
    GENERATOR_VERSION,
    GOVERNED_TEMPLATE_IDS,
    generate_batch,
    generate_manifest,
)
from hocrsyngen.rendering_coverage import (
    RENDERING_COVERAGE_REPORT_FILENAME,
    RENDERING_COVERAGE_REPORT_VERSION,
    build_rendering_coverage_report,
    write_rendering_coverage_report,
)
from hocrsyngen.manifest import GenerationManifest, TextMetadata


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "hocrsyngen"
    / "schemas"
    / "rendering_coverage_report.schema.json"
)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
BIDI_NIQQUD_CORPUS_PATH = FIXTURES_DIR / "bidi_niqqud_rendering_corpus.txt"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _assert_report_paths_are_portable(report: dict) -> None:
    assert report["batch"]["manifest_path"] == "generation_manifest.json"
    for entry in report["coverage"].values():
        for evidence in entry["evidence"]:
            asset_path_text = evidence.get("asset_path")
            if asset_path_text is None:
                continue
            asset_path = PurePosixPath(asset_path_text)
            assert not asset_path.is_absolute()
            assert ".." not in asset_path.parts
            assert "\\" not in asset_path_text


def test_rendering_coverage_report_matches_v1_schema_for_generated_batch(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "coverage-batch"
    sample_count = len(GOVERNED_TEMPLATE_IDS)
    manifest = generate_batch(
        count=sample_count,
        seed=17,
        output_dir=output_dir,
        template_ids=GOVERNED_TEMPLATE_IDS,
    )

    report = build_rendering_coverage_report(manifest, output_dir)

    jsonschema.validate(report, _schema())
    assert report["report_version"] == RENDERING_COVERAGE_REPORT_VERSION
    assert report["generator_name"] == "hocrsyngen"
    assert report["generator_version"] == GENERATOR_VERSION
    assert report["batch"] == {
        "manifest_path": "generation_manifest.json",
        "sample_count": sample_count,
        "page_count": sample_count,
    }
    assert report["environment"]["pillow_raqm"] is True
    assert set(report["coverage"]) == {
        "fonts",
        "templates",
        "recipes",
        "degradation_presets",
        "text_features",
        "bidi_mixed_direction",
        "rendering_path",
        "asset_smoke",
    }
    assert report["coverage"]["templates"]["missing"] == []
    assert report["coverage"]["recipes"]["missing"] == []
    assert report["coverage"]["degradation_presets"]["missing"] == []
    assert report["coverage"]["fonts"]["missing"] == []
    assert report["coverage"]["asset_smoke"]["covered"] == [
        "readable_jpeg",
        "declared_dimensions_match",
        "non_empty_ink",
    ]
    _assert_report_paths_are_portable(report)


def test_rendering_coverage_report_summarizes_missing_text_dimensions(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "default-batch"
    manifest = generate_batch(count=2, seed=17, output_dir=output_dir)

    report = build_rendering_coverage_report(manifest, output_dir)

    text_features = report["coverage"]["text_features"]
    assert "final_forms" in text_features["covered"]
    assert "punctuation" in text_features["covered"]
    assert "numerals" in text_features["covered"]
    assert "nfc_logical_order_text" in text_features["covered"]
    assert "latin_fragments" in text_features["missing"]
    assert "sparse_niqqud" in text_features["missing"]
    assert "fuller_niqqud" in text_features["missing"]
    assert any(
        limitation.startswith("text_features missing coverage:")
        for limitation in report["limitations"]
    )


def test_rendering_coverage_report_detects_bidi_and_fuller_niqqud_fixture_text(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "bidi-niqqud-batch"
    manifest = generate_manifest(
        count=1,
        seed=2027,
        output_dir=output_dir,
        template_ids=["printed_letter"],
        text_corpus_path=BIDI_NIQQUD_CORPUS_PATH,
    )

    report = build_rendering_coverage_report(manifest, output_dir)

    text_features = report["coverage"]["text_features"]
    assert "sparse_niqqud" in text_features["covered"]
    assert "fuller_niqqud" in text_features["covered"]
    assert "latin_fragments" in text_features["covered"]
    bidi = report["coverage"]["bidi_mixed_direction"]
    assert bidi["covered"] == [
        "hebrew_latin_fragments",
        "hebrew_numeric_fragments",
        "hebrew_punctuation",
    ]
    assert bidi["missing"] == []
    text_evidence = report["coverage"]["text_features"]["evidence"]
    [evidence] = text_evidence
    assert "fuller_niqqud" in evidence["covered"]
    assert "latin_fragments" in evidence["covered"]
    assert isinstance(evidence["covered"], list)


def test_rendering_coverage_report_attributes_features_to_actual_samples(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mixed-feature-batch"
    generated = generate_batch(count=2, seed=17, output_dir=output_dir)
    manifest = GenerationManifest(
        samples=[
            replace(
                generated.samples[0],
                text=TextMetadata(
                    logical_order=unicodedata.normalize(
                        "NFC",
                        "כיוון מעורב: תיק HEOCR-2026-A17 נבדק. "
                        "הַיְּלָדִים כָּתְבוּ בַּמַּחְבֶּרֶת.",
                    )
                ),
            ),
            replace(
                generated.samples[1],
                text=TextMetadata(logical_order="שלום עולם."),
            ),
        ]
    )

    report = build_rendering_coverage_report(manifest, output_dir)

    text_evidence = {
        entry["sample_id"]: entry["covered"]
        for entry in report["coverage"]["text_features"]["evidence"]
    }
    first_sample_id = manifest.samples[0].sample_id
    second_sample_id = manifest.samples[1].sample_id
    assert "fuller_niqqud" in text_evidence[first_sample_id]
    assert "latin_fragments" in text_evidence[first_sample_id]
    assert "fuller_niqqud" not in text_evidence[second_sample_id]
    assert "latin_fragments" not in text_evidence[second_sample_id]


def test_rendering_coverage_report_asset_smoke_requires_all_pages_to_pass(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "corrupt-asset-batch"
    manifest = generate_batch(count=2, seed=17, output_dir=output_dir)
    corrupt_page = manifest.samples[1].pages[0]
    (output_dir / corrupt_page.asset_path).write_text("not a jpeg\n", encoding="utf-8")

    report = build_rendering_coverage_report(manifest, output_dir)

    asset_smoke = report["coverage"]["asset_smoke"]
    assert asset_smoke["covered"] == []
    assert asset_smoke["missing"] == [
        "readable_jpeg",
        "declared_dimensions_match",
        "non_empty_ink",
    ]
    failed_evidence = [
        entry
        for entry in asset_smoke["evidence"]
        if entry["sample_id"] == manifest.samples[1].sample_id
    ]
    assert failed_evidence == [
        {
            "sample_id": manifest.samples[1].sample_id,
            "asset_path": corrupt_page.asset_path,
            "readable_jpeg": False,
            "declared_dimensions_match": False,
            "non_empty_ink": False,
        }
    ]


def test_write_rendering_coverage_report_writes_sidecar_without_manifest_changes(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "coverage-sidecar"
    manifest = generate_batch(count=2, seed=17, output_dir=output_dir)
    manifest_before = (output_dir / "generation_manifest.json").read_text(
        encoding="utf-8"
    )

    report_path = write_rendering_coverage_report(manifest, output_dir)

    assert report_path == output_dir / RENDERING_COVERAGE_REPORT_FILENAME
    assert report_path.is_file()
    assert (output_dir / "generation_manifest.json").read_text(
        encoding="utf-8"
    ) == manifest_before
    jsonschema.validate(json.loads(report_path.read_text(encoding="utf-8")), _schema())
