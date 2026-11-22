"""Seeded one-bit photocopy views for synthetic printed training pages."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist

import cv2
import numpy as np
from PIL import Image

from .geometry import Warp
from .low_ppi import checked_annotation, normalized_grain, render_low_ppi
from .pipeline import _rng

PROFILE = "bw_photocopy"
NOMINAL = {
    "severity": 1.0,
    "rotate_deg": 1.6,
    "ppi": 100.0,
    "blur_px": 0.79,
    "brightness": 0.88,
    "contrast": 0.02,
    "noise": 0.73,
    "threshold": 128.0,
    "toner_speckle": 0.0,
}
_SEVERITY_KNOTS = (0.0, 0.4, 0.75, 1.0)
_BAND_WEIGHTS = (0.55, 0.35, 0.10)
_CURVES = {
    "rotate_deg": (0.2, 0.7, 1.2),
    "ppi": (200.0, 150.0, 120.0),
    "blur_px": (0.24, 0.37, 0.46),
    "brightness": (0.965, 0.945, 0.91),
    "contrast": (0.26, 0.09, 0.045),
    "noise": (0.15, 0.31, 0.55),
    "threshold": (126.0, 127.1, 127.8),
    "toner_speckle": (0.00001, 0.00004, 0.00014),
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
        return checked_annotation(record, self.warp)


def _highlights(shape, seed):
    field = normalized_grain(_rng(seed, f"{PROFILE}/highlights"), shape)
    return np.searchsorted(_HIGHLIGHT_CUTS, field).astype(np.float32)


def _parameters(seed, severity):
    if severity is None:
        rng = _rng(seed, f"{PROFILE}/parameters")
        band = rng.choice(len(_BAND_WEIGHTS), p=_BAND_WEIGHTS)
        severity = float(rng.uniform(_SEVERITY_KNOTS[band], _SEVERITY_KNOTS[band + 1]))
    if not 0 <= severity <= 1:
        raise ValueError("severity must be between 0 and 1")
    return {
        "severity": severity,
        **{
            key: float(np.interp(severity, _SEVERITY_KNOTS, (*values, NOMINAL[key])))
            for key, values in _CURVES.items()
        },
    }


def bw_photocopy(image, *, source_ppi, seed, nominal=False, severity=None, rasterize=None):
    """Return a bilevel PIL page and its source-to-output pixel-edge map.

    Set source_ppi to the rasterization density of the original page. The
    profile's smaller working grid is the only stage where the blur and toner
    noise act. If the page comes from a PDF or vector renderer, pass
    rasterize(ppi) to render the same oriented page directly on that grid.
    The result is nearest-neighbour resampled to the oriented source
    size for consumers that expect the original page dimensions.
    Omit severity to sample the mixture or set it between 0 and 1.
    nominal=True selects the exact hard endpoint.
    """
    if nominal and severity is not None:
        raise ValueError("nominal and severity are mutually exclusive")
    params = _parameters(seed, 1.0 if nominal else severity)
    rgb, warp, _ = render_low_ppi(
        image, source_ppi, params["ppi"], params["rotate_deg"], rasterize,
    )
    low_size = rgb.shape[1::-1]
    gray = cv2.transform(rgb.astype(np.float32), np.array([[.2126, .7152, .0722]], np.float32))
    blurred = cv2.GaussianBlur(gray, (0, 0), params["blur_px"], borderType=cv2.BORDER_REPLICATE)
    tone = np.floor((blurred * params["brightness"] - 127.5) * params["contrast"] + 127.5)

    overlay = _highlights(tone.shape, seed)
    tone += overlay * (params["noise"] / NOMINAL["noise"]) ** 2
    ink = tone < params["threshold"]
    if params["toner_speckle"]:
        specks = _rng(seed, f"{PROFILE}/toner").random(ink.shape, dtype=np.float32)
        ink |= specks < params["toner_speckle"]

    mono = Image.fromarray(np.where(ink, 0, 255).astype(np.uint8))
    mono = mono.resize(warp.size, Image.Resampling.NEAREST).convert("1", dither=Image.Dither.NONE)
    return PhotocopyView(mono, warp, low_size, params)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, help="Path to a new one-bit PNG")
    parser.add_argument("--source-ppi", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    strength = parser.add_mutually_exclusive_group()
    strength.add_argument("--nominal", action="store_true", help="Use the hard reference settings")
    strength.add_argument("--severity", type=float, help="Set severity between 0 (mildest) and 1 (hardest)")
    parser.add_argument("--annotations", type=Path, help="JSON array of source annotations")
    args = parser.parse_args()
    sidecar = args.output.with_suffix(".json")
    if args.output.suffix.lower() != ".png":
        parser.error("output must be a PNG")
    if args.output.exists() or sidecar.exists():
        parser.error("output PNG and companion JSON must be new paths")
    with Image.open(args.input) as image:
        result = bw_photocopy(image, source_ppi=args.source_ppi, seed=args.seed,
                             nominal=args.nominal, severity=args.severity)
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
