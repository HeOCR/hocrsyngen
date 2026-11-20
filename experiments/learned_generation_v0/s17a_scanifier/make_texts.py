"""S17a add-on texts: Ben-Yehuda PD lines, decontaminated against dev and the scored references.

  make_texts.py OUT_DIR [--n 20000] [--seed 20261111]

Exclusions:
1. Whole works: every Ben-Yehuda work (pby_id) tied to a bynli dev record, whether through dev
   line labels or through f8f2_editions.json, and every work titled like Sippurei Ma'asiyot
   (the wslines dev unit).
2. Word 6-grams (Hebrew letters only, as in r8-tesseract/scripts/build_lists.py): drop a line
   sharing one with any R8 dev label (data/dev.list: bynli dev + wslines dev) or with the 38
   scored audit2 references (decision 0012).
3. Characters: every character must be in the R8 starter unicharset. Lines with niqqud are skipped,
   since the S17a render has no marks.
Lines are 15-60 characters, cut at word boundaries from paragraphs of the stripped text.
Writes texts.txt, texts.jsonl (text, pby_id) and texts_summary.json.
"""
import argparse, csv, hashlib, json, random, re, unicodedata
from pathlib import Path

HEOCR = Path.home() / "agents/environments/opensource/projects/heocr/tasks"
PBY = HEOCR / "s16c-glyph-scale/inputs/benyehuda-2026-03"
L2 = HEOCR / "s16c-glyph-scale/outputs/lines/bynli_lines_v2"
WS = HEOCR / "s16c-glyph-scale/outputs/lines/wslines_v1"
T = HEOCR / "r8-tesseract"
REFS = HEOCR / "real-source-mapping/intermediates/e2d3d_audit2/refs"

words = lambda t: re.sub(r"[^א-ת\s]", "", t).split()
grams = lambda t: {tuple(w[i:i + 6]) for w in [words(t)] for i in range(len(w) - 5)}


def labels(d):
    return {json.loads(l)["id"]: json.loads(l)["text"] for l in open(d / "manifest.jsonl", encoding="utf-8")}


def cut_lines(par, lo=15, hi=60):
    out, cur = [], ""
    for w in par.split():
        nxt = (cur + " " + w).strip()
        if len(nxt) > hi:
            if len(cur) >= lo:
                out.append(cur)
            cur = w if len(w) <= hi else ""
        else:
            cur = nxt
    if len(cur) >= lo:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261111)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    man = [json.loads(l) for l in open(L2 / "manifest.jsonl", encoding="utf-8")]
    dev_recs = {r["record_id"] for r in man if r["split"] != "train"}
    bad_works = {r["pby_id"] for r in man if r["split"] != "train"}
    ed = json.load(open(HEOCR / "s16c-glyph-scale/intermediates/f8f2_editions.json"))
    for rec, v in ed.items():
        if rec in dev_recs:
            bad_works |= set(v.get("pby_ids", []))
    cat = {row["ID"]: row for row in csv.DictReader(open(PBY / "pseudocatalogue.csv", encoding="utf-8"))}
    strip = lambda s: "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    for i, row in cat.items():
        if re.search(r"סיפורי\s*מעשיות|ספורי\s*מעשיות", strip(row["title"])):
            bad_works.add(i)

    lab = {**labels(L2), **labels(WS)}
    dev = (T / "data/dev.list").read_text().split()
    devg = set().union(*(grams(lab[Path(p).stem]) for p in dev))
    scored = set()
    for it in json.load(open(REFS / "reference_manifest.json"))["items"]:
        tr = json.load(open(REFS / "references" / it["source_item_id"] / "transcription.json"))
        scored |= grams(" ".join(x["text"] for x in tr["pages"]))
    uni = {l.split()[0] for l in (T / "starter/heb/heb.unicharset").read_text(encoding="utf-8").splitlines()[1:] if l.split()}
    uni |= {" "}

    cand, stats = [], {"works_seen": 0, "works_excluded": 0, "lines_cut": 0, "drop_chars": 0, "drop_marks": 0,
                       "drop_dev6": 0, "drop_scored6": 0}
    for i, row in cat.items():
        p = PBY / "txt/txt_stripped" / (row["path"].lstrip("/") + ".txt")
        if not p.exists():
            continue
        stats["works_seen"] += 1
        if i in bad_works:
            stats["works_excluded"] += 1
            continue
        for par in p.read_text(encoding="utf-8").split("\n"):
            for ln in cut_lines(par):
                stats["lines_cut"] += 1
                ln = unicodedata.normalize("NFC", ln)
                if any(unicodedata.category(c) == "Mn" for c in ln):
                    stats["drop_marks"] += 1; continue
                if not set(ln) <= uni or not re.search(r"[א-ת]", ln):
                    stats["drop_chars"] += 1; continue
                g = grams(ln)
                if g & devg:
                    stats["drop_dev6"] += 1; continue
                if g & scored:
                    stats["drop_scored6"] += 1; continue
                cand.append((ln, i))
    random.seed(a.seed)
    random.shuffle(cand)
    seen, pick = set(), []
    for ln, i in cand:
        if ln not in seen:
            seen.add(ln); pick.append((ln, i))
        if len(pick) >= a.n:
            break
    (out / "texts.txt").write_text("\n".join(t for t, _ in pick) + "\n", encoding="utf-8")
    with open(out / "texts.jsonl", "w", encoding="utf-8") as fo:
        for t, i in pick:
            fo.write(json.dumps({"text": t, "pby_id": i}, ensure_ascii=False) + "\n")
    summ = {**stats, "candidates": len(cand), "picked": len(pick), "excluded_works": sorted(bad_works, key=int),
            "dev_records": sorted(dev_recs), "dev_list_sha256": hashlib.sha256((T / "data/dev.list").read_bytes()).hexdigest(),
            "seed": a.seed}
    json.dump(summ, open(out / "texts_summary.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k != "excluded_works"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
