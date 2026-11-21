"""Exercise the measurement path with controlled pixel fixtures."""
import pytest
from PIL import Image, ImageDraw

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from experiments.scanifier_v2.degradations import show_through
from experiments.scanifier_v2.fit_old_print import measure_bands, measure_show_through


def test_scanner_crops_distinguish_border_and_partial_bar():
    raster = np.full((100, 160), 220, dtype=np.uint8)
    raster[:, :5] = 20
    raster[8:92, 100:104] = 35
    raster[40:44, 30:50] = 35
    result = measure_bands(raster)
    assert [item["side"] for item in result["edges"]] == ["left"]
    assert result["edges"][0]["edge_fraction"] == pytest.approx(5 / 160)
    assert [item["axis"] for item in result["bars"]] == ["vertical"]
    assert result["bars"][0]["bar_fraction"] == pytest.approx(4 / 160)
    assert result["bars"][0]["bar_span"] == pytest.approx(0.84)


def test_duplex_fit_accepts_mirrored_reverse_and_rejects_clean_front():
    front = Image.new("RGB", (272, 360), "white")
    reverse = front.copy()
    rng = np.random.default_rng(18)
    for image in (front, reverse):
        draw = ImageDraw.Draw(image)
        for _ in range(120):
            x, y = rng.integers((20, 20), (238, 332))
            draw.rectangle((x, y, x + 5, y + 6), fill="black")

    with_ghost = show_through(front, reverse, 51, opacity=(0.08, 0.08),
                              blur_px=(0.8, 0.8), offset_fraction=(0, 0))
    back = np.asarray(reverse.convert("L"))
    fitted = measure_show_through(np.asarray(with_ghost.convert("L")), back, 1)
    assert fitted is not None
    assert fitted["opacity"] == pytest.approx(0.08, abs=0.01)
    assert fitted["offset_x_fraction"] == fitted["offset_y_fraction"] == 0
    assert measure_show_through(np.asarray(front.convert("L")), back, 1) is None
