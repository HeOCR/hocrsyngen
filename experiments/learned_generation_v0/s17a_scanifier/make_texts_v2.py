"""S17a dose arm (add-on v2) texts: Ben-Yehuda PD lines that are new relative to v1.1, decontaminated against
every dev, report and eval set we hold, the whole mid-century held-out split included (lead, 2026-11-13).

  make_texts_v2.py OUT_DIR --v11 V11_MANIFEST [--n 20000] [--seed 20261113]

Run from tasks/. Everything in make_texts.py (v1) applies, plus:
1. Whole works excluded, besides v1's dev works:
   - every work already used in s17a_addon_v1.1 (new text for the dose arm);
   - every work placed in a bynli_lines_v3 dev record or in the R8b dev / excluded units
     (Kevar, Yedi'ot ha-Teva, Zerubavel).
2. Word 6-grams, besides v1's pools (R8 dev.list, the audit2 references). A line is dropped if any 6-gram, under
   either tokenisation (v1's letters-only words, or eval's ngram_overlap.grams), hits any pool:
   - rseries_lists: every list in eval-domains/intermediates/r8b_score/lists (Kevar, Yedi'ot, sel, Brainin IA/NLI,
     Silman, Bodek, reshumot dev, rab dev, ws dev, OLB dev v1 and v1.1), restored to logical order per list;
   - ngram_overlap_targets: eval's ngram_overlap.targets() minus its train: pools (R7 bynli dev, R8 ws dev,
     audit2, line_verify, wave 1);
   - pmod_eval_pages: Reshumot born-digital eval booklets of pmod_unit_split v3 and v5 (snapshot text);
   - midcentury: every held-out unit of midcentury_unit_split_v2 (test 90, dev 90, dev_retired 5):
     the publisher text layer (pdftotext) of every local PDF of those units (test PDFs in
     modern-s6-scout/midcentury_test, dev PDFs in the OLB dev cache), the 300 test/reserve page prefills
     (batch_manifest v0 and v1), the blind-pass prefills (the 27 blind pages), every string in the AI readings
     of those pages, and the OLB dev v1 / v1.1 manifest text.
   Held-out units with no local text are listed in texts_summary.json (pools_uncovered_units); they can only be
   excluded by provenance, and none of S17a's text (Ben-Yehuda) or style crops (bynli train books) comes from them.
Every pool must be non-empty or the script stops.
Writes texts.txt, texts.jsonl, texts_summary.json and pools.json (counts and source hashes, no text).
"""
import argparse, csv, glob, hashlib, json, random, re, subprocess, sys, unicodedata
from pathlib import Path

sys.path.insert(0, "eval-domains/scripts")
sys.path.insert(0, "s17a-scanifier/scripts")
import ngram_overlap as N  # noqa: E402
import make_texts as M  # noqa: E402

V3 = Path("s16c-glyph-scale/outputs/lines/bynli_lines_v3/manifest.jsonl")
R8B_UNITS = {"kevarpirezikhron00haco", "yediothateva06bernuoft", "zerubavel00levi"}
RLISTS = Path("eval-domains/intermediates/r8b_score/lists")
SNAP = Path("real-source-mapping/intermediates/e2d3e/tranche/e2d3e_real_tranche_v5/sources/reshumot_born_digital/snapshot")
MC_SPLIT = Path("eval-domains/labels/midcentury_unit_split_v2.json")
CAP = Path("eval-domains/capture/midcentury")
TEST_PDF = Path("modern-s6-scout/midcentury_test")
DEV_PDF = Path("real-source-mapping/intermediates/olb_reshumot/dev_cache/pdf")
OLB = [Path("s16c-glyph-scale/outputs/lines/olbreshumotlines_v1_dev"), Path("s16c-glyph-scale/outputs/lines/olbreshumotlines_v1.1_dev")]


def both(t):
    return M.grams(t) | N.grams(t)


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def list_texts(f):
    texts = [Path(q[: -len(".lstmf")] + ".gt.txt").read_text(encoding="utf-8").strip() for q in f.read_text().split()]
    return N.logical(texts)


def pdf_text(p):
    r = subprocess.run(["pdftotext", "-q", "-enc", "UTF-8", str(p), "-"], capture_output=True, text=True)
    return r.stdout


def unit_key(unit_id):
    return unit_id.split(":", 1)[1]   # reshumot_scanned:kovetz_hatakanot_311 -> kovetz_hatakanot_311; plenary:K10_125 -> K10_125


def pools():
    P, meta = {}, {}

    def add(name, texts, src):
        g = set(); n = 0
        for t in texts:
            g |= both(t); n += 1
        if not g:
            raise SystemExit(f"pool {name} is empty; refusing to continue")
        P[name] = g; meta[name] = {"items": n, "grams": len(g), "sources": src}

    # v1 pools
    lab = {**M.labels(M.L2), **M.labels(M.WS)}
    dev = (M.T / "data/dev.list").read_text().split()
    add("r8_dev_list", [lab[Path(p).stem] for p in dev], {str(M.T / "data/dev.list"): sha(M.T / "data/dev.list")})
    a2 = []
    for it in json.load(open(M.REFS / "reference_manifest.json"))["items"]:
        tr = json.load(open(M.REFS / "references" / it["source_item_id"] / "transcription.json"))
        a2.append(" ".join(x["text"] for x in tr["pages"]))
    add("audit2_refs", a2, {str(M.REFS / "reference_manifest.json"): sha(M.REFS / "reference_manifest.json")})
    # R-series dev / report / selection / OLB lists
    rl = sorted(RLISTS.glob("*.list"))
    add("rseries_lists", [t for f in rl for t in list_texts(f)], {str(f): sha(f) for f in rl})
    # eval's ngram_overlap targets, without the train pools
    T = N.targets()
    for k, g in T.items():
        if k.startswith("train:"):
            continue
        if not g:
            raise SystemExit(f"ngram_overlap target {k} is empty")
    P["ngram_overlap_targets"] = set().union(*(g for k, g in T.items() if not k.startswith("train:")))
    meta["ngram_overlap_targets"] = {"targets": sorted(k for k in T if not k.startswith("train:")),
                                     "grams": len(P["ngram_overlap_targets"]), "sources": {"eval-domains/scripts/ngram_overlap.py": sha("eval-domains/scripts/ngram_overlap.py")}}
    # P-mod born-digital eval booklets
    ev = set(); src = {}
    for v in ("v3", "v5"):
        f = Path(f"eval-domains/labels/pmod_unit_split_{v}.json"); src[str(f)] = sha(f)
        ev |= {u["unit_id"].split(":", 1)[1] for u in json.load(open(f))["reshumot_born_digital"]["eval"]}
    pt = []
    for l in open(SNAP / "entries.jsonl"):
        e = json.loads(l); b = e["booklet"]
        if f"{b['series']}_{b['booklet_number']}" in ev:
            pt.append((SNAP / "text" / f"{e['entry_id']}.txt").read_text())
    add("pmod_eval_pages", pt, src)
    # mid-century held-out split, whole units
    sp = json.load(open(MC_SPLIT))
    held = {u["unit_id"]: k for k in ("test", "dev", "dev_retired") for u in sp[k]}
    covered = set(); mt = []; msrc = {str(MC_SPLIT): sha(MC_SPLIT)}
    for l in open(TEST_PDF / "manifest.jsonl"):
        r = json.loads(l)
        if r["unit_id"] in held:
            p = TEST_PDF / r["file"]; t = pdf_text(p)
            msrc[str(p)] = r["sha256"]
            if N.grams(t):
                mt.append(t); covered.add(r["unit_id"])
    for p in sorted(DEV_PDF.glob("*.pdf")):
        key = p.name.split("__")[0]                      # reshumot_scanned_kovetz_hatakanot_147
        uid = next((u for u in held if u.replace(":", "_") == key), None)
        t = pdf_text(p); msrc[str(p)] = sha(p)
        if N.grams(t):
            mt.append(t)
            if uid:
                covered.add(uid)
    for f in ("batch_manifest.json", "batch_manifest_v1.json"):
        for pg in json.load(open(CAP / f))["pages"]:
            mt.append(pg.get("prefill") or ""); covered.add(pg["unit_id"])
        msrc[str(CAP / f)] = sha(CAP / f)
    for f in ("blind_prefill.json", "blind_prefill_v1.json"):
        mt += list(strings(json.load(open(CAP / f)))); msrc[str(CAP / f)] = sha(CAP / f)
    for f in sorted((CAP / "ai_readings").rglob("*.json")):
        mt += list(strings(json.load(open(f))))
    msrc[str(CAP / "ai_readings")] = f"{len(list((CAP / 'ai_readings').rglob('*.json')))} json files"
    for d in OLB:
        for l in open(d / "manifest.jsonl"):
            r = json.loads(l); mt.append(r["text"]); covered.add(r.get("unit_id", ""))
        msrc[str(d / "manifest.jsonl")] = sha(d / "manifest.jsonl")
    add("midcentury_heldout", mt, msrc)
    meta["midcentury_heldout"]["held_units"] = {k: sum(1 for v in held.values() if v == k) for k in ("test", "dev", "dev_retired")}
    unc = sorted(u for u in held if u not in covered)
    meta["midcentury_heldout"]["units_with_text"] = len(set(held) & covered)
    return P, meta, unc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--v11", required=True)
    ap.add_argument("--n", type=int, default=20000); ap.add_argument("--seed", type=int, default=20261113)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    # whole works
    man = [json.loads(l) for l in open(M.L2 / "manifest.jsonl", encoding="utf-8")]
    dev_recs = {r["record_id"] for r in man if r["split"] != "train"}
    bad = {r["pby_id"] for r in man if r["split"] != "train"}
    ed = json.load(open(Path("s16c-glyph-scale/intermediates/f8f2_editions.json")))
    for rec, v in ed.items():
        if rec in dev_recs:
            bad |= set(v.get("pby_ids", []))
    v3dev = set()
    for l in open(V3, encoding="utf-8"):
        r = json.loads(l)
        if r["split"] != "train" or r["book"] in R8B_UNITS or r["record_id"] in R8B_UNITS:
            v3dev.add(r["pby_id"]); dev_recs.add(r["record_id"])
    for rec, v in ed.items():
        if rec in dev_recs:
            v3dev |= set(v.get("pby_ids", []))
    v11 = {json.loads(l)["pby_id"] for l in open(a.v11, encoding="utf-8")}
    v11_texts = {json.loads(l)["text"] for l in open(a.v11, encoding="utf-8")}
    cat = {row["ID"]: row for row in csv.DictReader(open(M.PBY / "pseudocatalogue.csv", encoding="utf-8"))}
    strip = lambda s: "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    for i, row in cat.items():
        if re.search(r"סיפורי\s*מעשיות|ספורי\s*מעשיות", strip(row["title"])):
            bad.add(i)
    excl = bad | v3dev | v11

    P, meta, unc = pools()
    uni = {l.split()[0] for l in (M.T / "starter/heb/heb.unicharset").read_text(encoding="utf-8").splitlines()[1:] if l.split()}
    uni |= {" "}
    st = {"works_seen": 0, "works_excluded_dev": 0, "works_excluded_v11": 0, "lines_cut": 0, "drop_marks": 0,
          "drop_chars": 0, "drop_v11_text": 0, **{f"drop_6gram_{k}": 0 for k in P}}
    cand = []
    for i, row in cat.items():
        p = M.PBY / "txt/txt_stripped" / (row["path"].lstrip("/") + ".txt")
        if not p.exists():
            continue
        st["works_seen"] += 1
        if i in bad | v3dev:
            st["works_excluded_dev"] += 1; continue
        if i in v11:
            st["works_excluded_v11"] += 1; continue
        for par in p.read_text(encoding="utf-8").split("\n"):
            for ln in M.cut_lines(par):
                st["lines_cut"] += 1
                ln = unicodedata.normalize("NFC", ln)
                if any(unicodedata.category(c) == "Mn" for c in ln):
                    st["drop_marks"] += 1; continue
                if not set(ln) <= uni or not re.search(r"[א-ת]", ln):
                    st["drop_chars"] += 1; continue
                if ln in v11_texts:
                    st["drop_v11_text"] += 1; continue
                g = both(ln); hit = next((k for k, pool in P.items() if g & pool), None)
                if hit:
                    st[f"drop_6gram_{hit}"] += 1; continue
                cand.append((ln, i))
    random.seed(a.seed); random.shuffle(cand)
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
    assert not ({i for _, i in pick} & excl)
    summ = {**st, "candidates": len(cand), "picked": len(pick), "seed": a.seed, "v11_manifest_sha256": sha(a.v11),
            "excluded_works_dev": sorted(bad | v3dev, key=int), "excluded_works_v11": len(v11),
            "pools_uncovered_units": unc}
    json.dump(summ, open(out / "texts_summary.json", "w"), ensure_ascii=False, indent=1)
    json.dump(meta, open(out / "pools.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k not in ("excluded_works_dev", "pools_uncovered_units")}, ensure_ascii=False))
    print("pools", {k: v["grams"] for k, v in meta.items()}, "uncovered held-out units", len(unc))


if __name__ == "__main__":
    main()
