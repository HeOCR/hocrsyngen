"""Office-print pages: tender- and notice-like page images with exact line and cell boxes and logical labels.

This is the `hocrsyngen office-pages` surface (office-print plan, experiments/office_print_v0/PLAN.md §3-§5). The caller
supplies the text pool (JSONL of {id, unit_id, text}, logical order). This module adds the structure, the numbers, the
layout, the image-only marks and the degradation, and writes:

- ``pages/<page>.png``     the degraded page (greyscale)
- ``pages/<page>.json``    every line's quad on that image, its kind, label, number spans and sources; the image-only
                           regions; the realised degradation parameters and the page homography
- ``lines/<line>.png``     a rectified crop of each line or cell, cut from the degraded page
- ``lines/<line>.gt.txt``  its label: the drawn logical text with the stock-unicharset folds (below)
- ``manifest.jsonl``       one record per line crop; ``pages.jsonl`` one per page; ``summary.json`` the realised mix

Rules:
- Faces: only governed faces (render-lines manifest). The held-out face family (Tinos) is used only for
  ``split="val"``, and only there. A line with a character its face cannot draw is not drawn at all (counted).
- Bidi and shaping: Pillow with libraqm, RTL base direction (as render-lines). Words are placed one by one only on
  justified lines without Latin letters, where word-by-word placement equals the bidi algorithm's order.
- Numbers: every generated number is one token, drawn as one run, with the separators it shows (``2.2.4.``,
  ``17.11.2026``, ``1,234.50``). Its span in the label is recorded; tests check that the evaluation number pattern finds
  it whole there. Multi-level section labels lead their line (the most-missed shape, PLAN §2.2.1).
- Labels fold what stock heb's unicharset lacks the way line_fold_v1 folds it: ״→", ׳→', ־→-, “ ” „→"; the en and em
  dash are written ``-`` (PLAN §4). The page still draws the real signs. Every fold is one character for one, so span
  offsets hold in both strings.
- Image-only marks (emblems, signatures, stamps) are generated shapes, never real ones, and are never labelled; a line
  they overlap is masked out of the crops and counted.
- Nothing here imitates the D-bench generators: the families, templates and degradation are written from PLAN §3 and
  §5.2 only.
- Every random choice derives from (seed, page id), so a page renders identically in any batch.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .assets import default_font_manifest_path
from .line_render import GovernedFace, _font, _require_raqm, _sha256, face_weight, governed_faces, missing_chars
from .text_shaping import ShapingError, check_shaping, isolated_words_safe

OFFICE_PAGES_SCHEMA = "hocrsyngen_office_pages.v1"
DPI = 300
A4 = (2480, 3508)  # 210 x 297 mm at 300 dpi
NUM = re.compile(r"\d+(?:[.,/]\d+)*%?")  # the evaluation's number token (D-bench measures.numbers)

FAMILY_MIX = {"running_text": 0.25, "numbered": 0.30, "tables": 0.35, "front_matter": 0.10}
DEGRADATION_MIX = {"office_scan": 0.50, "photocopy": 0.25, "phone_photo": 0.15, "clean": 0.10}
# Share of generated numbers by shape (PLAN §4, re-weighted 2026-11-18 by the aligned miss classes).
SHAPE_MIX = {"label": 0.35, "date": 0.25, "short_int": 0.15, "amount": 0.15, "percent": 0.10}
HELD_OUT_FACES = ("tinos-regular", "tinos-bold")  # office_val only (PLAN §5.1)
HELD_OUT_TABLE_SCHEMA = "payment_schedule"        # office_val only (PLAN §5.3)
OFFICE_FACES = ("arimo", "cousine-regular", "cousine-bold", "open-sans")
BOLD_PAIRS = {"cousine-regular": "cousine-bold", "tinos-regular": "tinos-bold"}

LABEL_FOLD = str.maketrans({"״": '"', "׳": "'", "־": "-", "“": '"', "”": '"',
                            "„": '"', "–": "-", "—": "-"})


def fold_label(text: str) -> str:
    """The label for drawn text: stock heb's missing signs folded one-for-one (offsets are preserved)."""
    out = text.translate(LABEL_FOLD)
    assert len(out) == len(text)
    return out


# --------------------------------------------------------------------------------------------------------------------
# numbers


def gen_label(rng: random.Random, levels: int | None = None, trailing_dot: bool | None = None) -> str:
    """A multi-level section label: 2-4 levels, first level 1-40, later levels mostly small; trailing dot optional."""
    n = levels or rng.choices((2, 3, 4), (0.45, 0.35, 0.20))[0]
    parts = [rng.randint(1, 40)] + [rng.choices(range(1, 21), [1 / k for k in range(1, 21)])[0] for _ in range(n - 1)]
    s = ".".join(map(str, parts))
    return s + "." if (rng.random() < 0.5 if trailing_dot is None else trailing_dot) else s


def gen_date(rng: random.Random) -> str:
    y = rng.randint(1990, 2030)
    m, d = rng.randint(1, 12), rng.randint(1, 28 if rng.random() < 0.9 else 31)
    fmt = rng.choices(("dd.mm.yyyy", "d.m.yyyy", "dd/mm/yy", "dd.mm.yy", "dd/mm/yyyy"), (0.35, 0.2, 0.2, 0.15, 0.1))[0]
    if fmt == "dd.mm.yyyy":
        return f"{d:02d}.{m:02d}.{y}"
    if fmt == "d.m.yyyy":
        return f"{d}.{m}.{y}"
    if fmt == "dd/mm/yy":
        return f"{d:02d}/{m:02d}/{y % 100:02d}"
    if fmt == "dd.mm.yy":
        return f"{d:02d}.{m:02d}.{y % 100:02d}"
    return f"{d:02d}/{m:02d}/{y}"


def gen_short_int(rng: random.Random) -> str:
    k = rng.choices((1, 2, 3), (0.4, 0.4, 0.2))[0]
    return str(rng.randint(0 if k == 1 else 10 ** (k - 1), 10 ** k - 1))


def gen_amount(rng: random.Random) -> str:
    v = 10 ** rng.uniform(0, 9)
    dec = rng.random() < 0.5
    if dec:
        s = f"{v:,.2f}"
    else:
        s = f"{round(v):,}"
    if rng.random() < 0.1:
        s = s.replace(",", "")
    return s


def gen_percent(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.6:
        return f"{rng.randint(1, 100)}%"
    if r < 0.9:
        return f"{rng.uniform(0.1, 99.9):.1f}%"
    return f"{rng.uniform(0.01, 9.99):.2f}%"


GEN = {"label": gen_label, "date": gen_date, "short_int": gen_short_int, "amount": gen_amount, "percent": gen_percent}


# --------------------------------------------------------------------------------------------------------------------
# text pieces: a token is a word as drawn; a number token knows the span of its number inside it


@dataclass
class Tok:
    text: str
    spans: list[tuple[int, int, str]] = field(default_factory=list)  # (start, end, shape) inside text
    src: str | None = None


def num_tok(prefix: str, number: str, suffix: str, shape: str) -> Tok:
    """A drawn word holding one number, e.g. prefix "ב-" + "1.1.2026"; the span is the part the number pattern finds."""
    m = NUM.match(number)
    assert m, number
    s = len(prefix)
    return Tok(prefix + number + suffix, [(s + m.start(), s + m.end(), shape)])


def phrase(rng: random.Random, shape: str, gersh: bool) -> list[Tok]:
    """A number in one of the contexts that trigger the split (PLAN §4): after a prefix letter, in parentheses,
    next to ₪ or ש"ח, after a Hebrew word."""
    q = "״" if gersh else '"'
    n = GEN[shape](rng)
    if shape == "label":  # a section reference inside a sentence: no trailing dot
        n = n.rstrip(".")
        c = rng.choice(("בסעיף", "לסעיף", "סעיף", "ס'", "(ראו"))
        if c == "(ראו":
            return [Tok("(ראו"), Tok("סעיף"), num_tok("", n, ")", "section_ref")]
        return [Tok(c), num_tok("", n, "", "section_ref")]
    if shape == "date":
        c = rng.random()
        if c < 0.35:
            return [num_tok(rng.choice(("ב-", "ב־", "מ-", "עד ה-")), n, "", "date")] if c < 0.25 else \
                [Tok("עד"), num_tok("ה-", n, "", "date")]
        if c < 0.55:
            return [Tok(rng.choice(("מיום", "ביום", "מתאריך", "תאריך"))), num_tok("", n, "", "date")]
        if c < 0.7:
            return [num_tok("(", n, ")", "date")]
        if c < 0.85:
            return [num_tok("", n, "", "date"), Tok(rng.choice(("-", "–", "עד"))), num_tok("", gen_date(rng), "", "date")]
        return [num_tok("", n, rng.choice((",", "")), "date")]
    if shape == "amount":
        c = rng.random()
        if c < 0.3:
            return [Tok("סך"), Tok("של"), num_tok("", n, "", "amount"), Tok(f"ש{q}ח")]
        if c < 0.5:
            return [Tok("₪"), num_tok("", n, "", "amount")]
        if c < 0.7:
            return [num_tok("", n, "", "amount"), Tok("₪")]
        if c < 0.8:
            return [num_tok("₪", n, "", "amount")]
        return [num_tok("", n, "", "amount"), Tok(rng.choice((f"ש{q}ח", f"ש{q}ח,", "שקלים")))]
    if shape == "percent":
        c = rng.random()
        if c < 0.4:
            return [Tok(rng.choice(("בשיעור", "שיעור", "עד", "לפחות"))), num_tok("", n, "", "percent")]
        if c < 0.6:
            return [num_tok("(", n, ")", "percent")]
        return [num_tok("", n, rng.choice(("", ",")), "percent"), Tok(rng.choice(("מהתמורה", "מההיקף", "מהסכום")))]
    c = rng.random()  # short_int
    if c < 0.3:
        return [Tok(rng.choice(("תוך", "לפחות", "עד"))), num_tok("", n, "", "short_int"), Tok(rng.choice(("ימים", "חודשים", "שנים", "יחידות")))]
    if c < 0.5:
        return [num_tok("(", n, ")", "short_int")]
    if c < 0.7:
        return [Tok(rng.choice(("פריט", "נספח", "טופס", "מס'"))), num_tok("", n, "", "short_int")]
    return [num_tok(rng.choice(("ב-", "ל-", "")), n, "", "short_int")]


def tokens_of(text: str, src: str | None) -> list[Tok]:
    return [Tok(w, [], src) for w in text.split()]


def join_line(toks: Sequence[Tok]) -> tuple[str, list[tuple[int, int, str]], list[str]]:
    text, spans, srcs, off = [], [], [], 0
    for i, t in enumerate(toks):
        if i:
            text.append(" "); off += 1
        normalized = unicodedata.normalize("NFC", t.text)
        if normalized == t.text:
            spans += [(off + a, off + b, tag) for a, b, tag in t.spans]
        else:
            spans += [(off + len(unicodedata.normalize("NFC", t.text[:a])),
                       off + len(unicodedata.normalize("NFC", t.text[:b])), tag)
                      for a, b, tag in t.spans]
        text.append(normalized); off += len(normalized)
        if t.src and t.src not in srcs:
            srcs.append(t.src)
    return "".join(text), spans, srcs


# --------------------------------------------------------------------------------------------------------------------
# page model


@dataclass
class Run:
    text: str
    x: float          # right edge (anchor "rs") or left edge (anchor "ls")
    y: float          # baseline
    anchor: str = "rs"


@dataclass
class PLine:
    kind: str
    text: str                          # drawn, logical, NFC
    face: str
    size: int
    weight: int | None
    runs: list[Run]
    spans: list[tuple[int, int, str]]
    sources: list[str] = field(default_factory=list)
    cell: dict | None = None
    box: tuple[int, int, int, int] | None = None   # page coordinates before degradation (ink bbox of the runs)


@dataclass
class Region:
    kind: str          # emblem, signature, stamp, rule
    box: tuple[int, int, int, int]


@dataclass
class Page:
    id: str
    family: str
    size: tuple[int, int]
    ink: int
    lines: list[PLine] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    rules: list[tuple[float, float, float, float, int]] = field(default_factory=list)  # x0, y0, x1, y1, width
    marks: list[tuple[str, dict]] = field(default_factory=list)  # image-only drawing ops
    meta: dict = field(default_factory=dict)


class Ctx:
    """Per-page state: rng, faces, text pool cursor and the page being built."""

    def __init__(self, page: Page, rng: random.Random, face: GovernedFace, bold: GovernedFace, faces: dict,
                 pool: "TextPool", split: str, rule_dropout: float):
        self.page, self.rng, self.face, self.bold, self.faces, self.pool = page, rng, face, bold, faces, pool
        self.split, self.rule_dropout = split, rule_dropout
        self.gersh = not missing_chars(face, "״׳") and rng.random() < 0.3
        self.refused = 0
        w, h = page.size
        self.margin_r = rng.randint(190, 300)
        self.margin_l = rng.randint(190, 300)
        self.top = rng.randint(200, 320)
        self.bottom = h - rng.randint(220, 320)
        self.x_right = w - self.margin_r
        self.x_left = self.margin_l
        self.pt = rng.uniform(9.5, 12.5)
        self.lead = rng.uniform(1.25, 1.6)
        self.y = self.top
        bw = rng.randint(400, 700)
        self.weight, _ = face_weight(face, bw)
        self.bold_weight, _ = face_weight(bold, rng.randint(650, 800))

    # sizes
    def px(self, pt: float) -> int:
        return max(12, round(pt * DPI / 72))

    def font(self, bold=False, pt=None):
        f = self.bold if bold else self.face
        w = self.bold_weight if bold else self.weight
        return f, _font(str(f.path), self.px(pt or self.pt), w), w

    def width(self, text: str, font) -> float:
        return font.getlength(text, direction="rtl") if text else 0.0

    def ok(self, face: GovernedFace, text: str) -> bool:
        try:
            check_shaping(face.path, text)
        except ShapingError:
            return False
        return True

    def line_gap(self, pt=None) -> float:
        return self.px(pt or self.pt) * self.lead

    # emitting lines
    def add(self, kind: str, toks: Sequence[Tok], x_right: float, y: float, bold=False, pt=None, anchor="rs",
            justify_to: float | None = None, cell: dict | None = None, gap_after_first: float | None = None) -> PLine | None:
        """Place one line at baseline y; its first token starts at x_right (anchor rs) or at x_right as a left edge
        (anchor ls). `gap_after_first` draws the first token on its own with that gap (a label and a tab gap).
        `justify_to` spreads words only if independent shaping keeps their bidi order."""
        face, font, w = self.font(bold, pt)
        text, spans, srcs = join_line(toks)
        if not text.strip():
            return None
        if not self.ok(face, text):
            self.refused += 1
            return None
        runs: list[Run] = []
        if gap_after_first is not None and len(toks) > 1 and isolated_words_safe(toks[0].text):
            first, rest = text.split(" ", 1)
            runs.append(Run(first, x_right, y))
            runs.append(Run(rest, x_right - self.width(first, font) - gap_after_first, y))
        elif justify_to is not None and len(toks) > 2 and isolated_words_safe(text):
            words = text.split(" ")
            widths = [self.width(t, font) for t in words]
            slack = (x_right - justify_to) - sum(widths)
            sp = slack / (len(words) - 1)
            if sp < self.width(" ", font) * 0.7 or sp > self.width(" ", font) * 4:
                runs.append(Run(text, x_right, y))
            else:
                x = x_right
                for t, wd in zip(words, widths):
                    runs.append(Run(t, x, y)); x -= wd + sp
        else:
            runs.append(Run(text, x_right, y, anchor))
        ln = PLine(kind, text, face.id, font.size, w, runs, spans, srcs, cell)
        ln.box = run_box(ln.runs, font)
        if (ln.box[0] < 20 or ln.box[2] > self.page.size[0] - 20
                or ln.box[1] < 0 or ln.box[3] > self.page.size[1]):
            self.refused += 1
            return None
        self.page.lines.append(ln)
        return ln

    def rule(self, x0, y0, x1, y1, w=None):
        self.page.rules.append((x0, y0, x1, y1, w or self.rng.randint(2, 4)))


def run_box(runs: Sequence[Run], font) -> tuple[int, int, int, int]:
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    bs = [d.textbbox((r.x, r.y), r.text, font=font, anchor=r.anchor, direction="rtl") for r in runs]
    return (math.floor(min(b[0] for b in bs)), math.floor(min(b[1] for b in bs)),
            math.ceil(max(b[2] for b in bs)), math.ceil(max(b[3] for b in bs)))


# --------------------------------------------------------------------------------------------------------------------
# text pool


class TextPool:
    """Caller-supplied text: {id, unit_id, text}. Pages draw consecutive lines of one unit."""

    def __init__(self, rows: Iterable[dict]):
        self.units: dict[str, list[tuple[str, str]]] = {}
        for n, r in enumerate(rows, 1):
            if not all(isinstance(r.get(k), str) and r.get(k) for k in ("id", "unit_id", "text")):
                raise ValueError(f"text pool row {n}: needs non-empty string 'id', 'unit_id' and 'text'")
            t = " ".join(unicodedata.normalize("NFC", r["text"]).split())
            if t:
                self.units.setdefault(str(r["unit_id"]), []).append((str(r["id"]), t))
        if not self.units:
            raise ValueError("the text pool is empty")
        self.unit_ids = sorted(self.units)

    def paragraph(self, rng: random.Random, face: GovernedFace, n_words: int) -> list[Tok]:
        """About n_words of consecutive text from one unit, skipping lines the face cannot draw."""
        for _ in range(20):
            unit = self.units[rng.choice(self.unit_ids)]
            i = rng.randrange(len(unit))
            out: list[Tok] = []
            while i < len(unit) and len(out) < n_words:
                lid, t = unit[i]
                if not missing_chars(face, t):
                    out += tokens_of(t, lid)
                i += 1
            if out:
                return out[:max(n_words, 3)]
        return []

    def words(self, rng: random.Random, face: GovernedFace, k: int) -> list[Tok]:
        """k Hebrew words (a cell label or a heading)."""
        for _ in range(20):
            p = self.paragraph(rng, face, 12)
            heb = [t for t in p if re.fullmatch(r"[א-ת\"'׳״\-־]+", t.text)]
            if len(heb) >= k:
                s = rng.randrange(len(heb) - k + 1)
                return heb[s:s + k]
        return [Tok("פריט")]


def holdout_units(unit_ids: Iterable[str], frac: float = 0.05, salt: str = "office_val") -> set[str]:
    """Units held out for office_val by a hash of the unit id (stable under any pool order or size)."""
    return {u for u in unit_ids if int(hashlib.sha256(f"{salt}:{u}".encode()).hexdigest()[:8], 16) < frac * 2 ** 32}


# --------------------------------------------------------------------------------------------------------------------
# body text with numbers


def sprinkle(c: Ctx, toks: list[Tok], density: float, free_shapes: dict[str, float]) -> list[Tok]:
    """Insert number phrases at word boundaries, about one per 1/density words."""
    out: list[Tok] = []
    shapes, weights = zip(*free_shapes.items())
    for t in toks:
        out.append(t)
        if c.rng.random() < density:
            out += phrase(c.rng, c.rng.choices(shapes, weights)[0], c.gersh)
    return out


INLINE = {"date": 0.34, "amount": 0.17, "percent": 0.15, "short_int": 0.08, "label": 0.26}


def wrap(c: Ctx, toks: list[Tok], width: float, first_width: float | None = None, bold=False) -> list[list[Tok]]:
    _, font, _ = c.font(bold)
    sp = c.width(" ", font)
    lines, cur, cw = [], [], 0.0
    lim = first_width if first_width is not None else width
    for t in toks:
        tw = c.width(t.text, font)
        if cur and cw + sp + tw > lim:
            lines.append(cur); cur, cw, lim = [], 0.0, width
        cur.append(t); cw += (sp if len(cur) > 1 else 0) + tw
    if cur:
        lines.append(cur)
    return lines


def paragraph_block(c: Ctx, toks: list[Tok], x_right: float, x_left: float, justify: bool, kind="body") -> None:
    rows = wrap(c, toks, x_right - x_left)
    for i, row in enumerate(rows):
        if c.y + c.line_gap() > c.bottom:
            return
        c.y += c.line_gap()
        last = i == len(rows) - 1
        c.add(kind, row, x_right, c.y, justify_to=x_left if justify and not last else None)


def heading(c: Ctx, toks: list[Tok], centered=False, pt=None) -> None:
    pt = pt or c.pt * c.rng.uniform(1.0, 1.35)
    c.y += c.line_gap(pt) * 1.3
    if c.y > c.bottom:
        return
    _, font, _ = c.font(True, pt)
    text = " ".join(t.text for t in toks)
    xr = c.x_right
    if centered:
        xr = (c.x_right + c.x_left) / 2 + c.width(text, font) / 2
    c.add("heading", toks, xr, c.y, bold=True, pt=pt)


# --------------------------------------------------------------------------------------------------------------------
# numbered structure


HEB_LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"


class Counter:
    """Hierarchical section counter: dotted levels, then (א)/(1)/א. sub-levels."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.path = [rng.randint(1, 40)]
        self.trailing = rng.random() < 0.5
        self.sub_style = rng.choice(("paren_heb", "paren_num", "heb_dot"))
        self.sub = 0

    def next(self) -> tuple[str, str, int]:
        """(label, shape, level). Moves deeper, stays or climbs at random; 2-4 dotted levels dominate."""
        r = self.rng.random()
        if r < 0.18 and len(self.path) > 1:
            self.path = self.path[:-1]; self.path[-1] += 1; self.sub = 0
        elif r < 0.45 and len(self.path) < 4:
            self.path.append(1); self.sub = 0
        elif r < 0.6:
            self.sub += 1
            if self.sub <= len(HEB_LETTERS):
                k = self.sub
                if self.sub_style == "paren_heb":
                    return f"({HEB_LETTERS[k - 1]})", "sub_heb", len(self.path) + 1
                if self.sub_style == "heb_dot":
                    return f"{HEB_LETTERS[k - 1]}.", "sub_heb", len(self.path) + 1
                return f"({k})", "sub_num", len(self.path) + 1
            self.sub = 0
        else:
            self.path[-1] += 1; self.sub = 0
        if len(self.path) == 1:
            self.path.append(1)
        s = ".".join(map(str, self.path))
        return (s + "." if self.trailing else s), "label", len(self.path)


def label_tok(label: str, shape: str) -> Tok:
    m = NUM.search(label)
    if not m:
        return Tok(label)
    return Tok(label, [(m.start(), m.end(), shape)])


def numbered_item(c: Ctx, ctr: Counter, words: int, density: float) -> None:
    label, shape, level = ctr.next()
    lt = label_tok(label, shape)
    face, font, _ = c.font()
    indent_step = c.rng.uniform(40, 110)
    x_right = c.x_right - indent_step * max(0, level - 2) * (1 if c.rng.random() < 0.7 else 0)
    tab = c.rng.random() < 0.5
    gap = c.rng.uniform(50, 200) if tab else c.width(" ", font) * c.rng.uniform(0.6, 1.2)
    lw = c.width(label, font)
    body = sprinkle(c, c.pool.paragraph(c.rng, face, words), density, INLINE)
    hang = c.rng.random() < 0.7
    text_right = x_right - lw - gap
    first_w = text_right - c.x_left
    rest_right = text_right if hang else x_right
    rows = wrap(c, body, rest_right - c.x_left, first_width=first_w)
    if not rows:
        return
    if c.y + c.line_gap() > c.bottom:
        return
    c.y += c.line_gap() * c.rng.uniform(1.0, 1.4)
    c.add("label_line", [lt] + rows[0], x_right, c.y, gap_after_first=gap)
    for row in rows[1:]:
        if c.y + c.line_gap() > c.bottom:
            return
        c.y += c.line_gap()
        c.add("body", row, rest_right, c.y)


def family_numbered(c: Ctx) -> None:
    if c.rng.random() < 0.6:
        heading(c, c.pool.words(c.rng, c.face, c.rng.randint(2, 5)), centered=c.rng.random() < 0.5)
    ctr = Counter(c.rng)
    if c.rng.random() < 0.2:  # a schedule block
        heading(c, [Tok(c.rng.choice(("תוספת", "התוספת", "תוספת ראשונה", "נספח"))) ] , centered=True)
        if c.rng.random() < 0.6:
            c.y += c.line_gap()
            _, font, _ = c.font()
            n = gen_label(c.rng, 2, False) if c.rng.random() < 0.5 else gen_short_int(c.rng)
            toks = [Tok("(סעיף"), num_tok("", n, ")", "section_ref")]
            c.add("body", toks, (c.x_right + c.x_left) / 2 + c.width(" ".join(x.text for x in toks), font) / 2, c.y)
    while c.y + 2 * c.line_gap() < c.bottom:
        if c.rng.random() < 0.08:
            definition(c)
        else:
            numbered_item(c, ctr, c.rng.randint(3, 20), 0.06)


def definition(c: Ctx) -> None:
    term = c.pool.words(c.rng, c.face, c.rng.randint(1, 2))
    q = "”" if c.rng.random() < 0.3 and c.ok(c.face, "“”") else '"'
    toks = [Tok(q + term[0].text)] + term[1:-1] + [Tok((term[-1].text if len(term) > 1 else "") + q)] if len(term) > 1 \
        else [Tok(q + term[0].text + q)]
    toks += [Tok(c.rng.choice(("-", "–", "—")))] + sprinkle(c, c.pool.paragraph(c.rng, c.face, c.rng.randint(5, 25)), 0.06, INLINE)
    c.y += c.line_gap() * 0.4
    paragraph_block(c, toks, c.x_right - c.rng.uniform(0, 80), c.x_left, False)


# --------------------------------------------------------------------------------------------------------------------
# running text


def family_running(c: Ctx) -> None:
    cols = 2 if c.rng.random() < 0.2 else 1
    justify = c.rng.random() < 0.6
    if c.rng.random() < 0.7:
        heading(c, c.pool.words(c.rng, c.face, c.rng.randint(2, 6)), centered=c.rng.random() < 0.6)
    ctr = Counter(c.rng)
    top = c.y
    gutter = c.rng.uniform(60, 120)
    colw = (c.x_right - c.x_left - gutter * (cols - 1)) / cols
    for col in range(cols):
        xr = c.x_right - col * (colw + gutter)
        xl = xr - colw
        c.y = top
        while c.y + 2 * c.line_gap() < c.bottom:
            toks = sprinkle(c, c.pool.paragraph(c.rng, c.face, c.rng.randint(10, 45)), 0.10, INLINE)
            if c.rng.random() < 0.85:  # a numbered paragraph opening: the label leads the line
                label, shape, _ = ctr.next()
                toks = [label_tok(label, shape)] + toks
            c.y += c.line_gap() * c.rng.uniform(0.3, 0.9)
            paragraph_block(c, toks, xr, xl, justify)
    if cols == 2:
        c.rule((c.x_right + c.x_left) / 2, top, (c.x_right + c.x_left) / 2, c.bottom, 2) if c.rng.random() < 0.4 else None


# --------------------------------------------------------------------------------------------------------------------
# tables

SCHEMAS = {
    "price_list": [("מס'", "idx"), ("תיאור", "text"), ("יחידה", "unit"), ("כמות", "int"), ("מחיר ליחידה", "amount"),
                   ("סה\"כ", "amount")],
    "bid_scores": [("מס'", "idx"), ("הצעה", "text"), ("ניקוד מחיר", "score"), ("ניקוד איכות", "score"),
                   ("משקל", "percent"), ("סה\"כ", "score")],
    "schedule": [("שלב", "label"), ("תיאור", "text"), ("מתאריך", "date"), ("עד תאריך", "date"), ("היקף", "percent")],
    "budget": [("סעיף", "label"), ("תיאור", "text"), ("תקציב", "amount"), ("ביצוע", "amount"), ("שיעור ביצוע", "percent")],
    "quantities": [("פריט", "label"), ("תיאור", "text"), ("כמות", "int"), ("יחידה", "unit"), ("הערות", "short")],
    "payment_schedule": [("תשלום", "idx"), ("מועד", "date"), ("אבן דרך", "text"), ("סכום", "amount"),
                         ("% מהתמורה", "percent")],
}
UNITS = ("יח'", "מ\"ר", "מ\"א", "קומפ'", "ק\"ג", "טון", "שעה", "חודש")


def item_labels(r: random.Random, n: int) -> list[str]:
    """Item numbers of a bill of quantities: chapter.section.item (`3.2.1`, `3.2.2`, ...), dot style per table."""
    ch, sec = r.randint(1, 40), r.randint(1, 12)
    levels = r.choice((2, 3, 3))
    dot = r.random() < 0.25
    out, k = [], 0
    for _ in range(n):
        k += 1
        if levels == 3 and r.random() < 0.15:
            sec, k = sec + 1, 1
        s = f"{ch}.{sec}.{k}" if levels == 3 else f"{ch}.{k}"
        out.append(s + "." if dot else s)
    return out


def cell_toks(c: Ctx, typ: str, row: int, shekel: str, items: list[str] | None = None) -> list[Tok]:
    r = c.rng
    if typ == "idx":
        if items is not None and row < len(items):
            return [num_tok("", items[row], "", "label")]
        return [num_tok("", str(row + 1), "", "short_int")]
    if typ == "int":
        return [num_tok("", gen_short_int(r) if r.random() < 0.7 else gen_amount(r).split(".")[0], "", "short_int")]
    if typ == "score":
        v = f"{r.uniform(0, 100):.{r.choice((0, 1, 2))}f}"
        return [num_tok("", v, "", "short_int" if "." not in v else "amount")]
    if typ == "amount":
        a = gen_amount(r)
        if shekel == "before":
            return [Tok("₪"), num_tok("", a, "", "amount")] if r.random() < 0.6 else [num_tok("₪", a, "", "amount")]
        if shekel == "after":
            return [num_tok("", a, "", "amount"), Tok("₪")]
        return [num_tok("", a, "", "amount")]
    if typ == "percent":
        return [num_tok("", gen_percent(r), "", "percent")]
    if typ == "date":
        return [num_tok("", gen_date(r), "", "date")]
    if typ == "label":
        return [num_tok("", gen_label(r, r.choice((2, 2, 3)), r.random() < 0.3), "", "label")] if r.random() < 0.85 \
            else [num_tok("", gen_short_int(r), "", "short_int")]
    if typ == "unit":
        return [Tok(r.choice(UNITS))]
    if typ == "short":
        return c.pool.words(r, c.face, r.randint(1, 2)) if r.random() < 0.6 else []
    return c.pool.words(r, c.face, r.randint(1, 4))


def table(c: Ctx, schema_name: str) -> None:
    r = c.rng
    cols = SCHEMAS[schema_name]
    if r.random() < 0.3 and len(cols) > 4:
        cols = [cols[0]] + r.sample(cols[1:], len(cols) - 2)
        cols.sort(key=lambda x: SCHEMAS[schema_name].index(x))
    nrows = r.randint(4, 18)
    shekel = r.choice(("before", "after", "none", "header"))
    ruling = r.choices(("grid", "header_only", "rows", "none"), (0.4, 0.2, 0.2, 0.2))[0]
    pt = c.pt * r.uniform(0.85, 1.0)
    head = []
    for name, typ in cols:
        t = name + (" (₪)" if shekel == "header" and typ == "amount" else "")
        head.append(tokens_of(t, None))
    items = item_labels(r, nrows) if r.random() < 0.8 else None
    body = [[cell_toks(c, typ, i, shekel, items) for _, typ in cols] for i in range(nrows)]
    total = r.random() < 0.5 and any(typ == "amount" for _, typ in cols)
    if total:
        body.append([[Tok("סה\"כ")] if j == (1 if len(cols) > 1 else 0) else
                     (cell_toks(c, "amount", 0, shekel) if typ == "amount" else []) for j, (_, typ) in enumerate(cols)])
    padf = r.uniform(0.3, 0.6)
    avail = c.x_right - c.x_left
    for _ in range(4):  # a table too wide for the page is set in a smaller size, down to 70% of the body size
        _, font, _ = c.font(False, pt)
        _, bfont, _ = c.font(True, pt)
        pad = c.px(pt) * padf
        widths = []
        for j in range(len(cols)):
            w = max([c.width(join_line(head[j])[0], bfont)] + [c.width(join_line(row[j])[0], font) for row in body])
            widths.append(w + 2 * pad)
        if sum(widths) <= avail:
            break
        pt *= max(0.85, avail / sum(widths))
    if sum(widths) > avail or pt < c.pt * 0.7:
        return
    extra = (avail - sum(widths)) * r.uniform(0, 1)
    tj = [j for j, (_, t) in enumerate(cols) if t == "text"] or [0]
    for j in tj:
        widths[j] += extra / len(tj)
    rh = c.px(pt) * r.uniform(1.5, 2.1)
    group = r.random() < 0.3 and sum(1 for _, t in cols if t == "amount") >= 2
    n_head = 2 if group else 1
    if c.y + rh * (n_head + 3) > c.bottom:
        return
    x_edges = [c.x_right]
    for w in widths:
        x_edges.append(x_edges[-1] - w)
    y0 = c.y + rh * 0.4
    tid = len([ln for ln in c.page.lines if ln.cell]) and max(ln.cell["table"] for ln in c.page.lines if ln.cell) + 1 or 0
    align = r.choice(("start", "center", "end"))
    ytop = y0
    if group:  # a merged header over the amount columns
        aj = [j for j, (_, t) in enumerate(cols) if t == "amount"]
        a0, a1 = min(aj), max(aj)
        xr, xl = x_edges[a0], x_edges[a1 + 1]
        toks = tokens_of(r.choice(("תמורה", "עלות", "סכומים")), None)
        tw = c.width(join_line(toks)[0], bfont)
        c.add("cell_header", toks, (xr + xl) / 2 + tw / 2, ytop + rh * 0.68, bold=True, pt=pt,
              cell={"table": tid, "row": -2, "col": a0, "colspan": a1 - a0 + 1})
        if ruling == "grid":
            c.rule(xl, ytop + rh, xr, ytop + rh)
        ytop += rh
    yy = ytop
    for i, row in enumerate([head] + body):
        if yy + rh > c.bottom:
            break
        for j, toks in enumerate(row):
            if not toks:
                continue
            xr, xl = x_edges[j] - pad, x_edges[j + 1] + pad
            fnt = bfont if i == 0 else font
            tw = c.width(join_line(toks)[0], fnt)
            numeric = any(t.spans for t in toks)
            a = align if numeric else "start"
            x = xr if a == "start" else (xl + tw if a == "end" else (xr + xl) / 2 + tw / 2)
            c.add("cell_header" if i == 0 else "cell", toks, x, yy + rh * 0.68, bold=i == 0, pt=pt,
                  cell={"table": tid, "row": i - 1, "col": j, "schema": schema_name, "ruling": ruling,
                        "rect": [round(x_edges[j + 1]), round(yy), round(x_edges[j]), round(yy + rh)]})
        yy += rh
        if ruling in ("grid", "rows") or (ruling == "header_only" and i == 0):
            c.rule(x_edges[-1], yy, x_edges[0], yy)
    if ruling == "grid":
        c.rule(x_edges[-1], y0, x_edges[0], y0)
        for x in x_edges:
            c.rule(x, y0, x, yy)
    elif ruling == "header_only":
        c.rule(x_edges[-1], y0, x_edges[0], y0)
    c.y = yy + rh * 0.5


def family_tables(c: Ctx) -> None:
    names = [n for n in SCHEMAS if (n == HELD_OUT_TABLE_SCHEMA) == (c.split == "val")]
    if c.split == "val":
        names = sorted(SCHEMAS)  # office_val: every schema, the held-out one included
    ctr = Counter(c.rng)
    for _ in range(c.rng.choice((1, 1, 2))):
        if c.y + 6 * c.line_gap() > c.bottom:
            break
        label, shape, _ = ctr.next()
        heading(c, [label_tok(label, shape)] + c.pool.words(c.rng, c.face, c.rng.randint(1, 4)))
        if c.rng.random() < 0.5:
            paragraph_block(c, sprinkle(c, c.pool.paragraph(c.rng, c.face, c.rng.randint(10, 40)), 0.08, INLINE),
                            c.x_right, c.x_left, False)
        c.y += c.line_gap()
        table(c, c.rng.choice(names))
    while c.y + 3 * c.line_gap() < c.bottom and c.rng.random() < 0.85:  # notes under the table
        numbered_item(c, ctr, c.rng.randint(5, 25), 0.08)


# --------------------------------------------------------------------------------------------------------------------
# front matter

AUTHORITIES = ("משרד הדוגמה", "הרשות לבדיקות", "המועצה האזורית לדוגמה", "החברה הממשלתית לניסוי", "עיריית הדוגמה",
               "המרכז לשירותים לדוגמה", "הרשות הארצית לתרגול")
UNITS_ORG = ("אגף הרכש והלוגיסטיקה", "מינהלת המכרזים", "היחידה המשפטית", "אגף הכספים", "ועדת המכרזים")
FIRST = ("אורי", "נועה", "דנה", "יואב", "מיכל", "עמית", "רונית", "אלון", "תמר", "גיל", "שירה", "עידו", "ליאת", "רועי")
LAST = ("כהן-דוגמה", "לוי-בדיקה", "ניסיוני", "דוגמאי", "בדיקתי", "פלוני", "אלמוני", "תרגולי")
TITLES = ("מנהל/ת הרכש", "יו\"ר ועדת המכרזים", "ממונה על המכרזים", "מנהל/ת האגף", "רכז/ת מכרזים")


def family_front(c: Ctx) -> None:
    r = c.rng
    W = c.page.size[0]
    em = r.randint(160, 260)
    ex = r.choice(("center", "right"))
    cx = W / 2 if ex == "center" else c.x_right - em / 2
    emblem(c, cx, c.top + em / 2, em)
    c.y = c.top + em + 20
    _, bfont, _ = c.font(True, c.pt * 1.3)
    for t, bold in ((r.choice(AUTHORITIES), True), (r.choice(UNITS_ORG), False)):
        toks = tokens_of(t, None)
        f = bfont if bold else c.font()[1]
        c.y += c.line_gap(c.pt * (1.3 if bold else 1))
        xr = cx + c.width(t, f) / 2 if ex == "center" else c.x_right
        c.add("front", toks, xr, c.y, bold=bold, pt=c.pt * (1.3 if bold else 1))
    q = "'"
    c.y += c.line_gap()
    ph = [Tok("טל" + q), num_tok("", f"0{r.randint(2, 9)}-{r.randint(1000000, 9999999)}", "", "phone")]
    if r.random() < 0.7:
        ph += [Tok("פקס"), num_tok("", f"0{r.randint(2, 9)}-{r.randint(1000000, 9999999)}", "", "phone")]
    _, font, _ = c.font()
    c.add("front", ph, cx + c.width(join_line(ph)[0], font) / 2 if ex == "center" else c.x_right, c.y)
    c.rule(c.x_left, c.y + c.line_gap() * 0.5, c.x_right, c.y + c.line_gap() * 0.5, r.randint(2, 5))
    c.y += c.line_gap() * 1.2
    # date and reference, on the left
    for toks in ([Tok("תאריך:"), num_tok("", gen_date(r), "", "date")] if r.random() < 0.6 else [num_tok("", gen_date(r), "", "date")],
                 [Tok("סימוכין:"), num_tok("", f"{r.randint(1, 9999)}/{r.randint(2015, 2030)}", "", "short_int")]):
        c.y += c.line_gap()
        c.add("front", toks, c.x_left, c.y, anchor="ls")
    c.y += c.line_gap() * 0.6
    for toks in ([Tok("לכבוד")], tokens_of(f"{r.choice(FIRST)} {r.choice(LAST)}", None),
                 tokens_of(r.choice(UNITS_ORG), None)):
        c.y += c.line_gap()
        c.add("front", toks, c.x_right, c.y)
    c.y += c.line_gap() * 1.4
    year = r.randint(2015, 2030)
    subj = [Tok("הנדון:"), Tok("מכרז"), Tok("מס'"), num_tok("", f"{r.randint(1, 99)}/{year}", "", "short_int"),
            Tok(r.choice(("-", "–")))] + c.pool.words(r, c.face, r.randint(2, 5))
    c.add("front", subj, c.x_right, c.y, bold=True)
    ctr = Counter(r)
    c.y += c.line_gap() * 0.5
    sig_y = c.bottom - c.line_gap() * 7
    while c.y + 2 * c.line_gap() < sig_y:
        if r.random() < 0.6:
            numbered_item(c, ctr, r.randint(8, 30), 0.08)
        else:
            c.y += c.line_gap() * 0.5
            paragraph_block(c, sprinkle(c, c.pool.paragraph(r, c.face, r.randint(15, 50)), 0.08, INLINE),
                            c.x_right, c.x_left, r.random() < 0.5)
    c.y = max(c.y, sig_y) + c.line_gap()
    c.add("front", [Tok("בכבוד"), Tok("רב,")], c.x_left + (c.x_right - c.x_left) * 0.35, c.y)
    # the signature sits between the closing and the name, the stamp beside it; lines they still overlap are masked
    sh = r.randint(90, 150)
    sx = c.x_left + (c.x_right - c.x_left) * r.uniform(0.25, 0.4)
    signature(c, sx, c.y + 40, r.randint(260, 420), sh)
    if r.random() < 0.5:
        st = r.randint(170, 280)
        stamp(c, sx - st / 2 - r.uniform(20, 120), c.y + 40 + sh / 2 + r.uniform(-40, 40), st)
    c.y += sh + 110
    name = tokens_of(f"{r.choice(FIRST)} {r.choice(LAST)}", None)
    c.add("front", name, c.x_left + (c.x_right - c.x_left) * 0.35, c.y)
    c.y += c.line_gap()
    c.add("front", tokens_of(r.choice(TITLES), None), c.x_left + (c.x_right - c.x_left) * 0.35, c.y)


# --------------------------------------------------------------------------------------------------------------------
# image-only marks (generated; never labelled)


def emblem(c: Ctx, cx: float, cy: float, size: float) -> None:
    r = c.rng
    k = r.choice((5, 6, 7, 8, 12))
    c.page.marks.append(("emblem", {"cx": cx, "cy": cy, "size": size, "k": k, "rings": r.randint(1, 3),
                                     "rot": r.uniform(0, math.pi), "fill": r.random() < 0.5}))
    c.page.regions.append(Region("emblem", (int(cx - size / 2), int(cy - size / 2), int(cx + size / 2), int(cy + size / 2))))


def signature(c: Ctx, x: float, y: float, w: float, h: float) -> None:
    r = c.rng
    pts, n = [], r.randint(14, 30)
    for i in range(n):
        pts.append((x + w * i / (n - 1) + r.uniform(-20, 20), y + h / 2 + math.sin(i * r.uniform(0.6, 1.6)) * h / 2.4
                    + r.uniform(-h / 6, h / 6)))
    c.page.marks.append(("signature", {"pts": pts, "width": r.randint(3, 6), "loops": r.randint(0, 3), "seed": r.random()}))
    c.page.regions.append(Region("signature", (int(x - 30), int(y - 20), int(x + w + 30), int(y + h + 20))))


def stamp(c: Ctx, cx: float, cy: float, size: float) -> None:
    r = c.rng
    c.page.marks.append(("stamp", {"cx": cx, "cy": cy, "size": size, "round": r.random() < 0.6,
                                    "grey": r.randint(60, 150), "rot": r.uniform(-25, 25),
                                    "text": r.choice(("נתקבל", "העתק נאמן למקור", "אושר", "נבדק")),
                                    "date": gen_date(r)}))
    c.page.regions.append(Region("stamp", (int(cx - size / 2 - 10), int(cy - size / 2 - 10),
                                           int(cx + size / 2 + 10), int(cy + size / 2 + 10))))


def draw_marks(img: Image.Image, page: Page, faces: dict, rng: random.Random) -> None:
    d = ImageDraw.Draw(img)
    for kind, m in page.marks:
        if kind == "emblem":
            cx, cy, s = m["cx"], m["cy"], m["size"]
            for i in range(m["rings"]):
                rr = s / 2 - i * s / 10
                d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=page.ink, width=4)
            rr = s / 2 - m["rings"] * s / 10
            pts = []
            for i in range(2 * m["k"]):
                a = m["rot"] + i * math.pi / m["k"]
                q = rr * (1 if i % 2 == 0 else 0.45)
                pts.append((cx + q * math.cos(a), cy + q * math.sin(a)))
            d.polygon(pts, outline=page.ink, fill=page.ink if m["fill"] else None, width=3)
        elif kind == "signature":
            pts = m["pts"]
            d.line(pts, fill=page.ink, width=m["width"], joint="curve")
            sr = random.Random(m["seed"])
            for _ in range(m["loops"]):
                i = sr.randrange(len(pts))
                x, y = pts[i]
                rr = sr.uniform(15, 45)
                d.arc((x - rr, y - rr, x + rr, y + rr), sr.uniform(0, 180), sr.uniform(200, 360), fill=page.ink,
                      width=m["width"])
        elif kind == "stamp":
            s = int(m["size"])
            layer = Image.new("L", (s + 40, s + 40), 0)
            ld = ImageDraw.Draw(layer)
            if m["round"]:
                ld.ellipse((20, 20, 20 + s, 20 + s), outline=255, width=6)
                ld.ellipse((40, 40, s, s), outline=255, width=3)
            else:
                ld.rectangle((20, 20 + s * 0.2, 20 + s, 20 + s * 0.8), outline=255, width=6)
            face = faces.get("arimo") or next(iter(faces.values()))
            f = _font(str(face.path), max(14, s // 7))
            for txt, dy in ((m["text"], -s * 0.08), (m["date"], s * 0.12)):
                ld.text((20 + s / 2, 20 + s / 2 + dy), txt, font=f, fill=255, anchor="mm", direction="rtl")
            layer = layer.rotate(m["rot"], resample=Image.Resampling.BICUBIC)
            ink = Image.new("L", layer.size, m["grey"])
            x0, y0 = int(m["cx"] - layer.width / 2), int(m["cy"] - layer.height / 2)
            base = img.crop((x0, y0, x0 + layer.width, y0 + layer.height))
            img.paste(ImageChops.darker(base, ink), (x0, y0), layer)


# --------------------------------------------------------------------------------------------------------------------
# headers, footers, counters


def furniture(c: Ctx, page_no: int, n_pages: int) -> None:
    r = c.rng
    pt = c.pt * r.uniform(0.75, 0.9)
    _, font, _ = c.font(False, pt)
    W, H = c.page.size
    if r.random() < 0.8 and c.page.family != "front_matter":
        y = c.top - c.line_gap(pt) * 1.2
        c.add("header", tokens_of(r.choice(AUTHORITIES), None), c.x_right, y, pt=pt)
        yr = r.randint(2015, 2030)
        hl = [Tok("מכרז"), Tok("מס'"), num_tok("", f"{r.randint(1, 99)}/{yr}", "", "short_int")]
        c.add("header", hl, c.x_left, y, pt=pt, anchor="ls")
        if r.random() < 0.6:
            c.rule(c.x_left, y + c.px(pt) * 0.4, c.x_right, y + c.px(pt) * 0.4, 2)
    fy = H - r.randint(130, 200)
    style = r.choice(("of", "dash", "slash", "bare"))
    if style == "of":
        toks = [Tok("עמוד"), num_tok("", str(page_no), "", "short_int"), Tok("מתוך"), num_tok("", str(n_pages), "", "short_int")]
    elif style == "dash":
        toks = [Tok("-"), num_tok("", str(page_no), "", "short_int"), Tok("-")]
    elif style == "slash":
        toks = [num_tok("", f"{page_no}/{n_pages}", "", "short_int")]
    else:
        toks = [num_tok("", str(page_no), "", "short_int")]
    tw = c.width(join_line(toks)[0], font)
    where = r.choice(("center", "left", "right"))
    x = {"center": W / 2 + tw / 2, "left": c.x_left + tw, "right": c.x_right}[where]
    c.add("counter", toks, x, fy, pt=pt)
    if r.random() < 0.15 and c.y < c.bottom - 3 * c.line_gap(pt):  # a footnote under a short rule
        y = c.bottom - c.line_gap(pt)
        c.rule(c.x_right - 500, y - c.px(pt), c.x_right, y - c.px(pt), 2)
        toks = [num_tok("", str(r.randint(1, 30)), "", "short_int")] + sprinkle(
            c, c.pool.paragraph(r, c.face, r.randint(6, 18)), 0.1, INLINE)
        rows = wrap(c, toks, c.x_right - c.x_left)
        c.add("footnote", rows[0], c.x_right, y, pt=pt)


# --------------------------------------------------------------------------------------------------------------------
# geometry


def homography(src: Sequence[tuple[float, float]], dst: Sequence[tuple[float, float]]) -> list[float]:
    """3x3 H (row-major, h33 = 1) with H(src[i]) = dst[i] for four point pairs."""
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    n = 8
    M = [row[:] + [bb] for row, bb in zip(A, b)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(M[k][i]))
        M[i], M[p] = M[p], M[i]
        for k in range(n):
            if k != i:
                f = M[k][i] / M[i][i]
                M[k] = [a - f * c for a, c in zip(M[k], M[i])]
    h = [M[i][n] / M[i][i] for i in range(n)]
    return h + [1.0]


def apply_h(H: Sequence[float], x: float, y: float) -> tuple[float, float]:
    w = H[6] * x + H[7] * y + H[8]
    return (H[0] * x + H[1] * y + H[2]) / w, (H[3] * x + H[4] * y + H[5]) / w


def invert_h(H: Sequence[float]) -> list[float]:
    a, b, c, d, e, f, g, h, i = H
    co = [e * i - f * h, c * h - b * i, b * f - c * e, f * g - d * i, a * i - c * g, c * d - a * f,
          d * h - e * g, b * g - a * h, a * e - b * d]
    det = a * co[0] + b * co[3] + c * co[6]
    inv = [v / det for v in co]
    return [v / inv[8] for v in inv]


def warp(img: Image.Image, H: Sequence[float], size: tuple[int, int], fill: int) -> Image.Image:
    inv = invert_h(H)
    return img.transform(size, Image.Transform.PERSPECTIVE, tuple(inv[:8]), Image.Resampling.BICUBIC, fillcolor=fill)


def geometry(model: str, page_size: tuple[int, int], rng: random.Random) -> tuple[list[float], tuple[int, int], dict]:
    """The page homography, output size and its parameters for a degradation model (scale to the target dpi,
    skew, and the phone's perspective)."""
    W, H = page_size
    if model == "office_scan":
        dpi = rng.randint(200, 400)
        skew = rng.triangular(-3, 3, 0)
        persp = 0.0
    elif model == "photocopy":
        dpi = rng.randint(200, 300)
        skew = rng.triangular(-2, 2, 0)
        persp = 0.0
    elif model == "phone_photo":
        dpi = rng.randint(150, 250)
        skew = rng.triangular(-3, 3, 0)  # what the app's deskew leaves
        persp = rng.uniform(0, 6)
    else:
        dpi = rng.randint(150, 300)
        skew = 0.0
        persp = 0.0
    s = dpi / DPI
    cx, cy = W / 2, H / 2
    a = math.radians(skew)
    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    dst = []
    t = math.tan(math.radians(persp)) / 4
    side = rng.randrange(4)
    for k, (x, y) in enumerate(corners):
        dx, dy = x - cx, y - cy
        if persp:  # keystone: the two corners of one side pulled in
            if side in (0, 2) and ((k in (0, 1)) == (side == 0)):
                dx *= 1 - t
            if side in (1, 3) and ((k in (1, 2)) == (side == 1)):
                dy *= 1 - t
            dx += rng.uniform(-1, 1) * t * W * 0.1
            dy += rng.uniform(-1, 1) * t * H * 0.1
        rx, ry = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
        dst.append((rx * s + cx * s, ry * s + cy * s))
    size = (round(W * s), round(H * s))
    Hm = homography(corners, dst)
    return Hm, size, {"dpi": dpi, "skew_deg": round(skew, 4), "perspective_deg": round(persp, 4),
                      "keystone_side": side if persp else None}


# --------------------------------------------------------------------------------------------------------------------
# photometric degradation


def _lut(img: Image.Image, f) -> Image.Image:
    return img.point([max(0, min(255, round(f(v)))) for v in range(256)])


def _noise(img: Image.Image, std: float, rng: random.Random) -> Image.Image:
    if std <= 0:
        return img
    k = std / 73.9
    n = Image.frombytes("L", img.size, rng.randbytes(img.width * img.height)).point(
        lambda v: max(0, min(255, round(128 + (v - 128) * k))))
    return ImageChops.add(img, n, scale=1.0, offset=-128)


def _jpeg(img: Image.Image, q: int) -> Image.Image:
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=q); buf.seek(0)
    return Image.open(buf).convert("L")


def _otsu_bin(img: Image.Image) -> Image.Image:
    from .line_render import _otsu  # noqa: PLC0415
    t = _otsu(img)
    return img.point(lambda v: 255 if v > t else 0)


def _gradient(size: tuple[int, int], rng: random.Random, lo: float, hi: float) -> Image.Image:
    g = Image.linear_gradient("L").rotate(rng.uniform(0, 360), resample=Image.Resampling.BICUBIC, expand=False,
                                          fillcolor=128).resize(size, Image.Resampling.BILINEAR)
    return _lut(g, lambda v: 255 * (lo + (hi - lo) * v / 255))


def photometric(img: Image.Image, model: str, rng: random.Random, paper_fill: int) -> tuple[Image.Image, dict]:
    p: dict = {}
    if model == "clean":
        return img, p
    if model == "office_scan":
        paper, ink = rng.randint(228, 252), rng.randint(0, 40)
        img = _lut(img, lambda v: ink + (paper - ink) * v / 255)
        if rng.random() < 0.3:  # bleed-through of the page's own back side, faint and blurred
            a = rng.uniform(0.03, 0.09)
            back = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT).filter(ImageFilter.GaussianBlur(2.5))
            img = ImageChops.darker(img, _lut(back, lambda v: 255 - (255 - v) * a))
            p["bleed"] = round(a, 3)
        blur = rng.uniform(0.2, 0.9)
        img = img.filter(ImageFilter.GaussianBlur(blur))
        std = rng.uniform(1, 6)
        img = _noise(img, std, rng)
        b = rng.choices(("grey", "otsu", "fixed"), (0.5, 0.35, 0.15))[0]
        if b == "otsu":
            img = _otsu_bin(img)
        elif b == "fixed":
            t = rng.randint(120, 170)
            img = img.point(lambda v: 255 if v > t else 0)
        q = rng.randint(70, 92)
        img = _jpeg(img, q)
        p.update(paper=paper, ink=ink, blur=round(blur, 3), noise=round(std, 3), binarise=b, jpeg=q)
        return img, p
    if model == "photocopy":
        gens = rng.choice((1, 2))
        p["generations"] = gens
        for g in range(gens):
            gamma = rng.uniform(1.3, 2.2)
            img = _lut(img, lambda v: 255 * (v / 255) ** gamma)
            stroke = rng.choices(("keep", "thicken", "thin"), (0.4, 0.4, 0.2))[0]
            if stroke == "thicken":
                img = img.filter(ImageFilter.MinFilter(3))
            elif stroke == "thin":
                img = img.filter(ImageFilter.MaxFilter(3))
            d = ImageDraw.Draw(img)
            dens = rng.uniform(0.000025, 0.0002)  # halved 2026-11-18: denser specks sat inside letters like a dagesh
            for _ in range(int(img.width * img.height * dens)):
                x, y, rr = rng.randrange(img.width), rng.randrange(img.height), rng.uniform(0.6, 2.2)
                d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=rng.randint(0, 90))
            edge = rng.choice(("left", "right", "top", "bottom"))
            wpx = rng.randint(20, 140)
            sh = Image.new("L", img.size, 255)
            sd = ImageDraw.Draw(sh)
            dark = rng.uniform(60, 150)
            for k in range(wpx):
                v = round(255 - dark * (1 - k / wpx) ** 2)
                if edge == "left":
                    sd.line((k, 0, k, img.height), fill=v)
                elif edge == "right":
                    sd.line((img.width - 1 - k, 0, img.width - 1 - k, img.height), fill=v)
                elif edge == "top":
                    sd.line((0, k, img.width, k), fill=v)
                else:
                    sd.line((0, img.height - 1 - k, img.width, img.height - 1 - k), fill=v)
            img = ImageChops.multiply(img, sh)
            band = Image.new("L", img.size, 255)
            bd = ImageDraw.Draw(band)
            y = 0
            while y < img.height:
                hgt = rng.randint(30, 220)
                bd.rectangle((0, y, img.width, y + hgt), fill=255 - rng.randint(0, 14))
                y += hgt
            img = ImageChops.multiply(img, band)
            p[f"gen{g}"] = {"gamma": round(gamma, 3), "stroke": stroke, "speckle": round(dens, 6), "shadow_edge": edge,
                            "shadow_px": wpx}
        blur = rng.uniform(0.2, 0.7)
        img = img.filter(ImageFilter.GaussianBlur(blur))
        q = rng.randint(75, 92)
        img = _jpeg(img, q)
        p.update(blur=round(blur, 3), jpeg=q)
        return img, p
    # phone_photo
    lo = rng.uniform(0.62, 0.9)
    img = ImageChops.multiply(img, _gradient(img.size, rng, lo, 1.0))
    v = Image.radial_gradient("L").resize(img.size, Image.Resampling.BILINEAR)
    vig = rng.uniform(0.05, 0.25)
    img = ImageChops.multiply(img, _lut(v, lambda x: 255 * (1 - vig * (x / 255) ** 2)))
    kind = rng.choice(("defocus", "motion"))
    if kind == "defocus":
        r_ = rng.uniform(0.5, 1.6)
        img = img.filter(ImageFilter.GaussianBlur(r_))
    else:
        r_ = rng.choice((3, 5))
        horiz = rng.random() < 0.5
        k = [0.0] * (r_ * r_)
        for i in range(r_):
            k[(r_ // 2) * r_ + i if horiz else i * r_ + r_ // 2] = 1.0
        img = img.filter(ImageFilter.Kernel((r_, r_), k, scale=r_))
    std = rng.uniform(2, 8)
    img = _noise(img, std, rng)
    q = rng.randint(60, 85)
    img = _jpeg(img, q)
    p.update(light_min=round(lo, 3), vignette=round(vig, 3), blur_kind=kind, blur=round(r_, 3), noise=round(std, 3),
             jpeg=q)
    return img, p


# --------------------------------------------------------------------------------------------------------------------
# rendering, crops, writing


def draw_page(page: Page, rule_dropout: float, rng: random.Random, faces: dict) -> Image.Image:
    img = Image.new("L", page.size, 255)
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1, w in page.rules:
        if rule_dropout and w <= 3:  # a thin rule a copier drops out in places
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 40))
            for k in range(n):
                if rng.random() < rule_dropout:
                    continue
                a, b = k / n, (k + 1) / n
                d.line((x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, x0 + (x1 - x0) * b, y0 + (y1 - y0) * b), fill=page.ink, width=w)
        else:
            d.line((x0, y0, x1, y1), fill=page.ink, width=w)
    for ln in page.lines:
        draw_line(d, ln, faces, page.ink)
    draw_marks(img, page, faces, rng)
    return img


def draw_line(d: ImageDraw.ImageDraw, ln: PLine, faces: dict, ink: int) -> None:
    f = _font(str(faces[ln.face].path), ln.size, ln.weight)
    for r in ln.runs:
        d.text((r.x, r.y), r.text, font=f, fill=ink, anchor=r.anchor, direction="rtl")


def padded(box: tuple[int, int, int, int], size: int, cell: dict | None = None,
           rng: random.Random | None = None) -> tuple[float, float, float, float]:
    """The crop box around a line's ink. A cell's crop reaches toward its cell rectangle by a random share (up to a
    little past it), so some cell crops carry border remnants, as a cell cut from a real ruled table does."""
    pv, ph = max(4, size * 0.18), max(6, size * 0.3)
    b = [box[0] - ph, box[1] - pv, box[2] + ph, box[3] + pv]
    if cell and cell.get("rect") and rng is not None:
        rect = cell["rect"]
        for k, out in ((0, -1), (1, -1), (2, 1), (3, 1)):
            t = rng.uniform(0.0, 1.15)
            reach = rect[k] + out * 4
            b[k] = b[k] + (reach - b[k]) * t if (reach - b[k]) * out > 0 else b[k]
    return b[0], b[1], b[2], b[3]


def quad(H: Sequence[float], box: Sequence[float]) -> list[tuple[float, float]]:
    """The box's corners on the degraded page: upper-left, lower-left, lower-right, upper-right (PIL QUAD order)."""
    x0, y0, x1, y1 = box
    return [apply_h(H, x, y) for x, y in ((x0, y0), (x0, y1), (x1, y1), (x1, y0))]


def rectified_crop(img: Image.Image, q: Sequence[tuple[float, float]], scale: float, box: Sequence[float]) -> Image.Image:
    w = max(1, round((box[2] - box[0]) * scale))
    h = max(1, round((box[3] - box[1]) * scale))
    data = tuple(v for pt in q for v in pt)
    return img.transform((w, h), Image.Transform.QUAD, data, Image.Resampling.BICUBIC)


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _page_rng(seed: int, page_id: str, part: str = "") -> random.Random:
    return random.Random(int(hashlib.sha256(f"{seed}:{page_id}:{part}".encode()).hexdigest()[:16], 16))


def build_page(pool: TextPool, faces: dict, page_id: str, seed: int, split: str, family: str | None = None,
               face_id: str | None = None) -> tuple[Page, Ctx]:
    rng = _page_rng(seed, page_id)
    fam = family or rng.choices(list(FAMILY_MIX), list(FAMILY_MIX.values()))[0]
    names = page_faces(faces, split)
    weights = [3 if f in OFFICE_FACES else 1 for f in names]
    fid = face_id or rng.choices(names, weights)[0]
    face = faces[fid]
    bold = faces.get(BOLD_PAIRS.get(fid, fid), face)
    page = Page(page_id, fam, A4, rng.randint(0, 35))
    model_rule_dropout = 0.0
    c = Ctx(page, rng, face, bold, faces, pool, split, model_rule_dropout)
    {"running_text": family_running, "numbered": family_numbered, "tables": family_tables,
     "front_matter": family_front}[fam](c)
    n_pages = rng.randint(1, 40)
    furniture(c, rng.randint(1, n_pages), n_pages)
    return page, c


def page_faces(faces: dict, split: str) -> list[str]:
    if split == "val":
        return [f for f in HELD_OUT_FACES if f in faces and not f.endswith("-bold")]
    return sorted(f for f in faces if f not in HELD_OUT_FACES and not f.endswith("-bold"))


def render_page(page: Page, faces: dict, seed: int, model: str | None = None,
                force_skew: float | None = None) -> tuple[Image.Image, list[float], dict]:
    """Draw, warp and degrade one page; returns the page image, its homography and the realised parameters."""
    rng = _page_rng(seed, page.id, "degrade")
    m = model or rng.choices(list(DEGRADATION_MIX), list(DEGRADATION_MIX.values()))[0]
    dropout = rng.uniform(0.1, 0.5) if m == "photocopy" and rng.random() < 0.6 else 0.0
    img = draw_page(page, dropout, rng, faces)
    H, size, gp = geometry(m, page.size, rng)
    if force_skew is not None:
        W, Hh = page.size
        s = gp["dpi"] / DPI
        a = math.radians(force_skew)
        cx, cy = W / 2, Hh / 2
        dst = [((x - cx) * math.cos(a) - (y - cy) * math.sin(a) + cx) * s for x, y in ((0, 0), (W, 0), (W, Hh), (0, Hh))]
        dsty = [((x - cx) * math.sin(a) + (y - cy) * math.cos(a) + cy) * s for x, y in ((0, 0), (W, 0), (W, Hh), (0, Hh))]
        H = homography([(0, 0), (W, 0), (W, Hh), (0, Hh)], list(zip(dst, dsty)))
        gp.update(skew_deg=force_skew, perspective_deg=0.0, keystone_side=None)
    fill = rng.randint(70, 140) if m == "phone_photo" else 255
    img = warp(img, H, size, fill)
    img, pp = photometric(img, m, rng, fill)
    return img, H, {"model": m, "rule_dropout": round(dropout, 3), **gp, **pp}


def office_pages(texts: Iterable[dict], output: Path, *, seed: int, pages: int, split: str = "train",
                 manifest_path: Path | None = None, families: Sequence[str] | None = None,
                 models: Sequence[str] | None = None, prefix: str = "op") -> dict:
    """Generate `pages` office-print pages from the text pool into `output`. Returns the summary dict."""
    _require_raqm()
    if split not in ("train", "val"):
        raise ValueError("split must be 'train' or 'val'")
    for f in families or ():
        if f not in FAMILY_MIX:
            raise ValueError(f"unknown family {f!r}; choose from {sorted(FAMILY_MIX)}")
    for m in models or ():
        if m not in DEGRADATION_MIX:
            raise ValueError(f"unknown degradation model {m!r}; choose from {sorted(DEGRADATION_MIX)}")
    faces = governed_faces(manifest_path)
    pool = TextPool(texts)
    out = Path(output)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    (out / "lines").mkdir(parents=True, exist_ok=True)
    stats = {"pages": 0, "lines": 0, "by_family": {}, "by_model": {}, "by_face": {}, "by_kind": {},
             "number_shapes": {}, "lines_with_number": {}, "masked_by_mark": 0,
             "out_of_frame": 0, "refused_missing_chars": 0}
    with open(out / "manifest.jsonl", "w", encoding="utf-8") as fm, open(out / "pages.jsonl", "w", encoding="utf-8") as fp:
        for k in range(pages):
            pid = f"{prefix}{seed}_{k:06d}"
            rng = _page_rng(seed, pid, "choice")
            fam = rng.choice(list(families)) if families else None
            mod = rng.choice(list(models)) if models else None
            page, c = build_page(pool, faces, pid, seed, split, fam)
            img, H, deg = render_page(page, faces, seed, mod)
            img.save(out / "pages" / f"{pid}.png")
            s = deg["dpi"] / DPI
            recs = []
            crng = _page_rng(seed, pid, "crops")
            for i, ln in enumerate(page.lines):
                lid = f"{pid}_{i:03d}"
                label = fold_label(ln.text)
                pb = padded(ln.box, ln.size, ln.cell, crng)
                q = quad(H, pb)
                masked = any(_overlap(ln.box, r.box) for r in page.regions)
                inside = all(0 <= x < img.width and 0 <= y < img.height for x, y in q)
                rec = {"schema": OFFICE_PAGES_SCHEMA, "id": lid, "page": pid, "kind": ln.kind, "text": label,
                       "drawn_text": ln.text, "label_order": "logical",
                       "number_spans": [{"start": a, "end": b, "shape": sh} for a, b, sh in ln.spans],
                       "quad": [[round(x, 2), round(y, 2)] for x, y in q], "box_page_300dpi": list(ln.box),
                       "cell": ln.cell, "sources": ln.sources, "font_id": ln.face, "size_px_300dpi": ln.size,
                       "weight": ln.weight, "family": page.family, "degradation": deg["model"], "split": split,
                       "seed": seed, "synthetic": "rendered", "masked_by_mark": masked, "in_frame": inside}
                recs.append(rec)
                stats["by_kind"][ln.kind] = stats["by_kind"].get(ln.kind, 0) + 1
                for _, _, sh in ln.spans:
                    stats["number_shapes"][sh] = stats["number_shapes"].get(sh, 0) + 1
                nk = sum(1 for m_ in NUM.finditer(label))
                key = "cells" if ln.cell else "text"
                d = stats["lines_with_number"].setdefault(key, [0, 0, 0])
                d[0] += nk > 0; d[1] += nk >= 2; d[2] += 1
                if masked:
                    stats["masked_by_mark"] += 1; continue
                if not inside:
                    stats["out_of_frame"] += 1; continue
                crop = rectified_crop(img, q, s, pb)
                crop.save(out / "lines" / f"{lid}.png")
                (out / "lines" / f"{lid}.gt.txt").write_text(label + "\n", encoding="utf-8")
                rec.update(image=f"lines/{lid}.png", label=f"lines/{lid}.gt.txt", width=crop.width, height=crop.height)
                fm.write(json.dumps(rec, ensure_ascii=False) + "\n")
                stats["lines"] += 1
                stats["by_face"][ln.face] = stats["by_face"].get(ln.face, 0) + 1
            face = faces[c.face.id]
            prec = {"schema": OFFICE_PAGES_SCHEMA, "id": pid, "image": f"pages/{pid}.png", "family": page.family,
                    "split": split, "width": img.width, "height": img.height, "degradation": deg,
                    "homography": [round(v, 10) for v in H],
                    "font": {"id": face.id, "file": face.file, "sha256": face.sha256, "license": face.license},
                    "regions": [{"kind": r.kind, "quad": [[round(x, 2), round(y, 2)] for x, y in quad(H, r.box)],
                                 "labelled": False} for r in page.regions],
                    "lines": recs, "refused_missing_chars": c.refused, "seed": seed, "synthetic": "rendered"}
            (out / "pages" / f"{pid}.json").write_text(json.dumps(prec, ensure_ascii=False), encoding="utf-8")
            fp.write(json.dumps({k_: v for k_, v in prec.items() if k_ != "lines"} | {"n_lines": len(recs)},
                                ensure_ascii=False) + "\n")
            stats["pages"] += 1
            stats["by_family"][page.family] = stats["by_family"].get(page.family, 0) + 1
            stats["by_model"][deg["model"]] = stats["by_model"].get(deg["model"], 0) + 1
            stats["refused_missing_chars"] += c.refused
    tot = sum(v for k_, v in stats["number_shapes"].items() if k_ in SHAPE_MIX)
    stats["number_shape_share"] = {k_: round(stats["number_shapes"].get(k_, 0) / tot, 4) if tot else 0 for k_ in SHAPE_MIX}
    stats["lines_with_number_share"] = {k_: round(a / n, 4) if n else 0 for k_, (a, _, n) in stats["lines_with_number"].items()}
    stats["lines_with_2plus_numbers_share"] = {k_: round(b / n, 4) if n else 0
                                               for k_, (_, b, n) in stats["lines_with_number"].items()}
    allb, alln = sum(v[1] for v in stats["lines_with_number"].values()), sum(v[2] for v in stats["lines_with_number"].values())
    stats["lines_with_2plus_numbers_share"]["all"] = round(allb / alln, 4) if alln else 0
    mpath = Path(manifest_path or default_font_manifest_path())
    try:
        from importlib.metadata import version as _v  # noqa: PLC0415
        version = _v("hocrsyngen")
    except Exception:  # noqa: BLE001
        version = "source"
    summary = {"schema": OFFICE_PAGES_SCHEMA, "seed": seed, "split": split, **stats,
               "targets": {"family_mix": FAMILY_MIX, "degradation_mix": DEGRADATION_MIX, "shape_mix": SHAPE_MIX},
               "font_manifest_sha256": _sha256(mpath), "hocrsyngen_version": version, "synthetic": "rendered"}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
