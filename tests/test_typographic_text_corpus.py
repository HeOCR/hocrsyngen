"""Deterministic checks for the packaged S13b typographic Hebrew text corpora.

The corpus card lives in ``docs/typographic_text_corpus_card.md``. Mark-class
definitions and the character constants come from
``scripts/typographic_text_corpus_stats.py`` so the card, the report and these
checks count the same thing. Everything here is offline: the hocrgen evaluation
corpus is checked through the S13a hash-only fixture.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import statistics
import unicodedata
from functools import lru_cache
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from hocrsyngen.assets import synthetic_data_path
from hocrsyngen.generator import (
    GOVERNED_TEMPLATE_IDS,
    _recipe_for_template,
    _wrap_hebrew_text,
    generate_batch,
    load_text_corpus,
)
from hocrsyngen.line_annotations import LINE_ANNOTATIONS_FILENAME
from hocrsyngen.validation import validate_batch
from test_training_text_corpus import (
    ALL_FILES as S10B_FILES,
    ARCHIVE_CARD_BODY_WIDTH,
    ARCHIVE_CARD_ROW_CAP,
    BASE_CHARSET,
    EVAL_FILES as S10B_EVAL_FILES,
    FINAL_FORMS,
    HANDWRITTEN_FONT,
    HEBREW_LETTERS,
    PRINTED_FONT,
    WRAPPING_BODIES,
    _font,
    _is_valid_israeli_id,
    _rendered_width,
    _skeleton,
    _word_ngrams,
)
from test_mixed_script_text_corpus import (
    BIDI_CONTROLS,
    BRAND_NAMES,
    EVAL as S13A_EVAL,
    MIXED_FILES as S13A_FILES,
    _hocrgen_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS_CARD_PATH = ROOT / "docs" / "typographic_text_corpus_card.md"
_STATS_SPEC = importlib.util.spec_from_file_location(
    "typographic_text_corpus_stats", ROOT / "scripts" / "typographic_text_corpus_stats.py"
)
assert _STATS_SPEC is not None and _STATS_SPEC.loader is not None
STATS = importlib.util.module_from_spec(_STATS_SPEC)
_STATS_SPEC.loader.exec_module(STATS)

TRAIN = STATS.TYPOGRAPHIC_TRAIN
EVAL = STATS.TYPOGRAPHIC_EVAL
TYPOGRAPHIC_FILES = (TRAIN, EVAL)
# Held-out text that the typographic files must not leak into.
PROTECTED_EVAL_FILES = (*S10B_EVAL_FILES, S13A_EVAL)

# The S10b set without ASCII quotes (this register writes ׳ ״ and “ ” instead),
# plus em and en dash, geresh, gershayim, typographic quotes and the ellipsis.
TYPOGRAPHIC_CHARSET = (BASE_CHARSET - STATS.ASCII_STAND_INS) | STATS.TYPOGRAPHIC_MARKS
OPENERS = {"(": ")", STATS.LEFT_DOUBLE: STATS.RIGHT_DOUBLE, STATS.LOW_DOUBLE: STATS.RIGHT_DOUBLE,
           STATS.LEFT_SINGLE: STATS.RIGHT_SINGLE}
CLOSERS = frozenset(OPENERS.values())

MIN_TRAIN_LINES = 3500
EVAL_LINE_RANGE = (350, 480)
MAX_LINE_CHARS = 55
LONG_LINE_SHARE = (0.18, 0.35)
MEDIAN_LENGTH_RANGE = (18, 30)
# Realistic rates: share of lines carrying each class, in both files.
RATE_BANDS = {
    "gershayim_in_word": (0.22, 0.45),
    "geresh_after_letter": (0.12, 0.30),
    "em_dash": (0.10, 0.25),
    "en_dash": (0.06, 0.16),
    "double_quotes": (0.06, 0.18),
    "ellipsis": (0.02, 0.10),
    "semicolon": (0.02, 0.10),
    "no_typographic_mark": (0.20, 0.45),
}
# A typeset line carries one or two kinds of mark, not one of each.
MAX_FOUR_KIND_SHARE = 0.03
# Minimum lines per class (train, eval); floors are about 75% of the observed
# train count and of the proportional eval count. See the card.
MIN_CLASS_LINES = {
    "gershayim_in_word": (1110, 70),
    "geresh_after_letter": (630, 42),
    "geresh_letter_numeral": (410, 29),
    "geresh_foreign_sound": (64, 5),
    "em_dash": (586, 37),
    "en_dash_range": (231, 11),
    "en_dash_spaced": (137, 11),
    "double_quotes": (339, 22),
    "low_double_quotes": (101, 7),
    "single_quotes": (22, 2),
    "ellipsis": (151, 9),
    "semicolon": (174, 12),
}
MAX_TRAIN_TO_EVAL_WORD3_SHARE = 0.05


@lru_cache(maxsize=None)
def _lines(file_name: str) -> tuple[str, ...]:
    return tuple(synthetic_data_path(f"texts/{file_name}").read_text(encoding="utf-8").split("\n")[:-1])


def _nfc(line: str) -> str:
    return unicodedata.normalize("NFC", line)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _word3_types(lines: tuple[str, ...]) -> set[tuple[str, ...]]:
    return set().union(*(_word_ngrams(_nfc(line), 3) for line in lines))


def _neighbours(line: str, index: int) -> tuple[str, str]:
    return (line[index - 1] if index else "", line[index + 1] if index + 1 < len(line) else "")


# --- format, normalisation and logical order ---


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_corpus_file_is_clean_lf_utf8_with_one_line_per_row(file_name: str) -> None:
    text = synthetic_data_path(f"texts/{file_name}").read_bytes().decode("utf-8")
    assert not text.startswith("﻿") and "\r" not in text
    assert text.endswith("\n") and not text.endswith("\n\n")
    for line in _lines(file_name):
        assert line and line == line.strip(), f"blank or padded line: {line!r}"
        assert "  " not in line and "\t" not in line, f"irregular spacing: {line!r}"
    assert tuple(load_text_corpus(synthetic_data_path(f"texts/{file_name}"))) == _lines(file_name)


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_corpus_lines_are_nfc_unique_and_free_of_bidi_controls(file_name: str) -> None:
    lines = _lines(file_name)
    assert all(_nfc(line) == line for line in lines)
    assert len(set(lines)) == len(lines)
    assert not [line for line in lines if BIDI_CONTROLS & set(line)]


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_corpus_uses_the_typographic_character_set(file_name: str) -> None:
    for line in _lines(file_name):
        for char in line:
            assert char in TYPOGRAPHIC_CHARSET, f"U+{ord(char):04X} not allowed: {line!r}"
        assert any(char in HEBREW_LETTERS for char in line), f"no Hebrew letter in {line!r}"
        assert ".." not in line, f"ASCII dots instead of an ellipsis: {line!r}"


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_lines_are_in_logical_order_with_balanced_quotes(file_name: str) -> None:
    # Visual-order storage puts final forms word-initially and closers before
    # openers; logical order does neither. Quotes pair like parentheses.
    for line in _lines(file_name):
        for index, char in enumerate(line[:-1]):
            if char in FINAL_FORMS:
                assert line[index + 1] not in HEBREW_LETTERS, f"medial final form in {line!r}"
        stack: list[str] = []
        for char in line:
            if char in OPENERS:
                stack.append(OPENERS[char])
            elif char in CLOSERS:
                assert stack and stack.pop() == char, f"unbalanced {char!r} in {line!r}"
        assert stack == [], f"unclosed quote or parenthesis in {line!r}"


def test_non_final_forms_end_words_only_before_geresh_or_gershayim() -> None:
    pattern = re.compile(rf"[א-ת]+[כמנצפ](?![א-ת{STATS.GERESH}{STATS.GERSHAYIM}])")
    offenders = [line for file_name in TYPOGRAPHIC_FILES for line in _lines(file_name) if pattern.search(line)]
    assert offenders == []


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_geresh_and_gershayim_sit_where_hebrew_typesetting_puts_them(file_name: str) -> None:
    for line in _lines(file_name):
        for match in re.finditer(STATS.GERSHAYIM, line):
            before, after = _neighbours(line, match.start())
            assert before in HEBREW_LETTERS and after in HEBREW_LETTERS, f"gershayim outside a word: {line!r}"
        for match in re.finditer(STATS.GERESH, line):
            before, after = _neighbours(line, match.start())
            assert before in HEBREW_LETTERS, f"geresh not after a letter: {line!r}"
            # Inside a word only for the foreign sounds ג׳ ז׳ צ׳.
            assert after not in HEBREW_LETTERS or before in "גזצ", f"geresh inside a word: {line!r}"


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_dashes_and_ellipses_are_spaced_as_typeset(file_name: str) -> None:
    for line in _lines(file_name):
        for match in re.finditer(STATS.EM_DASH, line):
            before, after = _neighbours(line, match.start())
            # Spaced on both sides, or opening a line as a dialogue dash.
            assert after == " " and before in ("", " "), f"unspaced em dash: {line!r}"
        for match in re.finditer(STATS.EN_DASH, line):
            before, after = _neighbours(line, match.start())
            spaced, joined = before == after == " ", before not in ("", " ") and after not in ("", " ")
            assert spaced or joined, f"half-spaced en dash: {line!r}"
        for match in re.finditer(STATS.ELLIPSIS, line):
            before, after = _neighbours(line, match.start())
            assert before != " ", f"detached ellipsis: {line!r}"
            assert after in ("", " ", ")", "?", "!", STATS.RIGHT_DOUBLE, STATS.RIGHT_SINGLE), line


# --- privacy ---


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_corpus_has_no_identity_or_phone_number_patterns_or_brand_names(file_name: str) -> None:
    for line in _lines(file_name):
        for run in re.findall(r"\d+", line):
            assert len(run) < 7, f"long digit run in {line!r}"
            if len(run) >= 5:
                assert not _is_valid_israeli_id(run), f"{run} passes the Israeli ID check digit: {line!r}"
        for joined in re.findall(r"\d+(?:[- ]\d+)+", line):
            assert len(re.sub(r"\D", "", joined)) < 9, f"phone/ID-like digit group in {line!r}"
        assert not BRAND_NAMES.search(line), f"vendor or product name in {line!r}"
        assert "@" not in line and not re.search(r"https?:|www\.", line), f"email or URL in {line!r}"


# --- leakage ---


def test_corpus_sizes() -> None:
    assert len(_lines(TRAIN)) >= MIN_TRAIN_LINES
    assert EVAL_LINE_RANGE[0] <= len(_lines(EVAL)) <= EVAL_LINE_RANGE[1]


def test_typographic_files_share_no_line_with_any_packaged_corpus() -> None:
    seen: dict[str, str] = {}
    for file_name in (*S10B_FILES, *S13A_FILES, *TYPOGRAPHIC_FILES):
        for line in map(_nfc, _lines(file_name)):
            assert line not in seen, f"{line!r} is in both {seen[line]} and {file_name}"
            seen[line] = file_name


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_typographic_files_share_no_line_or_word_trigram_with_hocrgen_eval_corpus(file_name: str) -> None:
    fixture = _hocrgen_hashes()
    lines = _lines(file_name)
    assert not {_sha256(line) for line in lines} & set(fixture["line_sha256"])
    grams = {_sha256(" ".join(gram)) for gram in _word3_types(lines)}
    assert not grams & set(fixture["word3_sha256"])


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
@pytest.mark.parametrize("protected", PROTECTED_EVAL_FILES)
def test_typographic_files_share_no_word_trigram_with_other_eval_text(file_name: str, protected: str) -> None:
    assert not _word3_types(_lines(file_name)) & _word3_types(_lines(protected))


def test_train_word_trigram_overlap_with_typographic_eval_is_low() -> None:
    eval_grams = _word3_types(_lines(EVAL))
    shared = _word3_types(_lines(TRAIN)) & eval_grams
    assert len(shared) / len(eval_grams) <= MAX_TRAIN_TO_EVAL_WORD3_SHARE


def test_train_and_eval_do_not_share_number_or_code_variants() -> None:
    train_skeletons = {_skeleton(line) for line in _lines(TRAIN)}
    assert [line for line in _lines(EVAL) if _skeleton(line) in train_skeletons] == []


def test_eval_characters_all_occur_in_train() -> None:
    assert set("".join(_lines(EVAL))) - set("".join(_lines(TRAIN))) == set()


# --- coverage spec ---


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_marks_occur_at_realistic_rates(file_name: str) -> None:
    lines = list(_lines(file_name))
    counts = STATS.class_counts(lines)
    out_of_band = {
        name: round(counts[name] / len(lines), 3)
        for name, (low, high) in RATE_BANDS.items()
        if not low <= counts[name] / len(lines) <= high
    }
    assert out_of_band == {}
    four_kinds = sum(STATS.mark_kinds(line) >= 4 for line in lines)
    assert four_kinds / len(lines) <= MAX_FOUR_KIND_SHARE


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_every_new_character_occurs(file_name: str) -> None:
    assert STATS.TYPOGRAPHIC_MARKS - set("".join(_lines(file_name))) == set()


@pytest.mark.parametrize("file_name, column", ((TRAIN, 0), (EVAL, 1)))
def test_every_mark_class_is_covered(file_name: str, column: int) -> None:
    counts = STATS.class_counts(list(_lines(file_name)))
    short = {name: (counts[name], minimum[column]) for name, minimum in MIN_CLASS_LINES.items() if counts[name] < minimum[column]}
    assert short == {}


@pytest.mark.parametrize("file_name", TYPOGRAPHIC_FILES)
def test_line_lengths_match_the_s10b_train_mix(file_name: str) -> None:
    lengths = [len(line) for line in _lines(file_name)]
    assert max(lengths) <= MAX_LINE_CHARS
    long_share = sum(31 <= length <= 55 for length in lengths) / len(lengths)
    assert LONG_LINE_SHARE[0] <= long_share <= LONG_LINE_SHARE[1], long_share
    assert sum(36 <= length <= 47 for length in lengths) >= len(lengths) // 10
    assert MEDIAN_LENGTH_RANGE[0] <= statistics.median(lengths) <= MEDIAN_LENGTH_RANGE[1]


def test_train_is_not_a_refilled_template() -> None:
    lines = _lines(TRAIN)
    openings: dict[str, int] = {}
    for line in lines:
        key = " ".join(line.split()[:2])
        openings[key] = openings.get(key, 0) + 1
    assert max(openings.values()) <= 25
    assert len({_skeleton(line) for line in lines}) / len(lines) >= 0.97


# --- fonts: every new character has a real glyph in both packaged fonts ---


@pytest.mark.parametrize("font_file", (PRINTED_FONT, HANDWRITTEN_FONT))
def test_every_new_character_has_a_glyph_in_both_fonts(font_file: str) -> None:
    font = _font(font_file, 48)

    def render(text: str) -> Image.Image:
        image = Image.new("L", (160, 120), 255)
        ImageDraw.Draw(image).text((40, 20), text, font=font, fill=0)
        return image

    notdef = render("")  # a private-use code point: the font's .notdef box
    missing = [
        f"U+{ord(char):04X}"
        for char in sorted(STATS.TYPOGRAPHIC_MARKS)
        if render(char).getbbox() is None
        or ImageChops.invert(render(char)).getbbox() is None
        or ImageChops.difference(render(char), notdef).getbbox() is None
    ]
    assert missing == []


# --- no-loss wrapping (same rule as S10b) ---


@pytest.mark.parametrize("template_id, font_file, size, width, _cap", WRAPPING_BODIES)
def test_no_word_is_wider_than_any_wrapping_body(template_id: str, font_file: str, size: int, width: int, _cap: int | None) -> None:
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    font = _font(font_file, size)
    for token in sorted({token for file_name in TYPOGRAPHIC_FILES for line in _lines(file_name) for token in line.split()}):
        token_width = _rendered_width(draw, token, font)
        assert token_width <= width, f"{template_id}: {token!r} is {token_width}px > {width}px"


def test_archive_card_pages_never_truncate_wrapped_rows() -> None:
    max_rows_per_line = ARCHIVE_CARD_ROW_CAP // _recipe_for_template("archive_card").line_count
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    font = _font(PRINTED_FONT, 38)
    too_long = [
        line
        for file_name in TYPOGRAPHIC_FILES
        for line in _lines(file_name)
        if len(_wrap_hebrew_text(draw, line, font, ARCHIVE_CARD_BODY_WIDTH)) > max_rows_per_line
    ]
    assert too_long == []


# --- generation smoke ---


def test_typographic_corpus_renders_on_every_governed_template(tmp_path: Path) -> None:
    # Two pages per template. The S11b/S12b guards raise on a token that would
    # cross its cell or column, so a clean run is the overflow check; only the
    # ledger may cap wrapped rows (the S10b known truncation).
    manifest = generate_batch(
        2 * len(GOVERNED_TEMPLATE_IDS), 17, tmp_path, list(GOVERNED_TEMPLATE_IDS),
        text_corpus_path=synthetic_data_path(f"texts/{TRAIN}"), emit_line_annotations=True,
    )
    assert validate_batch(tmp_path).sample_count == len(manifest.samples)
    templates = {sample.sample_id: sample.provenance.template_id for sample in manifest.samples}
    assert set(templates.values()) == set(GOVERNED_TEMPLATE_IDS)
    assert {sample.provenance.source_corpus for sample in manifest.samples} == {f"packaged:synthetic/texts/{TRAIN}"}
    pages = json.loads((tmp_path / LINE_ANNOTATIONS_FILENAME).read_text(encoding="utf-8"))["pages"]
    assert [page["sample_id"] for page in pages if page["truncated_segments"] and templates[page["sample_id"]] != "ledger"] == []
    gold = "".join(line["text"] for page in pages for line in page["lines"])
    assert STATS.TYPOGRAPHIC_MARKS & set(gold), "no typographic mark reached the page gold"


def test_corpus_card_records_current_line_counts_and_sha256() -> None:
    card = CORPUS_CARD_PATH.read_text(encoding="utf-8")
    for file_name in TYPOGRAPHIC_FILES:
        digest = hashlib.sha256(synthetic_data_path(f"texts/{file_name}").read_bytes()).hexdigest()
        row = re.search(rf"\| `texts/{re.escape(file_name)}` \| [^|]+ \| (\d+) \| `([0-9a-f]{{64}})` \|", card)
        assert row, f"corpus card has no row for {file_name}"
        assert int(row.group(1)) == len(_lines(file_name))
        assert row.group(2) == digest, f"corpus card sha256 is stale for {file_name}"
