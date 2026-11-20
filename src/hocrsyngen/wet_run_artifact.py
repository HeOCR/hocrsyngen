from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


WET_TEST_RUN_FILENAME = "wet_test_run.json"
WET_TEST_RUN_REPORT_VERSION = "wet_test_run.v1"
WET_ANALYSIS_REPORT_VERSION = "wet_analysis_report.v1"


class WetRunArtifactError(ValueError):
    """Raised when a wet-test run artifact cannot be loaded or read."""


@dataclass(frozen=True)
class WetRunBatch:
    """A wet-test run batch as recorded in ``wet_test_run.json``.

    Carries the original report metadata only. Call :meth:`resolved` to
    obtain absolute filesystem paths under a given run root.
    """

    batch_id: str
    role: str
    batch_path: str
    manifest_path: str

    def resolved(self, run_root: Path) -> ResolvedWetRunBatch:
        """Return a copy with absolute paths under ``run_root``.

        Asserts that ``manifest_path`` matches the canonical
        ``batch_path/generation_manifest.json`` shape and that both paths
        resolve under ``run_root``. Raises :class:`WetRunArtifactError`
        (a :class:`ValueError` subclass) on any failure.
        """
        assert_canonical_manifest_path(self)
        try:
            batch_dir = resolve_run_path(run_root, self.batch_path)
            manifest_path_abs = resolve_run_path(run_root, self.manifest_path)
        except ValueError as exc:
            raise WetRunArtifactError(str(exc)) from exc
        return ResolvedWetRunBatch(
            batch_id=self.batch_id,
            role=self.role,
            batch_path=self.batch_path,
            manifest_path=self.manifest_path,
            batch_dir=batch_dir,
            manifest_path_abs=manifest_path_abs,
        )


@dataclass(frozen=True)
class ResolvedWetRunBatch:
    """A :class:`WetRunBatch` with absolute filesystem paths attached."""

    batch_id: str
    role: str
    batch_path: str
    manifest_path: str
    batch_dir: Path
    manifest_path_abs: Path


@dataclass(frozen=True)
class BatchReadError:
    code: str
    message: str
    batch_id: str | None = None


def load_wet_run_payload(
    run_root: Path,
    *,
    require_passed: bool = False,
) -> dict[str, Any]:
    """Load and version-check ``reports/wet_test_run.json``.

    When ``require_passed`` is True, also raises ``WetRunArtifactError``
    if the run's status is not ``"passed"``. ``wet-analyze`` keeps the
    default so it can inspect failed runs; ``wet-gallery`` and
    ``wet-review-*`` require passed runs.
    """
    path = run_root / "reports" / WET_TEST_RUN_FILENAME
    if not path.is_file():
        raise WetRunArtifactError(f"missing wet-test run report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    report_version = payload.get("report_version")
    if report_version != WET_TEST_RUN_REPORT_VERSION:
        raise WetRunArtifactError(
            "wet-test run report has unexpected report_version: "
            f"{report_version!r} (expected {WET_TEST_RUN_REPORT_VERSION!r})"
        )
    if require_passed:
        status = payload.get("status")
        if status != "passed":
            raise WetRunArtifactError(
                f"wet-test run did not pass: status={status!r}"
            )
    return payload


def read_batches(payload: dict[str, Any]) -> list[WetRunBatch]:
    """Strict reader: raises ``WetRunArtifactError`` on the first
    malformed batch.
    """
    batches, errors = read_batches_safely(payload)
    if errors:
        raise WetRunArtifactError(errors[0].message)
    return batches


def read_batches_safely(
    payload: dict[str, Any],
) -> tuple[list[WetRunBatch], list[BatchReadError]]:
    """Tolerant reader for ``wet-analyze``: returns the batches that
    parsed cleanly plus structured errors for the rest.
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
                message=(
                    "wet-test run report supplemental_batches must be a list"
                ),
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


def assert_canonical_manifest_path(batch: WetRunBatch) -> None:
    """Assert ``batch.manifest_path`` matches ``batch.batch_path/generation_manifest.json``.

    Raises :class:`WetRunArtifactError` when the recorded manifest path
    drifted from the canonical shape. Does not open or validate the
    manifest itself.
    """
    manifest_path = PurePosixPath(batch.manifest_path)
    expected = PurePosixPath(batch.batch_path) / "generation_manifest.json"
    if manifest_path != expected:
        raise WetRunArtifactError(
            "wet-test run manifest_path must match the validated batch manifest: "
            f"{batch.manifest_path!r} (expected {expected.as_posix()!r})"
        )


def try_portable_path(value: object) -> PurePosixPath | None:
    """Return a :class:`PurePosixPath` if ``value`` is a portable relative
    string, else ``None``. Useful for filter predicates.
    """
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        return None
    return path


def portable_path(value: object) -> PurePosixPath:
    """Strict variant of :func:`try_portable_path` that raises
    :class:`ValueError` on bad input.
    """
    path = try_portable_path(value)
    if path is None:
        raise ValueError(f"expected a portable relative path: {value!r}")
    return path


def portable_relative_str(value: object) -> str:
    """String convenience wrapper around :func:`portable_path`."""
    return portable_path(value).as_posix()


def resolve_run_path(run_root: Path, relative_path: str) -> Path:
    """Resolve ``relative_path`` under ``run_root``. Raises
    :class:`ValueError` when the result would escape ``run_root``.
    """
    portable = portable_path(relative_path)
    resolved = (run_root / Path(*portable.parts)).resolve()
    try:
        resolved.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(
            f"path escapes wet-test run root: {relative_path!r}"
        ) from exc
    return resolved


def relative_to_run(run_root: Path, path: Path) -> str:
    """Return ``path`` as a portable POSIX path relative to ``run_root``.

    Resolves ``path`` (following symlinks) but assumes ``run_root`` is
    already an absolute, resolved path — callers must resolve it before
    calling, which they all do at entry to public functions. Raises
    :class:`ValueError` if ``path`` is not a descendant of ``run_root``.
    """
    relative = path.resolve().relative_to(run_root)
    return PurePosixPath(*relative.parts).as_posix()


def extract_run_meta(run_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the run-meta summary fields from a loaded ``wet_test_run.json`` payload."""
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


def load_analysis_summary(run_root: Path) -> dict[str, Any] | None:
    """Load the analysis-summary slice from ``reports/wet_analysis_report.json``.

    Returns ``None`` when the file is absent, malformed, or version-mismatched,
    so callers can treat the analysis report as optional.
    """
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
