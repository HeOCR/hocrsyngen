"""S17a text-consistency gates (agreed with heocr-lead, 2026-11-11).

  gates.py GEN_DIR [--best PATH] [--sheet]

GEN_DIR holds generate.py output: g{k}.png, g{k}_render.png and gen.jsonl.
Writes GEN_DIR/gates.jsonl (one row per line) and GEN_DIR/gates_summary.json.

Gate 1, the ink check: mandatory, and no OCR is involved.
  a. ink_outside: more than OUT_FRAC of the output's ink (Otsu) lies outside the render's
     glyph mask dilated by DIL px, or, in some WIN-px column window, at least LOC_PX outside
     pixels make up more than LOC_FRAC of that window's ink (an added stroke). Heavy styles
     spread ink evenly and pass the local test.
  b. glyph_no_ink: a render glyph (connected component) has less than COVER of its pixels
     inked in the output.
  c. stray_cc: more than STRAY_MAX output ink components (>= SPECK px), centred inside the
     letter band, lie mostly (> 50%) outside the dilated glyph mask. Off-band strays (edge
     fragments of neighbouring lines, taller lamed ascenders) are only counted, not rejected. This replaces a raw component-count comparison: scan
     texture breaks thin strokes, so good outputs have 20-70% more components than the render.
Gate 2, gross-failure read-back: reject only if BOTH R7 and tessdata_best read the line at
  CER > 0.25 against the intended text. Labels are always the intended text.
Rows also carry the style crop's book and the character classes, so acceptance can be
reported per style book and per class.
"""
import argparse, json, subprocess, sys, tempfile, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from build_pairs import otsu  # noqa: E402
from generate import lev, R7  # noqa: E402

BEST = Path.home() / "agents/environments/opensource/projects/heocr/tasks/r5-tesseract-ft/models/best"
DIL, OUT_FRAC, COVER, STRAY_MAX, SPECK = 3, 0.06, 0.30, 0, 6
WIN, LOC_PX, LOC_FRAC = 16, 6, 0.03
GROSS = 0.25


def read(path, tessdir):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["tesseract", str(path), f"{td}/o", "--tessdata-dir", str(tessdir), "-l", "heb", "--psm", "7"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Path(f"{td}/o.txt").read_text().strip()


def cer(hyp, ref):
    h, r = hyp.replace(" ", ""), ref.replace(" ", "")
    return lev(h, r) / max(1, len(r))


def ink_check(gen_png, ren_png):
    g = np.asarray(Image.open(gen_png).convert("L"))
    r = np.asarray(Image.open(ren_png).convert("L"))
    w = min(g.shape[1], r.shape[1]); g, r = g[:, :w], r[:, :w]
    ink = g < otsu(g)
    glyphs = r < 128
    near = ndimage.binary_dilation(glyphs, iterations=DIL)
    lab_r, nr0 = ndimage.label(glyphs)
    rs = ndimage.sum(glyphs, lab_r, range(1, nr0 + 1)) if nr0 else []
    keep = [i + 1 for i, s in enumerate(rs) if s >= SPECK]  # drop anti-alias fragments
    nr = len(keep)
    # Letter band: median top to median bottom of the render's glyphs, +-2 px. Edge fragments
    # of neighbouring lines and taller lamed ascenders fall outside it and are scan realism.
    if keep:
        objs = ndimage.find_objects(lab_r)
        b0 = float(np.median([objs[i - 1][0].start for i in keep])) - 2
        b1 = float(np.median([objs[i - 1][0].stop for i in keep])) + 2
    else:
        b0, b1 = 0.0, float(g.shape[0])
    band = np.zeros_like(ink); band[max(0, int(b0)):int(np.ceil(b1)) + 1] = True
    outside = ink & ~near
    out_frac = float((outside & band).sum() / max(1, (ink & band).sum()))
    # Local check in the band: heavy inking spreads evenly, but an added stroke is a local spike.
    oc, ic = (outside & band).sum(0), (ink & band).sum(0)
    loc = 0.0
    for x in range(0, max(1, w - WIN + 1), WIN // 2):
        o, i = int(oc[x:x + WIN].sum()), int(ic[x:x + WIN].sum())
        if o >= LOC_PX:
            loc = max(loc, o / max(1, i))
    cover = ndimage.mean(ink, lab_r, keep) if nr else []
    min_cover = float(min(cover)) if nr else 0.0
    lab_g, ng = ndimage.label(ink)
    sizes = ndimage.sum(ink, lab_g, range(1, ng + 1)) if ng else []
    inside = ndimage.mean(near, lab_g, range(1, ng + 1)) if ng else []
    cys = ndimage.center_of_mass(ink, lab_g, range(1, ng + 1)) if ng else []
    ng_clean = int(sum(s >= SPECK for s in sizes))
    # Stray components: ink blobs mostly outside the dilated glyph mask and centred in the band.
    stray = int(sum(s >= SPECK and f < 0.5 and b0 <= cy <= b1 for s, f, (cy, _) in zip(sizes, inside, cys)))
    stray_off = int(sum(s >= SPECK and f < 0.5 for s, f in zip(sizes, inside))) - stray
    fails = []
    if out_frac > OUT_FRAC or loc > LOC_FRAC:
        fails.append("ink_outside")
    if nr and min_cover < COVER:
        fails.append("glyph_no_ink")
    if stray > STRAY_MAX:
        fails.append("stray_cc")
    return fails, {"out_frac": round(out_frac, 4), "out_local": round(loc, 3), "min_cover": round(min_cover, 3),
                   "cc_render": nr, "cc_out": ng_clean, "stray_cc": stray, "stray_off_band": stray_off}


def classes(text):
    c = set()
    for ch in text:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        c.add("digit" if cat[0] == "N" else "letter" if cat[0] == "L" else "mark" if cat == "Mn" else "punct")
    return sorted(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gen_dir")
    ap.add_argument("--best", default=str(BEST))
    ap.add_argument("--book-of", help="pairs.jsonl to map style crop paths to books")
    a = ap.parse_args()
    d = Path(a.gen_dir)
    book_of = {}
    if a.book_of:
        for l in open(a.book_of):
            r = json.loads(l); book_of[Path(r["real"]).name] = r["book"]
    rows = [json.loads(l) for l in open(d / "gen.jsonl")]
    out = []
    for r in rows:
        k = r["k"]
        fails, m = ink_check(d / f"g{k:05d}.png", d / f"g{k:05d}_render.png")
        c7 = r.get("cer")
        hb = read(d / f"g{k:05d}.png", a.best); cb = cer(hb, r["text"])
        gross = c7 > GROSS and cb > GROSS
        out.append({"k": k, "text": r["text"], "style_book": book_of.get(Path(r["style"]).name, "?"),
                    "classes": classes(r["text"]), "gate1_fails": fails, **m,
                    "cer_r7": c7, "cer_best": round(cb, 4), "best": hb, "gate2_gross": gross,
                    "accepted": not fails and not gross})
    with open(d / "gates.jsonl", "w") as fo:
        for o in out:
            fo.write(json.dumps(o, ensure_ascii=False) + "\n")
    n = len(out)
    g1 = Counter(f for o in out for f in o["gate1_fails"])
    by_book, by_cls = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for o in out:
        by_book[o["style_book"]][0] += o["accepted"]; by_book[o["style_book"]][1] += 1
        for c in o["classes"]:
            by_cls[c][0] += o["accepted"]; by_cls[c][1] += 1
    summ = {"n": n, "accepted": sum(o["accepted"] for o in out),
            "gate1_rejected": sum(bool(o["gate1_fails"]) for o in out), "gate1_by_rule": dict(g1),
            "gate2_rejected": sum(o["gate2_gross"] for o in out),
            "gate2_only": sum(o["gate2_gross"] and not o["gate1_fails"] for o in out),
            "by_style_book": {b: f"{x}/{t}" for b, (x, t) in sorted(by_book.items())},
            "by_class": {c: f"{x}/{t}" for c, (x, t) in sorted(by_cls.items())},
            "params": {"DIL": DIL, "OUT_FRAC": OUT_FRAC, "COVER": COVER, "STRAY_MAX": STRAY_MAX, "WIN": WIN, "LOC_PX": LOC_PX, "LOC_FRAC": LOC_FRAC,
                       "SPECK": SPECK, "GROSS": GROSS, "best": a.best}}
    json.dump(summ, open(d / "gates_summary.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
