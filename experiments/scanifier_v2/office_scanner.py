# SPDX-License-Identifier: CC0-1.0
"""Apply a pinned 300 PPI monochrome office-scanner appearance profile."""

from hashlib import sha256
from io import BytesIO
import json

import cv2
import numpy as np
from PIL import Image

from .geometry import Warp
from .phone_training import PhoneView, phone_annotations


SCHEMA = "heocr.scanifier.office-scanner-dev.v2"


def _bounded(values, length, lo, hi):
    array = np.asarray(values, dtype=float)
    return array.shape == (length,) and np.all(np.isfinite(array) & (array >= lo) & (array <= hi))


def _check(profile):
    if (profile.get("schema") != SCHEMA or profile.get("scope") != "private_development"
            or profile.get("dpi") != 300 or profile.get("mode") != "monochrome"):
        raise ValueError("Expected a private DEV monochrome office-scanner profile at 300 PPI")
    if not _bounded(profile["tone_lut"], 256, 0, 255) or not _bounded(profile["noise_sigma_lut"], 256, 0, 30):
        raise ValueError("Tone and noise curves must have 256 finite in-range entries")
    if not _bounded([profile["toner_gain"]], 1, 0, 1) or not _bounded([profile["blur_sigma"]], 1, 0, 4):
        raise ValueError("The office-scanner toner and blur settings are out of range")
    groups = profile["skew_clockwise_degrees"]
    if ("dev01" not in groups or len(groups) < 2
            or any(not angles or not _bounded(angles, len(angles), -8, 8) for angles in groups.values())):
        raise ValueError("Expected DEV01 and at least one additional in-range skew cohort")
    encoder = profile["jpeg_encoder"]
    if (set(encoder) != {"qtables", "subsampling"} or encoder["subsampling"] not in (0, 1, 2)
            or len(encoder["qtables"]) != 2 or any(len(table) != 64 or any(type(q) is not int or not 1 <= q <= 255
               for q in table) for table in encoder["qtables"])):
        raise ValueError("Expected two integer JPEG quantization tables and a supported subsampling mode")


def render_office_scan(image, lines, *, profile_path, seed, source_ppi, skew=True):
    """Return a same-size raster and exact projected input line annotations."""
    if source_ppi != 300:
        raise ValueError("Render the producer PDF at 300 PPI before applying the office-scanner profile")
    payload = profile_path.read_bytes()
    profile = json.loads(payload)
    _check(profile)
    rng = np.random.default_rng(seed)
    gray = np.asarray(image.convert("L"))
    height, width = gray.shape
    angle = 0.0
    if skew:
        groups = profile["skew_clockwise_degrees"]
        companions = sorted(set(groups) - {"dev01"})
        group = "dev01" if rng.integers(2) == 0 else companions[int(rng.integers(len(companions)))]
        angle = float(rng.choice(groups[group]))
    matrix = cv2.getRotationMatrix2D(((width - 1) / 2, (height - 1) / 2), -angle, 1)
    if angle:
        gray = cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_LINEAR, borderValue=255)
    pixels = gray.astype(np.float32)
    if profile["toner_gain"]:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        strengthened = cv2.erode(gray, kernel).astype(np.float32)
        pixels += profile["toner_gain"] * (strengthened - pixels)
    if profile["blur_sigma"]:
        pixels = cv2.GaussianBlur(pixels, (0, 0), profile["blur_sigma"])
    levels = np.arange(256)
    tone = np.interp(pixels, levels, profile["tone_lut"]).astype(np.float32)
    amplitude = np.interp(pixels, levels, profile["noise_sigma_lut"]).astype(np.float32)
    tone += rng.standard_normal(gray.shape, dtype=np.float32) * amplitude
    gray = Image.fromarray(np.uint8(np.clip(tone + .5, 0, 255))).convert("RGB")
    with BytesIO() as encoded:
        gray.save(encoded, format="JPEG", **profile["jpeg_encoder"])
        encoded.seek(0)
        with Image.open(encoded) as decoded:
            scan = decoded.convert("RGB")

    # OpenCV matrices map pixel centres. The annotation convention uses pixel edges.
    projected = np.vstack((matrix, [0, 0, 1]))
    projected[:2, 2] += .5 - projected[:2, :2] @ np.array([.5, .5])
    warp = Warp(np.eye(3), np.array((0, height)), np.zeros(2), np.array((0, width)),
                np.zeros(2), projected, image.size)
    parameters = {"profile": "office-scanner", "profile_sha256": sha256(payload).hexdigest(),
                  "source_ppi": source_ppi, "seed": seed, "skew_clockwise_deg": angle, "warp": warp.record()}
    return PhoneView(scan, phone_annotations(lines, warp, image.size), warp, parameters)
