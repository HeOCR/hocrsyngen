from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


WET_REVIEW_TEMPLATE_REPORT_VERSION = "wet_review_template.v1"
WET_REVIEW_VALIDATION_REPORT_VERSION = "wet_review_validation.v1"
WET_TEST_RUN_FILENAME = "wet_test_run.json"

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
    "run_id",
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
REASON_CODE_SEPARATOR = "|"


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
    run_id: str
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
class _ReviewBatch:
    batch_id: str
    batch_path: str
    manifest_path: str


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
        "review_path": _relative_to_run(run_root, output),
        "review_format": review_format,
        "row_count": len(pages),
        "sample_count": len({(page.batch_id, page.sample_id) for page in pages}),
        "page_count": len(pages),
        "decision_states": list(DECISION_STATES),
        "severity_levels": list(SEVERITY_LEVELS),
        "reason_codes": list(REASON_CODES),
        "review_fields": list(REVIEW_FIELDS),
        "scope": {
            "generator_quality_evidence_only": True,
            "release_ready_dataset_artifact": False,
            "manifest_v1_changed": False,
            "hocrgen_behavior_added": False,
            "human_review_sidecar_included": True,
            "llm_triage_included": False,
            "network_required": False,
        },
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

    review_format = _detect_review_format(review_path)
    pages = _reviewable_pages(run_root)
    expected_keys = {
        (page.batch_id, page.sample_id, page.page_id) for page in pages
    }
    expected_run_ids = {page.run_id for page in pages}
    expected_run_id = pages[0].run_id if pages else run_root.name

    rows, parse_errors = _read_review_rows(review_path, review_format)
    errors: list[dict[str, object]] = list(parse_errors)
    seen_keys: set[tuple[str, str, str]] = set()
    decision_counts: dict[str, int] = {state: 0 for state in DECISION_STATES}
    decision_counts["unreviewed"] = 0
    severity_counts: dict[str, int] = {level: 0 for level in SEVERITY_LEVELS}
    reason_code_counts: dict[str, int] = {code: 0 for code in REASON_CODES}
    regression_fixture_count = 0
    reviewed_count = 0

    for row in rows:
        line = int(row.get("__line__", 0))
        run_id = (row.get("run_id") or "").strip()
        batch_id = (row.get("batch_id") or "").strip()
        sample_id = (row.get("sample_id") or "").strip()
        page_id = (row.get("page_id") or "").strip()
        decision = (row.get("decision") or "").strip()
        severity = (row.get("severity") or "").strip()
        reason_codes_text = (row.get("reason_codes") or "").strip()
        regression_text = (row.get("regression_fixture_candidate") or "").strip()
        reviewer = (row.get("reviewer") or "").strip()

        if run_id and run_id not in expected_run_ids:
            errors.append(
                {
                    "code": "unknown_run_id",
                    "row": line,
                    "value": run_id,
                    "expected_run_id": expected_run_id,
                }
            )
        key = (batch_id, sample_id, page_id)
        if key in expected_keys:
            if key in seen_keys:
                errors.append(
                    {
                        "code": "duplicate_page_row",
                        "row": line,
                        "batch_id": batch_id,
                        "sample_id": sample_id,
                        "page_id": page_id,
                    }
                )
            seen_keys.add(key)
        else:
            errors.append(
                {
                    "code": "unknown_page_id",
                    "row": line,
                    "batch_id": batch_id,
                    "sample_id": sample_id,
                    "page_id": page_id,
                }
            )

        if decision and decision not in DECISION_STATES:
            errors.append(
                {
                    "code": "unknown_decision",
                    "row": line,
                    "value": decision,
                }
            )
        elif decision in DECISION_STATES:
            decision_counts[decision] += 1
            reviewed_count += 1
            if not reviewer:
                errors.append(
                    {
                        "code": "missing_reviewer",
                        "row": line,
                        "decision": decision,
                    }
                )
        else:
            decision_counts["unreviewed"] += 1

        if severity and severity not in SEVERITY_LEVELS:
            errors.append(
                {
                    "code": "unknown_severity",
                    "row": line,
                    "value": severity,
                }
            )
        elif severity:
            severity_counts[severity] += 1

        for code in _split_reason_codes(reason_codes_text):
            if code not in REASON_CODES:
                errors.append(
                    {
                        "code": "unknown_reason_code",
                        "row": line,
                        "value": code,
                    }
                )
            else:
                reason_code_counts[code] += 1

        if regression_text:
            normalized = regression_text.lower()
            if normalized in ("true", "yes", "1"):
                regression_fixture_count += 1
            elif normalized not in ("false", "no", "0"):
                errors.append(
                    {
                        "code": "invalid_regression_fixture_value",
                        "row": line,
                        "value": regression_text,
                    }
                )

        if decision in ("hold", "reject"):
            if not severity:
                errors.append(
                    {
                        "code": "missing_severity",
                        "row": line,
                        "decision": decision,
                    }
                )
            if not reason_codes_text:
                errors.append(
                    {
                        "code": "missing_reason_codes",
                        "row": line,
                        "decision": decision,
                    }
                )

    missing_pages = sorted(expected_keys - seen_keys)
    for batch_id, sample_id, page_id in missing_pages:
        errors.append(
            {
                "code": "missing_page_row",
                "batch_id": batch_id,
                "sample_id": sample_id,
                "page_id": page_id,
            }
        )

    valid = not errors
    status = "passed" if valid else "blocked"
    payload: dict[str, Any] = {
        "report_version": WET_REVIEW_VALIDATION_REPORT_VERSION,
        "run_path": ".",
        "review_path": _relative_to_run(run_root, review_path),
        "review_format": review_format,
        "valid": valid,
        "status": status,
        "summary": {
            "row_count": len(rows),
            "expected_page_count": len(expected_keys),
            "reviewed_page_count": reviewed_count,
            "error_count": len(errors),
            "regression_fixture_candidate_count": regression_fixture_count,
        },
        "decision_counts": decision_counts,
        "severity_counts": severity_counts,
        "reason_code_counts": reason_code_counts,
        "errors": sorted(errors, key=_error_sort_key),
        "scope": {
            "generator_quality_evidence_only": True,
            "release_ready_dataset_artifact": False,
            "manifest_v1_changed": False,
            "hocrgen_behavior_added": False,
            "human_review_sidecar_included": True,
            "llm_triage_included": False,
            "network_required": False,
        },
    }
    return WetReviewValidationResult(
        run_root=run_root,
        review_path=review_path,
        payload=payload,
    )


def _reviewable_pages(run_root: Path) -> list[_ReviewablePage]:
    run_payload = _load_wet_test_run(run_root)
    run_id = run_root.name
    batches = _review_batches(run_payload)
    pages: list[_ReviewablePage] = []
    for batch in batches:
        manifest_path = _resolve_run_path(run_root, batch.manifest_path)
        if not manifest_path.is_file():
            raise ValueError(
                f"wet-test run is missing manifest: {batch.manifest_path}"
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"wet-test run manifest is not valid JSON: {batch.manifest_path}: {exc}"
            ) from exc
        samples = manifest.get("samples", [])
        if not isinstance(samples, list):
            raise ValueError(
                f"manifest samples must be a list: {batch.manifest_path}"
            )
        batch_path = PurePosixPath(batch.batch_path)
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
            recipe_id = str(
                provenance.get("recipe_id", sample.get("recipe_id", ""))
            )
            persona = controls.get("persona")
            condition = controls.get("condition")
            degradation = str(provenance.get("degradation_preset", ""))
            font_id = str(provenance.get("font_id", ""))
            for page in sample_pages:
                if not isinstance(page, dict):
                    raise ValueError(
                        f"manifest page must be an object: {batch.manifest_path}"
                    )
                asset_path_text = page.get("asset_path")
                portable_asset = _portable_path(asset_path_text)
                if portable_asset is None:
                    raise ValueError(
                        "manifest asset path must be relative and portable: "
                        f"{asset_path_text}"
                    )
                run_asset_path = batch_path / portable_asset
                pages.append(
                    _ReviewablePage(
                        run_id=run_id,
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
    pages.sort(
        key=lambda page: (
            page.batch_id,
            page.sample_id,
            page.page_id,
            page.asset_path,
        )
    )
    return pages


def _load_wet_test_run(run_root: Path) -> dict[str, Any]:
    path = run_root / "reports" / WET_TEST_RUN_FILENAME
    if not path.is_file():
        raise ValueError(f"missing wet-test run report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("report_version") != "wet_test_run.v1":
        raise ValueError("wet-review requires a wet_test_run.v1 report")
    if payload.get("status") != "passed":
        raise ValueError("wet-review requires a passed wet-test run")
    return payload


def _review_batches(run_payload: dict[str, Any]) -> list[_ReviewBatch]:
    generated_batch = run_payload.get("generated_batch")
    if not isinstance(generated_batch, dict):
        raise ValueError("wet-test run report is missing generated_batch")
    batches = [
        _ReviewBatch(
            batch_id=str(generated_batch.get("batch_id", "generated_batch")),
            batch_path=_portable_relative_str(generated_batch.get("batch_path")),
            manifest_path=_portable_relative_str(generated_batch.get("manifest_path")),
        )
    ]
    supplemental_batches = run_payload.get("supplemental_batches", [])
    if not isinstance(supplemental_batches, list):
        raise ValueError("wet-test run report supplemental_batches must be a list")
    for index, raw_batch in enumerate(supplemental_batches):
        if not isinstance(raw_batch, dict):
            raise ValueError(
                "wet-test run report supplemental batch must be an object"
            )
        batches.append(
            _ReviewBatch(
                batch_id=str(raw_batch.get("batch_id", f"supplemental_{index}")),
                batch_path=_portable_relative_str(raw_batch.get("batch_path")),
                manifest_path=_portable_relative_str(raw_batch.get("manifest_path")),
            )
        )
    return batches


def _write_csv_template(output: Path, pages: list[_ReviewablePage]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(REVIEW_FIELDS),
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for page in pages:
        writer.writerow(_template_row(page))
    output.write_text(buffer.getvalue(), encoding="utf-8")


def _write_jsonl_template(output: Path, pages: list[_ReviewablePage]) -> None:
    lines = [
        json.dumps(_template_row(page), ensure_ascii=False, sort_keys=True)
        for page in pages
    ]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _template_row(page: _ReviewablePage) -> dict[str, str]:
    return {
        "run_id": page.run_id,
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
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    text = review_path.read_text(encoding="utf-8")
    if review_format == "csv":
        return _read_csv_rows(text)
    return _read_jsonl_rows(text)


def _read_csv_rows(
    text: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    errors: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    missing_fields = [field for field in REVIEW_FIELDS if field not in fieldnames]
    if missing_fields:
        errors.append(
            {
                "code": "missing_csv_field",
                "fields": sorted(missing_fields),
            }
        )
    for index, raw in enumerate(reader, start=2):
        row: dict[str, object] = {"__line__": index}
        for field in REVIEW_FIELDS:
            row[field] = raw.get(field, "")
        rows.append(row)
    return rows, errors


def _read_jsonl_rows(
    text: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    errors: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "code": "invalid_jsonl_row",
                    "row": index,
                    "message": exc.msg,
                }
            )
            continue
        if not isinstance(entry, dict):
            errors.append(
                {
                    "code": "invalid_jsonl_row",
                    "row": index,
                    "message": "review row must be a JSON object",
                }
            )
            continue
        row: dict[str, object] = {"__line__": index}
        for field in REVIEW_FIELDS:
            value = entry.get(field, "")
            row[field] = "" if value is None else str(value)
        rows.append(row)
    return rows, errors


def _split_reason_codes(text: str) -> list[str]:
    return [code.strip() for code in text.split(REASON_CODE_SEPARATOR) if code.strip()]


def _error_sort_key(error: dict[str, object]) -> tuple[str, int, str]:
    return (
        str(error.get("code", "")),
        int(error.get("row", 0) or 0),
        str(error.get("value", "")),
    )


def _portable_path(value: object) -> PurePosixPath | None:
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        return None
    return path


def _portable_relative_str(value: object) -> str:
    path = _portable_path(value)
    if path is None:
        raise ValueError(f"expected a portable relative path: {value}")
    return path.as_posix()


def _resolve_run_path(run_root: Path, relative_path: str) -> Path:
    portable = _portable_path(relative_path)
    if portable is None:
        raise ValueError(f"expected a portable relative path: {relative_path}")
    resolved = (run_root / Path(*portable.parts)).resolve()
    try:
        resolved.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(
            f"path escapes wet-test run root: {relative_path}"
        ) from exc
    return resolved


def _relative_to_run(run_root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(run_root)
    except ValueError:
        return path.resolve().as_posix()
    return PurePosixPath(*relative.parts).as_posix()
