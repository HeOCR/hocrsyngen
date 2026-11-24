"""Source-scale variation for scanned glyph instances in the S16 printed pilot."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot, radians
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


RECIPE = "s16-printed-glyph-variance-v1"


@dataclass(frozen=True)
class GlyphVariant:
    opacity: np.ndarray
    pad: int
    scale: float
    rotation_degrees: float
    warp_x_px: float
    warp_y_px: float
    stroke_delta_px: float
    ink_scale: float
    attempt: int
    raster_sha256: str


def _smooth_edges(opacity, ndimage):
    ink = opacity >= 0.5
    has_ink = ndimage.maximum_filter(ink, size=3)
    all_ink = ndimage.minimum_filter(ink, size=3)
    blend = (has_ink & ~all_ink) & (opacity < 0.8)
    soft = ndimage.gaussian_filter(opacity, sigma=0.48)
    return opacity + 0.22 * blend * (soft - opacity)


def vary_glyph(
    opacity: np.ndarray,
    *,
    seed: int,
    index: int,
    seen: set[str],
    ink_range: float = 255.0,
) -> GlyphVariant:
    """Vary one gray-first glyph without moving its typographic origin.

    Use ``pad`` to offset its placement in both axes. Share ``seen`` among
    occurrences of the same source glyph within a rendered job. Comparison is
    at the ink contrast of the output to reject visibly identical instances.
    The caller must still run its stroke and exact-transcription gates.
    """
    from hashlib import sha256

    import numpy as np
    from scipy import ndimage

    alpha = np.asarray(opacity, dtype=np.float32)
    if alpha.ndim != 2 or not np.isfinite(alpha).all() or not ((0 <= alpha) & (alpha <= 1)).all():
        raise ValueError("Expected a finite 2D opacity array in [0, 1]")
    ink_y, ink_x = np.nonzero(alpha >= 0.5)
    if not ink_y.size or not 0 < ink_range <= 255:
        raise ValueError("Expected visible source ink and positive output contrast")

    pad = ceil(0.025 * hypot(*alpha.shape)) + 3
    canvas = np.pad(alpha, pad)
    center_y = (ink_y.min() + ink_y.max()) / 2 + pad
    center_x = (ink_x.min() + ink_x.max()) / 2 + pad
    yy, xx = np.indices(canvas.shape, dtype=np.float32)
    dy, dx = yy - center_y, xx - center_x
    wave_y = np.pi * dy / max(8, 1 + np.ptp(ink_y))
    wave_x = np.pi * dx / max(8, 1 + np.ptp(ink_x))
    rng = np.random.default_rng(np.random.SeedSequence([seed, index, 0x533136]))
    original = sha256(np.rint(canvas * ink_range).astype(np.uint8).tobytes()).hexdigest()
    cross = ndimage.generate_binary_structure(2, 1)

    for attempt in range(8):
        scale = float(rng.uniform(0.978, 1.022))
        angle = float(rng.uniform(-1.4, 1.4))
        warp_x, warp_y = map(float, rng.uniform(-0.42, 0.42, size=2))
        phase_x, phase_y = rng.uniform(0, 2 * np.pi, size=2)
        stroke = float(rng.uniform(-1.0, 1.0))
        ink_scale = float(rng.uniform(0.95, 1.05))
        sine, cosine = np.sin(radians(angle)) / scale, np.cos(radians(angle)) / scale
        sample_y = center_y + cosine * dy - sine * dx + warp_y * np.sin(wave_x + phase_y)
        sample_x = center_x + sine * dy + cosine * dx + warp_x * np.sin(wave_y + phase_x)
        warped = np.clip(ndimage.map_coordinates(canvas, [sample_y, sample_x], order=3), 0, 1)

        # One pixel is the total thickness budget: split it between both sides.
        ink = warped >= 0.5
        edge = ndimage.maximum_filter(ink, size=3) & ~ndimage.minimum_filter(ink, size=3)
        shape = ndimage.maximum_filter if stroke > 0 else ndimage.minimum_filter
        weighted = warped + (abs(stroke) / 2) * edge * (shape(warped, footprint=cross) - warped)
        varied = np.clip(_smooth_edges(weighted, ndimage) * ink_scale, 0, 1)
        raster = np.rint(varied * ink_range).astype(np.uint8)
        fingerprint = sha256(raster.tobytes()).hexdigest()
        if np.any(varied >= 0.5) and fingerprint != original and fingerprint not in seen:
            seen.add(fingerprint)
            return GlyphVariant(varied, pad, scale, angle, warp_x, warp_y, stroke, ink_scale, attempt, fingerprint)

    raise ValueError("Could not produce a distinct visible variant of the source glyph")
