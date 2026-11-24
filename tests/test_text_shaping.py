import csv
import hashlib
import random
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from hocrsyngen.generator import _BookLine, _LineRecorder, _draw_book_lines, _load_font
from hocrsyngen.line_render import governed_faces, render_line, render_lines
from hocrsyngen.office_pages import Tok, join_line
from hocrsyngen.text_shaping import ShapingError, missing_characters


def test_missing_glyph_matches_the_native_notdef_probe():
    face = governed_faces()["alef-regular"]
    assert missing_characters(face.path, "מלך字\U000F0000") == ["字", "\U000F0000"]


def test_refuses_orphan_mark_and_bidi_override_before_writing(tmp_path):
    rows = [
        {"id": "valid", "text": "שָׁלוֹם 12/3"},
        {"id": "lost-mark", "text": "שלוֹם ֶ"},
        {"id": "override", "text": "שלוֹם \u202e12"},
    ]
    summary = render_lines(rows, tmp_path, seed=2, fonts=["alef-regular"], preset="none")
    assert summary["rendered"] == 1
    assert {row["id"]: row["reason"] for row in summary["refused"]} == {
        "lost-mark": "unattached_mark", "override": "bidi_override",
    }
    assert (tmp_path / "lines/valid.gt.txt").read_text() == rows[0]["text"] + "\n"
    with pytest.raises(ShapingError, match="font_missing_chars"):
        render_line("שלום 字", governed_faces()["alef-regular"], 40, "none", random.Random(2))


def test_mixed_book_line_is_one_native_bidi_run_and_preserves_label():
    font = _load_font(governed_faces()["alef-regular"].path, 38)
    text = "טופס AC 123 / 45 סוף ךםןףץ"
    img = Image.new("L", (960, 120), 255)
    expected = img.copy()
    line = _BookLine(text.split(), 900, 20, font, 19, "body", "body", 0, False, 0)
    recorder = _LineRecorder()
    _draw_book_lines(ImageDraw.Draw(img), [line], recorder)
    ImageDraw.Draw(expected).text((900, 20), text, font=font, fill=0, anchor="ra", direction="rtl")
    assert ImageChops.difference(img, expected).getbbox() is None
    assert recorder.lines[0].text == text


def test_office_nfc_numeric_offsets_follow_the_drawn_token():
    text, spans, _ = join_line([Tok("A\u030A12", [(2, 4, "number")]), Tok("מספר")])
    assert text == "Å12 מספר"
    assert spans == [(1, 3, "number")]


def test_modern_font_inventory_matches_governed_bytes_and_covers_standard_glyphs():
    index = Path(__file__).resolve().parents[1] / "docs/modern-print-font-expansion.csv"
    with index.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len({row["family"] for row in rows}) >= 10
    faces = governed_faces()
    for row in rows:
        face = faces[row["id"]]
        assert face.sha256 == row["font_sha256"] == hashlib.sha256(face.path.read_bytes()).hexdigest()
        license_path = face.path.parent / face.license_file
        assert face.license == row["license"] == "OFL-1.1"
        assert hashlib.sha256(license_path.read_bytes()).hexdigest() == row["license_sha256"]
        assert not missing_characters(face.path, "אבגדהוזחטיכלמנסעפצקרשתךםןףץ ABC 12/34 ₪ ׳״־–—")
