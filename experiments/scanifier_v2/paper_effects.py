# SPDX-License-Identifier: CC0-1.0
"""Opt-in textured paper, hard cast shadows, and projected rounded creases."""

from dataclasses import dataclass
import math

import cv2 as cv
import numpy as np

from .paper_scene import _grid, encode, linear


def _smoothstep(x):
    value = np.clip(x, 0, 1)
    return value * value * (3 - 2 * value)


def paper_texture(mask, seed, strength):
    """Seed a linear reflectance multiplier for a whole sheet, including its ink."""
    h, w = mask.shape
    rng = np.random.default_rng(seed)
    x, y = _grid((w, h))
    coarse = cv.resize(rng.normal(0, 1, (8, 7)).astype(np.float32), (w, h), interpolation=cv.INTER_CUBIC)
    speckle = rng.standard_normal((h, w), dtype=np.float32)
    fibres = cv.GaussianBlur(speckle, (0, 0), sigmaX=2.2, sigmaY=.70)
    tone = 1 + strength * (.062 * coarse + .025 * fibres + .008 * speckle)
    stains = np.zeros_like(coarse)
    stains_meta = []
    left, top, width, height = cv.boundingRect((mask > .5).astype(np.uint8))
    if width == 0 or height == 0:
        raise ValueError("Paper texture requires a visible sheet")
    # Let marks extend past the paper's edge so some are partly cropped.
    for _ in range(6):
        u, v = (np.array([left, top]) + rng.uniform(.04, .96, 2) * [width,height]) / [w,h]
        rx, ry = rng.uniform(.035, .113, 2) * min(width, height)
        tilt = rng.uniform(-1, 1)
        dx, dy = x - u*w, y - v*h
        ax = dx * math.cos(tilt) + dy * math.sin(tilt)
        ay = dy * math.cos(tilt) - dx * math.sin(tilt)
        radius = np.hypot(ax/rx, ay/ry) * (1 + .10 * coarse)
        ring = np.exp(-((radius-.83)/.20)**2)
        wash = np.maximum(1 - radius, 0)**.8
        darkness = rng.uniform(.14, .34)
        stains += darkness * (.37*ring + .63*wash)
        stains_meta.append({"center_uv": [float(u), float(v)], "radii_px": [float(rx), float(ry)],
                            "angle_radians": float(tilt), "density": float(darkness)})
    colour = (tone[..., None] * (1 - strength*stains[..., None]*np.float32([.43,.73,1.04])))
    gain = 1 + (np.clip(colour, .58, 1.15)-1) * mask[..., None]
    return gain, stains_meta


@dataclass(frozen=True)
class ShadowBand:
    """Projected occluder edge or finite bar, in final raster pixel centres."""

    center: tuple
    angle_deg: float
    penumbra: float
    half_width: float | None = None

    def coverage(self, x, y):
        d = _offset(x, y, self.center, self.angle_deg)
        inside = d if self.half_width is None else self.half_width - abs(d)
        return _smoothstep(.5 + inside / self.penumbra)


def _offset(x, y, center, angle_deg):
    angle = math.radians(angle_deg)
    return (y - center[1])*math.cos(angle) - (x - center[0])*math.sin(angle)


def cast_shadow(size, bands, ambient_rgb):
    """Apply the occluder across the scene so both the sheet and its support receive it."""
    x, y = _grid(size)
    coverage = np.maximum.reduce([band.coverage(x, y) for band in bands])
    return 1 - coverage[..., None] * (1 - np.asarray(ambient_rgb, np.float32)), coverage


@dataclass(frozen=True)
class Crease:
    """One straight crease with a rounded hinge and relaxed shoulders."""

    center: tuple
    angle_deg: float
    shoulder_px: float
    compression: float
    valley: float


class CreaseWarp:
    """Inverse raster map for rounded creases on a photographed sheet.

    Interior compression and shoulder relaxation preserve the original page
    silhouette. This approximates the projection of folded paper in a fixed
    camera frame. Use the full 3D renderer when the fold moves the silhouette
    or exposes the underside of the sheet.
    """

    def __init__(self, mask, creases):
        self._size = mask.shape[::-1]
        x, y = _grid(self._size)
        distance = cv.distanceTransform((mask > .5).astype(np.uint8), cv.DIST_L2, cv.DIST_MASK_PRECISE)
        blend = _smoothstep(distance / (min(self._size) * .068))
        self._shift = np.zeros((*mask.shape, 2), np.float32)
        self.illumination = np.ones(mask.shape, np.float32)
        for crease in creases:
            d = _offset(x, y, crease.center, crease.angle_deg)
            s = d / crease.shoulder_px
            theta = math.radians(crease.angle_deg)
            move = crease.compression * d * np.exp(-.5*s**2) * blend
            self._shift[..., 0] -= math.sin(theta) * move
            self._shift[..., 1] += math.cos(theta) * move
            fibre = .10 * np.exp(-.5*((s + .066)/.038)**2)
            falloff = .64 * np.exp(-.5*((s - .19)/.21)**2)
            fold_line = .36 * np.exp(-.5*(s/.073)**2)
            self.illumination *= 1 + (fibre - crease.valley*(falloff + fold_line)) * blend

    def remap(self, rgb):
        x, y = _grid(self._size)
        return cv.remap(rgb, x + self._shift[..., 0], y + self._shift[..., 1],
                        cv.INTER_LINEAR, borderMode=cv.BORDER_REPLICATE)

    def rectify(self, captured):
        """Sample the rendered RGB back into the previous camera coordinate space."""
        x, y = _grid(self._size)
        px, py = x, y
        for _ in range(16):
            shift = cv.remap(self._shift, px, py, cv.INTER_LINEAR, borderMode=cv.BORDER_REPLICATE)
            px, py = x - shift[..., 0], y - shift[..., 1]
        return cv.remap(captured, px, py, cv.INTER_CUBIC, borderMode=cv.BORDER_REPLICATE)

    def _displacement(self, points):
        points = np.asarray(points, np.float64)
        height, width = self._shift.shape[:2]
        x = np.clip(points[:, 0], 0, width-1)
        y = np.clip(points[:, 1], 0, height-1)
        u, v = np.minimum(x.astype(int), width-2), np.minimum(y.astype(int), height-2)
        a, b = (x-u)[:, None], (y-v)[:, None]
        # Match the map's bilinear geometry without quantising the vertices.
        return ((1-b) * ((1-a)*self._shift[v,u] + a*self._shift[v,u+1])
                + b*((1-a)*self._shift[v+1,u] + a*self._shift[v+1,u+1]))

    def inverse(self, points):
        return points + self._displacement(points)

    def forward(self, points):
        target = np.asarray(points, np.float64)
        moved = target.copy()
        for _ in range(20):
            moved = target - self._displacement(moved)
        if np.max(np.linalg.norm(self.inverse(moved) - target, axis=1)) >= .15:
            raise ValueError("Crease projection did not converge")
        return moved


def tone(rgb, gain):
    """Apply one radiometric field to photographed ink, blank paper, and support."""
    return encode(linear(rgb) * gain)
