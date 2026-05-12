from __future__ import annotations

import json
from pathlib import Path

import pytest

from hocrsyngen.cli import main
from hocrsyngen.wet_triage import LLM_TRIAGE_PACKET_REPORT_VERSION, build_llm_triage_packet


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
                "--format",
                "json",
            ]
        )
        == 0
    )
    return run_dir


def test_packet_is_deterministic(smoke_run: Path) -> None:
    out1 = smoke_run / "triage-det-1"
    out2 = smoke_run / "triage-det-2"
    build_llm_triage_packet(run_root=smoke_run, output=out1, max_samples=5)
    build_llm_triage_packet(run_root=smoke_run, output=out2, max_samples=5)
    assert (out1 / "llm_triage_prompt.md").read_text(encoding="utf-8") == (
        out2 / "llm_triage_prompt.md"
    ).read_text(encoding="utf-8")
    pkt1 = json.loads((out1 / "llm_triage_packet.json").read_text(encoding="utf-8"))
    pkt2 = json.loads((out2 / "llm_triage_packet.json").read_text(encoding="utf-8"))
    assert pkt1 == pkt2


def test_max_samples_respected(smoke_run: Path) -> None:
    out = smoke_run / "triage-max1"
    result = build_llm_triage_packet(run_root=smoke_run, output=out, max_samples=1)
    assert result.payload["selected_sample_count"] <= 1
    packet = json.loads((out / "llm_triage_packet.json").read_text(encoding="utf-8"))
    assert len(packet["samples"]) <= 1


def test_prompt_does_not_contain_forbidden_strings(smoke_run: Path) -> None:
    out = smoke_run / "triage-forbidden"
    build_llm_triage_packet(run_root=smoke_run, output=out, max_samples=5)
    prompt = (out / "llm_triage_prompt.md").read_text(encoding="utf-8")
    for bad_string in _FORBIDDEN_STRINGS:
        assert bad_string not in prompt, (
            f"prompt must not contain {bad_string!r}"
        )


def test_prompt_contains_advisory_disclaimer(smoke_run: Path) -> None:
    out = smoke_run / "triage-advisory"
    build_llm_triage_packet(run_root=smoke_run, output=out, max_samples=3)
    prompt = (out / "llm_triage_prompt.md").read_text(encoding="utf-8")
    assert "advisory" in prompt.lower()
    assert "not pass/fail" in prompt.lower() or "not pass" in prompt.lower()


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


def test_json_format_report_schema_version(
    smoke_run: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = smoke_run / "triage-json-report"
    ret = main(
        [
            "wet-llm-packet",
            str(smoke_run),
            "--output",
            str(out),
            "--format",
            "json",
        ]
    )
    assert ret == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["report_version"] == LLM_TRIAGE_PACKET_REPORT_VERSION
    assert report["report_version"] == "llm_triage_packet_report.v1"


def test_packet_json_schema_version(smoke_run: Path) -> None:
    out = smoke_run / "triage-schema-check"
    build_llm_triage_packet(run_root=smoke_run, output=out)
    packet = json.loads((out / "llm_triage_packet.json").read_text(encoding="utf-8"))
    assert packet["schema_version"] == LLM_TRIAGE_PACKET_REPORT_VERSION
    assert packet["advisory"] != ""


def test_scope_flags(smoke_run: Path) -> None:
    out = smoke_run / "triage-scope"
    result = build_llm_triage_packet(run_root=smoke_run, output=out)
    scope = result.payload["scope"]
    assert scope["generator_quality_evidence_only"] is True
    assert scope["release_ready_dataset_artifact"] is False
    assert scope["manifest_v1_changed"] is False
    assert scope["llm_triage_included"] is True
    assert scope["network_required"] is False


def test_total_count_in_payload(smoke_run: Path) -> None:
    out = smoke_run / "triage-count"
    result = build_llm_triage_packet(run_root=smoke_run, output=out, max_samples=100)
    assert result.payload["total_sample_count"] >= 1
    assert result.payload["selected_sample_count"] <= result.payload["total_sample_count"]
    assert result.payload["selected_sample_count"] <= 100
