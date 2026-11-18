"""office-pages: labels and number spans, folds, exact boxes after skew, rectified crops, bidi in cells, held-out
splits, determinism and the CLI. The text pool here is invented filler, not drawn from any dataset."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat, features

from hocrsyngen.cli import main
from hocrsyngen.line_render import governed_faces
from hocrsyngen.office_pages import (
    DEGRADATION_MIX,
    FAMILY_MIX,
    HELD_OUT_FACES,
    HELD_OUT_TABLE_SCHEMA,
    NUM,
    SHAPE_MIX,
    PLine,
    Run,
    TextPool,
    build_page,
    draw_line,
    fold_label,
    gen_amount,
    gen_date,
    gen_label,
    gen_percent,
    gen_short_int,
    holdout_units,
    office_pages,
    padded,
    quad,
    rectified_crop,
    render_page,
    warp,
)

pytestmark = pytest.mark.skipif(not features.check("raqm"), reason="needs Pillow with libraqm (see AGENTS.md)")

WORDS = ("המבקש הגוף המוסמך יקבע את התנאים לשם מתן היתר כאמור בכפוף לאישור השר בתקופה שתיקבע בהודעה ובלבד "
         "שהבקשה הוגשה במועד ועל פי הנוהל שפורסם לציבור הרחב").split()


def pool_rows(units=6, lines=30, seed=1):
    r = random.Random(seed)
    return [{"id": f"u{u}_l{i}", "unit_id": f"u{u}", "text": " ".join(r.choice(WORDS) for _ in range(r.randint(6, 14)))}
            for u in range(units) for i in range(lines)]


FAMS = sorted(FAMILY_MIX)
MODELS = sorted(DEGRADATION_MIX)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("op")
    summaries = []
    for k, (fam, mod) in enumerate(zip(FAMS * 2, MODELS + MODELS[::-1])):
        summaries.append(office_pages(pool_rows(), out / f"r{k}", seed=k, pages=1, families=[fam], models=[mod]))
    recs = []
    for d in sorted(out.iterdir()):
        for p in sorted((d / "pages").glob("*.json")):
            page = json.loads(p.read_text(encoding="utf-8"))
            for rec in page["lines"]:
                recs.append((d, page, rec))
    return out, summaries, recs


# ---- numbers and folds ------------------------------------------------------------------------------------------


def test_fold_is_one_for_one_and_folds_what_stock_lacks():
    s = "ש״ח ג׳ ב־1.1.2026 “מונח” „ – — - \" '"
    f = fold_label(s)
    assert len(f) == len(s)
    assert not set(f) & set("״׳־“”„–—")
    assert f == 'ש"ח ג\' ב-1.1.2026 "מונח" " - - - " \''


@pytest.mark.parametrize("seed", range(200))
def test_generated_numbers_are_single_number_tokens(seed):
    r = random.Random(seed)
    lab = gen_label(r)
    core = lab.rstrip(".")
    assert NUM.fullmatch(core) and 2 <= core.count(".") + 1 <= 4 and 1 <= int(core.split(".")[0]) <= 40
    for g in (gen_date, gen_short_int, gen_amount, gen_percent):
        v = g(r)
        assert NUM.fullmatch(v), (g.__name__, v)
    d = gen_date(r)
    y = int(re.split(r"[./]", d)[-1])
    assert 1990 <= y <= 2030 or 0 <= y <= 99


def test_label_levels_and_trailing_dot_can_be_forced():
    r = random.Random(0)
    assert gen_label(r, 4, True).count(".") == 4 and gen_label(r, 2, False).count(".") == 1


# ---- labels and spans on generated pages ------------------------------------------------------------------------


def test_every_number_span_is_whole_in_the_label(run):
    _, _, recs = run
    n = 0
    for _, _, rec in recs:
        label = rec["text"]
        found = {(m.start(), m.end()) for m in NUM.finditer(label)}
        for sp in rec["number_spans"]:
            a, b = sp["start"], sp["end"]
            tok = label[a:b]
            assert tok and not re.search(r"\s", tok), (label, sp)
            assert (a, b) in found, (label, sp, tok)       # the evaluation's pattern finds it whole, no more, no less
            assert rec["drawn_text"][a:b] == tok           # digits and separators are drawn exactly as labelled
            n += 1
    assert n > 200


def test_label_lines_start_with_their_section_label(run):
    _, _, recs = run
    lines = [rec for _, _, rec in recs if rec["kind"] == "label_line"]
    assert lines
    multi = 0
    for rec in lines:
        first = rec["number_spans"][0] if rec["number_spans"] else None
        if first and first["shape"] == "label":
            assert first["start"] == 0
            multi += "." in rec["text"][first["start"]:first["end"]]
        elif first and first["shape"] == "sub_num":  # (1)
            assert first["start"] == 1 and rec["text"].startswith("(") and rec["text"][first["end"]] == ")"
        else:  # a Hebrew-letter sub-level such as (א) or א.
            assert re.match(r"^(\([א-ת]\)|[א-ת]\.) ", rec["text"]), rec["text"]
    assert multi >= len(lines) // 2


def test_labels_are_the_folded_drawn_text_and_files_match(run):
    _, _, recs = run
    for d, _, rec in recs:
        assert rec["text"] == fold_label(rec["drawn_text"])
        if "label" in rec:
            assert (d / rec["label"]).read_text(encoding="utf-8") == rec["text"] + "\n"
            im = Image.open(d / rec["image"])
            assert im.size == (rec["width"], rec["height"]) and im.mode == "L"
        else:
            assert rec["masked_by_mark"] or not rec["in_frame"]


def test_image_only_marks_are_never_labelled(run):
    _, _, recs = run
    pages = {page["id"]: page for _, page, _ in recs}
    regions = [r for p in pages.values() for r in p["regions"]]
    assert regions and all(r["labelled"] is False for r in regions)
    for _, _, rec in recs:
        assert not any(w in rec["text"] for w in ("נתקבל", "העתק נאמן למקור"))


def test_every_family_and_model_appears_and_summary_counts(run):
    _, summaries, recs = run
    assert {p["family"] for _, p, _ in recs} == set(FAMS)
    assert {p["degradation"]["model"] for _, p, _ in recs} == set(MODELS)
    for s in summaries:
        assert s["lines"] == sum(s["by_face"].values()) > 0
        assert s["refused_missing_chars"] == 0


def test_tables_hold_numeric_cells_with_rectangles(run):
    _, _, recs = run
    cells = [rec for _, _, rec in recs if rec["kind"] == "cell"]
    assert len(cells) > 30
    assert sum(bool(c["number_spans"]) for c in cells) / len(cells) >= 0.6
    for c in cells:
        x0, y0, x1, y1 = c["cell"]["rect"]
        b = c["box_page_300dpi"]
        assert x0 - 2 <= b[0] and b[2] <= x1 + 2, (c["text"], b, c["cell"]["rect"])


# ---- geometry -----------------------------------------------------------------------------------------------------


def _ink(img, thr=128):
    return img.point(lambda v: 255 if v < thr else 0)


def _solo(page, ln, faces):
    img = Image.new("L", page.size, 255)
    draw_line(ImageDraw.Draw(img), ln, faces, 0)
    return img


@pytest.fixture(scope="module")
def numbered_page():
    faces = governed_faces()
    page, _ = build_page(TextPool(pool_rows()), faces, "geom", 5, "train", "numbered", "arimo")
    return page, faces


def test_line_boxes_are_tight_on_the_flat_page(numbered_page):
    page, faces = numbered_page
    for ln in page.lines[:25]:
        bb = _ink(_solo(page, ln, faces)).getbbox()
        assert bb, ln.text
        b = ln.box
        assert b[0] - 1 <= bb[0] and b[1] - 1 <= bb[1] and bb[2] <= b[2] + 1 and bb[3] <= b[3] + 1, (ln.text, b, bb)
        assert max(bb[0] - b[0], bb[1] - b[1], b[2] - bb[2], b[3] - bb[3]) <= 6, (ln.text, b, bb)


@pytest.mark.parametrize("skew", (-3.0, 3.0))
def test_boxes_follow_the_ink_after_skew(numbered_page, skew):
    page, faces = numbered_page
    _, H, deg = render_page(page, faces, 5, "clean", force_skew=skew)
    s = deg["dpi"] / 300
    size = (round(page.size[0] * s), round(page.size[1] * s))
    for ln in page.lines[:12]:
        ink = _ink(warp(_solo(page, ln, faces), H, size, 255))
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).polygon(quad(H, ln.box), fill=255)
        mask = mask.filter(ImageFilter.MaxFilter(5))
        outside = ImageChops.subtract(ink, mask)
        assert outside.getbbox() is None, (ln.text, skew)


def test_rectified_crop_straightens_a_skewed_line(numbered_page):
    page, faces = numbered_page
    ln = max(page.lines, key=lambda x: x.box[2] - x.box[0])
    flat, Hf, df = render_page(page, faces, 5, "clean", force_skew=0.0)
    sk, Hs, ds = render_page(page, faces, 5, "clean", force_skew=3.0)
    assert df["dpi"] == ds["dpi"]
    s = df["dpi"] / 300
    pb = padded(ln.box, ln.size)
    rows = []
    for img, H in ((flat, Hf), (sk, Hs)):
        crop = rectified_crop(_ink(img), quad(H, pb), s, pb)
        bb = crop.getbbox()
        rows.append(bb[3] - bb[1])
        assert bb[0] > 0 and bb[2] < crop.width  # the padding keeps the ink off the crop's sides
    # skew of 3 degrees over a long line would add sin(3)*width ~ 0.05 * width rows; rectified it adds almost none
    assert abs(rows[1] - rows[0]) <= 4, rows


def test_page_renders_identically_in_any_batch(tmp_path):
    a = office_pages(pool_rows(), tmp_path / "a", seed=3, pages=2)
    b = office_pages(pool_rows(), tmp_path / "b", seed=3, pages=1)
    assert a["pages"] == 2 and b["pages"] == 1
    pa = (tmp_path / "a" / "pages" / "op3_000000.png").read_bytes()
    pb = (tmp_path / "b" / "pages" / "op3_000000.png").read_bytes()
    assert pa == pb


# ---- bidi in cells and labels ---------------------------------------------------------------------------------------

SIZE = 40


def _draw(text, face_id="arimo"):
    faces = governed_faces()
    f = ImageFont.truetype(str(faces[face_id].path), SIZE, layout_engine=ImageFont.Layout.RAQM)
    w = int(f.getlength(text, direction="rtl")) + 40
    img = Image.new("L", (w, 70), 255)
    draw_line(ImageDraw.Draw(img), PLine("cell", text, face_id, SIZE, None, [Run(text, w - 20, 50)], []), faces, 0)
    return img, faces[face_id]


def _x(img, face, ch):
    f = ImageFont.truetype(str(face.path), SIZE, layout_engine=ImageFont.Layout.RAQM)
    m = f.getmask(ch, mode="L")
    t = ImageChops.invert(Image.frombytes("L", m.size, bytes(m)))
    best = None
    for y in range(0, img.height - t.height + 1):
        for x in range(0, img.width - t.width + 1):
            d = ImageStat.Stat(ImageChops.difference(img.crop((x, y, x + t.width, y + t.height)), t)).mean[0]
            if best is None or d < best[0]:
                best = (d, x + t.width / 2)
    return best[1]


def test_cell_amount_with_shekel_keeps_digit_order():
    img, face = _draw("₪ 1,234")
    x = {c: _x(img, face, c) for c in ("₪", "1", "2", "3", "4")}
    assert x["1"] < x["2"] < x["3"] < x["4"] < x["₪"], x


def test_line_initial_label_stays_at_the_right_in_digit_order():
    img, face = _draw("1.2.4. אב")
    x = {c: _x(img, face, c) for c in ("1", "2", "4", "א", "ב")}
    assert x["ב"] < x["א"] < x["1"] < x["2"] < x["4"], x


def test_prefixed_date_keeps_digit_order():
    img, face = _draw("ב-13.05.2024")
    x = {c: _x(img, face, c) for c in ("ב", "1", "3", "5", "4")}
    assert x["1"] < x["3"] < x["5"] < x["4"] < x["ב"], x


# ---- splits ---------------------------------------------------------------------------------------------------------


def test_train_never_uses_the_held_out_face_or_schema(tmp_path):
    office_pages(pool_rows(), tmp_path, seed=9, pages=6, families=["tables"])
    for p in (tmp_path / "pages").glob("*.json"):
        page = json.loads(p.read_text(encoding="utf-8"))
        assert page["font"]["id"] not in HELD_OUT_FACES
        assert all((r["cell"] or {}).get("schema") != HELD_OUT_TABLE_SCHEMA for r in page["lines"])


def test_val_uses_only_the_held_out_face(tmp_path):
    office_pages(pool_rows(), tmp_path, seed=9, pages=3, split="val")
    for p in (tmp_path / "pages").glob("*.json"):
        page = json.loads(p.read_text(encoding="utf-8"))
        assert page["font"]["id"] in HELD_OUT_FACES
        assert {r["font_id"] for r in page["lines"]} <= set(HELD_OUT_FACES)


def test_holdout_units_is_stable_and_about_the_share():
    ids = [f"unit{i}" for i in range(4000)]
    h = holdout_units(ids)
    assert h == holdout_units(list(reversed(ids))) and 0.035 < len(h) / len(ids) < 0.065


def test_pool_rows_need_ids_and_units():
    with pytest.raises(ValueError):
        TextPool([{"id": "a", "text": "שלום"}])


# ---- mix ------------------------------------------------------------------------------------------------------------


def test_shape_mix_leans_on_line_initial_labels(tmp_path):
    s = office_pages(pool_rows(), tmp_path, seed=21, pages=24)
    share = s["number_shape_share"]
    assert share["label"] >= 0.25, share
    assert all(share[k] >= 0.05 for k in SHAPE_MIX), share
    assert s["lines_with_number_share"]["text"] >= 0.4 and s["lines_with_number_share"]["cells"] >= 0.6
    assert s["lines_with_2plus_numbers_share"]["text"] >= 0.2


def test_cli_writes_pages_and_lines(tmp_path, capsys):
    texts = tmp_path / "pool.jsonl"
    texts.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in pool_rows()), encoding="utf-8")
    assert main(["office-pages", "--texts", str(texts), "--output", str(tmp_path / "o"), "--seed", "4", "--pages", "1",
                 "--family", "numbered", "--degradation", "office_scan"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pages"] == 1 and out["lines"] > 10 and out["by_family"] == {"numbered": 1}
    assert len(list((tmp_path / "o" / "lines").glob("*.png"))) == out["lines"]
    assert (tmp_path / "o" / "summary.json").exists() and (tmp_path / "o" / "pages.jsonl").exists()
