"""Seeded phone views and label-preserving crops for annotated training pages."""

import io
import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .dev_profiles import RANGE_BOUNDS, _render, sample_profile
from .geometry import Warp, corners, transform_annotation
from .pipeline import _rng, _scene, linear_to_srgb


@dataclass(frozen=True)
class PhoneView:
    image: Image.Image
    lines: tuple[dict, ...]
    warp: Warp
    parameters: dict


def _finite(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def phone_warp(source_size, *, size, quad, curl=0, fold=None, preserve_frame=False):
    """Build a normalized camera projection with vertical page displacement.

    The signed curl is a fraction of source height. A fold adds a local
    piecewise-linear crease centered at its normalized x coordinate.
    """
    width, height = source_size
    target = np.asarray(quad, dtype=np.float32)
    low, high = (-1.0, 2.0) if preserve_frame else (0.01, 0.99)
    if (
        target.shape != (4, 2)
        or not np.isfinite(target).all()
        or not np.all((low <= target) & (target <= high))
        or not cv2.isContourConvex(target)
        or cv2.contourArea(target, oriented=True) < 0.15
        or not _finite(curl, -0.04, 0.04)
        or len(size) != 2
        or not all(type(value) is int and 128 <= value <= 6000 for value in size)
    ):
        raise ValueError("Invalid normalized phone geometry")
    if preserve_frame:
        visible, _ = cv2.intersectConvexConvex(target, np.float32(corners((1, 1))))
        if visible < 0.15:
            raise ValueError(
                "Observed phone geometry leaves too little of the page visible"
            )
    t = np.linspace(0, 1, 33)
    if fold is not None:
        center, span, amplitude = fold
        if (
            not _finite(center, 0.15, 0.85)
            or not _finite(span, 0.02, 0.15)
            or not _finite(amplitude, -0.03, 0.03)
        ):
            raise ValueError("Invalid phone fold")
        t = np.unique(np.r_[t, center - span, center, center + span])
    rise = curl * (4 * (t - 0.5) ** 2 - 0.5)
    if fold is not None:
        rise += amplitude * np.maximum(0, 1 - np.abs(t - center) / span)
    camera = cv2.getPerspectiveTransform(
        np.float32(corners(source_size)),
        target * np.float32(size),
    )
    return Warp(
        np.eye(3),
        np.array([0, height]),
        np.zeros(2),
        t * width,
        rise * height,
        camera,
        tuple(size),
    )


def _shade(image, shadow, fold):
    """Apply a soft local shadow and shading on either side of a crease."""
    if shadow is None and fold is None:
        return image
    width, height = image.size
    y, x = np.ogrid[:height, :width]
    x, y = (x + 0.5) / width, (y + 0.5) / height
    gain = np.ones((height, width), dtype=np.float32)
    if shadow is not None:
        cx, cy, sx, sy, depth = shadow
        if (
            not _finite(cx, 0, 1)
            or not _finite(cy, 0, 1)
            or not _finite(sx, 0.06, 0.65)
            or not _finite(sy, 0.06, 0.65)
            or not _finite(depth, 0, 0.45)
        ):
            raise ValueError("Invalid phone shadow")
        gain *= 1 - depth * np.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))
    if fold is not None:
        center, span, amplitude = fold
        relative = (x - center) / (0.24 * span)
        gain *= 1 + (5 * amplitude) * relative * np.exp(-0.5 * relative**2)
    return Image.fromarray(
        np.clip(np.asarray(image) * gain[..., None] + 0.5, 0, 255).astype(np.uint8)
    )


def phone_annotations(lines, warp, source_size):
    """Map each line and record its minimum projected sampling height."""
    annotations = []
    for line in lines:
        x1, y1, x2, y2 = line["box"]
        if not (0 <= x1 < x2 <= source_size[0] and 0 <= y1 < y2 <= source_size[1]):
            raise ValueError("Invalid source line box")
        transformed = transform_annotation(line, warp)
        baseline = line.get("baseline", ((x1, y2), (x2, y2)))
        ends = sorted((baseline[0], baseline[-1]), key=lambda point: point[0])
        chord = warp.forward(ends)
        dx, dy = chord[1] - chord[0]
        length = math.hypot(dx, dy)
        if not length:
            raise ValueError("Degenerate phone line baseline")
        xs = np.r_[x1, warp.y_knots[(x1 < warp.y_knots) & (warp.y_knots < x2)], x2]
        top = warp.forward(np.column_stack((xs, np.full(len(xs), y1))))
        bottom = warp.forward(np.column_stack((xs, np.full(len(xs), y2))))
        height = np.min((bottom - top) @ (np.array([-dy, dx]) / length))
        annotations.append(
            transformed
            | {"crop_chord": chord.tolist(), "min_local_height": float(height)}
        )
    return tuple(annotations)


def render_phone_view(
    image,
    lines,
    profile,
    *,
    seed,
    size,
    quad,
    native_long_edge,
    curl=0,
    fold=None,
    shadow=None,
    sharpen=0,
    preserve_frame=False,
    frame_light=None,
):
    """Use the same geometry for pixels, polygons, and baselines.

    Supply an upright page and annotations in its pixel-edge coordinates.
    The profile supplies paper, gradient, effective optics, noise and JPEG.
    """
    if image.getexif().get(274, 1) != 1:
        raise ValueError(
            "Orient the source raster and annotations before generating phone views"
        )
    if (
        profile.get("name") not in ("phone_flat", "phone_oblique", "adobe_scan")
        or not _finite(native_long_edge, 128, 12000)
        or not _finite(sharpen, 0, 0.5)
    ):
        raise ValueError("Invalid phone endpoint, optical scale or sharpening")
    warp = phone_warp(
        image.size,
        size=size,
        quad=quad,
        curl=curl,
        fold=fold,
        preserve_frame=preserve_frame,
    )
    source = _shade(image.convert("RGB"), shadow, fold)
    surface = {
        "rgb": (255, 255, 255) if profile["name"] == "adobe_scan" else (107, 105, 102),
        "texture": 0,
    }
    rgb = _scene(
        np.asarray(source), warp, surface, _rng(seed, "phone_training/surface")
    )
    raster = Image.fromarray(np.uint8(np.clip(linear_to_srgb(rgb) * 255 + 0.5, 0, 255)))
    parameters = sample_profile(profile, seed)
    if frame_light is not None:
        keys = {"paper_r", "paper_g", "paper_b", "gradient_x", "gradient_y"}
        if (
            not isinstance(frame_light, dict)
            or set(frame_light) != keys
            or any(not _finite(frame_light[key], *RANGE_BOUNDS[key]) for key in keys)
        ):
            raise ValueError("Invalid observed frame illumination")
        parameters.update(frame_light)
    scale = max(size) / native_long_edge
    for key in ("blur_sigma", "defocus_add", "motion_px"):
        parameters[key] *= scale
    parameters.update(sharpen_amount=sharpen, sharpen_sigma=max(0.45, 0.85 * scale))
    result = _render(raster, parameters, seed, None)
    if isinstance(result, bytes):
        with Image.open(io.BytesIO(result)) as decoded:
            result = decoded.convert("RGB")
    provenance = {
        "seed": seed,
        "profile": profile["name"],
        "profile_status": profile["status"],
        "geometry": warp.record(),
        "size": list(size),
        "native_long_edge": native_long_edge,
        "curl": curl,
        "fold": fold,
        "shadow": shadow,
        "optics_and_tone": parameters,
    }
    return PhoneView(
        result, phone_annotations(lines, warp, image.size), warp, provenance
    )


def render_fitted_phone_view(image, lines, profile, bank, *, seed, long_edge=2250):
    """Draw a complete geometry recipe for the requested fitted endpoint."""
    if (
        bank.get("schema") != "scanifier_phone_bank.v1"
        or profile.get("status") != "dev_fit"
    ):
        raise ValueError(
            "A non-test geometry bank and fitted optical profile are required"
        )
    geometries = bank["profiles"][profile["name"]]
    framing = bank.get("framing", "reframed")
    if framing not in ("reframed", "observed"):
        raise ValueError("Unknown fitted phone framing")
    if not geometries or type(seed) is not int or seed < 0:
        raise ValueError("Expected nonempty fitted geometry and a nonnegative seed")
    row = geometries[
        int(_rng(seed, "phone_training/geometry").integers(len(geometries)))
    ]
    aspect = row["frame_ratio"]
    if (
        not _finite(aspect, 0.4, 2.5)
        or type(long_edge) is not int
        or not 320 <= long_edge <= 6000
    ):
        raise ValueError("Invalid fitted frame dimensions")
    size = (
        (long_edge, round(long_edge / aspect))
        if aspect >= 1
        else (round(long_edge * aspect), long_edge)
    )
    view = render_phone_view(
        image,
        lines,
        profile,
        seed=seed,
        size=size,
        quad=row["quad"],
        native_long_edge=row["native_long_edge"],
        curl=row["curl"],
        shadow=row["shadow"],
        preserve_frame=framing == "observed",
        frame_light=row.get("frame_light") if framing == "observed" else None,
    )
    return PhoneView(
        view.image,
        view.lines,
        view.warp,
        view.parameters | {"fit_capture_sha256": row["capture_sha256"]},
    )


def phone_line_crop(view, index, *, padding=2, minimum_height=11):
    """Deskew the line chord and preserve its curvature and local scale.

    Return an image and no reason, or no image and a rejection reason.
    A crop must fit inside the frame and exclude neighboring line ink boxes.
    """
    line = view.lines[index]
    if (
        type(padding) is not int
        or padding < 0
        or type(minimum_height) is not int
        or minimum_height < 1
    ):
        raise ValueError("Invalid line crop limits")
    if line["min_local_height"] < minimum_height:
        return None, "underresolved"
    first, last = np.asarray(line["crop_chord"])
    dx, dy = last - first
    angle = math.degrees(math.atan2(dy, dx))
    rotation = cv2.getRotationMatrix2D(tuple(first), angle, 1)
    polygon = np.asarray(line["box_polygon"])
    straight = polygon @ rotation[:, :2].T + rotation[:, 2]
    left, top = np.floor(straight.min(axis=0)).astype(int) - padding
    right, bottom = np.ceil(straight.max(axis=0)).astype(int) + padding
    rect = np.float32([(left, top), (right, top), (right, bottom), (left, bottom)])
    inverse = cv2.invertAffineTransform(rotation)
    footprint = rect @ inverse[:, :2].T + inverse[:, 2]
    if np.any(footprint < 0) or np.any(footprint > view.image.size):
        return None, "clipped"
    low, high = footprint.min(axis=0), footprint.max(axis=0)
    for other_index, other in enumerate(view.lines):
        if other_index == index:
            continue
        x1, y1, x2, y2 = other["box"]
        if x2 <= low[0] or y2 <= low[1] or x1 >= high[0] or y1 >= high[1]:
            continue
        hull = cv2.convexHull(np.asarray(other["box_polygon"], dtype=np.float32))
        area, _ = cv2.intersectConvexConvex(footprint.astype(np.float32), hull)
        if area > 1:
            return None, "neighbor_overlap"
    rotation[:, 2] += rotation[:, :2] @ np.array([0.5, 0.5]) - (left + 0.5, top + 0.5)
    raster = view.image.convert("L") if view.image.mode == "1" else view.image
    crop = cv2.warpAffine(
        np.asarray(raster),
        rotation,
        (right - left, bottom - top),
        flags=cv2.INTER_CUBIC,
        borderValue=(255, 255, 255),
    )
    return Image.fromarray(crop), None
