from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from hocrsyngen.wet_run_artifact import (
    WetRunArtifactError,
    load_wet_run_payload,
    portable_path,
    read_batches,
    relative_to_run,
    resolve_run_path,
)


LLM_TRIAGE_PACKET_REPORT_VERSION = "llm_triage_packet_report.v1"
WET_ANALYSIS_REPORT_VERSION = "wet_analysis_report.v1"

DEFAULT_MAX_SAMPLES = 20

_ADVISORY_PREAMBLE = """\
> **Advisory notice:** This packet is a developer quality-review aid only.
> Findings and observations produced in response to this packet are **advisory
> only**. They are not pass/fail determinations, release-eligibility assessments,
> OCR or HTR utility claims, domain-match claims, or real-authorship statements.
> Generated samples are synthetic candidate outputs for internal developer review,
> not approved dataset artifacts."""

_REVIEW_QUESTIONS = [
    "Does the Hebrew text appear readable and visually coherent?",
    "Are there visible rendering artifacts (clipping, overlap, unusual spacing)?",
    "Does the page layout look plausible for a Hebrew manuscript page?",
    "Are there signs of extreme ink degradation that obscures the text?",
    "Does the text density seem consistent with the specified condition?",
    "Are there any samples that look significantly different from the others?",
]

_FORBIDDEN_CLAIM_REMINDER = """\
> **Important constraints for the reviewing LLM:**
>
> - Do **not** make release-readiness or release-eligibility statements.
> - Do **not** claim these samples represent real authorship, real identity,
>   or any specific person's handwriting.
> - Do **not** make OCR accuracy, HTR utility, or transcription-quality claims.
> - Do **not** make domain-match or production-readiness claims.
> - Do **not** infer demographic, medical, or psychological attributes from
>   any sample.
> - Frame all observations as advisory notes for developer review only."""

_SCOPE: dict[str, bool] = {
    "generator_quality_evidence_only": True,
    "release_ready_dataset_artifact": False,
    "manifest_v1_changed": False,
    "hocrgen_behavior_added": False,
    "human_review_sidecar_included": False,
    "llm_triage_included": True,
    "network_required": False,
}


@dataclass(frozen=True)
class WetTriageResult:
    run_root: Path
    output: Path
    prompt_path: Path
    packet_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class _TriageSample:
    batch_id: str
    sample_id: str
    template_id: str
    recipe_id: str
    asset_path: str
    logical_text: str
    warnings: tuple[str, ...]


def build_llm_triage_packet(
    *,
    run_root: Path,
    output: Path,
    max_samples: int = DEFAULT_MAX_SAMPLES,
) -> WetTriageResult:
    if max_samples < 1:
        raise ValueError(f"max_samples must be at least 1, got {max_samples}")
    run_root = run_root.resolve()
    output = output.resolve()
    if not run_root.is_dir():
        raise WetRunArtifactError(f"wet-test run directory does not exist: {run_root}")
    try:
        output.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(
            "LLM triage packet output path must be inside the wet-test run"
        ) from exc

    run_payload = load_wet_run_payload(run_root, require_passed=True)
    batches = read_batches(run_payload)

    all_samples = _collect_samples(run_root, batches, run_payload)
    selected = all_samples[:max_samples]

    analysis_summary = _load_analysis_summary(run_root)
    run_meta = _extract_run_meta(run_payload)

    output.mkdir(parents=True, exist_ok=True)

    packet_data = _build_packet_data(
        run_root=run_root,
        run_meta=run_meta,
        analysis_summary=analysis_summary,
        selected=selected,
        total_sample_count=len(all_samples),
        max_samples=max_samples,
    )
    packet_path = output / "llm_triage_packet.json"
    packet_path.write_text(
        json.dumps(packet_data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    prompt_path = output / "llm_triage_prompt.md"
    prompt_text = _build_prompt(run_meta, analysis_summary, selected, max_samples)
    prompt_path.write_text(prompt_text, encoding="utf-8")

    payload: dict[str, Any] = {
        "report_version": LLM_TRIAGE_PACKET_REPORT_VERSION,
        "run_path": ".",
        "output_path": relative_to_run(run_root, output),
        "prompt_path": relative_to_run(run_root, prompt_path),
        "packet_path": relative_to_run(run_root, packet_path),
        "max_samples": max_samples,
        "total_sample_count": len(all_samples),
        "selected_sample_count": len(selected),
        "analysis_summary_available": analysis_summary is not None,
        "run_meta": run_meta,
        "scope": _SCOPE,
    }
    return WetTriageResult(
        run_root=run_root,
        output=output,
        prompt_path=prompt_path,
        packet_path=packet_path,
        payload=payload,
    )


def _collect_samples(
    run_root: Path,
    batches: list[Any],
    run_payload: dict[str, Any],
) -> list[_TriageSample]:
    samples: list[_TriageSample] = []
    for batch in batches:
        resolved = batch.resolved(run_root)
        manifest = json.loads(resolved.manifest_path_abs.read_text(encoding="utf-8"))
        batch_path = PurePosixPath(batch.batch_path)
        for raw_sample in manifest.get("samples", []):
            if not isinstance(raw_sample, dict):
                continue
            provenance = raw_sample.get("provenance") or {}
            controls = raw_sample.get("controls") or {}
            if not isinstance(provenance, dict):
                provenance = {}
            if not isinstance(controls, dict):
                controls = {}
            text_field = raw_sample.get("text") or {}
            logical_text = ""
            if isinstance(text_field, dict):
                logical_text = str(text_field.get("logical_order", ""))
            sample_id = str(raw_sample.get("sample_id", ""))
            template_id = str(provenance.get("template_id", ""))
            recipe_id = str(provenance.get("recipe_id", raw_sample.get("recipe_id", "")))
            for raw_page in raw_sample.get("pages", []):
                if not isinstance(raw_page, dict):
                    continue
                try:
                    run_asset_path = batch_path / portable_path(raw_page.get("asset_path"))
                    resolve_run_path(run_root, run_asset_path.as_posix())
                except (ValueError, WetRunArtifactError):
                    continue
                samples.append(
                    _TriageSample(
                        batch_id=batch.batch_id,
                        sample_id=sample_id,
                        template_id=template_id,
                        recipe_id=recipe_id,
                        asset_path=run_asset_path.as_posix(),
                        logical_text=logical_text,
                        warnings=(),
                    )
                )
                break  # one representative page per sample
    samples.sort(key=lambda s: (s.batch_id, s.sample_id))
    return samples


def _load_analysis_summary(run_root: Path) -> dict[str, Any] | None:
    report_path = run_root / "reports" / "wet_analysis_report.json"
    if not report_path.is_file():
        return None
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("report_version") != WET_ANALYSIS_REPORT_VERSION:
        return None
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return None
    hard_blockers = data.get("hard_blockers")
    warnings_list = data.get("warnings")
    return {
        "sample_count": summary.get("sample_count"),
        "page_count": summary.get("page_count"),
        "warning_count": summary.get("warning_count"),
        "hard_blocker_count": summary.get("hard_blocker_count"),
        "hard_blockers": hard_blockers if isinstance(hard_blockers, list) else [],
        "warnings": warnings_list if isinstance(warnings_list, list) else [],
    }


def _extract_run_meta(run_payload: dict[str, Any]) -> dict[str, Any]:
    config = run_payload.get("config") or {}
    validation = run_payload.get("validation") or {}
    package = run_payload.get("package") or {}
    if not isinstance(config, dict):
        config = {}
    if not isinstance(validation, dict):
        validation = {}
    if not isinstance(package, dict):
        package = {}
    batch_count = (
        config.get("primary_count", 0) + config.get("supplemental_count", 0)
        if isinstance(config.get("primary_count"), int)
        else config.get("total_count")
    )
    return {
        "generator_version": package.get("version"),
        "profile": run_payload.get("profile"),
        "seed": config.get("seed"),
        "batch_count": batch_count,
        "sample_count": validation.get("sample_count"),
        "status": run_payload.get("status"),
    }


def _build_packet_data(
    *,
    run_root: Path,
    run_meta: dict[str, Any],
    analysis_summary: dict[str, Any] | None,
    selected: list[_TriageSample],
    total_sample_count: int,
    max_samples: int,
) -> dict[str, Any]:
    return {
        "schema_version": LLM_TRIAGE_PACKET_REPORT_VERSION,
        "advisory": (
            "Findings are advisory only. Not pass/fail, release-eligibility, "
            "OCR utility, or domain-match claims."
        ),
        "run_meta": run_meta,
        "analysis_summary": analysis_summary,
        "selection": {
            "total_sample_count": total_sample_count,
            "selected_count": len(selected),
            "max_samples": max_samples,
        },
        "samples": [
            {
                "batch_id": s.batch_id,
                "sample_id": s.sample_id,
                "template_id": s.template_id,
                "recipe_id": s.recipe_id,
                "asset_path": s.asset_path,
                "logical_text": s.logical_text,
                "warnings": list(s.warnings),
            }
            for s in selected
        ],
    }


def _build_prompt(
    run_meta: dict[str, Any],
    analysis_summary: dict[str, Any] | None,
    selected: list[_TriageSample],
    max_samples: int,
) -> str:
    parts: list[str] = []

    parts.append("# Developer Quality-Review Aid — LLM Triage Packet\n")
    parts.append(_ADVISORY_PREAMBLE)
    parts.append("")

    parts.append("## Run Metadata\n")
    parts.append(f"- Generator version: `{run_meta.get('generator_version', 'unknown')}`")
    parts.append(f"- Profile: `{run_meta.get('profile', 'unknown')}`")
    parts.append(f"- Seed: `{run_meta.get('seed', 'unknown')}`")
    parts.append(f"- Batch count: `{run_meta.get('batch_count', 'unknown')}`")
    parts.append(f"- Total sample count: `{run_meta.get('sample_count', 'unknown')}`")
    parts.append("")

    parts.append("## Warning Summary\n")
    if analysis_summary is not None:
        parts.append(
            f"- Samples analysed: `{analysis_summary.get('sample_count', 'n/a')}`"
        )
        parts.append(
            f"- Pages analysed: `{analysis_summary.get('page_count', 'n/a')}`"
        )
        parts.append(
            f"- Warnings: `{analysis_summary.get('warning_count', 0)}`"
        )
        parts.append(
            f"- Hard blockers: `{analysis_summary.get('hard_blocker_count', 0)}`"
        )
        hard_blockers = analysis_summary.get("hard_blockers", [])
        if hard_blockers:
            parts.append("")
            parts.append("### Hard Blockers\n")
            for b in hard_blockers[:10]:
                if isinstance(b, dict):
                    parts.append(
                        f"- [{b.get('severity', '?')}] `{b.get('code', '?')}`: "
                        f"{b.get('message', '')}"
                    )
        warnings_list = analysis_summary.get("warnings", [])
        if warnings_list:
            parts.append("")
            parts.append("### Warnings (first 10)\n")
            for w in warnings_list[:10]:
                if isinstance(w, dict):
                    parts.append(
                        f"- [{w.get('severity', '?')}] `{w.get('code', '?')}`: "
                        f"{w.get('message', '')}"
                    )
    else:
        parts.append(
            "_Warning analysis report not found. Run `hocrsyngen wet-analyze` "
            "to generate it._"
        )
    parts.append("")

    parts.append(
        f"## Sample Review ({len(selected)} of "
        f"{run_meta.get('sample_count', '?')} total, "
        f"capped at {max_samples})\n"
    )
    for i, s in enumerate(selected, 1):
        parts.append(f"### Sample {i}: `{s.sample_id}`\n")
        parts.append(f"- Batch: `{s.batch_id}`")
        parts.append(f"- Template: `{s.template_id}`")
        parts.append(f"- Recipe: `{s.recipe_id}`")
        parts.append(f"- Asset path: `{s.asset_path}`")
        parts.append(f"- Hebrew text (logical order): `{s.logical_text}`")
        if s.warnings:
            parts.append(f"- Warnings: {', '.join(s.warnings)}")
        parts.append("")

    parts.append("## Suggested Review Questions\n")
    parts.append(
        "Please review the samples above and share observations on the following "
        "questions. Frame all responses as advisory notes only.\n"
    )
    for q in _REVIEW_QUESTIONS:
        parts.append(f"1. {q}")
    parts.append("")

    parts.append("## Constraints\n")
    parts.append(_FORBIDDEN_CLAIM_REMINDER)
    parts.append("")

    return "\n".join(parts)
