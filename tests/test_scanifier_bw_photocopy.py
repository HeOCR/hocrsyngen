import json
import subprocess
import sys

import pytest
from PIL import Image, ImageDraw

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from experiments.scanifier_v2.bw_photocopy import NOMINAL, RANGES, bw_photocopy


def test_bilevel_seeded_views_keep_labels_and_geometry():
    page = Image.new("RGB", (900, 1200), "white")
    ImageDraw.Draw(page).rectangle((125, 280, 675, 295), fill="black")
    annotation = {"box": [100, 260, 700, 310], "label": "מס׳ 12 — א", "ordinal": 2}
    first = bw_photocopy(page, source_ppi=300, seed=17, nominal=True)
    repeat = bw_photocopy(page, source_ppi=300, seed=17, nominal=True)
    other = bw_photocopy(page, source_ppi=300, seed=19)
    assert first.parameters == NOMINAL
    assert first.photocopy_size == (300, 400)
    assert first.image.mode == "1"
    assert first.image.size == page.size
    assert first.image.tobytes() == repeat.image.tobytes()
    assert first.image.tobytes() != other.image.tobytes()
    assert all(low <= other.parameters[key] <= high for key, (low, high) in RANGES.items())
    mapped = first.annotation(annotation)
    assert mapped["label"] == annotation["label"]
    assert mapped["ordinal"] == annotation["ordinal"]
    assert mapped["box"] != annotation["box"]
    for x, y in first.warp.forward([[150, 287], [650, 287]]):
        patch = first.image.crop((round(x) - 3, round(y) - 3, round(x) + 4, round(y) + 4))
        assert 0 in patch.getextrema()
    assert first.warp.forward([[700, 600]])[0, 1] > 600  # clockwise
    assert np.allclose(first.warp.inverse(first.warp.forward([[500, 300]])), [[500, 300]])
    with pytest.raises(ValueError, match="clips"):
        first.annotation({"box": [0, 0, 30, 20], "label": "א"})


def test_direct_render_uses_working_ppi_and_preserves_white():
    source = Image.new("RGB", (2480, 3508), "white")
    resolutions = []

    def rasterize(ppi):
        resolutions.append(ppi)
        return Image.new("RGBA", (827, 1170), "white")

    view = bw_photocopy(source, source_ppi=300, seed=9, nominal=True, rasterize=rasterize)
    assert resolutions == [100]
    assert view.photocopy_size == (827, 1170)
    assert view.image.size == source.size
    assert view.image.getextrema() == (255, 255)
    with pytest.raises(ValueError, match="Direct render size"):
        bw_photocopy(source, source_ppi=300, seed=9, nominal=True, rasterize=lambda _: source)


def test_cli_writes_one_bit_png_and_unicode_sidecar(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "photocopy.png"
    annotations = tmp_path / "gold.json"
    Image.new("L", (600, 900), 255).save(source)
    annotations.write_text(json.dumps([{"box": [100, 100, 500, 200], "label": "א–ב"}]))
    subprocess.run([
        sys.executable, "-m", "experiments.scanifier_v2.bw_photocopy",
        str(source), str(output), "--source-ppi", "300", "--seed", "31",
        "--nominal", "--annotations", str(annotations),
    ], check=True)
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.mode == "1"
    actual = json.loads(output.with_suffix(".json").read_text())
    assert actual["profile"] == "bw_photocopy"
    assert actual["photocopy_size"] == [200, 300]
    assert actual["annotations"][0]["label"] == "א–ב"
