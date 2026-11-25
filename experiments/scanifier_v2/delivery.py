"""Estimate a JPEG delivery profile from independently matched calibration frames."""

import hashlib
import io
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image, JpegImagePlugin

from .phone_training import PhoneView, phone_annotations
from .pipeline import _rng


@dataclass(frozen=True)
class JpegDelivery:
    original_sha256: str
    delivered_sha256: str
    original_size: tuple[int, int]
    delivered_size: tuple[int, int]
    subsampling: int
    qtables: tuple[tuple[int, ...], ...]

    @property
    def long_edge(self):
        return max(self.delivered_size)


def _frame(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "JPEG" or image.mode != "RGB":
            raise ValueError("Expected a three-component JPEG frame")
        if image.getexif().get(274, 1) != 1:
            raise ValueError("Expected upright JPEG delivery frames")
        image.load()
        keys = sorted(image.quantization)
        if keys != list(range(len(keys))) or len(keys) not in (1, 2):
            raise ValueError("Unsupported JPEG quantization table layout")
        tables = tuple(tuple(image.quantization[key]) for key in keys)
        if any(
            len(table) != 64 or min(table) < 1 or max(table) > 255 for table in tables
        ):
            raise ValueError("Expected 8-bit JPEG quantization tables")
        sampling = JpegImagePlugin.get_sampling(image)
        if sampling not in (0, 1, 2):
            raise ValueError("Unsupported JPEG chroma sampling")
        return image.size, sampling, tables


def fit_jpeg_delivery(original, delivered, *, original_sha256, delivered_sha256):
    """Read a measured endpoint after the caller verifies a same-frame A/F pair.

    The input hashes must come from an authorized calibration manifest. Geometry
    checks reject incompatible frames, but cannot establish same-frame identity.
    Only downsampled pairs identify the delivery size cap.
    """
    if (
        hashlib.sha256(original).hexdigest() != original_sha256
        or hashlib.sha256(delivered).hexdigest() != delivered_sha256
    ):
        raise ValueError("JPEG delivery pair SHA-256 mismatch")
    original_size, _, _ = _frame(original)
    delivered_size, sampling, tables = _frame(delivered)
    width, height = original_size
    target_width, target_height = delivered_size
    # Permit one output pixel of rounding along the short edge.
    if (
        max(delivered_size) >= max(original_size)
        or (width > height) != (target_width > target_height)
        or abs(width * target_height - height * target_width) > max(original_size)
    ):
        raise ValueError("Expected a same-orientation, whole-frame downsample")
    return JpegDelivery(
        original_sha256,
        delivered_sha256,
        original_size,
        delivered_size,
        sampling,
        tables,
    )


def apply_jpeg_delivery(view, lines, source_size, fits, *, seed):
    """Draw one whole endpoint, then transport the source annotations with it."""
    if not fits:
        raise ValueError("An observed JPEG delivery fit is required")
    if view.image.size != view.warp.size or view.image.getexif().get(274, 1) != 1:
        raise ValueError(
            "Delivery requires an upright phone view with matching geometry"
        )
    choice = int(_rng(seed, "phone_training/jpeg_delivery").integers(len(fits)))
    fit = fits[choice]
    width, height = view.image.size
    factor = min(1.0, fit.long_edge / max(width, height))
    size = (max(1, round(width * factor)), max(1, round(height * factor)))
    image = view.image.convert("RGB")
    if size != image.size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    # Strip the source JPEG metadata, even when the raster did not need resizing.
    image.info.clear()
    output = io.BytesIO()
    image.save(output, format="JPEG", subsampling=fit.subsampling, qtables=fit.qtables)
    with Image.open(output) as decoded:
        image = decoded.convert("RGB")
    scale = np.diag([size[0] / width, size[1] / height, 1.0])
    warp = replace(view.warp, camera=scale @ view.warp.camera, size=size)
    provenance = {
        "fit_index": choice,
        "seed": seed,
        "original_sha256": fit.original_sha256,
        "delivered_sha256": fit.delivered_sha256,
        "size": list(size),
        "encoded_sha256": hashlib.sha256(output.getvalue()).hexdigest(),
    }
    return PhoneView(
        image,
        phone_annotations(lines, warp, source_size),
        warp,
        view.parameters | {"jpeg_delivery": provenance},
    )
