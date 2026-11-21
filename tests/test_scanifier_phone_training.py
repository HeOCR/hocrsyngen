import hashlib
import json

import numpy as np
import pytest
from experiments.scanifier_v2.dev_profiles import RANGE_BOUNDS
from experiments.scanifier_v2.fit_phone_training import read_pairs, register
from experiments.scanifier_v2.phone_training import (
    phone_line_crop,
    phone_warp,
    render_fitted_phone_view,
    render_phone_view,
)
from PIL import Image, ImageDraw

SIZE = (540, 700)
QUAD = [[0.12, 0.08], [0.84, 0.16], [0.94, 0.91], [0.06, 0.88]]
LINE = {
    "box": [80, 230, 460, 258],
    "baseline": [[460, 250], [80, 250]],
    "text": "אב גד",
}


def profile():
    ranges = {key: [0, 0] for key in RANGE_BOUNDS}
    for key in ("paper_r", "paper_g", "paper_b"):
        ranges[key] = [240, 240]
    ranges["blur_sigma"] = [0.6, 0.8]
    encoder = {"qtables": [[8] * 64, [12] * 64], "subsampling": 2}
    return {
        "version": 1,
        "name": "phone_oblique",
        "status": "dev_fit",
        "seed": 5,
        "ranges": ranges,
        "jpeg_encoders": [encoder],
    }


def page():
    image = Image.new("RGB", SIZE, "white")
    draw = ImageDraw.Draw(image)
    for x in range(100, 455, 7):
        draw.rectangle((x, 234, x + 3, 252), fill="black")
    return image


def test_phone_fold_maps_raster_and_baseline_through_same_warp():
    options = {
        "seed": 36,
        "size": SIZE,
        "quad": QUAD,
        "native_long_edge": 700,
        "curl": 0.01,
        "fold": (0.51, 0.08, 0.016),
        "shadow": (0.5, 0.5, 0.2, 0.3, 0.2),
        "sharpen": 0.12,
    }
    view = render_phone_view(page(), [LINE], profile(), **options)
    repeat = render_phone_view(page(), [LINE], profile(), **options)
    assert view.image.tobytes() == repeat.image.tobytes()
    assert view.lines == repeat.lines
    assert view.lines[0]["text"] == LINE["text"]
    baseline = np.asarray(view.lines[0]["baseline"])
    assert len(baseline) > 20
    assert np.allclose(view.warp.inverse(baseline)[:, 1], 250)
    left, right = baseline[[0, -1]]
    assert (
        np.max(
            np.abs(
                (baseline - left) @ np.array([right[1] - left[1], left[0] - right[0]])
            )
        )
        > 100
    )
    centers = np.column_stack([np.arange(101, 455, 7), np.full(51, 244.0)])
    points = np.round(view.warp.forward(centers) - 0.5).astype(int)
    ink = np.asarray(view.image)[points[:, 1], points[:, 0]]
    assert np.quantile(ink, 0.9) < 70
    crop, reason = phone_line_crop(view, 0)
    assert reason is None and crop.width > crop.height * 5


def test_neighbor_admission_and_underresolved_crops_are_rejected():
    neighbor = {"box": [90, 261, 450, 280]}
    view = render_phone_view(
        page(),
        [LINE, neighbor],
        profile(),
        seed=0,
        size=SIZE,
        quad=QUAD,
        native_long_edge=700,
        fold=(0.51, 0.12, 0.024),
    )
    assert phone_line_crop(view, 0) == (None, "neighbor_overlap")
    assert phone_line_crop(view, 0, minimum_height=80) == (None, "underresolved")
    with pytest.raises(ValueError, match="phone geometry"):
        phone_warp(SIZE, size=SIZE, quad=list(reversed(QUAD)))


def test_fitted_bank_is_seeded_and_carries_selected_capture_identity():
    rows = [
        {
            "quad": QUAD,
            "frame_ratio": 540 / 700,
            "native_long_edge": 700,
            "curl": curl,
            "shadow": None,
            "capture_sha256": checksum * 64,
        }
        for curl, checksum in [(0.0, "a"), (0.005, "b")]
    ]
    bank = {"schema": "scanifier_phone_bank.v1", "profiles": {"phone_oblique": rows}}
    view = render_fitted_phone_view(
        page(), [LINE], profile(), bank, seed=29, long_edge=700
    )
    repeat = render_fitted_phone_view(
        page(), [LINE], profile(), bank, seed=29, long_edge=700
    )
    assert view.parameters == repeat.parameters
    assert view.parameters["fit_capture_sha256"] in {"a" * 64, "b" * 64}
    assert view.image.tobytes() == repeat.image.tobytes()
    assert view.parameters["fold"] is None
    assert view.parameters["optics_and_tone"]["sharpen_amount"] == 0


def test_register_retains_a_bow_supported_by_disjoint_landmarks():
    source = Image.new("RGB", SIZE, "white")
    rng = np.random.default_rng(52)
    draw = ImageDraw.Draw(source)
    for x, y, length in rng.integers((60, 65, 4), (475, 625, 20), size=(370, 3)):
        draw.line((x, y, x + length, y + length // 2), fill="black", width=3)
        draw.rectangle((x, y, x + 3, y + length), outline="black", width=2)
    view = render_phone_view(
        source,
        [],
        profile(),
        seed=8,
        size=SIZE,
        quad=QUAD,
        native_long_edge=700,
        curl=0.009,
    )
    _, _, _, _, fit = register(source, view.image)
    assert fit["curl"] == pytest.approx(0.009, abs=0.002)
    assert fit["fitted_error_px"] < 0.75 * fit["planar_error_px"]


def test_private_calibration_rejects_cross_split_pages_and_wrong_hash(tmp_path):
    source = tmp_path / "original.png"
    capture = tmp_path / "capture.png"
    second = tmp_path / "second.png"
    files = (source, capture, second)
    for index, file in enumerate(files):
        Image.new("L", (128, 128), 248 + index).save(file)
    source_sha, capture_sha, other_sha = [
        hashlib.sha256(file.read_bytes()).hexdigest() for file in files
    ]
    row = {
        "page_id": "a",
        "split": "fit",
        "profile": "phone_flat",
        "source": source.name,
        "source_sha256": source_sha,
        "capture": capture.name,
        "capture_sha256": capture_sha,
    }
    manifest = tmp_path / "manifest.json"

    def write(*rows):
        manifest.write_text(
            json.dumps({"purpose": "non_test_phone_calibration", "pairs": rows})
        )

    write(row)
    assert next(read_pairs(manifest))["capture_path"] == capture
    write(
        row,
        row
        | {
            "split": "check",
            "profile": "phone_oblique",
            "capture": second.name,
            "capture_sha256": other_sha,
        },
    )
    with pytest.raises(ValueError, match="disjoint split"):
        list(read_pairs(manifest))
    write(row | {"capture_sha256": "c" * 64})
    with pytest.raises(ValueError, match="hash mismatch"):
        list(read_pairs(manifest))
