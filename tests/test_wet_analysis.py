"""
Regression tests for three findings confirmed in the smoke-17 human review
(wet_review_feedback.v1, 2026-05-13):

  repeated_page_id  — P1, promote_to_test: yes
  repeated_sample_id — P1, promote_to_test: yes
  duplicate_text     — P2, promote_to_test: yes
  low_ink_density    — P2, promote_to_test: no  (reviewer: not a real issue)

Each cluster verifies that the finding is present, has the expected severity,
and carries correctly-shaped details. The smoke-17 run is the canonical trigger:
the supplemental batch reuses sample/page IDs from the main batch by design.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hocrsyngen.cli import main
from hocrsyngen.wet_analysis import analyze_wet_test_run


@pytest.fixture(scope="module")
def smoke_17_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    run_dir = tmp_path_factory.mktemp("wet-analysis-smoke17") / "run"
    assert (
        main(
            [
                "wet-run",
                "--profile",
                "smoke",
                "--seed",
                "17",
                "--output",
                str(run_dir),
            ]
        )
        == 0
    )
    return run_dir


@pytest.fixture(scope="module")
def smoke_17_analysis(smoke_17_run: Path) -> Any:
    return analyze_wet_test_run(run_root=smoke_17_run)


def _get_warning(analysis: Any, code: str) -> dict[str, Any]:
    for w in analysis.payload["warnings"]:
        if w["code"] == code:
            return w
    pytest.fail(f"expected warning code {code!r} not found in analysis warnings")


# ---------------------------------------------------------------------------
# repeated_page_id (P1)
# ---------------------------------------------------------------------------


def test_repeated_page_id_is_detected(smoke_17_analysis: Any) -> None:
    codes = {w["code"] for w in smoke_17_analysis.payload["warnings"]}
    assert "repeated_page_id" in codes


def test_repeated_page_id_severity_is_p1(smoke_17_analysis: Any) -> None:
    assert _get_warning(smoke_17_analysis, "repeated_page_id")["severity"] == "P1"


def test_repeated_page_id_details_are_structured(smoke_17_analysis: Any) -> None:
    warning = _get_warning(smoke_17_analysis, "repeated_page_id")
    details = warning.get("details", [])
    assert len(details) >= 1, "details must list at least one duplicate page_id"
    for entry in details:
        assert "page_id" in entry, "each detail entry must have page_id"
        assert entry["count"] >= 2, "each duplicate must appear at least twice"


# ---------------------------------------------------------------------------
# repeated_sample_id (P1)
# ---------------------------------------------------------------------------


def test_repeated_sample_id_is_detected(smoke_17_analysis: Any) -> None:
    codes = {w["code"] for w in smoke_17_analysis.payload["warnings"]}
    assert "repeated_sample_id" in codes


def test_repeated_sample_id_severity_is_p1(smoke_17_analysis: Any) -> None:
    assert _get_warning(smoke_17_analysis, "repeated_sample_id")["severity"] == "P1"


def test_repeated_sample_id_details_are_structured(smoke_17_analysis: Any) -> None:
    warning = _get_warning(smoke_17_analysis, "repeated_sample_id")
    details = warning.get("details", [])
    assert len(details) >= 1, "details must list at least one duplicate sample_id"
    for entry in details:
        assert "sample_id" in entry, "each detail entry must have sample_id"
        assert entry["count"] >= 2, "each duplicate must appear at least twice"


# ---------------------------------------------------------------------------
# duplicate_text (P2)
# ---------------------------------------------------------------------------


def test_duplicate_text_is_detected(smoke_17_analysis: Any) -> None:
    codes = {w["code"] for w in smoke_17_analysis.payload["warnings"]}
    assert "duplicate_text" in codes


def test_duplicate_text_severity_is_p2(smoke_17_analysis: Any) -> None:
    assert _get_warning(smoke_17_analysis, "duplicate_text")["severity"] == "P2"


def test_duplicate_text_report_section_is_consistent(smoke_17_analysis: Any) -> None:
    dup = smoke_17_analysis.payload["duplicate_text"]
    assert dup["duplicate_text_sample_count"] >= 1
    assert dup["duplicate_text_rate"] > 0.0
    assert len(dup["duplicate_text_values"]) >= 1
    for entry in dup["duplicate_text_values"]:
        assert entry["count"] >= 2, "each listed text must appear at least twice"


def test_duplicate_text_details_match_report_section(smoke_17_analysis: Any) -> None:
    warning = _get_warning(smoke_17_analysis, "duplicate_text")
    dup = smoke_17_analysis.payload["duplicate_text"]
    assert warning["count"] == len(dup["duplicate_text_values"])
