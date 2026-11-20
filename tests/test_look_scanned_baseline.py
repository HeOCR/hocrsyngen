from dataclasses import replace

from PIL import Image, ImageDraw
import pytest

np = pytest.importorskip("numpy")

from experiments.look_scanned_baseline import ScanEffects, apply_scan_effects


def test_neutral_effects_preserve_opaque_raster():
    source = Image.new("RGB", (5, 7), (35, 128, 210))
    result = apply_scan_effects(source, ScanEffects(), seed=0)
    assert result.image.tobytes() == source.tobytes()
    np.testing.assert_allclose(result.transform_points([(0, 0), (5, 7)]), [(0, 0), (5, 7)])


def test_crop_coordinates_follow_clockwise_rotation_and_scale():
    source = Image.new("L", (60, 60), 255)
    ImageDraw.Draw(source).rectangle((9, 19, 12, 22), fill=0)
    result = apply_scan_effects(source, ScanEffects(rotate_deg=90, scale=2, border=True), seed=4)
    assert result.image.size == (120, 120)
    np.testing.assert_allclose(result.transform_points([(11, 21)]), [(78, 22)])
    assert max(result.image.getpixel((78, 22))) < 30
    assert result.image.getpixel((50, 0)) == (0, 0, 0)
    assert result.image.getpixel((50, 1)) == (255, 255, 255)


def test_global_tone_and_seeded_grain():
    source = Image.new("RGB", (64, 64), (180, 155, 110))
    gray = ScanEffects(colorspace="gray", brightness=0.90, contrast=1.1)
    toned = apply_scan_effects(source, gray, seed=3).image.getpixel((32, 32))
    neutral_gray = apply_scan_effects(source, ScanEffects(colorspace="gray"), seed=3)
    assert toned[0] == toned[1] == toned[2] < neutral_gray.image.getpixel((32, 32))[0]
    settings = replace(gray, yellowish=0.4, noise_stddev=0.02, rotate_deg=-1, rotate_variance_deg=2)
    one = apply_scan_effects(source, settings, seed=1)
    repeat = apply_scan_effects(source, settings, seed=1)
    other = apply_scan_effects(source, settings, seed=2)
    assert -1 <= one.rotation_deg < 1
    assert one.rotation_deg == repeat.rotation_deg != other.rotation_deg
    assert one.image.tobytes() == repeat.image.tobytes() != other.image.tobytes()
    r, g, b = one.image.getpixel((32, 32))
    assert r > g > b


@pytest.mark.parametrize("values", [{"scale": 0}, {"yellowish": 1.1}, {"blur_px": float("nan")}])
def test_invalid_effects_rejected(values):
    with pytest.raises(ValueError):
        ScanEffects(**values)
