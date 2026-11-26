import numpy as np
from PIL import Image
import pytest

cv = pytest.importorskip("cv2")

from experiments.scanifier_v2.paper_scene import (Gutter, Phone, gutter_scan, halo_residual,
                                                    linear, near_phone, sdxl_shared_relight)


@pytest.mark.parametrize("side", ("left", "right"))
def test_cylindrical_gutter_foreshortens_and_roundtrips(side):
    warp = Gutter((400, 500), side)
    x = np.array([0., 6., 100., 235., 390., 399.])
    y = np.array([10., 53., 200., 450., 190., 471.])
    px, py = warp.forward_xy(x, y)
    rx, ry = warp.inverse_xy(px, py)
    assert np.allclose(rx, x) and np.allclose(ry, y)
    spine_pair = (0, 1) if side == "left" else (4, 5)
    assert np.diff(px[list(spine_pair)])[0] < .6 * np.diff(x[list(spine_pair)])[0]
    image = np.asarray(gutter_scan(Image.new("RGB", warp.size, "white"), warp, seed=19))
    scan = image[image.shape[0] // 2, :, 0].astype(int)
    spine = int(warp.facing if side == "left" else warp.section - 1)
    outside = 1 if side == "left" else -1
    assert scan[spine] < scan[spine + outside * 22] < scan[spine + outside * 70]
    assert np.max(np.abs(np.diff(scan))) < 19


def test_phone_roundtrip_and_textured_support():
    warp = Phone((82, 112), (172, 216), ((.24,.14),(.74,.19),(.86,.86),(.17,.90)), .025, -.03)
    x, y = np.meshgrid([0., 28., 76.], [0., 43., 101.])
    px, py = warp.forward_xy(x, y)
    rx, ry = warp.inverse_xy(px, py)
    assert np.allclose(rx, x) and np.allclose(ry, y)
    texture = np.zeros((61, 91, 3), dtype=np.uint8)
    texture[:] = 62
    texture[:, 37:55] = 109
    paper = Image.new("RGB", warp.source_size, "white")
    result = near_phone(paper, texture, warp, 9, (1,1,1), (11,5))
    pixels = np.asarray(result)
    assert result.tobytes() == near_phone(paper, texture, warp, 9, (1,1,1), (11,5)).tobytes()
    assert abs(float(pixels[5, :, 0].max()) - float(pixels[5, :, 0].min())) > 20
    assert np.linalg.norm(pixels[110, 85].astype(float) - pixels[13, 13]) > 90


def test_gutter_duplex_preserves_control_and_mirrors_reverse_ink():
    warp = Gutter((320, 400), "left")
    paper = Image.new("RGB", warp.size, "white")
    reverse = np.asarray(paper).copy()
    reverse[178:222, 42:66] = 0
    reverse = Image.fromarray(reverse)
    control = gutter_scan(paper, warp, 91)
    assert control.tobytes() == gutter_scan(paper, warp, 91, reverse=reverse,
                                          duplex_strength=0).tobytes()
    legacy = gutter_scan(paper, warp, 91, reverse=reverse)
    assert legacy.tobytes() == gutter_scan(paper, warp, 91, reverse=reverse,
                                         duplex_strength=.086, duplex_blur_sigma=2.2).tobytes()
    strong = gutter_scan(paper, warp, 91, reverse=reverse, duplex_strength=.24)
    x, y = warp.forward_xy(320 - 1 - 54, 200)
    mirror = (round(x), round(y))
    assert strong.getpixel(mirror)[0] < legacy.getpixel(mirror)[0] < control.getpixel(mirror)[0]
    x, y = warp.forward_xy(54, 200)
    direct = (round(x), round(y))
    assert strong.getpixel(direct) == control.getpixel(direct)


def test_shared_light_changes_ink_under_legacy_protection():
    native = np.full((210, 200, 3), 198, np.uint8)
    native[80:84, 35:165] = 92
    edited = np.full_like(native, 179)
    excluded = np.zeros(native.shape[:2], bool)
    excluded[64:98, 20:180] = True
    edited[75:89, 29:171] = native[75:89, 29:171]
    page = np.ones(native.shape[:2], np.uint8)
    relit, gain = sdxl_shared_relight(native, edited, page, excluded)
    assert np.max(np.abs(linear(relit) - linear(native) * gain)) < .005
    assert not np.array_equal(native[excluded], relit[excluded])
    glyphs = native[:, :, 0] < 100
    before = halo_residual(edited, native, glyphs, page.astype(bool))
    after = halo_residual(relit, native, glyphs, page.astype(bool))
    assert after["p95_abs"] < before["p95_abs"] * .5
