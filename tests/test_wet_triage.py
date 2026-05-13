from __future__ import annotations

import json
from pathlib import Path

import pytest

from hocrsyngen.cli import main
from hocrsyngen.wet_triage import (
    LLM_TRIAGE_PACKET_REPORT_VERSION,
    _TriageSample,
    _apply_sample_warnings,
    build_llm_triage_packet,
)


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
    run_dir = tmp_path_factory.mktemp("wet-triage-smoke") / "run"
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
def triage_out(smoke_run: Path, request: pytest.FixtureRequest) -> Path:
    return smoke_run / "triage" / request.node.name


def test_packet_is_deterministic(smoke_run: Path) -> None:
    out1 = smoke_run / "triage" / "det-1"
    out2 = smoke_run / "triage" / "det-2"
    build_llm_triage_packet(run_root=smoke_run, output=out1, max_samples=5)
    build_llm_triage_packet(run_root=smoke_run, output=out2, max_samples=5)
    assert (out1 / "llm_triage_prompt.md").read_text(encoding="utf-8") == (
        out2 / "llm_triage_prompt.md"
    ).read_text(encoding="utf-8")
    pkt1 = json.loads((out1 / "llm_triage_packet.json").read_text(encoding="utf-8"))
    pkt2 = json.loads((out2 / "llm_triage_packet.json").read_text(encoding="utf-8"))
    assert pkt1 == pkt2


def test_max_samples_respected(triage_out: Path, smoke_run: Path) -> None:
    result = build_llm_triage_packet(run_root=smoke_run, output=triage_out, max_samples=1)
    assert result.payload["selected_sample_count"] == 1
    packet = json.loads((triage_out / "llm_triage_packet.json").read_text(encoding="utf-8"))
    assert len(packet["samples"]) == 1


def test_prompt_does_not_contain_forbidden_strings(
    triage_out: Path, smoke_run: Path
) -> None:
    build_llm_triage_packet(run_root=smoke_run, output=triage_out, max_samples=5)
    prompt = (triage_out / "llm_triage_prompt.md").read_text(encoding="utf-8")
    for bad_string in _FORBIDDEN_STRINGS:
        assert bad_string not in prompt, f"prompt must not contain {bad_string!r}"


def test_prompt_contains_advisory_disclaimer(triage_out: Path, smoke_run: Path) -> None:
    build_llm_triage_packet(run_root=smoke_run, output=triage_out, max_samples=3)
    prompt = (triage_out / "llm_triage_prompt.md").read_text(encoding="utf-8")
    assert "advisory" in prompt
    assert "not pass/fail" in prompt


def test_prompt_questions_are_sequentially_numbered(
    triage_out: Path, smoke_run: Path
) -> None:
    build_llm_triage_packet(run_root=smoke_run, output=triage_out)
    prompt = (triage_out / "llm_triage_prompt.md").read_text(encoding="utf-8")
    assert "1. Does the Hebrew text" in prompt
    assert "2. Are there visible rendering" in prompt
    assert "1. Are there visible rendering" not in prompt


def test_invalid_run_directory_exits_nonzero(tmp_path: Path) -> None:
    out = tmp_path / "does-not-exist" / "review"
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "wet-llm-packet",
                str(tmp_path / "does-not-exist"),
                "--output",
                str(out),
            ]
        )
    assert exc_info.value.code != 0


def test_max_samples_zero_exits_nonzero(smoke_run: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "wet-llm-packet",
                str(smoke_run),
                "--output",
                str(smoke_run / "triage" / "zero-samples"),
                "--max-samples",
                "0",
            ]
        )
    assert exc_info.value.code != 0


def test_json_format_report_schema_version(
    triage_out: Path,
    smoke_run: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ret = main(
        [
            "wet-llm-packet",
            str(smoke_run),
            "--output",
            str(triage_out),
            "--format",
            "json",
        ]
    )
    assert ret == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["report_version"] == LLM_TRIAGE_PACKET_REPORT_VERSION


def test_packet_json_schema_version(triage_out: Path, smoke_run: Path) -> None:
    build_llm_triage_packet(run_root=smoke_run, output=triage_out)
    packet = json.loads((triage_out / "llm_triage_packet.json").read_text(encoding="utf-8"))
    assert packet["schema_version"] == LLM_TRIAGE_PACKET_REPORT_VERSION
    assert packet["advisory"] != ""


def test_scope_flags(triage_out: Path, smoke_run: Path) -> None:
    result = build_llm_triage_packet(run_root=smoke_run, output=triage_out)
    scope = result.payload["scope"]
    assert scope["generator_quality_evidence_only"] is True
    assert scope["release_ready_dataset_artifact"] is False
    assert scope["manifest_v1_changed"] is False
    assert scope["llm_triage_included"] is True
    assert scope["network_required"] is False


def test_total_count_in_payload(triage_out: Path, smoke_run: Path) -> None:
    result = build_llm_triage_packet(run_root=smoke_run, output=triage_out, max_samples=100)
    assert result.payload["total_sample_count"] >= 1
    assert result.payload["selected_sample_count"] <= result.payload["total_sample_count"]
    assert result.payload["selected_sample_count"] <= 100


def test_apply_sample_warnings_links_findings() -> None:
    samples = [
        _TriageSample(
            batch_id="b1", sample_id="s1", template_id="t1",
            recipe_id="r1", asset_path="b1/s1.png", logical_text="text",
            warnings=(),
        ),
        _TriageSample(
            batch_id="b1", sample_id="s2", template_id="t1",
            recipe_id="r1", asset_path="b1/s2.png", logical_text="text",
            warnings=(),
        ),
    ]
    analysis_summary = {
        "warnings": [
            {"batch_id": "b1", "sample_id": "s1", "code": "near_blank_page"},
            {"batch_id": "b1", "sample_id": "s1", "code": "low_ink_density"},
        ],
    }
    result = _apply_sample_warnings(samples, analysis_summary)
    assert result[0].warnings == ("near_blank_page", "low_ink_density")
    assert result[1].warnings == ()


def test_apply_sample_warnings_no_analysis_returns_unchanged() -> None:
    samples = [
        _TriageSample(
            batch_id="b1", sample_id="s1", template_id="t1",
            recipe_id="r1", asset_path="b1/s1.png", logical_text="text",
            warnings=(),
        ),
    ]
    assert _apply_sample_warnings(samples, None) is samples
