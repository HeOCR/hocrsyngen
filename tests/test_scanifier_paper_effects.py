import numpy as np

from experiments.scanifier_v2.paper_effects import Crease, CreaseWarp, ShadowBand, cast_shadow, paper_texture, tone
from experiments.scanifier_v2.paper_scene import linear


def test_paper_grain_and_stains_are_seeded_and_stay_on_the_sheet():
    mask = np.zeros((240, 202), np.float32)
    mask[23:-18, 25:-32] = 1
    first, marks = paper_texture(mask, 19, 1.2)
    replay, _ = paper_texture(mask, 19, 1.2)
    alternate, _ = paper_texture(mask, 23, 1.2)
    assert len(marks) == 6
    assert np.array_equal(first, replay) and not np.array_equal(first, alternate)
    assert np.all(first[mask == 0] == 1)
    assert np.std(first[mask == 1]) > .04


def test_hard_shadow_cast_applies_equally_to_light_paper_and_ink():
    shape = (180, 150)
    bands = [ShadowBand((75, 75), 0, 6)]
    gain, coverage = cast_shadow(shape[::-1], bands, (.24,.24,.24))
    rgb = np.full((*shape, 3), 222, np.uint8)
    rgb[:, 70:79] = 75
    final = tone(rgb, gain)
    paper = linear(final[95, 10, 0]) / linear(rgb[95, 10, 0])
    ink = linear(final[95, 74, 0]) / linear(rgb[95, 74, 0])
    assert abs(paper-ink) < .015
    assert .22 < paper < .26
    assert np.count_nonzero((coverage[:, 70] > 0) & (coverage[:,70] < 1)) == 5
    assert np.array_equal(rgb[:50], final[:50])


def test_projected_crease_moves_lines_but_preserves_its_support():
    mask = np.zeros((240, 300), np.float32)
    mask[38:-40, 32:-30] = 1
    warp = CreaseWarp(mask, [Crease((140,115), 7, 45, .40, .55),
                             Crease((160,120), 100, 20, .25, .40)])
    points = np.array([[34.,23.], [176.,143.], [142.,135.], [172.,101.], [279.,215.]])
    moved = warp.forward(points)
    assert np.linalg.norm(points - moved, axis=1).max() > 4
    assert np.linalg.norm(warp.inverse(moved) - points, axis=1).max() < .01
    assert np.array_equal(points[[0,4]], moved[[0,4]])
    rgb = np.random.default_rng(23).integers(0,256,(*mask.shape,3),dtype=np.uint8)
    result = warp.remap(rgb)
    assert np.array_equal(rgb[mask == 0], result[mask == 0])
    assert np.min(warp.illumination[mask > .5]) < .67
    flat = np.zeros((*mask.shape,3), dtype=np.uint8)
    flat[125:145,150:175] = 220
    recovered = warp.rectify(warp.remap(flat))
    assert (recovered[129:141,154:171] > 205).all()
