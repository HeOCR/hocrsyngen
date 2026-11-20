"""R8c step 0 report: per-book CER (line_fold_v1) of R7 and R8b-main-fold on each degraded dev copy, plus
small-gap letter confusions. Run from tasks/ with rapidfuzz, numpy and pillow available.

Sets: the undegraded Kevar / Yedi'ot held-out lines (eval's *.full sets filtered by the heldout lists), each
r8c_diag_<op> set, Brainin IA (brainin_v3) and Brainin IA upscaled to a 37 px band (r8c_diag_ia_up37).
Confusions are substitutions in the Levenshtein alignment of the folded reference and output, per 1k ref chars.
"""
import json, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "eval-domains/scripts")
import score_lines as S  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

P = json.load(open(S.PROFILES / "line_fold_v1.json"))
MODELS = ["r7", "r8b-main-fold"]
PAIRS = [("ה", "ח"), ("ר", "ד"), ("כ", "ב")]
BOOKS = {"kevar": "kevarpirezikhron00haco", "yediot": "yediothateva06bernuoft"}
L = Path("eval-domains/intermediates/r8b_score/lists")


def book_of(p):
    return next((k for k, v in BOOKS.items() if v in Path(p).name), "brainin")


def stats(setname, keep=None):
    D = S.ROOT / setname
    C = json.load(open(D / "codes.json"))["lines"]
    if keep is not None:
        C = [c for c in C if c["lstmf"] in keep]
    out = {}
    for m in MODELS:
        O = S.outputs(D, m)
        acc = {}
        for c in C:
            b = book_of(c["lstmf"])
            a = acc.setdefault(b, {"lines": 0, "chars": 0, "err": 0, "conf": Counter()})
            r, h = S.norm(c["ref_lstm_order"], P), S.norm(O[c["code"]], P)
            a["lines"] += 1; a["chars"] += len(r); a["err"] += Levenshtein.distance(r, h)
            for op in Levenshtein.editops(r, h):
                if op.tag == "replace":
                    x, y = r[op.src_pos], h[op.dest_pos]
                    for p, q in PAIRS:
                        if {x, y} == {p, q}:
                            a["conf"][f"{p}/{q}"] += 1
        out[m] = {b: {"lines": a["lines"], "cer": round(100 * a["err"] / a["chars"], 3),
                      **{k: round(1000 * a["conf"][k] / a["chars"], 2) for k in ("ה/ח", "ר/ד", "כ/ב")}}
                  for b, a in acc.items()}
    return out


def main():
    res = {}
    for b, full in BOOKS.items():
        keep = set((L / f"{full}.heldout.list").read_text().split())
        res[f"clean_{b}"] = stats(f"{full}.full", keep)
    for v in ["levels", "speckle", "downscale", "unsharp", "grain", "jpeg", "down_sharp", "all", "all_blur"]:
        res[v] = stats(f"r8c_diag_{v}")
    res["brainin_ia"] = stats("brainin_v3")
    res["brainin_ia_up37"] = stats("r8c_diag_ia_up37")
    json.dump(res, open("s17a-scanifier/r8c-aug/diagnostics/step0_report.json", "w"), ensure_ascii=False, indent=1)
    print(f"{'set':18s} {'book':8s} {'lines':>5s} {'R7':>7s} {'R8b':>7s} {'R8b-R7':>7s}  ה/ח r7>r8b   ר/ד r7>r8b   כ/ב r7>r8b")
    for s, d in res.items():
        for b in d["r7"]:
            x, y = d["r7"][b], d["r8b-main-fold"][b]
            print(f"{s:18s} {b:8s} {x['lines']:5d} {x['cer']:7.3f} {y['cer']:7.3f} {y['cer'] - x['cer']:+7.3f}  "
                  + "  ".join(f"{x[k]:4.2f}>{y[k]:4.2f}" for k in ("ה/ח", "ר/ד", "כ/ב")))


if __name__ == "__main__":
    main()
