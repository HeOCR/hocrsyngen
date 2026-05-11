from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from hocrsyngen.validation import validate_batch
from hocrsyngen.wet_run_artifact import (
    WetRunBatch,
    load_wet_run_payload,
    portable_path,
    read_batches,
    relative_to_run,
    require_passed_run,
    resolve_run_path,
    validated_manifest_path,
)


WET_REVIEW_TEMPLATE_REPORT_VERSION = "wet_review_template_report.v1"
WET_REVIEW_VALIDATION_REPORT_VERSION = "wet_review_validation_report.v1"

DECISION_STATES: tuple[str, ...] = ("pass", "hold", "reject")
SEVERITY_LEVELS: tuple[str, ...] = ("P0", "P1", "P2", "info")
REASON_CODES: tuple[str, ...] = (
    "invalid_manifest",
    "unsafe_asset_path",
    "missing_asset",
    "hash_mismatch",
    "blank_or_near_blank_page",
    "hebrew_not_readable",
    "text_clipped",
    "text_overlap",
    "layout_implausible",
    "degradation_obscures_text",
    "metadata_image_mismatch",
    "catalog_join_problem",
    "excessive_repetition",
    "style_condition_not_distinct",
    "forbidden_claim_risk",
    "reviewer_uncertain",
)
REVIEW_FIELDS: tuple[str, ...] = (
    "batch_id",
    "sample_id",
    "page_id",
    "template_id",
    "recipe_id",
    "persona",
    "condition",
    "degradation",
    "font_id",
    "asset_path",
    "reviewer",
    "decision",
    "severity",
    "reason_codes",
    "notes",
    "regression_fixture_candidate",
)
REVIEW_FORMATS: tuple[str, ...] = ("csv", "jsonl")


@dataclass(frozen=True)
class WetReviewTemplateResult:
    run_root: Path
    output: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class WetReviewValidationResult:
    run_root: Path
    review_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class _ReviewablePage:
    batch_id: str
    sample_id: str
    page_id: str
    template_id: str
    recipe_id: str
    persona: str
    condition: str
    degradation: str
    font_id: str
    asset_path: str


@dataclass(frozen=True)
class _ParsedRow:
    line: int
    fields: Mapping[str, str]
    raw_reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class _ReviewError:
    code: str
    message: str
    row: int | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.row is not None:
            payload["row"] = self.row
        if self.details:
            payload["details"] = dict(self.details)
        return payload


def build_wet_review_template(
    *,
    run_root: Path,
    output: Path,
    review_format: str,
) -> WetReviewTemplateResult:
    if review_format not in REVIEW_FORMATS:
        raise ValueError(f"unsupported review template format: {review_format}")
    run_root = run_root.resolve()
    output = output.resolve()
    if not run_root.is_dir():
        raise ValueError(f"wet-test run directory does not exist: {run_root}")
    try:
        output.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(
            "review template output path must be inside the wet-test run"
        ) from exc
    if output.exists():
        raise ValueError(
            f"review template output path already exists: {output}"
        )

    pages = _reviewable_pages(run_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    if review_format == "csv":
        _write_csv_template(output, pages)
    else:
        _write_jsonl_template(output, pages)

    payload: dict[str, Any] = {
        "report_version": WET_REVIEW_TEMPLATE_REPORT_VERSION,
        "run_path": ".",
        "review_path": relative_to_run(run_root, output),
        "review_format": review_format,
        "row_count": len(pages),
        "sample_count": len({(page.batch_id, page.sample_id) for page in pages}),
        "page_count": len(pages),
        "decision_states": list(DECISION_STATES),
        "severity_levels": list(SEVERITY_LEVELS),
        "reason_codes": list(REASON_CODES),
        "review_fields": list(REVIEW_FIELDS),
        "scope": _SCOPE,
    }
    return WetReviewTemplateResult(run_root=run_root, output=output, payload=payload)


def validate_wet_review(
    *,
    run_root: Path,
    review_path: Path,
) -> WetReviewValidationResult:
    run_root = run_root.resolve()
    review_path = review_path.resolve()
    if not run_root.is_dir():
        raise ValueError(f"wet-test run directory does not exist: {run_root}")
    if not review_path.is_file():
        raise ValueError(f"review file does not exist: {review_path}")
    try:
        review_path.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(
            "review file must be inside the wet-test run"
        ) from exc

    review_format = _detect_review_format(review_path)
    pages = _reviewable_pages(run_root)
    expected_keys = {
        (page.batch_id, page.sample_id, page.page_id) for page in pages
    }

    rows, parse_errors = _read_review_rows(review_path, review_format)
    errors: list[_ReviewError] = list(parse_errors)
    seen_keys: set[tuple[str, str, str]] = set()
    decision_counts: dict[str, int] = {state: 0 for state in DECISION_STATES}
    severity_counts: dict[str, int] = {level: 0 for level in SEVERITY_LEVELS}
    reason_code_counts: dict[str, int] = {code: 0 for code in REASON_CODES}
    regression_fixture_count = 0
    reviewed_count = 0
    unreviewed_count = 0

    for row in rows:
        fields = row.fields
        batch_id = _get_str(fields, "batch_id")
        sample_id = _get_str(fields, "sample_id")
        page_id = _get_str(fields, "page_id")
        decision = _get_str(fields, "decision")
        severity = _get_str(fields, "severity")
        notes = _get_str(fields, "notes")
        regression_text = _get_str(fields, "regression_fixture_candidate")
        reviewer = _get_str(fields, "reviewer")
        reason_codes = row.raw_reason_codes

        key = (batch_id, sample_id, page_id)
        if key in expected_keys:
            if key in seen_keys:
                errors.append(
                    _ReviewError(
                        code="duplicate_page_row",
                        message="Worksheet contains duplicate rows for the same page.",
                        row=row.line,
                        details={
                            "batch_id": batch_id,
                            "sample_id": sample_id,
                            "page_id": page_id,
                        },
                    )
                )
            seen_keys.add(key)
        else:
            errors.append(
                _ReviewError(
                    code="unknown_page_id",
                    message="Worksheet row does not match any sample/page in the wet-test run.",
                    row=row.line,
                    details={
                        "batch_id": batch_id,
                        "sample_id": sample_id,
                        "page_id": page_id,
                    },
                )
            )

        if decision and decision not in DECISION_STATES:
            errors.append(
                _ReviewError(
                    code="unknown_decision",
                    message=(
                        "Worksheet decision is not one of pass/hold/reject."
                    ),
                    row=row.line,
                    details={"value": decision},
                )
            )
        elif decision in DECISION_STATES:
            decision_counts[decision] += 1
            reviewed_count += 1
            if not reviewer:
                errors.append(
                    _ReviewError(
                        code="missing_reviewer",
                        message=(
                            "Reviewed row must record a reviewer identifier or initials."
                        ),
                        row=row.line,
                        details={"decision": decision},
                    )
                )
        else:
            unreviewed_count += 1
            if reviewer:
                errors.append(
                    _ReviewError(
                        code="reviewer_without_decision",
                        message=(
                            "Reviewer initials were recorded but decision is empty."
                        ),
                        row=row.line,
                        details={"reviewer": reviewer},
                    )
                )

        if severity and severity not in SEVERITY_LEVELS:
            errors.append(
                _ReviewError(
                    code="unknown_severity",
                    message="Worksheet severity is not one of P0/P1/P2/info.",
                    row=row.line,
                    details={"value": severity},
                )
            )
        elif severity:
            severity_counts[severity] += 1

        for code in reason_codes:
            if code not in REASON_CODES:
                errors.append(
                    _ReviewError(
                        code="unknown_reason_code",
                        message="Worksheet reason code is not in the documented set.",
                        row=row.line,
                        details={"value": code},
                    )
                )
            else:
                reason_code_counts[code] += 1

        if regression_text:
            normalized = regression_text.lower()
            if normalized in ("true", "yes", "1"):
                regression_fixture_count += 1
            elif normalized not in ("false", "no", "0"):
                errors.append(
                    _ReviewError(
                        code="invalid_regression_fixture_value",
                        message=(
                            "regression_fixture_candidate must be empty, true, "
                            "false, yes, no, 1, or 0."
                        ),
                        row=row.line,
                        details={"value": regression_text},
                    )
                )

        if decision in ("hold", "reject"):
            if not severity:
                errors.append(
                    _ReviewError(
                        code="missing_severity",
                        message=(
                            "Hold and reject rows must record a severity level."
                        ),
                        row=row.line,
                        details={"decision": decision},
                    )
                )
            if not reason_codes:
                errors.append(
                    _ReviewError(
                        code="missing_reason_codes",
                        message=(
                            "Hold and reject rows must record at least one reason code."
                        ),
                        row=row.line,
                        details={"decision": decision},
                    )
                )

        # `notes` is free-form; we don't validate its contents but suppress
        # the unused-binding lint by referencing it.
        del notes

    for batch_id, sample_id, page_id in sorted(expected_keys - seen_keys):
        errors.append(
            _ReviewError(
                code="missing_page_row",
                message="Worksheet is missing a row for an expected sample/page.",
                details={
                    "batch_id": batch_id,
                    "sample_id": sample_id,
                    "page_id": page_id,
                },
            )
        )

    valid = not errors
    status = "passed" if valid else "blocked"
    payload: dict[str, Any] = {
        "report_version": WET_REVIEW_VALIDATION_REPORT_VERSION,
        "run_path": ".",
        "review_path": relative_to_run(run_root, review_path),
        "review_format": review_format,
        "valid": valid,
        "status": status,
        "summary": {
            "row_count": len(rows),
            "expected_page_count": len(expected_keys),
            "reviewed_page_count": reviewed_count,
            "unreviewed_page_count": unreviewed_count,
            "regression_fixture_candidate_count": regression_fixture_count,
            "error_count": len(errors),
        },
        "decision_counts": decision_counts,
        "severity_counts": severity_counts,
        "reason_code_counts": reason_code_counts,
        "errors": [error.to_payload() for error in sorted(errors, key=_error_sort_key)],
        "scope": _SCOPE,
    }
    return WetReviewValidationResult(
        run_root=run_root,
        review_path=review_path,
        payload=payload,
    )


_SCOPE: dict[str, bool] = {
    "generator_quality_evidence_only": True,
    "release_ready_dataset_artifact": False,
    "manifest_v1_changed": False,
    "hocrgen_behavior_added": False,
    "human_review_sidecar_included": True,
    "llm_triage_included": False,
    "network_required": False,
}


def _reviewable_pages(run_root: Path) -> list[_ReviewablePage]:
    run_payload = load_wet_run_payload(run_root)
    require_passed_run(run_payload)
    batches = read_batches(run_payload)
    pages: list[_ReviewablePage] = []
    for batch in batches:
        batch_dir = resolve_run_path(run_root, batch.batch_path)
        validate_batch(batch_dir)
        manifest_path = resolve_run_path(run_root, validated_manifest_path(batch))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages.extend(_pages_for_batch(run_root, batch, manifest))
    pages.sort(
        key=lambda page: (
            page.batch_id,
            page.sample_id,
            page.page_id,
            page.asset_path,
        )
    )
    return pages


def _pages_for_batch(
    run_root: Path,
    batch: WetRunBatch,
    manifest: dict[str, Any],
) -> list[_ReviewablePage]:
    samples = manifest.get("samples", [])
    if not isinstance(samples, list):
        raise ValueError(f"manifest samples must be a list: {batch.manifest_path}")
    batch_path = PurePosixPath(batch.batch_path)
    pages: list[_ReviewablePage] = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError(
                f"manifest sample must be an object: {batch.manifest_path}"
            )
        provenance = sample.get("provenance") or {}
        controls = sample.get("controls") or {}
        sample_pages = sample.get("pages", [])
        if not isinstance(provenance, dict) or not isinstance(controls, dict):
            raise ValueError(
                f"manifest sample metadata is invalid: {batch.manifest_path}"
            )
        if not isinstance(sample_pages, list):
            raise ValueError(
                f"manifest sample pages must be a list: {batch.manifest_path}"
            )
        sample_id = str(sample.get("sample_id", ""))
        template_id = str(provenance.get("template_id", ""))
        recipe_id = str(provenance.get("recipe_id", sample.get("recipe_id", "")))
        persona = controls.get("persona")
        condition = controls.get("condition")
        degradation = str(provenance.get("degradation_preset", ""))
        font_id = str(provenance.get("font_id", ""))
        for page in sample_pages:
            if not isinstance(page, dict):
                raise ValueError(
                    f"manifest page must be an object: {batch.manifest_path}"
                )
            portable_asset = portable_path(page.get("asset_path"))
            if portable_asset is None:
                raise ValueError(
                    "manifest asset path must be relative and portable: "
                    f"{page.get('asset_path')!r}"
                )
            run_asset_path = batch_path / portable_asset
            # Verify the asset resolves under the run root before recording it.
            resolve_run_path(run_root, run_asset_path.as_posix())
            pages.append(
                _ReviewablePage(
                    batch_id=batch.batch_id,
                    sample_id=sample_id,
                    page_id=str(page.get("page_id", "")),
                    template_id=template_id,
                    recipe_id=recipe_id,
                    persona=str(persona) if persona is not None else "",
                    condition=str(condition) if condition is not None else "",
                    degradation=degradation,
                    font_id=font_id,
                    asset_path=run_asset_path.as_posix(),
                )
            )
    return pages


def _write_csv_template(output: Path, pages: list[_ReviewablePage]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(REVIEW_FIELDS),
        lineterminator="\n",
    )
    writer.writeheader()
    for page in pages:
        writer.writerow(_csv_template_row(page))
    output.write_text(buffer.getvalue(), encoding="utf-8")


def _write_jsonl_template(output: Path, pages: list[_ReviewablePage]) -> None:
    lines = [
        json.dumps(_jsonl_template_row(page), ensure_ascii=False, sort_keys=True)
        for page in pages
    ]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _csv_template_row(page: _ReviewablePage) -> dict[str, str]:
    return {
        "batch_id": page.batch_id,
        "sample_id": page.sample_id,
        "page_id": page.page_id,
        "template_id": page.template_id,
        "recipe_id": page.recipe_id,
        "persona": page.persona,
        "condition": page.condition,
        "degradation": page.degradation,
        "font_id": page.font_id,
        "asset_path": page.asset_path,
        "reviewer": "",
        "decision": "",
        "severity": "",
        "reason_codes": "",
        "notes": "",
        "regression_fixture_candidate": "",
    }


def _jsonl_template_row(page: _ReviewablePage) -> dict[str, object]:
    row = _csv_template_row(page)
    # JSON Lines worksheets carry reason_codes as a real JSON array.
    row["reason_codes"] = []  # type: ignore[assignment]
    return row


def _detect_review_format(review_path: Path) -> str:
    suffix = review_path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in (".jsonl", ".ndjson"):
        return "jsonl"
    raise ValueError(
        "review file must use a .csv, .jsonl, or .ndjson extension: "
        f"{review_path.name}"
    )


def _read_review_rows(
    review_path: Path,
    review_format: str,
) -> tuple[list[_ParsedRow], list[_ReviewError]]:
    text = review_path.read_text(encoding="utf-8")
    if review_format == "csv":
        return _read_csv_rows(text)
    return _read_jsonl_rows(text)


def _read_csv_rows(
    text: str,
) -> tuple[list[_ParsedRow], list[_ReviewError]]:
    errors: list[_ReviewError] = []
    rows: list[_ParsedRow] = []
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    missing_fields = [field for field in REVIEW_FIELDS if field not in fieldnames]
    if missing_fields:
        errors.append(
            _ReviewError(
                code="missing_csv_field",
                message="Worksheet CSV header is missing required columns.",
                details={"fields": sorted(missing_fields)},
            )
        )
        return rows, errors
    for line, raw in enumerate(reader, start=2):
        fields = {field: (raw.get(field) or "").strip() for field in REVIEW_FIELDS}
        reason_codes = _split_csv_reason_codes(fields.get("reason_codes", ""))
        rows.append(
            _ParsedRow(
                line=line,
                fields=fields,
                raw_reason_codes=reason_codes,
            )
        )
    return rows, errors


def _read_jsonl_rows(
    text: str,
) -> tuple[list[_ParsedRow], list[_ReviewError]]:
    errors: list[_ReviewError] = []
    rows: list[_ParsedRow] = []
    for line, source in enumerate(text.splitlines(), start=1):
        if not source.strip():
            continue
        try:
            entry = json.loads(source)
        except json.JSONDecodeError as exc:
            errors.append(
                _ReviewError(
                    code="invalid_jsonl_row",
                    message="Worksheet JSONL row is not valid JSON.",
                    row=line,
                    details={"detail": exc.msg},
                )
            )
            continue
        if not isinstance(entry, dict):
            errors.append(
                _ReviewError(
                    code="invalid_jsonl_row",
                    message="Worksheet JSONL row must be a JSON object.",
                    row=line,
                )
            )
            continue
        fields: dict[str, str] = {}
        reason_codes: tuple[str, ...] = ()
        for field in REVIEW_FIELDS:
            value = entry.get(field, "")
            if field == "reason_codes":
                reason_codes = _coerce_jsonl_reason_codes(value)
                fields[field] = ",".join(reason_codes)
                continue
            if value is None:
                fields[field] = ""
            elif isinstance(value, bool):
                fields[field] = "true" if value else "false"
            else:
                fields[field] = str(value).strip()
        rows.append(
            _ParsedRow(
                line=line,
                fields=fields,
                raw_reason_codes=reason_codes,
            )
        )
    return rows, errors


def _split_csv_reason_codes(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _coerce_jsonl_reason_codes(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return _split_csv_reason_codes(value)
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),)


def _get_str(fields: Mapping[str, str], key: str) -> str:
    return (fields.get(key) or "").strip()


def _error_sort_key(error: _ReviewError) -> tuple[str, int, str]:
    return (error.code, error.row if error.row is not None else 0, error.message)
