# SPDX-License-Identifier: CC0-1.0
"""Cylindrical book gutters and ink-preserving paper photometry for review captures."""

from dataclasses import dataclass
from functools import cached_property
import math

import cv2 as cv
import numpy as np
from PIL import Image

from experiments.capture3d.geometry import distort, undistort


def linear(rgb):
    values = np.asarray(rgb, np.float32) / 255
    return np.where(values <= .04045, values / 12.92, ((values + .055) / 1.055) ** 2.4)


def encode(rgb):
    values = np.clip(rgb, 0, 1)
    srgb = np.where(values <= .0031308, 12.92 * values, 1.055 * values ** (1 / 2.4) - .055)
    return np.rint(255 * srgb).astype(np.uint8)


def inked_albedo(paper, transmittance, irradiance):
    """Light one matte surface after its paper albedo has absorbed the ink."""
    return paper * transmittance * irradiance


def _sample(image, x, y, border=cv.BORDER_REPLICATE, outside=0):
    return cv.remap(image, np.asarray(x, np.float32), np.asarray(y, np.float32),
                    cv.INTER_LINEAR, borderMode=border, borderValue=outside)


def _grid(size):
    width, height = size
    y, x = np.mgrid[:height, :width]
    return x.astype(np.float32), y.astype(np.float32)


@dataclass(frozen=True)
class Gutter:
    """One cylindrical leaf, with the physical arc length supplied in source pixels."""

    size: tuple
    side: str
    depth_fraction: float = .24
    turn_deg: float = 72

    @cached_property
    def span(self):
        return self.size[0] * self.depth_fraction

    @cached_property
    def turn(self):
        return math.radians(self.turn_deg)

    @cached_property
    def radius(self):
        return self.span / self.turn

    @cached_property
    def flat_edge(self):
        return self.radius * math.sin(self.turn)

    @cached_property
    def section(self):
        return self.size[0] - self.span + self.flat_edge

    @cached_property
    def facing(self):
        return self.size[0] * .104

    @cached_property
    def output_size(self):
        return int(math.ceil(self.section + self.facing)), self.size[1]

    def _height_scale(self, distance):
        angle = self.turn * np.maximum(1 - distance / self.span, 0)
        return 1 - .032 * (1 - np.cos(angle))

    def forward_xy(self, x, y):
        width, height = self.size
        distance = x if self.side == "left" else width - 1 - x
        angle = self.turn * np.maximum(1 - distance / self.span, 0)
        projected = np.where(distance < self.span, self.flat_edge - self.radius * np.sin(angle),
                             distance - self.span + self.flat_edge)
        x_target = self.facing + projected if self.side == "left" else self.section - 1 - projected
        return x_target, (y - (height - 1) / 2) * self._height_scale(distance) + (height - 1) / 2

    def inverse_xy(self, x, y):
        width, height = self.size
        projected = x - self.facing if self.side == "left" else self.section - 1 - x
        curved = self.span - self.radius * np.arcsin(np.clip((self.flat_edge - projected) / self.radius, -1, 1))
        distance = np.where(projected < self.flat_edge, curved, self.span + projected - self.flat_edge)
        source_x = distance if self.side == "left" else width - 1 - distance
        return source_x, (y - (height - 1) / 2) / self._height_scale(distance) + (height - 1) / 2


def gutter_scan(front, warp, seed, paper_rgb=(240, 230, 211), reverse=None):
    rgb = np.asarray(front)
    x, y = _grid(warp.output_size)
    distance = x - warp.facing if warp.side == "left" else warp.section - 1 - x
    u, v = warp.inverse_xy(x, y)
    # The same angle controls horizontal foreshortening, cosine falloff and blur.
    theta = np.arcsin(np.clip((warp.flat_edge - np.abs(distance)) / warp.radius, 0, 1))
    incidence = np.maximum(np.cos(theta), 0)
    valley = (0.25 + .75 * incidence**1.7) * (1 - .72 * np.exp(-np.abs(distance) / (warp.span * .13)))
    height, width = rgb.shape[:2]
    transmittance = .066 + .934 * linear(cv.cvtColor(rgb, cv.COLOR_RGB2GRAY))
    if reverse is not None:
        back = cv.cvtColor(np.asarray(reverse), cv.COLOR_RGB2GRAY)[:, ::-1]
        back = cv.resize(back, (width, height), interpolation=cv.INTER_AREA)
        transmittance *= 1 - .086 * cv.GaussianBlur(1 - back.astype(np.float32) / 255, (0, 0), 2.2)
    warped = _sample(transmittance, u, v)
    warped[(distance < 0) | (v < -.5) | (v > height - .5)] = 1
    blurred = cv.GaussianBlur(warped, (0, 0), 2.0)
    focus_loss = np.clip(theta / warp.turn, 0, 1)**2 * .81
    warped += (blurred - warped) * focus_loss
    rng = np.random.default_rng(seed)
    grain = rng.normal(0, .009, warped.shape).astype(np.float32)
    lamp = .99 - .06 * (y / height - .50)**2 - .034 * x / x.shape[1]
    paper = linear(np.asarray(paper_rgb))[None, None, :] * (1 + grain[..., None])
    output = inked_albedo(paper, warped[..., None], (valley * lamp)[..., None])
    return Image.fromarray(encode(output))


@dataclass(frozen=True)
class Phone:
    """An oblique plane with a slight, invertible lift at the far and near edges."""

    source_size: tuple
    size: tuple
    quad: tuple
    curl: float
    k1: float

    @cached_property
    def transform(self):
        width, height = self.size
        return cv.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]),
                                          np.float32(self.quad) * [np.float32(width), np.float32(height)])

    @cached_property
    def inverse_transform(self):
        return np.linalg.inv(self.transform)

    def _curve(self, v):
        # Near edge bends toward the lens, moving the page up and slightly wider.
        return self.curl * ((1 - v) ** 6 - .72 * v**8)

    def forward_xy(self, x, y):
        u, v = (x + .5) / self.source_size[0], (y + .5) / self.source_size[1]
        bend = self._curve(v)
        bx, by = _project(self.transform, .5 + (u - .5) * (1 - .60 * bend), v + bend)
        fx, fy = distort(bx, by, *self.size, self.k1)
        return fx - .5, fy - .5

    def inverse_xy(self, x, y):
        bx, by = undistort(x + .5, y + .5, *self.size, self.k1)
        u, warped_v = _project(self.inverse_transform, bx, by)
        v = np.clip(warped_v, 0, 1)
        for _ in range(7):
            bend = self._curve(v)
            slope = 1 - self.curl * (6 * (1 - v)**5 + 5.76 * v**7)
            v = np.clip(v - (v + bend - warped_v) / slope, -.12, 1.12)
        bend = self._curve(v)
        return (.5 + (u - .5) / (1 - .60 * bend)) * self.source_size[0] - .5, v * self.source_size[1] - .5


def _project(matrix, x, y):
    den = matrix[2, 0] * x + matrix[2, 1] * y + matrix[2, 2]
    return ((matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 2]) / den,
            (matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 2]) / den)


def near_phone(front, texture, warp, seed, white_balance, shadow, reverse=None):
    """Photograph one inked sheet on a textured support with directional contact shadow."""
    rng = np.random.default_rng(seed)
    rgb = np.asarray(front)
    h, w = rgb.shape[:2]
    width, height = warp.size
    x, y = _grid(warp.size)
    u, v = warp.inverse_xy(x, y)
    alpha = np.minimum(np.minimum(u + 1., w - u), np.minimum(v + 1., h - v))
    alpha = np.clip(alpha, 0, 1).astype(np.float32)
    v_norm = np.clip((v + .5) / h, 0, 1)
    lift = .30 + .70 * np.abs(2 * v_norm - 1)**2
    weight = alpha * lift
    cast = cv.warpAffine(weight, np.float32([[1, 0, shadow[0]], [0, 1, shadow[1]]]),
                         (width, height), flags=cv.INTER_LINEAR)
    cast = cv.GaussianBlur(cast, (0, 0), 8.5)
    contact = cv.GaussianBlur(alpha, (0, 0), 3.0)
    tx = (x / width * .82 + .075 + .085 * (1 - y / height)) * (texture.shape[1] - 1)
    ty = (y / height * .86 + .06) * (texture.shape[0] - 1)
    surface = _sample(linear(texture), tx, ty)
    surface = cv.GaussianBlur(surface, (0, 0), .7)
    surface *= (1 - .56 * cast - .38 * contact * (1 - alpha))[..., None]
    ink = 1 - linear(cv.cvtColor(rgb, cv.COLOR_RGB2GRAY))
    if reverse is not None:
        reverse_gray = cv.cvtColor(np.asarray(reverse), cv.COLOR_RGB2GRAY)[:, ::-1]
        reverse_gray = cv.resize(reverse_gray, (w, h), interpolation=cv.INTER_AREA)
        reverse_show = cv.GaussianBlur(1 - reverse_gray.astype(np.float32) / 255, (0, 0), 2.5)
    else:
        reverse_show = 0
    transmittance = _sample((1 - .928 * ink) * (1 - .032 * reverse_show), u, v)
    lighting_x, lighting_y = x / width - .5, y / height - .5
    cast_line = .84 + .16 * np.tanh((lighting_x + lighting_y * .67 + .06) * 3.1)
    shared = (.98 + .15 * lighting_x - .17 * lighting_y) * cast_line
    vignette = 1 - .18 * (lighting_x**2 + lighting_y**2)
    local_paper = .972 + rng.normal(0, .006, alpha.shape).astype(np.float32)
    local_paper += (.026 * np.sin(v_norm * np.pi) - .068 * (1 - v_norm)**8).astype(np.float32)
    paper = local_paper[..., None] * linear(np.array([252, 249, 239]))
    combination = paper * (transmittance * alpha)[..., None] + surface * (1 - alpha[..., None])
    camera = inked_albedo(combination, 1, (shared * vignette)[..., None] * np.asarray(white_balance, np.float32))
    # The whole scene has a shallow depth-of-field gradient.
    defocus = np.clip(.1 + (y / height - .51)**2 * 2.25, 0, .68)
    optical = camera + (cv.GaussianBlur(camera, (0, 0), 1.2) - camera) * defocus[..., None]
    optical += rng.normal(0, .0033, alpha.shape).astype(np.float32)[..., None]
    return Image.fromarray(encode(optical))


def _normalized_blur(field, valid, sigma, fallback):
    weight = cv.GaussianBlur(valid.astype(np.float32), (0, 0), sigma)
    total = cv.GaussianBlur(field * valid[..., None], (0, 0), sigma)
    if total.ndim == 2:
        total = total[..., None]
    return np.divide(total, weight[..., None], out=np.broadcast_to(fallback, total.shape).copy(),
                     where=weight[..., None] > .002)


def ink_layers(native):
    """Factor an inked native raster into reconstructed paper and ink transmission."""
    print_rgb = linear(native)
    paper = cv.morphologyEx(print_rgb, cv.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    paper = np.maximum(paper, print_rgb)
    transmission = np.divide(print_rgb, paper, out=np.ones_like(paper), where=paper > 0)
    return paper, transmission


def sdxl_shared_relight(native, edited, page, excluded, phase=0):
    """Recover smooth SDXL illumination from open paper and apply it to the whole inked raster.

    The signed native image supplies the ink and surface geometry. The old text
    protection mask is only a sampling exclusion for estimating lighting.
    It never selects output pixels. No SDXL glyphs are transferred.
    """
    height, width = native.shape[:2]
    original = linear(native)
    donor = linear(edited)
    ratio = np.log(np.clip((donor + .04) / (original + .04), .68, 1.46))
    ratio = cv.resize(ratio, (max(1, width // 7), max(1, height // 7)), interpolation=cv.INTER_AREA)
    good = (page > 0) & ~excluded & (np.min(native, axis=2) > 65)
    if not np.any(good):
        raise ValueError("No open paper for estimating SDXL illumination")
    good_small = cv.resize(good.astype(np.float32), ratio.shape[1::-1], interpolation=cv.INTER_AREA)
    usable = good_small > .94
    if not usable.any():
        raise ValueError("No open-paper blocks after illumination downsampling")
    fallback = np.median(ratio[usable], axis=0).astype(np.float32)
    lit = _normalized_blur(ratio, usable, max(2, ratio.shape[0] * .057), fallback)
    gain = np.exp(cv.resize(lit, (width, height), interpolation=cv.INTER_LINEAR))

    # An oblique window shadow traverses several lines, as well as open paper.
    x, y = _grid((width, height))
    boundary = y / height + (-.43 if phase % 2 else .41) * (x / width - .5)
    shade = .64 + .37 * (.5 + .5 * np.tanh((boundary - (.46 + .032 * (phase % 4))) / .056))
    gain *= shade[..., None].astype(np.float32)
    paper, transmission = ink_layers(native)
    return encode(inked_albedo(paper, transmission, gain)), gain


def halo_residual(rgb, native, ink, valid):
    """Compare 3–6 px rings to locally detrended open paper at the review resolution."""
    distance = cv.distanceTransform(1 - ink.astype(np.uint8), cv.DIST_L2, cv.DIST_MASK_PRECISE)
    luma = lambda image: cv.cvtColor(image, cv.COLOR_RGB2GRAY).astype(np.float32)
    residual = luma(rgb) - luma(native)
    open_paper = valid & (distance >= 8)
    # A 15 px neighbourhood removes slow illumination changes. Only open paper
    # contributes to the baseline, even when the field crosses a line.
    estimate = _normalized_blur(residual[..., None], open_paper, 5, np.zeros(1, np.float32))[..., 0]
    supported = cv.GaussianBlur(open_paper.astype(np.float32), (0, 0), 5) > .055
    inside = valid & supported & (distance >= 3) & (distance <= 6)
    open_paper &= supported
    if not inside.any() or not open_paper.any():
        raise ValueError("Insufficient ring or paper samples for halo measurement")
    adjusted = residual - estimate
    baseline = float(np.median(adjusted[open_paper]))
    values = adjusted[inside] - baseline
    return {"ring_pixels": int(values.size), "open_paper_pixels": int(open_paper.sum()),
            "ring_minus_open": float(np.mean(values)), "p95_abs": float(np.quantile(np.abs(values), .95))}
