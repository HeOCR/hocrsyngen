"""HeOCR calibration print pack v1 (scanifier v2): 8 A4 pages plus thin-paper copies of pages 2 and 3.

  python3 experiments/scanifier_v2/calibration_pack/make_pack.py TEXT_JSON OUT_DIR [--dpi 600]

Every page is rendered at 600 dpi (A4, 4961 x 7016 px) and placed full-bleed in a PDF, losslessly, to print at 100%.
Every page carries:
  - four ArUco markers (DICT_4X4_50, 12 mm) at the corners, ids 4(k-1)..4(k-1)+3 for page code k: page, homography;
  - a QR page-id code ("HEOCR-CAL-V1-Pnn");
  - a margin strip with a 14 mm slanted-edge square (5 degrees) and a 6-step grey wedge.
Page 1 is the full target: nine slanted-edge squares on a 3 x 3 grid (blur and defocus across the page), a 12-step
grey wedge, six colour patches and Hebrew text at 8, 10, 12 and 16 pt.
Pages 2-8 are layouts of public-domain Hebrew text: prose, two-column news, a ruled table, pointed verse, an old-print
page with Rashi-script commentary, a mixed page and large type. Pages 9 and 10 are pages 2 and 3 again, for thin paper.
Writes OUT/calibration_pack_v1.pdf (pages 1-8), OUT/calibration_pack_v1_thin.pdf (pages 9-10) and OUT/gt/Pnn.json:
every text line (logical-order text, box in page pixels, font, size, weight), every marker, edge, patch and furniture
box. Captures of these pages are calibration and dev data only, never test (REGISTER.md).
"""
import argparse, hashlib, io, json, random
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

REPO = Path(__file__).resolve().parents[3]
FONTS = REPO / "src/hocrsyngen/data/synthetic/fonts"
SEED = 20261133
MM = 1.0  # set in main: pixels per mm
PT = 1.0  # pixels per point


def mm(x):
    return int(round(x * MM))


class Font:
    def __init__(self, file, pt, weight=None):
        self.file, self.pt, self.weight = file, pt, weight
        self.f = ImageFont.truetype(str(FONTS / file), max(1, round(pt * PT)), layout_engine=ImageFont.Layout.RAQM)
        if weight is not None:
            axes = [a["name"] for a in self.f.get_variation_axes()]
            self.f.set_variation_by_axes([weight if n == b"Weight" else 100 for n in axes])
        a, d = self.f.getmetrics()
        self.asc, self.desc = a, d

    def w(self, t):
        return self.f.getlength(t, direction="rtl", language="he")

    def meta(self):
        return {"font": self.file, "size_pt": self.pt, "weight": self.weight}


class Page:
    def __init__(self, code, title, colour=False):
        self.code, self.title = code, title
        self.W, self.H = mm(210), mm(297)
        self.img = Image.new("RGB" if colour else "L", (self.W, self.H), (255, 255, 255) if colour else 255)
        self.d = ImageDraw.Draw(self.img)
        self.gt = {"page": f"P{code:02d}", "title": title, "size_px": [self.W, self.H], "lines": [], "markers": [],
                   "edges": [], "wedge": [], "colour_patches": [], "furniture": []}
        self.ink = (0, 0, 0) if colour else 0

    def grey(self, g):
        return (g, g, g) if self.img.mode == "RGB" else g

    # ---- calibration furniture
    def markers(self):
        D = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        s, inset = mm(12), mm(8)
        pos = [(inset, inset), (self.W - inset - s, inset), (self.W - inset - s, self.H - inset - s), (inset, self.H - inset - s)]
        for k, (x, y) in enumerate(pos):
            mid = 4 * (self.code - 1) + k
            m = cv2.aruco.generateImageMarker(D, mid, s)
            self.img.paste(Image.fromarray(m).convert(self.img.mode), (x, y))
            self.gt["markers"].append({"dict": "DICT_4X4_50", "id": mid, "corners_tl_tr_br_bl": [[x, y], [x + s, y], [x + s, y + s], [x, y + s]]})

    def qr(self, x, y, size):
        q = cv2.QRCodeEncoder.create().encode(f"HEOCR-CAL-V1-P{self.code:02d}")
        q = Image.fromarray(q).resize((size, size), Image.Resampling.NEAREST).convert(self.img.mode)
        self.img.paste(q, (x, y))
        self.gt["furniture"].append({"kind": "qr", "text": f"HEOCR-CAL-V1-P{self.code:02d}", "box": [x, y, x + size, y + size]})

    def edge(self, cx, cy, side, angle=5.0):
        a = np.deg2rad(angle); h = side / 2
        pts = [(-h, -h), (h, -h), (h, h), (-h, h)]
        poly = [(cx + px * np.cos(a) - py * np.sin(a), cy + px * np.sin(a) + py * np.cos(a)) for px, py in pts]
        self.d.polygon(poly, fill=self.ink)
        self.gt["edges"].append({"center": [cx, cy], "side_px": side, "angle_deg": angle, "polygon": [[round(x, 2), round(y, 2)] for x, y in poly]})

    def wedge(self, x, y, n, cell, label="wedge"):
        for i in range(n):
            g = round(255 * (1 - i / (n - 1)))
            b = [x + i * cell, y, x + (i + 1) * cell, y + cell]
            self.d.rectangle(b, fill=self.grey(g), outline=self.grey(0) if g == 255 else None, width=max(1, mm(0.2)))
            self.gt["wedge"].append({"set": label, "step": i, "ink_fraction": round(i / (n - 1), 4), "grey": g, "box": b})

    def strip(self):
        """Bottom margin strip: QR, slanted edge, 6-step wedge, page label (furniture, not text ground truth)."""
        y0 = self.H - mm(38)
        self.qr(mm(26), y0, mm(16))
        self.edge(mm(56), y0 + mm(8), mm(13))
        self.wedge(mm(72), y0 + mm(2), 6, mm(10), "strip")
        lab = Font("Arimo-wght.ttf", 7, 400)
        t = f"HeOCR cal. pack v1 | P{self.code:02d} | calibration/dev only"
        self.d.text((mm(134), y0 + mm(6)), t, font=lab.f, fill=self.ink)
        self.gt["furniture"].append({"kind": "label", "text": t, "box": list(self.d.textbbox((mm(134), y0 + mm(6)), t, font=lab.f))})
        return y0

    def frame(self):
        self.markers()
        return mm(24), self.strip() - mm(6)  # text area top, bottom

    # ---- text
    def line(self, words, font, right, y, width, block, justify, align="right", spans=None):
        """Draw one line of words right to left. spans: per-word Font overrides. y is the line's top."""
        fonts = spans or [font] * len(words)
        ws = [f.w(w) for f, w in zip(fonts, words)]
        sp = font.w(" ")
        tot = sum(ws) + sp * (len(words) - 1)
        gap = (width - sum(ws)) / (len(words) - 1) if justify and len(words) > 1 else sp
        x = right if align == "right" else (right - (width - tot) / 2 if align == "center" else right - (width - tot))
        base = y + font.asc
        lefts, rights = [], []
        for f, w, wd in zip(fonts, words, ws):
            self.d.text((x - wd, base), w, font=f.f, fill=self.ink, anchor="ls", direction="rtl", language="he")
            lefts.append(x - wd); rights.append(x)
            x -= wd + gap
        box = [int(np.floor(min(lefts))), int(y), int(np.ceil(max(rights))), int(np.ceil(y + font.asc + font.desc))]
        rec = {"id": f"P{self.code:02d}_{len(self.gt['lines']):04d}", "block": block, "text": " ".join(words), "box": box, **font.meta()}
        if spans:
            rec["word_fonts"] = [f.meta() for f in fonts]
        self.gt["lines"].append(rec)

    def flow(self, words, font, rect, block, lead=1.35, justify=True, indent_mm=0.0, para=None, align="right", bold=None):
        """Fill rect (x0, y0, x1, y1) with words; returns (words left over, y after the last line).
        para: set of word indexes that start a paragraph. bold: (Font, set of word indexes) drawn bold."""
        x0, y0, x1, y1 = rect
        lh = font.pt * PT * lead
        y, i = y0, 0
        para = para or set()
        while i < len(words) and y + font.asc + font.desc <= y1:
            ind = mm(indent_mm) if i in para else 0
            width = x1 - x0 - ind
            j, used = i, 0.0
            while j < len(words):
                f = bold[0] if bold and j in bold[1] else font
                add = f.w(words[j]) + (font.w(" ") if j > i else 0)
                if used + add > width and j > i:
                    break
                if j > i and j in para:
                    break
                used += add; j += 1
            end_para = j >= len(words) or j in para
            spans = [bold[0] if bold and k in bold[1] else font for k in range(i, j)] if bold else None
            self.line(words[i:j], font, x1 - ind, y, width, block, justify and not end_para, align, spans)
            y += lh * (1.4 if end_para and para else 1.0)
            i = j
        return words[i:], y


def paras(lines, rng, lo=35, hi=80):
    words = " ".join(lines).split()
    starts, k = {0}, 0
    while True:
        k += rng.randint(lo, hi)
        if k >= len(words):
            break
        starts.add(k)
    return words, starts


def page1(T, rng):
    p = Page(1, "target", colour=True)
    top, bot = p.frame()
    xs = [mm(40), mm(105), mm(170)]
    ys = [top + mm(14), top + (bot - top) // 2, bot - mm(14)]
    for y in ys:
        for x in xs:
            p.edge(x, y, mm(20))
    # 12-step wedge and colour patches, between rows 1 and 2
    p.wedge(mm(33), ys[0] + mm(20), 12, mm(12), "target12")
    cols = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 255, 255), (255, 0, 255), (255, 255, 0)]
    for i, c in enumerate(cols):
        b = [mm(33) + i * mm(24), ys[0] + mm(36), mm(33) + i * mm(24) + mm(20), ys[0] + mm(56)]
        p.d.rectangle(b, fill=c)
        p.gt["colour_patches"].append({"rgb": list(c), "box": b})
    # text blocks: 8 and 10 pt between rows 1-2 (below the patches), 12 and 16 pt between rows 2-3
    for name, pt, rect in [("p1_t08", 8, (mm(22), ys[0] + mm(62), mm(188), ys[1] - mm(14))),
                           ("p1_t10", 10, None), ("p1_t12", 12, (mm(22), ys[1] + mm(14), mm(188), ys[2] - mm(14))),
                           ("p1_t16", 16, None)]:
        f = Font("FrankRuhlLibre-wght.ttf", pt, 400)
        if rect:
            cur = list(rect)
        _, yend = p.flow(" ".join(T[name]["lines"]).split(), f, tuple(cur), name)
        cur[1] = int(yend + mm(4))
    return p


def page2(T, rng):
    p = Page(2, "prose"); top, bot = p.frame()
    w, s = paras(T["p2_body"]["lines"], rng)
    p.flow(w, Font("DavidLibre-Regular.ttf", 11), (mm(22), top, mm(188), bot), "p2_body", indent_mm=6, para=s)
    return p


def page3(T, rng, code=3):
    p = Page(code, "news"); top, bot = p.frame()
    head = T["p3_head"]["lines"][0].split()[:6]
    hf = Font("FrankRuhlLibre-wght.ttf", 22, 700)
    p.line(head, hf, mm(188), top, mm(166), "p3_head", False, "center")
    y = top + int(hf.pt * PT * 1.6)
    p.d.line([(mm(22), y), (mm(188), y)], fill=p.ink, width=mm(0.4)); p.gt["furniture"].append({"kind": "rule", "box": [mm(22), y, mm(188), y]})
    y += mm(4)
    w, s = paras(T["p3_body"]["lines"], rng, 40, 90)
    f = Font("Tinos-Regular.ttf", 9)
    gutter = mm(6); cw = (mm(166) - gutter) // 2
    left = w
    for c in range(2):  # right column first
        x1 = mm(188) - c * (cw + gutter)
        off = len(w) - len(left)
        left, _ = p.flow(left, f, (x1 - cw, y, x1, bot), f"p3_body_col{c + 1}", para={k - off for k in s if k >= off})
    xm = mm(188) - cw - gutter // 2
    p.d.line([(xm, y), (xm, bot)], fill=p.ink, width=mm(0.25)); p.gt["furniture"].append({"kind": "rule", "box": [xm, y, xm, bot]})
    return p


def page4(T, rng):
    p = Page(4, "table"); top, bot = p.frame()
    rows = T["p4_rows"]["lines"]
    hf = Font("Assistant-wght.ttf", 16, 700)
    p.line(rows[0].split()[:5], hf, mm(188), top, mm(166), "p4_title", False)
    y = top + int(hf.pt * PT * 1.8)
    cols = [("מס'", 14), ("תאריך", 28), ("פרטים", 82), ("כמות", 18), ("סכום", 24)]   # widths in mm, right to left
    f = Font("Assistant-wght.ttf", 10, 400); fb = Font("Assistant-wght.ttf", 10, 700)
    rh = int(f.pt * PT * 1.9)
    xs = [mm(188)]
    for _, wmm in cols:
        xs.append(xs[-1] - mm(wmm))
    n = 0
    data = []
    for r in rows[1:]:
        if y + rh * (len(data) + 2) > bot:
            break
        d = rng.randint(1, 28); mth = rng.randint(1, 12); yr = rng.randint(1950, 1999)
        data.append([str(len(data) + 1), f"{d:02d}.{mth:02d}.{yr}", r, str(rng.randint(1, 250)),
                     f"{rng.randint(10, 99999):,}.{rng.randint(0, 99):02d}"])
    for ri, row in enumerate([[c for c, _ in cols]] + data):
        yy = y + ri * rh
        for ci, cell in enumerate(row):
            ff = fb if ri == 0 else f
            words = cell.split()
            while len(words) > 1 and ff.w(" ".join(words)) > xs[ci] - xs[ci + 1] - mm(3):
                words = words[:-1]
            p.line(words, ff, xs[ci] - mm(1.5), yy + (rh - ff.asc - ff.desc) // 2, xs[ci] - xs[ci + 1] - mm(3),
                   f"p4_r{ri:02d}_c{ci}", False, "right")
        n = ri
    yb = y + (n + 1) * rh
    for ri in range(n + 2):
        p.d.line([(xs[-1], y + ri * rh), (xs[0], y + ri * rh)], fill=p.ink, width=mm(0.3 if ri in (0, 1, n + 1) else 0.15))
    for x in xs:
        p.d.line([(x, y), (x, yb)], fill=p.ink, width=mm(0.2))
    p.gt["furniture"].append({"kind": "table_grid", "box": [xs[-1], y, xs[0], yb], "rows": n + 1, "cols": len(cols)})
    return p


def page5(T, rng):
    p = Page(5, "pointed verse"); top, bot = p.frame()
    f = Font("FrankRuhlLibre-wght.ttf", 13, 400)
    y, lh = top, f.pt * PT * 1.75
    for k, ln in enumerate(T["p5_poem"]["lines"]):
        if y + f.asc + f.desc > bot:
            break
        p.line(ln.split(), f, mm(188), y, mm(166), "p5_poem", False, "center")
        y += lh * (1.6 if k % 4 == 3 else 1.0)
    return p


def page6(T, rng):
    p = Page(6, "old print"); top, bot = p.frame()
    mf = Font("FrankRuhlLibre-wght.ttf", 14, 500); cf = Font("NotoRashiHebrew-wght.ttf", 9, 400)
    mw = mm(92); mx1 = mm(105) + mw // 2; mh = int((bot - top) * 0.45)
    main = " ".join(T["p6_main"]["lines"]).split()
    p.flow(main, mf, (mx1 - mw, top, mx1, top + mh), "p6_main", lead=1.4)
    p.d.rectangle([mx1 - mw - mm(2), top - mm(2), mx1 + mm(2), top + mh + mm(1)], outline=p.ink, width=mm(0.25))
    p.gt["furniture"].append({"kind": "rule_box", "box": [mx1 - mw - mm(2), top - mm(2), mx1 + mm(2), top + mh + mm(1)]})
    com = " ".join(T["p6_comm"]["lines"]).split()
    g = mm(5)
    com, _ = p.flow(com, cf, (mx1 + g, top, mm(188), top + mh), "p6_comm_right", lead=1.3)
    com, _ = p.flow(com, cf, (mm(22), top, mx1 - mw - g, top + mh), "p6_comm_left", lead=1.3)
    p.flow(com, cf, (mm(22), top + mh + mm(6), mm(188), bot), "p6_comm_bottom", lead=1.3)
    return p


def page7(T, rng):
    p = Page(7, "mixed"); top, bot = p.frame()
    h1 = Font("Heebo-wght.ttf", 20, 700); h2 = Font("Heebo-wght.ttf", 14, 600)
    body = Font("NotoSerifHebrew-wdth-wght.ttf", 10.5, 400); bold = Font("NotoSerifHebrew-wdth-wght.ttf", 10.5, 700)
    note = Font("NotoSerifHebrew-wdth-wght.ttf", 8, 400)
    hw = T["p7_head"]["lines"][0].split()[:5]
    p.line(hw, h1, mm(188), top, mm(166), "p7_h1", False)
    y = top + int(h1.pt * PT * 1.7)
    w, s = paras(T["p7_body"]["lines"], rng, 30, 60)
    half = len(w) // 2
    b1 = {k for k in range(0, 12)}
    _, y = p.flow(w[:half], body, (mm(22), y, mm(188), bot), "p7_body1", para={k for k in s if k < half}, bold=(bold, b1))
    p.line(w[half:half + 4], h2, mm(188), int(y + mm(3)), mm(166), "p7_h2", False)
    y += mm(3) + h2.pt * PT * 1.7
    items = T["p7_list"]["lines"][:6]
    for it in items:
        cy = int(y + body.asc * 0.6)
        r = mm(0.9)
        p.d.ellipse([mm(186) - r, cy - r, mm(186) + r, cy + r], fill=p.ink)
        p.gt["furniture"].append({"kind": "bullet", "box": [mm(186) - r, cy - r, mm(186) + r, cy + r]})
        _, y = p.flow(it.split(), body, (mm(22), int(y), mm(182), bot), "p7_list", justify=False)
    y += mm(2)
    rest = w[half + 4:]
    _, y = p.flow(rest, body, (mm(22), int(y), mm(188), bot - mm(32)), "p7_body2", para={0})
    yn = max(int(y + mm(4)), bot - mm(30))
    p.d.line([(mm(140), yn), (mm(188), yn)], fill=p.ink, width=mm(0.2)); p.gt["furniture"].append({"kind": "rule", "box": [mm(140), yn, mm(188), yn]})
    nw = T["p7_note"]["lines"]
    third = max(1, len(nw) // 2)
    y = yn + mm(2)
    for k, chunk in enumerate([nw[:third], nw[third:]]):
        _, y = p.flow([f"{k + 1}."] + " ".join(chunk).split(), note, (mm(22), int(y), mm(188), bot), f"p7_note{k + 1}", lead=1.3)
    return p


def page8(T, rng):
    p = Page(8, "large type"); top, bot = p.frame()
    df = Font("Rubik-wght.ttf", 18, 400)
    p.line([f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1950, 1999)}"], df, mm(188), top, mm(166), "p8_date", False, "left")
    w = " ".join(T["p8_body"]["lines"]).split()
    p.flow(w, Font("Alef-Regular.ttf", 22), (mm(22), top + mm(18), mm(188), bot), "p8_body", lead=1.45, justify=False)
    return p


def save_pdf(pages, path):
    doc = fitz.open()
    for p in pages:
        b = io.BytesIO(); p.img.save(b, "PNG", optimize=True)
        pg = doc.new_page(width=595.2756, height=841.8898)
        pg.insert_image(pg.rect, stream=b.getvalue())
    doc.set_metadata({"title": "HeOCR calibration pack v1", "subject": "Calibration and dev captures only, never test",
                      "creator": "hocrsyngen experiments/scanifier_v2/calibration_pack/make_pack.py"})
    doc.save(str(path), deflate=True, garbage=3)


def main():
    global MM, PT
    ap = argparse.ArgumentParser(); ap.add_argument("text"); ap.add_argument("out"); ap.add_argument("--dpi", type=int, default=600)
    a = ap.parse_args()
    assert features.check("raqm"), "Pillow without libraqm"
    MM, PT = a.dpi / 25.4, a.dpi / 72
    T = json.load(open(a.text, encoding="utf-8"))["blocks"]
    out = Path(a.out); (out / "gt").mkdir(parents=True, exist_ok=True)
    mk = [page1, page2, page3, page4, page5, page6, page7, page8]
    pages = [f(T, random.Random(SEED + k)) for k, f in enumerate(mk, 1)]
    thin = [page2(T, random.Random(SEED + 2)), page3(T, random.Random(SEED + 3))]
    for p, c in zip(thin, (9, 10)):   # same layout and text as pages 2 and 3, new page code and markers
        src = pages[c - 8]
        q = Page(c, src.title + " (thin paper copy of P%02d)" % src.code)
        q.img = src.img.copy(); q.d = ImageDraw.Draw(q.img)
        q.gt["lines"] = [{**l, "id": l["id"].replace(f"P{src.code:02d}_", f"P{c:02d}_")} for l in src.gt["lines"]]
        q.gt["furniture"] = [f for f in src.gt["furniture"] if f["kind"] not in ("qr", "label")]
        q.gt["edges"], q.gt["wedge"] = src.gt["edges"], src.gt["wedge"]
        for m in src.gt["markers"]:   # blank the old markers, QR and label, then draw the new ones
            (x0, y0), (x1, y1) = m["corners_tl_tr_br_bl"][0], m["corners_tl_tr_br_bl"][2]
            q.d.rectangle([x0, y0, x1, y1], fill=255)
        for f in src.gt["furniture"]:
            if f["kind"] in ("qr", "label"):
                q.d.rectangle(f["box"], fill=255)
        q.markers()
        y0 = q.H - mm(38)
        q.qr(mm(26), y0, mm(16))
        lab = Font("Arimo-wght.ttf", 7, 400)
        t = f"HeOCR cal. pack v1 | P{c:02d} = P{src.code:02d} thin | calib./dev only"
        q.d.text((mm(134), y0 + mm(6)), t, font=lab.f, fill=q.ink)
        q.gt["furniture"].append({"kind": "label", "text": t, "box": list(q.d.textbbox((mm(134), y0 + mm(6)), t, font=lab.f))})
        q.gt["same_as"] = f"P{src.code:02d}"
        thin[c - 9] = q
    for p in pages + thin:
        p.gt.update({"dpi": a.dpi, "pack": "HeOCR calibration pack v1", "use": "calibration and dev only, never test"})
        json.dump(p.gt, open(out / "gt" / f"{p.gt['page']}.json", "w"), ensure_ascii=False, indent=1)
    save_pdf(pages, out / "calibration_pack_v1.pdf")
    save_pdf(thin, out / "calibration_pack_v1_thin.pdf")
    for p in pages + thin:
        p.img.resize((p.W // 6, p.H // 6), Image.Resampling.LANCZOS).save(out / f"preview_{p.gt['page']}.png")
    summ = {"pages": {p.gt["page"]: {"lines": len(p.gt["lines"]), "chars": sum(len(l["text"]) for l in p.gt["lines"])} for p in pages + thin},
            "pdf_sha256": {n: hashlib.sha256((out / n).read_bytes()).hexdigest() for n in ("calibration_pack_v1.pdf", "calibration_pack_v1_thin.pdf")},
            "text_sha256": hashlib.sha256(Path(a.text).read_bytes()).hexdigest(), "dpi": a.dpi, "seed": SEED}
    json.dump(summ, open(out / "summary.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
