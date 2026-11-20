"""S17a scan-ifier: clean render -> real-looking scan line, conditioned on a style crop.

Generator: U-Net on the render (1 channel), FiLM-modulated by a style vector from a
style encoder that sees a *different* real line of the same book, plus a noise vector.
Discriminator: PatchGAN on (render, image). Loss: LSGAN + lambda * L1 against the real crop.

Exploratory code (hocrsyngen learned_generation_packaging_boundary.md): lives outside
src/hocrsyngen and is not packaged. Data: build_pairs.py output (bynli_lines_v2 train only).
"""
import argparse, json, random, time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

H, W = 64, 256


def load_line(p, h=H):
    im = Image.open(p).convert("L")
    w = max(1, round(im.width * h / im.height))
    return np.asarray(im.resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0


def window(a, x, w=W):
    if a.shape[1] < w:
        a = np.pad(a, ((0, 0), (0, w - a.shape[1])), constant_values=float(np.median(a)) if a.size else 1.0)
    return a[:, x:x + w]


class Pairs(torch.utils.data.Dataset):
    def __init__(self, root, rows):
        self.root, self.rows = Path(root), rows
        self.by_book = defaultdict(list)
        for i, r in enumerate(rows):
            self.by_book[r["book"]].append(i)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        ren, real = load_line(self.root / r["render"]), load_line(self.root / r["real"])
        w = min(ren.shape[1], real.shape[1])
        ren, real = ren[:, :w], real[:, :w]
        x = random.randint(0, max(0, w - W))
        same = self.by_book[r["book"]]
        j = random.choice([k for k in same if k != i] or [i])
        sty = load_line(self.root / self.rows[j]["real"])
        sx = random.randint(0, max(0, sty.shape[1] - W))
        t = lambda a: torch.from_numpy(np.ascontiguousarray(a))[None]
        return t(window(ren, x)), t(window(real, x)), t(window(sty, sx))


def block(i, o, down=True):
    if down:
        return nn.Sequential(nn.Conv2d(i, o, 4, 2, 1), nn.InstanceNorm2d(o), nn.LeakyReLU(0.2))
    return nn.Sequential(nn.ConvTranspose2d(i, o, 4, 2, 1), nn.InstanceNorm2d(o), nn.ReLU())


class StyleEnc(nn.Module):
    def __init__(self, d=256):
        super().__init__()
        self.net = nn.Sequential(block(1, 64), block(64, 128), block(128, 256), block(256, d))

    def forward(self, x):
        return self.net(x).mean((2, 3))


class Gen(nn.Module):
    def __init__(self, sd=256, zd=32):
        super().__init__()
        ch = [1, 64, 128, 256, 256, 256]
        self.downs = nn.ModuleList(block(ch[k], ch[k + 1]) for k in range(5))
        self.ups = nn.ModuleList()
        self.films = nn.ModuleList()
        up_in = [256, 512, 512, 256, 128]
        up_out = [256, 256, 128, 64, 32]
        for a, b in zip(up_in, up_out):
            self.ups.append(block(a, b, down=False))
            self.films.append(nn.Linear(sd + zd, 2 * b))
        self.out = nn.Conv2d(32 + 1, 1, 3, 1, 1)
        self.zd = zd

    def forward(self, x, s, z=None):
        if z is None:
            z = torch.randn(x.shape[0], self.zd, device=x.device)
        c = torch.cat([s, z], 1)
        skips, h = [], x
        for d in self.downs:
            h = d(h); skips.append(h)
        h = skips.pop()
        for k, (u, f) in enumerate(zip(self.ups, self.films)):
            h = u(h)
            g, b = f(c).chunk(2, 1)
            h = h * (1 + g[:, :, None, None]) + b[:, :, None, None]
            if skips:
                h = torch.cat([h, skips.pop()], 1)
        return torch.sigmoid(self.out(torch.cat([h, x], 1)))


class Disc(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Conv2d(2, 64, 4, 2, 1), nn.LeakyReLU(0.2), block(64, 128), block(128, 256),
                                 nn.Conv2d(256, 1, 3, 1, 1))

    def forward(self, ren, img):
        return self.net(torch.cat([ren, img], 1))


def sheet(G, E, batch, path, dev):
    ren, real, sty = [t.to(dev) for t in batch]
    with torch.no_grad():
        fake = G(ren, E(sty))
    rows = []
    for k in range(min(6, ren.shape[0])):
        rows += [ren[k, 0], fake[k, 0], real[k, 0], torch.ones(4, W, device=dev) * 0.5]
    img = (torch.cat(rows, 0).clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)
    Image.fromarray(img).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs_dir")
    ap.add_argument("out")
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--l1", type=float, default=50.0)
    ap.add_argument("--val-books", type=int, default=2, help="hold out the N smallest-but-nonempty books for visual val")
    ap.add_argument("--seed", type=int, default=20261111)
    a = ap.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    rows = [json.loads(l) for l in open(Path(a.pairs_dir) / "pairs.jsonl")]
    books = sorted({r["book"] for r in rows})
    counts = {b: sum(r["book"] == b for r in rows) for b in books}
    multi = [b for b in sorted(books, key=lambda b: counts[b]) if counts[b] >= 2]
    val_books = set(multi[: a.val_books]) if len(multi) > a.val_books else set()
    tr = [r for r in rows if r["book"] not in val_books]
    va = [r for r in rows if r["book"] in val_books] or tr[:8]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump({"train_pairs": len(tr), "val_pairs": len(va), "val_books": sorted(val_books), "args": vars(a),
               "device": dev}, open(out / "run.json", "w"), indent=1)
    dl = torch.utils.data.DataLoader(Pairs(a.pairs_dir, tr), batch_size=a.batch, shuffle=True, num_workers=2,
                                     drop_last=len(tr) >= a.batch, persistent_workers=True)
    vb = next(iter(torch.utils.data.DataLoader(Pairs(a.pairs_dir, va), batch_size=6, shuffle=True)))
    G, E, D = Gen().to(dev), StyleEnc().to(dev), Disc().to(dev)
    og = torch.optim.Adam(list(G.parameters()) + list(E.parameters()), 2e-4, betas=(0.5, 0.999))
    od = torch.optim.Adam(D.parameters(), 2e-4, betas=(0.5, 0.999))
    it, t0, log = 0, time.time(), open(out / "log.jsonl", "a")
    while it < a.iters:
        for ren, real, sty in dl:
            ren, real, sty = ren.to(dev), real.to(dev), sty.to(dev)
            fake = G(ren, E(sty))
            ld = (F.mse_loss(D(ren, real), torch.ones_like(D(ren, real))) +
                  F.mse_loss(D(ren, fake.detach()), torch.zeros_like(D(ren, real)))) / 2
            od.zero_grad(); ld.backward(); od.step()
            pf = D(ren, fake)
            adv, l1 = F.mse_loss(pf, torch.ones_like(pf)), F.l1_loss(fake, real)
            lg = adv + a.l1 * l1
            og.zero_grad(); lg.backward(); og.step()
            it += 1
            if it % 50 == 0 or it == a.iters:
                rec = {"it": it, "d": round(ld.item(), 4), "adv": round(adv.item(), 4), "l1": round(l1.item(), 4),
                       "sec": round(time.time() - t0, 1)}
                log.write(json.dumps(rec) + "\n"); log.flush(); print(rec, flush=True)
            if it % 1000 == 0 or it == a.iters:
                sheet(G, E, vb, out / f"val_{it:06d}.png", dev)
                torch.save({"G": G.state_dict(), "E": E.state_dict(), "D": D.state_dict(), "it": it}, out / "last.pt")
            if it >= a.iters:
                break


if __name__ == "__main__":
    main()
