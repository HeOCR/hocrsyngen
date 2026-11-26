from copy import deepcopy

import numpy as np
import pytest
from PIL import Image, ImageDraw

from experiments.scanifier_v2.dev_profiles import RANGE_BOUNDS
from experiments.scanifier_v2.real_capture import render_real_capture

LINE = {
    "id": "line-1",
    "box": [60, 120, 260, 148],
    "polygon": [[60, 120], [260, 120], [260, 148], [60, 148]],
    "text": "אב גד",
}


def profile(name="adobe_scan", status="prior_only", encoders=()):
    ranges = {key: [0, 0] for key in RANGE_BOUNDS}
    ranges.update(paper_r=[245, 248], paper_g=[238, 242], paper_b=[225, 235],
                  blur_sigma=[0.4, 0.7], noise_sd=[1, 2], noise_cv=[0.2, 0.5])
    return {"version": 1, "name": name, "status": status, "seed": 0,
            "ranges": ranges, "jpeg_encoders": list(encoders)}


def page(y):
    image = Image.new("RGB", (320, 430), "white")
    draw = ImageDraw.Draw(image)
    for x in range(63, 260, 7):
        draw.rectangle((x, y, x + 3, y + 18), fill="black")
    return image


def test_scanner_stages_preserve_projected_lines_and_frame():
    front = page(125)
    back = page(214)
    base = dict(seed=571, long_edge=430, scanner_rotation_deg=(1, 3),
                scanner_perspective=(0.01, 0.02), scanner_jpeg_quality=(90, 96))
    effects = dict(reverse=back, duplex={"opacity": (0.1, 0.1)},
                   scanner_bands={"edge_sides": ("right",), "bar_count": (0, 0)},
                   recompression_quality=(71, 73))
    view = render_real_capture(front, [LINE], profile(), **base, **effects)
    repeat = render_real_capture(front, [LINE], profile(), **base, **effects)
    plain = render_real_capture(front, [LINE], profile(), **base)
    assert view.image.tobytes() == repeat.image.tobytes()
    assert view.parameters == repeat.parameters
    assert view.image.size == plain.image.size == front.size
    assert view.image.tobytes() != plain.image.tobytes()
    assert view.lines == repeat.lines == plain.lines
    assert view.lines[0]["text"] == LINE["text"]
    assert np.allclose(view.warp.inverse(view.lines[0]["polygon"]), LINE["polygon"])
    assert set(view.parameters["real_capture_stages"]) == {
        "duplex", "scanner_bands", "scanner_pose", "scanner_jpeg", "recompression",
    }


def test_scanner_rejects_bands_on_labels_and_unpaired_recompression():
    damaged = deepcopy(LINE)
    damaged["box"][0] = 1
    with pytest.raises(ValueError, match="band intersects"):
        render_real_capture(
            page(125), [damaged], profile(), seed=571,
            scanner_bands={"edge_sides": ("left",), "edge_fraction": (0.1, 0.1),
                           "bar_count": (0, 0)},
        )
    with pytest.raises(ValueError, match="initial JPEG"):
        render_real_capture(page(125), [LINE], profile(), seed=571, recompression_quality=(80, 80))


def test_phone_requires_train_optics_and_geometry_and_keeps_acquisition_encoder():
    phone = profile("phone_oblique", "train_fit", [{"qtables": [[8] * 64], "subsampling": 0}])
    bank = {
        "schema": "scanifier_phone_bank.v1", "fit_split": "train",
        "profiles": {"phone_oblique": [{
            "page_id": "synthetic-fixture",
            "quad": [[0.09, 0.12], [0.84, 0.08], [0.93, 0.91], [0.15, 0.88]],
            "frame_ratio": 320 / 430, "native_long_edge": 430,
            "curl": 0, "shadow": None, "capture_sha256": "a" * 64,
        }]},
    }
    view = render_real_capture(
        page(125), [LINE], phone, phone_bank=bank, seed=571, long_edge=430,
        recompression_quality=(71, 73),
    )
    assert view.parameters["fit_capture_sha256"] == "a" * 64
    assert view.parameters["optics_and_tone"]["jpeg"]["qtables"] == [[8] * 64]
    assert view.lines[0]["id"] == LINE["id"]
    with pytest.raises(ValueError, match="DEV-fitted"):
        render_real_capture(page(125), [LINE], phone | {"status": "dev_fit"},
                            phone_bank=bank, seed=571)
    with pytest.raises(ValueError, match="matching TRAIN"):
        render_real_capture(page(125), [LINE], phone, phone_bank=bank | {"fit_split": "dev"},
                            seed=571)
