import json
from pathlib import Path

import pytest

from hocrsyngen import font_exclusion as fx
from hocrsyngen.generator import _font_path, _load_font


def test_exclusion_list_names_the_held_out_faces():
    data = json.loads(fx.EXCLUSION_PATH.read_text(encoding="utf-8"))
    assert data["schema"] == "heocr_font_exclusion.v1"
    assert {f["family"] for f in data["families"]} == {
        "Drugulin CLM", "Simple CLM", "Aharoni CLM", "Ellinia CLM", "Keter YG", "Shofar", "Yehuda CLM",
    }
    assert len({row["sha256"] for face in data["families"] for row in face["files"]}) == 23
    assert all(fx.is_excluded(face) for face in ("Aharoni CLM", "Keter YG", "Shofar", "Ellinia CLM", "Yehuda CLM"))
    assert all(len(x["sha256"]) == 64 for f in data["families"] for x in f["files"])


@pytest.mark.parametrize("font", ["Drugulin CLM", "Simple CLM", "SimpleCLM-Medium.ttf", "/x/DrugulinCLM-Bold.otf",
                                  "simple-clm-bold.ttf"])
def test_held_out_faces_are_refused(font, monkeypatch):
    monkeypatch.delenv(fx.EVAL_ENV, raising=False)
    with pytest.raises(fx.HeldOutFontError):
        fx.check_font(font)


def test_refused_by_sha256_under_another_name(tmp_path, monkeypatch):
    monkeypatch.delenv(fx.EVAL_ENV, raising=False)
    sha = json.loads(fx.EXCLUSION_PATH.read_text())["families"][0]["files"][0]["sha256"]
    monkeypatch.setattr(fx, "_sha256", lambda p: sha)
    renamed = tmp_path / "renamed.otf"
    renamed.write_bytes(b"x")
    with pytest.raises(fx.HeldOutFontError):
        fx.check_font(renamed)


def test_shipped_fonts_pass_and_eval_renders_may_use_held_out_faces(monkeypatch):
    monkeypatch.delenv(fx.EVAL_ENV, raising=False)
    fonts = Path(fx.__file__).with_name("data") / "synthetic" / "fonts"
    for f in sorted(fonts.glob("*.ttf")):
        assert fx.check_font(f) == f
    monkeypatch.setenv(fx.EVAL_ENV, "1")
    assert fx.check_font("Simple CLM") == "Simple CLM"


def test_generator_font_loading_is_guarded(tmp_path, monkeypatch):
    monkeypatch.delenv(fx.EVAL_ENV, raising=False)
    held = tmp_path / "SimpleCLM-Medium.ttf"
    held.write_bytes(b"not a font")
    with pytest.raises(fx.HeldOutFontError):
        _font_path(tmp_path / "manifest.yaml", {"id": "simple", "file": held.name})
    with pytest.raises(fx.HeldOutFontError):
        _load_font(held, 16)


@pytest.mark.parametrize("preset", ["modern_print_scan_v1", "handwriting_v1"])
def test_governed_faces_refuse_a_held_out_face(tmp_path, monkeypatch, preset):
    """render-lines and office pages take faces from governed_faces(): a manifest that lists a held-out face fails."""
    import hashlib

    from hocrsyngen.line_render import governed_faces

    monkeypatch.delenv(fx.EVAL_ENV, raising=False)
    font = tmp_path / "SimpleCLM-Medium.ttf"
    font.write_bytes(b"not a real font")
    (tmp_path / "LICENSE.txt").write_text("x", encoding="utf-8")
    sha = hashlib.sha256(font.read_bytes()).hexdigest()
    (tmp_path / "manifest.yaml").write_text(
        "fonts:\n  - id: renamed-face\n    file: SimpleCLM-Medium.ttf\n    style: x\n    license: GPL-2.0\n"
        f"    license_file: LICENSE.txt\n    sha256: {sha}\n    line_render: true\n    handwriting_line_render: true\n",
        encoding="utf-8")
    with pytest.raises(fx.HeldOutFontError):
        governed_faces(tmp_path / "manifest.yaml", preset=preset)
    monkeypatch.setenv(fx.EVAL_ENV, "1")
    assert list(governed_faces(tmp_path / "manifest.yaml", preset=preset)) == ["renamed-face"]
