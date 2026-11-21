"""Apply a seeded, fixed-geometry calibration profile to a PIL page.

Profiles are JSON documents. Fit statistics and fitted profiles can be kept
outside the source repository. The renderer never opens a calibration input.
"""
import io
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .pipeline import _optics, _rng


PROFILES = ("phone_flat", "phone_oblique", "adobe_scan", "flatbed_old")
RANGE_BOUNDS = {
    "paper_r": (0, 255), "paper_g": (0, 255), "paper_b": (0, 255),
    "gradient_x": (-2, 2), "gradient_y": (-2, 2),
    "blur_sigma": (0, 12), "defocus_add": (0, 12),
    "motion_px": (0, 24), "motion_deg": (0, 180),
    "noise_sd": (0, 32), "noise_low_mix": (0, 1), "noise_cv": (0, 1),
    "show_through_opacity": (0, 1), "scanner_edge_fraction": (0, 0.5),
    "scanner_bar_fraction": (0, 0.5), "scanner_bars": (0, 6),
}


def read_profile(path):
    """Load and validate a profile produced by the development fitter."""
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_profile(profile)
    return profile


def validate_profile(profile):
    if (not isinstance(profile, dict) or profile.get("version") != 1
            or profile.get("name") not in PROFILES
            or profile.get("status") not in ("dev_fit", "prior_only")
            or type(profile.get("seed")) is not int or profile["seed"] < 0):
        raise ValueError("Invalid scanifier development profile header")
    ranges = profile.get("ranges")
    if not isinstance(ranges, dict) or ranges.keys() != RANGE_BOUNDS.keys():
        raise ValueError("Scanifier profile must provide all named ranges")
    for key, (low, high) in RANGE_BOUNDS.items():
        value = ranges[key]
        if (not isinstance(value, list) or len(value) != 2
                or any(type(item) not in (int, float) or not math.isfinite(item) for item in value)
                or not low <= value[0] <= value[1] <= high):
            raise ValueError(f"Invalid scanifier profile range {key}")
        if key == "scanner_bars" and any(type(item) is not int for item in value):
            raise ValueError(f"Scanifier profile range {key} needs integer endpoints")
    encoders = profile.get("jpeg_encoders")
    if not isinstance(encoders, list):
        raise ValueError("jpeg_encoders must list observed encoders, or be empty for no JPEG")
    for encoder in encoders:
        if (not isinstance(encoder, dict) or set(encoder) != {"subsampling", "qtables"}
                or type(encoder["subsampling"]) is not int or encoder["subsampling"] not in (0, 1, 2)
                or not isinstance(encoder["qtables"], list) or not 1 <= len(encoder["qtables"]) <= 2
                or any(not isinstance(table, list) or len(table) != 64
                       or any(type(item) is not int or not 1 <= item <= 255 for item in table)
                       for table in encoder["qtables"])):
            raise ValueError("Invalid JPEG subsampling or baseline quantization tables")


def sample_profile(profile, seed=None):
    """Sample named renderer ranges with stable, independent random streams."""
    validate_profile(profile)
    seed = profile["seed"] if seed is None else seed
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    sampled = {}
    for key, (low, high) in profile["ranges"].items():
        rng = _rng(seed, "dev_profile/" + key)
        sampled[key] = (int(rng.integers(low, high + 1)) if key == "scanner_bars"
                        else float(rng.uniform(low, high)))
    encoders = profile["jpeg_encoders"]
    index = _rng(seed, "dev_profile/jpeg_encoder").integers(len(encoders)) if encoders else None
    sampled["jpeg"] = encoders[index] if index is not None else None
    return sampled


def _noise(size, p, rng):
    width, height = size
    white = rng.standard_normal((height, width), dtype=np.float32)
    low = cv2.GaussianBlur(white, (0, 0), 1.2)
    low /= max(float(low.std()), 1e-6)
    mixture = white * math.sqrt(1 - p["noise_low_mix"]) + low * math.sqrt(p["noise_low_mix"])
    mixture /= max(float(mixture.std()), 1e-6)
    grid = rng.standard_normal((8, 8), dtype=np.float32)
    field = cv2.resize(grid, size, interpolation=cv2.INTER_LINEAR)
    field /= max(float(field.std()), 1e-6)
    # Lognormal scales keep noise amplitude positive across the frame.
    sigma = math.sqrt(math.log1p(p["noise_cv"] ** 2))
    gain = np.exp(sigma * field - sigma ** 2 / 2)
    return p["noise_sd"] * mixture * gain


def _render(image, p, seed, reverse):
    original = image.convert("RGB")
    if reverse is not None and p["show_through_opacity"] > 0:
        from .degradations import show_through

        opacity = p["show_through_opacity"]
        original = show_through(original, reverse, seed, opacity=(opacity, opacity))
    rgb = np.asarray(original, dtype=np.float32) / 255
    height, width = rgb.shape[:2]
    y, x = np.ogrid[-0.5:0.5:height * 1j, -0.5:0.5:width * 1j]
    paper = np.float32([p["paper_r"], p["paper_g"], p["paper_b"]])
    gain = np.exp(x * p["gradient_x"] + y * p["gradient_y"]).astype(np.float32)
    rgb = rgb * (gain[..., None] * paper)
    optics = {"defocus_sigma_px": p["blur_sigma"], "defocus_gradient_px": 0,
              "motion_length_px": p["motion_px"], "motion_angle_deg": p["motion_deg"]}
    sharp = _optics(rgb, optics)
    if p["defocus_add"] > 0:
        soft = _optics(rgb, optics | {"defocus_sigma_px": p["blur_sigma"] + p["defocus_add"]})
        radial = np.clip((np.hypot(x, y) - 0.15) / 0.45, 0, 1).astype(np.float32)[..., None]
        sharp = sharp * (1 - radial) + soft * radial
    if p["noise_sd"] > 0:
        sharp = sharp + _noise(image.size, p, _rng(seed, "dev_profile/noise_pixels"))[..., None]
    output = Image.fromarray(np.uint8(np.clip(sharp + 0.5, 0, 255)))
    if p["scanner_edge_fraction"] > 0 or p["scanner_bars"] > 0:
        from .degradations import scanner_artifacts

        edge, bar, count = p["scanner_edge_fraction"], p["scanner_bar_fraction"], p["scanner_bars"]
        output = scanner_artifacts(output, seed, edge_fraction=(edge, edge),
                                   bar_fraction=(bar, bar), bars=(count, count))
    if p["jpeg"] is None:
        return output
    buffer = io.BytesIO()
    output.save(buffer, format="JPEG", **p["jpeg"])
    return buffer.getvalue()


def apply_profile(image, profile, *, seed=None, reverse=None):
    """Return an RGB raster, preserving the source dimensions and coordinates.

    A JPEG profile performs a single encode and decode. Callers should save the
    resulting raster losslessly to keep that degradation from being applied twice.
    The optional reverse must be an eligible training/development page.
    """
    sampled = sample_profile(profile, seed)
    seed = profile["seed"] if seed is None else seed
    result = _render(image, sampled, seed, reverse)
    if isinstance(result, bytes):
        with Image.open(io.BytesIO(result)) as decoded:
            return decoded.convert("RGB")
    return result
