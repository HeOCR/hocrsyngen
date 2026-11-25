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
