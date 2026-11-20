"""Fit measurable scanifier v2 ranges from registered HEOCR-CAL-V1 photos."""

import argparse
import csv
import io
import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .geometry import corners, project
from .pipeline import BOUNDS, INTEGER_RANGES, linear_to_srgb, read_config, srgb_to_linear, validate_config


PACK = Path(__file__).with_name("calibration_pack")
REGISTRATION_CONDITIONS = {"A", "B", "B2", "C", "D", "E", "H", "I", "Jd", "Jw"}


def registered_shots():
    with (PACK / "shot_list.csv").open(encoding="utf-8", newline="") as handle:
        rows = [(r["file_name"], r["page"], r["condition"]) for r in csv.DictReader(handle)]
    phones = {name.removesuffix(".jpg").rsplit("-", 1)[1] for name, _, _ in rows}
    rows.extend((name.replace("-A-", "-F-"), page, "F")
                for name, page, condition in list(rows) if condition == "A")
    rows.extend((f"{page}-{condition}-{phone}.jpg", page, condition)
                for page in ("P11", "P12") for condition in ("A", "B", "D", "F", "G")
                for phone in sorted(phones))
    return rows


def _registration(rgb, target):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dictionary)
    params = detector.getDetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector.setDetectorParameters(params)
    matches, ids, _ = detector.detectMarkers(gray)
    expected = {m["id"]: m["corners_tl_tr_br_bl"] for m in target["markers"]}
    if ids is None:
        raise ValueError("No calibration fiducials")
    found = ids.flatten().tolist()
    if len(found) < 3 or len(set(found)) != len(found) or not set(found) <= expected.keys():
        raise ValueError("Fiducials do not identify the expected calibration page")
    clean = np.array([expected[marker] for marker in found], dtype=float).reshape(-1, 2)
    photo = np.asarray(matches, dtype=float).reshape(-1, 2)
    tolerance = max(2, max(gray.shape) * 0.003)
    matrix, mask = cv2.findHomography(clean, photo, cv2.RANSAC, tolerance)
    if matrix is None or mask is None:
        raise ValueError("Could not register calibration fiducials")
    keep = mask.ravel().astype(bool)
    if sum(keep) < 10 or len({i // 4 for i in np.flatnonzero(keep)}) < 3:
        raise ValueError("Too few consistent calibration fiducials")
    return matrix, clean[keep], photo[keep], gray


def _pose(clean, photo, target_size, frame, horizontal_fov):
    width, height = frame
    long_edge = max(target_size)
    focal = width / (2 * math.tan(math.radians(horizontal_fov / 2)))
    intrinsic = np.array([[focal, 0, width / 2], [0, focal, height / 2], [0, 0, 1]])
    points = (clean - np.array(target_size) / 2) / long_edge
    object_points = np.column_stack((points, np.zeros(len(points))))
    ok, rotation, translation = cv2.solvePnP(object_points, photo, intrinsic, None)
    if not ok or translation[2, 0] <= 0:
        return {}
    reprojection, _ = cv2.projectPoints(object_points, rotation, translation, intrinsic, None)
    if np.median(np.linalg.norm(reprojection.reshape(-1, 2) - photo, axis=1)) > max(frame) * 0.008:
        return {}
    r, _ = cv2.Rodrigues(rotation)
    yaw = math.degrees(math.asin(float(np.clip(-r[2, 0], -1, 1))))
    pitch = math.degrees(math.atan2(r[2, 1], r[2, 2]))
    roll = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return {"pitch_deg": pitch, "yaw_deg": yaw, "roll_deg": (roll + 45) % 90 - 45,
            "distance": float(translation[2, 0])}


def _edge_widths(gray, polygon):
    widths = []
    for index in range(4):
        start, end = polygon[index], polygon[(index + 1) % 4]
        delta = end - start
        span = np.linalg.norm(delta)
        if span < 12:
            continue
        normal = np.array([-delta[1], delta[0]]) / span
        across = np.linspace(-min(12, span / 3), min(12, span / 3), 81)
        along = start + np.linspace(0.24, 0.76, 17)[:, None] * delta
        coords = (along[:, None, :] + across[:, None] * normal).astype(np.float32)
        if (coords.min() < 1 or coords[..., 0].max() >= gray.shape[1] - 1
                or coords[..., 1].max() >= gray.shape[0] - 1):
            continue
        profile = np.mean(cv2.remap(gray, coords, None, cv2.INTER_LINEAR), axis=0)
        left, right = np.median(profile[:8]), np.median(profile[-8:])
        if abs(right - left) < 25:
            continue
        normalized = np.maximum.accumulate((profile - left) / (right - left))
        if normalized[0] < 0.1 and normalized[-1] > 0.9:
            low, high = np.interp((0.1, 0.9), normalized, across)
            # Normal-CDF 10–90% width expressed as an equivalent Gaussian sigma.
            widths.append((high - low) / 2.5631)
    return widths


def _patch(rgb, matrix, box):
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) * 0.22, (y1 - y0) * 0.22
    inner_box = [(x0 + dx, y0 + dy), (x1 - dx, y0 + dy), (x1 - dx, y1 - dy), (x0 + dx, y1 - dy)]
    polygon = project(matrix, inner_box)
    x, y, w, h = cv2.boundingRect(polygon.astype(np.float32))
    if min(w, h) < 7 or x < 0 or y < 0 or x + w > rgb.shape[1] or y + h > rgb.shape[0]:
        return None
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, np.rint(polygon - (x, y)).astype(np.int32), 1)
    mask = cv2.erode(mask, np.ones((3, 3), np.uint8)).astype(bool)
    data = rgb[y:y + h, x:x + w]
    if np.count_nonzero(mask) < 30:
        return None
    colour = np.median(data[mask], axis=0) / 255
    linear = srgb_to_linear(np.mean(data.astype(np.float32) / 255, axis=2))
    residual = (linear - cv2.blur(linear, (3, 3)))[mask]
    noise = 1.4826 * np.median(np.abs(residual - np.median(residual))) / math.sqrt(8 / 9)
    return colour, float(np.median(linear[mask])), float(noise ** 2)


@lru_cache(maxsize=1)
def _known_quantization():
    tables = defaultdict(list)
    for quality in range(1, 101):
        encoded = io.BytesIO()
        Image.new("RGB", (8, 8)).save(encoded, format="JPEG", quality=quality)
        encoded.seek(0)
        with Image.open(encoded) as jpeg:
            tables[_table_key(jpeg.quantization)].append(quality)
    return {table: values[0] for table, values in tables.items() if len(values) == 1}


def _table_key(tables):
    return tuple((index, tuple(table)) for index, table in sorted(tables.items()))


def _jpeg_quality(tables):
    key = _table_key(tables)
    known = _known_quantization()
    if key in known:
        return known[key]
    if not key:
        return None
    luma = np.log(key[0][1])
    distances = [(float(np.mean(np.abs(luma - np.log(candidate[0][1])))), quality)
                 for candidate, quality in known.items()]
    error, quality = min(distances)
    return quality if error <= 0.22 else None


def _page_brightness(rgb, matrix, target_size):
    # White-paper envelope from rectified tiles, with clipping excluded.
    scale = 480 / max(target_size)
    w, h = (round(s * scale) for s in target_size)
    rectify = np.diag([scale, scale, 1]) @ np.linalg.inv(matrix)
    image = cv2.warpPerspective(rgb, rectify, (w, h))
    gray = srgb_to_linear(image.mean(axis=2) / 255)
    rows, values = [], []
    for y in np.linspace(-0.36, 0.36, 7):
        for x in np.linspace(-0.36, 0.36, 7):
            cx, cy = round((x + 0.5) * w), round((y + 0.5) * h)
            dx, dy = max(1, w // 30), max(1, h // 30)
            value = float(np.quantile(gray[cy - dy:cy + dy, cx - dx:cx + dx], 0.9))
            if 0.06 < value < 0.98:
                rows.append([1, x, y, -2 * (x * x + y * y)])
                values.append(value)
    if len(rows) < 24:
        return {}
    intercept, gx, gy, v = np.linalg.lstsq(rows, values, rcond=None)[0]
    if intercept <= 0:
        return {}
    result = {"gradient": math.hypot(gx, gy) / intercept}
    if v >= 0:
        result["vignette"] = float(v / intercept)
    return result


def measure(path, target, condition, horizontal_fov):
    with Image.open(path) as image:
        if image.format != "JPEG":
            raise ValueError("Registered phone frames must be JPEG")
        exif = image.getexif()
        tag = exif.get(274, 1)
        orientation = tag if type(tag) is int and 1 <= tag <= 8 else 1
        tables = getattr(image, "quantization", {})
        rgb = np.asarray(ImageOps.exif_transpose(image).convert("RGB"))
    matrix, clean, photo, gray = _registration(rgb, target)
    frame = (rgb.shape[1], rgb.shape[0])
    size = target["size_px"]
    page = project(matrix, corners(size))
    hull = page.astype(np.float32)
    if (not np.isfinite(page).all() or not cv2.isContourConvex(hull)
            or cv2.contourArea(hull) < 0.02 * frame[0] * frame[1]):
        raise ValueError("Registered page outline is invalid")
    values = {}
    if condition in REGISTRATION_CONDITIONS:
        values.update({f"geometry.{key}": value
                       for key, value in _pose(clean, photo, size, frame, horizontal_fov).items()})
        if np.all(page >= 0) and np.all(page < frame):
            values["geometry.long_edge_px"] = max(frame)
            values["geometry.frame_aspect"] = min(frame) / max(frame)
            span = np.ptp(page, axis=0)
            values["geometry.margin"] = float(np.min(frame - span) / (2 * min(frame)))
        # Resize and recompression copies are reported separately from camera priors.
        quality = _jpeg_quality(tables)
        if quality is not None:
            values["jpeg.quality"] = quality

    edge_gray = gray.astype(np.float32)
    edges = [_edge_widths(edge_gray, project(matrix, edge["polygon"])) for edge in target["edges"]]
    edges = [widths for widths in edges if len(widths) == 4]
    if condition in ("A", "C") and edges:
        minima = [min(widths) for widths in edges]
        values["optics.defocus_sigma_px"] = float(np.median(minima))
        if len(minima) > 2:
            values["optics.defocus_gradient_px"] = float(np.ptp(minima))
    if condition in ("B", "B2") and edges:
        # Anisotropy gives a lower-bound estimate for straight-line motion.
        estimates = [math.sqrt(12 * (max(edge) ** 2 - min(edge) ** 2)) for edge in edges]
        values["optics.motion_length_px"] = float(np.median(estimates))

    wedge = [(step, _patch(rgb, matrix, step["box"])) for step in target["wedge"]]
    white = [sample[0] for step, sample in wedge if step["grey"] == 255 and sample is not None]
    if white and condition in REGISTRATION_CONDITIONS:
        colour = srgb_to_linear(np.median(white, axis=0))
        level = float(np.mean(colour))
        if 0.05 < level < 0.98:
            key = "low_light_exposure" if condition == "D" else "exposure"
            values[f"lighting.{key}"] = level
        if np.all((colour > 0.05) & (colour < 0.98)):
            for channel, gain in zip("rgb", colour / level):
                values[f"lighting.white_balance_{channel}"] = float(gain)
    if condition in ("A", "C", "D", "Jd", "Jw"):
        values.update({f"lighting.{key}": value
                       for key, value in _page_brightness(rgb, matrix, size).items()})
    if condition in ("A", "D"):
        flat = [(mean, variance) for _, sample in wedge if sample is not None
                for _, mean, variance in [sample] if 0.02 < mean < 0.96 and variance > 0]
        if len(flat) >= 4 and np.ptp([mean for mean, _ in flat]) > 0.25:
            slope, floor = np.polyfit(*np.array(flat).T, deg=1)
            prefix = "low_light_" if condition == "D" else ""
            if slope > 0:
                values[f"sensor.{prefix}shot_noise"] = float(slope)
            if floor > 0:
                values[f"sensor.{prefix}read_noise"] = math.sqrt(floor)

    if condition in ("Jd", "Jw"):
        # Sample an eroded exterior in a small thumbnail to avoid paper edges.
        scale = min(1.0, 480 / max(frame))
        thumb = cv2.resize(rgb, (round(frame[0] * scale), round(frame[1] * scale)),
                           interpolation=cv2.INTER_AREA)
        exterior = np.ones(thumb.shape[:2], np.uint8)
        cv2.fillConvexPoly(exterior, np.rint(page * scale).astype(np.int32), 0)
        exterior = cv2.erode(exterior, np.ones((9, 9), np.uint8)).astype(bool)
        if exterior.mean() >= 0.06:
            kind = "dark_table" if condition == "Jd" else "wood"
            surface = np.median(thumb[exterior], axis=0) / 255
            if white:
                paper_gain = srgb_to_linear(np.median(white, axis=0))
                surface = linear_to_srgb(srgb_to_linear(surface) / np.maximum(paper_gain, 0.07))
            values[f"surface.{kind}_rgb"] = (255 * surface).tolist()
    return values, orientation


def fit_directory(photo_dir, *, horizontal_fov=68, min_observations=3):
    """Open only registered filenames and measure only fiducial-verified pages."""
    low, high = 0.05, 0.95
    config = read_config()
    series = defaultdict(list)
    used, skipped = [], []
    targets = {}
    for name, page, condition in registered_shots():
        path = photo_dir / name
        if path.is_symlink() or not path.is_file():
            continue
        if page not in targets:
            targets[page] = json.loads((PACK / "gt" / f"{page}.json").read_text(encoding="utf-8"))
        try:
            measurements, orientation = measure(path, targets[page], condition, horizontal_fov)
        except (ValueError, OSError, cv2.error) as error:
            skipped.append({"filename": name, "reason": str(error)})
            continue
        for key, value in measurements.items():
            series[key].append(value)
        used.append({"filename": name, "condition": condition, "exif_orientation": orientation,
                     "measured": sorted(measurements)})
    counts, fitted = {}, []
    for section, fields in config.items():
        for field in fields:
            key = f"{section}.{field}"
            values = series[key]
            counts[key] = len(values)
            if len(values) < min_observations:
                continue
            interval = np.quantile(values, (low, high), axis=0).T
            if field.endswith("_rgb"):
                fields[field] = np.round(interval, 3).tolist()
            else:
                default_max = 0.95 if field == "vignette" else 64
                bounds = BOUNDS.get(field, (-360 if field.endswith("_deg") else 0, default_max))
                if np.any(interval < bounds[0]) or np.any(interval > bounds[1]):
                    # A bad model fit should not turn into a clipped prior.
                    continue
                if field in INTEGER_RANGES:
                    fields[field] = [math.floor(interval[0]), math.ceil(interval[1])]
                else:
                    fields[field] = np.round(interval, 9).tolist()
            fitted.append(key)
    validate_config(config)
    return config, {
        "pack": "HEOCR-CAL-V1", "status": "partial_photo_fit" if fitted else "uncalibrated",
        "quantiles": [low, high], "horizontal_fov_deg_assumed": horizontal_fov,
        "min_observations": min_observations,
        "frames_registered": used, "frames_rejected": skipped,
        "frames_missing": len(registered_shots()) - len(used) - len(skipped),
        "observation_counts": counts, "fitted": sorted(fitted),
        "retained_priors": sorted(set(counts) - set(fitted)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", type=Path, help="Dedicated folder of original HEOCR-CAL-V1 JPEGs")
    parser.add_argument("output", type=Path, help="New directory for config.json and fit_report.json")
    parser.add_argument("--horizontal-fov", type=float, default=68, help="Approximate horizontal field of view in degrees")
    parser.add_argument("--min-observations", type=int, default=3)
    args = parser.parse_args()
    if not args.photos.is_dir() or not 10 <= args.horizontal_fov <= 150 or args.min_observations < 1:
        parser.error("Provide a capture directory, field of view in [10, 150], and positive observation minimum")
    config, report = fit_directory(args.photos, horizontal_fov=args.horizontal_fov,
                                   min_observations=args.min_observations)
    if args.output.exists():
        parser.error("Output directory must be new")
    args.output.mkdir(parents=True)
    for name, payload in (("config.json", config), ("fit_report.json", report)):
        (args.output / name).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"{report['status']}: {len(report['frames_registered'])} registered, {len(report['fitted'])} ranges fitted")


if __name__ == "__main__":
    main()
