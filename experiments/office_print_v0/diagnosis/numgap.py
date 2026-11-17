"""Number-recall miss diagnosis on D-bench synthetic sets B and C (office-print plan §2.2).

    python numgap.py <dbench dir> <run id> <out.json> [readers...]

Uses eval's frozen measures.py (NUM, fold, clean) and gate.doc_units' reference construction, so a "miss" here is
exactly a miss under the gate: ref Counter - hyp Counter, per document. Each missed token is classed against the
document's extra hyp tokens (hyp Counter - ref Counter), page-local when the output has the reference's page count:
  reordered  an extra token with the same digit groups in reverse order, or the same characters reversed (bidi)
  misread    an extra token at Levenshtein distance 1-2 (wrong digit, separator, or % sign)
  split      two extras that concatenate (either order, separators dropped or kept) to the token
  joined     one extra that is this token joined with another missed token (either order)
  absent     nothing of the above
Extras are consumed greedily in that order. Output: aggregate counts only (no reference or output text), per cell,
per reader, plus breakdowns by token shape. Nothing here writes to the dbench tree.
"""
from __future__ import annotations

import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

DB = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(DB / "scripts"))
import measures as M  # noqa: E402
from gate import doc_units  # noqa: E402,F401  (imported to pin the same code path)
from report import SYN, gold_doc, j, out_text  # noqa: E402

RUN = DB / "runs" / sys.argv[2]
OUT = Path(sys.argv[3])
READERS = sys.argv[4:] or ["heocr", "stock", "docling", "pymupdf4llm"]
CELLS = {"T5": ["B/pdf_t5_scan", "C/pdf_t5_office", "C/pdf_t5_office_numbers"],
         "T4": ["B/pdf_t4_garbage"],
         "tables": ["C/pdf_t5_table", "C/pdf_t5_table_faint", "C/pdf_t5_table_merged"]}
SEP = re.compile(r"[.,/]")


def ref_pages_of(item: str) -> list[str]:
    s, case, doc = item.split("/")
    root = {"A": SYN / "out", "B": SYN / "out_b", "C": SYN / "out_c"}[s]
    tg = j(root / case / f"{doc}.table.json") if case.startswith("pdf_t5_table") else None
    lf = root / case / f"{doc}.layout.json"
    layout = j(lf) if lf.exists() else None
    if tg:
        return [M.table_reference(tg)]
    if layout and isinstance(layout.get("pages"), list):
        return M.pdf_reference(layout)
    return [M.doc_reference(gold_doc(doc))]


def toks(text: str) -> Counter:
    return Counter(M.NUM.findall(M.fold(M.clean(text))))


def shape(t: str) -> str:
    if t.endswith("%"):
        return "percent"
    if re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", t):
        return "date"
    if "," in t:
        return "thousands"
    if re.fullmatch(r"\d+\.\d+", t):
        return "decimal_or_section"
    if "/" in t:
        return "slash_ref"
    if re.fullmatch(r"\d+(\.\d+){2,}", t):
        return "section_multi"
    return "int_len%d" % min(len(t), 6) if len(t) < 6 else "int_len6+"


def reordered(a: str, b: str) -> bool:
    if a == b:
        return False
    if b == a[::-1]:
        return True
    ga, gb = SEP.split(a), SEP.split(b)
    return len(ga) > 1 and ga[::-1] == gb


def classify(missed: Counter, extra: Counter) -> Counter:
    ex = list(extra.elements())
    out = Counter()
    pending = list(missed.elements())
    left = []
    for t in pending:  # reordered, then misread (both consume one extra)
        k = next((i for i, e in enumerate(ex) if reordered(t, e)), None)
        if k is not None:
            ex.pop(k); out[("reordered", t)] += 1; continue
        k = next((i for i, e in enumerate(ex) if 1 <= M.Levenshtein.distance(t, e) <= 2), None)
        if k is not None:
            ex.pop(k); out[("misread", t)] += 1; continue
        left.append(t)
    left2 = []
    for t in left:  # split: two extras concatenate to t (with or without its separators)
        bare = SEP.sub("", t.rstrip("%"))
        hit = None
        for i in range(len(ex)):
            for k in range(len(ex)):
                if i != k:
                    c = ex[i] + ex[k]
                    if c in (t, bare) or SEP.sub("", c.rstrip("%")) == bare:
                        hit = (i, k); break
            if hit:
                break
        if hit:
            for i in sorted(hit, reverse=True):
                ex.pop(i)
            out[("split", t)] += 1
        else:
            left2.append(t)
    used = set()
    for a in range(len(left2)):  # joined: one extra is two missed tokens joined
        if a in used:
            continue
        for b in range(len(left2)):
            if b == a or b in used:
                continue
            for c in (left2[a] + left2[b], left2[b] + left2[a]):
                k = next((i for i, e in enumerate(ex) if e == c or SEP.sub("", e) == SEP.sub("", c)), None)
                if k is not None:
                    ex.pop(k); used |= {a, b}; out[("joined", left2[a])] += 1; out[("joined", left2[b])] += 1; break
            if a in used:
                break
    for i, t in enumerate(left2):
        if i not in used:
            out[("absent", t)] += 1
    return out


def main():
    rj = j(RUN / "run.json")
    res = {}
    for reader in READERS:
        recs = {x["item"]: x for x in rj["results"].get(reader, [])}
        res[reader] = {}
        for cell, cases in CELLS.items():
            items = [i for i in recs if i.rsplit("/", 1)[0] in cases]
            cls, shapes_all, shapes_miss = Counter(), Counter(), defaultdict(Counter)
            ref_n = hits = docs = pagelocal = 0
            for item in items:
                hyp = (out_text(RUN, reader, item) or "") if recs[item]["status"] == "ok" else ""
                rp = ref_pages_of(item)
                R, H = toks("\n".join(rp)), toks(hyp)
                docs += 1; ref_n += sum(R.values()); hits += sum((R & H).values())
                for t, n in R.items():
                    shapes_all[shape(t)] += n
                hp = hyp.split("\f")
                if len(hp) == len(rp) and len(rp) > 1:
                    pagelocal += 1
                    # page-local classes, but only for tokens missed at document level (the gate's count)
                    dm = R - H
                    for r_, h_ in zip(rp, hp):
                        Rp, Hp = toks(r_), toks(h_)
                        mp = Counter({t: min(n, dm[t]) for t, n in (Rp - Hp).items() if dm[t] > 0})
                        dm -= mp
                        c = classify(mp, Hp - Rp)
                        for (k, t), n in c.items():
                            cls[k] += n; shapes_miss[k][shape(t)] += n
                    for t, n in dm.items():  # missed at doc level but not page-local (moved page): absent
                        cls["absent"] += n; shapes_miss["absent"][shape(t)] += n
                else:
                    c = classify(R - H, H - R)
                    for (k, t), n in c.items():
                        cls[k] += n; shapes_miss[k][shape(t)] += n
            miss = ref_n - hits
            assert miss == sum(cls.values()), (reader, cell, miss, sum(cls.values()))
            res[reader][cell] = {
                "docs": docs, "ref_numbers": ref_n, "hits": hits, "misses": miss,
                "number_recall_pct": round(100 * hits / ref_n, 2) if ref_n else None,
                "page_local_docs": pagelocal,
                "miss_classes": dict(cls),
                "miss_class_pct_of_ref": {k: round(100 * v / ref_n, 2) for k, v in cls.items()} if ref_n else {},
                "ref_shapes": dict(shapes_all),
                "miss_shapes_by_class": {k: dict(v) for k, v in shapes_miss.items()},
            }
    OUT.write_text(json.dumps({"run": sys.argv[2], "rule": __doc__.strip().splitlines()[0], "results": res},
                              ensure_ascii=False, indent=1))
    for reader, cells in res.items():
        for cell, r in cells.items():
            print(f"{reader:12s} {cell:7s} docs {r['docs']:3d} ref {r['ref_numbers']:5d} NR {r['number_recall_pct']}  "
                  + "  ".join(f"{k} {v}" for k, v in sorted(r["miss_class_pct_of_ref"].items())))


if __name__ == "__main__":
    main()
