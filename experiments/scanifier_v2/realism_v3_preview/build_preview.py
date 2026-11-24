"""Fit the synthetic comparison to fresh public-domain capture witnesses."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from experiments.scanifier_v2.realism_v3 import render, smooth_vector

from experiments.scanifier_v2.realism_v2_preview import build_preview as v2

HERE = Path(__file__).resolve().parent
WIDTH = 640

# Crop coordinates are fractions measured on the rendered source page. Use
# mostly anonymous body copy and margins. Keep specimen boundaries visible.
REFERENCES = (
    ("land", 10, (0, .15, .94, .73), "copy"),
    ("land", 20, (0, .09, .94, .73), "copy"),
    ("land", 42, (0, .23, .94, .79), "copy"),
    ("land", 74, (0, .11, .95, .76), "copy"),
    ("fire", 12, (0, .12, .94, .73), "copy"),
    ("fire", 17, (0, .35, .93, .89), "copy"),
    ("fire", 27, (0, .11, .94, .73), "copy"),
    ("fire", 36, (0, .40, .93, .91), "copy"),
    ("fay", 8, (0, .14, .95, .72), "copy"),
    ("fay", 11, (0, .21, .95, .76), "copy"),
    ("fay", 17, (0, .17, .95, .67), "copy"),
    ("fay", 23, (0, .30, .95, .86), "copy"),
    ("wolf", 12, (0, .16, .95, .71), "copy"),
    ("wolf", 23, (0, .36, .94, .91), "copy"),
    ("wolf", 28, (0, .30, .94, .86), "copy"),
    ("wolf", 38, (0, .22, .94, .77), "copy"),
    ("plate", None, (.00, .75, 1, 1), "flatbed"),
    ("plate", None, (.03, .03, .95, .39), "flatbed"),
    ("book", None, (.36, .00, .68, .27), "spine"),
    ("book2", None, (.092, .032, .81, .17), "spine"),
)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def raster(path, page):
    if page is None:
        with Image.open(path) as image:
            return image.convert("RGB")
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(path) as pdf, closing(pdf[page - 1]) as leaf:
        with closing(leaf.render(scale=110 / 72)) as bitmap:
            return bitmap.to_pil().convert("RGB")


def resized_crop(image, box):
    w, h = image.size
    x0, y0, x1, y1 = box
    crop = image.crop(tuple(round(v) for v in (w*x0, h*y0, w*x1, h*y1)))
    return crop.resize((WIDTH, round(crop.height * WIDTH / crop.width)), Image.Resampling.LANCZOS)


def line_angle(gray):
    """Projected screen-space baseline slope, available for text-like witnesses."""
    if min(gray.shape) < 60:
        return None
    mask = np.uint8(gray < np.percentile(gray, 20) * .88) * 255
    joined = cv2.dilate(mask, np.ones((1, 15), np.uint8))
    segs = cv2.HoughLinesP(joined, 1, np.pi / 720, threshold=25,
                          minLineLength=max(35, gray.shape[1] // 5), maxLineGap=12)
    if segs is None:
        return None
    angles = [float(np.degrees(np.arctan2(y1-y0, x1-x0)))
              for [[x0, y0, x1, y1]] in segs if x1 > x0 and abs(y1-y0)/(x1-x0) < .085]
    return float(np.median(angles)) if len(angles) >= 3 else None


def measure(image):
    """Measure comparable 640-px crops. Values are raster proxies."""
    rgb = np.asarray(image)
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    h, w = g.shape
    inner = g[:, w//10:9*w//10]
    paper_level = float(np.percentile(inner, 88))
    ink_floor = float(np.percentile(inner, 3))
    dark = g < paper_level - max(32, (paper_level-ink_floor) * .48)
    ink = g[dark]
    ink_level = float(np.percentile(ink, 15)) if ink.size else paper_level
    near_ink = ((cv2.dilate(dark.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
                & ~dark)
    transition = float(np.mean(g[near_ink] < paper_level - 13)) if near_ink.any() else 0
    gradient = np.maximum(np.abs(np.diff(inner, axis=1, prepend=inner[:, :1])),
                          np.abs(np.diff(inner, axis=0, prepend=inner[:1, :])))
    edges = gradient[gradient > 20]
    sharp = max(15., float(np.percentile(edges, 86))) if edges.size else 15.
    # Edge-spread sigma proxy, not a count of copier generations.
    sigma = (paper_level - ink_level) / (sharp * np.sqrt(2*np.pi))
    left = g[:, :w//14]
    right = g[:, -w//14:]
    side_paper = [float(np.percentile(v, 65)) for v in (left, right)]
    side = int(side_paper[1] < side_paper[0])
    edge = [left, right[:, ::-1]][side]
    means = np.percentile(edge, 65, axis=0)
    edge_drop = max(0., paper_level - float(np.percentile(means, 20)))
    edge_width = np.count_nonzero(means < paper_level - max(7., edge_drop*.42))
    row_paper = np.percentile(inner, 82, axis=1)
    band = row_paper - smooth_vector(row_paper, 11)
    band_sd = float((np.percentile(band, 90) - np.percentile(band, 10)) / 2.56)
    blur = cv2.GaussianBlur(g, (0, 0), 4)
    point_mask = np.uint8((g < blur - 23) & (blur > min(210, paper_level-18)))
    _, components, stat, _ = cv2.connectedComponentsWithStats(point_mask)
    # Exclude glyph fragments and the rims of large dark objects.
    large = np.uint8((stat[:, cv2.CC_STAT_AREA] > 11)[components] & (components > 0))
    near_large = cv2.dilate(large, np.ones((5, 5), np.uint8))
    specks = []
    for x, y, xx, yy, a in stat[1:]:
        if 1 <= a <= 11 and xx <= 5 and yy <= 5 and not near_large[y:y+yy, x:x+xx].any():
            specks.append(int(a))
    _, _, marks, centers = cv2.connectedComponentsWithStats(np.uint8(dark))
    punches = []
    for (x, y, xx, yy, a), (cx, cy) in zip(marks[1:], centers[1:]):
        if (5 <= xx <= 28 and 5 <= yy <= 28 and .54 <= xx/yy <= 1.85
                and a >= 20 and a/(xx*yy) > .35 and cx < .08*w
                and 0 < x and x+xx < w and 0 < y and y+yy < h):
            punches.append([float(cx/w), float(cy/h), float(xx/2), float(yy/2)])
    center = line_angle(g[:, w//5:4*w//5])
    gutter = line_angle(g[:, :w//3] if side == 0 else g[:, -w//3:])
    white = rgb[(g >= np.percentile(inner, 82))]
    return {
        "paper_gray": paper_level, "paper_rgb": np.median(white, axis=0).tolist(),
        "ink_floor": ink_level, "ink_crush_fraction": float(np.mean(ink < 26)) if ink.size else 0,
        "edge_midtone_fraction": transition, "blur_proxy_px": float(sigma),
        "inner_paper_band_sd": band_sd, "dark_edge_side": "right" if side else "left",
        "edge_drop": edge_drop, "edge_width_px": int(edge_width),
        "specks_per_mpx": round(len(specks) * 1e6 / g.size),
        "speck_median_area": float(np.median(specks)) if specks else None,
        "near_margin_punch_candidates": punches,
        "skew_deg": center, "gutter_minus_center_deg": None if center is None or gutter is None else gutter-center,
    }


def fit(stats, role):
    clip = np.clip
    return {
        "paper_rgb": stats["paper_rgb"],
        "ink": float(clip(stats["ink_floor"], 4, 116)),
        "knee": float(clip(.14 + .27*stats["ink_crush_fraction"] + .12*(1-stats["edge_midtone_fraction"]), .16, .52)),
        "blur": float(clip(stats["blur_proxy_px"], .27, 1.35)),
        "band_sd": float(clip(stats["inner_paper_band_sd"], 0, 4.2)),
        "edge_side": stats["dark_edge_side"],
        "edge_drop": float(clip(stats["edge_drop"], 0, 145)),
        "edge_width": int(clip(stats["edge_width_px"], 1, 40)),
        "specks_per_mpx": int(clip(stats["specks_per_mpx"], 0, 1350)),
        "speck_radius": float(clip(np.sqrt((stats["speck_median_area"] or 1)/np.pi), .42, 1.15)),
        "margin_punches": stats["near_margin_punch_candidates"][:4] if role == "copy" else [],
        "skew": float(clip(stats["skew_deg"] or 0, -2.2, 2.2)),
        "gutter_bend_deg": float(clip(stats["gutter_minus_center_deg"] or 0, -3, 3)) if role == "spine" else 0,
    }


def tune_render(clean, stats, settings, seed, i, role):
    """Correct coupled proxy errors after a trial render of this sheet."""
    def score(actual):
        return sum(abs(actual[key] - stats[key]) / scale for key, scale in (
            ("ink_floor", 32), ("blur_proxy_px", .5),
            ("edge_midtone_fraction", .35), ("inner_paper_band_sd", 3),
            ("specks_per_mpx", 1200),
        ))

    params = settings
    best_image = render(clean, params, seed, i, role)
    best_stats = measure(best_image)
    for _ in range(2):
        correction = {
            "ink": float(np.clip(params["ink"] + .85*(stats["ink_floor"]-best_stats["ink_floor"]), 4, 116)),
            "blur": float(np.clip(params["blur"] + .62*(stats["blur_proxy_px"]-best_stats["blur_proxy_px"]), .20, 1.35)),
            "knee": float(np.clip(params["knee"] + .24*(best_stats["edge_midtone_fraction"]-stats["edge_midtone_fraction"]), .16, .60)),
            "band_sd": float(np.clip(params["band_sd"] + .65*(stats["inner_paper_band_sd"]-best_stats["inner_paper_band_sd"]), 0, 4.2)),
            "specks_per_mpx": int(np.clip(params["specks_per_mpx"] + .74*(stats["specks_per_mpx"]-best_stats["specks_per_mpx"]), 0, 1350)),
        }
        trial_params = {**params, **correction}
        trial = render(clean, trial_params, seed, i, role)
        trial_stats = measure(trial)
        if score(trial_stats) < score(best_stats):
            params, best_image, best_stats = trial_params, trial, trial_stats
    return params, best_image


def write_image(image, path):
    image.save(path, "JPEG", quality=90, subsampling=0)
    return {"path": f"images/{path.name}", "sha256": digest(path), "size": list(image.size)}


def build(source_dir, output):
    sources = json.loads((HERE/"sources.json").read_bytes())
    by_id = {row["id"]: row for row in sources}
    for source in sources:
        if digest(source_dir/source["file"]) != source["sha256"]:
            raise ValueError("Reference hash differs: " + source["id"])
    copy_path = HERE.parent/"realism_v2_preview/copy.json"
    copy = json.loads(copy_path.read_bytes())
    output.mkdir(parents=True)
    rows = []
    for i, (key, page, box, role) in enumerate(REFERENCES):
        source = by_id[key]
        ref = resized_crop(raster(source_dir/source["file"], page), box)
        stats = measure(ref)
        settings = fit(stats, role)
        style = i % 5
        heading = copy["headings"][i]
        body = copy["blocks"][(i//5 + style)%4]
        layout = "Bound book" if role == "spine" else "Platen and photocopy"
        clean, lines = v2.recto(heading, body, family=layout, style=style, treated=True)
        # Keep all authored lines exactly; show a common whole-column region.
        clean = resized_crop(clean, (0, .115, 1, .908))
        seed = 26011243 + i*31
        settings, synthetic = tune_render(clean, stats, settings, seed, i, role)
        pair = {"id": f"{i+1:02}", "role": role, "source_id": key, "original_page": page,
                "original_crop_xyxy_fraction": box, "reference_stats": stats, "fitted_settings": settings,
                "seed": seed, "labels_sha256": [line["label_sha256"] for line in lines]}
        for key, image in (("control", clean), ("preview", synthetic), ("reference", ref)):
            pair[key] = write_image(image, output/f"{i+1:02}-{key}.jpg")
        pair["preview_stats"] = measure(Image.open(output/f"{i+1:02}-preview.jpg").convert("RGB"))
        rows.append(pair)
    manifest = {"schema":"heocr.scanifier_realism_v3_preview.v1", "licence":"CC0-1.0 (authored work)",
                "reference_licence":"public domain per sources.json", "calibration_width_px":WIDTH,
                "generator_sha256":digest(Path(__file__)), "source_ledger_sha256":digest(HERE/"sources.json"),
                "copy_sha256":digest(copy_path), "pairs":rows}
    (output.parent/"generation_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=HERE/"images")
    args = ap.parse_args()
    build(args.sources, args.output)
