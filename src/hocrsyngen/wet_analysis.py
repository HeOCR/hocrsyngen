from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, UnidentifiedImageError

from hocrsyngen.generator import GOVERNED_TEMPLATE_IDS, rich_template_catalog
from hocrsyngen.io import sha256_file
from hocrsyngen.validation import BatchValidationError, validate_batch


WET_ANALYSIS_REPORT_VERSION = "wet_analysis_report.v1"
WET_TEST_RUN_FILENAME = "wet_test_run.json"
NEAR_BLANK_INK_DENSITY_MAX = 0.002
LOW_INK_DENSITY_MIN = 0.01
HIGH_INK_DENSITY_MAX = 0.95
INK_LUMA_THRESHOLD = 128


@dataclass(frozen=True)
class WetAnalysisResult:
    run_root: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class AnalysisBatch:
    batch_id: str
    role: str
    batch_path: str
    manifest_path: str


@dataclass(frozen=True)
class PageMetric:
    batch_id: str
    sample_id: str
    page_id: str
    asset_path: str
    manifest_width: int
    manifest_height: int
    actual_width: int | None
    actual_height: int | None
    ink_density: float | None
    sha256_matches_manifest: bool


def analyze_wet_test_run(*, run_root: Path) -> WetAnalysisResult:
    run_root = run_root.resolve()
    hard_blockers: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    if not run_root.is_dir():
        raise ValueError(f"wet-test run directory does not exist: {run_root}")

    run_payload = _load_wet_test_run(run_root)
    if run_payload.get("status") != "passed":
        hard_blockers.append(
            _finding(
                code="wet_run_not_passed",
                severity="P0",
                message="wet-analyze requires a passed wet-test run.",
                source_path="reports/wet_test_run.json",
            )
        )

    batches = _analysis_batches(run_payload)
    catalog = _catalog_by_join_key()
    checksum_inventory = _load_checksum_inventory(run_root)
    sample_ids: Counter[str] = Counter()
    page_ids: Counter[str] = Counter()
    page_hashes: Counter[str] = Counter()
    texts: Counter[str] = Counter()
    observed: dict[str, Counter[str]] = {
        "template_id": Counter(),
        "recipe_id": Counter(),
        "style_persona": Counter(),
        "condition": Counter(),
        "degradation": Counter(),
        "font_id": Counter(),
        "document_family": Counter(),
        "layout_density": Counter(),
    }
    catalog_missing: list[dict[str, str]] = []
    page_metrics: list[PageMetric] = []
    unsafe_path_count = 0
    hash_mismatch_count = 0
    checksum_inventory_mismatch_count = 0
    checksum_inventory_missing_count = 0

    for batch in batches:
        batch_dir = _resolve_run_path(run_root, batch.batch_path)
        manifest_path_text = _validated_manifest_path(batch)
        manifest_path = _resolve_run_path(run_root, manifest_path_text)
        try:
            validate_batch(batch_dir)
        except BatchValidationError as exc:
            hard_blockers.append(
                _finding(
                    code="batch_validation_failed",
                    severity="P0",
                    message=str(exc),
                    batch_id=batch.batch_id,
                    source_path=batch.batch_path,
                )
            )
        if not manifest_path.is_file():
            hard_blockers.append(
                _finding(
                    code="manifest_missing",
                    severity="P0",
                    message="Batch manifest is missing.",
                    batch_id=batch.batch_id,
                    source_path=manifest_path_text,
                )
            )
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            hard_blockers.append(
                _finding(
                    code="manifest_json_invalid",
                    severity="P0",
                    message=f"Malformed manifest JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                    batch_id=batch.batch_id,
                    source_path=manifest_path_text,
                )
            )
            continue
        samples = manifest.get("samples", [])
        if not isinstance(samples, list):
            hard_blockers.append(
                _finding(
                    code="manifest_samples_invalid",
                    severity="P0",
                    message="Manifest samples must be a list.",
                    batch_id=batch.batch_id,
                    source_path=manifest_path_text,
                )
            )
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                hard_blockers.append(
                    _finding(
                        code="manifest_sample_invalid",
                        severity="P0",
                        message="Manifest sample must be an object.",
                        batch_id=batch.batch_id,
                        source_path=manifest_path_text,
                    )
                )
                continue
            sample_id = str(sample.get("sample_id", ""))
            sample_ids[sample_id] += 1
            text = sample.get("text", {})
            if isinstance(text, dict):
                texts[str(text.get("logical_order", ""))] += 1
            provenance = sample.get("provenance", {})
            controls = sample.get("controls", {})
            if not isinstance(provenance, dict):
                provenance = {}
            if not isinstance(controls, dict):
                controls = {}
            template_id = str(provenance.get("template_id", ""))
            recipe_id = str(provenance.get("recipe_id", sample.get("recipe_id", "")))
            observed["template_id"][template_id] += 1
            observed["recipe_id"][recipe_id] += 1
            observed["style_persona"][str(controls.get("persona") or "default")] += 1
            observed["condition"][str(controls.get("condition") or "default")] += 1
            observed["degradation"][str(provenance.get("degradation_preset", ""))] += 1
            observed["font_id"][str(provenance.get("font_id", ""))] += 1
            catalog_entry = catalog.get((template_id, recipe_id))
            if catalog_entry is None:
                catalog_missing.append(
                    {
                        "batch_id": batch.batch_id,
                        "sample_id": sample_id,
                        "template_id": template_id,
                        "recipe_id": recipe_id,
                    }
                )
            else:
                observed["document_family"][
                    str(catalog_entry["document_family"])
                ] += 1
                observed["layout_density"][str(catalog_entry["layout_density"])] += 1
            pages = sample.get("pages", [])
            if not isinstance(pages, list):
                hard_blockers.append(
                    _finding(
                        code="manifest_pages_invalid",
                        severity="P0",
                        message="Manifest sample pages must be a list.",
                        batch_id=batch.batch_id,
                        sample_id=sample_id,
                        source_path=manifest_path_text,
                    )
                )
                continue
            for page in pages:
                if not isinstance(page, dict):
                    hard_blockers.append(
                        _finding(
                            code="manifest_page_invalid",
                            severity="P0",
                            message="Manifest page must be an object.",
                            batch_id=batch.batch_id,
                            sample_id=sample_id,
                            source_path=manifest_path_text,
                        )
                    )
                    continue
                page_id = str(page.get("page_id", ""))
                page_ids[f"{batch.batch_id}:{page_id}"] += 1
                asset_path = str(page.get("asset_path", ""))
                portable_asset = _portable_path(asset_path)
                if portable_asset is None:
                    unsafe_path_count += 1
                    hard_blockers.append(
                        _finding(
                            code="unsafe_asset_path",
                            severity="P0",
                            message="Manifest asset path must be relative, portable, and stay below the batch root.",
                            batch_id=batch.batch_id,
                            sample_id=sample_id,
                            page_id=page_id,
                            source_path=asset_path,
                        )
                    )
                    continue
                run_asset_path = PurePosixPath(batch.batch_path) / portable_asset
                asset_abs = _resolve_run_path(run_root, run_asset_path.as_posix())
                expected_sha = str(page.get("sha256", ""))
                actual_sha = sha256_file(asset_abs) if asset_abs.is_file() else ""
                if actual_sha:
                    page_hashes[actual_sha] += 1
                sha_matches = actual_sha == expected_sha
                if not sha_matches:
                    hash_mismatch_count += 1
                inventory_sha = checksum_inventory.get(run_asset_path.as_posix())
                if inventory_sha is None:
                    checksum_inventory_missing_count += 1
                elif inventory_sha != actual_sha:
                    checksum_inventory_mismatch_count += 1
                page_metric, image_blocker = _page_metric(
                    batch_id=batch.batch_id,
                    sample_id=sample_id,
                    page_id=page_id,
                    asset_path=run_asset_path.as_posix(),
                    asset_abs=asset_abs,
                    page=page,
                    sha256_matches_manifest=sha_matches,
                )
                if image_blocker is not None:
                    hard_blockers.append(image_blocker)
                if page_metric is not None:
                    page_metrics.append(page_metric)

    warnings.extend(
        _duplicate_warnings(sample_ids, page_ids, page_hashes, texts, len(texts))
    )
    warnings.extend(_image_warnings(page_metrics))
    if catalog_missing:
        warnings.append(
            _finding(
                code="catalog_join_missing",
                severity="P1",
                message="Some manifest template/recipe pairs did not join to template_catalog.v2.",
                count=len(catalog_missing),
            )
        )
    if hash_mismatch_count:
        hard_blockers.append(
            _finding(
                code="manifest_hash_mismatch",
                severity="P0",
                message="One or more page asset hashes do not match manifest sha256 values.",
                count=hash_mismatch_count,
            )
        )
    if checksum_inventory_mismatch_count:
        hard_blockers.append(
            _finding(
                code="checksum_inventory_mismatch",
                severity="P0",
                message="One or more checksum inventory entries do not match current artifacts.",
                count=checksum_inventory_mismatch_count,
                source_path="reports/wet_test_checksums.txt",
            )
        )
    if checksum_inventory_missing_count:
        warnings.append(
            _finding(
                code="checksum_inventory_missing_asset",
                severity="P2",
                message="One or more analyzed assets are absent from the wet-run checksum inventory.",
                count=checksum_inventory_missing_count,
                source_path="reports/wet_test_checksums.txt",
            )
        )

    sample_count = sum(sample_ids.values())
    page_count = len(page_metrics)
    duplicate_text_sample_count = sum(count - 1 for count in texts.values() if count > 1)
    status = (
        "blocked"
        if hard_blockers
        else "passed_with_warnings"
        if warnings
        else "passed"
    )
    payload: dict[str, Any] = {
        "report_version": WET_ANALYSIS_REPORT_VERSION,
        "run_path": ".",
        "source_report_path": "reports/wet_test_run.json",
        "status": status,
        "summary": {
            "sample_count": sample_count,
            "page_count": page_count,
            "batch_count": len(batches),
            "warning_count": len(warnings),
            "hard_blocker_count": len(hard_blockers),
        },
        "coverage_matrix": _coverage_matrix(run_payload, observed),
        "duplicate_text": {
            "sample_count": sample_count,
            "unique_text_count": len(texts),
            "duplicate_text_sample_count": duplicate_text_sample_count,
            "duplicate_text_rate": _ratio(duplicate_text_sample_count, sample_count),
            "duplicate_text_values": [
                {"text": text, "count": count}
                for text, count in sorted(texts.items())
                if count > 1
            ],
        },
        "asset_dimensions": _asset_dimensions(page_metrics),
        "image_smoke": {
            "ink_luma_threshold": INK_LUMA_THRESHOLD,
            "near_blank_ink_density_max": NEAR_BLANK_INK_DENSITY_MAX,
            "low_ink_density_min": LOW_INK_DENSITY_MIN,
            "high_ink_density_max": HIGH_INK_DENSITY_MAX,
            "ink_density_range": _ink_density_range(page_metrics),
            "pages": [_page_metric_payload(page) for page in page_metrics],
        },
        "catalog_join": {
            "catalog_version": "template_catalog.v2",
            "complete": not catalog_missing,
            "joined_sample_count": sample_count - len(catalog_missing),
            "missing_sample_count": len(catalog_missing),
            "missing": catalog_missing,
        },
        "path_hash_safety": {
            "portable_asset_path_count": page_count,
            "unsafe_asset_path_count": unsafe_path_count,
            "manifest_hash_mismatch_count": hash_mismatch_count,
            "checksum_inventory_path": "reports/wet_test_checksums.txt",
            "checksum_inventory_asset_missing_count": checksum_inventory_missing_count,
            "checksum_inventory_mismatch_count": checksum_inventory_mismatch_count,
        },
        "warnings": sorted(warnings, key=_finding_sort_key),
        "hard_blockers": sorted(hard_blockers, key=_finding_sort_key),
        "scope": {
            "generator_quality_evidence_only": True,
            "release_ready_dataset_artifact": False,
            "realism_acceptance_claimed": False,
            "ocr_htr_utility_claimed": False,
            "domain_match_claimed": False,
            "manifest_v1_changed": False,
            "hocrgen_behavior_added": False,
            "human_review_sidecar_included": False,
            "llm_triage_included": False,
            "network_required": False,
        },
    }
    return WetAnalysisResult(run_root=run_root, payload=payload)


def _load_wet_test_run(run_root: Path) -> dict[str, Any]:
    path = run_root / "reports" / WET_TEST_RUN_FILENAME
    if not path.is_file():
        raise ValueError(f"missing wet-test run report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("report_version") != "wet_test_run.v1":
        raise ValueError("wet-analyze requires a wet_test_run.v1 report")
    return payload


def _analysis_batches(run_payload: dict[str, Any]) -> list[AnalysisBatch]:
    generated_batch = run_payload.get("generated_batch")
    if not isinstance(generated_batch, dict):
        raise ValueError("wet-test run report is missing generated_batch")
    batches = [
        AnalysisBatch(
            batch_id=str(generated_batch.get("batch_id", "generated_batch")),
            role=str(generated_batch.get("role", "generated_batch")),
            batch_path=_portable_relative_str(generated_batch.get("batch_path")),
            manifest_path=_portable_relative_str(generated_batch.get("manifest_path")),
        )
    ]
    supplemental_batches = run_payload.get("supplemental_batches", [])
    if not isinstance(supplemental_batches, list):
        raise ValueError("wet-test run report supplemental_batches must be a list")
    for index, raw_batch in enumerate(supplemental_batches):
        if not isinstance(raw_batch, dict):
            raise ValueError("wet-test run report supplemental batch must be an object")
        batches.append(
            AnalysisBatch(
                batch_id=str(raw_batch.get("batch_id", f"supplemental_{index}")),
                role=str(raw_batch.get("role", "supplemental")),
                batch_path=_portable_relative_str(raw_batch.get("batch_path")),
                manifest_path=_portable_relative_str(raw_batch.get("manifest_path")),
            )
        )
    return batches


def _catalog_by_join_key() -> dict[tuple[str, str], dict[str, object]]:
    entries: dict[tuple[str, str], dict[str, object]] = {}
    for entry in rich_template_catalog():
        entries[(entry.template_id, entry.recipe_id)] = {
            "document_family": entry.capability_metadata.document_family,
            "layout_density": entry.capability_metadata.layout_density,
        }
    return entries


def _load_checksum_inventory(run_root: Path) -> dict[str, str]:
    path = run_root / "reports" / "wet_test_checksums.txt"
    if not path.is_file():
        return {}
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "  " not in line:
            continue
        digest, relative_path = line.split("  ", 1)
        entries[relative_path] = digest
    return entries


def _validated_manifest_path(batch: AnalysisBatch) -> str:
    manifest_path = PurePosixPath(batch.manifest_path)
    expected_manifest_path = PurePosixPath(batch.batch_path) / "generation_manifest.json"
    if manifest_path != expected_manifest_path:
        raise ValueError(
            "wet-test run manifest_path must match the validated batch manifest: "
            f"{batch.manifest_path}"
        )
    return manifest_path.as_posix()


def _page_metric(
    *,
    batch_id: str,
    sample_id: str,
    page_id: str,
    asset_path: str,
    asset_abs: Path,
    page: dict[str, Any],
    sha256_matches_manifest: bool,
) -> tuple[PageMetric | None, dict[str, object] | None]:
    try:
        with Image.open(asset_abs) as image:
            image.load()
            width, height = image.size
            ink_density = _ink_density(image)
    except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
        return None, _finding(
            code="asset_unreadable",
            severity="P0",
            message=f"Could not read page asset: {exc}",
            batch_id=batch_id,
            sample_id=sample_id,
            page_id=page_id,
            source_path=asset_path,
        )
    return (
        PageMetric(
            batch_id=batch_id,
            sample_id=sample_id,
            page_id=page_id,
            asset_path=asset_path,
            manifest_width=int(page.get("width", 0)),
            manifest_height=int(page.get("height", 0)),
            actual_width=width,
            actual_height=height,
            ink_density=round(ink_density, 6),
            sha256_matches_manifest=sha256_matches_manifest,
        ),
        None,
    )


def _ink_density(image: Image.Image) -> float:
    grayscale = image.convert("L")
    histogram = grayscale.histogram()
    ink_pixels = sum(histogram[: INK_LUMA_THRESHOLD + 1])
    total_pixels = grayscale.width * grayscale.height
    return _ratio(ink_pixels, total_pixels)


def _coverage_matrix(
    run_payload: dict[str, Any], observed: dict[str, Counter[str]]
) -> dict[str, object]:
    requested = run_payload.get("config", {}).get("primary_template_ids", [])
    requested_templates = (
        [str(value) for value in requested]
        if isinstance(requested, list)
        else list(GOVERNED_TEMPLATE_IDS)
    )
    observed_templates = sorted(observed["template_id"])
    missing_requested = [
        template_id
        for template_id in requested_templates
        if observed["template_id"][template_id] == 0
    ]
    return {
        "requested_primary_template_ids": requested_templates,
        "observed_template_ids": _counter_payload(observed["template_id"]),
        "missing_requested_template_ids": missing_requested,
        "observed_recipe_ids": _counter_payload(observed["recipe_id"]),
        "observed_style_persona": _counter_payload(observed["style_persona"]),
        "observed_condition": _counter_payload(observed["condition"]),
        "observed_degradation": _counter_payload(observed["degradation"]),
        "observed_font_id": _counter_payload(observed["font_id"]),
        "observed_document_family": _counter_payload(observed["document_family"]),
        "observed_layout_density": _counter_payload(observed["layout_density"]),
        "complete_requested_template_coverage": not missing_requested,
        "observed_template_count": len(observed_templates),
    }


def _asset_dimensions(page_metrics: list[PageMetric]) -> dict[str, object]:
    dimension_counts: Counter[str] = Counter()
    mismatches: list[dict[str, object]] = []
    for page in page_metrics:
        key = f"{page.actual_width}x{page.actual_height}"
        dimension_counts[key] += 1
        if (
            page.actual_width != page.manifest_width
            or page.actual_height != page.manifest_height
        ):
            mismatches.append(
                {
                    "batch_id": page.batch_id,
                    "sample_id": page.sample_id,
                    "page_id": page.page_id,
                    "asset_path": page.asset_path,
                    "manifest": {
                        "width": page.manifest_width,
                        "height": page.manifest_height,
                    },
                    "actual": {
                        "width": page.actual_width,
                        "height": page.actual_height,
                    },
                }
            )
    return {
        "dimension_counts": _counter_payload(dimension_counts),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def _ink_density_range(page_metrics: list[PageMetric]) -> dict[str, float | None]:
    values = [
        page.ink_density for page in page_metrics if page.ink_density is not None
    ]
    if not values:
        return {"min": None, "max": None}
    return {"min": min(values), "max": max(values)}


def _page_metric_payload(page: PageMetric) -> dict[str, object]:
    return {
        "batch_id": page.batch_id,
        "sample_id": page.sample_id,
        "page_id": page.page_id,
        "asset_path": page.asset_path,
        "dimensions": {
            "width": page.actual_width,
            "height": page.actual_height,
        },
        "ink_density": page.ink_density,
        "sha256_matches_manifest": page.sha256_matches_manifest,
    }


def _duplicate_warnings(
    sample_ids: Counter[str],
    page_ids: Counter[str],
    page_hashes: Counter[str],
    texts: Counter[str],
    unique_text_count: int,
) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    duplicate_sample_ids = [
        {"sample_id": sample_id, "count": count}
        for sample_id, count in sorted(sample_ids.items())
        if count > 1
    ]
    duplicate_page_ids = [
        {"page_id_key": page_id, "count": count}
        for page_id, count in sorted(page_ids.items())
        if count > 1
    ]
    duplicate_texts = [
        {"text": text, "count": count}
        for text, count in sorted(texts.items())
        if count > 1
    ]
    duplicate_page_hashes = [
        {"sha256": digest, "count": count}
        for digest, count in sorted(page_hashes.items())
        if count > 1
    ]
    if duplicate_sample_ids:
        warnings.append(
            _finding(
                code="repeated_sample_id",
                severity="P1",
                message="Repeated sample ids were found in the wet-test run.",
                count=len(duplicate_sample_ids),
                details=duplicate_sample_ids,
            )
        )
    if duplicate_page_ids:
        warnings.append(
            _finding(
                code="repeated_page_id",
                severity="P1",
                message="Repeated page ids were found within a batch.",
                count=len(duplicate_page_ids),
                details=duplicate_page_ids,
            )
        )
    if duplicate_texts:
        warnings.append(
            _finding(
                code="duplicate_text",
                severity="P2",
                message="Repeated logical-order manifest text was found.",
                count=len(duplicate_texts),
                unique_text_count=unique_text_count,
                details=duplicate_texts,
            )
        )
    if duplicate_page_hashes:
        warnings.append(
            _finding(
                code="repeated_page_hash",
                severity="P2",
                message="Repeated page asset hashes were found in the wet-test run.",
                count=len(duplicate_page_hashes),
                details=duplicate_page_hashes,
            )
        )
    return warnings


def _image_warnings(page_metrics: list[PageMetric]) -> list[dict[str, object]]:
    near_blank_pages = [
        _page_metric_payload(page)
        for page in page_metrics
        if page.ink_density is not None
        and page.ink_density <= NEAR_BLANK_INK_DENSITY_MAX
    ]
    low_ink_pages = [
        _page_metric_payload(page)
        for page in page_metrics
        if page.ink_density is not None
        and NEAR_BLANK_INK_DENSITY_MAX < page.ink_density < LOW_INK_DENSITY_MIN
    ]
    high_ink_pages = [
        _page_metric_payload(page)
        for page in page_metrics
        if page.ink_density is not None and page.ink_density > HIGH_INK_DENSITY_MAX
    ]
    warnings: list[dict[str, object]] = []
    if near_blank_pages:
        warnings.append(
            _finding(
                code="near_blank_image",
                severity="P1",
                message="One or more page assets are blank or near-blank by deterministic ink-density smoke.",
                count=len(near_blank_pages),
                threshold=NEAR_BLANK_INK_DENSITY_MAX,
                details=near_blank_pages,
            )
        )
    if low_ink_pages:
        warnings.append(
            _finding(
                code="low_ink_density",
                severity="P2",
                message="One or more page assets have low ink density.",
                count=len(low_ink_pages),
                threshold=LOW_INK_DENSITY_MIN,
                details=low_ink_pages,
            )
        )
    if high_ink_pages:
        warnings.append(
            _finding(
                code="high_ink_density",
                severity="P2",
                message="One or more page assets have unusually high ink density.",
                count=len(high_ink_pages),
                threshold=HIGH_INK_DENSITY_MAX,
                details=high_ink_pages,
            )
        )
    return warnings


def _finding(
    *,
    code: str,
    severity: str,
    message: str,
    **extra: object,
) -> dict[str, object]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        **{key: value for key, value in extra.items() if value is not None},
    }


def _finding_sort_key(finding: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(finding.get("severity", "")),
        str(finding.get("code", "")),
        str(finding.get("source_path", "")),
    )


def _counter_payload(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


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
    portable = PurePosixPath(_portable_relative_str(relative_path))
    resolved = (run_root / Path(*portable.parts)).resolve()
    try:
        resolved.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(f"path escapes wet-test run root: {relative_path}") from exc
    return resolved
