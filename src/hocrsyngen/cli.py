from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from hocrsyngen.generator import (
    GOVERNED_TEMPLATE_IDS,
    SUPPORTED_STYLE_BUNDLE_IDS,
    TemplateCatalogEntry,
    generate_batch,
    template_catalog,
)
from hocrsyngen.validation import BatchValidationError, validate_batch


CONTRACT_FIXTURE_CATALOG_SCHEMA_VERSION = "contract_fixture_catalog.v1"
CONTRACT_FIXTURE_EXPORT_SCHEMA_VERSION = "contract_fixture_export.v1"
GENERATION_REPORT_SCHEMA_VERSION = "generation_report.v1"
TEMPLATE_CATALOG_SCHEMA_VERSION = "template_catalog.v1"
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
    output_path: Path, *, sample_count: int, page_count: int
) -> str:
    payload: dict[str, object] = {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": sample_count,
        "page_count": page_count,
        "output_path": str(output_path),
        "manifest_path": str(output_path / "generation_manifest.json"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


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
        help="Optional generator control only; not a real condition claim.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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
            catalog = template_catalog()
        except FileNotFoundError as exc:
            parser.error(
                f"templates: required packaged resource is missing: {exc.filename or exc}"
            )
        except ValueError as exc:
            parser.error(f"templates: {exc}")
        if args.format == "json":
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
        try:
            manifest = generate_batch(
                count=args.count,
                seed=args.seed,
                output_dir=args.output,
                template_ids=args.template_ids,
                persona=args.persona,
                condition=args.condition,
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
                )
            )
        return 0
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
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
