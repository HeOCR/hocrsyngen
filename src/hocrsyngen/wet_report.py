from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hocrsyngen.wet_analysis import WET_ANALYSIS_REPORT_VERSION
from hocrsyngen.wet_review import validate_wet_review
from hocrsyngen.wet_run_artifact import (
    WetRunArtifactError,
    load_wet_run_payload,
)


WET_REPORT_VERSION = "wet_report.v1"

_NON_RELEASE_STATEMENT = (
    "This report is generator-quality evidence only. It is not a release "
    "eligibility determination, OCR/HTR utility claim, or domain-match "
    "assessment. Generated batches remain candidate synthetic inputs until "
    "downstream hocrgen governance admits them."
)

_SCOPE: dict[str, bool] = {
    "generator_quality_evidence_only": True,
    "release_ready_dataset_artifact": False,
    "manifest_v1_changed": False,
    "hocrgen_behavior_added": False,
    "human_review_sidecar_included": False,
    "llm_triage_included": False,
    "network_required": False,
}


@dataclass(frozen=True)
class WetReportResult:
    run_root: Path
    payload: dict[str, Any]
    has_hard_blockers: bool


def build_wet_report(
    *,
    run_root: Path,
    review_path: Path | None = None,
    llm_packet_path: Path | None = None,
) -> WetReportResult:
    run_root = run_root.resolve()
    if not run_root.is_dir():
        raise WetRunArtifactError(f"wet-test run directory does not exist: {run_root}")

    run_payload = load_wet_run_payload(run_root)
    run_meta = _extract_run_meta(run_payload)
    analysis_summary = _load_analysis_summary(run_root)
    review_summary = _load_review_summary(run_root, review_path)
    llm_triage_summary = _load_llm_triage_summary(llm_packet_path)
    coverage_matrix = _load_coverage_matrix(run_root)

    has_hard_blockers = bool(
        analysis_summary is not None
        and (analysis_summary.get("hard_blocker_count") or 0) > 0
    )

    scope = dict(_SCOPE)
    scope["human_review_sidecar_included"] = review_path is not None
    scope["llm_triage_included"] = llm_packet_path is not None

    payload: dict[str, Any] = {
        "report_version": WET_REPORT_VERSION,
        "run_path": ".",
        "run_meta": run_meta,
        "analysis_summary": analysis_summary,
        "review_summary": review_summary,
        "llm_triage_summary": llm_triage_summary,
        "non_release_statement": _NON_RELEASE_STATEMENT,
        "scope": scope,
    }
    if coverage_matrix is not None:
        payload["coverage_matrix"] = coverage_matrix

    return WetReportResult(
        run_root=run_root,
        payload=payload,
        has_hard_blockers=has_hard_blockers,
    )


def format_wet_report_text(payload: dict[str, Any]) -> str:
    run_meta = payload.get("run_meta") or {}
    analysis = payload.get("analysis_summary")
    review = payload.get("review_summary") or {}
    llm_triage = payload.get("llm_triage_summary") or {}

    profile = run_meta.get("profile", "?")
    seed = run_meta.get("seed", "?")
    samples = run_meta.get("sample_count", "?")

    lines = [f"wet-report: profile={profile} seed={seed} samples={samples}"]

    if analysis is not None:
        warnings = analysis.get("warning_count", 0)
        blockers = analysis.get("hard_blocker_count", 0)
        lines.append(f"analysis: warnings={warnings} hard_blockers={blockers}")
    else:
        lines.append("analysis: not provided")

    review_status = review.get("status", "not_provided")
    if review_status == "not_provided":
        lines.append("review: not provided")
    elif review_status == "error":
        lines.append(f"review: error ({review.get('error', '?')})")
    else:
        rev_count = review.get("reviewed_page_count")
        unreviewed = review.get("unreviewed_page_count", 0)
        total = (
            rev_count + unreviewed
            if isinstance(rev_count, int) and isinstance(unreviewed, int)
            else "?"
        )
        dc = review.get("decision_counts") or {}
        p = dc.get("pass", 0)
        h = dc.get("hold", 0)
        r = dc.get("reject", 0)
        lines.append(
            f"review: reviewed={rev_count}/{total} pass={p} hold={h} reject={r}"
        )

    llm_status = llm_triage.get("status", "not_provided")
    if llm_status == "not_provided":
        lines.append("llm_triage: not provided")
    elif llm_status == "error":
        lines.append(f"llm_triage: error ({llm_triage.get('error', '?')})")
    else:
        sel = llm_triage.get("selected_sample_count", "?")
        lines.append(f"llm_triage: samples={sel} [advisory]")

    has_blockers = bool(
        analysis is not None and (analysis.get("hard_blocker_count") or 0) > 0
    )
    if has_blockers:
        n = analysis.get("hard_blocker_count", 0) if analysis else 0
        lines.append(f"status: BLOCKED ({n} hard blockers)")
    else:
        lines.append("status: OK")

    return "\n".join(lines)


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
    return {
        "generator_version": package.get("version"),
        "profile": run_payload.get("profile"),
        "seed": config.get("seed"),
        "batch_count": config.get("total_count"),
        "sample_count": validation.get("sample_count"),
        "status": run_payload.get("status"),
    }


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


def _load_review_summary(
    run_root: Path,
    review_path: Path | None,
) -> dict[str, Any]:
    if review_path is None:
        return {"status": "not_provided"}
    review_path = review_path.resolve()
    try:
        result = validate_wet_review(run_root=run_root, review_path=review_path)
    except (WetRunArtifactError, ValueError) as exc:
        return {"status": "error", "error": str(exc)}
    summary = result.payload.get("summary") or {}
    return {
        "status": "provided",
        "valid": result.payload.get("valid"),
        "reviewed_page_count": summary.get("reviewed_page_count"),
        "unreviewed_page_count": summary.get("unreviewed_page_count"),
        "decision_counts": result.payload.get("decision_counts"),
        "severity_counts": result.payload.get("severity_counts"),
        "error_count": summary.get("error_count"),
    }


def _load_llm_triage_summary(llm_packet_path: Path | None) -> dict[str, Any]:
    if llm_packet_path is None:
        return {"status": "not_provided"}
    llm_packet_path = llm_packet_path.resolve()
    try:
        data = json.loads(llm_packet_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "error", "error": str(exc)}
    if not isinstance(data, dict):
        return {"status": "error", "error": "LLM triage packet is not a JSON object"}
    selection = data.get("selection") or {}
    if not isinstance(selection, dict):
        selection = {}
    return {
        "status": "provided",
        "advisory": True,
        "selected_sample_count": selection.get("selected_count"),
        "total_sample_count": selection.get("total_sample_count"),
        "advisory_text": data.get("advisory"),
    }


def _load_coverage_matrix(run_root: Path) -> list[str] | None:
    catalog_path = run_root / "reports" / "template_catalog_v2.json"
    if not catalog_path.is_file():
        return None
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    templates = data.get("templates")
    if not isinstance(templates, list):
        return None
    return sorted({
        str(t.get("template_id", ""))
        for t in templates
        if isinstance(t, dict) and t.get("template_id")
    })
