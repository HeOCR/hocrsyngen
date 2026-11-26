import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

pytest.importorskip("cv2")

from experiments.capture3d import batch


def test_invisible_clean_arm_has_no_marker_png(tmp_path, monkeypatch):
    image = tmp_path / "page.png"
    Image.new("RGB", (150, 210), "white").save(image)
    job = tmp_path / "input.json"
    job.write_text(json.dumps({
        "split": "train-calibration", "text_gate_sha256": "0" * 64,
        "fonts_guard_sha256": "1" * 64,
        "pages": [{"id": "paper", "scene": "desk", "sha256": batch.sha(image),
                   "font_sha256": "2" * 64, "image": image.name, "seed": 3,
                   "annotations": [{"id": "line", "kind": "line", "text": "דף",
                                    "bbox": [20, 30, 120, 40]}]}],
    }))
    assets = tmp_path / "assets.json"
    assets.write_text(json.dumps({role: {"path": image.name, "sha256": batch.sha(image), "licence": "CC0-1.0"}
                                  for role in ("desk", "floor", "environment")}))

    def reject_frame(command, **_):
        requested = json.loads(Path(command[-1]).read_text())
        case, = requested["cases"]
        assert case["arm"] == "clean"
        batch.json_write(Path(requested["result"]), {"rows": [{
            "id": case["id"], "pair_id": case["pair_id"], "scene": case["scene"],
            "rejected_regions": ["line"], "marker_positions": [[10, 10]],
        }]})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(batch.subprocess, "run", reject_frame)
    with pytest.raises(ValueError, match="Every render failed the frame or visibility threshold"):
        batch.run(job, assets, tmp_path / "out", "blender", "CPU", (300, 400), 2, .65,
                  realism_seed=4, developable_paper=True, clean_arm_only=True)
