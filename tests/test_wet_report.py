from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from hocrsyngen.cli import main
from hocrsyngen.wet_report import WET_REPORT_VERSION, build_wet_report
from hocrsyngen.wet_review import REVIEW_FIELDS


_FORBIDDEN_STRINGS = (
    "release eligible",
    "release ready",
    "release-eligible",
    "release-ready",
    "CER",
    "WER",
    "release eligibility",
    "production ready",
    "production-ready",
)


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    run_dir = tmp_path_factory.mktemp("wet-report-smoke") / "run"
    assert (
        main(
            [
                "wet-run",
                "--profile",
                "smoke",
                "--seed",
                "42",
                "--output",
                str(run_dir),
            ]
        )
        == 0
    )
    return run_dir


@pytest.fixture
def report_out(smoke_run: Path, request: pytest.FixtureRequest) -> Path:
    return smoke_run / "reports" / request.node.name


def test_bare_run_no_review_no_llm(smoke_run: Path) -> None:
    result = build_wet_report(run_root=smoke_run)
    assert result.payload["review_summary"]["status"] == "not_provided"
    assert result.payload["llm_triage_summary"]["status"] == "not_provided"


def test_non_release_statement_present_and_non_empty(smoke_run: Path) -> None:
    result = build_wet_report(run_root=smoke_run)
    statement = result.payload.get("non_release_statement", "")
    assert isinstance(statement, str) and statement.strip()


def test_scope_flags(smoke_run: Path) -> None:
    result = build_wet_report(run_root=smoke_run)
    scope = result.payload["scope"]
    assert scope["release_ready_dataset_artifact"] is False
    assert scope["network_required"] is False
    assert scope["manifest_v1_changed"] is False


def test_json_format_report_version(
    smoke_run: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ret = main(
        [
            "wet-report",
            str(smoke_run),
            "--format",
            "json",
        ]
    )
    assert ret == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["report_version"] == WET_REPORT_VERSION


def test_hard_blockers_exit_code_1(smoke_run: Path) -> None:
    reports_dir = smoke_run / "reports"
    fake_analysis = {
        "report_version": "wet_analysis_report.v1",
        "status": "blocked",
        "summary": {
            "sample_count": 1,
            "page_count": 1,
            "warning_count": 0,
            "hard_blocker_count": 1,
        },
        "hard_blockers": [
            {
                "code": "test_blocker",
                "severity": "P0",
                "message": "Injected test hard blocker.",
            }
        ],
        "warnings": [],
    }
    analysis_path = reports_dir / "wet_analysis_report.json"
    original_exists = analysis_path.exists()
    original_content = analysis_path.read_bytes() if original_exists else None
    try:
        analysis_path.write_text(
            json.dumps(fake_analysis, ensure_ascii=False), encoding="utf-8"
        )
        result = build_wet_report(run_root=smoke_run)
        assert result.has_hard_blockers is True
        # Also verify exit code via CLI
        ret = main(["wet-report", str(smoke_run)])
        assert ret == 1
    finally:
        if original_content is not None:
            analysis_path.write_bytes(original_content)
        elif analysis_path.exists():
            analysis_path.unlink()


def _make_valid_review(smoke_run: Path, review_path: Path) -> None:
    """Write a minimal valid completed review worksheet for smoke_run."""
    from hocrsyngen.wet_run_artifact import load_wet_run_payload, read_batches
    from pathlib import PurePosixPath
    from hocrsyngen.wet_run_artifact import portable_path
    import json as _json

    run_payload = load_wet_run_payload(smoke_run, require_passed=True)
    batches = read_batches(run_payload)
    rows = []
    for batch in batches:
        resolved = batch.resolved(smoke_run)
        manifest = _json.loads(
            resolved.manifest_path_abs.read_text(encoding="utf-8")
        )
        for sample in manifest.get("samples", []):
            provenance = sample.get("provenance") or {}
            controls = sample.get("controls") or {}
            for page in sample.get("pages", []):
                run_asset_path = (
                    PurePosixPath(batch.batch_path)
                    / portable_path(page.get("asset_path"))
                )
                rows.append(
                    {
                        "batch_id": batch.batch_id,
                        "sample_id": str(sample.get("sample_id", "")),
                        "page_id": str(page.get("page_id", "")),
                        "template_id": str(provenance.get("template_id", "")),
                        "recipe_id": str(
                            provenance.get(
                                "recipe_id", sample.get("recipe_id", "")
                            )
                        ),
                        "persona": str(controls.get("persona") or ""),
                        "condition": str(controls.get("condition") or ""),
                        "degradation": str(
                            provenance.get("degradation_preset", "")
                        ),
                        "font_id": str(provenance.get("font_id", "")),
                        "asset_path": run_asset_path.as_posix(),
                        "reviewer": "test_reviewer",
                        "decision": "pass",
                        "severity": "",
                        "reason_codes": "",
                        "notes": "",
                        "regression_fixture_candidate": "",
                    }
                )
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(REVIEW_FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_with_valid_review_file(smoke_run: Path) -> None:
    review_path = smoke_run / "review" / "test_valid_review.csv"
    _make_valid_review(smoke_run, review_path)
    result = build_wet_report(run_root=smoke_run, review_path=review_path)
    rs = result.payload["review_summary"]
    assert rs["valid"] is True
    dc = rs.get("decision_counts") or {}
    assert isinstance(dc, dict) and dc


def test_report_text_does_not_contain_forbidden_strings(
    smoke_run: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ret = main(["wet-report", str(smoke_run)])
    assert ret == 0
    captured = capsys.readouterr()
    text = captured.out
    for bad in _FORBIDDEN_STRINGS:
        assert bad not in text, f"report text must not contain {bad!r}"
