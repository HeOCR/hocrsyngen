from __future__ import annotations

import json
import platform
import shutil
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any

from PIL import features

from hocrsyngen.generator import (
    GOVERNED_TEMPLATE_IDS,
    generate_batch,
    rich_template_catalog,
)
from hocrsyngen.io import sha256_file
from hocrsyngen.rendering_coverage import write_rendering_coverage_report
from hocrsyngen.validation import validate_batch


WET_TEST_RUN_REPORT_VERSION = "wet_test_run.v1"
WET_TEST_RUN_FILENAME = "wet_test_run.json"
WET_TEST_CHECKSUMS_FILENAME = "wet_test_checksums.txt"
SMOKE_PROFILE = "smoke"
SMOKE_PROFILE_PRIMARY_TEMPLATE_IDS = tuple(GOVERNED_TEMPLATE_IDS)
SMOKE_PROFILE_NON_DEFAULT_TEMPLATE_IDS = ("printed_letter",)
SMOKE_PROFILE_NON_DEFAULT_PERSONA = "style_open_drift_v1"
SMOKE_PROFILE_NON_DEFAULT_CONDITION = "condition_low_contrast_v1"
SMOKE_PROFILE_PRIMARY_COUNT = len(SMOKE_PROFILE_PRIMARY_TEMPLATE_IDS)
SMOKE_PROFILE_NON_DEFAULT_COUNT = len(SMOKE_PROFILE_NON_DEFAULT_TEMPLATE_IDS)
SMOKE_PROFILE_TOTAL_COUNT = (
    SMOKE_PROFILE_PRIMARY_COUNT + SMOKE_PROFILE_NON_DEFAULT_COUNT
)


@dataclass(frozen=True)
class WetRunResult:
    run_root: Path
    batch_dir: Path
    reports_dir: Path
    wet_test_run_path: Path
    checksum_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class SmokeBatchSpec:
    batch_id: str
    role: str
    relative_path: Path
    count: int
    seed: int
    template_ids: tuple[str, ...]
    persona: str | None
    condition: str | None
    generation_report_name: str
    validation_report_name: str
    rendering_coverage_report: bool


def create_wet_test_smoke_run(
    *,
    output: Path,
    seed: int,
    command_line: list[str],
    rendering_coverage_report: bool = False,
) -> WetRunResult:
    if output.exists() and not output.is_dir():
        raise ValueError(f"output path exists and is not a directory: {output}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            f"wet-run output directory already exists and is not empty: {output}"
        )

    output_parent = output.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output_parent))
    try:
        result = _create_wet_test_smoke_run_in_root(
            run_root=temp_root,
            seed=seed,
            command_line=command_line,
            rendering_coverage_report=rendering_coverage_report,
        )
    except (Exception, KeyboardInterrupt) as exc:
        shutil.rmtree(temp_root, ignore_errors=True)
        _write_failed_run_report(
            output=output,
            seed=seed,
            command_line=command_line,
            rendering_coverage_report=rendering_coverage_report,
            error=exc,
        )
        raise

    if output.exists():
        output.rmdir()
    temp_root.rename(output)
    return WetRunResult(
        run_root=output,
        batch_dir=output / "batch",
        reports_dir=output / "reports",
        wet_test_run_path=output / "reports" / WET_TEST_RUN_FILENAME,
        checksum_path=output / "reports" / WET_TEST_CHECKSUMS_FILENAME,
        payload=result.payload,
    )


def _create_wet_test_smoke_run_in_root(
    *,
    run_root: Path,
    seed: int,
    command_line: list[str],
    rendering_coverage_report: bool,
) -> WetRunResult:
    batch_dir = run_root / "batch"
    reports_dir = run_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    specs = _smoke_batch_specs(
        seed=seed,
        rendering_coverage_report=rendering_coverage_report,
    )

    retained_paths: list[Path] = []
    batch_payloads: list[dict[str, Any]] = []
    for spec in specs:
        batch_payload, batch_retained_paths = _run_smoke_batch(
            run_root=run_root,
            reports_dir=reports_dir,
            spec=spec,
        )
        batch_payloads.append(batch_payload)
        retained_paths.extend(batch_retained_paths)

    template_catalog_path = reports_dir / "template_catalog_v2.json"
    template_catalog_path.write_text(
        _json_dumps(_rich_template_catalog_payload()) + "\n",
        encoding="utf-8",
    )
    retained_paths.append(template_catalog_path)
    checksums = _checksums(run_root, retained_paths)
    checksum_path = reports_dir / WET_TEST_CHECKSUMS_FILENAME
    _write_checksum_file(checksum_path, checksums)

    wet_test_run_path = reports_dir / WET_TEST_RUN_FILENAME
    primary_batch = batch_payloads[0]
    supplemental_batches = batch_payloads[1:]
    total_sample_count = sum(batch["sample_count"] for batch in batch_payloads)
    total_page_count = sum(batch["page_count"] for batch in batch_payloads)
    payload: dict[str, Any] = {
        "report_version": WET_TEST_RUN_REPORT_VERSION,
        "profile": SMOKE_PROFILE,
        "status": "passed",
        "command_line": command_line,
        "package": {
            "name": "hocrsyngen",
            "version": _package_version(),
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "pillow_raqm": bool(features.check("raqm")),
        },
        "config": {
            "seed": seed,
            "total_count": total_sample_count,
            "primary_count": primary_batch["sample_count"],
            "supplemental_count": sum(
                batch["sample_count"] for batch in supplemental_batches
            ),
            "primary_template_ids": list(SMOKE_PROFILE_PRIMARY_TEMPLATE_IDS),
            "supplemental_controls": [
                {
                    "batch_id": batch["batch_id"],
                    "template_ids": batch["template_ids"],
                    "persona": batch["persona"],
                    "condition": batch["condition"],
                }
                for batch in supplemental_batches
            ],
            "primary_rendering_coverage_report": rendering_coverage_report,
            "output_path": ".",
            "batch_path": primary_batch["batch_path"],
        },
        "reports": {
            "template_catalog_v2_path": _relative_path(run_root, template_catalog_path),
            "checksum_path": _relative_path(run_root, checksum_path),
            "checksum_file_includes_wet_test_run": True,
        },
        "generated_batch": {
            "batch_id": primary_batch["batch_id"],
            "batch_path": primary_batch["batch_path"],
            "manifest_path": primary_batch["manifest_path"],
            "generation_report_path": primary_batch["generation_report_path"],
            "validation_report_path": primary_batch["validation_report_path"],
            "rendering_coverage_report_path": primary_batch[
                "rendering_coverage_report_path"
            ],
            "sample_count": primary_batch["sample_count"],
            "page_count": primary_batch["page_count"],
            "asset_paths": primary_batch["asset_paths"],
            "template_ids": primary_batch["template_ids"],
            "persona": primary_batch["persona"],
            "condition": primary_batch["condition"],
        },
        "supplemental_batches": supplemental_batches,
        "validation": {
            "valid": True,
            "sample_count": total_sample_count,
            "page_count": total_page_count,
        },
        "artifact_checksums": checksums,
        "checksum_contract": {
            "algorithm": "sha256",
            "artifact_checksums_exclude": [
                "reports/wet_test_run.json",
                "reports/wet_test_checksums.txt",
            ],
            "checksum_file_includes": [
                *sorted(checksums),
                "reports/wet_test_run.json",
            ],
        },
        "scope": {
            "generator_quality_evidence_only": True,
            "release_ready_dataset_artifact": False,
            "manifest_v1_changed": False,
            "hocrgen_behavior_added": False,
            "human_review_included": False,
            "llm_triage_included": False,
        },
    }
    wet_test_run_path.write_text(
        _json_dumps(payload) + "\n",
        encoding="utf-8",
    )
    run_checksum = {
        _relative_path(run_root, wet_test_run_path): sha256_file(wet_test_run_path)
    }
    _write_checksum_file(checksum_path, {**checksums, **run_checksum})

    return WetRunResult(
        run_root=run_root,
        batch_dir=batch_dir,
        reports_dir=reports_dir,
        wet_test_run_path=wet_test_run_path,
        checksum_path=checksum_path,
        payload=payload,
    )


def _smoke_batch_specs(
    *, seed: int, rendering_coverage_report: bool
) -> list[SmokeBatchSpec]:
    return [
        SmokeBatchSpec(
            batch_id="default_governed_templates",
            role="governed_template_coverage",
            relative_path=Path("batch"),
            count=SMOKE_PROFILE_PRIMARY_COUNT,
            seed=seed,
            template_ids=SMOKE_PROFILE_PRIMARY_TEMPLATE_IDS,
            persona=None,
            condition=None,
            generation_report_name="generation_report.json",
            validation_report_name="validation_report.json",
            rendering_coverage_report=rendering_coverage_report,
        ),
        SmokeBatchSpec(
            batch_id="non_default_style_condition",
            role="style_condition_smoke",
            relative_path=Path("control_batches") / "non_default_style_condition",
            count=SMOKE_PROFILE_NON_DEFAULT_COUNT,
            seed=seed,
            template_ids=SMOKE_PROFILE_NON_DEFAULT_TEMPLATE_IDS,
            persona=SMOKE_PROFILE_NON_DEFAULT_PERSONA,
            condition=SMOKE_PROFILE_NON_DEFAULT_CONDITION,
            generation_report_name="non_default_style_condition_generation_report.json",
            validation_report_name="non_default_style_condition_validation_report.json",
            rendering_coverage_report=False,
        ),
    ]


def _run_smoke_batch(
    *,
    run_root: Path,
    reports_dir: Path,
    spec: SmokeBatchSpec,
) -> tuple[dict[str, Any], list[Path]]:
    batch_dir = run_root / spec.relative_path
    manifest = generate_batch(
        count=spec.count,
        seed=spec.seed,
        output_dir=batch_dir,
        template_ids=list(spec.template_ids),
        persona=spec.persona,
        condition=spec.condition,
    )
    rendering_report_path = (
        write_rendering_coverage_report(manifest, batch_dir)
        if spec.rendering_coverage_report
        else None
    )
    validation_result = validate_batch(batch_dir)
    generation_report_path = reports_dir / spec.generation_report_name
    generation_report_path.write_text(
        _json_dumps(
            _generation_report_payload(
                _relative_path(run_root, batch_dir),
                sample_count=len(manifest.samples),
                page_count=sum(len(sample.pages) for sample in manifest.samples),
                rendering_coverage_report_path=(
                    _relative_path(run_root, rendering_report_path)
                    if rendering_report_path is not None
                    else None
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    validation_report_path = reports_dir / spec.validation_report_name
    validation_report_path.write_text(
        _json_dumps(
            {
                "schema_version": "validation_report.v1",
                "valid": True,
                "sample_count": validation_result.sample_count,
                "page_count": validation_result.page_count,
                "path": _relative_path(run_root, batch_dir),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    asset_paths = [
        batch_dir / Path(*PurePosixPath(page.asset_path).parts)
        for sample in manifest.samples
        for page in sample.pages
    ]
    retained_paths = [
        batch_dir / "generation_manifest.json",
        generation_report_path,
        validation_report_path,
        *asset_paths,
    ]
    if rendering_report_path is not None:
        retained_paths.append(rendering_report_path)
    batch_payload: dict[str, Any] = {
        "batch_id": spec.batch_id,
        "role": spec.role,
        "batch_path": _relative_path(run_root, batch_dir),
        "manifest_path": _relative_path(run_root, batch_dir / "generation_manifest.json"),
        "generation_report_path": _relative_path(run_root, generation_report_path),
        "validation_report_path": _relative_path(run_root, validation_report_path),
        "rendering_coverage_report_path": (
            _relative_path(run_root, rendering_report_path)
            if rendering_report_path is not None
            else None
        ),
        "sample_count": validation_result.sample_count,
        "page_count": validation_result.page_count,
        "template_ids": list(spec.template_ids),
        "persona": spec.persona,
        "condition": spec.condition,
        "asset_paths": [_relative_path(run_root, path) for path in asset_paths],
    }
    return batch_payload, retained_paths


def _write_failed_run_report(
    *,
    output: Path,
    seed: int,
    command_line: list[str],
    rendering_coverage_report: bool,
    error: BaseException,
) -> None:
    if output.exists() and any(output.iterdir()):
        return
    reports_dir = output / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "report_version": WET_TEST_RUN_REPORT_VERSION,
        "profile": SMOKE_PROFILE,
        "status": "failed",
        "command_line": command_line,
        "package": {
            "name": "hocrsyngen",
            "version": _package_version(),
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "pillow_raqm": bool(features.check("raqm")),
        },
        "config": {
            "seed": seed,
            "primary_template_ids": list(SMOKE_PROFILE_PRIMARY_TEMPLATE_IDS),
            "primary_rendering_coverage_report": rendering_coverage_report,
            "output_path": ".",
        },
        "reports": {
            "wet_test_run_path": f"reports/{WET_TEST_RUN_FILENAME}",
        },
        "validation": {
            "valid": False,
        },
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
        "scope": {
            "generator_quality_evidence_only": True,
            "release_ready_dataset_artifact": False,
            "manifest_v1_changed": False,
            "hocrgen_behavior_added": False,
            "human_review_included": False,
            "llm_triage_included": False,
        },
    }
    (reports_dir / WET_TEST_RUN_FILENAME).write_text(
        _json_dumps(payload) + "\n",
        encoding="utf-8",
    )


def _checksums(root: Path, paths: list[Path]) -> dict[str, str]:
    return {
        _relative_path(root, path): sha256_file(path)
        for path in sorted(paths, key=lambda candidate: _relative_path(root, candidate))
    }


def _write_checksum_file(path: Path, checksums: dict[str, str]) -> None:
    lines = [f"{digest}  {relative_path}" for relative_path, digest in sorted(checksums.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _relative_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    return PurePosixPath(*relative.parts).as_posix()


def _package_version() -> str | None:
    try:
        return metadata.version("hocrsyngen")
    except metadata.PackageNotFoundError:
        return None


def _generation_report_payload(
    output_path: str,
    *,
    sample_count: int,
    page_count: int,
    rendering_coverage_report_path: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "generation_report.v1",
        "sample_count": sample_count,
        "page_count": page_count,
        "output_path": output_path,
        "manifest_path": PurePosixPath(output_path, "generation_manifest.json").as_posix(),
    }
    if rendering_coverage_report_path is not None:
        payload["rendering_coverage_report_path"] = rendering_coverage_report_path
    return payload


def _rich_template_catalog_payload() -> dict[str, object]:
    return {
        "schema_version": "template_catalog.v2",
        "templates": [
            {
                "template_id": entry.template_id,
                "recipe_id": entry.recipe_id,
                "layout_style": entry.layout_style,
                "font_style": entry.font_style,
                "font_id": entry.font_id,
                "degradation_preset": entry.degradation_preset,
                "document_family": entry.capability_metadata.document_family,
                "base_family": entry.capability_metadata.base_family,
                "page_regions": list(entry.capability_metadata.page_regions),
                "annotation_types": list(entry.capability_metadata.annotation_types),
                "identifier_types": list(entry.capability_metadata.identifier_types),
                "layout_density": entry.capability_metadata.layout_density,
                "review_features": list(entry.capability_metadata.review_features),
            }
            for entry in rich_template_catalog()
        ],
    }


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
