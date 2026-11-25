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
