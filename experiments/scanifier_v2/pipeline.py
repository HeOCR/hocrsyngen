"""Seeded RGB phone capture stages and their configurable priors."""

import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .geometry import Warp, make_warp


PRIORS_PATH = Path(__file__).with_name("priors.json")

# Physical/implementation bounds for config validation, independent of priors.
BOUNDS = {
    "long_edge_px": (16, 8192),
    "margin": (0, 0.45),
    "frame_aspect": (0.38, 1),
    "pitch_deg": (-70, 70),
    "yaw_deg": (-70, 70),
    "distance": (1, 20),
    "curl": (-0.18, 0.18),
    "crumple": (0, 0.15),
    "crumple_cycles": (0, 8),
    "texture": (0, 1),
    "vignette": (0, 0.95),
    "gradient": (0, 0.95),
    "center_x": (0, 1),
    "center_y": (0, 1),
    "width": (0.01, 2),
    "shadow_gain": (0, 1),
    "sun_gain": (1, 8),
    "quality": (1, 100),
}
INTEGER_RANGES = {"long_edge_px", "quality"}


def read_config(path=None):
    defaults = json.loads(PRIORS_PATH.read_text(encoding="utf-8"))
    if path is not None:
        overrides = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(overrides, dict) or set(overrides) - defaults.keys():
            raise ValueError("Unknown scanifier config section")
        for section, values in overrides.items():
            if not isinstance(values, dict) or set(values) - defaults[section].keys():
                raise ValueError(f"Unknown scanifier config field in {section}")
            for key, value in values.items():
                if key.endswith("_weights") and isinstance(value, dict):
                    if value.keys() != defaults[section][key].keys():
                        raise ValueError(f"{section}.{key} must list every allowed category")
            defaults[section].update(values)
    validate_config(defaults)
    return defaults


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _valid_range(value, low, high):
    return (isinstance(value, list) and len(value) == 2
            and all(_finite(item) for item in value) and low <= value[0] <= value[1] <= high)


def validate_config(config):
    template = json.loads(PRIORS_PATH.read_text(encoding="utf-8"))
    if config.keys() != template.keys():
        raise ValueError("Scanifier config must have all prior sections")
    for section, fields in config.items():
        if not isinstance(fields, dict) or fields.keys() != template[section].keys():
            raise ValueError(f"Scanifier config must have all {section} fields")
        for key, value in fields.items():
            if key.endswith("_weights"):
                valid = (isinstance(value, dict) and value.keys() == template[section][key].keys()
                         and all(_finite(v) and 0 <= v <= 1 for v in value.values()) and sum(value.values()) > 0)
            elif key == "probability" or key.endswith("_probability"):
                valid = _finite(value) and 0 <= value <= 1
            elif key.endswith("_rgb"):
                valid = isinstance(value, list) and len(value) == 3 and all(_valid_range(v, 0, 255) for v in value)
            else:
                fallback = (-360, 360) if key.endswith("_deg") else (0, 64)
                low, high = BOUNDS.get(key, fallback)
                if key.endswith("_strength"):
                    high = 1
                valid = _valid_range(value, low, high)
                if valid and key in INTEGER_RANGES:
                    valid = all(type(v) is int for v in value)
            if not valid:
                raise ValueError(f"Invalid scanifier config value {section}.{key}: {value!r}")


def _rng(seed, stage):
    digest = hashlib.sha256(f"scanifier-v2/{seed}/{stage}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], "big"))


def _weighted(weights, rng):
    keys = sorted(weights)
    values = np.array([weights[key] for key in keys], dtype=float)
    return str(rng.choice(keys, p=values / values.sum()))


def _ranges(fields, rng):
    return {key: float(rng.uniform(*value)) for key, value in sorted(fields.items())
            if isinstance(value, list) and len(value) == 2}


def sample_parameters(config, seed):
    """Sample each stage from a separate stream so stage changes stay local."""
    sampled = {}
    for stage, fields in config.items():
        rng = _rng(seed, stage)
        params = _ranges(fields, rng)
        if stage == "geometry":
            params["long_edge_px"] = int(rng.integers(fields["long_edge_px"][0], fields["long_edge_px"][1] + 1))
            params["quarter_turn"] = int(_weighted(fields["quarter_turn_weights"], rng))
            for key in ("curl", "crumple"):
                if rng.random() >= fields[f"{key}_probability"]:
                    params[key] = 0.0
        elif stage == "surface":
            params["kind"] = _weighted(fields["kind_weights"], rng)
            params["rgb"] = [float(rng.uniform(*v)) for v in fields[f"{params['kind']}_rgb"]]
        elif stage == "lighting":
            params["low_light"] = bool(rng.random() < fields["low_light_probability"])
        elif stage == "hard_light":
            params["kind"] = (_weighted(fields["kind_weights"], rng)
                              if rng.random() < fields["probability"] else "none")
        elif stage == "optics" and rng.random() >= fields["motion_probability"]:
            params["motion_length_px"] = 0.0
        elif stage == "jpeg":
            params["quality"] = int(rng.integers(fields["quality"][0], fields["quality"][1] + 1))
            params["subsampling"] = int(_weighted(fields["subsampling_weights"], rng))
        sampled[stage] = params
    return sampled


def srgb_to_linear(rgb):
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(rgb):
    rgb = np.clip(rgb, 0, 1)
    return np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * rgb ** (1 / 2.4) - 0.055)


def _surface(size, p, rng):
    w, h = size
    if p["texture"] == 0:
        return np.broadcast_to(np.array(p["rgb"], np.float32) / 255, (h, w, 3)).copy()
    noise = cv2.resize(rng.standard_normal((9, 9), dtype=np.float32), size, interpolation=cv2.INTER_CUBIC)
    noise *= 0.24
    noise += rng.standard_normal((h, w), dtype=np.float32) * 0.10
    if p["kind"] == "wood":
        y, x = np.ogrid[-0.5:0.5:h * 1j, -0.5:0.5:w * 1j]
        angle = np.deg2rad(p["wood_angle_deg"])
        cross = x * np.cos(angle) + y * np.sin(angle)
        along = -x * np.sin(angle) + y * np.cos(angle)
        phase = 2 * np.pi * (p["wood_rings"] * (cross + 0.12 * along ** 2) + 0.38 * noise)
        rings = (np.sin(phase) + 0.63 * np.sin(phase * 0.41) + 0.22 * np.sin(phase * 3.71)) / 1.85
        noise += np.asarray(rings, dtype=np.float32) * 0.65
    rgb = np.array(p["rgb"], np.float32) / 255
    return np.clip(rgb * (1 + p["texture"] * noise[..., None]), 0, 1)


def _scene(image, warp, params, rng):
    w, h = warp.size
    result = _surface(warp.size, params, rng)
    # Remap in strips to keep the double-precision inverse grids small.
    for start in range(0, h, 192):
        stop = min(start + 192, h)
        y, x = np.mgrid[start:stop, :w]
        source = warp.inverse(np.stack((x + 0.5, y + 0.5), axis=-1))
        u, v = source[..., 0], source[..., 1]
        distance = np.minimum(np.minimum(u, image.shape[1] - u), np.minimum(v, image.shape[0] - v))
        alpha = np.clip(distance + 0.5, 0, 1).astype(np.float32)[..., None]
        mapping = (source - 0.5).astype(np.float32)
        page = cv2.remap(image, mapping, None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        result[start:stop] *= 1 - alpha
        result[start:stop] += alpha * (page.astype(np.float32) / 255)
    return srgb_to_linear(result)


def _lighting(rgb, p, hard):
    height, width = rgb.shape[:2]
    y, x = np.ogrid[-0.5:0.5:height * 1j, -0.5:0.5:width * 1j]
    angle = np.deg2rad(p["gradient_angle_deg"])
    gain = (1 + p["gradient"] * (np.cos(angle) * x + np.sin(angle) * y))
    gain *= 1 - p["vignette"] * (x * x + y * y) * 2
    if hard["kind"] != "none":
        yy, xx = np.ogrid[:height, :width]
        xx = xx + 0.5 - hard["center_x"] * width
        yy = yy + 0.5 - hard["center_y"] * height
        a = np.deg2rad(hard["angle_deg"])
        transverse = xx * np.cos(a) + yy * np.sin(a)
        distance = np.abs(transverse)
        if hard["kind"] != "shadow_stripe":
            longitudinal = -xx * np.sin(a) + yy * np.cos(a)
            distance = np.maximum(distance, np.abs(longitudinal))
        radius = hard["width"] * min(height, width) / 2
        mask = np.clip((radius - distance) / max(hard["edge_px"], 1e-9) + 0.5, 0, 1)
        factor = hard["sun_gain"] if hard["kind"] == "sun_patch" else hard["shadow_gain"]
        gain *= 1 + (factor - 1) * mask
    exposure = p["low_light_exposure"] if p["low_light"] else p["exposure"]
    white_balance = [p["white_balance_r"], p["white_balance_g"], p["white_balance_b"]]
    return rgb * (gain[..., None] * exposure * np.array(white_balance)).astype(np.float32)


def _gaussian(image, sigma):
    return cv2.GaussianBlur(image, (0, 0), sigma) if sigma > 0.01 else image


def _optics(rgb, p):
    sharp = _gaussian(rgb, p["defocus_sigma_px"])
    gradient = p["defocus_gradient_px"]
    if gradient > 0.01:
        soft = _gaussian(rgb, p["defocus_sigma_px"] + gradient)
        h, w = rgb.shape[:2]
        y, x = np.ogrid[-0.5:0.5:h * 1j, -0.5:0.5:w * 1j]
        angle = np.deg2rad(p["defocus_angle_deg"])
        ramp = (0.5 + (x * np.cos(angle) + y * np.sin(angle)) /
                (abs(np.cos(angle)) + abs(np.sin(angle)))).astype(np.float32)
        sharp = sharp * (1 - ramp[..., None]) + soft * ramp[..., None]
    length = p["motion_length_px"]
    if length > 0.01:
        radius = math.ceil(length / 2) + 1
        kernel = np.zeros((2 * radius + 1, 2 * radius + 1), np.float32)
        angle = np.deg2rad(p["motion_angle_deg"])
        t = np.linspace(-length / 2, length / 2, math.ceil(length * 4) + 1)
        x, y = radius + t * np.cos(angle), radius + t * np.sin(angle)
        ix, iy = x.astype(int), y.astype(int)
        fx, fy = x - ix, y - iy
        np.add.at(kernel, (iy, ix), (1 - fx) * (1 - fy))
        np.add.at(kernel, (iy + 1, ix), (1 - fx) * fy)
        np.add.at(kernel, (iy, ix + 1), fx * (1 - fy))
        np.add.at(kernel, (iy + 1, ix + 1), fx * fy)
        sharp = cv2.filter2D(sharp, -1, kernel / kernel.sum())
    return sharp


def _sensor(rgb, p, low_light, rng):
    prefix = "low_light_" if low_light else ""
    shot, read = p[prefix + "shot_noise"], p[prefix + "read_noise"]
    if shot > 0 or read > 0:
        deviation = np.sqrt(np.maximum(rgb, 0) * shot + read * read)
        rgb = rgb + deviation * rng.standard_normal(rgb.shape, dtype=np.float32)
    return linear_to_srgb(rgb)


def _isp(rgb, p, low_light):
    strength = p["low_light_denoise_strength"] if low_light else p["denoise_strength"]
    if strength > 0:
        smooth = _gaussian(rgb, p["denoise_sigma_px"])
        detail = rgb - smooth
        threshold = max(p["denoise_edge_threshold"], 1e-6)
        fraction = strength / (1 + np.square(np.max(np.abs(detail), axis=2, keepdims=True) / threshold))
        rgb = rgb - fraction * detail
    if p["sharpen_amount"] > 0:
        rgb = rgb + p["sharpen_amount"] * (rgb - _gaussian(rgb, p["sharpen_sigma_px"]))
    return Image.fromarray(np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8))


@dataclass(frozen=True)
class Capture:
    jpeg: bytes
    warp: Warp
    parameters: dict
    input_orientation: int


def capture(image, seed, config):
    """Render a page; input annotations use the stored raster's coordinates."""
    p = sample_parameters(config, seed)
    tag = image.getexif().get(274, 1)
    orientation = tag if type(tag) is int and 1 <= tag <= 8 else 1
    warp = make_warp(image.size, orientation, p["geometry"])
    raster = np.asarray(image.convert("RGB"))
    rgb = _scene(raster, warp, p["surface"], _rng(seed, "surface_pixels"))
    rgb = _lighting(rgb, p["lighting"], p["hard_light"])
    rgb = _optics(rgb, p["optics"])
    low_light = p["lighting"]["low_light"]
    rgb = _sensor(rgb, p["sensor"], low_light, _rng(seed, "sensor_pixels"))
    output = _isp(rgb, p["isp"], low_light)
    buffer = io.BytesIO()
    output.save(buffer, format="JPEG", quality=p["jpeg"]["quality"], subsampling=p["jpeg"]["subsampling"])
    return Capture(buffer.getvalue(), warp, p, orientation)
