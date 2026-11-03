from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from hocrsyngen.generator import (
    DEFAULT_TEMPLATE_IDS,
    GENERATOR_VERSION,
    GOVERNED_TEMPLATE_IDS,
    RichTemplateCatalogEntry,
    SUPPORTED_CONDITION_BUNDLE_IDS,
    SUPPORTED_STYLE_BUNDLE_IDS,
    TemplateCatalogEntry,
    generate_batch,
    rich_template_catalog,
    source_corpus_id,
    template_catalog,
)
from hocrsyngen.io import sha256_file
from hocrsyngen.line_annotations import LINE_ANNOTATIONS_FILENAME
from hocrsyngen.rendering_coverage import write_rendering_coverage_report
from hocrsyngen.quality_check import quality_check
from hocrsyngen.validation import BatchValidationError, validate_batch
from hocrsyngen.wet_analysis import analyze_wet_test_run
from hocrsyngen.wet_gallery import create_wet_gallery
from hocrsyngen.wet_review import (
    REVIEW_FORMATS,
    build_wet_review_template,
    validate_wet_review,
)
from hocrsyngen.wet_run import create_wet_test_smoke_run
from hocrsyngen.wet_report import NON_RELEASE_STATEMENT, WET_REPORT_VERSION, build_wet_report, format_wet_report_text
from hocrsyngen.wet_triage import DEFAULT_MAX_SAMPLES, build_llm_triage_packet


EVIDENCE_RUN_REPORT_SCHEMA_VERSION = "candidate_evidence_run_report.v1"
# Downstream-defined runtime contract read by `hocrgen hocrsyngen-preflight`
# from `candidate_evidence_run_report.provider_runtime`.
PROVIDER_RUNTIME_SCHEMA_VERSION = "hocrgen_hocrsyngen_provider_runtime.v1"
PROVIDER_RUNTIME_BASIS = (
    "hocrsyngen baseline evidence-run renders locally with Pillow and validates "
    "with jsonschema only; baseline dependency policy forbids network, REST, "
    "GPU, LLM, and diffusion runtimes"
)
CONTRACT_FIXTURE_CATALOG_SCHEMA_VERSION = "contract_fixture_catalog.v1"
CONTRACT_FIXTURE_EXPORT_SCHEMA_VERSION = "contract_fixture_export.v1"
GENERATION_REPORT_SCHEMA_VERSION = "generation_report.v1"
TEMPLATE_CATALOG_SCHEMA_VERSION = "template_catalog.v1"
RICH_TEMPLATE_CATALOG_SCHEMA_VERSION = "template_catalog.v2"
VALIDATION_REPORT_SCHEMA_VERSION = "validation_report.v1"
CONTRACT_FIXTURE_ID = "generation_manifest_v1_fixture_batch"
CONTRACT_FIXTURE_CONTRACT = "generation_manifest.v1"
CONTRACT_FIXTURE_RESOURCE_PATH = "data/contracts/generation_manifest_v1/fixture-batch"
CONTRACT_FIXTURE_MANIFEST_RESOURCE_PATH = (
    "data/contracts/generation_manifest_v1/fixture-batch/generation_manifest.json"
)


@dataclass(frozen=True)
class ContractFixtureCatalogEntry:
    fixture_id: str
    contract: str
    sample_count: int
    page_count: int
    resource_path: str
    manifest_resource_path: str


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _format_template_catalog_entry(entry: TemplateCatalogEntry) -> str:
    return (
        f"template_id={entry.template_id} "
        f"recipe_id={entry.recipe_id} "
        f"layout_style={entry.layout_style} "
        f"font_style={entry.font_style} "
        f"font_id={entry.font_id} "
        f"degradation_preset={entry.degradation_preset}"
    )


def _format_template_catalog_json(catalog: list[TemplateCatalogEntry]) -> str:
    payload = {
        "schema_version": TEMPLATE_CATALOG_SCHEMA_VERSION,
        "templates": [
            {
                "template_id": entry.template_id,
                "recipe_id": entry.recipe_id,
                "layout_style": entry.layout_style,
                "font_style": entry.font_style,
                "font_id": entry.font_id,
                "degradation_preset": entry.degradation_preset,
            }
            for entry in catalog
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _format_rich_template_catalog_json(catalog: list[RichTemplateCatalogEntry]) -> str:
    payload = {
        "schema_version": RICH_TEMPLATE_CATALOG_SCHEMA_VERSION,
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
            for entry in catalog
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _contract_fixture_catalog() -> list[ContractFixtureCatalogEntry]:
    source = resources.files("hocrsyngen") / CONTRACT_FIXTURE_RESOURCE_PATH
    if not source.is_dir():
        raise FileNotFoundError(CONTRACT_FIXTURE_RESOURCE_PATH)
    with resources.as_file(source) as fixture_path:
        result = validate_batch(fixture_path)
    return [
        ContractFixtureCatalogEntry(
            fixture_id=CONTRACT_FIXTURE_ID,
            contract=CONTRACT_FIXTURE_CONTRACT,
            sample_count=result.sample_count,
            page_count=result.page_count,
            resource_path=CONTRACT_FIXTURE_RESOURCE_PATH,
            manifest_resource_path=CONTRACT_FIXTURE_MANIFEST_RESOURCE_PATH,
        )
    ]


def _format_contract_fixture_catalog_entry(
    entry: ContractFixtureCatalogEntry,
) -> str:
    return (
        f"fixture_id={entry.fixture_id} "
        f"contract={entry.contract} "
        f"sample_count={entry.sample_count} "
        f"page_count={entry.page_count} "
        f"resource_path={entry.resource_path} "
        f"manifest_resource_path={entry.manifest_resource_path}"
    )


def _format_contract_fixture_catalog_json(
    catalog: list[ContractFixtureCatalogEntry],
) -> str:
    payload = {
        "schema_version": CONTRACT_FIXTURE_CATALOG_SCHEMA_VERSION,
        "fixtures": [
            {
                "fixture_id": entry.fixture_id,
                "contract": entry.contract,
                "sample_count": entry.sample_count,
                "page_count": entry.page_count,
                "resource_path": entry.resource_path,
                "manifest_resource_path": entry.manifest_resource_path,
            }
            for entry in catalog
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _format_generation_report_json(
    output_path: Path,
    *,
    sample_count: int,
    page_count: int,
    rendering_coverage_report_path: Path | None = None,
    line_annotations_path: Path | None = None,
    paired_render_path: Path | None = None,
    text_corpus: dict[str, object] | None = None,
) -> str:
    payload: dict[str, object] = {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": sample_count,
        "page_count": page_count,
        "output_path": str(output_path),
        "manifest_path": str(output_path / "generation_manifest.json"),
    }
    if rendering_coverage_report_path is not None:
        payload["rendering_coverage_report_path"] = str(
            rendering_coverage_report_path
        )
    if line_annotations_path is not None:
        payload["line_annotations_path"] = str(line_annotations_path)
    if paired_render_path is not None:
        payload["paired_render_path"] = str(paired_render_path)
    if text_corpus is not None:
        payload["text_corpus"] = text_corpus
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _text_corpus_record(text_corpus_path: Path | None) -> dict[str, object] | None:
    """Corpus provenance for run records; only present for --text-corpus runs."""

    if text_corpus_path is None:
        return None
    return {
        "source_corpus": source_corpus_id(text_corpus_path),
        "sha256": sha256_file(text_corpus_path),
    }


def _require_text_corpus_file(
    parser: argparse.ArgumentParser, command: str, text_corpus_path: Path | None
) -> None:
    if text_corpus_path is not None and not text_corpus_path.is_file():
        parser.error(f"{command}: --text-corpus is not a file: {text_corpus_path}")


def _format_contract_fixture_export_report_json(
    entry: ContractFixtureCatalogEntry,
    output_path: Path,
) -> str:
    payload: dict[str, object] = {
        "schema_version": CONTRACT_FIXTURE_EXPORT_SCHEMA_VERSION,
        "fixture_id": entry.fixture_id,
        "contract": entry.contract,
        "sample_count": entry.sample_count,
        "page_count": entry.page_count,
        "output_path": str(output_path),
        "manifest_path": str(output_path / "generation_manifest.json"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _format_contract_fixture_export_report_text(
    entry: ContractFixtureCatalogEntry,
    output_path: Path,
) -> str:
    return (
        f"fixture_id={entry.fixture_id} "
        f"contract={entry.contract} "
        f"sample_count={entry.sample_count} "
        f"page_count={entry.page_count} "
        f"output_path={output_path} "
        f"manifest_path={output_path / 'generation_manifest.json'}"
    )


def _format_valid_validation_report_json(
    path: Path, *, sample_count: int, page_count: int
) -> str:
    payload: dict[str, object] = {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "valid": True,
        "sample_count": sample_count,
        "page_count": page_count,
        "path": str(path),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _format_invalid_validation_report_json(path: Path, *, error: str) -> str:
    payload: dict[str, object] = {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "valid": False,
        "path": str(path),
        "error": error,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _copy_traversable_tree(source: Traversable, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        _copy_traversable_tree(child, destination / child.name)


def _export_contract_fixture(entry: ContractFixtureCatalogEntry, output: Path) -> None:
    if output.exists():
        raise ValueError(f"output path already exists: {output}")
    source = resources.files("hocrsyngen") / entry.resource_path
    if not source.is_dir():
        raise FileNotFoundError(entry.resource_path)
    output_parent = output.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output_parent))
    temp_output = temp_root / output.name
    try:
        _copy_traversable_tree(source, temp_output)
        result = validate_batch(temp_output)
        if (
            result.sample_count != entry.sample_count
            or result.page_count != entry.page_count
        ):
            raise ValueError(
                "exported fixture counts do not match the packaged fixture catalog: "
                f"expected {entry.sample_count} samples and {entry.page_count} pages, "
                f"got {result.sample_count} samples and {result.page_count} pages"
            )
        temp_output.rename(output)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def _contract_fixture_by_id(fixture_id: str) -> ContractFixtureCatalogEntry:
    catalog = {entry.fixture_id: entry for entry in _contract_fixture_catalog()}
    try:
        return catalog[fixture_id]
    except KeyError as exc:
        raise ValueError(f"unknown contract fixture id: {fixture_id}") from exc


class _ProgressPrinter:
    _COLORS = {
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "reset": "\033[0m",
    }

    def __init__(self, color: str) -> None:
        self._step = 0
        self._use_color = color == "always" or (
            color == "auto" and sys.stderr.isatty()
        )

    def step(self, message: str) -> float:
        self._step += 1
        self._write(
            "blue",
            f"\n[{self._step:02d}] {message}",
            bold=True,
        )
        return time.monotonic()

    def done(self, message: str, started_at: float) -> None:
        elapsed = time.monotonic() - started_at
        self._write("green", f"[ok] {message} ({elapsed:.1f}s)")

    def note(self, label: str, value: object) -> None:
        self._write("dim", f"  {label}: {value}")

    def warn(self, message: str) -> None:
        self._write("yellow", f"[warn] {message}")

    def final(self, message: str) -> None:
        self._write("magenta", f"\n{message}", bold=True)

    def _write(self, color: str, message: str, *, bold: bool = False) -> None:
        if not self._use_color:
            print(message, file=sys.stderr)
            return
        prefix = self._COLORS[color]
        if bold:
            prefix = self._COLORS["bold"] + prefix
        print(f"{prefix}{message}{self._COLORS['reset']}", file=sys.stderr)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _default_evidence_run_id(*, count: int, seed: int) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-seed{seed}-count{count}"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json_report(path: Path, text: str) -> dict[str, object]:
    _write_text(path, text + "\n")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"report payload must be a JSON object: {path}")
    return payload


def _write_checksum_inventory(root: Path, output_path: Path) -> None:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == output_path:
            continue
        relative = path.relative_to(root).as_posix()
        lines.append(f"{sha256_file(path)}  {relative}")
    _write_text(output_path, "\n".join(lines) + ("\n" if lines else ""))


def _write_evidence_run_notes(
    path: Path,
    *,
    started_at: datetime,
    count: int,
    seed: int,
    template_ids: list[str],
    run_dir: Path,
    include_rendering_coverage_report: bool,
    text_corpus: dict[str, object] | None = None,
    emit_line_annotations: bool = False,
) -> None:
    optional_notes = []
    if text_corpus is not None:
        optional_notes.append(f"- text_corpus: {text_corpus['source_corpus']}")
    if emit_line_annotations:
        optional_notes.append(f"- line_annotations: generated_batch/{LINE_ANNOTATIONS_FILENAME}")
    _write_text(
        path,
        "\n".join(
            [
                "# hocrsyngen candidate evidence run",
                "",
                "- purpose: downstream adapter preflight/import-packet evidence",
                f"- started_utc: {_format_utc(started_at)}",
                "- command boundary: hocrsyngen public CLI command",
                f"- python: {sys.executable}",
                f"- generator_version: {GENERATOR_VERSION}",
                f"- count: {count}",
                f"- seed: {seed}",
                f"- template_ids: {', '.join(template_ids)}",
                f"- rendering_coverage_report: {str(include_rendering_coverage_report).lower()}",
                *optional_notes,
                f"- output_root: {run_dir}",
                "- release_eligible: false",
                "- downstream release path: not used",
                "",
            ]
        ),
    )


def _candidate_evidence_report(
    *,
    started_at: datetime,
    completed_at: datetime,
    run_dir: Path,
    count: int,
    seed: int,
    template_ids: list[str],
    reports_dir: Path,
    fixture_batch_dir: Path,
    generated_batch_dir: Path,
    checksum_path: Path,
    rendering_coverage_report_path: Path | None,
    template_catalog_v1: dict[str, object],
    template_catalog_v2: dict[str, object],
    contracts: dict[str, object],
    fixture_export: dict[str, object],
    fixture_validation: dict[str, object],
    generation: dict[str, object],
    generated_validation: dict[str, object],
    line_annotations_path: Path | None = None,
    text_corpus: dict[str, object] | None = None,
) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": EVIDENCE_RUN_REPORT_SCHEMA_VERSION,
        "started_at_utc": _format_utc(started_at),
        "completed_at_utc": _format_utc(completed_at),
        "release_eligible": False,
        "count": count,
        "seed": seed,
        "template_ids": list(template_ids),
        "generator_version": GENERATOR_VERSION,
        "provider_runtime": _provider_runtime(),
        "output_root": str(run_dir),
        "reports_dir": str(reports_dir),
        "fixture_batch_path": str(fixture_batch_dir),
        "generated_batch_path": str(generated_batch_dir),
        "generated_manifest_path": str(generated_batch_dir / "generation_manifest.json"),
        "checksums_path": str(checksum_path),
        "rendering_coverage_report_path": (
            str(rendering_coverage_report_path)
            if rendering_coverage_report_path is not None
            else None
        ),
        "reports": {
            "template_catalog_v1": template_catalog_v1,
            "template_catalog_v2": template_catalog_v2,
            "contracts": contracts,
            "fixture_export": fixture_export,
            "fixture_validation": fixture_validation,
            "generation": generation,
            "generated_validation": generated_validation,
        },
    }
    if line_annotations_path is not None:
        report["line_annotations_path"] = str(line_annotations_path)
    if text_corpus is not None:
        report["text_corpus"] = text_corpus
    return report


def _provider_runtime() -> dict[str, object]:
    return {
        "schema_version": PROVIDER_RUNTIME_SCHEMA_VERSION,
        "used_network": False,
        "used_rest_service": False,
        "used_gpu": False,
        "used_llm": False,
        "used_diffusion": False,
        "basis": PROVIDER_RUNTIME_BASIS,
    }


def _format_evidence_run_text(report: dict[str, object]) -> str:
    return "\n".join(
        [
            "hocrsyngen evidence run complete",
            f"output_root={report['output_root']}",
            f"generated_manifest_path={report['generated_manifest_path']}",
            f"generated_batch_path={report['generated_batch_path']}",
            f"checksums_path={report['checksums_path']}",
            "release_eligible=false",
        ]
    )


def _run_evidence_capture(
    *,
    output_root: Path,
    run_id: str | None,
    count: int,
    seed: int,
    overwrite: bool,
    color: str,
    include_rendering_coverage_report: bool,
    template_ids: list[str] | None = None,
    text_corpus_path: Path | None = None,
    emit_line_annotations: bool = False,
) -> dict[str, object]:
    template_ids = list(DEFAULT_TEMPLATE_IDS if template_ids is None else template_ids)
    text_corpus = _text_corpus_record(text_corpus_path)
    progress = _ProgressPrinter(color)
    started_at = _utc_now()
    actual_run_id = run_id or _default_evidence_run_id(count=count, seed=seed)
    run_dir = output_root / actual_run_id
    reports_dir = run_dir / "reports"
    fixture_batch_dir = run_dir / "fixture_batch"
    generated_batch_dir = run_dir / "generated_batch"
    checksum_path = run_dir / "SHA256SUMS"
    evidence_report_path = run_dir / "candidate_evidence_run_report.json"
    notes_path = run_dir / "RUN_NOTES.md"

    started = progress.step("Prepare output directory")
    if run_dir.exists():
        if not overwrite:
            raise ValueError(
                f"evidence run output already exists: {run_dir} "
                "(use --overwrite to replace it)"
            )
        shutil.rmtree(run_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    progress.note("output_root", run_dir)
    progress.note("reports", reports_dir)
    progress.done("output directory ready", started)

    started = progress.step("Write run notes")
    _write_evidence_run_notes(
        notes_path,
        started_at=started_at,
        count=count,
        seed=seed,
        template_ids=template_ids,
        run_dir=run_dir,
        include_rendering_coverage_report=include_rendering_coverage_report,
        text_corpus=text_corpus,
        emit_line_annotations=emit_line_annotations,
    )
    progress.note("notes", notes_path)
    progress.done("run notes written", started)

    started = progress.step("Capture template catalog v1")
    template_catalog_v1 = _write_json_report(
        reports_dir / "template_catalog_v1.json",
        _format_template_catalog_json(template_catalog()),
    )
    progress.note("template_count", len(template_catalog_v1["templates"]))
    progress.done("template catalog v1 captured", started)

    started = progress.step("Capture template catalog v2")
    template_catalog_v2 = _write_json_report(
        reports_dir / "template_catalog_v2.json",
        _format_rich_template_catalog_json(rich_template_catalog()),
    )
    progress.note("template_count", len(template_catalog_v2["templates"]))
    progress.done("template catalog v2 captured", started)

    started = progress.step("Capture contract fixture catalog")
    fixture_catalog = _contract_fixture_catalog()
    contracts = _write_json_report(
        reports_dir / "contracts.json",
        _format_contract_fixture_catalog_json(fixture_catalog),
    )
    progress.note("fixture_count", len(contracts["fixtures"]))
    progress.done("contract fixture catalog captured", started)

    started = progress.step("Export packaged fixture batch")
    entry = _contract_fixture_by_id(CONTRACT_FIXTURE_ID)
    _export_contract_fixture(entry, fixture_batch_dir)
    fixture_export = _write_json_report(
        reports_dir / "fixture_export_report.json",
        _format_contract_fixture_export_report_json(entry, fixture_batch_dir),
    )
    progress.note("fixture_batch", fixture_batch_dir)
    progress.done("packaged fixture exported", started)

    started = progress.step("Validate packaged fixture batch")
    fixture_result = validate_batch(fixture_batch_dir)
    fixture_validation = _write_json_report(
        reports_dir / "fixture_validation_report.json",
        _format_valid_validation_report_json(
            fixture_batch_dir,
            sample_count=fixture_result.sample_count,
            page_count=fixture_result.page_count,
        ),
    )
    progress.note("valid", fixture_validation["valid"])
    progress.note("sample_count", fixture_validation["sample_count"])
    progress.note("page_count", fixture_validation["page_count"])
    progress.done("packaged fixture validated", started)

    started = progress.step(f"Generate candidate batch count={count} seed={seed}")
    progress.note("template_ids", ",".join(template_ids))
    manifest = generate_batch(
        count=count,
        seed=seed,
        output_dir=generated_batch_dir,
        template_ids=template_ids,
        text_corpus_path=text_corpus_path,
        emit_line_annotations=emit_line_annotations,
    )
    rendering_coverage_report_path = (
        write_rendering_coverage_report(manifest, generated_batch_dir)
        if include_rendering_coverage_report
        else None
    )
    line_annotations_path = (
        generated_batch_dir / LINE_ANNOTATIONS_FILENAME if emit_line_annotations else None
    )
    generation = _write_json_report(
        reports_dir / "generation_report.json",
        _format_generation_report_json(
            generated_batch_dir,
            sample_count=len(manifest.samples),
            page_count=sum(len(sample.pages) for sample in manifest.samples),
            rendering_coverage_report_path=rendering_coverage_report_path,
            line_annotations_path=line_annotations_path,
            text_corpus=text_corpus,
        ),
    )
    progress.note("generated_batch", generated_batch_dir)
    progress.note("sample_count", generation["sample_count"])
    progress.note("page_count", generation["page_count"])
    if rendering_coverage_report_path is not None:
        progress.note("rendering_coverage_report", rendering_coverage_report_path)
    if line_annotations_path is not None:
        progress.note("line_annotations", line_annotations_path)
    progress.done("candidate batch generated", started)

    started = progress.step("Validate generated candidate batch")
    generated_result = validate_batch(generated_batch_dir)
    generated_validation = _write_json_report(
        reports_dir / "generated_validation_report.json",
        _format_valid_validation_report_json(
            generated_batch_dir,
            sample_count=generated_result.sample_count,
            page_count=generated_result.page_count,
        ),
    )
    progress.note("valid", generated_validation["valid"])
    progress.note("sample_count", generated_validation["sample_count"])
    progress.note("page_count", generated_validation["page_count"])
    progress.done("generated candidate batch validated", started)

    completed_at = _utc_now()
    report = _candidate_evidence_report(
        started_at=started_at,
        completed_at=completed_at,
        run_dir=run_dir,
        count=count,
        seed=seed,
        template_ids=template_ids,
        reports_dir=reports_dir,
        fixture_batch_dir=fixture_batch_dir,
        generated_batch_dir=generated_batch_dir,
        checksum_path=checksum_path,
        rendering_coverage_report_path=rendering_coverage_report_path,
        template_catalog_v1=template_catalog_v1,
        template_catalog_v2=template_catalog_v2,
        contracts=contracts,
        fixture_export=fixture_export,
        fixture_validation=fixture_validation,
        generation=generation,
        generated_validation=generated_validation,
        line_annotations_path=line_annotations_path,
        text_corpus=text_corpus,
    )

    started = progress.step("Write candidate evidence report")
    _write_text(
        evidence_report_path,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    progress.note("report", evidence_report_path)
    progress.done("candidate evidence report written", started)

    started = progress.step("Write checksum inventory")
    _write_checksum_inventory(run_dir, checksum_path)
    progress.note("checksums", checksum_path)
    progress.done("checksum inventory written", started)

    progress.final("Candidate evidence run complete")
    progress.note("report", evidence_report_path)
    progress.note("generated_manifest", generated_batch_dir / "generation_manifest.json")
    progress.warn("release_eligible=false")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hocrsyngen")
    subparsers = parser.add_subparsers(dest="command", required=True)
    contracts = subparsers.add_parser(
        "contracts", help="List and export packaged contract fixtures."
    )
    contracts.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the packaged contract fixture catalog.",
    )
    contract_subparsers = contracts.add_subparsers(dest="contract_command")
    contracts_export = contract_subparsers.add_parser(
        "export", help="Export a packaged contract fixture batch."
    )
    contracts_export.add_argument(
        "--fixture-id",
        required=True,
        choices=(CONTRACT_FIXTURE_ID,),
        help="Packaged contract fixture id to export.",
    )
    contracts_export.add_argument(
        "--output", type=Path, required=True, help="Output directory."
    )
    contracts_export.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the export report.",
    )
    templates = subparsers.add_parser(
        "templates", help="List packaged synthetic template catalog entries."
    )
    templates.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the packaged template catalog.",
    )
    templates.add_argument(
        "--catalog-version",
        choices=("v1", "v2"),
        default="v1",
        help=(
            "Template catalog contract version. v1 preserves the original "
            "catalog shape; v2 adds richer layout metadata."
        ),
    )
    generate = subparsers.add_parser(
        "generate", help="Generate a deterministic synthetic fixture batch."
    )
    generate.add_argument(
        "--count",
        type=_non_negative_int,
        required=True,
        help="Number of samples to generate.",
    )
    generate.add_argument(
        "--seed",
        type=_non_negative_int,
        required=True,
        help="Deterministic generation seed.",
    )
    generate.add_argument(
        "--output", type=Path, required=True, help="Output directory."
    )
    generate.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the generation report.",
    )
    generate.add_argument(
        "--template-id",
        action="append",
        dest="template_ids",
        choices=GOVERNED_TEMPLATE_IDS,
        help="Template id to include. May be provided more than once.",
    )
    generate.add_argument(
        "--persona",
        choices=SUPPORTED_STYLE_BUNDLE_IDS,
        help=(
            "Synthetic style bundle id to write to controls.persona; not a "
            "real-writer identity claim."
        ),
    )
    generate.add_argument(
        "--condition",
        choices=SUPPORTED_CONDITION_BUNDLE_IDS,
        help=(
            "Synthetic rendering condition bundle id to write to controls.condition; "
            "not a real condition claim."
        ),
    )
    generate.add_argument(
        "--rendering-coverage-report",
        action="store_true",
        help=(
            "Write an opt-in rendering_coverage_report.v1 sidecar beside the "
            "manifest without changing generation_manifest.json v1."
        ),
    )
    generate.add_argument(
        "--text-corpus",
        type=Path,
        help=(
            "UTF-8 Hebrew line corpus (one line per row) to sample body text "
            "from instead of the packaged corpus. Recorded as "
            "provenance.source_corpus external:sha256:<hex>."
        ),
    )
    generate.add_argument("--plain-evaluation", action="store_true", help="Render text only at original positions for synthetic evaluation.")
    generate.add_argument("--emit-paired-render", action="store_true",
                          help="Write hash-bound pre-photometric PNG pairs and a sidecar.")
    generate.add_argument(
        "--emit-line-annotations",
        action="store_true",
        help=(
            "Write an opt-in hocrsyngen_line_annotations.v1 sidecar "
            "(line_annotations.json) with per-line polygons and baselines in "
            "final-page pixels, without changing generation_manifest.json v1."
        ),
    )
    validate = subparsers.add_parser(
        "validate", help="Validate a generated hocrsyngen fixture batch."
    )
    validate.add_argument(
        "path", type=Path, help="Generated batch directory to validate."
    )
    validate.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the validation report.",
    )
    quality = subparsers.add_parser("quality-check", help="Summarize recorded annotation quality signals.")
    quality.add_argument("path", type=Path, help="Annotated batch directory.")
    quality.add_argument("--max-truncated-segments", type=_non_negative_int)
    quality.add_argument("--max-occluded-lines", type=_non_negative_int)
    quality.add_argument("--format", choices=("text", "json"), default="text")
    wet_run = subparsers.add_parser(
        "wet-run", help="Run a deterministic wet-test artifact profile."
    )
    wet_run.add_argument(
        "--profile",
        choices=("smoke",),
        default="smoke",
        help="Wet-test profile to run.",
    )
    wet_run.add_argument(
        "--seed",
        type=_non_negative_int,
        required=True,
        help="Deterministic generation seed.",
    )
    wet_run.add_argument(
        "--output", type=Path, required=True, help="Wet-test run output directory."
    )
    wet_run.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the wet-test run summary.",
    )
    wet_run.add_argument(
        "--rendering-coverage-report",
        action="store_true",
        help=(
            "Retain an opt-in rendering_coverage_report.v1 sidecar for the "
            "generated smoke batch."
        ),
    )
    wet_gallery = subparsers.add_parser(
        "wet-gallery",
        help="Generate a static human-inspection gallery for a wet-test run.",
    )
    wet_gallery.add_argument(
        "run_root",
        type=Path,
        help="Existing wet-test run directory created by hocrsyngen wet-run.",
    )
    wet_gallery.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Gallery output directory.",
    )
    wet_gallery.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the gallery summary.",
    )
    wet_analyze = subparsers.add_parser(
        "wet-analyze",
        help="Analyze deterministic warning metrics for a wet-test run.",
    )
    wet_analyze.add_argument(
        "run_root",
        type=Path,
        help="Existing wet-test run directory created by hocrsyngen wet-run.",
    )
    wet_analyze.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the analysis summary.",
    )
    wet_review_template = subparsers.add_parser(
        "wet-review-template",
        help=(
            "Generate a human-review worksheet template for an existing wet-test "
            "run."
        ),
    )
    wet_review_template.add_argument(
        "run_root",
        type=Path,
        help="Existing wet-test run directory created by hocrsyngen wet-run.",
    )
    wet_review_template.add_argument(
        "--output",
        type=Path,
        required=True,
        help=(
            "Output review template path. Must be inside the wet-test run "
            "directory and use a .csv, .jsonl, or .ndjson extension."
        ),
    )
    wet_review_template.add_argument(
        "--review-format",
        choices=REVIEW_FORMATS,
        default="csv",
        help="Review worksheet format. Defaults to csv.",
    )
    wet_review_template.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the template summary.",
    )
    wet_review_validate = subparsers.add_parser(
        "wet-review-validate",
        help=(
            "Validate a completed human-review worksheet for an existing "
            "wet-test run."
        ),
    )
    wet_review_validate.add_argument(
        "run_root",
        type=Path,
        help="Existing wet-test run directory created by hocrsyngen wet-run.",
    )
    wet_review_validate.add_argument(
        "review_path",
        type=Path,
        help="Completed review worksheet (.csv, .jsonl, or .ndjson).",
    )
    wet_review_validate.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the validation summary.",
    )
    wet_llm_packet = subparsers.add_parser(
        "wet-llm-packet",
        help=(
            "Export a bounded LLM triage packet for an existing wet-test run. "
            "Advisory only — no LLM API calls, no network dependency."
        ),
    )
    wet_llm_packet.add_argument(
        "run_root",
        type=Path,
        help="Existing wet-test run directory created by hocrsyngen wet-run.",
    )
    wet_llm_packet.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory to write the LLM triage packet files into.",
    )
    wet_llm_packet.add_argument(
        "--max-samples",
        type=_positive_int,
        default=DEFAULT_MAX_SAMPLES,
        help=(
            f"Maximum number of samples to include in the prompt. "
            f"Defaults to {DEFAULT_MAX_SAMPLES}."
        ),
    )
    wet_llm_packet.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the packet summary report.",
    )
    wet_report = subparsers.add_parser(
        "wet-report",
        help=(
            "Aggregate a developer-facing generator-quality report over an "
            "existing wet-test run. Read-only; exits non-zero when hard "
            "blockers are present."
        ),
    )
    wet_report.add_argument(
        "run_root",
        type=Path,
        help="Existing wet-test run directory created by hocrsyngen wet-run.",
    )
    wet_report.add_argument(
        "--review",
        dest="review_path",
        type=Path,
        default=None,
        help=(
            "Optional completed review file (.csv or .jsonl). "
            "If omitted, review_summary is marked not_provided."
        ),
    )
    wet_report.add_argument(
        "--llm-packet",
        dest="llm_packet_path",
        type=Path,
        default=None,
        help=(
            "Optional llm_triage_packet.json file. "
            "If omitted, llm_triage_summary is marked not_provided."
        ),
    )
    wet_report.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the report. Defaults to text.",
    )
    evidence_run = subparsers.add_parser(
        "evidence-run",
        help="Generate a candidate batch with operator evidence and progress logs.",
    )
    evidence_run.add_argument(
        "--count",
        type=_non_negative_int,
        default=20,
        help="Number of generated candidate samples. Defaults to 20.",
    )
    evidence_run.add_argument(
        "--seed",
        type=_non_negative_int,
        default=101,
        help="Deterministic generation seed. Defaults to 101.",
    )
    evidence_run.add_argument(
        "--template-id",
        action="append",
        dest="template_ids",
        choices=GOVERNED_TEMPLATE_IDS,
        help=(
            "Template id to include. May be provided more than once. Defaults "
            "to the generate command's default templates."
        ),
    )
    evidence_run.add_argument(
        "--output-root",
        type=Path,
        default=Path(tempfile.gettempdir()) / "hocrsyngen-candidate-batches",
        help=(
            "Directory under which the timestamped evidence run directory is "
            "created. Defaults to the system temp directory."
        ),
    )
    evidence_run.add_argument(
        "--run-id",
        help=(
            "Optional explicit run directory name. Defaults to "
            "YYYYMMDDTHHMMSSZ-seedSEED-countCOUNT."
        ),
    )
    evidence_run.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output-root/run-id directory.",
    )
    evidence_run.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Colorize progress logs on stderr. Defaults to auto.",
    )
    evidence_run.add_argument(
        "--no-rendering-coverage-report",
        action="store_true",
        help=(
            "Do not write the optional rendering_coverage_report.v1 sidecar for "
            "the generated batch."
        ),
    )
    evidence_run.add_argument(
        "--text-corpus",
        type=Path,
        help=(
            "UTF-8 Hebrew line corpus (one line per row) to sample body text "
            "from instead of the packaged corpus. Recorded as "
            "provenance.source_corpus external:sha256:<hex>."
        ),
    )
    evidence_run.add_argument(
        "--emit-line-annotations",
        action="store_true",
        help=(
            "Write an opt-in hocrsyngen_line_annotations.v1 sidecar "
            "(line_annotations.json) with per-line polygons and baselines in "
            "final-page pixels, without changing generation_manifest.json v1."
        ),
    )
    evidence_run.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the final evidence-run report on stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command_line = ["hocrsyngen", *(argv if argv is not None else sys.argv[1:])]
    if (
        args.command == "templates"
        and args.catalog_version == "v2"
        and args.format != "json"
    ):
        parser.error("templates: --catalog-version v2 requires --format json")
    if args.command == "contracts":
        if args.contract_command is None:
            try:
                catalog = _contract_fixture_catalog()
            except FileNotFoundError as exc:
                parser.error(
                    f"contracts: required packaged resource is missing: {exc.filename or exc}"
                )
            except (BatchValidationError, ValueError) as exc:
                parser.error(f"contracts: {exc}")
            if args.format == "json":
                print(_format_contract_fixture_catalog_json(catalog))
            else:
                for entry in catalog:
                    print(_format_contract_fixture_catalog_entry(entry))
            return 0
        if args.contract_command == "export":
            try:
                entry = _contract_fixture_by_id(args.fixture_id)
                _export_contract_fixture(entry, args.output)
            except FileNotFoundError as exc:
                parser.error(
                    f"contracts export: required packaged resource is missing: {exc.filename or exc}"
                )
            except OSError as exc:
                parser.error(f"contracts export: {exc}")
            except (BatchValidationError, ValueError) as exc:
                parser.error(f"contracts export: {exc}")
            if args.format == "json":
                print(_format_contract_fixture_export_report_json(entry, args.output))
            else:
                print(_format_contract_fixture_export_report_text(entry, args.output))
            return 0
        raise AssertionError(f"Unhandled contracts command: {args.contract_command}")
    if args.command == "templates":
        try:
            catalog = (
                rich_template_catalog()
                if args.catalog_version == "v2"
                else template_catalog()
            )
        except FileNotFoundError as exc:
            parser.error(
                f"templates: required packaged resource is missing: {exc.filename or exc}"
            )
        except ValueError as exc:
            parser.error(f"templates: {exc}")
        if args.format == "json":
            if args.catalog_version == "v2":
                print(_format_rich_template_catalog_json(catalog))
            else:
                print(_format_template_catalog_json(catalog))
        else:
            for entry in catalog:
                print(_format_template_catalog_entry(entry))
        return 0
    if args.command == "generate":
        if args.output.exists() and not args.output.is_dir():
            parser.error(
                f"generate: output path exists and is not a directory: {args.output}"
            )
        _require_text_corpus_file(parser, "generate", args.text_corpus)
        try:
            manifest = generate_batch(
                count=args.count,
                seed=args.seed,
                output_dir=args.output,
                template_ids=args.template_ids,
                persona=args.persona,
                condition=args.condition,
                text_corpus_path=args.text_corpus,
                emit_line_annotations=args.emit_line_annotations,
                emit_paired_render=args.emit_paired_render,
                plain_evaluation=args.plain_evaluation,
            )
            rendering_coverage_report_path = (
                write_rendering_coverage_report(manifest, args.output)
                if args.rendering_coverage_report
                else None
            )
        except FileNotFoundError as exc:
            parser.error(
                f"generate: required packaged resource is missing: {exc.filename or exc}"
            )
        except (RuntimeError, ValueError) as exc:
            parser.error(f"generate: {exc}")
        if args.format == "json":
            print(
                _format_generation_report_json(
                    args.output,
                    sample_count=len(manifest.samples),
                    page_count=sum(len(sample.pages) for sample in manifest.samples),
                    rendering_coverage_report_path=rendering_coverage_report_path,
                    line_annotations_path=(
                        args.output / LINE_ANNOTATIONS_FILENAME
                        if args.emit_line_annotations
                        else None
                    ),
                    paired_render_path=(args.output / "paired_render.json" if args.emit_paired_render else None),
                    text_corpus=_text_corpus_record(args.text_corpus),
                )
            )
        return 0
    if args.command == "quality-check":
        try:
            report = quality_check(args.path, max_truncated_segments=args.max_truncated_segments,
                                   max_occluded_lines=args.max_occluded_lines)
        except (BatchValidationError, ValueError, OSError) as exc:
            parser.exit(2, f"hocrsyngen quality-check: {exc}\n")
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"Recorded quality signals: {json.dumps(report['totals'], sort_keys=True)}")
            print(f"Thresholds exceeded: {', '.join(report['exceeded']) or 'none'}")
            print(report["limitation"])
        return 1 if report["exceeded"] else 0
    if args.command == "validate":
        try:
            result = validate_batch(args.path)
        except BatchValidationError as exc:
            if args.format == "json":
                print(_format_invalid_validation_report_json(args.path, error=str(exc)))
                return 1
            parser.exit(1, f"hocrsyngen validate: {exc}\n")
        if args.format == "json":
            print(
                _format_valid_validation_report_json(
                    args.path,
                    sample_count=result.sample_count,
                    page_count=result.page_count,
                )
            )
            return 0
        print(
            f"Validated {result.sample_count} samples and {result.page_count} pages in {args.path}"
        )
        return 0
    if args.command == "wet-run":
        try:
            result = create_wet_test_smoke_run(
                output=args.output,
                seed=args.seed,
                command_line=command_line,
                rendering_coverage_report=args.rendering_coverage_report,
            )
        except FileNotFoundError as exc:
            parser.error(
                f"wet-run: required packaged resource is missing: {exc.filename or exc}"
            )
        except (BatchValidationError, RuntimeError, ValueError) as exc:
            parser.error(f"wet-run: {exc}")
        if args.format == "json":
            print(json.dumps(result.payload, ensure_ascii=False, indent=2))
            return 0
        print(
            "Wet-test smoke run wrote "
            f"{result.payload['validation']['sample_count']} samples and "
            f"{result.payload['validation']['page_count']} pages to {args.output}; "
            f"summary: {result.wet_test_run_path}"
        )
        return 0
    if args.command == "wet-gallery":
        try:
            result = create_wet_gallery(run_root=args.run_root, output=args.output)
        except (BatchValidationError, OSError, RuntimeError, ValueError) as exc:
            parser.error(f"wet-gallery: {exc}")
        if args.format == "json":
            print(json.dumps(result.payload, ensure_ascii=False, indent=2))
            return 0
        print(
            "Wet-test gallery wrote "
            f"{result.payload['page_count']} pages to {result.index_path}"
        )
        return 0
    if args.command == "wet-analyze":
        try:
            result = analyze_wet_test_run(run_root=args.run_root)
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(f"wet-analyze: {exc}")
        if args.format == "json":
            print(json.dumps(result.payload, ensure_ascii=False, indent=2))
        else:
            print(
                "Wet-test analysis inspected "
                f"{result.payload['summary']['sample_count']} samples and "
                f"{result.payload['summary']['page_count']} pages; "
                f"warnings={result.payload['summary']['warning_count']} "
                f"hard_blockers={result.payload['summary']['hard_blocker_count']}"
            )
        return 1 if result.payload["hard_blockers"] else 0
    if args.command == "wet-review-template":
        try:
            template_result = build_wet_review_template(
                run_root=args.run_root,
                output=args.output,
                review_format=args.review_format,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(f"wet-review-template: {exc}")
        if args.format == "json":
            print(json.dumps(template_result.payload, ensure_ascii=False, indent=2))
        else:
            print(
                "Wet-review template wrote "
                f"{template_result.payload['row_count']} rows to "
                f"{template_result.output} ({template_result.payload['review_format']})"
            )
        return 0
    if args.command == "wet-review-validate":
        try:
            validation_result = validate_wet_review(
                run_root=args.run_root,
                review_path=args.review_path,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(f"wet-review-validate: {exc}")
        if args.format == "json":
            print(json.dumps(validation_result.payload, ensure_ascii=False, indent=2))
        else:
            summary = validation_result.payload["summary"]
            print(
                f"Wet-review validation: valid={validation_result.payload['valid']} "
                f"errors={summary['error_count']} rows={summary['row_count']} "
                f"reviewed={summary['reviewed_page_count']} "
                f"unreviewed={summary['unreviewed_page_count']}"
            )
            print("use --format json for the full report")
        return 0 if validation_result.payload["valid"] else 1
    if args.command == "wet-llm-packet":
        try:
            triage_result = build_llm_triage_packet(
                run_root=args.run_root,
                output=args.output,
                max_samples=args.max_samples,
            )
        except (BatchValidationError, OSError, RuntimeError, ValueError) as exc:
            parser.error(f"wet-llm-packet: {exc}")
        if args.format == "json":
            print(json.dumps(triage_result.payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"LLM triage packet wrote {triage_result.payload['selected_sample_count']} "
                f"samples (of {triage_result.payload['total_sample_count']} total) to "
                f"{triage_result.output}"
            )
        return 0
    if args.command == "wet-report":
        try:
            report_result = build_wet_report(
                run_root=args.run_root,
                review_path=args.review_path,
                llm_packet_path=args.llm_packet_path,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(f"wet-report: {exc}")
        review_summary = report_result.payload.get("review_summary") or {}
        if review_summary.get("status") == "error":
            print(
                f"wet-report: review file error: {review_summary.get('error', '?')}",
                file=sys.stderr,
            )
            return 2
        if args.format == "json":
            print(json.dumps(report_result.payload, ensure_ascii=False, indent=2))
        else:
            print(format_wet_report_text(report_result.payload))
        return 1 if report_result.has_hard_blockers else 0
    if args.command == "evidence-run":
        _require_text_corpus_file(parser, "evidence-run", args.text_corpus)
        try:
            report = _run_evidence_capture(
                output_root=args.output_root,
                run_id=args.run_id,
                count=args.count,
                seed=args.seed,
                overwrite=args.overwrite,
                color=args.color,
                include_rendering_coverage_report=(
                    not args.no_rendering_coverage_report
                ),
                template_ids=args.template_ids,
                text_corpus_path=args.text_corpus,
                emit_line_annotations=args.emit_line_annotations,
            )
        except FileNotFoundError as exc:
            parser.exit(
                1,
                "hocrsyngen evidence-run: required packaged resource is missing: "
                f"{exc.filename or exc}\n",
            )
        except (BatchValidationError, OSError, RuntimeError, ValueError) as exc:
            parser.exit(1, f"hocrsyngen evidence-run: {exc}\n")
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(_format_evidence_run_text(report))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
