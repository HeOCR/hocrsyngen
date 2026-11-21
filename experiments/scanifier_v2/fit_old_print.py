"""Measure scanner bands and duplex show-through on cleared old-print DEV rasters."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def _ranges(values):
    return np.round(np.quantile(values, [0.10, 0.90]), 6).tolist()


def _luma(path):
    with Image.open(path) as image:
        raster = np.array(ImageOps.exif_transpose(image).convert("L"))
    if min(raster.shape) < 64:
        raise ValueError("Scan must span at least 64 pixels per axis")
    return raster


def _slice_box(gray, box):
    if not isinstance(box, list) or len(box) != 4 or any(type(x) is not int for x in box):
        raise ValueError("Page crop must be four integer pixel-edge coordinates")
    left, top, right, bottom = box
    height, width = gray.shape
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("Page crop leaves the stored raster")
    if min(right - left, bottom - top) < 64:
        raise ValueError("Page crop must span at least 64 pixels per axis")
    return gray[top:bottom, left:right]


def _runs(active):
    transitions = np.flatnonzero(np.diff(np.r_[False, active, False]))
    return zip(transitions[::2], transitions[1::2])


def measure_bands(gray):
    """Observe near-black border candidates on the full scan, before page crop."""
    paper = float(np.quantile(gray, 0.80))
    if paper < 100:
        return {"edges": [], "bars": [], "status": "no_light_paper"}
    dark = gray < min(70, paper * 0.35)
    edges, bars = [], []
    for axis, oriented, values, names in (
        ("vertical", dark, gray, ("left", "right")),
        ("horizontal", dark.T, gray.T, ("top", "bottom")),
    ):
        major, minor = oriented.shape
        span = max(4, round(major * 0.1))
        center = oriented[span:-span]
        y = (np.arange(span, major - span) + 0.5) / major - 0.5
        max_edge = min(round(minor * 0.24), minor - 1)
        edge_limits = []
        for reverse, side in enumerate(names):
            view = center[:, ::-1] if reverse else center
            widths = np.argmax(~view[:, :max_edge + 1], axis=1)
            present = (widths >= 1) & (widths < max_edge) & ~view[:, max_edge]
            if np.mean(present) < 0.60:
                edge_limits.append(0)
                continue
            taper, width = np.polyfit(y[present], widths[present] / minor, 1)
            edge_limit = int(np.max(widths[present]))
            edge_limits.append(edge_limit)
            original = values[span:-span, ::-1] if reverse else values[span:-span]
            band = original[present, :max(1, int(edge_limit / 2))]
            edges.append({"side": side, "edge_fraction": float(np.clip(width, 0, 0.5)),
                          "edge_taper": float(taper),
                          "edge_darkness": float(1 - np.median(band[band < 70]) / paper)})
        # Only count bars with a contiguous dark segment spanning most of the
        # image. Printed rules and hard cropping can still need manual review.
        start, end = (edge_limits[0] + 1, minor - edge_limits[1] - 1)
        for left, right in _runs(oriented[:, start:end].mean(axis=0) >= 0.58):
            if right - left > minor * 0.12:
                continue
            left, right = start + left, start + right
            core = oriented[:, (left + right - 1) // 2]
            ranges = list(_runs(core))
            top, bottom = max(ranges, key=lambda run: run[1] - run[0])
            if bottom - top < 0.58 * major:
                continue
            bar = values[top:bottom, left:right]
            bars.append({
                "axis": axis, "bar_fraction": (right - left) / minor,
                "box": [int(x) for x in ((left, top, right, bottom) if axis == "vertical"
                                          else (top, left, bottom, right))],
                "bar_span": (bottom - top) / major,
                "bar_darkness": float(1 - np.median(bar) / paper),
            })
    return {"edges": edges, "bars": bars, "status": "candidates"}


def _ink(gray):
    # Close over ink and weak ghosts to approximate the slowly varying paper
    # envelope. Relative darkness factors out first-order discoloration.
    radius = min(25, max(5, round(min(gray.shape) * 0.01)))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * radius + 1,) * 2)
    background = cv2.GaussianBlur(cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel), (0, 0), radius / 3)
    return np.clip(1 - gray / np.maximum(background.astype(np.float32), 1), 0, 1).astype(np.float32)


def _association(x, y):
    x = x - np.mean(x)
    y = y - np.mean(y)
    xx, yy = np.dot(x, x), np.dot(y, y)
    if min(xx, yy) <= 1e-9:
        return 0.0, 0.0
    xy = np.dot(x, y)
    return float(xy / np.sqrt(xx * yy)), float(xy / xx)


def measure_show_through(front, reverse, seed):
    """Fit a mirrored reverse-ink proxy in manually registered leaf crops.

    The reverse is in normal reading orientation. Return no fitted observation
    when a candidate does not replicate in disjoint bands of the same leaf.
    """
    height, width = front.shape
    if min(height, width) < 64 or min(reverse.shape) < 64:
        raise ValueError("Duplex crops must span at least 64 pixels per axis")
    scale = min(1, 1200 / max(front.shape))
    proxy_width, proxy_height = max(64, round(width * scale)), max(64, round(height * scale))
    size = (proxy_width, proxy_height)
    recto = _ink(cv2.resize(front, size, interpolation=cv2.INTER_AREA))
    verso = _ink(cv2.resize(reverse[:, ::-1], size, interpolation=cv2.INTER_AREA))
    margin = max(5, round(max(size) * 0.03))
    ink_mask = cv2.dilate(np.uint8(recto >= 0.30), np.ones((7, 7), np.uint8))
    ys, xs = np.nonzero((ink_mask == 0) & (recto < 0.25))
    keep = (ys >= margin) & (xs >= margin) & (ys < size[1] - margin) & (xs < size[0] - margin)
    ys, xs = ys[keep], xs[keep]
    if len(ys) < 2000 or np.count_nonzero(verso >= 0.25) < 100:
        return None
    rng = np.random.default_rng(seed)
    keep = rng.choice(len(ys), min(18000, len(ys)), replace=False)
    ys, xs = ys[keep], xs[keep]
    learn = (6 * ys // size[1] % 2) == 0
    if min(np.count_nonzero(learn), np.count_nonzero(~learn)) < 500:
        return None
    residual = recto[ys, xs]
    x_steps = np.unique(np.rint(np.linspace(-0.02, 0.02, 13) * size[0]).astype(int))
    y_steps = np.unique(np.rint(np.linspace(-0.02, 0.02, 13) * size[1]).astype(int))
    best = None
    for blur in (0, 0.45, 0.8, 1.15, 1.7, 2.5):
        softened = cv2.GaussianBlur(verso, (0, 0), blur) if blur else verso
        for dy in y_steps:
            for dx in x_steps:
                ink = softened[ys[learn] - dy, xs[learn] - dx]
                correlation, alpha = _association(ink, residual[learn])
                if best is None or correlation > best[0]:
                    best = (correlation, alpha, dx, dy, blur, softened)
    corr, alpha, dx, dy, blur, softened = best
    check_x, check_y = xs[~learn] - dx, ys[~learn] - dy
    check = residual[~learn]
    check_corr, check_alpha = _association(softened[check_y, check_x], check)
    # Wrong horizontal placements are negative controls against regular lines
    # of front text, which can correlate even without legible reverse ink.
    wrong = max(_association(softened[check_y, (check_x + round(size[0] * delta)) % size[0]], check)[0]
                for delta in (-0.18, -0.11, 0.11, 0.18))
    if min(corr, check_corr) < 0.10 or check_corr < wrong + 0.05:
        return None
    if not 0.005 <= min(alpha, check_alpha) <= max(alpha, check_alpha) <= 0.40:
        return None
    if abs(alpha - check_alpha) > max(0.02, 0.5 * max(alpha, check_alpha)):
        return None
    return {"opacity": (alpha + check_alpha) / 2, "blur_px": blur / scale,
            "offset_x_fraction": float(dx / size[0]), "offset_y_fraction": float(dy / size[1]),
            "fit_correlation": corr, "check_correlation": check_corr, "wrong_location_correlation": wrong}


def _path(value):
    forbidden = {"eval_refs", "ps_v1", "ps-v1", "nq1", "preregistration", "heocr-restricted-eval"}
    path = Path(value).resolve(strict=True)
    parts = [part.lower() for part in path.parts]
    if forbidden.intersection(parts) or any(
        part == "runs" and i + 1 < len(parts) and "test" in parts[i + 1] for i, part in enumerate(parts)
    ):
        raise ValueError("Evaluation paths are forbidden")
    return path


def _manifest(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("purpose") != "cleared_public_domain_old_print_calibration":
        raise ValueError("Use an explicit cleared public-domain calibration manifest")
    captures = document.get("leaves")
    if not isinstance(captures, list) or len(captures) < 3:
        raise ValueError("Provide at least three distinct cleared leaves")
    images, identities, work = set(), set(), []
    for leaf in captures:
        if any(not isinstance(leaf.get(field), str) or not leaf[field]
               for field in ("source_id", "leaf_id", "rights_url", "clearance", "capture_type")):
            raise ValueError("Every leaf needs source, identity, rights, clearance and capture type")
        identity = leaf["source_id"], leaf["leaf_id"]
        if identity in identities:
            raise ValueError("Each physical leaf must be listed once")
        identities.add(identity)
        front = _path(leaf["recto"])
        back = _path(leaf["verso"]) if "verso" in leaf else None
        paths = [front, back] if back is not None else [front]
        if set(paths) & images or len(set(paths)) != len(paths):
            raise ValueError("Each image belongs to one physical leaf and side")
        images.update(paths)
        work.append((leaf, front, back))
    return work


def _fit(leaves, seed):
    measurements = []
    for index, (leaf, front_path, back_path) in enumerate(leaves):
        base = _luma(front_path)
        details = measure_bands(base)
        if back_path is not None:
            front = _slice_box(base, leaf["recto_box"])
            reverse = _slice_box(_luma(back_path), leaf["verso_box"])
            details["show_through"] = measure_show_through(front, reverse, seed + index)
        measurements.append({k: leaf[k] for k in ("source_id", "leaf_id", "capture_type", "rights_url", "clearance")} | details)

    ghost = [row["show_through"] for row in measurements if row.get("show_through")]
    edges = [edge for row in measurements for edge in row["edges"]]
    bars = [bar for row in measurements for bar in row["bars"]]
    ranges = {}
    if sum(bool(row["edges"]) for row in measurements) >= 3:
        ranges["edge"] = {key: _ranges([edge[key] for edge in edges])
                          for key in ("edge_fraction", "edge_taper", "edge_darkness")}
        ranges["edge"]["edge_sides"] = [edge["side"] for edge in edges]
    if sum(bool(row["bars"]) for row in measurements) >= 3:
        ranges["bars"] = {key: _ranges([bar[key] for bar in bars])
                          for key in ("bar_fraction", "bar_span", "bar_darkness")}
        ranges["bars"]["bar_axes"] = [bar["axis"] for bar in bars]
        ranges["bars"]["bar_count"] = [min(len(row["bars"]) for row in measurements),
                                       max(len(row["bars"]) for row in measurements)]
    if len(ghost) >= 3:
        ranges["show_through"] = {key: _ranges([row[key] for row in ghost])
                                  for key in ("opacity", "blur_px")}
        # The renderer uses one shared range, sampled independently on each axis.
        ranges["show_through"]["offset_fraction"] = _ranges(
            [row[key] for row in ghost for key in ("offset_x_fraction", "offset_y_fraction")])
    return {"version": 1, "seed": seed, "status": "dev_calibration_candidates",
            "measurements": measurements, "candidate_ranges": ranges}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("private_report", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("--seed must be nonnegative")
    cv2.setNumThreads(1)
    results = _fit(_manifest(args.manifest), args.seed)
    with args.private_report.open("x", encoding="utf-8") as file:
        file.write(json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
