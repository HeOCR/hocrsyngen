"""Shared raster and label geometry for low-PPI scanner profiles."""

import math

import cv2
import numpy as np
from PIL import Image, ImageOps

from .geometry import Warp, exif_transform, transform_annotation


def checked_annotation(record, warp):
    result = transform_annotation(record, warp)
    left, top, right, bottom = result["box"]
    width, height = warp.size
    if left < 0 or top < 0 or right > width or bottom > height:
        raise ValueError("Scan rotation clips the annotation")
    return result


def _rotation(size, degrees):
    center = np.asarray(size, dtype=float) / 2
    radians = np.deg2rad(degrees)
    c, s = np.cos(radians), np.sin(radians)
    matrix = np.array([[c, -s, 0], [s, c, 0], [0., 0., 1.]])
    matrix[:2, 2] = center - matrix[:2, :2] @ center
    return matrix


def rotate_raster(pixels, rotation, size, background):
    # OpenCV samples at array-index centres. Shift the edge-coordinate affine
    # to those centres so annotations track the same rotation.
    affine = rotation[:2].copy()
    affine[:, 2] += affine[:, :2] @ [0.5, 0.5] - 0.5
    return cv2.warpAffine(pixels, affine, size, flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=background)


def _rgb_on_white(image):
    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image.convert("RGBA"))
    return background.convert("RGB")


def render_low_ppi(image, source_ppi, working_ppi, degrees, rasterize):
    if not math.isfinite(source_ppi) or source_ppi <= 0:
        raise ValueError("source_ppi must be finite and positive")
    if source_ppi < working_ppi:
        raise ValueError("source_ppi must be at least the sampled working PPI")

    orientation = image.getexif().get(274, 1)
    page = ImageOps.exif_transpose(image)
    ratio = working_ppi / source_ppi
    low_size = tuple(max(1, round(edge * ratio)) for edge in page.size)
    if rasterize is None:
        rgb = cv2.resize(np.asarray(_rgb_on_white(page)), low_size, interpolation=cv2.INTER_AREA)
    else:
        native = rasterize(working_ppi)
        if any(abs(expected - actual) > 1 for expected, actual in zip(low_size, native.size)):
            raise ValueError("Direct render size does not match the source page and PPI")
        low_size = native.size
        rgb = np.asarray(_rgb_on_white(native))

    scale = np.diag([low_size[0] / page.width, low_size[1] / page.height, 1.])
    rotation = _rotation(low_size, degrees)
    camera = np.linalg.inv(scale) @ rotation @ scale
    knots = np.array([0., 1.])
    zeros = np.zeros(2)
    warp = Warp(exif_transform(image.size, orientation), knots, zeros,
                knots, zeros, camera, page.size)
    return rotate_raster(rgb, rotation, low_size, (255, 255, 255)), warp, rotation


def normalized_grain(rng, shape):
    fine = rng.standard_normal(shape, dtype=np.float32)
    coarse = cv2.GaussianBlur(fine, (0, 0), 0.95, borderType=cv2.BORDER_REFLECT)
    field = fine + 3.0 * coarse
    field -= field.mean()
    field /= max(float(field.std()), 1e-6)
    return field
