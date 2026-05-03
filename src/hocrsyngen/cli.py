from __future__ import annotations

import argparse
from pathlib import Path

from hocrsyngen.generator import DEFAULT_TEMPLATE_IDS, generate_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hocrsyngen")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate a deterministic synthetic fixture batch.")
    generate.add_argument("--count", type=int, required=True, help="Number of samples to generate.")
    generate.add_argument("--seed", type=int, required=True, help="Deterministic generation seed.")
    generate.add_argument("--output", type=Path, required=True, help="Output directory.")
    generate.add_argument(
        "--template-id",
        action="append",
        dest="template_ids",
        choices=DEFAULT_TEMPLATE_IDS,
        help="Template id to include. May be provided more than once.",
    )
    generate.add_argument("--persona", help="Optional generator control only; not a real-writer identity claim.")
    generate.add_argument("--condition", help="Optional generator control only; not a real condition claim.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        generate_batch(
            count=args.count,
            seed=args.seed,
            output_dir=args.output,
            template_ids=args.template_ids,
            persona=args.persona,
            condition=args.condition,
        )
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
