from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path

import pytest

from hocrsyngen.cli import main
from hocrsyngen.wet_report import NON_RELEASE_STATEMENT, WET_REPORT_VERSION, build_wet_report
from hocrsyngen.wet_review import REVIEW_FIELDS, build_wet_review_template


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


def _make_valid_review(smoke_run: Path, review_path: Path) -> None:
    """Write a completed all-pass review worksheet by patching a generated template."""
    review_path.parent.mkdir(parents=True, exist_ok=True)
    template_path = review_path.parent / (review_path.stem + "_tpl.csv")
    build_wet_review_template(
        run_root=smoke_run, output=template_path, review_format="csv"
    )
    text = template_path.read_text(encoding="utf-8")
    template_path.unlink()
    buf = io.StringIO()
    reader = csv.DictReader(io.StringIO(text))
    writer = csv.DictWriter(buf, fieldnames=list(REVIEW_FIELDS), lineterminator="\n")
    writer.writeheader()
    for row in reader:
        row["reviewer"] = "test_reviewer"
        row["decision"] = "pass"
        writer.writerow(row)
    review_path.write_text(buf.getvalue(), encoding="utf-8")


def test_bare_run_no_review_no_llm(smoke_run: Path) -> None:
    result = build_wet_report(run_root=smoke_run)
    assert result.payload["review_summary"]["status"] == "not_provided"
    assert result.payload["llm_triage_summary"]["status"] == "not_provided"


def test_non_release_statement_exact_content(smoke_run: Path) -> None:
    result = build_wet_report(run_root=smoke_run)
    assert result.payload["non_release_statement"] == NON_RELEASE_STATEMENT


def test_scope_flags(smoke_run: Path) -> None:
    result = build_wet_report(run_root=smoke_run)
    scope = result.payload["scope"]
    assert scope["generator_quality_evidence_only"] is True
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


def test_hard_blockers_exit_code_1(smoke_run: Path, tmp_path: Path) -> None:
    run_copy = tmp_path / "run"
    shutil.copytree(smoke_run, run_copy)
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
    analysis_path = run_copy / "reports" / "wet_analysis_report.json"
    analysis_path.write_text(
        json.dumps(fake_analysis, ensure_ascii=False), encoding="utf-8"
    )
    result = build_wet_report(run_root=run_copy)
    assert result.has_hard_blockers is True
    ret = main(["wet-report", str(run_copy)])
    assert ret == 1


def test_with_valid_review_file(smoke_run: Path) -> None:
    review_path = smoke_run / "review" / "test_valid_review.csv"
    _make_valid_review(smoke_run, review_path)
    result = build_wet_report(run_root=smoke_run, review_path=review_path)
    rs = result.payload["review_summary"]
    assert rs["valid"] is True
    dc = rs["decision_counts"]
    assert isinstance(dc, dict)
    assert set(dc.keys()) >= {"pass", "hold", "reject"}
    assert dc["pass"] > 0
    assert dc["hold"] == 0
    assert dc["reject"] == 0


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
