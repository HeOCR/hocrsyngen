"""S17a: accept/reject sheets per style book and per character class, plus the digit-bias report.

  gate_sheets.py GEN_DIR OUT_DIR --v11 V11_MANIFEST [--per 12] [--seed 20261113]

Reads GEN_DIR/gates.jsonl (gates.py). Each tile is the generated line over its clean render, so the intended text can
be read off the render (labels are always the intended text). A tile's caption gives k, the gate decision and, for
rejections, the failing sub-rules (OUT = ink_outside, NOINK = glyph_no_ink, STRAY = stray_cc, G2 = gross read-back).
Sheets:
  book_<style_book>.png   up to --per accepted and --per rejected lines of that style book
  class_<cls>.png         same per character class: letters_only, punct, digit
  rule_<rule>.png         rejected lines per gate-1 sub-rule, and gate2_only (rejected by gate 2 alone)
Writes OUT/sheets_summary.json, with acceptance per book, class and rule, and digits.json, the digit share of the
accepted lines against v1.1, the per-class gate-2 rejection rate.
"""
import argparse, json, random, re
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

TAG = {"ink_outside": "OUT", "glyph_no_ink": "NOINK", "stray_cc": "STRAY"}
DIG = re.compile(r"[0-9]")
W, H = 900, 44


def tile(d, r):
    g = Image.open(d / f"g{r['k']:05d}.png").convert("L"); ren = Image.open(d / f"g{r['k']:05d}_render.png").convert("L")
    def fit(im):
        s = min(H / im.height, W / im.width); return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))
    g, ren = fit(g), fit(ren)
    t = Image.new("L", (W, 2 * H + 16), 255)
    t.paste(g, (W - g.width, 0)); t.paste(ren, (W - ren.width, H))
    why = "+".join([TAG[f] for f in r["gate1_fails"]] + (["G2"] if r["gate2_gross"] else []))
    cap = f"k={r['k']} {'ACCEPT' if r['accepted'] else 'REJECT ' + why}  r7={r['cer_r7']:.2f} best={r['cer_best']:.2f}"
    ImageDraw.Draw(t).text((4, 2 * H + 2), cap, fill=0)
    return t


def sheet(d, rows, path, title):
    if not rows:
        return
    ts = [tile(d, r) for r in rows]
    im = Image.new("L", (W + 20, 24 + sum(t.height + 6 for t in ts)), 255)
    dr = ImageDraw.Draw(im); dr.text((10, 6), title, fill=0)
    y = 24
    for t in ts:
        im.paste(t, (10, y)); dr.line([(10, y + t.height + 2), (W + 10, y + t.height + 2)], fill=180); y += t.height + 6
    im.save(path)


def cls_of(r):
    c = set(r["classes"])
    out = []
    if c == {"letter"}:
        out.append("letters_only")
    if "punct" in c:
        out.append("punct")
    if "digit" in c:
        out.append("digit")
    return out


def digit_stats(texts):
    n = len(texts); chars = sum(len(t.replace(" ", "")) for t in texts)
    return {"lines": n, "lines_with_digit": sum(bool(DIG.search(t)) for t in texts),
            "share_lines_with_digit": round(sum(bool(DIG.search(t)) for t in texts) / max(1, n), 4),
            "digits_per_1k_chars": round(1000 * sum(len(DIG.findall(t)) for t in texts) / max(1, chars), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gen"); ap.add_argument("out"); ap.add_argument("--v11", required=True)
    ap.add_argument("--per", type=int, default=12); ap.add_argument("--seed", type=int, default=20261113)
    a = ap.parse_args()
    d, o = Path(a.gen), Path(a.out); o.mkdir(parents=True, exist_ok=True)
    G = [json.loads(l) for l in open(d / "gates.jsonl")]
    rng = random.Random(a.seed)
    pick = lambda xs: rng.sample(xs, min(a.per, len(xs)))
    groups = defaultdict(list)
    for r in G:
        groups[("book", r["style_book"])].append(r)
        for c in cls_of(r):
            groups[("class", c)].append(r)
        for f in r["gate1_fails"]:
            groups[("rule", f)].append(r)
        if r["gate2_gross"] and not r["gate1_fails"]:
            groups[("rule", "gate2_only")].append(r)
    summ = {"book": {}, "class": {}, "rule": {}}
    for (kind, name), rs in sorted(groups.items()):
        acc = [r for r in rs if r["accepted"]]; rej = [r for r in rs if not r["accepted"]]
        summ[kind][name] = {"n": len(rs), "accepted": len(acc), "rate": round(len(acc) / len(rs), 4)}
        if kind == "rule":
            sheet(d, pick(rs), o / f"rule_{name}.png", f"rejected by {name}: {len(rs)} lines (sample of {min(a.per, len(rs))})")
        else:
            sheet(d, pick(acc) + pick(rej), o / f"{kind}_{name}.png",
                  f"{kind} {name}: accepted {len(acc)}/{len(rs)}; {min(a.per, len(acc))} accepted then {min(a.per, len(rej))} rejected")
    json.dump(summ, open(o / "sheets_summary.json", "w"), indent=1, ensure_ascii=False)
    v11 = [json.loads(l)["text"] for l in open(a.v11, encoding="utf-8")]
    gen_all = [r["text"] for r in G]; acc = [r["text"] for r in G if r["accepted"]]
    g2 = lambda f: {"lines": sum(f(r) for r in G), "gate2_rejected": sum(f(r) and r["gate2_gross"] for r in G),
                    "gate2_only": sum(f(r) and r["gate2_gross"] and not r["gate1_fails"] for r in G)}
    dig = {"v1.1_accepted": digit_stats(v11), "v2_generated": digit_stats(gen_all), "v2_accepted": digit_stats(acc),
           "v2_gate2_on_digit_lines": g2(lambda r: bool(DIG.search(r["text"]))),
           "v2_gate2_on_no_digit_lines": g2(lambda r: not DIG.search(r["text"]))}
    for k in ("v2_gate2_on_digit_lines", "v2_gate2_on_no_digit_lines"):
        dig[k]["gate2_rate"] = round(dig[k]["gate2_rejected"] / max(1, dig[k]["lines"]), 4)
    json.dump(dig, open(o / "digits.json", "w"), indent=1)
    print(json.dumps(dig, indent=1))


if __name__ == "__main__":
    main()
