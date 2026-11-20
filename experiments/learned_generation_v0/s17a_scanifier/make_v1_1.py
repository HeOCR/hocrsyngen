"""S17a: derive add-on v1.1 from v1 by dropping lines tied to the R8b dev units.

  make_v1_1.py V1_DIR BYNLI_V3_MANIFEST ADDON_LSTMF_LIST OUT_DIR [--units kevarpirezikhron00haco,yediothateva06bernuoft]

A v1 line is dropped if its Ben-Yehuda work (pby_id) is one of the works placed in the R8b dev units,
or if it shares a word 6-gram (Hebrew letters only) with their labels. Writes OUT/manifest.jsonl,
OUT/r8b_decontam_drops.json, OUT/train_lstmf.list (the kept subset of ADDON_LSTMF_LIST, in its order)
and OUT/lines/ as hardlinks to the v1 files. LICENSE, NOTICE, README and source_provenance.json are
documents, copied from the release rather than generated.
This is the inline step that built s17a_addon_v1.1 on 2026-11-12, turned into a script unchanged.
"""
import argparse, json, os, re
from pathlib import Path

words = lambda t: re.sub(r"[^א-ת\s]", "", t).split()
grams = lambda t: {tuple(w[i:i + 6]) for w in [words(t)] for i in range(len(w) - 5)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("v1"); ap.add_argument("v3_manifest"); ap.add_argument("lstmf_list"); ap.add_argument("out")
    ap.add_argument("--units", default="kevarpirezikhron00haco,yediothateva06bernuoft")
    a = ap.parse_args()
    units = set(a.units.split(","))
    dev, devworks = set(), set()
    for l in open(a.v3_manifest):
        r = json.loads(l)
        if r["book"] in units or r["record_id"] in units:
            dev |= grams(r["text"]); devworks.add(r["pby_id"])
    V1, V = Path(a.v1), Path(a.out)
    V.mkdir(parents=True, exist_ok=True)
    man = [json.loads(l) for l in open(V1 / "manifest.jsonl")]
    drop = {}
    for r in man:
        w = r["pby_id"] in devworks; g = bool(grams(r["text"]) & dev)
        if w or g:
            drop[r["id"]] = {"pby_id": r["pby_id"], "same_work": w, "shares_6gram": g, "text": r["text"]}
    keep = [r for r in man if r["id"] not in drop]
    with open(V / "manifest.jsonl", "w") as fo:
        for r in keep:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump({"r8b_dev_units": sorted(units), "r8b_dev_pby_works": sorted(devworks), "dropped": drop},
              open(V / "r8b_decontam_drops.json", "w"), ensure_ascii=False, indent=1)
    ids = {r["id"] for r in keep}
    src = [p for p in Path(a.lstmf_list).read_text().split() if Path(p).stem in ids]
    (V / "train_lstmf.list").write_text("\n".join(src) + "\n")
    (V / "lines").mkdir(exist_ok=True)
    for i in sorted(ids):
        for ext in (".png", ".gt.txt"):
            d = V / "lines" / f"{i}{ext}"
            if not d.exists():
                os.link(V1 / "lines" / f"{i}{ext}", d)
    print("v1", len(man), "dropped", len(drop), "(same work", sum(d["same_work"] for d in drop.values()),
          ", 6gram", sum(d["shares_6gram"] for d in drop.values()), ") kept", len(keep), "lstmf", len(src))


if __name__ == "__main__":
    main()
