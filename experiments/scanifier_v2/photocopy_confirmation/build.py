"""Build the approved-profile confirmation gallery from screened CC0 copy."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from experiments.scanifier_v2.realism_v2_preview import build_preview as preview
from experiments.scanifier_v2.train_realism import render_train_scanner

HERE = Path(__file__).resolve().parent
COPY = HERE.parent / "realism_v2_preview/copy.json"
SOURCE = COPY.with_name("generation_manifest.json")
EXAMPLES = ("mild",) * 6 + ("medium",) * 3 + ("hard",)
PPI = 200


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def build(out):
    out.mkdir(parents=True)
    copy = json.loads(COPY.read_text())
    source = json.loads(SOURCE.read_text())
    # The v2 manifest can repeat the same text across both sides and many pairs.
    def find_label_hashes(value):
        if isinstance(value, dict):
            if "label_sha256" in value:
                yield value["label_sha256"]
            for entry in value.values():
                yield from find_label_hashes(entry)
        elif isinstance(value, list):
            for entry in value:
                yield from find_label_hashes(entry)

    screened = set(find_label_hashes(source))
    rows = []
    for i, band in enumerate(EXAMPLES):
        heading, body = copy["headings"][i], copy["blocks"][(i//5 + i % 5) % 4]
        image, labels = preview.recto(heading, body, family="Platen and photocopy", style=(0, 2, 2, 3, 4)[i % 5], treated=True)
        lines = [{"box": line["box_xyxy"], "text": line["text"], "label_sha256": line["label_sha256"]} for line in labels]
        assert {line["label_sha256"] for line in lines} <= screened
        clean_ink = [np.count_nonzero(np.asarray(image.crop(line["box"]).convert("L")) < 120) for line in lines]
        for attempt in range(40):
            seed = 26012400 + i * 100 + attempt
            view = render_train_scanner(image, lines, profile="photocopy", band=band, source_ppi=PPI, seed=seed)
            ratios = [
                np.count_nonzero(~np.asarray(view.image.crop(line["box"]))) / max(1, count)
                for line, count in zip(view.lines, clean_ink, strict=True)
            ]
            if min(ratios) >= .38:
                break
        else:
            raise ValueError(f"No ink-preserving {band} draw for pair {i + 1}")
        assert view.image.mode == "1"
        assert [line["text"] for line in view.lines] == [line["text"] for line in lines]
        for line in view.lines:
            x1, y1, x2, y2 = line["box"]
            assert 0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height
        pair = {"id": i + 1, "band": band, "seed": seed, "rejected_draws": attempt, "min_line_ink_ratio": round(min(ratios), 4), "parameters": view.parameters,
                "label_sha256": [line["label_sha256"] for line in lines]}
        for side, raster in (("control", image), ("photocopy", view.image)):
            path = out / f"{i+1:02}-{side}.png"
            raster.save(path, optimize=True)
            pair[side] = {"path": path.relative_to(out.parent).as_posix(), "sha256": digest(path)}
        rows.append(pair)
    (out.parent / "generation_manifest.json").write_text(json.dumps({
        "schema": "heocr.photocopy_confirmation.v1", "licence": "CC0-1.0", "copy_sha256": digest(COPY),
        "screened_manifest_sha256": digest(SOURCE), "source_ppi": PPI, "pairs": rows,
    }, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "images")
    build(parser.parse_args().output)
