"""Regenerate exactly three developer previews from one project-authored page."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from hocrsyngen.cli import main as generator
from hocrsyngen.validation import validate_batch

from .batch import capture_batch
from .pipeline import read_config


DEV = Path(__file__).with_name("dev")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for the three previews")
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    cases = json.loads((DEV / "cases.json").read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix=".dev-scanifier-", dir=args.output.parent) as scratch:
        source = Path(scratch) / "source"
        generator(["generate", "--count", "1", "--seed", "20261120", "--template", "printed_letter",
                   "--output", str(source), "--text-corpus", str(DEV / "text.txt"),
                   "--plain-evaluation", "--emit-line-annotations", "--emit-paired-render"])
        override = Path(scratch) / "config.json"
        for name, case in cases.items():
            override.write_text(json.dumps(case["config"]), encoding="utf-8")
            destination = args.output / name
            capture_batch(source, destination, seed=case["seed"], config=read_config(override))
            validate_batch(destination)


if __name__ == "__main__":
    main()
