from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from hocrsyngen.cli import main
from hocrsyngen.generator import generate_batch
from hocrsyngen.io import sha256_file
from hocrsyngen.validation import BatchValidationError, validate_batch


def _manifest_path(batch_dir: Path) -> Path:
    return batch_dir / "generation_manifest.json"


def _load_manifest(batch_dir: Path) -> dict:
    return json.loads(_manifest_path(batch_dir).read_text(encoding="utf-8"))


def _write_manifest(batch_dir: Path, payload: dict) -> None:
    _manifest_path(batch_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _generated_batch(tmp_path: Path) -> Path:
    batch_dir = tmp_path / "fixture-batch"
    generate_batch(count=1, seed=17, output_dir=batch_dir)
    return batch_dir


def test_validate_generated_batch_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    batch_dir = _generated_batch(tmp_path)

    assert main(["validate", str(batch_dir)]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"Validated 1 samples and 1 pages in {batch_dir}\n"
    assert captured.err == ""


def test_validate_missing_manifest_fails_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    batch_dir = tmp_path / "missing-manifest"
    batch_dir.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        main(["validate", str(batch_dir)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Missing manifest" in captured.err
    assert "Traceback" not in captured.err


def test_validate_malformed_json_fails_cleanly(tmp_path: Path) -> None:
    batch_dir = tmp_path / "malformed"
    batch_dir.mkdir()
    _manifest_path(batch_dir).write_text("{not json\n", encoding="utf-8")

    with pytest.raises(BatchValidationError, match="Malformed manifest JSON"):
        validate_batch(batch_dir)


def test_validate_schema_invalid_manifest_fails_cleanly(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    del payload["samples"][0]["sample_id"]
    _write_manifest(batch_dir, payload)

    with pytest.raises(
        BatchValidationError,
        match=r"Manifest schema validation failed at \$\.samples\[0\]",
    ):
        validate_batch(batch_dir)


def test_validate_missing_asset_fails_cleanly(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    asset_path = batch_dir / payload["samples"][0]["pages"][0]["asset_path"]
    asset_path.unlink()

    with pytest.raises(BatchValidationError, match="asset_path is missing"):
        validate_batch(batch_dir)


def test_validate_asset_sha256_mismatch_fails_cleanly(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["pages"][0]["sha256"] = "0" * 64
    _write_manifest(batch_dir, payload)

    with pytest.raises(BatchValidationError, match="sha256 mismatch"):
        validate_batch(batch_dir)


def test_validate_generator_version_mismatch_fails_cleanly(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["generator_version"] = "other-generator"
    _write_manifest(batch_dir, payload)

    with pytest.raises(BatchValidationError, match="generator_version"):
        validate_batch(batch_dir)


def test_validate_rejects_unknown_provenance_template_id(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["provenance"]["template_id"] = "typo_template"
    _write_manifest(batch_dir, payload)

    with pytest.raises(
        BatchValidationError,
        match=r"samples\[0\]\.provenance\.template_id is not a governed template: typo_template",
    ):
        validate_batch(batch_dir)


def test_validate_rejects_mismatched_sample_and_provenance_recipe_id(
    tmp_path: Path,
) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["provenance"]["recipe_id"] = "handwritten_note_marginalia_v1"
    _write_manifest(batch_dir, payload)

    with pytest.raises(
        BatchValidationError,
        match=r"samples\[0\]\.recipe_id must match provenance\.recipe_id",
    ):
        validate_batch(batch_dir)


def test_validate_rejects_known_template_with_wrong_recipe_id(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["recipe_id"] = "handwritten_note_marginalia_v1"
    payload["samples"][0]["provenance"]["recipe_id"] = "handwritten_note_marginalia_v1"
    _write_manifest(batch_dir, payload)

    with pytest.raises(
        BatchValidationError,
        match=r"samples\[0\]\.provenance\.recipe_id must be printed_letter_form_v1",
    ):
        validate_batch(batch_dir)


def test_validate_rejects_known_template_with_wrong_degradation_preset(
    tmp_path: Path,
) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["provenance"]["degradation_preset"] = "notebook_scan_worn"
    _write_manifest(batch_dir, payload)

    with pytest.raises(
        BatchValidationError,
        match=r"samples\[0\]\.provenance\.degradation_preset must be office_scan_soft",
    ):
        validate_batch(batch_dir)


def test_validate_rejects_known_template_with_wrong_font_id(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["provenance"]["font_id"] = "gveret-levin-regular"
    _write_manifest(batch_dir, payload)

    with pytest.raises(
        BatchValidationError,
        match=r"samples\[0\]\.provenance\.font_id must be alef-regular",
    ):
        validate_batch(batch_dir)


@pytest.mark.parametrize(
    "asset_path", ["/tmp/page.jpg", "../page.jpg", "assets\\page.jpg"]
)
def test_validate_non_portable_asset_paths_are_rejected(
    tmp_path: Path, asset_path: str
) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["pages"][0]["asset_path"] = asset_path
    _write_manifest(batch_dir, payload)

    with pytest.raises(BatchValidationError, match="Manifest schema validation failed"):
        validate_batch(batch_dir)


def test_validate_dimension_mismatch_is_detected(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["pages"][0]["width"] = 1
    _write_manifest(batch_dir, payload)

    with pytest.raises(BatchValidationError, match="dimensions mismatch"):
        validate_batch(batch_dir)


def test_validate_media_type_mismatch_is_detected(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    page = payload["samples"][0]["pages"][0]
    asset_path = batch_dir / page["asset_path"]
    Image.new("RGB", (page["width"], page["height"]), (255, 255, 255)).save(
        asset_path, format="PNG"
    )
    page["sha256"] = sha256_file(asset_path)
    _write_manifest(batch_dir, payload)

    with pytest.raises(BatchValidationError, match="media_type mismatch"):
        validate_batch(batch_dir)


def test_validate_truncated_jpeg_is_detected_even_when_sha256_matches(
    tmp_path: Path,
) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    page = payload["samples"][0]["pages"][0]
    asset_path = batch_dir / page["asset_path"]
    asset_path.write_bytes(asset_path.read_bytes()[:512])
    page["sha256"] = sha256_file(asset_path)
    _write_manifest(batch_dir, payload)

    with pytest.raises(BatchValidationError, match="not a valid image"):
        validate_batch(batch_dir)


def test_validate_rejects_non_nfc_logical_text(tmp_path: Path) -> None:
    batch_dir = _generated_batch(tmp_path)
    payload = _load_manifest(batch_dir)
    payload["samples"][0]["text"]["logical_order"] = "\ufb31"
    _write_manifest(batch_dir, payload)

    with pytest.raises(BatchValidationError, match="NFC-normalized"):
        validate_batch(batch_dir)
