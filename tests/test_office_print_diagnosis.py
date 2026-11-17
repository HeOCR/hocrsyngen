"""The office-print number diagnosis probe (experiments/office_print_v0/diagnosis) keeps its patterns pinned.

The probe runs against eval's restricted D-bench outputs, which CI never has. Its classifier is pure, so the
known-string table it checks before every run is also checked here, and a regression like the ungrouped-alternation
bug of 2026-11-18 (PLAN.md §2.2.1) fails CI.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parents[1] / "experiments" / "office_print_v0" / "diagnosis" / "number_assembly.py"


def _probe():
    spec = importlib.util.spec_from_file_location("number_assembly", PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NA = _probe()


@pytest.mark.parametrize(("token", "hyp", "want"), NA.KNOWN)
def test_known_strings(token, hyp, want):
    assert NA.classify(token, hyp) == want


def test_gap_alternation_stays_inside_the_gap():
    # The 2026-11-18 bug: with the gap ungrouped, this pattern matched any lone "3" next to whitespace.
    p = NA.pattern(["1", "3"], NA.GAP_SPACE)
    assert p.count("(?:") == 1
    assert NA.classify("3.1", "בעמוד 3 ראו") == "no_group"


def test_self_test_passes_and_main_runs_it():
    NA.self_test()
    NA.main(["number_assembly.py", "--self-test"])
