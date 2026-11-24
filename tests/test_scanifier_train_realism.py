import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import pytest

from experiments.scanifier_v2.bw_photocopy import bw_photocopy
from experiments.scanifier_v2.phone_training import phone_line_crop
from experiments.scanifier_v2.train_realism import render_train_scan, render_train_scanner, scanner_quotas


def page():
    image = Image.new("RGB", (640, 820), "white")
    ImageDraw.Draw(image).rectangle((120, 310, 450, 334), fill="black")
    lines = [{"box": [115, 305, 455, 340], "text": "אותיות 42", "line_id": "first"}]
    return image, lines


def test_locked_presets_match_the_v3_gallery():
    root = Path(__file__).parents[1] / "experiments/scanifier_v2"
    preset = json.loads((root / "presets/train_realism_v3.json").read_text())
    manifest = json.loads((root / "realism_v3_preview/generation_manifest.json").read_text())
    for role, gallery_role in (("flatbed", "flatbed"), ("bound", "spine")):
        expected = [{"pair": row["id"], **row["fitted_settings"]} for row in manifest["pairs"]
                    if row["role"] == gallery_role]
        assert preset["profiles"][role] == expected
    assert scanner_quotas(10_000) == (("mild", 275), ("medium", 175), ("hard", 50))
    assert sum(quota for _, quota in scanner_quotas(36_037)) == 1801


@pytest.mark.parametrize("profile,ids", [("flatbed", {"17", "18"}), ("bound", {"19", "20"})])
def test_scan_warp_and_determinism(profile, ids):
    image, lines = page()
    view = render_train_scan(image, lines, profile=profile, seed=1)
    replay = render_train_scan(image, lines, profile=profile, seed=1)
    assert view.image.tobytes() == replay.image.tobytes()
    assert view.image.size == image.size
    assert view.parameters["v3_pair"] in ids and view.parameters["round_stains"]
    assert view.lines[0]["text"] == lines[0]["text"]
    xy = np.asarray([[(x + .5), 322.5] for x in (150, 300, 425)])
    observed = np.floor(view.warp.forward(xy)).astype(int)
    assert all(view.image.getpixel(tuple(point))[0] < 150 for point in observed)
    crop, rejection = phone_line_crop(view, 0)
    assert rejection is None and crop is not None


def test_photocopy_routes_to_approved_one_bit_renderer():
    image, lines = page()
    view = render_train_scanner(image, lines, profile="photocopy", band="hard", source_ppi=200, seed=1)
    assert view.image.mode == "1"
    approved = bw_photocopy(image, source_ppi=200, seed=1, severity=view.parameters["severity"])
    assert view.image.tobytes() == approved.image.tobytes()
    assert view.lines[0]["text"] == lines[0]["text"]
    crop, rejection = phone_line_crop(view, 0)
    assert rejection is None and crop is not None
    color = render_train_scanner(image, lines, profile="old-color", band="mild", source_ppi=200, seed=1)
    assert color.image.mode == "RGB" and color.lines[0]["text"] == lines[0]["text"]
