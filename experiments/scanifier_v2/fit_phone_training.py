"""Fit phone geometry and local shadow from hash-bound non-test page pairs."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .geometry import corners, project

ENDPOINTS = ("phone_flat", "phone_oblique", "adobe_scan")
FORBIDDEN = {
    "eval_refs",
    "ps_v1",
    "ps-v1",
    "nq1",
    "preregistration",
    "heocr-restricted-eval",
}


def _asset(root, path, sha):
    file = (root / path).resolve(strict=True)
    parts = tuple(part.lower() for part in file.parts)
    if (
        not file.is_relative_to(root)
        or FORBIDDEN.intersection(parts)
        or any(a == "runs" and "test" in b for a, b in itertools.pairwise(parts))
    ):
        raise ValueError("Capture paths must stay in the approved non-test input root")
    with file.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != sha:
            raise ValueError("Non-test calibration input hash mismatch")
    return file


def read_pairs(manifest, *, train_only=False):
    path = Path(manifest).resolve(strict=True)
    data = json.loads(path.read_bytes())
    purpose = (
        "approved_train_phone_calibration"
        if train_only
        else "non_test_phone_calibration"
    )
    if data.get("purpose") != purpose:
        raise ValueError("A scope-matched phone calibration allowlist is required")
    groups, sources, targets, views = {}, {}, set(), set()
    source_for_page, page_for_source = {}, {}
    for row in data["pairs"]:
        page, split, mode = (row[key] for key in ("page_id", "split", "profile"))
        source_sha, capture_sha = row["source_sha256"], row["capture_sha256"]
        if (
            not isinstance(page, str)
            or not page
            or mode not in ENDPOINTS
            or split not in ("fit", "check")
            or groups.setdefault(page, split) != split
            or sources.setdefault(source_sha, split) != split
            or (not train_only and (page, mode) in views)
            or (
                train_only
                and (
                    split != "fit"
                    or mode == "adobe_scan"
                    or type(row.get("optics_eligible")) is not bool
                    or source_for_page.setdefault(page, source_sha) != source_sha
                    or page_for_source.setdefault(source_sha, page) != page
                )
            )
            or capture_sha in targets
        ):
            raise ValueError(
                "Each physical page and all its views need one disjoint split"
            )
        views.add((page, mode))
        targets.add(capture_sha)
        yield row | {
            "source_path": _asset(path.parent, row["source"], source_sha),
            "capture_path": _asset(path.parent, row["capture"], capture_sha),
        }


def load_rgb(path):
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def working_size(size, long_edge=1500):
    return tuple(round(p * long_edge / max(size)) for p in size)


def _features(image, sift):
    # cv2 keypoints are pixel-center coordinates. Shift them into edge coordinates.
    gray = np.asarray(
        image.resize(working_size(image.size), Image.Resampling.LANCZOS).convert("L")
    )
    keypoints, descriptors = sift.detectAndCompute(gray, None)
    return (
        np.float32([key.pt for key in keypoints]) + 0.5,
        descriptors,
        gray.shape[::-1],
    )


def _bow(points, height, width, curl):
    shifted = points.copy()
    shifted[:, 1] += height * curl * (4 * (points[:, 0] / width - 0.5) ** 2 - 0.5)
    return shifted


def register(source, capture):
    """Fit projective geometry and validate extra bow on spatially split matches."""
    sift = cv2.SIFT_create(nfeatures=3500)
    src, src_desc, src_size = _features(source, sift)
    dst, dst_desc, dst_size = _features(capture, sift)
    if src_desc is None or dst_desc is None or len(dst) < 2:
        raise ValueError("Too few stable landmarks for phone registration")
    matches = cv2.BFMatcher().knnMatch(src_desc, dst_desc, k=2)
    unique = {}
    for nearest, second in sorted(
        (m for m in matches if len(m) == 2), key=lambda m: m[0].distance
    ):
        if nearest.distance < 0.76 * second.distance:
            unique.setdefault(nearest.trainIdx, nearest.queryIdx)
    src = src[list(unique.values())]
    dst = dst[list(unique)]
    w, h = src_size
    cells = np.floor(src / np.array((w / 11, h / 11))).astype(int)
    fitter = (cells[:, 0] + cells[:, 1] * 3) % 4 != 0
    if fitter.sum() < 25:
        raise ValueError("Too few landmarks in the geometry fit split")
    plane, mask = cv2.findHomography(src[fitter], dst[fitter], cv2.RANSAC, 3.0)
    if plane is None or mask.sum() < 24:
        raise ValueError("Phone registration lacks supported perspective")
    loss = np.linalg.norm(project(plane, src) - dst, axis=1)
    use = loss < 5.0
    train, check = use & fitter, use & ~fitter
    if (
        train.sum() < 24
        or np.ptp(src[train, 0]) < w * 0.28
        or np.ptp(src[train, 1]) < h * 0.1
    ):
        raise ValueError("Phone registration landmarks do not span the page")
    # Refit the plane on the same landmarks used for each nonlinear trial.
    # This keeps least-squares refinement out of the estimated curl benefit.
    plane, _ = cv2.findHomography(src[train], dst[train], 0)
    if plane is None:
        raise ValueError("Phone registration plane refinement failed")
    loss = np.linalg.norm(project(plane, src) - dst, axis=1)
    best = (float(np.median(loss[train])), 0.0, plane, loss)
    if check.sum() >= 12 and np.ptp(src[check, 0]) >= w * 0.24:
        for step in range(-18, 19):
            if step == 0:
                continue
            curl = step / 1000
            shifted = _bow(src, h, w, curl)
            matrix, _ = cv2.findHomography(shifted[train], dst[train], 0)
            if matrix is None:
                continue
            residual = np.linalg.norm(project(matrix, shifted) - dst, axis=1)
            score = float(np.median(residual[train]))
            if score < best[0]:
                best = (score, curl, matrix, residual)
    _, curl, matrix, residual = best
    if not curl or np.median(loss[check]) - np.median(residual[check]) < max(
        0.12, 0.15 * np.median(loss[check])
    ):
        curl, matrix, residual = 0.0, plane, loss
    projected = project(matrix, corners(src_size))
    relative_area = cv2.contourArea(
        projected.astype(np.float32), oriented=True
    ) / np.prod(dst_size)
    if (
        not cv2.isContourConvex(projected.astype(np.float32))
        or not 0.16 <= relative_area <= 1.6
    ):
        raise ValueError("Unreliable phone page quadrilateral")
    check_loss = float(np.median(loss[check])) if check.any() else None
    check_residual = float(np.median(residual[check])) if check.any() else None
    return (
        matrix,
        src_size,
        dst_size,
        projected,
        {
            "curl": curl,
            "fit_features": int(train.sum()),
            "check_features": int(check.sum()),
            "planar_error_px": check_loss,
            "fitted_error_px": check_residual,
        },
    )


def _blank_tiles(source, capture, fit):
    """Sample matching blank paper in page and observed frame coordinates."""
    matrix, (w, h), size, _, diagnostics = fit
    # Work in source coordinates. Exclude ink, borders, and areas outside
    # the photographed frame before sampling paper.
    clean = np.asarray(source.resize((w, h)).convert("L"))
    resized = capture.resize(size)
    observed = np.asarray(resized.convert("L"))
    color = np.asarray(resized.convert("RGB"))
    xs, ys = np.meshgrid(np.linspace(0.08, 0.92, 14), np.linspace(0.08, 0.92, 19))
    uv = np.column_stack((xs.ravel(), ys.ravel()))
    points = _bow(uv * (w, h), h, w, diagnostics["curl"])
    coordinates = project(matrix, points)
    tiles = []
    for i, ((u, v), (x, y)) in enumerate(zip(uv, coordinates, strict=True)):
        a, b, x, y = round(u * w), round(v * h), round(x - 0.5), round(y - 0.5)
        if not (5 <= x < size[0] - 5 and 5 <= y < size[1] - 5):
            continue
        before = clean[b - 4 : b + 5, a - 4 : a + 5]
        after = observed[y - 4 : y + 5, x - 4 : x + 5]
        if np.min(before) > 244 and np.ptp(after) < 18:
            medians = np.median(color[y - 4 : y + 5, x - 4 : x + 5], axis=(0, 1))
            tiles.append(
                (
                    u,
                    v,
                    np.log(max(1, np.median(after))),
                    i,
                    (x + 0.5) / size[0] - 0.5,
                    (y + 0.5) / size[1] - 0.5,
                    *medians,
                )
            )
    return np.asarray(tiles, dtype=float).reshape(-1, 9)


def _shadow(tiles):
    """Estimate a coherent local dimming component on matched blank paper."""
    if len(tiles) < 45:
        return None
    u, v, levels, indices = tiles[:, :4].T
    train = (indices.astype(int) + indices.astype(int) // 14) % 2 == 0
    plane = np.column_stack((np.ones(len(u)), u, v))
    base, *_ = np.linalg.lstsq(plane[train], levels[train], rcond=None)
    baseline = np.mean(np.abs(levels[~train] - plane[~train] @ base))
    best = (float("inf"), None)
    for cx in np.linspace(0.05, 0.95, 7):
        for cy in np.linspace(0.05, 0.95, 7):
            for sx, sy in ((0.16, 0.18), (0.28, 0.36), (0.45, 0.21)):
                spot = np.exp(-0.5 * (((u - cx) / sx) ** 2 + ((v - cy) / sy) ** 2))
                design = np.column_stack((plane, spot))
                weights, *_ = np.linalg.lstsq(design[train], levels[train], rcond=None)
                depth = 1 - np.exp(min(0, weights[-1]))
                if not 0.055 <= depth <= 0.45:
                    continue
                objective = float(
                    np.mean(np.abs(levels[train] - design[train] @ weights))
                )
                if objective < best[0]:
                    best = (objective, (cx, cy, sx, sy, depth, design, weights))
    if best[1] is None:
        return None
    cx, cy, sx, sy, depth, design, weights = best[1]
    error = np.mean(np.abs(levels[~train] - design[~train] @ weights))
    if baseline - error < max(0.006, 0.2 * baseline):
        return None
    return [float(value) for value in (cx, cy, sx, sy, depth)]


def _frame_light(tiles):
    if len(tiles) < 45:
        return None
    _, _, levels, indices, x, y, *_ = tiles.T
    fit = (indices.astype(int) + indices.astype(int) // 14) % 2 == 0
    if min(fit.sum(), (~fit).sum()) < 12 or min(np.ptp(x[fit]), np.ptp(y[fit])) < 0.35:
        return None
    plane = np.column_stack((np.ones(len(x)), x, y))
    weights, _, rank, _ = np.linalg.lstsq(plane[fit], levels[fit], rcond=None)
    _, sx, sy = weights
    if rank != 3 or max(abs(sx), abs(sy)) > 2:
        return None
    residual = np.mean(np.abs(levels[~fit] - (plane @ weights)[~fit]))
    constant = np.mean(np.abs(levels[~fit] - np.median(levels[fit])))
    if residual >= constant:
        sx = sy = 0.0
    gain = (x * sx + y * sy)[:, None]
    center = np.median(np.log(np.maximum(1, tiles[:, 6:]))[fit] - gain[fit], axis=0)
    r, g, b = np.clip(np.exp(center), 0, 255)
    return {
        "paper_r": float(r),
        "paper_g": float(g),
        "paper_b": float(b),
        "gradient_x": float(sx),
        "gradient_y": float(sy),
    }


def observe(source, capture, *, preserve_frame=False):
    fit = register(source, capture)
    _, _, size, quad, diagnostics = fit
    if not preserve_frame:
        low, high = quad.min(axis=0), quad.max(axis=0)
        # Legacy whole-page simulation retains line ink by reframing.
        scale = min(np.asarray(size) * 0.90 / (high - low))
        quad = (quad - (low + high) / 2) * scale + np.asarray(size) / 2
    quad = quad / size
    lengths = np.linalg.norm(np.roll(quad, -1, axis=0) - quad, axis=1)
    angle_score = abs(np.log(lengths[0] / lengths[2])) + abs(
        np.log(lengths[1] / lengths[3])
    )
    tiles = _blank_tiles(source, capture, fit)
    row = diagnostics | {
        "quad": quad.tolist(),
        "angle_score": float(angle_score),
        "frame_ratio": capture.width / capture.height,
        "native_long_edge": max(capture.size),
        "shadow": _shadow(tiles),
    }
    if preserve_frame:
        row["frame_light"] = _frame_light(tiles)
    return row


def fit_bank(manifest, *, preserve_frame=False):
    cv2.setNumThreads(1)
    cv2.setRNGSeed(47261)
    bank = {name: [] for name in ENDPOINTS}
    for row in read_pairs(manifest):
        if row["split"] != "fit":
            continue
        measured = observe(
            load_rgb(row["source_path"]),
            load_rgb(row["capture_path"]),
            preserve_frame=preserve_frame,
        )
        bank[row["profile"]].append(
            measured
            | {
                "page_id": row["page_id"],
                "capture_sha256": row["capture_sha256"],
                "source_sha256": row["source_sha256"],
            }
        )
    supported = [rows for rows in bank.values() if rows or not preserve_frame]
    if not supported or any(
        min(
            len({row["page_id"] for row in rows}),
            len({row["source_sha256"] for row in rows}),
        )
        < 3
        for rows in supported
    ):
        raise ValueError("Each endpoint needs at least three non-test fit pages")
    result = {"schema": "scanifier_phone_bank.v1", "profiles": bank}
    if preserve_frame:
        result["framing"] = "observed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preserve-frame", action="store_true")
    args = parser.parse_args()
    result = fit_bank(args.manifest, preserve_frame=args.preserve_frame)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
