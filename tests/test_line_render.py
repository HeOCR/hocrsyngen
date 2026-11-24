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
    CALIBRATION_TEXT,
    HANDWRITING_PRESET,
    LINE_PRESETS,
    _calibration_band,
    band_ratio,
    band_size,
    face_weight,
    missing_chars,
    governed_faces,
    read_lines,
    render_line,
    render_lines,
)

pytestmark = pytest.mark.skipif(not features.check("raqm"), reason="needs Pillow with libraqm (see AGENTS.md)")

SIZE = 40
# Added from google/fonts 3cb0866 (OFL-1.1); see the font manifest notes.
NEW_FACES = ("noto-sans-hebrew", "noto-serif-hebrew", "assistant", "heebo", "rubik", "miriam-libre")
# Office faces from google/fonts 7af0d90 (OFL-1.1): metric-compatible stand-ins for Arial, Times and Courier, plus Open Sans.
OFFICE_FACES = ("arimo", "tinos-regular", "tinos-bold", "cousine-regular", "cousine-bold", "open-sans")
EXPANSION_FACES = ("bona-nova", "cardo", "fredoka", "ibm-plex-sans-hebrew", "karantina", "lunasima", "m-plus-1p",
                   "secular-one", "suez-one", "varela-round")
# Signs a face lacks, by the coverage check recorded in the manifest notes.
KNOWN_GAPS = {"open-sans": {"\u05f3", "\u05f4"}}
OFFICE_SIGNS = "₪%" + "0123456789"
LETTERS = "".join(chr(c) for c in range(0x05D0, 0x05EB))
NIQQUD = "".join(chr(c) for c in list(range(0x05B0, 0x05BD)) + [0x05C1, 0x05C2, 0x05C7])
DIGITS = "0123456789"
PUNCT = ".,:;!?\"'()[]-/%–—״׳־"


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


def test_handwriting_cli_writes_repeatable_training_lines(tmp_path, capsys):
    assert main(["render-lines", "--preset", HANDWRITING_PRESET, "--list-fonts"]) == 0
    faces = json.loads(capsys.readouterr().out)
    assert set(faces) == {"gveret-levin-regular", "playpen-sans-hebrew"}
    assert set(faces).isdisjoint(governed_faces())

    text = "כתבתי 12 שורות (ועוד אחת)."
    inp = _write(tmp_path, [{"id": "line-a", "text": text}, {"id": "line-b", "text": text}])
    first, second = tmp_path / "first", tmp_path / "second"
    args = ["render-lines", "--input", str(inp), "--seed", "51", "--preset", HANDWRITING_PRESET,
            "--size-range", "40", "40"]
    for out in (first, second):
        assert main([*args, "--output", str(out)]) == 0
    manifest = first / "manifest.jsonl"
    assert manifest.read_bytes() == (second / manifest.name).read_bytes()
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert {row["font_id"] for row in rows} == set(faces)
    for row in rows:
        assert row["schema"] == "hocrsyngen_line_render.v1"
        assert row["synthetic"] == "rendered" and row["label_order"] == "logical"
        assert row["image"] == f"lines/{row['id']}.png"
        assert row["label"] == f"lines/{row['id']}.gt.txt"
        assert (first / row["label"]).read_text(encoding="utf-8") == text + "\n"
        assert (first / row["image"]).read_bytes() == (second / row["image"]).read_bytes()
        assert {"wobble_em", "slant", "letter_spacing_scale", "stroke_px"} <= row["preset_params"].keys()
        with Image.open(first / row["image"]) as img:
            threshold = (row["preset_params"]["ink"] + row["preset_params"]["paper"]) / 2
            ink = img.point(lambda pixel: 255 if pixel < threshold else 0).getbbox()
            assert img.mode == "L" and img.size == (row["width"], row["height"])
            assert ink and 0 < ink[0] < ink[2] < img.width and 0 < ink[1] < ink[3] < img.height
    assert rows[0]["preset_params"] != rows[1]["preset_params"]


def test_handwriting_warp_preserves_rtl_and_digit_order():
    face = governed_faces(preset=HANDWRITING_PRESET)["gveret-levin-regular"]
    img, params = render_line("ת   29   א", face, SIZE, HANDWRITING_PRESET, random.Random(0))
    threshold = (params["ink"] + params["paper"]) / 2
    img = img.point(lambda pixel: 0 if pixel < threshold else 255)
    x = {char: _best_x(img, _template(face, char)) for char in "את29"}
    assert x["א"] < x["2"] < x["9"] < x["ת"], x


def test_refuses_ungoverned_and_unknown_fonts_and_presets(tmp_path):
    with pytest.raises(ValueError, match="not governed"):
        render_lines(ROWS[:1], tmp_path / "x", seed=1, fonts=["gveret-levin-regular"])
    with pytest.raises(ValueError, match="not governed"):
        render_lines(ROWS[:1], tmp_path / "x", seed=1, fonts=["no-such-font"])
    with pytest.raises(ValueError, match="not governed"):
        render_lines(ROWS[:1], tmp_path / "x", seed=1, preset=HANDWRITING_PRESET, fonts=["alef-regular"])
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
    assert set(faces) == {"alef-regular", "david-libre-regular", "frank-ruhl-libre"} | set(NEW_FACES) | set(OFFICE_FACES) | set(EXPANSION_FACES)
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
    # The calibration line itself: otsu2pct counts a row only above 2% of the line's ink columns, so the band of a
    # shorter line can differ by several px on some faces (an ascender row drops in or out). The band is defined on
    # the calibration line, and every face must land within 3 px of the target there.
    n = len(governed_faces())
    rows = [{"id": f"b{i}", "text": CALIBRATION_TEXT} for i in range(n)]
    for bd, field in (("otsu2pct", "ink_band_px_otsu2pct"), ("p5p95", "ink_band_px")):
        s = render_lines(rows, tmp_path / bd, seed=4, preset="none", band_range=(27, 34), band_def=bd)
        man = [json.loads(l) for l in (tmp_path / bd / "manifest.jsonl").read_text().splitlines()]
        assert s["size_mode"] == "band" and s["band_def"] == bd and len({r["font_id"] for r in man}) == n
        for r in man:
            assert 27 <= r["target_band_px"] <= 34 and r["band_def"] == bd
            assert abs(r[field] - r["target_band_px"]) <= 3, r
            assert 0 < r["dark_density"] < 1 and 0 < r["ink_band_frac_otsu2pct"] < 1


def test_otsu2pct_matches_the_r9_face_stats_definition():
    # Hand-built line: 10 rows of solid ink (cols 5-24) on a 100x30 white image, plus one row with 1 ink pixel (1% < 2%).
    from hocrsyngen.line_render import measure_band_otsu2pct
    img = Image.new("L", (100, 30), 255)
    for y in range(10, 20):
        for x in range(5, 25):
            img.putpixel((x, y), 0)
    img.putpixel((30, 25), 0)
    m = measure_band_otsu2pct(img)
    assert m["ink_band_px_otsu2pct"] == 10 and m["ink_band_frac_otsu2pct"] == 1.0


def test_weight_applies_to_variable_faces_only(tmp_path):
    faces = governed_faces()
    img_l, _ = render_line("שלום", faces["frank-ruhl-libre"], 40, "none", random.Random(0), 300)
    img_h, _ = render_line("שלום", faces["frank-ruhl-libre"], 40, "none", random.Random(0), 900)
    dark = lambda im: sum(1 for v in im.tobytes() if v < 128)
    assert dark(img_h) > dark(img_l)
    s = render_lines([{"id": "a", "text": "שלום"}], tmp_path / "o", seed=1, fonts=["alef-regular"], weight_range=(700, 700))
    r = json.loads((tmp_path / "o" / "manifest.jsonl").read_text())
    assert r["weight"] is None and r["font"]["variable_weight"] is False and s["rendered"] == 1


def test_refuses_combining_marks_the_face_lacks_and_keeps_niqqud_it_has(tmp_path):
    # A line with a ta'am must be refused on a face without te'amim (the mark would vanish from the image while the
    # label keeps it) and rendered on a face that has them (the two Noto faces); a pointed line renders everywhere.
    rows = [{"id": "taam", "text": "בְּרֵאשִׁ֖ית בָּרָא"}, {"id": "niqqud", "text": "שָׁלוֹם עוֹלָם"}]
    with_teamim = {"noto-sans-hebrew", "noto-serif-hebrew", "arimo", "tinos-regular", "tinos-bold", "cousine-regular", "cousine-bold"}
    with_teamim.update(("cardo", "lunasima", "m-plus-1p"))
    for f in governed_faces():
        s = render_lines(rows, tmp_path / f, seed=1, fonts=[f])
        ref = {r["id"]: r for r in s["refused"]}
        if f in with_teamim:
            assert not ref and (tmp_path / f / "lines" / "taam.png").exists(), (f, s["refused"])
        else:
            assert set(ref) == {"taam"} and ref["taam"]["reason"] == "font_missing_chars", (f, s["refused"])
            assert "\u0596" in ref["taam"]["chars"]
        assert (tmp_path / f / "lines" / "niqqud.png").exists()


@pytest.mark.parametrize("face_id", NEW_FACES)
def test_new_face_is_governed_and_covers_letters_niqqud_digits_punctuation(face_id):
    face = governed_faces()[face_id]
    assert face.license == "OFL-1.1" and face.license_file.startswith("LICENSE-")
    for name, chars in (("letters", LETTERS), ("niqqud", NIQQUD), ("digits", DIGITS), ("punct", PUNCT)):
        assert missing_chars(face, chars) == [], (face_id, name, missing_chars(face, chars))


@pytest.mark.parametrize("face_id", NEW_FACES)
def test_new_face_renders_the_bidi_lines_in_visual_order(face_id):
    img, face = _plain("א 12 (ב)", face_id)
    x = {c: _best_x(img, _template(face, c)) for c in ("א", "ב", "1", "2", "(", ")")}
    assert x["("] < x["ב"] < x[")"] < x["1"] < x["2"] < x["א"], (face_id, x)
    img, face = _plain("ש ABC ת", face_id)
    x = {c: _best_x(img, _template(face, c)) for c in ("ש", "A", "B", "C", "ת")}
    assert x["ת"] < x["A"] < x["B"] < x["C"] < x["ש"], (face_id, x)


@pytest.mark.parametrize("face_id", OFFICE_FACES)
def test_office_face_is_governed_and_covers_what_office_print_needs(face_id):
    face = governed_faces()[face_id]
    assert face.license == "OFL-1.1" and face.license_file.startswith("LICENSE-")
    gaps = KNOWN_GAPS.get(face_id, set())
    for name, chars in (("letters", LETTERS), ("niqqud", NIQQUD), ("digits", DIGITS), ("office", OFFICE_SIGNS),
                        ("punct", "".join(c for c in PUNCT if c not in gaps))):
        assert missing_chars(face, chars) == [], (face_id, name, missing_chars(face, chars))
    # the recorded gaps are real, so the manifest note stays true
    assert set(missing_chars(face, "".join(sorted(gaps)))) == gaps


@pytest.mark.parametrize("face_id", OFFICE_FACES)
def test_office_face_renders_numbers_and_shekel_in_visual_order(face_id):
    img, face = _plain("א 12 (ב)", face_id)
    x = {c: _best_x(img, _template(face, c)) for c in ("א", "ב", "1", "2", "(", ")")}
    assert x["("] < x["ב"] < x[")"] < x["1"] < x["2"] < x["א"], (face_id, x)
    img, face = _plain("ש ABC ת", face_id)
    x = {c: _best_x(img, _template(face, c)) for c in ("ש", "A", "B", "C", "ת")}
    assert x["ת"] < x["A"] < x["B"] < x["C"] < x["ש"], (face_id, x)
    # an amount with a percent sign: the number keeps its digit order, % follows it on its right
    img, face = _plain("שיעור 35% בלבד", face_id)
    x = {c: _best_x(img, _template(face, c)) for c in ("3", "5", "%", "ש")}
    assert x["3"] < x["5"] < x["%"] < x["ש"], (face_id, x)


def test_band_size_keeps_the_ratio_guess_when_it_lands_and_searches_when_a_hinted_face_misses():
    faces = governed_faces()
    # an older face: the guess from the 100 px ratio is kept, so its earlier output is unchanged
    f = faces["frank-ruhl-libre"]
    for t in (24, 30, 36):
        assert band_size(str(f.path), 400, t) == max(6, round(t / band_ratio(str(f.path), 400)))
    # Cousine Bold is hinted and static: the ratio guess misses the band at small sizes, the search lands it
    f = faces["cousine-bold"]
    w, _ = face_weight(f, 400)
    guess = max(6, round(27 / band_ratio(str(f.path), w)))
    assert abs(_calibration_band(str(f.path), guess, w, "otsu2pct") - 27) > 2
    assert abs(_calibration_band(str(f.path), band_size(str(f.path), w, 27), w, "otsu2pct") - 27) <= 2
