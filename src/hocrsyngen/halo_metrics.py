"""Halo check for composed pages: is there a grey ring around pasted glyphs that real print or handwriting lacks?

Composites that paste a glyph together with its source patch (background, grey fringe, seams) leave a ring around
each glyph. This module measures, per image:

- ``paper``: the paper level, the median of pixels at or above the 40th percentile;
- ink: pixels darker than ``paper - ink_drop`` (default 60 grey levels);
- ``ring_minus_open``: mean luminance in a ring ``ring_inner``..``ring_outer`` px from ink (default 3..6) minus the
  mean of open paper, pixels more than ``open_px`` px (default 8) from any ink. Negative = a darker ring (a halo).

The target for composites is ``|ring_minus_open| < 2`` grey levels. Real scans show a small natural ring from ink spread,
so compare with real pages of the same source too.

    python -m hocrsyngen.halo_metrics PAGE.png [PAGE.png ...] [--max-abs 2.0]

prints per-page values and the median, and exits 1 when the median's magnitude exceeds ``--max-abs``. Needs the
optional extra: ``pip install hocrsyngen[metrics]`` (numpy, scipy).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

_EXTRA_HINT = "hocrsyngen.halo_metrics needs the optional extra: pip install 'hocrsyngen[metrics]' (numpy, scipy)"


def _deps():
    try:
        import numpy
        from scipy import ndimage
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ImportError(_EXTRA_HINT) from e
    return numpy, ndimage


def measure(image, ink_drop: float = 60, ring_inner: int = 3, ring_outer: int = 6, open_px: int = 8) -> dict | None:
    """Halo measures of one image (path or PIL image); None when it has no ink or no open paper."""
    np, ndimage = _deps()
    img = image if isinstance(image, Image.Image) else Image.open(image)
    g = np.asarray(img.convert("L"), dtype=np.float32)
    paper = float(np.median(g[g >= np.percentile(g, 40)]))
    ink = g < paper - ink_drop
    if not ink.any():
        return None
    near = ndimage.binary_dilation(ink, iterations=ring_inner)
    ring = ndimage.binary_dilation(ink, iterations=ring_outer) & ~near
    far = ~ndimage.binary_dilation(ink, iterations=open_px)
    far[:2] = far[-2:] = False
    far[:, :2] = far[:, -2:] = False
    if not ring.any() or not far.any():
        return None
    return {"paper": paper, "ring_minus_open": float(g[ring].mean() - g[far].mean()),
            "ring_px": int(ring.sum()), "open_px": int(far.sum())}


def summarise(paths, **kw) -> dict:
    np, _ = _deps()
    rows = [(str(p), measure(p, **kw)) for p in paths]
    ok = [(p, m) for p, m in rows if m]
    if not ok:
        return {"n": 0, "skipped": len(rows)}
    vals = [m["ring_minus_open"] for _, m in ok]
    return {"n": len(ok), "skipped": len(rows) - len(ok), "median_ring_minus_open": float(np.median(vals)),
            "max_abs": float(max(abs(v) for v in vals)),
            "pages": [{"page": Path(p).name, "ring_minus_open": round(m["ring_minus_open"], 3)} for p, m in ok]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pages", nargs="+", type=Path)
    ap.add_argument("--max-abs", type=float, default=2.0)
    a = ap.parse_args(argv)
    s = summarise(a.pages)
    s["pass"] = bool(s.get("n")) and abs(s["median_ring_minus_open"]) <= a.max_abs
    print(json.dumps(s, indent=1))
    return 0 if s["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
