# SPDX-License-Identifier: CC0-1.0
"""Optional, geometry-preserving phone output profile for matched capture studies."""

from dataclasses import dataclass
import json
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class PhonePhotometry:
    tone_curve: tuple[tuple[int, int], ...] = ()
    local_tone_radius: float = 0.0
    sharpen_amount: float = 0.0
    sensor_noise_scale: float = 1.0
    luma_noise_sd: float = 0.0
    jpeg_tables: tuple[tuple[int, ...], ...] = ()
    blank_reverse: bool = False

    @classmethod
    def read(cls, path):
        record = json.loads(path.read_bytes())
        if not isinstance(record, dict):
            raise ValueError("Expected a phone photometry JSON object")
        unknown = record.keys() - cls.__dataclass_fields__.keys()
        if unknown:
            raise ValueError(f"Unknown phone photometry fields: {sorted(unknown)}")
        curve = record.get("tone_curve", [])
        if not isinstance(curve, list) or any(
            not isinstance(point, list) or len(point) != 2
            or any(type(level) is not int or not 0 <= level <= 255 for level in point)
            for point in curve
        ):
            raise ValueError("Tone curve must contain 8-bit [input, output] knots")
        if curve and (curve[0][0] != 0 or curve[-1][0] != 255
                      or any(b[0] <= a[0] or b[1] < a[1] for a, b in zip(curve, curve[1:]))):
            raise ValueError("Tone curve inputs must increase from 0 to 255 and outputs must not decrease")
        tables = record.get("jpeg_tables", [])
        if not isinstance(tables, list) or (tables and len(tables) != 2) or any(
            not isinstance(table, list) or len(table) != 64
            or any(type(level) is not int or not 1 <= level <= 255 for level in table)
            for table in tables
        ):
            raise ValueError("Supply both 64-entry JPEG quantization tables or omit them")
        for field, maximum in (("sensor_noise_scale", 4), ("luma_noise_sd", 16),
                               ("local_tone_radius", .15), ("sharpen_amount", .5)):
            value = record.get(field, getattr(cls, field))
            if type(value) not in (int, float) or not 0 <= value <= maximum or not math.isfinite(value):
                raise ValueError(f"{field} must be finite and between 0 and {maximum}")
        if type(record.get("blank_reverse", False)) is not bool:
            raise ValueError("blank_reverse must be Boolean")
        if record.get("local_tone_radius", 0) and not curve:
            raise ValueError("A local tone radius requires a tone curve")
        return cls(**{**record, "tone_curve": tuple(map(tuple, curve)), "jpeg_tables": tuple(map(tuple, tables))})

    def apply_tone(self, rgb):
        if not self.tone_curve:
            return rgb
        source, target = np.transpose(self.tone_curve)
        gray = rgb @ np.float32([.2126, .7152, .0722])
        lookup = np.interp(np.arange(256), source, target).astype(np.float32) / 255
        paper = gray
        if self.local_tone_radius:
            # Work on a small image so the kernel is independent of render DPI.
            # A wide morphological close suppresses the printed strokes.
            height, width = gray.shape
            scale = min(1, 360 / max(height, width))
            sample = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            radius = max(1, round(max(sample.shape) * self.local_tone_radius))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
            paper = cv2.morphologyEx(sample, cv2.MORPH_CLOSE, kernel)
            paper = cv2.GaussianBlur(paper, (0, 0), max(1, radius * .45))
        mapped = np.interp(paper * 255, np.arange(256), lookup).astype(np.float32)
        adjustment = mapped - paper
        if self.local_tone_radius:
            adjustment = cv2.resize(adjustment, (width, height), interpolation=cv2.INTER_LINEAR)
        return np.clip(rgb + adjustment[..., None], 0, 1)

    def sharpen(self, rgb):
        if not self.sharpen_amount:
            return rgb
        blurred = cv2.GaussianBlur(rgb, (0, 0), .85)
        return np.clip(rgb + self.sharpen_amount * (rgb - blurred), 0, 1)

    def add_luma_noise(self, rgb, seed):
        if not self.luma_noise_sd:
            return rgb
        rng = np.random.default_rng(seed ^ 73457)
        noise = rng.normal(0, self.luma_noise_sd / 255, rgb.shape[:2]).astype(np.float32)
        return rgb + noise[..., None]
