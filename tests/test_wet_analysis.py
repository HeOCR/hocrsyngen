"""
Regression tests for three warning codes that the smoke profile triggers
deterministically:

- repeated_page_id / repeated_sample_id: the supplemental batch starts its
  sample counter at 000000, colliding with the main batch's first sample.
  Exactly one sample ID and one page ID are shared across both batches.

- duplicate_text: with seed 17 the supplemental sample draws a logical text
  that already appears in the main batch. With 8 total samples this produces
  exactly one duplicate text and a rate of 0.125.

low_ink_density was confirmed not a real issue in human review and is not
tested here.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hocrsyngen.cli import main
from hocrsyngen.wet_analysis import WetAnalysisResult, analyze_wet_test_run


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
def smoke_17_analysis(smoke_17_run: Path) -> WetAnalysisResult:
    return analyze_wet_test_run(run_root=smoke_17_run)


def _get_warning(analysis: WetAnalysisResult, code: str) -> dict[str, object]:
    for w in analysis.payload["warnings"]:
        if w["code"] == code:
            return w
    pytest.fail(f"expected warning code {code!r} not found in analysis warnings")


# ---------------------------------------------------------------------------
# repeated_page_id (P1)
# ---------------------------------------------------------------------------


def test_repeated_page_id_severity_is_p1(smoke_17_analysis: WetAnalysisResult) -> None:
    assert _get_warning(smoke_17_analysis, "repeated_page_id")["severity"] == "P1"


def test_repeated_page_id_exactly_one_duplicate_of_count_two(
    smoke_17_analysis: WetAnalysisResult,
) -> None:
    details = _get_warning(smoke_17_analysis, "repeated_page_id")["details"]
    assert len(details) == 1
    assert details[0]["count"] == 2


# ---------------------------------------------------------------------------
# repeated_sample_id (P1)
# ---------------------------------------------------------------------------


def test_repeated_sample_id_severity_is_p1(smoke_17_analysis: WetAnalysisResult) -> None:
    assert _get_warning(smoke_17_analysis, "repeated_sample_id")["severity"] == "P1"


def test_repeated_sample_id_exactly_one_duplicate_of_count_two(
    smoke_17_analysis: WetAnalysisResult,
) -> None:
    details = _get_warning(smoke_17_analysis, "repeated_sample_id")["details"]
    assert len(details) == 1
    assert details[0]["count"] == 2


# ---------------------------------------------------------------------------
# duplicate_text (P2)
# ---------------------------------------------------------------------------


def test_duplicate_text_severity_is_p2(smoke_17_analysis: WetAnalysisResult) -> None:
    assert _get_warning(smoke_17_analysis, "duplicate_text")["severity"] == "P2"


def test_duplicate_text_report_section_exact_values(
    smoke_17_analysis: WetAnalysisResult,
) -> None:
    dup = smoke_17_analysis.payload["duplicate_text"]
    assert dup["duplicate_text_sample_count"] == 1
    assert dup["duplicate_text_rate"] == 0.125
    assert len(dup["duplicate_text_values"]) == 1
    assert dup["duplicate_text_values"][0]["count"] == 2
