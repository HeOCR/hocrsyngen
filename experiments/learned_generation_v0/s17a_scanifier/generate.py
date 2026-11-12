"""S17a: generate scan-like lines from text with a trained scan-ifier, then read them back with R7.

  generate.py CKPT OUT --texts texts.txt --style style.png [--style ...] [--n 50]

- Renders each text line RTL (Pillow + raqm) in FrankRuhlLibre at line height 64.
- Picks a style crop at random from --style, which must be train-split crops or other
  allowed sources, never scored or held-out scans.
- Runs the generator on the whole line (fully convolutional; width padded to /32).
- R7 Tesseract (psm 7) reads the output back; the CER against the intended text is in out/gen.jsonl.
"""
import argparse, json, os, random, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from train_scanifier import Gen, StyleEnc, load_line, H, W  # noqa: E402

R7 = Path(os.path.expanduser("~/agents/environments/opensource/projects/heocr/tasks/r7-tesseract-real/models/r7"))
FONT = Path(os.path.expanduser("~/clones/hocrsyngen/src/hocrsyngen/data/synthetic/fonts/FrankRuhlLibre-wght.ttf"))


def render(text, h=H):
    f = ImageFont.truetype(str(FONT), int(h * 0.62))
    l, t, r, b = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, direction="rtl", language="he")
    im = Image.new("L", (r - l + 24, h), 255)
    ImageDraw.Draw(im).text((12 - l, (h - (b - t)) // 2 - t), text, font=f, fill=0, direction="rtl", language="he")
    return np.asarray(im, dtype=np.float32) / 255.0


def lev(a, b):
    p = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        c = [i]
        for j, cb in enumerate(b, 1):
            c.append(min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (ca != cb)))
        p = c
    return p[-1]


def read_r7(path):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["tesseract", str(path), f"{td}/o", "--tessdata-dir", str(R7), "-l", "heb", "--psm", "7"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Path(f"{td}/o.txt").read_text().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt"); ap.add_argument("out")
    ap.add_argument("--texts", required=True)
    ap.add_argument("--style", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    ck = torch.load(a.ckpt, map_location=dev)
    G, E = Gen().to(dev).eval(), StyleEnc().to(dev).eval()
    G.load_state_dict(ck["G"]); E.load_state_dict(ck["E"])
    texts = [t.strip() for t in open(a.texts) if t.strip()][: a.n]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with open(out / "gen.jsonl", "w") as fo:
        for k, text in enumerate(texts):
            ren = render(text)
            w = ren.shape[1]; pw = (-w) % 32
            ren_p = np.pad(ren, ((0, 0), (0, pw)), constant_values=1.0)
            sp = random.choice(a.style)
            sty = load_line(sp)
            sx = random.randint(0, max(0, sty.shape[1] - W))
            sty = np.pad(sty, ((0, 0), (0, max(0, W - sty.shape[1]))), constant_values=float(np.median(sty)))[:, sx:sx + W]
            with torch.no_grad():
                s = E(torch.from_numpy(np.ascontiguousarray(sty))[None, None].to(dev))
                fake = G(torch.from_numpy(ren_p)[None, None].to(dev), s)[0, 0, :, :w].cpu().numpy()
            p = out / f"g{k:05d}.png"
            Image.fromarray((fake.clip(0, 1) * 255).astype(np.uint8)).save(p)
            Image.fromarray((ren * 255).astype(np.uint8)).save(out / f"g{k:05d}_render.png")
            hyp = read_r7(p)
            ref = text.replace(" ", ""); hy = hyp.replace(" ", "")
            rec = {"k": k, "text": text, "r7": hyp, "cer": round(lev(hy, ref) / max(1, len(ref)), 4), "style": sp}
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    rows = [json.loads(l) for l in open(out / "gen.jsonl")]
    cers = sorted(r["cer"] for r in rows)
    print({"n": len(rows), "median_cer": cers[len(cers) // 2] if cers else None,
           "frac_cer_le_0.05": round(sum(c <= 0.05 for c in cers) / max(1, len(cers)), 3)})


if __name__ == "__main__":
    main()
