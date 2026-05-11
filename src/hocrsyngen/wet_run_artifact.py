from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


WET_TEST_RUN_FILENAME = "wet_test_run.json"
WET_TEST_RUN_REPORT_VERSION = "wet_test_run.v1"


class WetRunArtifactError(ValueError):
    """Raised when a wet-test run artifact cannot be loaded or read."""


@dataclass(frozen=True)
class WetRunBatch:
    batch_id: str
    role: str
    batch_path: str
    manifest_path: str


@dataclass(frozen=True)
class BatchReadError:
    code: str
    message: str
    batch_id: str | None = None


def load_wet_run_payload(run_root: Path) -> dict[str, Any]:
    """Load and version-check ``reports/wet_test_run.json``.

    Does not check ``status``; callers that require a passed run should call
    :func:`require_passed_run` themselves so that ``wet-analyze`` can still
    inspect failed runs.
    """
    path = run_root / "reports" / WET_TEST_RUN_FILENAME
    if not path.is_file():
        raise WetRunArtifactError(f"missing wet-test run report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("report_version") != WET_TEST_RUN_REPORT_VERSION:
        raise WetRunArtifactError(
            "wet-test run report has unexpected report_version: "
            f"{payload.get('report_version')!r}; expected "
            f"{WET_TEST_RUN_REPORT_VERSION}"
        )
    return payload


def require_passed_run(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise WetRunArtifactError(
            f"wet-test run did not pass: status={payload.get('status')!r}"
        )


def read_batches(payload: dict[str, Any]) -> list[WetRunBatch]:
    """Strict reader: raises on the first malformed input."""
    batches, errors = read_batches_safely(payload)
    if errors:
        raise WetRunArtifactError(errors[0].message)
    return batches


def read_batches_safely(
    payload: dict[str, Any],
) -> tuple[list[WetRunBatch], list[BatchReadError]]:
    """Tolerant reader for ``wet-analyze``: returns whatever batches parsed
    cleanly plus a list of structured errors for the rest.
    """
    batches: list[WetRunBatch] = []
    errors: list[BatchReadError] = []

    generated = payload.get("generated_batch")
    if not isinstance(generated, dict):
        errors.append(
            BatchReadError(
                code="wet_run_report_invalid",
                message="wet-test run report is missing generated_batch",
            )
        )
    else:
        batch = _read_batch(
            generated,
            fallback_batch_id="generated_batch",
            fallback_role="generated_batch",
            errors=errors,
        )
        if batch is not None:
            batches.append(batch)

    supplemental = payload.get("supplemental_batches", [])
    if not isinstance(supplemental, list):
        errors.append(
            BatchReadError(
                code="wet_run_report_invalid",
                message="wet-test run report supplemental_batches must be a list",
            )
        )
        return batches, errors
    for index, raw in enumerate(supplemental):
        if not isinstance(raw, dict):
            errors.append(
                BatchReadError(
                    code="wet_run_report_invalid",
                    message=(
                        "wet-test run report supplemental batch must be an object"
                    ),
                )
            )
            continue
        batch = _read_batch(
            raw,
            fallback_batch_id=f"supplemental_{index}",
            fallback_role="supplemental",
            errors=errors,
        )
        if batch is not None:
            batches.append(batch)
    return batches, errors


def _read_batch(
    raw: dict[str, Any],
    *,
    fallback_batch_id: str,
    fallback_role: str,
    errors: list[BatchReadError],
) -> WetRunBatch | None:
    batch_id = str(raw.get("batch_id", fallback_batch_id))
    try:
        batch_path = portable_relative_str(raw.get("batch_path"))
        manifest_path = portable_relative_str(raw.get("manifest_path"))
    except ValueError as exc:
        errors.append(
            BatchReadError(
                code="wet_run_batch_path_invalid",
                message=str(exc),
                batch_id=batch_id,
            )
        )
        return None
    return WetRunBatch(
        batch_id=batch_id,
        role=str(raw.get("role", fallback_role)),
        batch_path=batch_path,
        manifest_path=manifest_path,
    )


def validated_manifest_path(batch: WetRunBatch) -> str:
    """Verify ``batch.manifest_path`` matches ``batch_path/generation_manifest.json``."""
    manifest_path = PurePosixPath(batch.manifest_path)
    expected = PurePosixPath(batch.batch_path) / "generation_manifest.json"
    if manifest_path != expected:
        raise WetRunArtifactError(
            "wet-test run manifest_path must match the validated batch manifest: "
            f"{batch.manifest_path}"
        )
    return manifest_path.as_posix()


def portable_path(value: object) -> PurePosixPath | None:
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        return None
    return path


def portable_relative_str(value: object) -> str:
    path = portable_path(value)
    if path is None:
        raise ValueError(f"expected a portable relative path: {value}")
    return path.as_posix()


def resolve_run_path(run_root: Path, relative_path: str) -> Path:
    portable = portable_path(relative_path)
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


def relative_to_run(run_root: Path, path: Path) -> str:
    """Return ``path`` as a portable POSIX path relative to ``run_root``.

    Raises ``ValueError`` if ``path`` is not a descendant of ``run_root``;
    callers that want a fall-through should handle the exception explicitly.
    """
    relative = path.resolve().relative_to(run_root.resolve())
    return PurePosixPath(*relative.parts).as_posix()
