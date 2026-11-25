"""Shared Realism v3 scan renderer, including round marks and gutter falloff."""

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from hocrsyngen.printed_ink import trim_ink_edge


@dataclass(frozen=True)
class ScanInkOptics:
    """Independent ink-edge perturbations for paired old-print calibration."""

    stroke_trim: float = 0.0
    halo_gain: float = 0.0
    blur_scale: float = 1.0

    def __post_init__(self):
        if not 0 <= self.stroke_trim <= .35:
            raise ValueError("Stroke trim must be in [0, 0.35]")
        if not -.65 <= self.halo_gain <= .25:
            raise ValueError("Halo gain must be in [-0.65, 0.25]")
        if not .30 <= self.blur_scale <= 1:
            raise ValueError("Blur scale must be in [0.30, 1]")


def _adjust_halo(opacity, gain, scale):
    if gain < 0:
        # Suppress diffuse ink while leaving a fully dark core unchanged.
        return opacity * (1 + gain * (1 - opacity)**2)
    spread = cv2.GaussianBlur(opacity, (0, 0), 1.65 * scale)
    return opacity + gain * np.maximum(spread - opacity, 0) * (1 - opacity)


def smooth_vector(v, sigma):
    return cv2.GaussianBlur(v.astype(np.float32)[None], (0, 0), sigma)[0]


def spots(rgb, rng, i, scale):
    """Apply seeded pale rings, diffuse pools and dark round marks."""
    h, w = rgb.shape[:2]
    y, x = np.ogrid[:h, :w]
    for j in range((2, 4, 1, 3, 5)[i % 5]):
        cx = float(rng.uniform(.012, .085) * w) if j < 2 else float(rng.uniform(.18, .93) * w)
        cy = float(rng.uniform(.10, .92) * h)
        r = float(rng.uniform(3.5, 14) if j < 2 else rng.uniform(7, 28)) * scale
        dist = np.sqrt(((x-cx)/r)**2 + ((y-cy)/(r*rng.uniform(.80, 1.13)))**2)
        mode = (i + j) % 4
        if mode == 0:
            density = 14*np.exp(-((dist-.81)/.18)**2) + 5*np.exp(-dist**2)
            tint = np.array([.76, .95, 1.55])
        elif mode == 1:
            density = 12*np.exp(-(dist/.82)**2)
            tint = np.array([.82, 1, 1.31])
        elif mode == 2 and j < 2:
            density = 25*np.exp(-(dist/.67)**2) + 8*np.exp(-((dist-1.0)/.26)**2)
            tint = np.ones(3)
        else:
            density = 16*np.exp(-((dist-.57)/.27)**2) + 6*np.exp(-dist**2)
            tint = np.ones(3)
        rgb -= density[..., None] * tint
    return rgb


def render(clean, p, seed, i, role, *, scale=1, warp=None, ink_optics=None):
    rng = np.random.default_rng(seed)
    g = np.asarray(clean.convert("L"), dtype=np.float32) / 255
    h, w = g.shape
    y, x = np.mgrid[:h, :w].astype(np.float32)
    side_dist = w-1-x if p["edge_side"] == "right" else x
    skew_y = (x-w/2) * np.tan(np.deg2rad(p["skew"]))
    bend_y = (w*.12 * np.tan(np.deg2rad(p["gutter_bend_deg"])) *
              np.exp(-side_dist/(w*.12)))
    vertical_offset = skew_y + bend_y
    if warp is not None:
        # Warp uses pixel edges. OpenCV samples at integer pixel centers.
        vertical_offset = -np.interp(np.arange(w) + .5, warp.y_knots, warp.y_offsets)
    g = cv2.remap(g, x, (y + vertical_offset).astype(np.float32), cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_CONSTANT, borderValue=1.)
    # Simulate an effective copy/scan edge spread and a clipped transfer. Only
    # the grayscale ink mask is blurred; paper texture is generated separately.
    paper_normalizer = np.percentile(g, 95)
    g = np.clip((g - .12)/max(paper_normalizer - .12, 1e-6), 0, 1)
    if role == "copy":
        # Toner spread keeps the thinnest authored font strokes from washing out.
        weight = .24 + .13 * p["knee"]
        g = (1-weight)*g + weight*cv2.erode(g, cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)))
    blur = p["blur"] * scale
    if ink_optics is not None:
        if ink_optics.stroke_trim:
            g = 1 - trim_ink_edge(1 - g, ink_optics.stroke_trim)
        blur *= ink_optics.blur_scale
    g = cv2.GaussianBlur(g, (0, 0), blur)
    low = p["knee"]*.63
    high = 1-p["knee"]*.33
    t = np.clip((g-low)/(high-low), 0, 1)
    paper = np.array(p["paper_rgb"])
    rgb = p["ink"] + t[..., None]*(paper-p["ink"])
    if ink_optics is not None and ink_optics.halo_gain:
        # Add the ink-only delta. Preserve the base optical field used by
        # stains, speckles and the rest of the acquisition simulation.
        opacity = 1 - t
        rgb -= (_adjust_halo(opacity, ink_optics.halo_gain, scale) - opacity)[..., None] * (paper-p["ink"])
    thin = smooth_vector(rng.normal(size=h), 1.7 * scale)
    broad = smooth_vector(rng.normal(size=h), 8. * scale)
    stripes = .68*thin/max(.03, float(thin.std())) + .32*broad/max(.03, float(broad.std()))
    rgb += stripes[:, None, None] * p["band_sd"]
    # Soft lid/gutter falloff with a narrow contact fringe where measured.
    width = p["edge_width"] * scale * (1+.13*np.sin((y/h)*np.pi*.91))
    edge = .76*np.exp(-side_dist/np.maximum(2 * scale, width))*p["edge_drop"]
    edge += .24*p["edge_drop"]*np.clip((width*.20-side_dist)/(2 * scale),0,1)
    rgb -= edge[..., None]
    field = cv2.resize(rng.normal(0, .55, (9, 7)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    rgb += .55*field[..., None] + rng.normal(0, .45 if role == "copy" else .40, (h, w, 1))
    mask = np.zeros((h, w), np.float32)
    for _ in range(round(h*w*p["specks_per_mpx"]/(1e6 * scale**2))):
        xx = int(rng.integers(w))
        yy = int(rng.integers(h))
        cv2.circle(mask, (xx, yy), max(1, round(p["speck_radius"] * scale * rng.uniform(.62, 1.65))),
                   float(rng.uniform(13, 60)), -1)
    rgb -= (cv2.GaussianBlur(mask, (0, 0), .40 * scale)*(t**2))[..., None]
    rgb = spots(rgb, rng, i, scale)
    punches = np.zeros((h, w), np.float32)
    for cx, cy, rx, ry in p["margin_punches"]:
        cv2.ellipse(punches, (round(cx*w), round(cy*h)), (round(rx), round(ry)),
                    0, 0, 360, float(rng.uniform(165, 203)), -1)
    rgb -= cv2.GaussianBlur(punches, (0, 0), .59)[..., None]
    return Image.fromarray(np.rint(np.clip(rgb, 0, 255)).astype(np.uint8))
