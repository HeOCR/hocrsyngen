from __future__ import annotations

import json
import shutil
import unicodedata
from pathlib import Path

import pytest

from glyph_bank_fixture import (
    DEFAULT_STYLES,
    FixtureStyle,
    HEBREW_LETTERS,
    build_fixture_bank,
    rewrite_glyphs,
    rewrite_index,
)
from hocrsyngen.cli import main
from hocrsyngen.generator import GLYPH_COMPOSER_VERSION, _rotated_point
from hocrsyngen.glyph_bank import GlyphBankError, load_glyph_bank
from hocrsyngen.glyph_compose import (
    SIZE_BAND_TOLERANCE,
    GlyphCompositionError,
    bidi_levels,
    compose_glyph_batch,
    corpus_skip_reason,
    gematria,
    rtl_placement_order,
)
from hocrsyngen.io import sha256_file
from hocrsyngen.line_annotations import polygon_contains
from hocrsyngen.validation import BatchValidationError, validate_batch


WORDS = ["שלום", "ספר", "בית", "דרך", "מכתב", "עולם", "ילד", "גן", "חצר", "פרק", "זמן", "קול", "אור", "טוב"]


def _plain_lines(count: int, offset: int = 0) -> list[str]:
    lines = []
    for index in range(count):
        words = [WORDS[(index * 3 + step + offset) % len(WORDS)] for step in range(4 + index % 5)]
        lines.append(" ".join(words) + ".")
    return lines


@pytest.fixture(scope="module")
def bank(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_fixture_bank(tmp_path_factory.mktemp("bank") / "bank")


@pytest.fixture(scope="module")
def batch(bank: Path, tmp_path_factory: pytest.TempPathFactory):
    output = tmp_path_factory.mktemp("batch") / "out"
    return output, compose_glyph_batch(bank, 3, 11, output)


def _copy_bank(bank: Path, tmp_path: Path) -> Path:
    target = tmp_path / "bank"
    shutil.copytree(bank, target)
    return target


# ------------------------------------------------------------ bank ----


def test_fixture_bank_loads(bank: Path) -> None:
    loaded = load_glyph_bank(bank)
    assert loaded.bank_id == "pgb-fixture"
    assert sorted(loaded.styles) == ["fx-alef", "fx-alef-columns"]
    assert "״" not in loaded.chars("fx-alef") and "׳" in loaded.chars("fx-alef")


def _set_first_glyph(key: str, value):
    def mutate(records):
        records[0][key] = value

    return mutate


@pytest.mark.parametrize(
    ("mutate_glyphs", "mutate_index", "message"),
    [
        (None, lambda index: index.update(glyphs_sha256="0" * 64), "glyphs_sha256"),
        (_set_first_glyph("asset_path", "/etc/passwd"), None, "schema violation"),
        (_set_first_glyph("asset_path", "styles/../x.png"), None, "schema violation"),
        (_set_first_glyph("asset_path", "styles/missing.png"), None, "missing file"),
        (_set_first_glyph("char", "אב"), None, "schema violation"),
        (_set_first_glyph("char", "שׁ"), None, "must be NFC"),
        (_set_first_glyph("char", "ָ"), None, "combining mark"),
        (_set_first_glyph("ink_box", [0, 0, 999, 5]), None, "inside size"),
        (_set_first_glyph("style_id", "nope"), None, "not a listed style"),
        (None, lambda index: index["styles"][0].update(licence="CC-BY-4.0"), "attribution"),
        (None, lambda index: index["styles"][0].update(licence="CC-BY-SA-4.0"), "schema violation"),
        (None, lambda index: index.update(glyph_count=1), "glyph_count"),
        (None, lambda index: index["styles"][0]["char_counts"].update({"א": 99}), "char_counts"),
        (None, lambda index: index["styles"][0].update(paper_patches=["styles/none.png"]), "missing file"),
        (None, lambda index: index["styles"][0]["metrics"].update(word_gap_px=[9, 3, 1]), "ordered"),
    ],
)
def test_bank_validation_errors(bank: Path, tmp_path: Path, mutate_glyphs, mutate_index, message: str) -> None:
    copy = _copy_bank(bank, tmp_path)
    if mutate_glyphs is not None:
        rewrite_glyphs(copy, mutate_glyphs)
    if mutate_index is not None:
        rewrite_index(copy, mutate_index)
    with pytest.raises(GlyphBankError, match=message):
        load_glyph_bank(copy)


def test_cc_by_style_with_attribution_loads(bank: Path, tmp_path: Path) -> None:
    copy = _copy_bank(bank, tmp_path)
    rewrite_index(copy, lambda index: index["styles"][0].update(licence="CC-BY-4.0", attribution="Scan: Example Library"))
    assert load_glyph_bank(copy).styles["fx-alef"].attribution == "Scan: Example Library"


# ------------------------------------------------------------ text ----


def test_bidi_reverses_numbers_only() -> None:
    word = "ב-1948,"
    levels = bidi_levels(word)
    order = "".join(word[index] for index in rtl_placement_order(levels))
    # Right-to-left placement: Hebrew first, then the digits so they read 1948 left to right.
    assert order == "ב-8491,"
    assert bidi_levels("13:40") == [2, 2, 2, 2, 2]
    assert bidi_levels("ABC DEF") is None
    assert bidi_levels("(ABC)") is not None


def test_corpus_skip_reasons() -> None:
    assert corpus_skip_reason("שָׁלוֹם עולם") == "niqqud_or_combining_mark"
    assert corpus_skip_reason("שלום‏עולם") == "control_or_format_char"
    assert corpus_skip_reason("New York שלום") == "unsupported_bidi"
    assert corpus_skip_reason("שלום עולם") is None


def test_gematria() -> None:
    assert gematria(15) == "טו"
    assert gematria(16) == "טז"
    assert gematria(123) == "קכג"
    assert gematria(400) == "ת"


# ------------------------------------------------------------ batch ----


def test_batch_validates(batch) -> None:
    output, result = batch
    assert validate_batch(output).page_count == 3
    manifest = json.loads((output / "generation_manifest.json").read_text(encoding="utf-8"))
    for sample in manifest["samples"]:
        assert sample["generator_version"] == GLYPH_COMPOSER_VERSION
        assert sample["provenance"]["template_id"] == "printed_book_glyph_page"
        assert sample["provenance"]["font_id"] == "real_glyph_bank"
        assert sample["provenance"]["source_corpus"] == (
            "packaged:synthetic/texts/hebrew_typographic_lines_train_v1.txt"
        )
    assert result.report["pages"] == 3
    assert result.report["lines"] == sum(len(page.lines) for page in result.pages)


def test_gold_text_is_the_rendered_glyph_sequence(batch, bank: Path) -> None:
    output, result = batch
    records = {glyph.glyph_id: glyph for glyph in load_glyph_bank(bank).glyphs}
    annotations = json.loads((output / "line_annotations.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "generation_manifest.json").read_text(encoding="utf-8"))
    for page, annotated, sample in zip(result.pages, annotations["pages"], manifest["samples"], strict=True):
        assert [line["text"] for line in annotated["lines"]] == [line.text for line in page.lines]
        assert sample["text"]["logical_order"] == "\n".join(line.text for line in page.lines)
        for line in page.lines:
            assert line.text == unicodedata.normalize("NFC", line.text)
            rebuilt: dict[int, list[str]] = {}
            for glyph in line.glyphs:
                assert records[glyph.glyph_id].char == glyph.bank_char
                rebuilt.setdefault(glyph.char_index, []).append(glyph.bank_char)
            text_without_spaces = []
            for index, char in enumerate(line.text):
                if char == " ":
                    assert index not in rebuilt
                    continue
                drawn = rebuilt.pop(index)
                if drawn == [char]:
                    text_without_spaces.append(char)
                else:
                    # Only gershayim / double quote may be built from two single marks.
                    assert char in ("״", '"') and len(drawn) == 2 and set(drawn) <= {"׳", "'"}
                    text_without_spaces.append(char)
            assert not rebuilt
            assert "".join(text_without_spaces) == line.text.replace(" ", "")


def test_line_polygons_contain_their_glyph_boxes(batch) -> None:
    output, result = batch
    annotations = json.loads((output / "line_annotations.json").read_text(encoding="utf-8"))
    for page, annotated in zip(result.pages, annotations["pages"], strict=True):
        for line, line_annotation in zip(page.lines, annotated["lines"], strict=True):
            for glyph in line.glyphs:
                left, top, right, bottom = glyph.box
                corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
                rotated = [_rotated_point(point, page.rotation_degrees, page.size) for point in corners]
                assert polygon_contains(line_annotation["polygon"], rotated), (line.text, glyph)
            xs = [x for x, _y in line_annotation["baseline"]]
            assert xs == sorted(xs) and xs[0] < xs[-1]


def test_one_style_per_page_and_size_band(batch, bank: Path) -> None:
    _output, result = batch
    loaded = load_glyph_bank(bank)
    records = {glyph.glyph_id: glyph for glyph in loaded.glyphs}
    for page in result.pages:
        for line in page.lines:
            styles = {records[glyph.glyph_id].style_id for glyph in line.glyphs}
            assert styles == {page.style_id}
            heights = [records[glyph.glyph_id].x_height_px for glyph in line.glyphs]
            # Every glyph of one line comes from one size band.
            assert max(heights) / min(heights) <= (1 + SIZE_BAND_TOLERANCE) / (1 - SIZE_BAND_TOLERANCE)
        body = [line for line in page.lines if line.region == "body"]
        body_target = loaded.styles[page.style_id].metrics.x_height_px
        for line in body:
            for glyph in line.glyphs:
                assert abs(records[glyph.glyph_id].x_height_px / body_target - 1) <= SIZE_BAND_TOLERANCE


def test_provenance_sidecar(batch) -> None:
    output, result = batch
    provenance = json.loads((output / "glyph_provenance.json").read_text(encoding="utf-8"))
    assert provenance["generation_manifest_sha256"] == sha256_file(output / "generation_manifest.json")
    assert provenance["bank"]["bank_id"] == "pgb-fixture"
    assert {style["style_id"] for style in provenance["styles"]} == {page.style_id for page in result.pages}
    for entry, page in zip(provenance["pages"], result.pages, strict=True):
        assert entry["page_sha256"] == page.sha256
        assert entry["glyph_count"] == sum(len(line.glyphs) for line in page.lines)


def test_determinism_by_seed(bank: Path, tmp_path: Path) -> None:
    first = compose_glyph_batch(bank, 2, 23, tmp_path / "a")
    second = compose_glyph_batch(bank, 2, 23, tmp_path / "b")
    other = compose_glyph_batch(bank, 2, 24, tmp_path / "c")
    for name in ("generation_manifest.json", "line_annotations.json", "glyph_provenance.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert [page.sha256 for page in first.pages] == [page.sha256 for page in second.pages]
    assert [page.sha256 for page in first.pages] != [page.sha256 for page in other.pages]


def test_missing_char_and_niqqud_lines_are_skipped(bank: Path, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.txt"
    with_shekel = [f"{line} 5 ₪" for line in _plain_lines(10)]
    niqqud = ["שָׁלוֹם עוֹלָם.", "בְּרֵאשִׁית בָּרָא."]
    corpus.write_text("\n".join([*_plain_lines(120), *with_shekel, *niqqud]) + "\n", encoding="utf-8")
    result = compose_glyph_batch(bank, 2, 3, tmp_path / "out", text_corpus_path=corpus)
    assert result.report["text_corpus"]["skipped_lines"] == {"niqqud_or_combining_mark": 2}
    styles = {style["style_id"]: style for style in result.report["styles"]}
    assert styles["fx-alef"]["skipped_missing_glyph"] == 10
    assert ["₪", 10] in styles["fx-alef"]["top_missing_chars"]
    for page in result.pages:
        for line in page.lines:
            assert "₪" not in line.text
            assert not any(unicodedata.category(char).startswith("M") for char in line.text)
    assert result.manifest.samples[0].provenance.source_corpus.startswith("external:sha256:")
    validate_batch(tmp_path / "out")


def test_gershayim_synthesized_from_two_geresh(bank: Path, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.txt"
    lines = [f"צה״ל {line} ת״א" for line in _plain_lines(120)]
    corpus.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = compose_glyph_batch(bank, 1, 5, tmp_path / "out", text_corpus_path=corpus, style_ids=["fx-alef"])
    synthesized = [
        glyph
        for page in result.pages
        for line in page.lines
        for glyph in line.glyphs
        if glyph.gold_char == "״"
    ]
    assert synthesized and all(glyph.bank_char == "׳" for glyph in synthesized)
    by_position: dict[tuple[int, int], list] = {}
    for line_number, line in enumerate(result.pages[0].lines):
        for glyph in line.glyphs:
            if glyph.gold_char == "״":
                by_position.setdefault((line_number, glyph.char_index), []).append(glyph)
    assert all(len(pair) == 2 and pair[0].glyph_id != pair[1].glyph_id for pair in by_position.values())
    provenance = json.loads((tmp_path / "out" / "glyph_provenance.json").read_text(encoding="utf-8"))
    assert provenance["pages"][0]["synthesized_double_marks"] == len(by_position)


def test_style_without_enough_text_is_excluded(tmp_path: Path) -> None:
    bank = build_fixture_bank(
        tmp_path / "bank",
        styles=(
            DEFAULT_STYLES[0],
            FixtureStyle(style_id="fx-sparse", font_file="Alef-Regular.ttf", font_size=36, chars=HEBREW_LETTERS[:10], variants=1),
        ),
    )
    result = compose_glyph_batch(bank, 1, 1, tmp_path / "out")
    assert [style["style_id"] for style in result.report["styles_excluded"]] == ["fx-sparse"]
    with pytest.raises(GlyphCompositionError, match="No style"):
        compose_glyph_batch(bank, 1, 1, tmp_path / "out2", style_ids=["fx-sparse"])
    with pytest.raises(GlyphCompositionError, match="Unknown --style-id"):
        compose_glyph_batch(bank, 1, 1, tmp_path / "out3", style_ids=["nope"])


def test_validate_rejects_missing_or_tampered_provenance(batch, tmp_path: Path) -> None:
    output, _result = batch
    copy = tmp_path / "copy"
    shutil.copytree(output, copy)
    (copy / "glyph_provenance.json").unlink()
    with pytest.raises(BatchValidationError, match="glyph_provenance.json"):
        validate_batch(copy)

    copy = tmp_path / "copy2"
    shutil.copytree(output, copy)
    payload = json.loads((copy / "glyph_provenance.json").read_text(encoding="utf-8"))
    payload["pages"][0]["glyph_count"] += 1
    (copy / "glyph_provenance.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BatchValidationError, match="source_pages"):
        validate_batch(copy)

    copy = tmp_path / "copy3"
    shutil.copytree(output, copy)
    manifest_path = copy / "generation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["samples"][0]["generator_version"] = "s14a-ledger-wrap-v1"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BatchValidationError, match=GLYPH_COMPOSER_VERSION):
        validate_batch(copy)


def test_cli_compose_glyph_pages(bank: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "cli"
    assert main(
        ["compose-glyph-pages", "--glyph-bank", str(bank), "--count", "1", "--seed", "4", "--output", str(output),
         "--min-glyph-score", "0.6", "--provenance-glyph-ids"]
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "glyph_composition_report.v1"
    assert report["pages"] == 1 and report["lines"] > 10 and report["chars"] > 100
    assert report["min_glyph_score"] == 0.6
    assert set(report["text_corpus"]["skipped_lines"]) <= {
        "niqqud_or_combining_mark",
        "control_or_format_char",
        "unsupported_bidi",
    }
    provenance = json.loads((output / "glyph_provenance.json").read_text(encoding="utf-8"))
    used = set(provenance["pages"][0]["glyph_ids"])
    scores = {glyph.glyph_id: glyph.score for glyph in load_glyph_bank(bank).glyphs}
    assert used and all(scores[glyph_id] >= 0.6 for glyph_id in used)
    assert main(["validate", str(output)]) == 0


def test_cli_rejects_bad_bank(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["compose-glyph-pages", "--glyph-bank", str(tmp_path), "--count", "1", "--seed", "1", "--output", str(tmp_path / "o")])
    assert "printed_glyph_bank.json" in capsys.readouterr().err


def test_templates_include_composed(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["templates", "--format", "json"]) == 0
    default = json.loads(capsys.readouterr().out)
    assert "printed_book_glyph_page" not in {entry["template_id"] for entry in default["templates"]}
    assert main(["templates", "--format", "json", "--catalog-version", "v2", "--include-composed"]) == 0
    composed = json.loads(capsys.readouterr().out)
    entry = next(entry for entry in composed["templates"] if entry["template_id"] == "printed_book_glyph_page")
    assert entry["font_id"] == "real_glyph_bank" and entry["page_regions"] == ["title", "body", "footer"]


def test_glyph_whose_mask_lost_ink_is_never_used(bank: Path, tmp_path: Path) -> None:
    from PIL import Image

    copy = _copy_bank(bank, tmp_path)
    records = [json.loads(line) for line in (copy / "glyphs.jsonl").read_text(encoding="utf-8").splitlines()]
    target = next(record for record in records if record["char"] == "ה" and record["style_id"] == "fx-alef")
    mask_path = copy / target["mask_path"]
    mask = Image.open(mask_path).convert("L")
    x0, y0, x1, y1 = target["ink_box"]
    # Erase the left half of the mask: the glyph would draw a broken letter.
    mask.paste(0, (x0, y0, (x0 + x1) // 2, y1))
    mask.convert("1").save(mask_path)
    result = compose_glyph_batch(copy, 2, 9, tmp_path / "out", style_ids=["fx-alef"])
    assert result.report["glyphs_rejected_mask_coverage"] >= 1
    used = {glyph.glyph_id for page in result.pages for line in page.lines for glyph in line.glyphs}
    assert target["glyph_id"] not in used


def test_paper_patch_screening(tmp_path: Path) -> None:
    import random as _random

    from PIL import Image

    from hocrsyngen.glyph_compose import _GlyphImages

    rng = _random.Random(1)
    size = 160
    noise = Image.frombytes("L", (size, size), rng.randbytes(size * size)).point(lambda value: 220 + (value - 128) // 16)
    noise.save(tmp_path / "clean.png")
    gradient = Image.linear_gradient("L").resize((size, size)).point(lambda value: 180 + value // 4)
    Image.blend(gradient, noise, 0.3).save(tmp_path / "gradient.png")
    striped = noise.copy()
    striped.paste(255, (40, 0, 44, size))
    striped.save(tmp_path / "stripe.png")
    images = _GlyphImages(tmp_path)
    clean = images.paper_grain("clean.png")
    assert clean is not None
    assert abs(sum(clean.getdata()) / (clean.width * clean.height) - 128) < 1
    assert images.paper_grain("gradient.png") is None
    assert images.paper_grain("stripe.png") is None


def test_bitonal_style_renders_white_paper(tmp_path: Path) -> None:
    from PIL import Image

    bank = build_fixture_bank(tmp_path / "bank", styles=(DEFAULT_STYLES[0],), paper_gray=255, ink_gray=10)
    result = compose_glyph_batch(bank, 2, 2, tmp_path / "out")
    for page in result.pages:
        with Image.open(page.path) as image:
            corner = image.convert("RGB").crop((0, 0, 120, 120))
            assert min(corner.convert("L").getdata()) >= 248
            red, green, blue = (band.getextrema() for band in corner.split())
            assert red == green == blue
        assert "tint" not in page.degradation and "show_through_opacity" not in page.degradation


def test_light_ink_glyphs_are_not_rejected(tmp_path: Path) -> None:
    bank = build_fixture_bank(tmp_path / "bank", styles=(DEFAULT_STYLES[0],), paper_gray=232, ink_gray=140)
    result = compose_glyph_batch(bank, 1, 2, tmp_path / "out")
    assert result.report["glyphs_rejected_mask_coverage"] == 0


def test_bold_variants_are_excluded_from_body_text(tmp_path: Path) -> None:
    bank = build_fixture_bank(tmp_path / "bank", styles=(DEFAULT_STYLES[0],), bold_letters=True)
    records = [json.loads(line) for line in (bank / "glyphs.jsonl").read_text(encoding="utf-8").splitlines()]
    bold = {record["glyph_id"] for record in records if record.get("fixture_bold")}
    assert len(bold) == len(HEBREW_LETTERS)
    result = compose_glyph_batch(bank, 2, 6, tmp_path / "out")
    used = {glyph.glyph_id for page in result.pages for line in page.lines for glyph in line.glyphs}
    assert used and not used & bold
    style = result.report["styles"][0]
    assert style["body_band_weight_dropped"] >= len(bold) * 0.9


def test_colon_cut_to_one_dot_is_never_drawn(bank: Path, tmp_path: Path) -> None:
    copy = _copy_bank(bank, tmp_path)

    def shrink_colons(records):
        for record in records:
            if record["char"] == ":":
                x0, y0, x1, y1 = record["ink_box"]
                record["ink_box"] = [x0, y1 - max(1, (y1 - y0) // 4), x1, y1]

    rewrite_glyphs(copy, shrink_colons)
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("\n".join([*_plain_lines(120), *(f"{line}: סוף" for line in _plain_lines(20))]) + "\n", encoding="utf-8")
    result = compose_glyph_batch(copy, 2, 4, tmp_path / "out", text_corpus_path=corpus, style_ids=["fx-alef"])
    assert all(":" not in line.text for page in result.pages for line in page.lines)
    style = result.report["styles"][0]
    assert [":", 20] in style["top_missing_chars"]
