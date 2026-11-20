"""S17a dose arm: the arm's train list = R8b train_main.list in its exact order + the add-on v2 lstmf lines at seeded
positions (pre-registration: seed 20261115), plus a pre-train 6-gram check of the add-on labels against the same pools
make_texts_v2.py used (positive control: a Kevar held-out line must hit).

  build_dose_list.py ADDON_LSTMF_LIST OUT_LIST [--seed 20261115]

Run from tasks/. Writes OUT_LIST and OUT_LIST.json (counts, hashes, check result). heocr-eval's
check_train_overlap.py must still report CLEAN on OUT_LIST before the run is released.
"""
import argparse, hashlib, json, random, sys
from pathlib import Path

sys.path.insert(0, "s17a-scanifier/scripts")
sys.path.insert(0, "eval-domains/scripts")
import make_texts_v2 as MT  # noqa: E402
import ngram_overlap as N  # noqa: E402

MAIN = Path("r8b-tesseract/data/train_main.list")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("addon"); ap.add_argument("out"); ap.add_argument("--seed", type=int, default=20261115)
    a = ap.parse_args()
    main_l = MAIN.read_text().split()
    add = Path(a.addon).read_text().split()
    assert len(set(add)) == len(add) and not (set(add) & set(main_l))
    assert all(Path(p).name.startswith("s17a2_") for p in add)
    add = sorted(add); random.Random(a.seed).shuffle(add)
    pos = set(random.Random(a.seed + 1).sample(range(len(main_l) + len(add)), len(add)))
    im, ia = iter(main_l), iter(add)
    arm = [next(ia) if i in pos else next(im) for i in range(len(main_l) + len(add))]
    ms = set(main_l)
    assert [p for p in arm if p in ms] == main_l and len(arm) == len(main_l) + len(add)

    # pre-train 6-gram check of the add-on labels (stored visual -> restored)
    texts = [Path(p[: -len(".lstmf")] + ".gt.txt").read_text(encoding="utf-8").strip() for p in add]
    texts = N.logical(texts)
    P, meta, _ = MT.pools()
    hits = {k: sum(bool(MT.both(t) & g) for t in texts) for k, g in P.items()}
    kev = Path("eval-domains/intermediates/r8b_score/lists/kevarpirezikhron00haco.heldout.list").read_text().split()
    ctl = N.logical([Path(q[: -len(".lstmf")] + ".gt.txt").read_text(encoding="utf-8").strip() for q in kev[:200]])
    pos_ctl = sum(bool(MT.both(t) & P["rseries_lists"]) for t in ctl if len(N.grams(t)))
    assert pos_ctl > 0, "positive control failed"
    assert not any(hits.values()), hits
    Path(a.out).write_text("\n".join(arm) + "\n")
    rep = {"main_list": str(MAIN), "main_sha256": hashlib.sha256(MAIN.read_bytes()).hexdigest(), "main_lines": len(main_l),
           "addon_lines": len(add), "arm_lines": len(arm), "seed": a.seed,
           "arm_sha256": hashlib.sha256(Path(a.out).read_bytes()).hexdigest(),
           "pretrain_6gram_hits": hits, "positive_control_kevar_hits": pos_ctl}
    json.dump(rep, open(a.out + ".json", "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
