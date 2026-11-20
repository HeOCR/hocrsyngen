"""R8c option 3 (read-only): where could R8b have learned to read a near-closed ה as ח?

  he_het_labels.py TRAIN_LIST OUT_JSON [--per-book 300] [--seed 20261112] [--workers 8]

Samples up to --per-book lines per training book from R8b's train list. Each line is read with an independent
reader, stock tessdata_best heb (r5-tesseract-ft/models/best, never trained on HeOCR data; --psm 7). The reader's
output is aligned with the label (.gt.txt is stored in visual order, so it is reversed to logical order first), and
substitutions are counted per book:
  lab_he_read_het  label ה, read ח   (the crop's ה looks closed, or the label says ה where the print has ח)
  lab_het_read_he  label ח, read ה   (the crop's ח looks open, or the label says ח where the print has ה)
The second kind is the one that would teach "open-looking glyph -> ח". The rates are per 1k label ה or ח.
The reader makes its own errors, so the rates are only comparable across books, against the s17a control
(synthetic lines whose labels are exact by construction).
"""
import argparse, json, random, subprocess, sys, tempfile, unicodedata
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from rapidfuzz.distance import Levenshtein

BEST = Path.home() / "agents/environments/opensource/projects/heocr/tasks/r5-tesseract-ft/models/best"


def norm(t):
    return " ".join(unicodedata.normalize("NFC", t).split())


def read(png):
    r = subprocess.run(["tesseract", png, "-", "--psm", "7", "-l", "heb", "--tessdata-dir", str(BEST)],
                       capture_output=True, text=True)
    return r.stdout.strip()


def job(lstmf):
    stem = lstmf[:-6]
    lab = norm(Path(stem + ".gt.txt").read_text(encoding="utf-8")[::-1])
    hyp = norm(read(stem + ".png"))
    hh = th = 0; ex = []
    for op in Levenshtein.editops(lab, hyp):
        if op.tag == "replace":
            x, y = lab[op.src_pos], hyp[op.dest_pos]
            if x == "ה" and y == "ח": hh += 1; ex.append("he>het")
            elif x == "ח" and y == "ה": th += 1; ex.append("het>he")
    return {"lstmf": lstmf, "n_he": lab.count("ה"), "n_het": lab.count("ח"), "he_het": hh, "het_he": th,
            "cer_num": Levenshtein.distance(lab, hyp), "chars": len(lab)}


def book_key(p):
    parts = Path(p).parts
    return parts[-4] + "/" + parts[-2]  # source/book


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list"); ap.add_argument("out")
    ap.add_argument("--per-book", type=int, default=300); ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    by = defaultdict(list)
    for p in Path(a.list).read_text().split():
        by[book_key(p)].append(p)
    pick = []
    for k in sorted(by):
        r = random.Random(f"{a.seed}:{k}"); v = sorted(by[k]); r.shuffle(v); pick += v[: a.per_book]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(job, pick, chunksize=16))
    agg = defaultdict(lambda: defaultdict(int))
    for r in rows:
        g = agg[book_key(r["lstmf"])]
        g["lines"] += 1
        for f in ("n_he", "n_het", "he_het", "het_he", "cer_num", "chars"):
            g[f] += r[f]
    books = {}
    for k, g in agg.items():
        books[k] = {**g, "train_lines": len(by[k]), "cer": round(100 * g["cer_num"] / max(1, g["chars"]), 2),
                    "he_het_per_1k_he": round(1000 * g["he_het"] / max(1, g["n_he"]), 2),
                    "het_he_per_1k_het": round(1000 * g["het_he"] / max(1, g["n_het"]), 2)}
    json.dump({"meta": {"list": a.list, "per_book": a.per_book, "seed": a.seed, "reader": str(BEST), "psm": 7},
               "books": books, "lines": rows}, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(len(rows), "lines,", len(books), "books")


if __name__ == "__main__":
    main()
