# SPDX-License-Identifier: CC0-1.0
"""Explicit phone pose in target-relative metres and camera-local roll."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CameraPose:
    offset_m: tuple[float, float, float]
    roll_deg: float
    lens_mm_equivalent: float

    @classmethod
    def from_record(cls, value):
        names = {"offset_m", "roll_deg", "lens_mm_equivalent"}
        if not isinstance(value, dict) or set(value) != names:
            raise ValueError("Expected camera pose offset_m, roll_deg and lens_mm_equivalent")
        offset = value["offset_m"]
        if not isinstance(offset, (tuple, list)) or len(offset) != 3:
            raise ValueError("Expected a three-element camera pose offset")
        values = (*offset, value["roll_deg"], value["lens_mm_equivalent"])
        limits = ((-.45, .45), (-.45, .45), (.20, .80), (-20, 20), (18, 50))
        if any(type(item) not in (int, float) or not math.isfinite(item) or not lo <= item <= hi
               for item, (lo, hi) in zip(values, limits, strict=True)):
            raise ValueError("Camera pose lies outside the supported phone range")
        return cls(tuple(offset), value["roll_deg"], value["lens_mm_equivalent"])
