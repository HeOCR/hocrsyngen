from __future__ import annotations

import hashlib
import json
import random
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageFont, ImageStat, features

from hocrsyngen.assets import default_font_manifest_path
from hocrsyngen.cli import main
from hocrsyngen.line_render import (
    LINE_PRESETS,
    governed_faces,
    read_lines,
    render_line,
    render_lines,
)

pytestmark = pytest.mark.skipif(not features.check("raqm"), reason="needs Pillow with libraqm (see AGENTS.md)")

SIZE = 40


def _template(face, ch):
    f = ImageFont.truetype(str(face.path), SIZE, layout_engine=ImageFont.Layout.RAQM)
    m = f.getmask(ch, mode="L")
    t = Image.frombytes("L", m.size, bytes(m))
    return ImageChops.invert(t)


def _best_x(img, tmpl):
    """x centre of the best (lowest mean absolute difference) placement of tmpl in img."""
    best = None
    tw, th = tmpl.size
    for y in range(0, img.height - th + 1):
        for x in range(0, img.width - tw + 1):
            d = ImageStat.Stat(ImageChops.difference(img.crop((x, y, x + tw, y + th)), tmpl)).mean[0]
            if best is None or d < best[0]:
                best = (d, x + tw / 2)
    return best[1]


def _plain(text, face_id="frank-ruhl-libre"):
    face = governed_faces()[face_id]
    img, _ = render_line(text, face, SIZE, "none", random.Random(0))
    return img, face


def test_rtl_line_with_number_and_brackets_reads_in_visual_order():
    # logical: alef, space, "12", space, "(", bet, ")"  ->  visual left to right: ( bet ) 1 2 ... alef
    img, face = _plain("א 12 (ב)")
    x = {c: _best_x(img, _template(face, c)) for c in ("א", "ב", "1", "2", "(", ")")}
    assert x["("] < x["ב"] < x[")"] < x["1"] < x["2"] < x["א"], x


def test_order_check_rejects_a_naively_reversed_line():
    # Negative control for the check above: reversing the string and drawing it without bidi (a common mistake)
    # puts the digits as "21" and leaves the brackets unmirrored, and the same order assertion must fail.
    from PIL import ImageDraw
    face = governed_faces()["frank-ruhl-libre"]
    f = ImageFont.truetype(str(face.path), SIZE, layout_engine=ImageFont.Layout.BASIC)
    img = Image.new("L", (300, 70), 255)
    ImageDraw.Draw(img).text((10, 5), "א 12 (ב)"[::-1], font=f, fill=0)
    x = {c: _best_x(img, _template(face, c)) for c in ("א", "ב", "1", "2", "(", ")")}
    assert not (x["("] < x["ב"] < x[")"] < x["1"] < x["2"] < x["א"]), x


def test_latin_run_stays_left_to_right_inside_hebrew():
    img, face = _plain("ש ABC ת")
    x = {c: _best_x(img, _template(face, c)) for c in ("ש", "A", "B", "C", "ת")}
    assert x["ת"] < x["A"] < x["B"] < x["C"] < x["ש"], x


def test_date_with_dots_keeps_digit_order():
    img, face = _plain("ב 3.5")
    x = {c: _best_x(img, _template(face, c)) for c in ("ב", "3", "5")}
    assert x["3"] < x["5"] < x["ב"], x


def _write(tmp_path, rows):
    p = tmp_path / "in.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


ROWS = [{"id": f"l{i:03d}", "text": t} for i, t in enumerate(
    ["לפי סעיף 12(א) לחוק", "הישיבה ה-345, יום ב' 3.5.1993", "ועדת ABC [ראו נספח]", "שלום עולם", "חוק הבחירות"] * 3)]


def test_provenance_labels_and_balance(tmp_path):
    out = tmp_path / "out"
    s = render_lines(read_lines(_write(tmp_path, ROWS)), out, seed=11)
    faces = governed_faces()
    assert s["rendered"] == len(ROWS) and not s["refused"]
    counts = list(s["by_font"].values())
    assert set(s["by_font"]) == set(faces) and max(counts) - min(counts) <= 1
    man = [json.loads(l) for l in (out / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    for r, src in zip(man, ROWS):
        assert r["id"] == src["id"] and r["synthetic"] == "rendered" and r["label_order"] == "logical"
        assert (out / r["label"]).read_text(encoding="utf-8").strip() == src["text"]
        f = faces[r["font"]["id"]]
        assert r["font"]["sha256"] == f.sha256 == hashlib.sha256(f.path.read_bytes()).hexdigest()
        assert r["font"]["license"] == "OFL-1.1" and r["font"]["license_file"]
        assert r["preset"] == "modern_print_scan_v1" and r["seed"] == 11 and set(r["preset_params"]) >= {"blur", "grain", "jpeg"}
        assert Image.open(out / r["image"]).mode == "L"
    assert s["font_manifest_sha256"] == hashlib.sha256(default_font_manifest_path().read_bytes()).hexdigest()


def test_deterministic_per_line_independent_of_batch(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    render_lines(ROWS, a, seed=5, preset="modern_print_scan_v1_small_inky")
    render_lines(list(reversed(ROWS[:4])) + ROWS[4:], b, seed=5, preset="modern_print_scan_v1_small_inky", fonts=None)
    ma = {json.loads(l)["id"]: json.loads(l) for l in (a / "manifest.jsonl").read_text().splitlines()}
    mb = {json.loads(l)["id"]: json.loads(l) for l in (b / "manifest.jsonl").read_text().splitlines()}
    same_font = [i for i in ma if ma[i]["font"]["id"] == mb[i]["font"]["id"]]
    assert same_font
    for i in same_font:
        assert (a / "lines" / f"{i}.png").read_bytes() == (b / "lines" / f"{i}.png").read_bytes()
    c = tmp_path / "c"
    render_lines(ROWS, c, seed=5, preset="modern_print_scan_v1_small_inky")
    for r in ROWS:
        assert (a / "lines" / f"{r['id']}.png").read_bytes() == (c / "lines" / f"{r['id']}.png").read_bytes()


def test_every_preset_renders(tmp_path):
    for p in LINE_PRESETS:
        s = render_lines(ROWS[:3], tmp_path / p, seed=1, preset=p)
        assert s["rendered"] == 3


def test_refuses_ungoverned_and_unknown_fonts_and_presets(tmp_path):
    with pytest.raises(ValueError, match="not governed"):
        render_lines(ROWS[:1], tmp_path / "x", seed=1, fonts=["gveret-levin-regular"])
    with pytest.raises(ValueError, match="not governed"):
        render_lines(ROWS[:1], tmp_path / "x", seed=1, fonts=["no-such-font"])
    with pytest.raises(ValueError, match="unknown preset"):
        render_lines(ROWS[:1], tmp_path / "x", seed=1, preset="heavy")


def test_refuses_face_whose_file_does_not_match_its_sha(tmp_path):
    src = default_font_manifest_path().parent
    d = tmp_path / "fonts"; shutil.copytree(src, d)
    (d / "Alef-Regular.ttf").write_bytes((d / "Alef-Regular.ttf").read_bytes() + b"\0")
    with pytest.raises(ValueError, match="sha256"):
        governed_faces(d / "manifest.yaml")


def test_refuses_face_without_licence_fields(tmp_path):
    src = default_font_manifest_path().parent
    d = tmp_path / "fonts"; shutil.copytree(src, d)
    m = d / "manifest.yaml"
    m.write_text(m.read_text().replace("    license: OFL-1.1\n    license_file: LICENSE-Alef-OFL.txt\n", "", 1))
    with pytest.raises(ValueError, match="lacks 'license'"):
        governed_faces(m)


def test_refuses_lines_with_characters_the_face_lacks_and_bad_ids(tmp_path):
    s = render_lines([{"id": "zh", "text": "שלום 漢字"}, {"id": "ok", "text": "שלום"}], tmp_path / "o", seed=3,
                     fonts=["frank-ruhl-libre"])
    assert s["rendered"] == 1 and s["refused"][0]["id"] == "zh" and s["refused"][0]["reason"] == "font_missing_chars"
    assert not (tmp_path / "o" / "lines" / "zh.png").exists()
    with pytest.raises(ValueError, match="filename-safe"):
        render_lines([{"id": "../x", "text": "א"}], tmp_path / "p", seed=1)
    with pytest.raises(ValueError, match="duplicate"):
        render_lines([{"id": "a", "text": "א"}, {"id": "a", "text": "ב"}], tmp_path / "q", seed=1)


def test_cli_render_lines_and_list_fonts(tmp_path, capsys):
    inp = _write(tmp_path, ROWS[:4])
    assert main(["render-lines", "--input", str(inp), "--output", str(tmp_path / "o"), "--seed", "2",
                 "--font", "alef-regular", "--preset", "none", "--size-range", "30", "30"]) == 0
    s = json.loads(capsys.readouterr().out)
    assert s["rendered"] == 4 and s["by_font"] == {"alef-regular": 4} and s["size_range"] == [30, 30] and s["size_mode"] == "size"
    assert main(["render-lines", "--list-fonts"]) == 0
    faces = json.loads(capsys.readouterr().out)
    assert set(faces) == {"alef-regular", "david-libre-regular", "frank-ruhl-libre"}
    with pytest.raises(SystemExit):
        main(["render-lines", "--input", str(inp), "--output", str(tmp_path / "o2"), "--seed", "2", "--font", "gveret-levin-regular"])


def test_groups_share_face_size_and_weight_and_balance_over_groups(tmp_path):
    rows = [{"id": f"g{g}_{i}", "text": "שלום עולם 12", "group": f"sitting{g}"} for g in range(6) for i in range(4)]
    s = render_lines(rows, tmp_path / "o", seed=9, weight_range=(300, 700))
    man = [json.loads(l) for l in (tmp_path / "o" / "manifest.jsonl").read_text().splitlines()]
    by = {}
    for r in man:
        by.setdefault(r["group"], set()).add((r["font_id"], r["size_px"], r["weight"]))
    assert all(len(v) == 1 for v in by.values())
    per_face = {}
    for g, v in by.items():
        f = next(iter(v))[0]; per_face[f] = per_face.get(f, 0) + 1
    assert max(per_face.values()) - min(per_face.values()) <= 1 and s["groups"] == 6


def test_band_range_lands_every_face_in_the_target_band(tmp_path):
    rows = [{"id": f"b{i}", "text": "הוועדה דנה בהצעת החוק לתיקון פקודת המסים"} for i in range(12)]
    s = render_lines(rows, tmp_path / "o", seed=4, preset="none", band_range=(27, 34))
    man = [json.loads(l) for l in (tmp_path / "o" / "manifest.jsonl").read_text().splitlines()]
    assert s["size_mode"] == "band" and len({r["font_id"] for r in man}) == 3
    for r in man:
        assert 27 <= r["target_band_px"] <= 34
        assert abs(r["ink_band_px"] - r["target_band_px"]) <= 3, r
        assert 0 < r["dark_density"] < 1


def test_weight_applies_to_variable_faces_only(tmp_path):
    faces = governed_faces()
    img_l, _ = render_line("שלום", faces["frank-ruhl-libre"], 40, "none", random.Random(0), 300)
    img_h, _ = render_line("שלום", faces["frank-ruhl-libre"], 40, "none", random.Random(0), 900)
    dark = lambda im: sum(1 for v in im.tobytes() if v < 128)
    assert dark(img_h) > dark(img_l)
    s = render_lines([{"id": "a", "text": "שלום"}], tmp_path / "o", seed=1, fonts=["alef-regular"], weight_range=(700, 700))
    r = json.loads((tmp_path / "o" / "manifest.jsonl").read_text())
    assert r["weight"] is None and r["font"]["variable_weight"] is False and s["rendered"] == 1
