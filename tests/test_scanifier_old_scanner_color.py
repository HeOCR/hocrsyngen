import json
import subprocess
import sys

import pytest
from PIL import Image, ImageDraw

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from experiments.scanifier_v2.old_scanner_color import NOMINAL, _parameters, old_scanner_color


def test_nominal_color_has_yellow_paper_and_seeded_grain():
    page = Image.new("RGB", (900, 1200), "white")
    actual = old_scanner_color(page, source_ppi=300, seed=19, nominal=True)
    repeated = old_scanner_color(page, source_ppi=300, seed=19, nominal=True)
    different = old_scanner_color(page, source_ppi=300, seed=20, nominal=True)
    assert actual.parameters == {**NOMINAL, "rotate_deg": -1.6}
    assert actual.scan_size == (231, 308)
    assert actual.image.mode == "RGB"
    assert actual.image.size == page.size
    assert actual.image.tobytes() == repeated.image.tobytes()
    assert actual.image.tobytes() != different.image.tobytes()
    red, green, blue = np.moveaxis(np.asarray(actual.image)[30:-30, 30:-30], -1, 0)
    assert np.median(red) == np.median(green) >= 254
    assert 243 <= np.median(blue) <= 246
    assert red.std() > 2


def test_sampled_color_preserves_source_labels_and_geometry():
    page = Image.new("RGB", (600, 900), "white")
    ImageDraw.Draw(page).rectangle((140, 310, 380, 340), fill="#18243b")
    view = old_scanner_color(page, source_ppi=300, seed=43)
    params = view.parameters
    assert 77 <= params["ppi"] <= 160
    assert abs(params["rotate_deg"] - params["rotate_base_deg"]) <= params["rotate_var_deg"]
    x, y = view.warp.forward([[260, 325]])[0]
    pixel = view.image.getpixel((round(x), round(y)))
    assert max(pixel) < 110
    label = {"box": [130, 290, 395, 355], "label": "א–ב ״ש", "ordinal": 3}
    annotation = view.annotation(label)
    assert annotation["label"] == label["label"]
    assert annotation["ordinal"] == label["ordinal"]
    assert annotation["box"] != label["box"]
    with pytest.raises(ValueError, match="clips"):
        view.annotation({"box": [0, 0, 15, 15], "text": "א"})


def test_severity_ramps_color_and_preserves_the_hard_reference():
    page = Image.new("RGB", (900, 1200), "white")
    views = [old_scanner_color(page, source_ppi=300, seed=19, severity=s) for s in (0.2, 0.575, 1.0)]
    assert [view.parameters["ppi"] for view in views] == [150, 122, 77]
    for key in ("yellowish", "noise", "blur_px"):
        mild, medium, hard = [view.parameters[key] for view in views]
        assert mild < medium < hard
    cores = [np.asarray(view.image)[30:-30, 30:-30] for view in views]
    white_blue = [np.median(core[..., 2]) for core in cores]
    red_grain = [core[..., 0].std() for core in cores]
    assert white_blue[0] > white_blue[1] > white_blue[2]
    assert red_grain[0] < red_grain[1] < red_grain[2]
    reference = old_scanner_color(page, source_ppi=300, seed=19, nominal=True)
    assert views[2].image.tobytes() == reference.image.tobytes()


def test_default_color_mix_favours_mild_and_medium():
    severity = [_parameters(seed, None)["severity"] for seed in range(1024)]
    counts, _ = np.histogram(severity, bins=[0, 0.4, 0.75, 1])
    mild, medium, hard = counts / len(severity)
    assert 0.5 < mild < 0.6
    assert 0.3 < medium < 0.4
    assert 0.07 < hard < 0.13


def test_cli_writes_rgb_png_and_geometry(tmp_path):
    source, output, gold = (tmp_path / p for p in ("clean.png", "scan.png", "text.json"))
    Image.new("RGB", (600, 900), "white").save(source)
    gold.write_text(json.dumps([{"box": [100, 100, 500, 200], "text": "אב – גד"}]))
    subprocess.run([
        sys.executable, "-m", "experiments.scanifier_v2.old_scanner_color",
        str(source), str(output), "--source-ppi", "300", "--seed", "12", "--nominal",
        "--annotations", str(gold),
    ], check=True)
    with Image.open(output) as im:
        assert (im.format, im.mode) == ("PNG", "RGB")
    metadata = json.loads(output.with_suffix(".json").read_text())
    assert metadata["profile"] == "old_scanner_color"
    assert metadata["scan_size"] == [154, 231]
    assert metadata["annotations"][0]["text"] == "אב – גד"
