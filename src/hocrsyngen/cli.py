from __future__ import annotations

import argparse
from pathlib import Path

from hocrsyngen.generator import (
    DEFAULT_TEMPLATE_IDS,
    TemplateCatalogEntry,
    generate_batch,
    template_catalog,
)
from hocrsyngen.validation import BatchValidationError, validate_batch


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hocrsyngen")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "templates", help="List packaged synthetic template catalog entries."
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
        "--template-id",
        action="append",
        dest="template_ids",
        choices=DEFAULT_TEMPLATE_IDS,
        help="Template id to include. May be provided more than once.",
    )
    generate.add_argument(
        "--persona",
        help="Optional generator control only; not a real-writer identity claim.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "templates":
        try:
            catalog = template_catalog()
        except FileNotFoundError as exc:
            parser.error(
                f"templates: required packaged resource is missing: {exc.filename or exc}"
            )
        except ValueError as exc:
            parser.error(f"templates: {exc}")
        for entry in catalog:
            print(_format_template_catalog_entry(entry))
        return 0
    if args.command == "generate":
        if args.output.exists() and not args.output.is_dir():
            parser.error(
                f"generate: output path exists and is not a directory: {args.output}"
            )
        try:
            generate_batch(
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
        return 0
    if args.command == "validate":
        try:
            result = validate_batch(args.path)
        except BatchValidationError as exc:
            parser.exit(1, f"hocrsyngen validate: {exc}\n")
        print(
            f"Validated {result.sample_count} samples and {result.page_count} pages in {args.path}"
        )
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
