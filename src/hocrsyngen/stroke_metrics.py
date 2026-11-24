"""Stroke-weight and letter-size gate for composed pages against real lines.

Composed pages can come out lighter and thinner than the real lines their glyphs were cut from: smaller letters
(a fixed line pitch) and eroded strokes (thresholding after a downscale). This module measures, per image:

- ``stroke``: 2 x the median distance-transform value on the ink ridge, the typical stroke width in px;
- ``body``: the median height of letter-sized ink components, in px;
- ``rel``: stroke / body, scale-free; the number to match;
- ``ink``: the share of pixels that are ink.

Binarisation is Otsu on grey images, and a fixed 128 threshold on images that are already two-level.

    python -m hocrsyngen.stroke_metrics COMPOSED_DIR REFERENCE_DIR [--max-rel-gap 0.10]

compares the medians of two folders of PNGs and exits 1 when the relative stroke weights differ by more than
``--max-rel-gap`` (default 10%). Needs the optional extra: ``pip install hocrsyngen[metrics]`` (numpy, scipy).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

_EXTRA_HINT = "hocrsyngen.stroke_metrics needs the optional extra: pip install 'hocrsyngen[metrics]' (numpy, scipy)"


def _deps():
    """numpy and scipy.ndimage, imported lazily so the baseline install (jsonschema, Pillow) never needs them."""
    try:
        import numpy
        from scipy import ndimage
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ImportError(_EXTRA_HINT) from e
    return numpy, ndimage


def _ink(gray):
    np, _ = _deps()
    if len(np.unique(gray)) <= 2:
        return gray < 128
    hist, _ = np.histogram(gray, 256, (0, 256))
    p = hist / hist.sum()
    w = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    t = int(np.argmax((mu[-1] * w - mu) ** 2 / (w * (1 - w) + 1e-9)))
    return gray < max(t, 1)


def measure(image) -> dict | None:
    """Stroke, body, stroke/body and ink cover of one image (path or PIL image); None if it has almost no ink."""
    np, ndimage = _deps()
    img = image if isinstance(image, Image.Image) else Image.open(image)
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    ink = _ink(gray)
    if ink.sum() < 50:
        return None
    dt = ndimage.distance_transform_edt(ink)
    ridge = (dt >= ndimage.maximum_filter(dt, 3)) & ink
    lab, _ = ndimage.label(ink)
    heights = [s[0].stop - s[0].start for s in ndimage.find_objects(lab) if s is not None]
    heights = [h for h in heights if h >= 0.3 * np.percentile(heights, 90)]
    body = float(np.median(heights))
    stroke = 2.0 * float(np.median(dt[ridge]))
    return {"stroke": stroke, "body": body, "rel": stroke / body, "ink": float(ink.mean())}


def summarise(paths) -> dict:
    np, _ = _deps()
    ms = [m for m in (measure(p) for p in paths) if m]
    if not ms:
        return {"n": 0}
    return {"n": len(ms), **{k: float(np.median([m[k] for m in ms])) for k in ("stroke", "body", "rel", "ink")}}


def compare(composed, reference, max_rel_gap: float = 0.10) -> dict:
    a, b = summarise(composed), summarise(reference)
    gap = abs(a["rel"] - b["rel"]) / b["rel"] if a.get("n") and b.get("n") else None
    return {"composed": a, "reference": b, "rel_gap": gap, "pass": gap is not None and gap <= max_rel_gap}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("composed", type=Path)
    ap.add_argument("reference", type=Path)
    ap.add_argument("--max-rel-gap", type=float, default=0.10)
    a = ap.parse_args(argv)
    r = compare(sorted(a.composed.glob("*.png")), sorted(a.reference.glob("*.png")), a.max_rel_gap)
    print(json.dumps(r, indent=1))
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
