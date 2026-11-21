"""Contract checks for opt-in training augmentations, not OCR evaluation."""
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
from PIL import Image, ImageDraw

from experiments.scanifier_v2 import degradations as d


@pytest.fixture
def page():
    return Image.new('RGB', (200, 300), 'white')


@pytest.mark.parametrize('effect,kwargs', [
    (d.paper_tint, {}), (d.scanner_artifacts, {}), (d.thumb_occlusion, {}),
    (d.spatial_noise, {}), (d.recompress, {'long_edge': (128, 128)}),
])
def test_seeded_effects(page, effect, kwargs):
    a = np.asarray(effect(page, seed=12, **kwargs))
    b = np.asarray(effect(page, seed=12, **kwargs))
    assert np.array_equal(a, b)
    assert not np.array_equal(a, np.asarray(page))
    assert np.array_equal(np.asarray(page), np.full((300, 200, 3), 255, dtype=np.uint8))


def test_reverse_page_is_mirrored_and_offset_does_not_wrap(page):
    reverse = Image.new('L', page.size, 'white')
    ImageDraw.Draw(reverse).rectangle((10, 20, 30, 40), fill='black')
    result = np.asarray(d.show_through(page, reverse, 1, opacity=(0.5, 0.5),
                                       blur_px=(0, 0), offset_fraction=(0, 0)))
    assert result[30, 180, 0] < 200
    assert result[30, 20, 0] == 255
    assert np.array_equal(result, np.asarray(d.show_through(page, reverse, 1, opacity=(0.5, 0.5),
                                                           blur_px=(0, 0), offset_fraction=(0, 0))))


def test_zero_strength_and_invalid_ranges(page):
    assert np.array_equal(np.asarray(page), np.asarray(d.paper_tint(page, 1, strength=(0, 0))))
    assert np.array_equal(np.asarray(page), np.asarray(d.spatial_noise(page, 1, sigma=(0, 0))))
    with pytest.raises(ValueError):
        d.scanner_artifacts(page, 1, bars=(1.2, 3))
    with pytest.raises(ValueError):
        d.recompress(page, 1, quality=(0, 90))
    with pytest.raises(ValueError):
        d.show_through(page, page, 1, opacity=(0.2, float('nan')))


def test_recompression_downsizes_only(page):
    assert d.recompress(page, 0, long_edge=(128, 128)).size == (85, 128)
    assert d.recompress(page, 0, long_edge=(1280, 1280)).size == page.size


def test_optics_and_rotation(page):
    ImageDraw.Draw(page).rectangle((10, 10, 20, 20), fill="black")
    for effect in (d.motion_blur, d.edge_defocus):
        assert np.array_equal(np.asarray(effect(page, 2)), np.asarray(effect(page, 2)))
        assert not np.array_equal(np.asarray(effect(page, 2)), np.asarray(page))
    page.getexif()[274] = 6
    rotated = d.rotated_save(page, 3, turns=(1,))
    assert rotated.size == (300, 200)
    assert 274 not in rotated.getexif()
