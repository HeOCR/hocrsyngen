import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")
from PIL import Image  # noqa: E402

from hocrsyngen import halo_metrics as H  # noqa: E402


def _page(halo: bool) -> Image.Image:
    g = np.full((120, 200), 240, np.uint8)
    for x0 in (20, 80, 140):
        if halo:
            g[30:90, x0 - 6:x0 + 26] = 215  # pasted patch background: a grey box around the glyph
        g[40:80, x0:x0 + 20] = 20  # the glyph
    return Image.fromarray(g)


def test_clean_composite_has_no_halo():
    m = H.measure(_page(False))
    assert m is not None and abs(m["ring_minus_open"]) < 0.5


def test_pasted_background_shows_a_halo():
    m = H.measure(_page(True))
    assert m is not None and m["ring_minus_open"] < -10


def test_cli_exit_codes(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _page(False).save(a); _page(True).save(b)
    assert H.main([str(a)]) == 0
    assert H.main([str(b)]) == 1
