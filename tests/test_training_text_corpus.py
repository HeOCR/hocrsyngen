"""Deterministic checks for the packaged R3 training and held-out evaluation text corpora.

The corpus card lives in ``docs/training_text_corpus_card.md``. These checks are
offline and only read packaged text and font files.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from hocrsyngen.assets import synthetic_data_path
from hocrsyngen.generator import CANVAS_SIZE, PAPER_MARGIN, load_text_corpus


DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
CORPUS_CARD_PATH = DOCS_DIR / "training_text_corpus_card.md"

TRAIN = "hebrew_lines_train_v1.txt"
EVAL = "hebrew_lines_eval_v1.txt"
NIQQUD_TRAIN = "hebrew_lines_niqqud_train_v1.txt"
NIQQUD_EVAL = "hebrew_lines_niqqud_eval_v1.txt"
# The original 19 packaged lines are the text of the seed-101 benchmark batch and
# stay eval-only reference text.
REFERENCE_EVAL = "hebrew_lines.txt"
CORPUS_FILES = (TRAIN, EVAL, NIQQUD_TRAIN, NIQQUD_EVAL)
ALL_FILES = (*CORPUS_FILES, REFERENCE_EVAL)
TRAIN_FILES = (TRAIN, NIQQUD_TRAIN)
EVAL_FILES = (EVAL, NIQQUD_EVAL, REFERENCE_EVAL)

HEBREW_LETTERS = frozenset(chr(code) for code in range(0x05D0, 0x05EB))
FINAL_FORMS = frozenset("ךםןףץ")
NIQQUD = frozenset(chr(code) for code in range(0x05B0, 0x05BD)) | {"ׁ", "ׂ", "ׇ"}
LATIN = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
DIGITS = frozenset("0123456789")
# Geresh and gershayim are written with ASCII ' and ", matching the packaged
# reference lines and the generator's own titles and ledger headers.
PUNCTUATION = frozenset(" .,:;!?'\"()-/%+") | {"₪"}
BASE_CHARSET = HEBREW_LETTERS | LATIN | DIGITS | PUNCTUATION
FORBIDDEN_LOOKALIKES = {
    "׳": "Hebrew punctuation geresh (use ASCII ')",
    "״": "Hebrew punctuation gershayim (use ASCII \")",
    "־": "maqaf (use ASCII -)",
    "–": "en dash",
    "—": "em dash",
    "“": "typographic quote",
    "”": "typographic quote",
    "‘": "typographic quote",
    "’": "typographic quote",
}

FONTS_DIR = synthetic_data_path("fonts")
PRINTED_FONT = "Alef-Regular.ttf"
HANDWRITTEN_FONT = "GveretLevin-Regular.ttf"
# Body text regions, mirroring the measurement used by the generator's word wrap.
# printed_letter / handwritten_note: page width minus margins, see _draw_document.
LETTER_BODY_WIDTH = CANVAS_SIZE[0] - (2 * PAPER_MARGIN) - 40
# archive_card: card_right - card_left - 340 with both edges at their worst-case
# -/+10px jitter, see _draw_archive_card. This is the narrowest free-text body.
ARCHIVE_CARD_BODY_WIDTH = (CANVAS_SIZE[0] - PAPER_MARGIN - 70 - 10) - (PAPER_MARGIN + 80 + 10) - 340
# ledger: the "details" column cell (310px minus 28px padding). The generator
# wraps body lines into several rows here by design, so only single tokens must fit.
LEDGER_DETAIL_CELL_WIDTH = 310 - 28
WHOLE_LINE_BUDGETS = (
    ("archive_card", PRINTED_FONT, 38, ARCHIVE_CARD_BODY_WIDTH),
    ("printed_letter", PRINTED_FONT, 42, LETTER_BODY_WIDTH),
    ("handwritten_note", HANDWRITTEN_FONT, 46, LETTER_BODY_WIDTH),
)

MIN_TRAIN_LINES = 6000
EVAL_LINE_RANGE = (550, 700)


@lru_cache(maxsize=None)
def _lines(file_name: str) -> tuple[str, ...]:
    return tuple(synthetic_data_path(f"texts/{file_name}").read_text(encoding="utf-8").split("\n")[:-1])


def _nfc(line: str) -> str:
    return unicodedata.normalize("NFC", line)


def _union(file_names: tuple[str, ...]) -> list[str]:
    return [line for file_name in file_names for line in _lines(file_name)]


@lru_cache(maxsize=8)
def _font(file_name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS_DIR / file_name), size)


def _rendered_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font, direction="rtl")
    return right - left


def _word_ngrams(line: str, size: int) -> set[tuple[str, ...]]:
    words = line.split()
    return {tuple(words[index : index + size]) for index in range(len(words) - size + 1)}


def _skeleton(line: str) -> str:
    """Collapse digit and Latin runs so lines differing only in numbers or codes collide."""

    return re.sub(r"[A-Za-z]+", "a", re.sub(r"\d+", "0", line))


def _is_valid_israeli_id(digits: str) -> bool:
    total = 0
    for index, char in enumerate(digits.zfill(9)):
        value = int(char) * (1 + index % 2)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


@pytest.mark.parametrize("file_name", ALL_FILES)
def test_corpus_file_is_clean_lf_utf8_with_one_line_per_row(file_name: str) -> None:
    raw = synthetic_data_path(f"texts/{file_name}").read_bytes()
    text = raw.decode("utf-8")
    assert not text.startswith("\ufeff")
    assert "\r" not in text
    assert text.endswith("\n") and not text.endswith("\n\n")
    lines = _lines(file_name)
    for line in lines:
        assert line, f"{file_name} has a blank line"
        assert line == line.strip(), f"{file_name} has surrounding whitespace: {line!r}"
        assert "  " not in line and "\t" not in line, f"{file_name} has irregular spacing: {line!r}"
    # The generator's loader must see exactly the same lines.
    assert tuple(load_text_corpus(synthetic_data_path(f"texts/{file_name}"))) == lines


@pytest.mark.parametrize("file_name", CORPUS_FILES)
def test_corpus_lines_are_nfc_and_unique(file_name: str) -> None:
    lines = _lines(file_name)
    assert all(unicodedata.normalize("NFC", line) == line for line in lines)
    assert len(set(lines)) == len(lines), f"{file_name} has duplicate lines"


def test_reference_eval_lines_are_unique_after_nfc() -> None:
    # The 19 reference lines stay byte-for-byte as packaged. One niqqud line is
    # not NFC on disk; the generator NFC-normalizes manifest text, so overlap
    # checks compare the NFC form.
    lines = [_nfc(line) for line in _lines(REFERENCE_EVAL)]
    assert len(set(lines)) == len(lines)


def test_corpus_sizes() -> None:
    assert len(_lines(TRAIN)) >= MIN_TRAIN_LINES
    assert EVAL_LINE_RANGE[0] <= len(_lines(EVAL)) <= EVAL_LINE_RANGE[1]
    assert len(_lines(NIQQUD_TRAIN)) > len(_lines(NIQQUD_EVAL)) > 0
    assert len(_lines(REFERENCE_EVAL)) == 19


def test_all_corpus_files_are_pairwise_disjoint() -> None:
    seen: dict[str, str] = {}
    for file_name in ALL_FILES:
        for line in map(_nfc, _lines(file_name)):
            assert line not in seen, f"{line!r} is in both {seen.get(line)} and {file_name}"
            seen[line] = file_name


def test_train_and_eval_do_not_share_number_or_code_variants() -> None:
    train_skeletons = {_skeleton(line) for line in _union(TRAIN_FILES)}
    leaked = [line for line in map(_nfc, _union(EVAL_FILES)) if _skeleton(line) in train_skeletons]
    assert leaked == []


def test_eval_characters_all_occur_in_train() -> None:
    train_chars = set("".join(_union(TRAIN_FILES)))
    unseen = set("".join(map(_nfc, _union(EVAL_FILES)))) - train_chars
    assert unseen == set()


def test_train_shares_no_word_trigram_with_reference_eval_lines() -> None:
    reference = set().union(*(_word_ngrams(_nfc(line), 3) for line in _lines(REFERENCE_EVAL)))
    shared = [line for line in _union(TRAIN_FILES) if _word_ngrams(line, 3) & reference]
    assert shared == []


@pytest.mark.parametrize("file_name", CORPUS_FILES)
def test_corpus_uses_allowed_character_set(file_name: str) -> None:
    allowed = BASE_CHARSET | (NIQQUD if "niqqud" in file_name else frozenset())
    for line in _lines(file_name):
        for char in line:
            assert char not in FORBIDDEN_LOOKALIKES, f"{FORBIDDEN_LOOKALIKES[char]} in {line!r}"
            assert char in allowed, f"U+{ord(char):04X} not allowed in {file_name}: {line!r}"
        assert any(char in HEBREW_LETTERS for char in line), f"no Hebrew letter in {line!r}"


@pytest.mark.parametrize("file_name", (NIQQUD_TRAIN, NIQQUD_EVAL))
def test_niqqud_subset_is_clearly_separated(file_name: str) -> None:
    assert all(any(char in NIQQUD for char in line) for line in _lines(file_name))


@pytest.mark.parametrize("file_name", (TRAIN, EVAL))
def test_corpus_covers_letters_final_forms_digits_punctuation_and_latin(file_name: str) -> None:
    lines = _lines(file_name)
    chars = set("".join(lines))
    assert HEBREW_LETTERS <= chars
    assert DIGITS <= chars
    assert {".", ",", ":", ";", "!", "?", "'", "\"", "-", "/", "(", ")", "%", "₪"} <= chars
    assert sum(any(char in LATIN for char in line) for line in lines) >= len(lines) // 50
    assert sum(any(char in DIGITS for char in line) for line in lines) >= len(lines) // 10
    # gershayim inside a Hebrew word (e.g. abbreviations) and geresh after a letter
    assert any(re.search(r"[\u05D0-\u05EA]\"[\u05D0-\u05EA]", line) for line in lines)
    assert any(re.search(r"[\u05D0-\u05EA]'", line) for line in lines)


@pytest.mark.parametrize("file_name", CORPUS_FILES)
def test_final_forms_only_appear_in_word_final_position(file_name: str) -> None:
    for line in _lines(file_name):
        letters_only = "".join(char for char in line if char not in NIQQUD)
        for index, char in enumerate(letters_only[:-1]):
            if char in FINAL_FORMS:
                assert letters_only[index + 1] not in HEBREW_LETTERS, f"medial final form in {line!r}"


def test_non_final_forms_do_not_end_plain_words() -> None:
    # Geresh/gershayim abbreviations (מס', עמ') and prefixed numbers (כ-300) are fine.
    # Word-final non-final pe is standard in loanwords (טרמפ, לפטופ), so only כ מ נ צ are checked.
    pattern = re.compile(r"[\u05D0-\u05EA]*[כמנצ](?=$|[ .,:;!?()/%])")
    offenders = [
        line
        for line in _union(CORPUS_FILES)
        for word in pattern.findall("".join(char for char in line if char not in NIQQUD))
        if len(word) > 1
    ]
    assert offenders == []


@pytest.mark.parametrize("file_name", CORPUS_FILES)
def test_corpus_has_no_contact_or_identity_number_patterns(file_name: str) -> None:
    for line in _lines(file_name):
        assert not re.search(r"@|https?:|www\.|\.(com|org|net|il)\b", line), line
        for run in re.findall(r"\d+", line):
            assert len(run) < 7, f"long digit run in {line!r}"
            if len(run) >= 5:
                assert not _is_valid_israeli_id(run), f"{run} passes the Israeli ID check digit: {line!r}"
        for joined in re.findall(r"\d+(?:[- ]\d+)+", line):
            assert len(re.sub(r"\D", "", joined)) < 9, f"phone/ID-like digit group in {line!r}"


@pytest.mark.parametrize("file_name", CORPUS_FILES)
def test_corpus_lines_fit_every_template_body_without_wrapping(file_name: str) -> None:
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    ledger_font = _font(PRINTED_FONT, 30)
    for line in _lines(file_name):
        for template_id, font_file, size, max_width in WHOLE_LINE_BUDGETS:
            width = _rendered_width(draw, line, _font(font_file, size))
            assert width <= max_width, f"{template_id}: {width}px > {max_width}px for {line!r}"
        for token in line.split():
            width = _rendered_width(draw, token, ledger_font)
            assert width <= LEDGER_DETAIL_CELL_WIDTH, f"ledger cell overflow {width}px for {token!r}"


def test_corpus_card_records_current_line_counts_and_sha256() -> None:
    card = CORPUS_CARD_PATH.read_text(encoding="utf-8")
    for file_name in ALL_FILES:
        path = synthetic_data_path(f"texts/{file_name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row = re.search(rf"\| `texts/{re.escape(file_name)}` \| [^|]+ \| (\d+) \| `([0-9a-f]{{64}})` \|", card)
        assert row, f"corpus card has no row for {file_name}"
        assert int(row.group(1)) == len(_lines(file_name))
        assert row.group(2) == digest, f"corpus card sha256 is stale for {file_name}"
