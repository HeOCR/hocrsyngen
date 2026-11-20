"""Apply scanifier v2 to a synthetic batch with line annotations."""

import argparse
from pathlib import Path

from .batch import capture_batch
from .pipeline import read_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Synthetic generator batch")
    parser.add_argument("output", type=Path, help="New output batch directory")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--config", type=Path, help="JSON overrides for the uncalibrated priors")
    parser.add_argument("--allow-source-jpeg", action="store_true", help="Use the manifest JPEG when no paired PNG exists")
    args = parser.parse_args()
    try:
        capture_batch(args.source, args.output, seed=args.seed, config=read_config(args.config),
                      allow_source_jpeg=args.allow_source_jpeg)
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
