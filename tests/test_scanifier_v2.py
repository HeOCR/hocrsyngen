"""Small, fully synthetic capture and calibration tests."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageOps

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from experiments.scanifier_v2.batch import CAPTURE_FILENAME, capture_batch
from experiments.scanifier_v2.fit_calibration import PACK, fit_directory, registered_shots
from experiments.scanifier_v2.geometry import Warp, exif_transform, make_warp, project, transform_annotation
from experiments.scanifier_v2.pipeline import (
    _isp, _lighting, _optics, _sensor, capture, read_config, sample_parameters, srgb_to_linear,
)
from hocrsyngen.cli import main
from hocrsyngen.io import sha256_file
from hocrsyngen.validation import validate_batch


def minimal_config():
    config = read_config()
    config["geometry"].update(
        long_edge_px=[192, 192], margin=[0, 0], frame_aspect=[112 / 192, 112 / 192], pitch_deg=[0, 0], yaw_deg=[0, 0],
        roll_deg=[0, 0], curl_probability=0, crumple_probability=0,
        quarter_turn_weights={"0": 1, "90": 0, "180": 0, "270": 0},
    )
    config["surface"].update(texture=[0, 0])
    config["lighting"].update(exposure=[1, 1], low_light_probability=0, gradient=[0, 0],
                              vignette=[0, 0], **{f"white_balance_{c}": [1, 1] for c in "rgb"})
    config["hard_light"]["probability"] = 0
    config["optics"].update(defocus_sigma_px=[0, 0], defocus_gradient_px=[0, 0], motion_probability=0)
    config["sensor"].update(shot_noise=[0, 0], read_noise=[0, 0])
    config["isp"].update(denoise_strength=[0, 0], sharpen_amount=[0, 0])
    config["jpeg"].update(quality=[100, 100], subsampling_weights={"0": 1, "1": 0, "2": 0})
    return config


@pytest.mark.parametrize("orientation", range(1, 9))
def test_exif_tags_align_pixels_and_annotations(orientation):
    source = Image.new("RGB", (192, 112), "white")
    ImageDraw.Draw(source).rectangle((9, 13, 25, 25), fill="black")
    source.getexif()[274] = orientation
    expected = np.asarray(ImageOps.exif_transpose(source))
    result = capture(source, 17, minimal_config())
    with Image.open(io.BytesIO(result.jpeg)) as output:
        assert output.size == result.warp.size
        assert 274 not in output.getexif()
        actual = np.asarray(output)
    assert np.array_equal(actual[:, :, 0] < 100, expected[:, :, 0] < 100)
    edge_center = project(exif_transform(source.size, orientation), [[17.5, 19.5]])[0]
    np.testing.assert_allclose(result.warp.forward([[17.5, 19.5]])[0], edge_center)
    x, y = np.floor(edge_center).astype(int)
    assert actual[y, x, 0] < 100


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_geometry_round_trip_and_exact_piecewise_edges(turn):
    config = read_config()
    p = sample_parameters(config, 17)["geometry"]
    p.update(curl=0.065, crumple=0.03, quarter_turn=turn, pitch_deg=29, yaw_deg=-23)
    transform = make_warp((480, 630), 7, p)
    points = np.random.default_rng(17).uniform([0, 0], [480, 630], (350, 2))
    np.testing.assert_allclose(transform.inverse(transform.forward(points)), points, atol=1e-9)
    assert np.all(transform.forward(points) >= 0)
    assert np.all(transform.forward(points) <= transform.size)

    source = {"text": "שָׁלוֹם 123", "polygon": [[18, 20], [418, 20], [418, 56], [18, 56]],
              "box": [16, 18, 422, 60], "baseline": [[19, 52], [417, 52]]}
    result = transform_annotation(source, transform)
    dense = np.column_stack((np.linspace(18, 418, 1000), np.repeat(20, 1000)))
    mapped = transform.forward(dense)
    polygon = np.asarray(result["polygon"])
    starts = polygon
    directions = np.roll(polygon, -1, axis=0) - starts
    relative = mapped[:, None, :] - starts[None, :, :]
    t = np.sum(relative * directions, axis=2) / np.sum(directions ** 2, axis=1)
    distances = np.linalg.norm(relative - np.clip(t, 0, 1)[..., None] * directions, axis=2)
    assert distances.min(axis=1).max() < 1e-9
    assert len(result["baseline"]) > 2
    assert result["text"] == source["text"]
    boundary = np.asarray(result["box_polygon"])
    assert result["box"] == [*np.floor(boundary.min(axis=0)), *np.ceil(boundary.max(axis=0))]


def test_perspective_rotation_curves_align_with_rendered_marks():
    config = minimal_config()
    config["geometry"].update(
        margin=[0.08, 0.08], pitch_deg=[25, 25], yaw_deg=[19, 19], roll_deg=[4, 4],
        curl_probability=1, curl=[0.055, 0.055], crumple_probability=1, crumple=[0.026, 0.026],
        quarter_turn_weights={"0": 0, "90": 1, "180": 0, "270": 0},
    )
    source = Image.new("RGB", (180, 230), "white")
    drawn = ImageDraw.Draw(source)
    points = [(31, 60), (148, 53), (98, 166)]
    for x, y in points:
        drawn.rectangle((x - 4, y - 4, x + 4, y + 4), fill="black")
    result = capture(source, 17, config)
    pixels = np.asarray(Image.open(io.BytesIO(result.jpeg)))
    for x, y in np.floor(result.warp.forward(points)).astype(int):
        assert pixels[y, x].max() < 30
    assert capture(source, 17, config).jpeg == result.jpeg
    assert capture(source, 18, config).jpeg != result.jpeg


@pytest.mark.parametrize(("kind", "factor"), [
    ("shadow_stripe", 0.4), ("shadow_square", 0.4), ("sun_patch", 1.6),
])
def test_hard_light_has_pixel_scale_boundaries(kind, factor):
    config = minimal_config()
    p = sample_parameters(config, 17)
    hard = p["hard_light"] | {"kind": kind, "width": 0.30, "angle_deg": 0,
                              "center_x": 0.5, "center_y": 0.5, "edge_px": 1,
                              "shadow_gain": 0.4, "sun_gain": 1.6}
    image = np.full((100, 100, 3), 0.5, dtype=np.float32)
    output = _lighting(image, p["lighting"], hard)
    np.testing.assert_allclose(output[50, 35, 0], 0.5 * factor)
    np.testing.assert_allclose(output[50, 34, 0], 0.5)
    np.testing.assert_allclose(output[0, 50, 0], 0.5 * factor if kind == "shadow_stripe" else 0.5)


def test_motion_spreads_along_its_direction_and_defocus_spreads_both_axes():
    impulse = np.zeros((31, 31, 3), dtype=np.float32)
    impulse[15, 15] = 1
    p = sample_parameters(minimal_config(), 17)["optics"]
    motion = _optics(impulse, p | {"motion_length_px": 7, "motion_angle_deg": 0})
    assert motion[15, 12, 0] > 0
    assert motion[12, 15, 0] == pytest.approx(0, abs=1e-7)
    defocus = _optics(impulse, p | {"defocus_sigma_px": 1.4})
    assert defocus[15, 12, 0] == pytest.approx(defocus[12, 15, 0])
    assert defocus[12, 15, 0] > 0


def test_low_light_noise_and_isp_change_pixel_values():
    rgb = np.full((80, 80, 3), 0.2, dtype=np.float32)
    p = sample_parameters(minimal_config(), 17)
    noise = _sensor(rgb, p["sensor"], True, np.random.default_rng(17))
    clean = _sensor(rgb, p["sensor"], False, np.random.default_rng(17))
    assert np.std(srgb_to_linear(noise)) > 0.001
    np.testing.assert_allclose(srgb_to_linear(clean), rgb, atol=1e-6)
    rgb[40:, :] = 0.65
    parameters = p["isp"] | {"denoise_strength": 0.6, "denoise_edge_threshold": 0.5,
                             "denoise_sigma_px": 1, "sharpen_sigma_px": 1}
    smear = np.asarray(_isp(rgb, parameters, False))
    sharp = np.asarray(_isp(rgb, parameters | {"denoise_strength": 0, "sharpen_amount": 1}, False))
    assert sharp[39, 40, 0] < 51 < smear[39, 40, 0]
    assert sharp[40, 40, 0] > 166 > smear[40, 40, 0]


def test_config_serialization_does_not_change_seeded_sampling():
    config = read_config()
    restored = json.loads(json.dumps(config, sort_keys=True))
    assert sample_parameters(config, 17) == sample_parameters(restored, 17)


def test_config_rejects_unknown_or_invalid_settings(tmp_path):
    path = tmp_path / "overrides.json"
    for payload in (
        {"geometry": {"margn": [0, 0]}},
        {"lighting": {"low_light_probability": -1}},
        {"jpeg": {"quality": [90, 101]}},
        {"hard_light": {"kind_weights": {"shadow_stripe": 1}}},
    ):
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            read_config(path)


def test_batch_preserves_gold_and_binds_derived_assets(tmp_path):
    source, output = tmp_path / "source", tmp_path / "capture"
    corpus = tmp_path / "dev-text.txt"
    corpus.write_text("דף תרגול לבדיקת צילום\nשורה נוספת מודפסת על הנייר\n", encoding="utf-8")
    args = ["generate", "--count", "1", "--seed", "17", "--template", "printed_letter",
            "--text-corpus", str(corpus), "--emit-line-annotations", "--emit-paired-render", "--output", str(source)]
    assert main(args) == 0
    config = minimal_config()
    config["geometry"]["quarter_turn_weights"] = {"0": 0, "90": 0, "180": 1, "270": 0}
    capture_batch(source, output, seed=5, config=config)
    assert validate_batch(output).page_count == 1
    original = json.loads((source / "line_annotations.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "generation_manifest.json").read_text(encoding="utf-8"))
    sidecar = json.loads((output / CAPTURE_FILENAME).read_text(encoding="utf-8"))
    assert sidecar["generation_manifest_sha256"] == sha256_file(output / "generation_manifest.json")
    assert sidecar["source_line_annotations_sha256"] == sha256_file(source / "line_annotations.json")
    assert sidecar["source_generation_manifest_sha256"] == sha256_file(source / "generation_manifest.json")
    record = sidecar["pages"][0]
    asset = manifest["samples"][0]["pages"][0]
    assert record["source_raster"] == "paired_png"
    assert record["page_sha256"] == asset["sha256"] == sha256_file(output / asset["asset_path"])
    geometry = record["warp"]
    x, dx = np.array(geometry["horizontal_shear"]).T
    y, dy = np.array(geometry["vertical_shear"]).T
    warp = Warp(np.array(geometry["exif_matrix"]), x, dx, y, dy, np.array(geometry["camera_matrix"]),
                (record["width"], record["height"]))
    for old, new in zip(original["pages"][0]["lines"], record["lines"], strict=True):
        assert new == transform_annotation(old, warp)
    for old, new in zip(original["pages"][0]["regions"], record["regions"], strict=True):
        assert new == transform_annotation(old, warp)
    with pytest.raises(ValueError, match="Output already exists"):
        capture_batch(source, output, seed=6, config=config)


def _synthetic_calibration_target():
    target = json.loads((PACK / "gt" / "P01.json").read_text(encoding="utf-8"))
    scale, pad = 0.16, 80
    w, h = target["size_px"]
    page = Image.new("RGB", (round(w * scale) + 2 * pad, round(h * scale) + 2 * pad), (55, 55, 55))
    draw = ImageDraw.Draw(page)

    def xy(point):
        return tuple(round(coordinate * scale + pad) for coordinate in point)

    draw.rectangle((xy((0, 0)), xy((w, h))), fill=(231, 226, 217))
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    for marker in target["markers"]:
        a, b, _, _ = [xy(point) for point in marker["corners_tl_tr_br_bl"]]
        pixels = cv2.aruco.generateImageMarker(dictionary, marker["id"], b[0] - a[0])
        page.paste(Image.fromarray(pixels), a)
    for edge in target["edges"]:
        draw.polygon([xy(point) for point in edge["polygon"]], fill=(20, 20, 20))
    for step in target["wedge"]:
        left, top, right, bottom = step["box"]
        draw.rectangle((xy((left, top)), xy((right, bottom))), fill=tuple(round(v * step["grey"] / 255)
                                                                         for v in (231, 226, 217)))
    return page


def test_calibration_fits_registered_frames_and_retains_missing_priors(tmp_path, monkeypatch):
    target = _synthetic_calibration_target()
    target.save(tmp_path / "P01-A-p9.jpg", quality=88)
    Image.new("RGB", target.size).save(tmp_path / "P01-A-p4a.jpg")
    (tmp_path / "unregistered.jpg").write_bytes(b"unregistered sentinel")
    opened = []
    real_open = Image.open

    def record_open(fp, *args, **kwargs):
        if isinstance(fp, Path):
            opened.append(fp.name)
        return real_open(fp, *args, **kwargs)

    monkeypatch.setattr(Image, "open", record_open)
    config, report = fit_directory(tmp_path, min_observations=1)
    assert len(registered_shots()) == len(set(registered_shots())) == 174
    assert set(opened) == {"P01-A-p9.jpg", "P01-A-p4a.jpg"}
    assert report["status"] == "partial_photo_fit"
    assert report["frames_rejected"][0]["filename"] == "P01-A-p4a.jpg"
    assert config["jpeg"]["quality"] == [88, 88]
    assert config["geometry"]["long_edge_px"] == [target.height, target.height]
    assert config["hard_light"] == read_config()["hard_light"]
    assert "optics.defocus_sigma_px" in report["fitted"]
    assert "lighting.white_balance_r" in report["fitted"]
    assert "geometry.roll_deg" in report["fitted"]
    assert "geometry.crumple" in report["retained_priors"]
