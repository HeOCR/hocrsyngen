"""R8c scan augmentation: degrade line crops toward the Brainin IA scan (small, sharpened, grainy, speckled, dark).

  scan_aug.py LIST OUT_DIR [--ops downscale,unsharp,jpeg,levels,grain,speckle] [--strength 1.0] [--share 1.0]
              [--seed 20261112] [--upscale-band 0] [--workers 8]

LIST holds .lstmf paths; the .png and .gt.txt next to each are read. For each picked line, writes OUT_DIR/<stem>.png,
<stem>.gt.txt (copied unchanged) and an OUT_DIR/aug.list of placeholder .lstmf paths (build lstmf separately).
Lines not picked (share < 1) are not written. OUT_DIR/aug_params.jsonl records every draw.

Ops (applied in this order; each draw is seeded by (seed, line stem); strength k in [0, 1] scales every range):
  levels    background -> N(165, 8), ink -> 40 (linear map of the line's medians); expected no-op for Tesseract
  speckle   dark 1-6 px blobs, density U(0.04, 0.12) per 1k px * k
  downscale area-resample so the letter band becomes band - k * (band - U(24, 34)) px (never upscaled back)
  blur      Gaussian sigma k * U(0.4, 0.7)  (optional; not in the default set)
  unsharp   unsharp mask radius 1, amount k * U(50, 120) %
  grain     additive Gaussian sigma k * U(2.5, 4) plus low-frequency mottling sigma k * 3
  jpeg      quality 95 - k * (95 - U(55, 85))
--upscale-band B (diagnostic, not an augmentation): Lanczos-upscale each line so its band is B px; no other op.
"""
import argparse, hashlib, io, json, random, shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

DEFAULT_OPS = "levels,speckle,downscale,unsharp,grain,jpeg"


def otsu(a):
    h = np.bincount(a.ravel(), minlength=256).astype(float); p = h / h.sum()
    w = np.cumsum(p); m = np.cumsum(p * np.arange(256))
    return int(np.argmax((m[-1] * w - m) ** 2 / np.maximum(w * (1 - w), 1e-12)))


def band_of(a):
    ink = a <= otsu(a)
    rows = np.where(ink.mean(1) > 0.02)[0]
    return float(rows[-1] - rows[0] + 1) if len(rows) else float(a.shape[0]), ink


def augment(img, ops, k, rng, upscale_band=0):
    a = np.asarray(img.convert("L"), dtype=np.uint8)
    band, ink = band_of(a)
    p = {"band_in": band}
    if upscale_band:
        f = upscale_band / max(band, 1)
        p["scale"] = round(f, 4)
        if f > 1:
            img = img.convert("L").resize((round(a.shape[1] * f), round(a.shape[0] * f)), Image.LANCZOS)
        return img, p
    x = a.astype(np.float32)
    if "levels" in ops:
        bgm, inkm = float(np.median(a[~ink])), float(np.median(a[ink]))
        bg_t = bgm - k * (bgm - rng.gauss(165, 8)); ink_t = inkm - k * (inkm - 40)
        x = (x - inkm) / max(bgm - inkm, 1) * (bg_t - ink_t) + ink_t
        p["levels"] = [round(bg_t, 1), round(ink_t, 1)]
    if "speckle" in ops:
        d = k * rng.uniform(0.04, 0.12); n = np.random.default_rng(rng.getrandbits(32)).poisson(d * x.size / 1000)
        ink_v = float(np.percentile(x, 5))
        for _ in range(n):
            s = rng.randint(1, 6); cy, cx = rng.randrange(x.shape[0]), rng.randrange(x.shape[1])
            r = max(1, int(round(np.sqrt(s / np.pi))))
            yy, xx = np.ogrid[-r:r + 1, -r:r + 1]; m = (yy ** 2 + xx ** 2) <= max(1, s / np.pi)
            y0, x0 = max(0, cy - r), max(0, cx - r); y1, x1 = min(x.shape[0], cy + r + 1), min(x.shape[1], cx + r + 1)
            sub = m[y0 - (cy - r):y1 - (cy - r), x0 - (cx - r):x1 - (cx - r)]
            x[y0:y1, x0:x1][sub] = ink_v + rng.uniform(0, 30)
        p["speckle"] = [round(d, 4), int(n)]
    img = Image.fromarray(np.clip(x, 0, 255).astype(np.uint8))
    if "downscale" in ops:
        tgt = band - k * (band - rng.uniform(24, 34))
        f = min(1.0, tgt / max(band, 1))
        if f < 1:
            img = img.resize((max(8, round(img.width * f)), max(8, round(img.height * f))), Image.BOX)
        p["scale"] = round(f, 4)
    if "blur" in ops:
        s = k * rng.uniform(0.4, 0.7); img = img.filter(ImageFilter.GaussianBlur(s)); p["blur"] = round(s, 3)
    if "unsharp" in ops:
        amt = int(k * rng.uniform(50, 120)); img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=amt, threshold=0))
        p["unsharp"] = amt
    if "grain" in ops:
        g = np.random.default_rng(rng.getrandbits(32)); x = np.asarray(img, dtype=np.float32)
        s = k * rng.uniform(2.5, 4); x = x + g.normal(0, s, x.shape)
        low = ndimage.zoom(g.normal(0, 1, (max(2, x.shape[0] // 8), max(2, x.shape[1] // 8))),
                           (x.shape[0] / max(2, x.shape[0] // 8), x.shape[1] / max(2, x.shape[1] // 8)), order=1)
        x = x + k * 3 * low[: x.shape[0], : x.shape[1]]
        img = Image.fromarray(np.clip(x, 0, 255).astype(np.uint8)); p["grain"] = round(s, 3)
    if "jpeg" in ops:
        q = int(round(95 - k * (95 - rng.uniform(55, 85)))); buf = io.BytesIO(); img.save(buf, "JPEG", quality=q)
        img = Image.open(io.BytesIO(buf.getvalue())).convert("L"); p["jpeg"] = q
    return img, p


def job(args):
    lstmf, out, ops, k, seed, upb = args
    stem = Path(lstmf).stem
    rng = random.Random(int(hashlib.sha256(f"{seed}:{stem}".encode()).hexdigest()[:16], 16))
    img, p = augment(Image.open(lstmf[:-6] + ".png"), ops, k, rng, upb)
    img.save(Path(out) / f"{stem}.png")
    shutil.copyfile(lstmf[:-6] + ".gt.txt", Path(out) / f"{stem}.gt.txt")
    return {"stem": stem, "src": lstmf, **p}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list"); ap.add_argument("out")
    ap.add_argument("--ops", default=DEFAULT_OPS); ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--share", type=float, default=1.0); ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--upscale-band", type=float, default=0); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    paths = Path(a.list).read_text().split()
    pick = [p for p in paths if random.Random(f"{a.seed}:share:{Path(p).stem}").random() < a.share]
    ops = set(a.ops.split(",")) if a.ops else set()
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(job, [(p, str(out), ops, a.strength, a.seed, a.upscale_band) for p in pick], chunksize=32))
    with open(out / "aug_params.jsonl", "w") as fo:
        for r in rows:
            fo.write(json.dumps(r) + "\n")
    (out / "aug.list").write_text("".join(str(out / f"{r['stem']}.lstmf") + "\n" for r in rows))
    json.dump({"list": a.list, "ops": sorted(ops), "strength": a.strength, "share": a.share, "seed": a.seed,
               "upscale_band": a.upscale_band, "lines_in": len(paths), "lines_out": len(rows)},
              open(out / "aug_summary.json", "w"), indent=1)
    print(len(paths), "->", len(rows), sorted(ops), a.strength)


if __name__ == "__main__":
    main()
