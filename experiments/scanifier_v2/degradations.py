"""Independently seeded, opt-in raster effects for training/calibration pages.

Ranges are inclusive bounds sampled uniformly; defaults are engineering priors,
not estimates of any held-out capture distribution. Each function returns RGB.
"""
import io
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps


def _range(value, name, low, high):
    if (not isinstance(value, (tuple, list)) or len(value) != 2
            or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value)
            or not low <= value[0] <= value[1] <= high):
        raise ValueError(f"invalid {name} range: {value!r}")
    return value


def _sample(rng, value, name, low, high):
    return float(rng.uniform(*_range(value, name, low, high)))


def paper_tint(image, seed, strength=(0.03, 0.16), color=(238, 225, 198)):
    """Multiply paper brightness by a sampled tint; strength is 0–1."""
    rng = np.random.default_rng(seed)
    amount = _sample(rng, strength, 'strength', 0, 1)
    if len(color) != 3 or any(not isinstance(x, int) or not 0 <= x <= 255 for x in color):
        raise ValueError('color must be three integer sRGB values')
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32)
    return Image.fromarray(np.uint8(np.clip(rgb * (1 - amount * (1 - np.array(color) / 255)), 0, 255)))


def show_through(image, reverse, seed, opacity=(0.025, 0.12), blur_px=(0.3, 1.2), offset_fraction=(-0.025, 0.025)):
    """Overlay mirrored reverse-page ink. Reverse must be a permitted training/dev image."""
    rng = np.random.default_rng(seed)
    alpha = _sample(rng, opacity, 'opacity', 0, 1)
    blur = _sample(rng, blur_px, 'blur_px', 0, 20)
    _range(offset_fraction, 'offset_fraction', -1, 1)
    page = np.asarray(image.convert('RGB'), dtype=np.float32)
    # White is transparent, darker reverse pixels contribute more ink. Mirroring
    # is performed here so callers supply the reverse in its normal reading view.
    back = ImageOps.mirror(reverse.convert('L')).resize(image.size, Image.Resampling.LANCZOS)
    ink = 1 - np.asarray(back, dtype=np.float32) / 255
    if blur > 0.01:
        ink = cv2.GaussianBlur(ink, (0, 0), blur)
    dx = rng.uniform(*offset_fraction) * image.width
    dy = rng.uniform(*offset_fraction) * image.height
    ink = cv2.warpAffine(ink, np.float32([[1, 0, dx], [0, 1, dy]]), image.size,
                         flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return Image.fromarray(np.uint8(np.clip(page * (1 - alpha * ink[..., None]), 0, 255)))


def scanner_artifacts(image, seed, edge_fraction=(0.005, 0.04), bar_fraction=(0.002, 0.015), bars=(0, 3), darkness=(0.75, 1.0)):
    """Add a dark scanner edge and zero or more full-length vertical bars."""
    rng = np.random.default_rng(seed)
    edge = _sample(rng, edge_fraction, 'edge_fraction', 0, 0.5)
    width = _sample(rng, bar_fraction, 'bar_fraction', 0, 0.5)
    dark = _sample(rng, darkness, 'darkness', 0, 1)
    _range(bars, 'bars', 0, 100)
    if any(type(x) is not int for x in bars):
        raise ValueError('bars must have integer endpoints')
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32).copy()
    h, w = rgb.shape[:2]
    n = round(edge * w)
    if n:
        if rng.integers(2):
            rgb[:, :n] *= 1 - dark
        else:
            rgb[:, w-n:] *= 1 - dark
    for _ in range(int(rng.integers(bars[0], bars[1] + 1))):
        x = int(rng.integers(w))
        rgb[:, x:min(w, x + max(1, round(width * w)))] *= 1 - dark
    return Image.fromarray(np.uint8(np.clip(rgb, 0, 255)))


def thumb_occlusion(image, seed, size_fraction=(0.06, 0.15), color=(181, 130, 105)):
    """Add a simple edge-entering thumb-shaped occluder; it may cover text."""
    rng = np.random.default_rng(seed)
    size = _sample(rng, size_fraction, 'size_fraction', 0, 0.5) * min(image.size)
    if len(color) != 3 or any(type(x) is not int or not 0 <= x <= 255 for x in color):
        raise ValueError('color must be three integer sRGB values')
    output = image.convert('RGB').copy()
    if size == 0:
        return output
    draw = ImageDraw.Draw(output)
    x = rng.uniform(0.15, 0.85) * image.width
    y = 0 if rng.integers(2) == 0 else image.height
    draw.ellipse((x-size, y-size*1.35, x+size, y+size*1.35), fill=color)
    return output


def spatial_noise(image, seed, sigma=(2.0, 12.0), variation=(0.3, 1.0), grid=8):
    """Add spatially varying Gaussian noise; sigma is in 8-bit sRGB levels."""
    rng = np.random.default_rng(seed)
    level = _sample(rng, sigma, 'sigma', 0, 255)
    amount = _sample(rng, variation, 'variation', 0, 1)
    if type(grid) is not int or not 2 <= grid <= 128:
        raise ValueError('grid must be an integer from 2 to 128')
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32)
    field = cv2.resize(rng.uniform(0, 1, (grid, grid)).astype(np.float32), image.size, interpolation=cv2.INTER_LINEAR)
    scale = level * ((1 - amount) + amount * field)
    noise = rng.standard_normal(rgb.shape, dtype=np.float32) * scale[..., None]
    return Image.fromarray(np.uint8(np.clip(rgb + noise, 0, 255)))


def recompress(image, seed, long_edge=(1280, 1280), quality=(70, 90)):
    """Resize down to the sampled long edge and JPEG-recompress; return RGB raster."""
    rng = np.random.default_rng(seed)
    for name, value, low, high in [('long_edge', long_edge, 1, 8192), ('quality', quality, 1, 100)]:
        _range(value, name, low, high)
        if any(type(x) is not int for x in value):
            raise ValueError(f'{name} must have integer endpoints')
    target = int(rng.integers(long_edge[0], long_edge[1] + 1))
    q = int(rng.integers(quality[0], quality[1] + 1))
    result = image.convert('RGB').copy()
    result.thumbnail((target, target), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    result.save(buffer, format='JPEG', quality=q, subsampling=2)
    buffer.seek(0)
    with Image.open(buffer) as decoded:
        return decoded.convert('RGB')


def motion_blur(image, seed, length_px=(1.4, 8.0), angle_deg=(0, 180)):
    """Apply a sampled linear motion blur in pixel units."""
    from .pipeline import _optics
    rng = np.random.default_rng(seed)
    length = _sample(rng, length_px, 'length_px', 0, 100)
    angle = _sample(rng, angle_deg, 'angle_deg', -360, 360)
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32) / 255
    result = _optics(rgb, {'defocus_sigma_px': 0, 'defocus_gradient_px': 0,
                           'motion_length_px': length, 'motion_angle_deg': angle})
    return Image.fromarray(np.uint8(np.clip(result * 255 + 0.5, 0, 255)))


def edge_defocus(image, seed, sigma_px=(0.5, 2.5), onset=(0.3, 0.7)):
    """Blend defocus toward frame edges; onset is a fraction of centre-to-corner distance."""
    rng = np.random.default_rng(seed)
    sigma = _sample(rng, sigma_px, 'sigma_px', 0, 20)
    start = _sample(rng, onset, 'onset', 0, 0.99)
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32)
    if sigma <= 0.01:
        return image.convert('RGB').copy()
    blurred = cv2.GaussianBlur(rgb, (0, 0), sigma)
    y, x = np.ogrid[-1:1:complex(image.height), -1:1:complex(image.width)]
    radius = np.sqrt((x*x + y*y) / 2)
    weight = np.clip((radius - start) / (1 - start), 0, 1)[..., None]
    return Image.fromarray(np.uint8(np.clip(rgb * (1 - weight) + blurred * weight + 0.5, 0, 255)))


def rotated_save(image, seed, turns=(0, 1, 2, 3)):
    """Bake a sampled counter-clockwise quarter turn into the raster, without EXIF."""
    if not turns or any(type(x) is not int or x not in (0, 1, 2, 3) for x in turns):
        raise ValueError('turns must contain quarter turns 0, 1, 2 or 3')
    turn = int(np.random.default_rng(seed).choice(turns))
    result = image.convert('RGB').rotate(90 * turn, expand=True)
    result.info.clear()
    return result


def scanner_edge_bars(
    image,
    seed,
    *,
    edge_sides=("left", "right", "top", "bottom"),
    edge_fraction=(0.005, 0.04),
    edge_taper=(-0.006, 0.006),
    edge_darkness=(0.78, 1.0),
    bar_axes=("vertical", "horizontal"),
    bar_count=(0, 2),
    bar_fraction=(0.002, 0.015),
    bar_span=(0.60, 1.0),
    bar_darkness=(0.75, 1.0),
    feather_px=(0, 1),
):
    """Darken edge bands and interior bars without moving source pixels.

    Fractions scale along the affected axis. Edge taper is the signed
    end-to-end change in width as a fraction of the perpendicular dimension.
    An empty side/axis list disables that component. Defaults are priors.
    """
    if any(side not in ("left", "right", "top", "bottom") for side in edge_sides):
        raise ValueError("edge_sides must contain only left, right, top or bottom")
    if any(axis not in ("vertical", "horizontal") for axis in bar_axes):
        raise ValueError("bar_axes must contain only vertical or horizontal")
    _range(bar_count, "bar_count", 0, 32)
    if any(type(count) is not int for count in bar_count):
        raise ValueError("bar_count must have integer endpoints")
    _range(bar_fraction, "bar_fraction", 0, 0.5)
    _range(bar_span, "bar_span", 0, 1)
    _range(bar_darkness, "bar_darkness", 0, 1)
    edge_seed, bar_seed, feather_seed = np.random.SeedSequence(seed).spawn(3)
    edge_rng, bar_rng = np.random.default_rng(edge_seed), np.random.default_rng(bar_seed)
    feather = _sample(np.random.default_rng(feather_seed), feather_px, "feather_px", 0, 20)
    width = _sample(edge_rng, edge_fraction, "edge_fraction", 0, 0.5)
    taper = _sample(edge_rng, edge_taper, "edge_taper", -0.5, 0.5)
    darkness = _sample(edge_rng, edge_darkness, "edge_darkness", 0, 1)
    rgb = np.array(image.convert("RGB"), dtype=np.float32)

    def coverage(distance):
        # A one-pixel transition at zero feather integrates the hard
        # boundary across the pixel instead of rounding away narrow bars.
        return np.clip(0.5 + distance / (1 + feather), 0, 1)

    if edge_sides and width > 0 and darkness > 0:
        side = edge_rng.choice(edge_sides)
        view = rgb if side in ("left", "right") else rgb.transpose(1, 0, 2)
        if side in ("right", "bottom"):
            view = view[:, ::-1]
        major, minor = view.shape[:2]
        station = (np.arange(major, dtype=np.float32) + 0.5) / major - 0.5
        band_width = np.clip(width + taper * station, 0, 0.5) * minor
        extent = min(minor, math.ceil(float(band_width.max()) + feather + 1))
        cross = np.arange(extent, dtype=np.float32) + 0.5
        mask = coverage(band_width[:, None] - cross[None, :])
        view[:, :extent] *= 1 - darkness * mask[..., None]

    count = int(bar_rng.integers(bar_count[0], bar_count[1] + 1))
    for _ in range(count if bar_axes else 0):
        axis = bar_rng.choice(bar_axes)
        width = _sample(bar_rng, bar_fraction, "bar_fraction", 0, 0.5)
        span = _sample(bar_rng, bar_span, "bar_span", 0, 1)
        darkness = _sample(bar_rng, bar_darkness, "bar_darkness", 0, 1)
        across, along = bar_rng.random(2)
        if width == 0 or span == 0 or darkness == 0:
            continue
        view = rgb if axis == "vertical" else rgb.transpose(1, 0, 2)
        major, minor = view.shape[:2]
        left = across * (1 - width) * minor
        top = along * (1 - span) * major
        right, bottom = left + width * minor, top + span * major
        x0, x1 = max(0, math.floor(left - feather)), min(minor, math.ceil(right + feather))
        y0, y1 = max(0, math.floor(top - feather)), min(major, math.ceil(bottom + feather))
        x = np.arange(x0, x1, dtype=np.float32) + 0.5
        y = np.arange(y0, y1, dtype=np.float32) + 0.5
        mask = coverage(np.minimum(x - left, right - x))[None, :] * coverage(np.minimum(y - top, bottom - y))[:, None]
        view[y0:y1, x0:x1] *= 1 - darkness * mask[..., None]

    return Image.fromarray(np.uint8(np.clip(rgb + 0.5, 0, 255)))
