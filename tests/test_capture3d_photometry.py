import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from PIL import Image
from experiments.capture3d.batch import phone_jpeg
from experiments.capture3d.photometry import PhonePhotometry


def test_profile_controls_jpeg_without_changing_pixel_grid(tmp_path):
    profile_file = tmp_path / "profile.json"
    profile_file.write_text(json.dumps({
        "tone_curve": [[0, 0], [100, 100], [255, 200]],
        "jpeg_tables": [[7] * 64, [11] * 64],
        "luma_noise_sd": 1,
        "blank_reverse": True,
    }))
    profile = PhonePhotometry.read(profile_file)
    assert profile.blank_reverse
    pixels = np.full((26, 23, 3), 255, dtype=np.uint8)
    settings = {"k1": 0, "noise_strength": 0, "jpeg_quality": 94}
    first, second, original, empty = (tmp_path / f"{name}.jpg" for name in ("a", "b", "c", "d"))
    phone_jpeg(pixels, settings, 5, first, profile)
    phone_jpeg(pixels, settings, 5, second, profile)
    phone_jpeg(pixels, settings, 5, original)
    phone_jpeg(pixels, settings, 5, empty, PhonePhotometry())
    assert original.read_bytes() == empty.read_bytes()
    assert first.read_bytes() == second.read_bytes()
    with Image.open(first) as decoded:
        assert decoded.size == (23, 26)
        assert decoded.quantization == {0: [7] * 64, 1: [11] * 64}
        assert 195 < np.mean(decoded) < 205


@pytest.mark.parametrize("invalid", [
    {"tone_curve": [[0, 10], [255, 0]]},
    {"jpeg_tables": [[7] * 64]},
    {"sensor_noise_scale": float("inf")},
    {"blank_reverse": 1},
    {"exposure": 2},
])
def test_invalid_profile_fails(tmp_path, invalid):
    profile_file = tmp_path / "profile.json"
    profile_file.write_text(json.dumps(invalid))
    with pytest.raises(ValueError):
        PhonePhotometry.read(profile_file)


def test_local_tone_lifts_shadows_without_compressing_local_ink_contrast():
    rgb = np.full((128, 128, 3), .8, dtype=np.float32)
    rgb[:, :64] = .4
    rgb[60:67, 28:35] = .1
    profile = PhonePhotometry(tone_curve=((0, 0), (102, 153), (204, 180), (255, 210)),
                              local_tone_radius=.09)
    mapped = profile.apply_tone(rgb)
    assert abs(float(mapped[64, 30, 0] - mapped[64, 40, 0]) + .3) < .01
    assert float(mapped[64, 96, 0] - mapped[64, 40, 0]) < .15
