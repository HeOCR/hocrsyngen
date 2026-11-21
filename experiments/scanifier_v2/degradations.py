"""Independently seeded, opt-in raster effects for training/calibration pages.

Ranges are inclusive bounds sampled uniformly; defaults are engineering priors,
not estimates of any held-out capture distribution. Each function returns RGB.
"""
import io
import math

import cv2
import numpy as np
from PIL import Image, ImageOps

from .pipeline import _rng


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


def show_through(image, reverse, seed, opacity=(0.025, 0.12), blur_px=(0.3, 1.2),
                 offset_fraction=(-0.025, 0.025), *, transmission_variation=0.0):
    """Overlay mirrored reverse-page ink. Reverse must be a permitted training/dev image."""
    rng = np.random.default_rng(seed)
    alpha = _sample(rng, opacity, 'opacity', 0, 1)
    blur = _sample(rng, blur_px, 'blur_px', 0, 64)
    _range(offset_fraction, 'offset_fraction', -1, 1)
    _range((transmission_variation, transmission_variation), 'transmission_variation', 0, 1)
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
    rounding = 0
    if transmission_variation:
        rng = _rng(seed, 'show_through/transmission')
        knots = rng.uniform(-1, 1, (5, 5)).astype(np.float32)
        field = cv2.resize(knots, image.size, interpolation=cv2.INTER_LINEAR)
        alpha = np.clip(alpha * (1 + transmission_variation * field), 0, 1)
        rounding = 0.5
    gain = 1 - alpha * ink
    return Image.fromarray(np.uint8(np.clip(page * gain[..., None] + rounding, 0, 255)))


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


def soft_scanner_edge(image, seed, *, side, width_fraction, darkness, feather_px,
                      text_box, taper=0.0):
    """Render a soft gutter or platen mark confined to the margin outside text_box."""
    if side not in ('left', 'right', 'top', 'bottom'):
        raise ValueError('unknown scanner edge side')
    _range((width_fraction, width_fraction), 'width_fraction', 0, 0.25)
    _range((darkness, darkness), 'darkness', 0, 1)
    _range((feather_px, feather_px), 'feather_px', 0.25, 32)
    _range((taper, taper), 'taper', -0.25, 0.25)
    left, top, right, bottom = text_box
    width, height = image.size
    if (any(type(coord) is not int for coord in text_box)
            or not (0 <= left < right <= width and 0 <= top < bottom <= height)):
        raise ValueError('expected an in-frame integer text box')
    margin = {'left': left, 'top': top, 'right': width - right, 'bottom': height - bottom}[side]
    result = np.array(image.convert('RGB'))
    if width_fraction == 0 or margin == 0 or darkness == 0:
        return Image.fromarray(result)
    strip = result.swapaxes(0, 1) if side in ('top', 'bottom') else result
    if side in ('right', 'bottom'):
        strip = strip[:, ::-1]
    length, across = strip.shape[:2]
    scale = 2
    positions = (np.arange(length * scale, dtype=np.float32) + 0.5) / (length * scale)
    rng = _rng(seed, 'soft_scanner_edge')
    ripple = np.interp(positions, np.linspace(0, 1, 7), rng.uniform(-0.12, 0.12, 7))
    edge = np.clip(across * (width_fraction * (1 + ripple) + taper * (positions - 0.5)), 0, margin)
    depth = min(margin, math.ceil(edge.max() + feather_px))
    sample_x = (np.arange(depth * scale, dtype=np.float32) + 0.5) / scale
    # A supersampled smoothstep covers partial pixels without drawing a hard band.
    cover = np.clip((edge[:, None] - sample_x) / feather_px + 0.5, 0, 1)
    cover[edge == 0] = 0
    cover *= cover * (3 - 2 * cover)
    cover = cover.reshape(length, scale, depth, scale).mean(axis=(1, 3))
    strip[:, :depth] = np.uint8(np.rint(strip[:, :depth] * (1 - darkness * cover[..., None])))
    return Image.fromarray(result)


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
