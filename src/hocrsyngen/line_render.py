"""Render given text lines to single-line images with logical-order labels and per-line provenance.

This is the `hocrsyngen render-lines` surface: the caller supplies the lines (an id and logical-order text each); the
renderer draws each line in one governed font, applies a named line-level degradation preset, and writes:

- ``lines/<id>.png``      greyscale line image
- ``lines/<id>.gt.txt``   the input text, NFC, logical order (never a reader's output)
- ``manifest.jsonl``      one record per line: font id/file/sha256/licence, size, preset and its realised parameters,
                          run seed and line seed, ``synthetic: "rendered"``
- ``summary.json``        counts per font and preset, font-manifest sha256, package version, refusals

Rules:
- Only faces listed in the packaged font manifest with ``line_render: true`` can be used. Every face's file must match
  its manifest sha256 and carry a licence id and licence file; anything else is refused.
- Bidi is resolved by Pillow's libraqm backend (the Unicode Bidirectional Algorithm with an RTL base direction), so
  Latin and digit runs stay left-to-right and paired brackets are mirrored. Pillow without libraqm is refused.
- A line with a character the chosen face cannot draw (it would render as .notdef) is refused, not rendered.
- Fonts are assigned by a seeded balanced permutation over groups (or lines when there is no ``group``); counts differ
  by at most one. Lines of a group share face, size and weight, so a sitting reads like one document.
- Every random choice derives from (seed, group or line id), so a line renders identically in any batch.
- Each record carries two ink-band measures: ``ink_band_px_otsu2pct`` / ``ink_band_frac_otsu2pct`` (the R9 face-stats
  definition) and ``ink_band_px`` / ``dark_density`` (p5-p95 letter body). ``--band-range`` targets one of them
  (``--band-def``, default otsu2pct), converted to a font size per face.
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import re
import unicodedata
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, features

from .assets import default_font_manifest_path
from .io import load_simple_font_manifest

LINE_RENDER_SCHEMA = "hocrsyngen_line_render.v1"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$")


@dataclass(frozen=True)
class LinePreset:
    """Line-level degradation. Ranges are sampled per line; zero-width ranges are fixed values."""

    blur: tuple[float, float]
    grain: tuple[float, float]           # std of additive seeded uniform noise, grey levels
    ink: tuple[int, int]                 # text grey level (0 = black)
    paper: tuple[int, int]               # background grey level
    jpeg: tuple[int, int]                # JPEG quality; 0 = no JPEG round trip
    downsample: tuple[float, float]      # scale factor before scaling back up; 1.0 = none
    spread: tuple[int, int]              # ink spread in px (MinFilter size 2*s+1); 0 = none
    rotate: tuple[float, float]          # degrees


LINE_PRESETS: dict[str, LinePreset] = {
    "none": LinePreset((0, 0), (0, 0), (0, 0), (255, 255), (0, 0), (1.0, 1.0), (0, 0), (0, 0)),
    # light (default): modern print on an office scanner
    "modern_print_scan_v1": LinePreset((0.0, 0.4), (0.0, 4.0), (0, 40), (225, 255), (85, 95), (1.0, 1.0), (0, 0), (-0.2, 0.2)),
    "modern_print_scan_v1_medium": LinePreset((0.2, 0.7), (2.0, 8.0), (10, 60), (200, 245), (70, 90), (0.7, 1.0), (0, 0), (-0.4, 0.4)),
    "modern_print_scan_v1_small_inky": LinePreset((0.3, 0.8), (2.0, 8.0), (0, 50), (190, 240), (65, 85), (0.5, 0.75), (0, 1), (-0.4, 0.4)),
}
DEFAULT_PRESET = "modern_print_scan_v1"
# Calibration line for --band-range: mixes letters with and without ascenders/descenders.
CALIBRATION_TEXT = "הוועדה דנה בהצעת החוק לתיקון פקודת המסים, ודחתה אותה"


@dataclass(frozen=True)
class GovernedFace:
    id: str
    file: str
    path: Path
    sha256: str
    license: str
    license_file: str
    style: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def governed_faces(manifest_path: Path | None = None) -> dict[str, GovernedFace]:
    """All faces the manifest allows for line rendering, verified against their sha256 and licence file."""
    manifest_path = Path(manifest_path or default_font_manifest_path())
    entries = load_simple_font_manifest(manifest_path).get("fonts", [])
    out: dict[str, GovernedFace] = {}
    for e in entries:
        if str(e.get("line_render", "")).lower() != "true":
            continue
        fid = e.get("id", "")
        for key in ("file", "sha256", "license", "license_file"):
            if not e.get(key):
                raise ValueError(f"font {fid!r}: manifest entry lacks {key!r}")
        path = manifest_path.parent / e["file"]
        lic = manifest_path.parent / e["license_file"]
        if not path.is_file() or not lic.is_file():
            raise ValueError(f"font {fid!r}: font or licence file missing next to the manifest")
        if _sha256(path) != e["sha256"]:
            raise ValueError(f"font {fid!r}: {e['file']} does not match its manifest sha256")
        out[fid] = GovernedFace(fid, e["file"], path, e["sha256"], e["license"], e["license_file"], e.get("style", ""))
    return out


def _require_raqm() -> None:
    if not features.check("raqm"):
        raise RuntimeError("render-lines needs Pillow with libraqm (bidi and Hebrew shaping); refusing to render.")


@lru_cache(maxsize=256)
def _font(path: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    if weight is not None and _wght_axis(path) is not None:
        axes = f.get_variation_axes()
        f.set_variation_by_axes([float(weight) if a.get("name") in (b"Weight", "Weight") else float(a["default"])
                                 for a in axes])
    return f


@lru_cache(maxsize=64)
def _wght_axis(path: str) -> tuple[int, int, int] | None:
    """(min, default, max) of the face's weight axis, or None for a static face."""
    try:
        axes = ImageFont.truetype(path, 16).get_variation_axes()
    except OSError:
        return None
    for a in axes:
        if a.get("name") in (b"Weight", "Weight"):
            return int(a["minimum"]), int(a["default"]), int(a["maximum"])
    return None


def face_weight(face: GovernedFace, wanted: int) -> tuple[int | None, bool]:
    """The weight actually used: `wanted` clipped to the axis for a variable face; None (the face's own) for static."""
    ax = _wght_axis(str(face.path))
    if ax is None:
        return None, False
    return max(ax[0], min(ax[2], wanted)), True


def measure_band(img: Image.Image, ink: int, paper: int) -> dict:
    """Ink band of a rendered line: dark = below the ink/paper midpoint; band = rows between the 5th and 95th
    percentile of dark-pixel rows (about the letter body; ascenders, descenders and specks are trimmed);
    dark_density = dark pixels inside the band / (band height x horizontal ink extent)."""
    thr = (ink + paper) / 2
    w, h = img.size
    dark = img.point(lambda v: 255 if v < thr else 0)
    rows = [0] * h
    data = dark.tobytes()
    for y in range(h):
        rows[y] = data[y * w:(y + 1) * w].count(255)
    total = sum(rows)
    if not total:
        return {"ink_band_px": 0, "dark_density": 0.0}
    def pct(q):
        acc = 0
        for y, n in enumerate(rows):
            acc += n
            if acc >= q * total:
                return y
        return h - 1
    y0, y1 = pct(0.05), pct(0.95)
    bbox = dark.getbbox() or (0, 0, w, h)
    inside = sum(rows[y0:y1 + 1])
    return {"ink_band_px": y1 - y0 + 1, "dark_density": round(inside / max(1, (y1 - y0 + 1) * (bbox[2] - bbox[0])), 4)}


def _otsu(img: Image.Image) -> int:
    hist = img.histogram()[:256]
    total = sum(hist); sum_all = sum(i * h for i, h in enumerate(hist))
    w = m = 0.0; best, t = -1.0, 0
    for i, h in enumerate(hist):
        w += h; m += i * h
        if w == 0 or w == total:
            continue
        b = (sum_all * w / total - m) ** 2 / (w * (total - w) / total)
        if b > best:
            best, t = b, i
    return t


def measure_band_otsu2pct(img: Image.Image) -> dict:
    """The R9 face-stats definition (tasks/r9-new-printed/face_stats/per_face_stats.py, as r8c measure.py): ink =
    pixels <= the Otsu threshold of the line image; band = rows from the first to the last row whose ink share is above
    2% (ascenders and descenders included); ink_band_frac = ink share inside the band rows x the columns from the first
    to the last ink column of those rows."""
    t = _otsu(img)
    w, h = img.size
    data = img.point(lambda v: 255 if v <= t else 0).tobytes()
    rows = [data[y * w:(y + 1) * w].count(255) for y in range(h)]
    hit = [y for y, n in enumerate(rows) if n > 0.02 * w]
    if not hit:
        return {"ink_band_px_otsu2pct": 0, "ink_band_frac_otsu2pct": 0.0}
    y0, y1 = hit[0], hit[-1]
    cols = [x for x in range(w) if any(data[y * w + x] for y in range(y0, y1 + 1))]
    x0, x1 = cols[0], cols[-1]
    inside = sum(data[y * w + x0:y * w + x1 + 1].count(255) for y in range(y0, y1 + 1))
    return {"ink_band_px_otsu2pct": y1 - y0 + 1,
            "ink_band_frac_otsu2pct": round(inside / ((y1 - y0 + 1) * (x1 - x0 + 1)), 4)}


BAND_DEFS = {"otsu2pct": "ink_band_px_otsu2pct", "p5p95": "ink_band_px"}
DEFAULT_BAND_DEF = "otsu2pct"


def line_measures(img: Image.Image, ink: int, paper: int) -> dict:
    return {**measure_band(img, ink, paper), **measure_band_otsu2pct(img)}


@lru_cache(maxsize=256)
def band_ratio(path: str, weight: int | None, band_def: str = DEFAULT_BAND_DEF) -> float:
    """Band px per px of font size for this face (and weight) under `band_def`, measured on CALIBRATION_TEXT at
    100 px with no preset."""
    f = _font(path, 100, weight)
    l, t, r, b = f.getbbox(CALIBRATION_TEXT, direction="rtl")
    img = Image.new("L", (r - l + 20, b - t + 20), 255)
    ImageDraw.Draw(img).text((10 - l, 10 - t), CALIBRATION_TEXT, font=f, fill=0, direction="rtl")
    return line_measures(img, 0, 255)[BAND_DEFS[band_def]] / 100.0


@lru_cache(maxsize=8192)
def _covers(path: str, ch: str) -> bool:
    """False if `ch` would be drawn as the face's .notdef glyph."""
    if ch.isspace() or unicodedata.category(ch) in ("Cf", "Mn"):
        return True
    f = _font(path, 48)
    def mask(c: str) -> bytes:
        m = f.getmask(c, mode="L")
        return bytes(m) + m.size[0].to_bytes(4, "big") + m.size[1].to_bytes(4, "big")
    return mask(ch) != mask("\U000F0000")


def missing_chars(face: GovernedFace, text: str) -> list[str]:
    return sorted({c for c in text if not _covers(str(face.path), c)})


def _line_rng(seed: int, line_id: str) -> random.Random:
    h = hashlib.sha256(f"{seed}:{line_id}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _u(rng: random.Random, r: tuple[float, float]) -> float:
    return r[0] if r[0] == r[1] else rng.uniform(*r)


def _i(rng: random.Random, r: tuple[int, int]) -> int:
    return r[0] if r[0] == r[1] else rng.randint(*r)


def render_line(text: str, face: GovernedFace, size_px: int, preset: str, rng: random.Random,
                weight: int | None = None) -> tuple[Image.Image, dict]:
    """Render one logical-order line. Returns the greyscale image and the realised preset parameters.
    `weight` applies to faces with a weight axis (clip it with face_weight first); static faces ignore it."""
    _require_raqm()
    p = LINE_PRESETS[preset]
    font = _font(str(face.path), size_px, weight)
    ink, paper = _i(rng, p.ink), _i(rng, p.paper)
    left, top, right, bottom = font.getbbox(text, direction="rtl")
    pad_x, pad_y = max(4, size_px // 3), max(3, size_px // 4)
    w, h = (right - left) + 2 * pad_x, (bottom - top) + 2 * pad_y
    img = Image.new("L", (max(1, w), max(1, h)), paper)
    ImageDraw.Draw(img).text((pad_x - left, pad_y - top), text, font=font, fill=ink, direction="rtl")
    params: dict = {"ink": ink, "paper": paper}
    rot = _u(rng, p.rotate)
    if rot:
        img = img.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=paper)
    params["rotate"] = round(rot, 4)
    spread = _i(rng, p.spread)
    if spread:
        img = img.filter(ImageFilter.MinFilter(2 * spread + 1))
    params["spread"] = spread
    ds = _u(rng, p.downsample)
    if ds < 1.0:
        small = (max(1, round(img.width * ds)), max(1, round(img.height * ds)))
        img = img.resize(small, Image.Resampling.LANCZOS).resize(img.size, Image.Resampling.BICUBIC)
    params["downsample"] = round(ds, 4)
    blur = _u(rng, p.blur)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    params["blur"] = round(blur, 4)
    grain = _u(rng, p.grain)
    if grain > 0:
        # Seeded uniform noise centred on 128, scaled to the requested std (uniform 0-255 has std ~73.9).
        k = grain / 73.9
        noise = Image.frombytes("L", img.size, rng.randbytes(img.width * img.height)).point(
            lambda v: max(0, min(255, round(128 + (v - 128) * k))))
        img = ImageChops.add(img, noise, scale=1.0, offset=-128)
    params["grain"] = round(grain, 4)
    q = _i(rng, p.jpeg)
    if q:
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=q); buf.seek(0)
        img = Image.open(buf).convert("L")
    params["jpeg"] = q
    return img, params


def _balanced_faces(ids: Sequence[str], faces: Sequence[str], seed: int) -> dict[str, str]:
    """Seeded balanced assignment of keys (line ids or group ids) to faces: counts differ by at most one."""
    order = sorted(set(ids))
    random.Random(f"{seed}:faces").shuffle(order)
    rot = list(faces)
    random.Random(f"{seed}:face-order").shuffle(rot)
    return {lid: rot[i % len(rot)] for i, lid in enumerate(order)}


def read_lines(path: Path) -> list[dict]:
    rows = []
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        r = json.loads(raw)
        if not isinstance(r.get("id"), str) or not isinstance(r.get("text"), str):
            raise ValueError(f"line {n}: each record needs string 'id' and 'text'")
        row = {"id": r["id"], "text": r["text"]}
        if r.get("group") is not None:
            if not isinstance(r["group"], str) or not r["group"]:
                raise ValueError(f"line {n}: 'group' must be a non-empty string")
            row["group"] = r["group"]
        rows.append(row)
    return rows


def render_lines(
    lines: Iterable[dict],
    output: Path,
    *,
    seed: int,
    fonts: Sequence[str] | None = None,
    preset: str = DEFAULT_PRESET,
    size_range: tuple[int, int] | None = None,
    band_range: tuple[int, int] | None = None,
    weight_range: tuple[int, int] = (400, 400),
    band_def: str = DEFAULT_BAND_DEF,
    manifest_path: Path | None = None,
) -> dict:
    """Render `lines` ({id, text[, group]} in logical order) into `output`. Returns the summary dict.

    Size: either `size_range` (font px, sampled) or `band_range` (target ink band px under `band_def`, sampled,
    converted per face with band_ratio so every face lands in the same band); default size_range (24, 72).
    band_def: "otsu2pct" (default; R9 face-stats: rows with > 2% Otsu ink, first to last) or "p5p95" (letter body).
    Weight: sampled from `weight_range` and clipped to each variable face's axis; static faces keep their own weight.
    Lines sharing a `group` share face, size/band and weight (sampled once per group); faces are balanced over
    groups, or over lines when no group is given. Degradation is drawn per line."""
    _require_raqm()
    if preset not in LINE_PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose one of {sorted(LINE_PRESETS)}")
    if size_range is not None and band_range is not None:
        raise ValueError("give size_range or band_range, not both")
    if band_def not in BAND_DEFS:
        raise ValueError(f"unknown band_def {band_def!r}; choose one of {sorted(BAND_DEFS)}")
    mode = "band" if band_range is not None else "size"
    lo, hi = band_range if band_range is not None else (size_range or (24, 72))
    if not (4 <= lo <= hi <= 400):
        raise ValueError(f"{mode} range must satisfy 4 <= lo <= hi <= 400, got {(lo, hi)}")
    wlo, whi = weight_range
    if not (1 <= wlo <= whi <= 1000):
        raise ValueError(f"weight_range must satisfy 1 <= lo <= hi <= 1000, got {weight_range}")
    governed = governed_faces(manifest_path)
    chosen = list(fonts) if fonts else sorted(governed)
    unknown = [f for f in chosen if f not in governed]
    if unknown:
        raise ValueError(f"fonts not governed for line rendering: {unknown}; allowed: {sorted(governed)}")
    if len(set(chosen)) != len(chosen) or not chosen:
        raise ValueError("fonts must be a non-empty list without repeats")
    rows = list(lines)
    seen: set[str] = set()
    for r in rows:
        if not ID_RE.match(r["id"]):
            raise ValueError(f"line id {r['id']!r} is not filename-safe ([A-Za-z0-9_.-], max 200)")
        if r["id"] in seen:
            raise ValueError(f"duplicate line id {r['id']!r}")
        seen.add(r["id"])
    out = Path(output); (out / "lines").mkdir(parents=True, exist_ok=True)
    key = {r["id"]: ("group:" + r["group"]) if r.get("group") else ("line:" + r["id"]) for r in rows}
    assign_k = _balanced_faces(list(key.values()), chosen, seed)
    assign = {lid: assign_k[k] for lid, k in key.items()}
    mpath = Path(manifest_path or default_font_manifest_path())
    counts: dict[str, int] = {f: 0 for f in chosen}
    refused: list[dict] = []
    with open(out / "manifest.jsonl", "w", encoding="utf-8") as fo:
        for r in rows:
            text = " ".join(unicodedata.normalize("NFC", r["text"]).split())
            if not text:
                refused.append({"id": r["id"], "reason": "empty"}); continue
            face = governed[assign[r["id"]]]
            miss = missing_chars(face, text)
            if miss:
                refused.append({"id": r["id"], "reason": "font_missing_chars", "font_id": face.id, "chars": miss}); continue
            grng = _line_rng(seed, key[r["id"]] + ":style")
            target = grng.randint(lo, hi)
            weight, variable = face_weight(face, grng.randint(wlo, whi))
            size = target if mode == "size" else max(6, round(target / band_ratio(str(face.path), weight, band_def)))
            rng = _line_rng(seed, r["id"])
            img, params = render_line(text, face, size, preset, rng, weight)
            band = line_measures(img, params["ink"], params["paper"])
            img.save(out / "lines" / f"{r['id']}.png")
            (out / "lines" / f"{r['id']}.gt.txt").write_text(text + "\n", encoding="utf-8")
            counts[face.id] += 1
            fo.write(json.dumps({
                "schema": LINE_RENDER_SCHEMA, "id": r["id"], "image": f"lines/{r['id']}.png",
                "label": f"lines/{r['id']}.gt.txt", "text": text, "label_order": "logical",
                "synthetic": "rendered",
                "group": r.get("group"),
                "font_id": face.id,
                "font": {"id": face.id, "file": face.file, "sha256": face.sha256, "license": face.license,
                         "license_file": face.license_file, "variable_weight": variable},
                "size_px": size, "size_mode": mode, "target_band_px": target if mode == "band" else None,
                "band_def": band_def if mode == "band" else None,
                "weight": weight, **band,
                "preset": preset, "preset_params": params,
                "seed": seed, "line_seed": f"sha256({seed}:{r['id']})", "style_seed": f"sha256({seed}:{key[r['id']]}:style)",
                "width": img.width, "height": img.height,
            }, ensure_ascii=False) + "\n")
    try:
        from importlib.metadata import version as _v  # noqa: PLC0415
        version = _v("hocrsyngen")
    except Exception:  # noqa: BLE001 - running from a source tree without an installed distribution
        version = "source"
    summary = {"schema": LINE_RENDER_SCHEMA, "lines_in": len(rows), "rendered": sum(counts.values()),
               "refused": refused, "by_font": counts, "preset": preset,
               "preset_definition": asdict(LINE_PRESETS[preset]), "size_mode": mode, f"{mode}_range": [lo, hi],
               "weight_range": [wlo, whi], "band_def": band_def if mode == "band" else None, "groups": len({r["group"] for r in rows if r.get("group")}), "seed": seed,
               "font_manifest_sha256": _sha256(mpath), "hocrsyngen_version": version, "synthetic": "rendered"}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
