"""HeOCR calibration pack v1 addendum: P11-P12, pointed text (scanifier v2 mark-loss calibration).

  python3 experiments/scanifier_v2/calibration_pack/make_addendum.py ADDENDUM_TEXT_JSON OUT_DIR [--dpi 600]

Same frame as make_pack.py: ArUco markers (ids 40-43 and 44-47), QR "HEOCR-CAL-V1-P11" / "-P12", slanted edge and grey
wedge strip. Bundled OFL faces only.
  - P11: three fully pointed prose blocks, at 10 pt (Frank Ruhl Libre), 11 pt (David Libre) and 12 pt (Noto Serif
    Hebrew), justified, line spacing 1.6 (room for the points).
  - P12: a pointed Tanakh passage in two justified columns at 10 pt (Frank Ruhl Libre), sof pasuq at each verse end.
Writes OUT/calibration_pack_v1_addendum.pdf, OUT/gt/P11.json, OUT/gt/P12.json and OUT/addendum_summary.json. The run
fails if any word does not fit on its page. Captures are calibration and dev data only, never test (REGISTER.md).
"""
import argparse, hashlib, json, random, sys
from pathlib import Path

from PIL import Image, features

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_pack as M  # noqa: E402

SEED = 20261134


def page11(T, rng):
    p = M.Page(11, "pointed prose, three sizes"); top, bot = p.frame()
    y = top
    specs = [("p11_a", "FrankRuhlLibre-wght.ttf", 10, 400), ("p11_b", "DavidLibre-Regular.ttf", 11, None),
             ("p11_c", "NotoSerifHebrew-wdth-wght.ttf", 12, 400)]
    left_over = 0
    for k, (blk, file, pt, wt) in enumerate(specs):
        words = " ".join(T[blk]["lines"]).split()
        f = M.Font(file, pt, wt)
        rest, y = p.flow(words, f, (M.mm(22), y, M.mm(188), bot), blk, lead=1.6)
        left_over += len(rest)
        y += M.mm(9)
    return p, left_over


def page12(T, rng):
    p = M.Page(12, "pointed Tanakh, two columns"); top, bot = p.frame()
    words = " ".join(T["p12_tanakh"]["lines"]).split()
    f = M.Font("FrankRuhlLibre-wght.ttf", 10, 400)
    gutter = M.mm(7); cw = (M.mm(166) - gutter) // 2
    left = words
    for c in range(2):  # right column first
        x1 = M.mm(188) - c * (cw + gutter)
        left, _ = p.flow(left, f, (x1 - cw, top, x1, bot), f"p12_tanakh_col{c + 1}", lead=1.55)
    xm = M.mm(188) - cw - gutter // 2
    p.d.line([(xm, top), (xm, bot)], fill=p.ink, width=M.mm(0.25))
    p.gt["furniture"].append({"kind": "rule", "box": [xm, top, xm, bot]})
    return p, len(left)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("text"); ap.add_argument("out"); ap.add_argument("--dpi", type=int, default=600)
    a = ap.parse_args()
    assert features.check("raqm"), "Pillow without libraqm"
    M.MM, M.PT = a.dpi / 25.4, a.dpi / 72
    T = json.load(open(a.text, encoding="utf-8"))["blocks"]
    out = Path(a.out); (out / "gt").mkdir(parents=True, exist_ok=True)
    pages, left = [], {}
    for k, f in ((11, page11), (12, page12)):
        p, n = f(T, random.Random(SEED + k))
        pages.append(p); left[f"P{k}"] = n
    if any(left.values()):
        raise SystemExit(f"words left over (text does not fit): {left}")
    for p in pages:
        p.gt.update({"dpi": a.dpi, "pack": "HeOCR calibration pack v1 (addendum P11-P12)",
                     "use": "calibration and dev only, never test"})
        json.dump(p.gt, open(out / "gt" / f"{p.gt['page']}.json", "w"), ensure_ascii=False, indent=1)
    pdf = out / "calibration_pack_v1_addendum.pdf"
    M.save_pdf(pages, pdf)
    for p in pages:
        p.img.resize((p.W // 6, p.H // 6), Image.Resampling.LANCZOS).save(out / f"preview_{p.gt['page']}.png")
    summ = {"pages": {p.gt["page"]: {"lines": len(p.gt["lines"]), "chars": sum(len(l["text"]) for l in p.gt["lines"])} for p in pages},
            "pdf_sha256": {pdf.name: hashlib.sha256(pdf.read_bytes()).hexdigest()},
            "text_sha256": hashlib.sha256(Path(a.text).read_bytes()).hexdigest(), "dpi": a.dpi, "seed": SEED}
    json.dump(summ, open(out / "addendum_summary.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
