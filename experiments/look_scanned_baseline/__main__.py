"""Apply Look Scanned effects to a local page image."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image

from . import ScanEffects, apply_scan_effects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--effects", type=Path, help="JSON object of ScanEffects settings")
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    effects = ScanEffects(**json.loads(args.effects.read_text())) if args.effects else ScanEffects()
    with Image.open(args.input) as source:
        result = apply_scan_effects(source, effects, seed=args.seed)
    result.image.save(args.output)
    print(json.dumps({
        "effects": asdict(effects),
        "seed": args.seed,
        "rotation_deg": result.rotation_deg,
        "source_size": result.source_size,
        "output_size": result.image.size,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
