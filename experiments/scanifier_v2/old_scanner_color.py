"""Seeded old color scanner views for synthetic printed training pages."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist

import cv2
import numpy as np
from PIL import Image

from .geometry import Warp
from .low_ppi import checked_annotation, normalized_grain, render_low_ppi, rotate_raster
from .pipeline import _rng
from .severity import severity_parameters


PROFILE = "old_scanner_color"
NOMINAL = {
    "severity": 1.0,
    "rotate_base_deg": -1.6,
    "rotate_var_deg": 1.1,
    "ppi": 77.0,
    "brightness": 1.08,
    "contrast": 1.10,
    "blur_px": 0.08,
    "noise": 0.75,
    "yellowish": 0.64,
}
_CURVES = {
    "rotate_base_deg": (-0.3, -0.7, -1.15),
    "rotate_var_deg": (0.2, 0.45, 0.8),
    "ppi": (160.0, 140.0, 104.0),
    "brightness": (1.01, 1.03, 1.055),
    "contrast": (1.02, 1.04, 1.075),
    "blur_px": (0.04, 0.055, 0.07),
    "noise": (0.15, 0.31, 0.53),
    "yellowish": (0.08, 0.20, 0.42),
}
_SEPIA = np.array([[.393, .769, .189], [.349, .686, .168], [.272, .534, .131]], dtype=np.float32)
_TILE_SIZE = (1000, 1000)
# Empirical alpha distribution of the procedural SVG tile at noise=.75.
# Only the generated tile is used. The normal scores let each seed draw a
# different field with the same proportions of clear paper and grain.
_ALPHA_CUTS = np.array([NormalDist().inv_cdf(p) for p in
                        (.7783, .8450, .8869, .9110, .9355, .9588, .9750, .9879, .9999)])
_ALPHA_STEPS = (0, 1, 3, 8, 15, 30, 60, 100, 150, 225)


@dataclass(frozen=True)
class ColorScannerView:
    image: Image.Image
    warp: Warp
    scan_size: tuple[int, int]
    parameters: dict[str, float]

    def annotation(self, record):
        """Map a label box or polygon, failing if the rotation clips it."""
        return checked_annotation(record, self.warp)


def _grain_alpha(seed, noise, size, rotation):
    field = normalized_grain(_rng(seed, f"{PROFILE}/grain"), _TILE_SIZE)
    opacity = np.interp(field, _ALPHA_CUTS, _ALPHA_STEPS[1:]).astype(np.float32)
    # The leading quantile represents fully transparent pixels.
    opacity[field < _ALPHA_CUTS[0]] = 0
    opacity *= (noise / NOMINAL["noise"]) / 255
    np.minimum(opacity, 1, out=opacity)
    opacity = cv2.resize(opacity, size, interpolation=cv2.INTER_LINEAR)
    opacity = rotate_raster(opacity, rotation, size, 0)
    # Compensate for resampling differences at the grain-size scale. A flat
    # white swatch gives the loss of contrast and the clear-paper floor.
    np.clip((opacity - 0.012) * 1.45, 0, 1, out=opacity)
    return opacity[..., None] * noise


def _parameters(seed, severity):
    rng = _rng(seed, f"{PROFILE}/parameters")
    params = severity_parameters(rng, severity, _CURVES, NOMINAL)
    variance = params["rotate_var_deg"]
    jitter = 0.0 if params["severity"] == 1.0 else float(rng.uniform(-variance, variance))
    params["rotate_deg"] = params["rotate_base_deg"] + jitter
    return params


def old_scanner_color(image, *, source_ppi, seed, nominal=False, severity=None, rasterize=None):
    """Return a color scanner view, parameters and pixel-edge geometry.

    The same oriented vector page may be rendered directly at the selected
    PPI with rasterize(ppi). Omit severity to sample the three-band mixture.
    Nominal or severity=1 fixes the hard reference, including the base angle.
    """
    if nominal and severity is not None:
        raise ValueError("nominal and severity are mutually exclusive")
    params = _parameters(seed, 1.0 if nominal else severity)
    rgb, warp, rotation = render_low_ppi(
        image, source_ppi, params["ppi"], params["rotate_deg"], rasterize,
    )
    size = rgb.shape[1::-1]
    rgb = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), params["blur_px"],
                           borderType=cv2.BORDER_REPLICATE)
    np.minimum(rgb * params["brightness"], 255, out=rgb)
    np.clip((rgb - 127.5) * params["contrast"] + 127.5, 0, 255, out=rgb)
    yellowish = params["yellowish"]
    rgb = np.clip((1 - yellowish) * rgb + yellowish * cv2.transform(rgb, _SEPIA), 0, 255)
    alpha = _grain_alpha(seed, params["noise"], size, rotation)
    rgb = (1 - alpha) * rgb + alpha * 160
    result = Image.fromarray(np.rint(rgb).astype(np.uint8))
    result = result.resize(warp.size, Image.Resampling.NEAREST)
    return ColorScannerView(result, warp, size, params)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, help="Path to a new RGB PNG")
    parser.add_argument("--source-ppi", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    strength = parser.add_mutually_exclusive_group()
    strength.add_argument("--nominal", action="store_true", help="Use the hard reference settings")
    strength.add_argument("--severity", type=float, help="Set severity between 0 (mildest) and 1 (hardest)")
    parser.add_argument("--annotations", type=Path, help="JSON array of source annotations")
    args = parser.parse_args()
    sidecar = args.output.with_suffix(".json")
    if args.output.suffix.lower() != ".png" or args.output.exists() or sidecar.exists():
        parser.error("output PNG and companion JSON must be new paths")
    with Image.open(args.input) as image:
        view = old_scanner_color(image, source_ppi=args.source_ppi, seed=args.seed,
                                 nominal=args.nominal, severity=args.severity)
    record = {
        "profile": PROFILE, "seed": args.seed, "parameters": view.parameters,
        "source_ppi": args.source_ppi, "scan_size": view.scan_size,
        "output_size": view.image.size, "warp": view.warp.record(),
    }
    if args.annotations:
        originals = json.loads(args.annotations.read_text(encoding="utf-8"))
        record["annotations"] = [view.annotation(annotation) for annotation in originals]
    view.image.save(args.output)
    sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
