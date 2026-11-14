"""S17a dose arm: apply the pre-registered decision rule (dose2/PREREGISTRATION.md, hocrsyngen cafb637).

  dose_decide.py ARM_NAME ARM_TRAIN_LIST OUT_JSON [--control r8b-main-fold]

Run from tasks/ after score_lines.py `run` has written out/ARM_NAME.txt for every set below (the control's outputs
are already there). Profile line_fold_v1; every line is charged (score_lines.norm on reference and output).
Delta = CER(control) - CER(arm): positive means the arm is better. 95% paired cluster bootstrap, 10,000 resamples, seed 0.
- Primary: olb_dev (olbreshumotlines_v1_dev), clusters = unit_id, views as in r8b_olb_gate.py; "excluded" leaves out
  lines that share a word 6-gram with ARM_TRAIN_LIST. OLB win = lower bound on "all" > 0; if "exact" has the opposite
  sign to "all", the result is unresolved.
- Guard: Kevar and Yedi'ot held-out lines (the .full sets restricted to the .heldout lists), Brainin IA (brainin_v3),
  Brainin NLI, Silman. Clusters = scan page (book + cNNNN from the file name). Loss = upper bound < 0.
- Report-only: bodek, reshumot_dev, rab_dev, ws_dev (CER and the same page/line interval, no rule).
- Secondary (lead 2026-11-13, not deciding): each guard book again without dev lines sharing a word 6-gram with
  ARM_TRAIN_LIST (guard_exposure_removed); OLB's "excluded" views are the same idea.
Decision: arm wins iff OLB win and no guard loss.
Stock tessdata_best heb (--stock) is a CER column on the same lines; it never enters an interval or the decision.
"""
import argparse, hashlib, json, random, re, sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from rapidfuzz.distance import Levenshtein

sys.path.insert(0, "eval-domains/scripts")
import ngram_overlap as N  # noqa: E402
import score_lines as S  # noqa: E402

PROFILE = "line_fold_v1"; B = 10000; CAP = 60
OLB = Path("s16c-glyph-scale/outputs/lines/olbreshumotlines_v1_dev")
L = Path("eval-domains/intermediates/r8b_score/lists")
GUARD = {"kevar": ("kevarpirezikhron00haco.full", "kevarpirezikhron00haco.heldout"),
         "yediot": ("yediothateva06bernuoft.full", "yediothateva06bernuoft.heldout"),
         "brainin_ia": ("brainin_v3", None), "brainin_nli": ("brainin_nli", None), "silman": ("silman", None)}
REPORT = {"bodek": "bodek", "reshumot_dev": "reshumot_dev", "rab_dev": "rab_dev", "ws_dev": "ws_dev"}
PAGE = re.compile(r"_c(\d+)_l\d+")


def boot(items, models, seed=0):
    """items: (cluster, n_chars, {model: errors}). Returns CERs and the paired interval of control - arm."""
    cl = sorted({c for c, _, _ in items}); ui = {u: i for i, u in enumerate(cl)}
    n = np.zeros(len(cl)); E = {m: np.zeros(len(cl)) for m in models}
    for c, k, e in items:
        n[ui[c]] += k
        for m in models:
            E[m][ui[c]] += e[m]
    cer = {m: round(float(100 * E[m].sum() / n.sum()), 3) for m in models}
    nr = np.random.default_rng(seed)
    idx = nr.integers(0, len(cl), size=(B, len(cl)))
    W = np.stack([np.bincount(i, minlength=len(cl)) for i in idx])
    nb = W @ n; ctl, arm = models[:2]  # any further model (stock) gets a CER column only, never the interval
    dd = 100 * (W @ E[ctl]) / nb - 100 * (W @ E[arm]) / nb
    lo, hi = np.percentile(dd, [2.5, 97.5])
    return {"lines": len(items), "clusters": len(cl), "chars": int(n.sum()), "cer": cer,
            "delta_control_minus_arm": round(cer[ctl] - cer[arm], 3), "ci95": [round(float(lo), 3), round(float(hi), 3)],
            "arm_better": bool(lo > 0), "arm_worse": bool(hi < 0)}


def set_items(setname, models, P, keep=None, cluster=None):
    D = S.ROOT / setname
    C = json.load(open(D / "codes.json"))["lines"]
    if keep is not None:
        C = [c for c in C if c["lstmf"] in keep]
    O = {m: S.outputs(D, m) for m in models}
    out = []
    for c in C:
        r = S.norm(c["ref_lstm_order"], P)
        e = {m: Levenshtein.distance(r, S.norm(O[m][c["code"]], P)) for m in models}
        if cluster:
            k = cluster(c)
        else:
            m = PAGE.search(Path(c["lstmf"]).name)
            k = (Path(c["lstmf"]).parent.name + ":c" + m.group(1)) if m else ("line:" + c["lstmf"])
        out.append((k, len(r), e, c))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm"); ap.add_argument("train_list"); ap.add_argument("out")
    ap.add_argument("--control", default="r8b-main-fold")
    ap.add_argument("--stock", default="stock-best", help="report-only CER column (tessdata_best heb); '' to skip")
    a = ap.parse_args()
    models = [a.control, a.arm] + ([a.stock] if a.stock else [])
    P = json.load(open(S.PROFILES / f"{PROFILE}.json"))
    rep = {"prereg": "hocrsyngen cafb637 experiments/learned_generation_v0/s17a_scanifier/dose_v2/PREREGISTRATION.md",
           "profile": PROFILE, "profile_sha256": hashlib.sha256((S.PROFILES / f"{PROFILE}.json").read_bytes()).hexdigest(),
           "models": {"control": a.control, "arm": a.arm, "stock_report_only": a.stock or None}, "bootstrap": {"B": B, "seed": 0}}

    # primary: OLB dev, unit clusters
    rows = {str(OLB.resolve() / (r["image"][:-4] + ".lstmf")): r for r in map(json.loads, (OLB / "manifest.jsonl").read_text().splitlines())}
    tg = set()
    stores = defaultdict(list)
    for p in Path(a.train_list).read_text().split():
        stores[str(Path(p).parent.parent)].append(Path(p[: -len(".lstmf")] + ".gt.txt").read_text(encoding="utf-8").strip())
    for texts in stores.values():
        for t in N.logical(texts):
            tg |= N.grams(t)
    it = set_items("olb_dev", models, P, cluster=lambda c: rows[c["lstmf"]]["unit_id"])
    L2 = [{"k": k, "n": n, "e": e, "tier": rows[c["lstmf"]]["tesseract_tier"],
           "ov": bool(N.grams(rows[c["lstmf"]]["text"]) & tg)} for k, n, e, c in it]
    rng = random.Random(0); byu = defaultdict(list)
    for x in L2:
        byu[x["k"]].append(x)
    capped = {id(x) for xs in byu.values() for x in (rng.sample(xs, CAP) if len(xs) > CAP else xs)}
    views = {"all": lambda x: True, "excluded": lambda x: not x["ov"], "exact": lambda x: x["tier"] == "exact",
             "not_exact": lambda x: x["tier"] == "not_exact", "all_cap60": lambda x: id(x) in capped,
             "excluded_cap60": lambda x: id(x) in capped and not x["ov"]}
    rep["olb"] = {"set": "olbreshumotlines_v1_dev", "manifest_sha256": hashlib.sha256((OLB / "manifest.jsonl").read_bytes()).hexdigest(),
                  "overlap_lines_with_arm_train": sum(x["ov"] for x in L2),
                  "views": {v: boot([(x["k"], x["n"], x["e"]) for x in L2 if f(x)], models) for v, f in views.items()}}
    va, ve = rep["olb"]["views"]["all"], rep["olb"]["views"]["exact"]
    unresolved = bool((va["delta_control_minus_arm"] > 0) != (ve["delta_control_minus_arm"] > 0))
    olb_win = va["arm_better"] and not unresolved

    rep["guard"] = {}; rep["guard_exposure_removed"] = {}
    for b, (sn, ho) in GUARD.items():
        keep = set((L / f"{ho}.list").read_text().split()) if ho else None
        its = set_items(sn, models, P, keep)
        rep["guard"][b] = boot([(k, n, e) for k, n, e, _ in its], models)
        # secondary (not deciding): drop dev lines that share a word 6-gram with the arm's training list
        clean = [(k, n, e) for k, n, e, c in its if not (N.grams(c["ref_lstm_order"][::-1]) & tg)]
        r = boot(clean, models) if clean else None
        if r:
            r["exposed_lines_removed"] = len(its) - len(clean)
        rep["guard_exposure_removed"][b] = r
    losses = [b for b, r in rep["guard"].items() if r["arm_worse"]]
    rep["report_only"] = {b: boot([(k, n, e) for k, n, e, _ in set_items(sn, models, P)], models) for b, sn in REPORT.items()}
    rep["decision"] = {"olb_win": olb_win, "olb_unresolved": unresolved, "guard_losses": losses,
                       "arm_wins": bool(olb_win and not losses),
                       "verdict": "unresolved (back to lead)" if unresolved else ("ARM WINS" if olb_win and not losses else "arm does not win")}
    json.dump(rep, open(a.out, "w"), indent=1)
    for v, r in rep["olb"]["views"].items():
        print(f"olb {v:15s} {r['lines']:5d}/{r['clusters']:3d}  ctl {r['cer'][a.control]:.3f}  arm {r['cer'][a.arm]:.3f}  d {r['delta_control_minus_arm']:+.3f} {r['ci95']}  stock {r['cer'].get(a.stock, float('nan')):.3f}")
    for g in ("guard", "guard_exposure_removed", "report_only"):
        for b, r in rep[g].items():
            if r is None:
                continue
            print(f"{g[:6]} {b:13s} {r['lines']:5d}/{r['clusters']:4d}  ctl {r['cer'][a.control]:.3f}  arm {r['cer'][a.arm]:.3f}  d {r['delta_control_minus_arm']:+.3f} {r['ci95']}  stock {r['cer'].get(a.stock, float('nan')):.3f}")
    print(rep["decision"])


if __name__ == "__main__":
    main()
