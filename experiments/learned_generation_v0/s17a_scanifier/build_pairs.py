"""S17a: build pixel-aligned (clean render, real crop) line pairs from bynli_lines_v2.

For each train line:
1. Run R7 Tesseract (psm 7, hOCR char boxes) on the real crop.
2. Keep the line only if Tesseract's characters, spaces removed, equal the label's.
   That makes each box map to exactly one label character.
3. Tighten each Tesseract box to the union of ink components (Otsu mask) whose
   centroid falls inside it.
4. Draw the font glyph for that character, ink-cropped, scaled into the tightened box,
   black on white, on a canvas the size of the crop.

Writes <out>/pairs/<id>_{render,real}.png and <out>/pairs.jsonl.
Train split only: no dev or test lines, so no scored or held-out scans are used.
"""
import argparse, json, os, re, subprocess, sys, tempfile, hashlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

LINES = Path(os.path.expanduser(
    "~/agents/environments/opensource/projects/heocr/tasks/s16c-glyph-scale/outputs/lines/bynli_lines_v2"))
R7 = Path(os.path.expanduser(
    "~/agents/environments/opensource/projects/heocr/tasks/r7-tesseract-real/models/r7"))
FONTS = Path(os.path.expanduser("~/clones/hocrsyngen/src/hocrsyngen/data/synthetic/fonts"))
CINFO = re.compile(r"<span class='ocrx_cinfo' title='x_bboxes (\d+) (\d+) (\d+) (\d+);[^']*'>([^<]*)</span>")

_glyph_cache = {}


def glyph(ch, font_path):
    key = (ch, font_path)
    if key not in _glyph_cache:
        f = ImageFont.truetype(font_path, 96)
        im = Image.new("L", (200, 200), 255)
        ImageDraw.Draw(im).text((50, 40), ch, font=f, fill=0)
        a = np.asarray(im) < 128
        if not a.any():
            _glyph_cache[key] = None
        else:
            ys, xs = np.nonzero(a)
            _glyph_cache[key] = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return _glyph_cache[key]


def otsu(a):
    hist = np.bincount(a.ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w = np.cumsum(p); mu = np.cumsum(p * np.arange(256)); mt = mu[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (mt * w - mu) ** 2 / (w * (1 - w))
    return int(np.nanargmax(s))


def process(args):
    row, out, font_path = args
    src = LINES / row["image"]
    real = Image.open(src).convert("L")
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "o"
        subprocess.run(["tesseract", str(src), str(base), "--tessdata-dir", str(R7), "-l", "heb",
                        "--psm", "7", "-c", "hocr_char_boxes=1", "hocr"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        try:
            hocr = (base.with_suffix(".hocr")).read_text()
        except FileNotFoundError:
            return None
    chars = [(int(a), int(b), int(c), int(d), t) for a, b, c, d, t in CINFO.findall(hocr)]
    chars = [c for c in chars if c[4].strip()]
    label = row["text"].replace(" ", "")
    if "".join(c[4] for c in chars) != label or not chars:
        return {"id": row["id"], "kept": False}
    a = np.asarray(real)
    mask = a < otsu(a)
    lab, n = ndimage.label(mask)
    objs = ndimage.find_objects(lab)
    cents = ndimage.center_of_mass(mask, lab, range(1, n + 1)) if n else []
    canvas = Image.new("L", real.size, 255)
    sizes = ndimage.sum(mask, lab, range(1, n + 1)) if n else []
    # Assign every ink component to exactly one character: the one whose box
    # centre is nearest in x among boxes containing its centroid (or within 3 px).
    boxes = [None] * len(chars)
    if n:
        med_size = float(np.median(sizes))
        med_bottom = float(np.median([sl[0].stop for sl in objs]))
        med_top = float(np.median([sl[0].start for sl in objs]))
    for k, (cy, cx) in enumerate(cents):
        sl = objs[k]
        # Specks: much smaller than a typical letter. Strays: wholly below the line band or above it.
        if sizes[k] < max(4, 0.08 * med_size) or sl[0].start >= med_bottom - 1 or sl[0].stop <= med_top + 1:
            continue
        best, bd = None, None
        for i, (x0, y0, x1, y1, _) in enumerate(chars):
            if x0 - 3 <= cx <= x1 + 3 and y0 - 6 <= cy <= y1 + 6:
                d = abs(cx - (x0 + x1) / 2)
                if bd is None or d < bd:
                    best, bd = i, d
        if best is None:
            continue
        sl = objs[k]
        b = (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)
        o = boxes[best]
        boxes[best] = b if o is None else (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
    # Reject the line if any character got no ink, or an ink box much wider than its Tesseract box.
    for (x0, y0, x1, y1, ch), b in zip(chars, boxes):
        if b is None or (b[2] - b[0]) > 1.6 * max(x1 - x0, 4) + 2:
            return {"id": row["id"], "kept": False, "reason": "box"}
    snapped = len(chars)
    for (_, _, _, _, ch), box in zip(chars, boxes):
        g = glyph(ch, font_path)
        w, h = box[2] - box[0], box[3] - box[1]
        if g is None or w < 1 or h < 1:
            continue
        canvas.paste(g.resize((w, h), Image.LANCZOS), (box[0], box[1]))
    pairs = Path(out) / "pairs"
    rp, tp = pairs / f"{row['id']}_render.png", pairs / f"{row['id']}_real.png"
    canvas.save(rp); real.save(tp)
    return {"id": row["id"], "kept": True, "book": row["book"], "record_id": row["record_id"],
            "text": row["text"], "n_chars": len(chars), "snapped": snapped,
            "size": list(real.size), "render": str(rp.relative_to(out)), "real": str(tp.relative_to(out)),
            "real_sha256": row["image_sha256"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--every", type=int, default=1, help="take every Nth train line")
    ap.add_argument("--font", default="FrankRuhlLibre-wght.ttf")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out); (out / "pairs").mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in open(LINES / "manifest.jsonl")]
    rows = [r for r in rows if r["split"] == "train"][:: a.every]
    if a.limit:
        rows = rows[: a.limit]
    font_path = str(FONTS / a.font)
    kept = tried = 0
    with open(out / "pairs.jsonl", "w") as fo, ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(process, [(r, str(out), font_path) for r in rows], chunksize=16):
            if res is None:
                continue
            tried += 1
            if res["kept"]:
                kept += 1
                fo.write(json.dumps(res, ensure_ascii=False) + "\n")
    summary = {"tried": tried, "kept": kept, "font": a.font, "every": a.every, "limit": a.limit,
               "manifest_sha256": hashlib.sha256(open(LINES / "manifest.jsonl", "rb").read()).hexdigest()}
    json.dump(summary, open(out / "summary.json", "w"), indent=1)
    print(summary)


if __name__ == "__main__":
    main()
