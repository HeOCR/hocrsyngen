from __future__ import annotations

import json
from pathlib import Path

import pytest

from hocrsyngen.cli import main
from hocrsyngen.generator import generate_batch
from hocrsyngen.quality_check import quality_check
from hocrsyngen.validation import BatchValidationError


@pytest.fixture
def batch(tmp_path: Path) -> Path:
    root = tmp_path / "batch"
    generate_batch(2, 17, root, ["printed_letter", "ledger"], emit_line_annotations=True)
    return root


def test_quality_counts_match_sidecar_and_thresholds_are_strict(batch: Path, capsys) -> None:
    data = json.loads((batch / "line_annotations.json").read_text())
    result = quality_check(batch)
    trunc = sum(p["truncated_segments"] for p in data["pages"])
    occ = sum(line["occluded"] for p in data["pages"] for line in p["lines"])
    assert result["totals"]["truncated_segments"] == trunc
    assert result["totals"]["occluded_lines"] == occ
    assert result["totals"]["page_count"] == 2
    assert quality_check(batch, max_truncated_segments=trunc, max_occluded_lines=occ)["exceeded"] == []
    assert main(["quality-check", str(batch), "--format", "json", "--max-occluded-lines", "0"]) == int(occ > 0)
    assert json.loads(capsys.readouterr().out)["totals"] == result["totals"]
    assert quality_check(batch) == result


def test_missing_and_malformed_sidecars_fail_closed(batch: Path) -> None:
    path = batch / "line_annotations.json"
    path.unlink()
    with pytest.raises(ValueError, match="requires line_annotations"):
        quality_check(batch)
    path.write_text("{}")
    with pytest.raises(BatchValidationError):
        quality_check(batch)


def test_sidecar_manifest_binding_is_checked(batch: Path) -> None:
    path = batch / "line_annotations.json"
    sidecar = json.loads(path.read_text())
    sidecar["generation_manifest_sha256"] = "0" * 64
    path.write_text(json.dumps(sidecar))
    with pytest.raises(BatchValidationError):
        quality_check(batch)


@pytest.mark.parametrize("value", [-1, True, 1.0, "0"])
def test_invalid_api_thresholds_rejected(batch: Path, value) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        quality_check(batch, max_occluded_lines=value)


def test_empty_batch_has_explicit_zero_coverage(tmp_path: Path) -> None:
    batch = tmp_path / "empty"
    generate_batch(0, 17, batch, emit_line_annotations=True)
    result = quality_check(batch, max_truncated_segments=0, max_occluded_lines=0)
    assert result["coverage"] == "no_pages"
    assert result["totals"]["page_count"] == 0
    assert result["totals"]["line_count"] == 0
    assert result["by_template"] == {} and result["affected_pages"] == []
    assert result["exceeded"] == []
    assert "not a quality or release decision" in result["limitation"]


def test_recorded_findings_report_ids_counts_and_both_limits(batch: Path, capsys) -> None:
    path = batch / "line_annotations.json"
    data = json.loads(path.read_text())
    for page in data["pages"]:
        page["truncated_segments"] = 0
        for line in page["lines"]:
            line["occluded"] = False
    data["pages"][0]["truncated_segments"] = 3
    data["pages"][0]["lines"][0]["occluded"] = True
    path.write_text(json.dumps(data, ensure_ascii=False))
    result = quality_check(batch, max_truncated_segments=0, max_occluded_lines=0)
    assert result["exceeded"] == ["truncated_segments", "occluded_lines"]
    assert result["by_template"]["printed_letter"]["pages_with_occlusion"] == 1
    assert result["affected_pages"] == [{"sample_id": data["pages"][0]["sample_id"],
        "page_id": data["pages"][0]["page_id"], "template_id": "printed_letter",
        "truncated_segments": 3, "occluded_lines": 1,
        "warning_ids": ["truncated_segments", "occluded_lines"]}]
    assert main(["quality-check", str(batch), "--format", "json", "--max-truncated-segments", "0"]) == 1
    assert json.loads(capsys.readouterr().out)["exceeded"] == ["truncated_segments"]
