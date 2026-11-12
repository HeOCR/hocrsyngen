"""S17a pairs v2: letters-only gate, edition punctuation kept (heocr-lead, 2026-11-11).

Differences from build_pairs.py:
- Keep a line if R7's *letters and digits* (spaces and punctuation removed) equal the
  edition text's. R7's punctuation output is ignored; only its letter boxes are used.
- Every punctuation mark in the edition text must be matched by unassigned ink in the
  gap where it belongs (between its neighbouring letters, in reading order). Each gap's
  ink is clustered into marks by x-overlap; the mark count must fit the expected count for
  the edition's punctuation there, and a gap with no edition punctuation must have no
  marks. Any disagreement drops the whole line. Real crops are never edited.
- Lines whose label has combining marks (niqqud, cantillation) are dropped: no render for them yet.

The render target is the edition text including its punctuation.
Train split only, as in v1.
"""
import argparse, hashlib, json, subprocess, sys, tempfile, unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from build_pairs import LINES, R7, FONTS, CINFO, glyph, otsu  # noqa: E402

# Marks a punctuation char may produce as x-overlap clusters: (min, max).
TWO = {'"': (1, 2), "״": (1, 2)}
LOW = set(".,„")
HIGH = set("'\"׳״`“”‘’")
MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<"}


def is_letter(ch):
    return unicodedata.category(ch)[0] in "LN"


def x_clusters(comps):
    """comps: list of (x0, y0, x1, y1). Merge boxes overlapping in x (1 px slack)."""
    comps = sorted(comps, key=lambda b: b[0])
    out = []
    for b in comps:
        if out and b[0] <= out[-1][2] + 1:
            o = out[-1]
            out[-1] = (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
        else:
            out.append(b)
    return out


def process(args):
    row, out, font_path = args
    text = row["text"]
    if any(unicodedata.category(c) == "Mn" for c in text):
        return {"id": row["id"], "kept": False, "reason": "marks"}
    src = LINES / row["image"]
    real = Image.open(src).convert("L")
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "o"
        subprocess.run(["tesseract", str(src), str(base), "--tessdata-dir", str(R7), "-l", "heb",
                        "--psm", "7", "-c", "hocr_char_boxes=1", "hocr"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        try:
            hocr = base.with_suffix(".hocr").read_text()
        except FileNotFoundError:
            return None
    tl = [(int(a), int(b), int(c), int(d), t) for a, b, c, d, t in CINFO.findall(hocr)]
    tl = [c for c in tl if len(c[4]) == 1 and is_letter(c[4])]
    # Edition text -> letters, plus the punctuation in each gap (gap i = before letter i; gap n = after last).
    seq = [c for c in text if not c.isspace()]
    letters = [c for c in seq if is_letter(c)]
    if not letters or "".join(c[4] for c in tl) != "".join(letters):
        return {"id": row["id"], "kept": False, "reason": "letters"}
    gaps = [[] for _ in range(len(letters) + 1)]
    li = 0
    for c in seq:
        if is_letter(c):
            li += 1
        else:
            gaps[li].append(c)

    a = np.asarray(real)
    mask = a < otsu(a)
    lab, n = ndimage.label(mask)
    if not n:
        return {"id": row["id"], "kept": False, "reason": "noink"}
    objs = ndimage.find_objects(lab)
    cents = ndimage.center_of_mass(mask, lab, range(1, n + 1))
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    med_size = float(np.median(sizes))
    med_bottom = float(np.median([sl[0].stop for sl in objs]))
    med_top = float(np.median([sl[0].start for sl in objs]))
    boxes = [None] * len(tl)
    loose = []  # unassigned ink: punctuation candidates
    for k, (cy, cx) in enumerate(cents):
        sl = objs[k]
        b = (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)
        if sizes[k] < max(3, 0.03 * med_size):
            continue  # speck
        if sl[0].start >= med_bottom + 2 or sl[0].stop <= med_top - 2:
            continue  # stray wholly outside the line band
        best, bd = None, None
        for i, (x0, y0, x1, y1, _) in enumerate(tl):
            if x0 - 2 <= cx <= x1 + 2 and y0 - 6 <= cy <= y1 + 6:
                d = abs(cx - (x0 + x1) / 2)
                if bd is None or d < bd:
                    best, bd = i, d
        letterish = sizes[k] >= max(4, 0.08 * med_size)
        if best is not None and letterish:
            o = boxes[best]
            boxes[best] = b if o is None else (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
        else:
            loose.append((cx, b))
    for (x0, y0, x1, y1, ch), b in zip(tl, boxes):
        if b is None or (b[2] - b[0]) > 1.6 * max(x1 - x0, 4) + 2:
            return {"id": row["id"], "kept": False, "reason": "box"}

    # Gap x-ranges in reading order (RTL): gap 0 is right of letter 0, gap i between
    # letter i-1 (right) and letter i (left), gap n left of the last letter.
    # Digit runs are LTR, so use the actual boxes: a gap spans between the two neighbours' edges.
    W = real.size[0]
    placed = []
    for g, punct in enumerate(gaps):
        if g == 0:
            lo, hi = boxes[0][2], W
        elif g == len(letters):
            lo, hi = 0, boxes[-1][0]
        else:
            p, q = boxes[g - 1], boxes[g]
            lo, hi = min(p[2], q[2]), max(p[0], q[0])
            if p[0] >= q[2]:      # RTL neighbours: p right of q
                lo, hi = q[2], p[0]
            elif q[0] >= p[2]:    # LTR neighbours (digits): q right of p
                lo, hi = p[2], q[0]
            else:
                lo, hi = 0, -1    # overlapping boxes: no room for a mark
        comps = [b for cx, b in loose if lo - 1 <= cx <= hi + 1]
        marks = x_clusters(comps)
        mn = sum(TWO.get(c, (1, 1))[0] for c in punct)
        mx = sum(TWO.get(c, (1, 1))[1] for c in punct)
        if not (mn <= len(marks) <= mx):
            return {"id": row["id"], "kept": False, "reason": "punct" if punct else "extra_ink"}
        if not punct:
            continue
        # Reading order inside the gap: RTL gaps right-to-left, and LTR (digit) gaps left-to-right.
        ltr = 0 < g < len(letters) and boxes[g][0] >= boxes[g - 1][2]
        marks = sorted(marks, key=lambda b: b[0] if ltr else -b[0])
        extra = len(marks) - mn  # marks beyond the minimum go to two-mark chars, in order
        mi = 0
        for c in punct:
            take = TWO.get(c, (1, 1))[0]
            if c in TWO and extra > 0:
                take += 1; extra -= 1
            grp = marks[mi:mi + take]; mi += take
            # Bidi mirroring: in RTL context a logical "(" is drawn as ")".
            placed.append((c if ltr else MIRROR.get(c, c), (min(b[0] for b in grp), min(b[1] for b in grp),
                               max(b[2] for b in grp), max(b[3] for b in grp))))

    # Sanity per placed mark: the ink's aspect ratio must be near the font glyph's, and
    # low marks must sit low and high marks high. A failure means ink and edition disagree.
    # Letters get the same aspect check: a sliver box turns aleph or yod into a dash.
    # Height check: each letter's box height, relative to the line's median letter height,
    # must be near the font glyph's height relative to the font's median letter height.
    lg = [glyph(c[4], font_path) for c in tl]
    fh = float(np.median([g.height for g in lg if g is not None] or [1]))
    bh = float(np.median([b[3] - b[1] for b in boxes]))
    for (_, _, _, _, ch), (x0, y0, x1, y1), g in zip(tl, boxes, lg):
        if g is None:
            continue
        ra = ((x1 - x0) / max(1, y1 - y0)) / (g.width / max(1, g.height))
        rh = ((y1 - y0) / max(1, bh)) / (g.height / fh)
        if not (0.5 <= ra <= 2.0 and 0.6 <= rh <= 1.6):
            return {"id": row["id"], "kept": False, "reason": "letter_shape"}
    mid = (med_top + med_bottom) / 2
    slack = 0.15 * (med_bottom - med_top)
    for ch, (x0, y0, x1, y1) in placed:
        g = glyph(ch, font_path)
        if g is None:
            continue
        ra = ((x1 - x0) / max(1, y1 - y0)) / (g.width / max(1, g.height))
        if not 0.4 <= ra <= 2.5:
            return {"id": row["id"], "kept": False, "reason": "punct_shape"}
        if (ch in LOW and y0 < mid - slack) or (ch in HIGH and y1 > mid + slack):
            return {"id": row["id"], "kept": False, "reason": "punct_position"}

    canvas = Image.new("L", real.size, 255)
    for ch, box in [(c[4], b) for c, b in zip(tl, boxes)] + placed:
        g = glyph(ch, font_path)
        w, h = box[2] - box[0], box[3] - box[1]
        if g is None or w < 1 or h < 1:
            continue
        canvas.paste(g.resize((w, h), Image.LANCZOS), (box[0], box[1]))
    pairs = Path(out) / "pairs"
    rp, tp = pairs / f"{row['id']}_render.png", pairs / f"{row['id']}_real.png"
    canvas.save(rp); real.save(tp)
    r7_punct = "".join(t for t in CINFO_all(hocr) if not all(is_letter(c) for c in t))
    return {"id": row["id"], "kept": True, "book": row["book"], "record_id": row["record_id"],
            "text": text, "n_letters": len(letters), "n_punct": len(placed),
            "r7_punct_differs": r7_punct != "".join(c for c in seq if not is_letter(c)),
            "size": list(real.size), "render": str(rp.relative_to(out)), "real": str(tp.relative_to(out)),
            "real_sha256": row["image_sha256"]}


def CINFO_all(hocr):
    return [t for *_, t in CINFO.findall(hocr) if t.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--every", type=int, default=1)
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
    reasons = {}
    with open(out / "pairs.jsonl", "w") as fo, ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(process, [(r, str(out), font_path) for r in rows], chunksize=16):
            if res is None:
                continue
            tried += 1
            if res["kept"]:
                kept += 1
                fo.write(json.dumps(res, ensure_ascii=False) + "\n")
            else:
                reasons[res.get("reason", "?")] = reasons.get(res.get("reason", "?"), 0) + 1
    summary = {"tried": tried, "kept": kept, "rejected": reasons, "font": a.font, "every": a.every,
               "limit": a.limit, "gate": "letters-only + ink-matched edition punctuation",
               "manifest_sha256": hashlib.sha256(open(LINES / "manifest.jsonl", "rb").read()).hexdigest()}
    json.dump(summary, open(out / "summary.json", "w"), indent=1)
    print(summary)


if __name__ == "__main__":
    main()
