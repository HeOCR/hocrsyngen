"""Compose seeded TRAIN phone fits and parameterized scanner degradations."""

import math
from hashlib import sha256

import numpy as np
from PIL import ImageChops

from .degradations import recompress, scanner_edge_bars, show_through
from .dev_profiles import validate_profile
from .geometry import corners
from .phone_training import PhoneView, render_fitted_phone_view, render_phone_view
from .pipeline import _rng


def _range(bounds, name, low, high, *, integer=False):
    types = (int,) if integer else (int, float)
    if (not isinstance(bounds, (tuple, list)) or len(bounds) != 2
            or any(type(value) not in types
                   or not math.isfinite(value) for value in bounds)
            or not low <= bounds[0] <= bounds[1] <= high):
        raise ValueError(f"Invalid {name} range")


def _seed(seed, stage):
    return int(_rng(seed, f"real_capture/{stage}").integers(0, 2**63))


def _scanner_view(image, lines, profile, seed, long_edge, rotation, perspective):
    _range(rotation, "scanner rotation", -10, 10)
    _range(perspective, "scanner perspective", 0, 0.04)
    width, height = image.size
    scale = long_edge / max(image.size)
    size = round(width * scale), round(height * scale)
    if min(size) < 128:
        raise ValueError("The scanner short edge must be at least 128 pixels")
    rng = _rng(seed, "real_capture/scanner_pose")
    turn = float(rng.uniform(*rotation))
    pitch = float(rng.uniform(*perspective))
    radians = math.radians(turn)
    c, s = math.cos(radians), math.sin(radians)
    frame = np.asarray(size)
    offset = np.asarray(corners(size)) - 0.5 * frame
    rotated = offset @ np.array([[c, s], [-s, c]])
    warped = rotated + rng.uniform(-pitch, pitch, size=(4, 2)) * frame
    # Fit the entire paper into the image while preserving its projective shape.
    margin = max(1.0, float(np.max(np.abs(warped) / (0.485 * frame))))
    quad = 0.5 + warped / (margin * frame)
    result = render_phone_view(
        image, lines, profile, seed=seed, size=size, quad=quad.tolist(),
        native_long_edge=long_edge,
    )
    return result, {"rotation_deg": turn, "perspective_fraction": pitch, "frame_scale": 1 / margin}


def _bands(image, lines, seed, options):
    with_bands = scanner_edge_bars(image, seed, **options)
    delta = ImageChops.difference(image, with_bands)
    for line in lines:
        x0, y0, x1, y1 = line["box"]
        if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
            raise ValueError("A line box falls outside the source raster")
        box = math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)
        if delta.crop(box).getbbox() is not None:
            raise ValueError("Scanner band intersects a source line")
    return with_bands


def _jpeg(image, seed, quality):
    _range(quality, "JPEG quality", 1, 100, integer=True)
    q = int(np.random.default_rng(seed).integers(quality[0], quality[1] + 1))
    edge = max(image.size)
    return recompress(image, seed, long_edge=(edge, edge), quality=(q, q)), q


def render_real_capture(
    image, lines, profile, *, seed, long_edge=1800, phone_bank=None,
    reverse=None, duplex=None, scanner_bands=None, scanner_rotation_deg=(0, 0),
    scanner_perspective=(0, 0), scanner_jpeg_quality=None, recompression_quality=None,
):
    """Return a raster, mapped literal annotations and realized capture parameters.

    Input boxes use upright source pixel edges. Supply an admitted TRAIN phone
    bank and optics profile together. A scanner uses a separate `adobe_scan`
    profile. Optional reverse ink and scanner bands share the paper projection.
    Codec stages operate on the final dimensions.
    """
    validate_profile(profile)
    if type(seed) is not int or seed < 0 or type(long_edge) is not int or not 320 <= long_edge <= 6000:
        raise ValueError("Expected a nonnegative seed and a long edge from 320 to 6000")
    if image.getexif().get(274, 1) != 1:
        raise ValueError("Orient the front raster and annotations before rendering")
    if profile["status"] == "dev_fit":
        raise ValueError("A DEV-fitted profile cannot supply TRAIN capture parameters")
    for field in ("show_through_opacity", "scanner_edge_fraction", "scanner_bar_fraction", "scanner_bars"):
        if any(profile["ranges"][field]):
            raise ValueError("Pass duplex and scanner bands as distinct capture stages")
    lines = tuple(lines)
    if not lines:
        raise ValueError("Supply at least one source line")

    paper = image.convert("RGB")
    stages = {}
    if (reverse is None) != (duplex is None):
        raise ValueError("Supply a registered reverse and duplex parameters together")
    if reverse is not None:
        if reverse.size != image.size or reverse.getexif().get(274, 1) != 1:
            raise ValueError("Register the upright reverse to the front dimensions")
        stage = _seed(seed, "duplex")
        paper = show_through(paper, reverse, stage, **duplex)
        stages["duplex"] = {
            "seed": stage, "parameters": duplex,
            "reverse_rgb_sha256": sha256(reverse.convert("RGB").tobytes()).hexdigest(),
        }

    if phone_bank is not None:
        if (profile["status"] != "train_fit" or phone_bank.get("fit_split") != "train"
                or profile["name"] not in {"phone_flat", "phone_oblique"}):
            raise ValueError("Phone geometry and optics require a matching TRAIN fit")
        if (scanner_bands is not None or scanner_jpeg_quality is not None
                or tuple(scanner_rotation_deg) != (0, 0)
                or tuple(scanner_perspective) != (0, 0)):
            raise ValueError("Scanner stages require a scanner profile")
        view = render_fitted_phone_view(paper, lines, profile, phone_bank, seed=seed, long_edge=long_edge)
    else:
        if profile["name"] != "adobe_scan":
            raise ValueError("A phone profile requires its TRAIN geometry bank")
        if scanner_bands is not None:
            stage = _seed(seed, "scanner_bands")
            paper = _bands(paper, lines, stage, scanner_bands)
            stages["scanner_bands"] = {"seed": stage, "parameters": scanner_bands}
        view, pose = _scanner_view(
            paper, lines, profile, seed, long_edge, scanner_rotation_deg, scanner_perspective,
        )
        stages["scanner_pose"] = pose

    result = view.image
    encoded = view.parameters["optics_and_tone"]["jpeg"] is not None
    if scanner_jpeg_quality is not None:
        if encoded:
            raise ValueError("The scanner profile already defines its initial JPEG encoder")
        stage = _seed(seed, "scanner_jpeg")
        result, quality = _jpeg(result, stage, scanner_jpeg_quality)
        stages["scanner_jpeg"] = {"seed": stage, "quality": quality}
        encoded = True
    if recompression_quality is not None:
        if not encoded:
            raise ValueError("Recompression requires an initial JPEG encode")
        stage = _seed(seed, "recompression")
        result, quality = _jpeg(result, stage, recompression_quality)
        stages["recompression"] = {"seed": stage, "quality": quality}
    return PhoneView(result, view.lines, view.warp, view.parameters | {"real_capture_stages": stages})
