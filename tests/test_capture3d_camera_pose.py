import hashlib
import json

import pytest

from experiments.capture3d.camera_pose import CameraPose


VALID = {"offset_m": [0.02, 0.2, 0.28], "roll_deg": -0.7, "lens_mm_equivalent": 25}


def test_camera_pose_uses_target_relative_metres():
    pose = CameraPose.from_record(VALID)
    assert pose.offset_m == (0.02, 0.2, 0.28)
    assert pose.roll_deg == -0.7
    assert pose.lens_mm_equivalent == 25


@pytest.mark.parametrize("record", [
    {"offset_m": [0, 0]},
    {"offset_m": [0, 0, 0.199]},
    {"offset_m": [0, float("inf"), 0.28]},
    {"offset_m": [False, 0, 0.28]},
    {"roll_deg": float("nan")},
    {"lens_mm_equivalent": 0},
    {"angle_deg": 1},
])
def test_camera_pose_rejects_invalid_or_ambiguous_records(record):
    with pytest.raises(ValueError):
        CameraPose.from_record({**VALID, **record})


def test_fiducial_uv_centres_are_the_drawn_pixel_centroids(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from PIL import Image

    from experiments.capture3d.batch import fiducials

    target = tmp_path / "uv.png"
    shape = (497, 739)
    measured = fiducials(shape, target, .0039)
    with Image.open(target) as image:
        mask = np.asarray(image)[:, :, 0].copy()
    count, _, _, centroids = cv2.connectedComponentsWithStats(mask)
    assert count == len(measured) + 1
    expected = (centroids[1:] + 0.5) / shape
    assert sorted(map(tuple, expected)) == sorted(measured)


def test_capture_accepts_geometry_only_regions_without_weakening_text_labels(tmp_path):
    pytest.importorskip("cv2")
    from PIL import Image

    from experiments.capture3d.batch import contextual_word_labels, source_rows

    image = tmp_path / "page.png"
    Image.new("RGB", (120, 180), "white").save(image)
    pin = hashlib.sha256(image.read_bytes()).hexdigest()
    region = {"id": "cell-0", "kind": "region", "bbox": [11, 22, 60, 70]}
    line = {"id": "line-0", "kind": "line", "bbox": [12, 26, 59, 31], "text": "סך"}
    manifest = {
        "split": "train-calibration", "text_gate_sha256": pin, "fonts_guard_sha256": pin,
        "pages": [{"id": "page-0", "image": image.name, "scene": "desk", "sha256": pin,
                   "font_sha256": pin, "annotations": [region, line]}],
    }
    path = tmp_path / "input.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    row, = source_rows(path)
    assert list(contextual_word_labels(row["annotations"])) == [region, line]

    region["text"] = "מוסתר"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Geometry-only region"):
        list(source_rows(path))
    del region["text"]
    del line["text"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid annotation text"):
        list(source_rows(path))
