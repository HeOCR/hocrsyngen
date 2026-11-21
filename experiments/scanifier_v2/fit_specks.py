"""Fit black dust from hash-pinned 300 dpi TRAIN scans without retaining pixels."""

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

import cv2
import numpy as np
from PIL import Image


def measure(gray):
    """Count isolated 1–3 px black components in blank 128 px tiles."""
    height, width = gray.shape
    margin = 0.1 * min(gray.shape)
    counts = [[], []]
    sizes = np.zeros(3, dtype=int)
    # Require a blank guard around each tile to avoid clipped letter strokes,
    # and leave the outermost 8 px out of the measurement.
    for y in range(12, height - 132, 128):
        for x in range(12, width - 132, 128):
            patch = gray[y-4:y+132, x-4:x+132]
            if np.percentile(patch, 10) < 180:
                continue
            _, _, stats, centers = cv2.connectedComponentsWithStats((patch <= 80).astype(np.uint8), 8)
            diameters = stats[1:, 2:4].max(axis=1)
            if (diameters > 3).any():
                continue
            central = ((centers[1:] >= 4) & (centers[1:] < 132)).all(axis=1)
            diameters = diameters[central]
            edge = min(x + 64, y + 64, width - x - 64, height - y - 64) < margin
            counts[int(edge)].append(len(diameters))
            sizes += np.bincount(diameters, minlength=4)[1:4]
    return counts, sizes


def fit(records, root):
    counts = [[], []]
    sizes = np.zeros(3, dtype=int)
    for source in records:
        if source["split"] != "train":
            raise ValueError("speck fitting requires TRAIN scans")
        relative = PurePosixPath(source["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("scan path must be relative to the authorized TRAIN root")
        image = root / relative
        if hashlib.sha256(image.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"scan hash mismatch: {source['path']}")
        with Image.open(image) as opened:
            dpi = opened.info.get("dpi", ())
            if len(dpi) != 2 or any(abs(component - 300) > 1 for component in dpi):
                raise ValueError(f"speck fitting requires a native 300 dpi raster: {source['path']}")
            regions, histogram = measure(np.asarray(opened.convert("L")))
        for region, values in zip(counts, regions, strict=True):
            region.extend(values)
        sizes += histogram
    inner, edge = (np.asarray(region, dtype=float) for region in counts)
    if not len(inner) or not len(edge) or not inner.sum():
        raise ValueError("not enough blank areas or black specks to fit")
    mean = inner.mean()
    # Remove the Poisson shot term before estimating rate variation.
    clustering = math.sqrt(max(0, inner.var() - mean)) / mean
    return {
        "parameters": {
            "density_per_mpx": float(mean * 1e6 / 128**2),
            "size_weights": (sizes / sizes.sum()).tolist(),
            "clustering": float(clustering),
            "edge_gain": float(edge.mean() / mean),
            "dpi": 300,
        },
        "fit": {
            "pages": len(records),
            "blank_tiles": {"interior": len(inner), "edge": len(edge)},
            "speck_counts": {"interior": int(inner.sum()), "edge": int(edge.sum())},
            "size_histogram": sizes.tolist(),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan_manifest", type=Path, help="JSON list of TRAIN paths and SHA-256 digests")
    parser.add_argument("root", type=Path, help="local directory containing the authorized scans")
    args = parser.parse_args()
    records = json.loads(args.scan_manifest.read_bytes())
    print(json.dumps(fit(records, args.root), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
