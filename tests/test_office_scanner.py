import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from PIL import Image, ImageDraw
from experiments.scanifier_v2.office_scanner import SCHEMA, render_office_scan


def test_office_scan_pins_profile_and_line_geometry(tmp_path):
    path = tmp_path / "office.json"
    path.write_text(json.dumps({
        "schema": SCHEMA, "scope": "private_development", "dpi": 300, "mode": "monochrome",
        "tone_lut": list(range(256)), "noise_sigma_lut": [0] * 256, "toner_gain": .5, "blur_sigma": 0,
        "skew_clockwise_degrees": {"dev01": [2], "other": [2]},
        "jpeg_encoder": {"qtables": [[3] * 64, [6] * 64], "subsampling": 2},
    }))
    image = Image.new("L", (150, 210), 255)
    ImageDraw.Draw(image).rectangle((30, 45, 105, 56), fill=10)
    lines = [{"id": "line-1", "text": "דוגמה", "box": [25, 40, 115, 62]}]
    result = render_office_scan(image, lines, profile_path=path, seed=5, source_ppi=300)
    repeat = render_office_scan(image, lines, profile_path=path, seed=5, source_ppi=300)
    assert result.image.size == image.size and result.image.tobytes() == repeat.image.tobytes()
    assert result.lines[0]["text"] == lines[0]["text"]
    assert result.parameters["skew_clockwise_deg"] == 2
    assert len(result.parameters["profile_sha256"]) == 64
    assert np.allclose(result.warp.inverse(result.lines[0]["box_polygon"]),
                       [(25, 40), (115, 40), (115, 62), (25, 62)])
    with pytest.raises(ValueError, match="300 PPI"):
        render_office_scan(image, lines, profile_path=path, seed=5, source_ppi=180)
