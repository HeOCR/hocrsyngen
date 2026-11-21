import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from experiments.scanifier_v2.archival_dev import archival_dev_view, render_verso
from experiments.scanifier_v2.dev_profiles import RANGE_BOUNDS
from hocrsyngen.print_typography import Paragraph, render_print_page


FRONT = (
    Paragraph("heading", "הודעות המדור"),
    Paragraph("body", "אסופת הערות מן המדור נערכה מחדש לאחר בדיקה חוזרת של פרטי ההודעה "
              "ושל גבולות התחום שבו אפשר לעיין בכל הנספחים לפני הגשת תגובה"),
    Paragraph("label", "סעיף 3 (ABC 12)"),
    Paragraph("note", "הודעה נוספת תפורסם בנפרד"),
)
BACK = (
    Paragraph("heading", "רשימת התיקונים"),
    Paragraph("body", "העיון בשינויים הושלם לקראת ישיבת החברים הבאה והנספחים יישלחו לעיון ממונה"),
)


def test_role_typography_preserves_labels_boxes_and_mixed_bidi():
    arguments = dict(seed=21, source_type="gazette", size=(550, 700), margin=(51, 42), body_px=27)
    result = render_print_page(FRONT, **arguments)
    assert result.image.tobytes() == render_print_page(FRONT, **arguments).image.tobytes()
    for index, paragraph in enumerate(FRONT):
        rows = [line for line in result.lines if line["paragraph"] == index]
        assert " ".join(line["text"] for line in rows) == paragraph.text
        assert all(result.image.crop(tuple(line["box"])).getextrema()[0][0] < 100 for line in rows)
        assert not rows[-1]["justified"]
    assert any(line["justified"] for line in result.lines if line["role"] == "body")
    assert result.lines[0]["font_size_px"] > 27 > result.lines[-1]["font_size_px"]
    assert all(line["font_sha256"] for line in result.lines)
    assert not any(line["justified"] for line in render_print_page(FRONT, justify=False, **arguments).lines)
    with pytest.raises(ValueError, match="does not fit"):
        render_print_page([Paragraph("heading", "הודעות " * 20 + "חדשות")], **arguments)


def _fit(rgb, noise, variation):
    ranges = {key: [0, 0] for key in RANGE_BOUNDS}
    for field, value in zip(("paper_r", "paper_g", "paper_b", "noise_sd", "noise_cv"),
                            (*rgb, noise, variation), strict=True):
        ranges[field] = [value, value]
    return {"version": 1, "seed": 0, "name": "flatbed_old", "status": "dev_fit",
            "ranges": ranges, "jpeg_encoders": []}


def test_archival_dev_uses_whole_fits_with_optional_distinct_verso():
    fits = {
        "green_book": {"base": _fit((233, 217, 196), 5, 0.8),
                       "duplex": {"status": "conditional_dev_fit", "ranges": {
                           "opacity": [0.13, 0.13], "blur_fraction_long_edge": [0.001, 0.001],
                           "offset_fraction": [0, 0]}}},
        "gazette_archive": {"base": _fit((248, 248, 248), 0, 0)},
    }
    front = render_print_page(FRONT, seed=21, source_type="book")
    reverse = render_verso(front, BACK, seed=21, source_type="green_book")
    assert reverse.lines[0]["text"] != front.lines[0]["text"]
    assert reverse.lines[0]["baseline"][0][1] > front.lines[0]["baseline"][0][1]
    with pytest.raises(ValueError, match="must be distinct"):
        render_verso(front, FRONT, seed=21, source_type="green_book")
    green = dict(source_type="green_book", fits=fits, seed=70)
    base = archival_dev_view(front, **green)
    captured = archival_dev_view(front, reverse=reverse, **green)
    assert captured.size == front.image.size
    assert base.tobytes() != captured.tobytes()
    assert captured.tobytes() == archival_dev_view(front, reverse=reverse, **green).tobytes()
    grey = archival_dev_view(front, source_type="gazette_archive", fits=fits, seed=70)
    assert grey.getpixel((0, 0)) == (248, 248, 248)
    blank_green = np.asarray(base)[650:1050, :, 0].astype(float)
    assert np.median(blank_green) < 240
    local_sd = [tile.std() for rows in np.array_split(blank_green, 4)
                for tile in np.array_split(rows, 8, axis=1)]
    assert max(local_sd) > 2 * min(local_sd)
    with pytest.raises(ValueError, match="matched source"):
        archival_dev_view(front, source_type="gazette_archive", fits=fits, seed=70, reverse=reverse)
    with pytest.raises(ValueError, match="independent verso"):
        archival_dev_view(front, reverse=front, **green)
