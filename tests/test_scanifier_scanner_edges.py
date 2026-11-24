"""Geometry and stream independence checks for the scanner family."""
import pytest
from PIL import Image

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from experiments.scanifier_v2.degradations import scanner_edge_bars


@pytest.mark.parametrize("side", ["left", "right", "top", "bottom"])
def test_scanner_edge_changes_only_the_selected_side(side):
    page = Image.new("RGB", (120, 100), "white")
    options = dict(edge_sides=(side,), edge_fraction=(0.1, 0.1),
                   edge_taper=(0, 0), edge_darkness=(1, 1), bar_count=(0, 0), feather_px=(0, 0))
    output = scanner_edge_bars(page, 42, **options)
    expected = np.full((100, 120, 3), 255, np.uint8)
    if side == "left":
        expected[:, :12] = 0
    elif side == "right":
        expected[:, -12:] = 0
    elif side == "top":
        expected[:10, :] = 0
    else:
        expected[-10:, :] = 0
    np.testing.assert_array_equal(output, expected)
    assert output.size == page.size and page.getpixel((0, 0)) == (255, 255, 255)


def test_disabling_edge_preserves_seeded_bar_placement():
    page = Image.new("RGB", (160, 100), "white")
    options = dict(edge_fraction=(0.1, 0.1), edge_taper=(0, 0),
                   bar_axes=("horizontal",), bar_fraction=(0.04, 0.04),
                   bar_count=(1, 1), bar_span=(0.7, 0.7), feather_px=(0, 0))
    bars = np.asarray(scanner_edge_bars(page, 2, edge_sides=(), **options))
    both = np.asarray(scanner_edge_bars(page, 2, edge_sides=("left",), **options))
    np.testing.assert_array_equal(both[:, 16:], bars[:, 16:])
    locations = np.argwhere(bars[:, :, 0] < 200)
    assert 2 <= np.ptp(locations[:, 0]) <= 4
    assert 108 <= np.ptp(locations[:, 1]) <= 113
