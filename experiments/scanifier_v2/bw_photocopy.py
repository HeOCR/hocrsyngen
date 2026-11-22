"""Seeded one-bit photocopy views for synthetic printed training pages."""

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist

import cv2
import numpy as np
from PIL import Image, ImageOps

from .geometry import Warp, exif_transform, transform_annotation
from .pipeline import _rng

PROFILE = "bw_photocopy"
NOMINAL = {
    "rotate_deg": 1.6,
    "ppi": 100.0,
    "blur_px": 0.79,
    "brightness": 0.88,
    "contrast": 0.02,
    "noise": 0.73,
    "toner_speckle": 0.0,
}
RANGES = {
    "rotate_deg": (1.1, 2.1),
    "ppi": (94.0, 106.0),
    "blur_px": (0.70, 0.88),
    "brightness": (0.86, 0.90),
    "contrast": (0.018, 0.023),
    "noise": (0.65, 0.81),
    "toner_speckle": (0.0, 0.0004),
}

# P(additive light < step) estimated on an invented 128-grey patch at
# 100 PPI using the reference renderer. Quantile-map Gaussian noise to
# the observed sparse, right-skewed highlight distribution.
_HIGHLIGHT_CDF = (
    .7889, .8790, .9185, .9423, .9581, .9691, .9772, .9833,
    .9880, .9913, .9939, .9958, .9972, .9982, .9989, .9995,
)
_HIGHLIGHT_CUTS = np.array([NormalDist().inv_cdf(p) for p in _HIGHLIGHT_CDF])


@dataclass(frozen=True)
class PhotocopyView:
    image: Image.Image
    warp: Warp
    photocopy_size: tuple[int, int]
    parameters: dict[str, float]

    def annotation(self, record):
        """Transform geometry and fail closed if a labelled region is clipped."""
        result = transform_annotation(record, self.warp)
        left, top, right, bottom = result["box"]
        width, height = self.image.size
        if left < 0 or top < 0 or right > width or bottom > height:
            raise ValueError("Photocopy rotation clips the annotation")
        return result


def _rotation(size, degrees):
    center = np.asarray(size, dtype=float) / 2
    radians = np.deg2rad(degrees)
    c, s = np.cos(radians), np.sin(radians)
    matrix = np.array([[c, -s, 0], [s, c, 0], [0., 0., 1.]])
    matrix[:2, 2] = center - matrix[:2, :2] @ center
    return matrix


def _highlights(shape, seed):
    rng = _rng(seed, f"{PROFILE}/highlights")
    fine = rng.standard_normal(shape, dtype=np.float32)
    coarse = cv2.GaussianBlur(fine, (0, 0), 0.95, borderType=cv2.BORDER_REFLECT)
    # Normalize the mixture so the step cutoffs keep their nominal probabilities.
    field = fine + 3.0 * coarse
    field -= field.mean()
    field /= max(float(field.std()), 1e-6)
    return np.searchsorted(_HIGHLIGHT_CUTS, field).astype(np.float32)


def _rgb_on_white(image):
    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image.convert("RGBA"))
    return background.convert("RGB")


def bw_photocopy(image, *, source_ppi, seed, nominal=False, rasterize=None):
    """Return a bilevel PIL page and its source-to-output pixel-edge map.

    Set source_ppi to the rasterization density of the original page. The
    profile's smaller working grid is the only stage where the blur and toner
    noise act. If the page comes from a PDF or vector renderer, pass
    rasterize(ppi) to render the same oriented page directly on that grid.
    The result is nearest-neighbour resampled to the oriented source
    size for consumers that expect the original page dimensions.
    """
    if not math.isfinite(source_ppi) or source_ppi <= 0:
        raise ValueError("source_ppi must be finite and positive")

    rng = _rng(seed, f"{PROFILE}/parameters")
    params = dict(NOMINAL) if nominal else {
        key: float(rng.uniform(*bounds)) for key, bounds in RANGES.items()
    }
    orientation = image.getexif().get(274, 1)
    page = ImageOps.exif_transpose(image)
    if source_ppi < params["ppi"]:
        raise ValueError("source_ppi must be at least the sampled photocopy PPI")

    ratio = params["ppi"] / source_ppi
    low_size = tuple(max(1, round(edge * ratio)) for edge in page.size)
    if rasterize is None:
        rgb = cv2.resize(np.asarray(_rgb_on_white(page)), low_size, interpolation=cv2.INTER_AREA)
    else:
        native = rasterize(params["ppi"])
        if any(abs(expected - actual) > 1 for expected, actual in zip(low_size, native.size)):
            raise ValueError("Direct render size does not match the source page and PPI")
        low_size = native.size
        rgb = np.asarray(_rgb_on_white(native))
    scale = np.diag([low_size[0] / page.width, low_size[1] / page.height, 1.])
    rotate = _rotation(low_size, params["rotate_deg"])
    camera = np.linalg.inv(scale) @ rotate @ scale

    # OpenCV samples at array-index centres. Shift the edge-coordinate affine
    # to those centres so annotations track the same rotation.
    affine = rotate[:2].copy()
    affine[:, 2] += affine[:, :2] @ [0.5, 0.5] - 0.5
    rgb = cv2.warpAffine(rgb, affine, low_size, flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    gray = cv2.transform(rgb.astype(np.float32), np.array([[.2126, .7152, .0722]], np.float32))
    blurred = cv2.GaussianBlur(gray, (0, 0), params["blur_px"], borderType=cv2.BORDER_REPLICATE)
    tone = np.floor((blurred * params["brightness"] - 127.5) * params["contrast"] + 127.5)

    overlay = _highlights(tone.shape, seed)
    tone += overlay * (params["noise"] / NOMINAL["noise"]) ** 2
    ink = tone < 128
    if params["toner_speckle"]:
        specks = _rng(seed, f"{PROFILE}/toner").random(ink.shape, dtype=np.float32)
        ink |= specks < params["toner_speckle"]

    mono = Image.fromarray(np.where(ink, 0, 255).astype(np.uint8))
    mono = mono.resize(page.size, Image.Resampling.NEAREST).convert("1", dither=Image.Dither.NONE)
    identity_knots = np.array([0., 1.])
    zeros = np.zeros(2)
    warp = Warp(exif_transform(image.size, orientation), identity_knots, zeros,
                identity_knots, zeros, camera, page.size)
    return PhotocopyView(mono, warp, low_size, params)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, help="Path to a new one-bit PNG")
    parser.add_argument("--source-ppi", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--nominal", action="store_true")
    parser.add_argument("--annotations", type=Path, help="JSON array of source annotations")
    args = parser.parse_args()
    sidecar = args.output.with_suffix(".json")
    if args.output.suffix.lower() != ".png":
        parser.error("output must be a PNG")
    if args.output.exists() or sidecar.exists():
        parser.error("output PNG and companion JSON must be new paths")
    with Image.open(args.input) as image:
        result = bw_photocopy(image, source_ppi=args.source_ppi, seed=args.seed, nominal=args.nominal)
    record = {
        "profile": PROFILE,
        "seed": args.seed,
        "parameters": result.parameters,
        "source_ppi": args.source_ppi,
        "photocopy_size": result.photocopy_size,
        "output_size": result.image.size,
        "warp": result.warp.record(),
    }
    if args.annotations:
        annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
        record["annotations"] = [result.annotation(annotation) for annotation in annotations]
    result.image.save(args.output)
    sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
