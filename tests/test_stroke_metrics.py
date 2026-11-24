import pytest
from PIL import Image, ImageDraw

pytest.importorskip("numpy")
pytest.importorskip("scipy")
from hocrsyngen import stroke_metrics as sm  # noqa: E402  (optional extra: pip install hocrsyngen[metrics])


def _strokes(width, height=40, n=6, w=300):
    img = Image.new("L", (w, height + 20), 255)
    d = ImageDraw.Draw(img)
    for i in range(n):
        x = 20 + i * 45
        d.rectangle([x, 10, x + width - 1, 10 + height - 1], fill=0)
    return img


def test_measures_known_stroke_and_height():
    m = sm.measure(_strokes(6))
    assert abs(m["stroke"] - 6) <= 1.5
    assert abs(m["body"] - 40) <= 1


def test_thinner_strokes_have_lower_rel():
    assert sm.measure(_strokes(4))["rel"] < sm.measure(_strokes(8))["rel"]


def test_compare_flags_a_thinner_set(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    for i in range(3):
        _strokes(4).save(tmp_path / "a" / f"{i}.png")
        _strokes(7).save(tmp_path / "b" / f"{i}.png")
    r = sm.compare(sorted((tmp_path / "a").glob("*.png")), sorted((tmp_path / "b").glob("*.png")))
    assert not r["pass"] and r["rel_gap"] > 0.2


def test_greyscale_and_binary_images_measure_alike():
    binary = _strokes(6)
    grey = binary.point(lambda v: 40 if v == 0 else 230)
    assert abs(sm.measure(binary)["stroke"] - sm.measure(grey)["stroke"]) <= 1
