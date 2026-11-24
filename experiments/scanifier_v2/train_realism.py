"""Default capture profiles for annotated synthetic training pages."""

from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from .bw_photocopy import bw_photocopy
from .geometry import Warp
from .old_scanner_color import old_scanner_color
from .phone_training import PhoneView, phone_annotations
from .pipeline import _rng
from .realism_v3 import render
from .severity import BAND_BOUNDARIES, BAND_WEIGHTS

_PRESET = (Path(__file__).parent / "presets/train_realism_v3.json").read_bytes()
_SETTINGS = json.loads(_PRESET)
PRESET_SHA256 = sha256(_PRESET).hexdigest()
SCANNER_SHARE_PERCENT = 5
SCANNER_PROFILES = {"photocopy": bw_photocopy, "old-color": old_scanner_color}
BANDS = ("mild", "medium", "hard")
C2_BOUND_INK_DROP = 8


def scanner_quotas(total):
    """Return the integer 5% quotas for one scanner arm, by severity."""
    count = total * SCANNER_SHARE_PERCENT // 100
    weights = [round(weight * 100) for weight in BAND_WEIGHTS]
    quotas = [count * weight // 100 for weight in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(count * weights[i] % 100), i))
    for i in order[:count - sum(quotas)]:
        quotas[i] += 1
    return tuple(zip(BANDS, quotas, strict=True))


def render_train_scan(image, lines, *, profile, seed, c2_bound_reduced_fade=False):
    """Apply the locked v3 scan preset, with the C2 v1.1 bound ink adjustment on request."""
    presets = _SETTINGS["profiles"][profile]
    rng = _rng(seed, "train_realism/flatbed_bound")
    settings = presets[int(rng.integers(len(presets)))]
    reduced_fade = profile == "bound" and c2_bound_reduced_fade
    if reduced_fade:
        settings = {**settings, "ink": settings["ink"] - C2_BOUND_INK_DROP}
    width, height = image.size
    x = np.linspace(-.5, width - .5, 65)
    side_dist = width - 1 - x if settings["edge_side"] == "right" else x
    skew = (x - width / 2) * np.tan(np.deg2rad(settings["skew"]))
    gutter = width * .12
    bend = gutter * np.tan(np.deg2rad(settings["gutter_bend_deg"])) * np.exp(-side_dist / gutter)
    warp = Warp(np.eye(3), np.array([0, height]), np.zeros(2), x + .5, -(skew + bend), np.eye(3), image.size)
    result = render(image, settings, seed, int(rng.integers(20)), "spine" if profile == "bound" else "flatbed",
                    scale=width / _SETTINGS["calibration_width_px"], warp=warp)
    parameters = {"profile": profile, "model": "realism_v3", "v3_pair": settings["pair"],
                  "preset_sha256": PRESET_SHA256, "round_stains": True, "seed": seed, "warp": warp.record()}
    if reduced_fade:
        parameters.update(capture_recipe="c2-v1.1", bound_ink_delta=-C2_BOUND_INK_DROP)
    return PhoneView(result, phone_annotations(lines, warp, image.size), warp, parameters)


def render_train_scanner(image, lines, *, profile, band, source_ppi, seed, rasterize=None):
    """Use the approved photocopy/old-scanner model and preserve literal lines."""
    strength = None
    if band is not None:
        i = BANDS.index(band)
        rng = _rng(seed, "train_realism/scanner_band")
        strength = float(rng.uniform(*BAND_BOUNDARIES[i:i + 2]))
    scanner = SCANNER_PROFILES[profile](image, source_ppi=source_ppi, seed=seed, severity=strength, rasterize=rasterize)
    annotations = phone_annotations(lines, scanner.warp, image.size)
    parameters = {**scanner.parameters, "profile": profile, "band": band,
                  "seed": seed, "warp": scanner.warp.record()}
    return PhoneView(scanner.image, annotations, scanner.warp, parameters)
