"""Measure scan properties of line crops: background level, contrast, texture, speckle, blur, stroke and gap.

  measure.py OUT.json NAME=LISTFILE_OR_GLOB ... [--n 400] [--seed 1]

Each input is a list of .png / .lstmf paths (the .png next to the .lstmf is used).
"""
import argparse, glob, json, random
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage


def otsu(a):
    h = np.bincount(a.ravel(), minlength=256).astype(float); p = h / h.sum()
    w = np.cumsum(p); m = np.cumsum(p * np.arange(256)); mt = m[-1]
    s = (mt * w - m) ** 2 / np.maximum(w * (1 - w), 1e-12)
    return int(np.argmax(s))


def stats(path):
    a = np.asarray(Image.open(path).convert("L")).astype(np.int32)
    if a.shape[0] < 12 or a.shape[1] < 40:
        return None
    t = otsu(a.astype(np.uint8)); ink = a <= t; bg = ~ndimage.binary_dilation(ink, iterations=2)
    if ink.sum() < 30 or bg.sum() < 100:
        return None
    bgv, inkv = a[bg], a[ink]
    # texture: background after removing slow shading (median filter 15)
    smooth = ndimage.median_filter(a, size=15)
    resid = (a - smooth)[bg]
    lab, n = ndimage.label(ink); sizes = ndimage.sum(ink, lab, range(1, n + 1)) if n else np.array([])
    speck = int((sizes <= 4).sum())
    # blur: 10-90% edge rise width along x on strong edges, approximated by contrast / max gradient
    gx = np.abs(np.diff(a, axis=1)); gy = np.abs(np.diff(a, axis=0))
    contrast = float(np.median(bgv) - np.median(inkv))
    sharp = float(np.percentile(np.concatenate([gx.ravel(), gy.ravel()]), 99.5) / max(1.0, contrast))
    # stroke width (2 x median distance-transform ridge) and height of the line's ink band
    dt = ndimage.distance_transform_edt(ink)
    rows = np.where(ink.mean(1) > 0.02)[0]
    band = float(rows[-1] - rows[0] + 1) if len(rows) else float(a.shape[0])
    stroke = float(2 * np.median(dt[ink & (dt >= ndimage.maximum_filter(dt, 3))]))
    # gap: white runs inside letters along rows in the band, as fraction of band height (small = closing risk)
    runs = []
    for y in rows[:: max(1, len(rows) // 8)]:
        r = ink[y]; idx = np.flatnonzero(np.diff(r.astype(int)))
        for s0, s1 in zip(idx[1::2], idx[2::2]):
            if 0 < s1 - s0 <= band * 0.5:
                runs.append(s1 - s0)
    return {"h": a.shape[0], "band": band, "bg": float(np.median(bgv)), "ink": float(np.median(inkv)), "contrast": contrast,
            "bg_std": float(bgv.std()), "texture": float(resid.std()), "speck_per_kpx": 1000 * speck / max(1, bg.sum()),
            "sharp": sharp, "stroke_rel": stroke / band, "gap_p10_rel": float(np.percentile(runs, 10) / band) if runs else None,
            "ink_frac": float(ink.mean())}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("sets", nargs="+")
    ap.add_argument("--n", type=int, default=400); ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(); res = {}
    for s in a.sets:
        name, src = s.split("=", 1)
        paths = Path(src).read_text().split() if Path(src).is_file() else glob.glob(src)
        paths = [p[:-6] + ".png" if p.endswith(".lstmf") else p for p in paths]
        random.Random(a.seed).shuffle(paths)
        rows = [r for r in (stats(p) for p in paths[: a.n * 2]) if r][: a.n]
        res[name] = {k: {"p10": round(float(np.percentile([r[k] for r in rows if r[k] is not None], 10)), 4),
                         "p50": round(float(np.median([r[k] for r in rows if r[k] is not None])), 4),
                         "p90": round(float(np.percentile([r[k] for r in rows if r[k] is not None], 90)), 4)} for k in rows[0]}
        res[name]["_n"] = len(rows)
    json.dump(res, open(a.out, "w"), indent=1)
    keys = [k for k in next(iter(res.values())) if k != "_n"]
    print("metric".ljust(14) + "".join(n[:16].rjust(18) for n in res))
    for k in keys:
        print(k.ljust(14) + "".join(f"{res[n][k]['p50']:>8} ({res[n][k]['p10']}-{res[n][k]['p90']})".rjust(18)[-18:] for n in res))


if __name__ == "__main__":
    main()
