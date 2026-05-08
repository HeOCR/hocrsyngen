from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import features

from hocrsyngen.generator import GOVERNED_TEMPLATE_IDS, generate_batch, rich_template_catalog
from hocrsyngen.io import sha256_file
from hocrsyngen.rendering_coverage import write_rendering_coverage_report
from hocrsyngen.validation import validate_batch


WET_TEST_RUN_REPORT_VERSION = "wet_test_run.v1"
WET_TEST_RUN_FILENAME = "wet_test_run.json"
WET_TEST_CHECKSUMS_FILENAME = "wet_test_checksums.txt"
SMOKE_PROFILE = "smoke"
SMOKE_PROFILE_COUNT = len(GOVERNED_TEMPLATE_IDS)
SMOKE_PROFILE_TEMPLATE_IDS = tuple(GOVERNED_TEMPLATE_IDS)


@dataclass(frozen=True)
class WetRunResult:
    run_root: Path
    batch_dir: Path
    reports_dir: Path
    wet_test_run_path: Path
    checksum_path: Path
    payload: dict[str, Any]


def create_wet_test_smoke_run(
    *,
    output: Path,
    seed: int,
    command_line: list[str],
    rendering_coverage_report: bool = False,
) -> WetRunResult:
    if output.exists() and not output.is_dir():
        raise ValueError(f"output path exists and is not a directory: {output}")
    batch_dir = output / "batch"
    reports_dir = output / "reports"
    if batch_dir.exists() or reports_dir.exists():
        raise ValueError(
            "wet-run output must not already contain batch/ or reports/ directories: "
            f"{output}"
        )

    reports_dir.mkdir(parents=True, exist_ok=True)
    manifest = generate_batch(
        count=SMOKE_PROFILE_COUNT,
        seed=seed,
        output_dir=batch_dir,
        template_ids=list(SMOKE_PROFILE_TEMPLATE_IDS),
    )
    rendering_report_path = (
        write_rendering_coverage_report(manifest, batch_dir)
        if rendering_coverage_report
        else None
    )
    validation_result = validate_batch(batch_dir)

    generation_report_path = reports_dir / "generation_report.json"
    generation_report_path.write_text(
        _json_dumps(
            _generation_report_payload(
                _relative_path(output, batch_dir),
                sample_count=len(manifest.samples),
                page_count=sum(len(sample.pages) for sample in manifest.samples),
                rendering_coverage_report_path=(
                    _relative_path(output, rendering_report_path)
                    if rendering_report_path is not None
                    else None
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    validation_report_path = reports_dir / "validation_report.json"
    validation_report_path.write_text(
        _json_dumps(
            {
                "schema_version": "validation_report.v1",
                "valid": True,
                "sample_count": validation_result.sample_count,
                "page_count": validation_result.page_count,
                "path": _relative_path(output, batch_dir),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    template_catalog_path = reports_dir / "template_catalog_v2.json"
    template_catalog_path.write_text(
        _json_dumps(_rich_template_catalog_payload()) + "\n",
        encoding="utf-8",
    )

    retained_paths = [
        batch_dir / "generation_manifest.json",
        generation_report_path,
        validation_report_path,
        template_catalog_path,
    ]
    if rendering_report_path is not None:
        retained_paths.append(rendering_report_path)
    for sample in manifest.samples:
        for page in sample.pages:
            retained_paths.append(batch_dir / Path(*PurePosixPath(page.asset_path).parts))

    checksums = _checksums(output, retained_paths)
    checksum_path = reports_dir / WET_TEST_CHECKSUMS_FILENAME
    _write_checksum_file(checksum_path, checksums)

    wet_test_run_path = reports_dir / WET_TEST_RUN_FILENAME
    payload: dict[str, Any] = {
        "report_version": WET_TEST_RUN_REPORT_VERSION,
        "profile": SMOKE_PROFILE,
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
            "count": SMOKE_PROFILE_COUNT,
            "template_ids": list(SMOKE_PROFILE_TEMPLATE_IDS),
            "persona": None,
            "condition": None,
            "rendering_coverage_report": rendering_coverage_report,
            "output_path": ".",
            "batch_path": _relative_path(output, batch_dir),
        },
        "reports": {
            "generation_report_path": _relative_path(output, generation_report_path),
            "validation_report_path": _relative_path(output, validation_report_path),
            "template_catalog_v2_path": _relative_path(output, template_catalog_path),
            "rendering_coverage_report_path": (
                _relative_path(output, rendering_report_path)
                if rendering_report_path is not None
                else None
            ),
            "checksum_path": _relative_path(output, checksum_path),
        },
        "generated_batch": {
            "manifest_path": _relative_path(output, batch_dir / "generation_manifest.json"),
            "sample_count": validation_result.sample_count,
            "page_count": validation_result.page_count,
            "asset_paths": [
                _relative_path(output, batch_dir / Path(*PurePosixPath(page.asset_path).parts))
                for sample in manifest.samples
                for page in sample.pages
            ],
        },
        "validation": {
            "valid": True,
            "sample_count": validation_result.sample_count,
            "page_count": validation_result.page_count,
        },
        "checksums": checksums,
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
    run_checksum = {_relative_path(output, wet_test_run_path): sha256_file(wet_test_run_path)}
    _write_checksum_file(checksum_path, {**checksums, **run_checksum})

    return WetRunResult(
        run_root=output,
        batch_dir=batch_dir,
        reports_dir=reports_dir,
        wet_test_run_path=wet_test_run_path,
        checksum_path=checksum_path,
        payload=payload,
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
