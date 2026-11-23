import hashlib
import json

import numpy as np
import pytest
from experiments.scanifier_v2 import fit_phone_training
from experiments.scanifier_v2.dev_profiles import RANGE_BOUNDS
from experiments.scanifier_v2.fit_phone_training import observe, read_pairs, register
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


def test_observed_frame_replay_preserves_clipping_and_joint_illumination():
    source = page()
    draw = ImageDraw.Draw(source)
    rng = np.random.default_rng(109)
    for x, y, length in rng.integers((70, 105, 4), (470, 625, 18), size=(245, 3)):
        draw.line((x, y, x + length, y + length), fill="black", width=3)
    quad = [[0.05, -0.12], [0.97, -0.10], [0.98, 0.91], [0.06, 0.88]]
    light = {
        "paper_r": 217,
        "paper_g": 209,
        "paper_b": 199,
        "gradient_x": 0.11,
        "gradient_y": -0.17,
    }
    clipped = {"box": [80, 1, 460, 24]}
    options = {"seed": 22, "size": SIZE, "quad": quad, "native_long_edge": 700}
    with pytest.raises(ValueError, match="phone geometry"):
        render_phone_view(source, [LINE], profile(), **options)
    invented = render_phone_view(
        source,
        [LINE, clipped],
        profile(),
        **options,
        preserve_frame=True,
        frame_light=light,
    )
    assert phone_line_crop(invented, 0)[1] is None
    assert phone_line_crop(invented, 1) == (None, "clipped")

    measured = observe(source, invented.image, preserve_frame=True)
    legacy = observe(source, invented.image)
    assert np.asarray(measured["quad"]) == pytest.approx(np.asarray(quad), abs=0.009)
    assert min(point[1] for point in legacy["quad"]) >= 0.05 - 1e-9
    for key in ("paper_r", "paper_g", "paper_b"):
        assert measured["frame_light"][key] == pytest.approx(light[key], abs=5)
    for key in ("gradient_x", "gradient_y"):
        assert measured["frame_light"][key] == pytest.approx(light[key], abs=0.035)

    bank = {
        "schema": "scanifier_phone_bank.v1",
        "framing": "observed",
        "profiles": {"phone_oblique": [measured | {"capture_sha256": "a" * 64}]},
    }
    replay = render_fitted_phone_view(
        source, [LINE, clipped], profile(), bank, seed=22, long_edge=700
    )
    assert phone_line_crop(replay, 0)[1] is None
    assert phone_line_crop(replay, 1) == (None, "clipped")
    assert (
        replay.parameters["optics_and_tone"]["gradient_y"]
        == measured["frame_light"]["gradient_y"]
    )


def test_observed_frame_rejects_pages_mostly_outside_capture():
    outside = [[0.98, 0.2], [1.8, 0.2], [1.8, 0.8], [0.98, 0.8]]
    with pytest.raises(ValueError, match="page visible"):
        phone_warp(SIZE, size=SIZE, quad=outside, preserve_frame=True)


def test_observed_bank_requires_distinct_pages_per_supported_mode(monkeypatch):
    rows = [
        {
            "split": "fit",
            "profile": "phone_flat",
            "page_id": str(n),
            "source_sha256": str(n) * 64,
            "capture_sha256": str(n + 3) * 64,
            "source_path": "source",
            "capture_path": "capture",
        }
        for n in range(3)
    ]
    monkeypatch.setattr(fit_phone_training, "read_pairs", lambda _: rows)
    monkeypatch.setattr(fit_phone_training, "load_rgb", lambda path: path)
    monkeypatch.setattr(
        fit_phone_training, "observe", lambda *args, **kwargs: {"quad": QUAD}
    )
    bank = fit_phone_training.fit_bank("pairs.json", preserve_frame=True)
    assert bank["framing"] == "observed"
    assert len(bank["profiles"]["phone_flat"]) == 3
    assert bank["profiles"]["phone_oblique"] == []
    rows[2]["source_sha256"] = rows[1]["source_sha256"]
    with pytest.raises(ValueError, match="at least three"):
        fit_phone_training.fit_bank("pairs.json", preserve_frame=True)


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


def test_train_allowlist_allows_repeat_captures_but_rejects_check_rows(tmp_path):
    files = [tmp_path / name for name in ("print.png", "first.png", "second.png")]
    for value, file in enumerate(files, 200):
        Image.new("L", (128, 128), value).save(file)
    pins = [hashlib.sha256(file.read_bytes()).hexdigest() for file in files]
    record = {
        "page_id": "first",
        "split": "fit",
        "profile": "phone_flat",
        "source": files[0].name,
        "source_sha256": pins[0],
        "capture": files[1].name,
        "capture_sha256": pins[1],
        "optics_eligible": True,
    }
    second = record | {"capture": files[2].name, "capture_sha256": pins[2]}
    manifest = tmp_path / "pairs.json"

    def write(rows):
        manifest.write_text(
            json.dumps({"purpose": "approved_train_phone_calibration", "pairs": rows})
        )

    write([record, second])
    assert len(list(read_pairs(manifest, train_only=True))) == 2
    for update in (
        {"split": "check"},
        {"page_id": "second"},
        {"capture_sha256": pins[1]},
    ):
        write([record, second | update])
        with pytest.raises(ValueError):
            list(read_pairs(manifest, train_only=True))


def test_train_profile_requires_train_bank_and_keeps_render_provenance():
    row = {
        "page_id": "a",
        "frame_ratio": SIZE[0] / SIZE[1],
        "quad": QUAD,
        "native_long_edge": 700,
        "curl": 0,
        "shadow": None,
        "capture_sha256": "1" * 64,
    }
    bank = {
        "schema": "scanifier_phone_bank.v1",
        "fit_split": "train",
        "framing": "observed",
        "profiles": {"phone_oblique": [row]},
    }
    train = profile() | {"status": "train_fit"}
    view = render_fitted_phone_view(page(), [LINE], train, bank, seed=5, long_edge=700)
    assert view.parameters["profile_status"] == "train_fit"
    assert view.parameters["fit_capture_sha256"] == row["capture_sha256"]
    assert view.lines[0]["text"] == LINE["text"]
    with pytest.raises(ValueError, match="non-test geometry bank"):
        render_fitted_phone_view(page(), [LINE], profile(), bank, seed=5, long_edge=700)


def test_native_optics_ignore_background_outside_the_projected_page():
    from experiments.scanifier_v2.fit_dev_profiles import _measure

    quad = [[0.22, 0.22], [0.78, 0.22], [0.78, 0.78], [0.22, 0.78]]
    originals = []
    for color in ((160, 40, 60), (26, 190, 241)):
        im = Image.new("RGB", (480, 480), color)
        ImageDraw.Draw(im).rectangle((104, 104, 376, 376), fill=(228, 228, 228))
        originals.append(_measure(im, seed=1, page_quad=quad))
    assert originals[0] == originals[1]
    assert originals[0]["paper_r"] == pytest.approx(228.0)


def test_train_fit_reports_support_by_distinct_page_and_never_mixes_endpoints(
    tmp_path, monkeypatch
):
    from experiments.scanifier_v2 import fit_train_phone

    manifest = tmp_path / "pairs.json"
    manifest.write_text("{}")
    jpeg = tmp_path / "approved.jpg"
    page().save(jpeg)
    rows = []
    for i, (mode, physical_page, optical) in enumerate(
        (
            ("phone_flat", "a", True),
            ("phone_flat", "a", True),
            ("phone_flat", "b", True),
            ("phone_flat", "c", True),
            ("phone_oblique", "a", True),
            ("phone_oblique", "a", True),
            ("phone_oblique", "b", True),
            ("phone_oblique", "c", False),
        )
    ):
        rows.append(
            {
                "page_id": physical_page,
                "profile": mode,
                "capture_path": jpeg,
                "source_path": jpeg,
                "optics_eligible": optical,
                "capture_sha256": f"{i:064x}",
                "source_sha256": physical_page * 64,
            }
        )
    monkeypatch.setattr(
        fit_train_phone,
        "read_pairs",
        lambda path, train_only: rows if train_only else [],
    )
    monkeypatch.setattr(
        fit_train_phone, "observe", lambda *args, **kwargs: {"quad": QUAD, "curl": 0}
    )
    monkeypatch.setattr(
        fit_train_phone,
        "_measure",
        lambda *args, **kwargs: {
            "paper_r": 240,
            "paper_g": 238,
            "paper_b": 236,
            "noise_sd": 1.0,
            "gradient_x": 0.02,
            "gradient_y": -0.1,
            "edge_sigma": 0.6,
        },
    )
    bank, fitted, evidence = fit_train_phone.fit_train(manifest)
    assert bank["fit_split"] == "train"
    assert len(bank["profiles"]["phone_flat"]) == 4
    assert set(fitted) == {"phone_flat"}
    assert fitted["phone_flat"]["status"] == "train_fit"
    assert evidence["coverage"]["phone_oblique"]["optical_pages"] == 2
    assert "phone_oblique" in evidence["unsupported_endpoints"]
