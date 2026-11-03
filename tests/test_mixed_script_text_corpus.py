"""Deterministic checks for the packaged S13a mixed Hebrew/Latin/digit text corpora.

The corpus card lives in ``docs/mixed_script_text_corpus_card.md``. Token-class
definitions come from ``scripts/mixed_text_corpus_stats.py`` so the card, the
report and these checks count the same thing. Everything here is offline: the
hocrgen evaluation corpus is checked through a hash-only fixture.
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
from PIL import Image, ImageDraw

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
    EVAL as S10B_EVAL,
    FINAL_FORMS,
    FORBIDDEN_LOOKALIKES,
    HEBREW_LETTERS,
    LATIN,
    PRINTED_FONT,
    REFERENCE_EVAL,
    WRAPPING_BODIES,
    _font,
    _is_valid_israeli_id,
    _rendered_width,
    _skeleton,
    _word_ngrams,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS_CARD_PATH = ROOT / "docs" / "mixed_script_text_corpus_card.md"
HOCRGEN_HASHES_PATH = Path(__file__).resolve().parent / "fixtures" / "hocrgen_bidi_synthetic_corpus.hashes.json"
_STATS_SPEC = importlib.util.spec_from_file_location("mixed_text_corpus_stats", ROOT / "scripts" / "mixed_text_corpus_stats.py")
assert _STATS_SPEC is not None and _STATS_SPEC.loader is not None
STATS = importlib.util.module_from_spec(_STATS_SPEC)
_STATS_SPEC.loader.exec_module(STATS)

TRAIN = "hebrew_mixed_lines_train_v1.txt"
EVAL = "hebrew_mixed_lines_eval_v1.txt"
MIXED_FILES = (TRAIN, EVAL)
# Held-out text that the mixed train file must not leak into.
PROTECTED_EVAL_FILES = (EVAL, S10B_EVAL, REFERENCE_EVAL)

# S13a adds "@" (emails) and "&" (R&D-style terms) to the S10b character set.
MIXED_CHARSET = BASE_CHARSET | {"@", "&"}
BIDI_CONTROLS = frozenset("؜‎‏‪‫‬‭‮⁦⁧⁨⁩")
RESERVED_HOST = re.compile(r"(?:[a-z0-9-]+\.)*(?:[a-z0-9-]+\.test|example\.(?:com|org|net))")
DOMAIN_LIKE = re.compile(
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|org|net|il|io|co|gov|edu|info|biz|test|example|invalid|ai|app|dev|me|tv|uk|us|eu)(?![A-Za-z0-9])",
    re.IGNORECASE,
)
# A guard, not a complete list: well-known vendor and product names must not appear.
BRAND_NAMES = re.compile(
    r"(?<![A-Za-z])(?:microsoft|windows|excel|outlook|google|gmail|android|apple|iphone|ipad|macos|cisco|dell|"
    r"lenovo|samsung|intel|nvidia|oracle|sap|ibm|xerox|siemens|philips|bosch|toyota|tesla|amazon|aws|azure|"
    r"whatsapp|facebook|linkedin|youtube|adobe|autocad|vmware|salesforce)(?![A-Za-z])",
    re.IGNORECASE,
)

MIN_TRAIN_LINES = 4000
EVAL_LINE_RANGE = (360, 450)
MAX_LINE_CHARS = 55
LATIN_LINE_SHARE = (0.30, 0.45)
# S10b train: 24% of lines are 31-55 characters, median 23.
LONG_LINE_SHARE = (0.18, 0.35)
MEDIAN_LENGTH_RANGE = (18, 30)
# Minimum lines per token class (train, eval). Every class in the coverage spec
# is required; see the card for observed counts.
MIN_CLASS_LINES = {
    "latin_word": (1050, 51),
    "acronym": (550, 25),
    "latin_run_2plus": (550, 27),
    "latin_run_3plus": (100, 5),
    "latin_at_start": (500, 23),
    "latin_at_end": (550, 29),
    "latin_in_middle": (550, 27),
    "alphanumeric_code": (350, 13),
    "date_slash": (90, 3),
    "date_dot": (80, 4),
    "date_iso": (40, 2),
    "date_month_year": (50, 4),
    "date_hebrew_month": (50, 4),
    "date_latin_month": (50, 2),
    "quarter_or_half": (40, 2),
    "time_of_day": (140, 6),
    "number_with_unit": (300, 10),
    "percent": (200, 12),
    "shekel_sign": (200, 12),
    "nis": (30, 2),
    "shekel_abbreviation": (60, 3),
    "foreign_currency": (40, 2),
    "email": (90, 4),
    "url_or_domain": (60, 2),
    "parenthesised_latin": (200, 14),
    "parenthesised_hebrew": (110, 3),
    "version_string": (130, 4),
    "section_number": (110, 5),
    "grouped_number": (250, 11),
    "hyphenated_prefix": (350, 24),
    "gershayim_in_word": (300, 11),
    "geresh_after_letter": (250, 10),
    "plain_hebrew": (700, 35),
}
MAX_TRAIN_TO_EVAL_WORD3_SHARE = 0.05


@lru_cache(maxsize=None)
def _lines(file_name: str) -> tuple[str, ...]:
    return tuple(synthetic_data_path(f"texts/{file_name}").read_text(encoding="utf-8").split("\n")[:-1])


def _nfc(line: str) -> str:
    return unicodedata.normalize("NFC", line)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _hocrgen_hashes() -> dict:
    return json.loads(HOCRGEN_HASHES_PATH.read_text(encoding="utf-8"))


def _word3_types(lines: tuple[str, ...]) -> set[tuple[str, ...]]:
    return set().union(*(_word_ngrams(_nfc(line), 3) for line in lines))


# --- format, normalisation and logical order ---


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_corpus_file_is_clean_lf_utf8_with_one_line_per_row(file_name: str) -> None:
    text = synthetic_data_path(f"texts/{file_name}").read_bytes().decode("utf-8")
    assert not text.startswith("﻿") and "\r" not in text
    assert text.endswith("\n") and not text.endswith("\n\n")
    for line in _lines(file_name):
        assert line and line == line.strip(), f"blank or padded line: {line!r}"
        assert "  " not in line and "\t" not in line, f"irregular spacing: {line!r}"
    assert tuple(load_text_corpus(synthetic_data_path(f"texts/{file_name}"))) == _lines(file_name)


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_corpus_lines_are_nfc_unique_and_free_of_bidi_controls(file_name: str) -> None:
    lines = _lines(file_name)
    assert all(_nfc(line) == line for line in lines)
    assert len(set(lines)) == len(lines)
    assert not [line for line in lines if BIDI_CONTROLS & set(line)]


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_corpus_uses_allowed_character_set(file_name: str) -> None:
    for line in _lines(file_name):
        for char in line:
            assert char not in FORBIDDEN_LOOKALIKES, f"{FORBIDDEN_LOOKALIKES[char]} in {line!r}"
            assert char in MIXED_CHARSET, f"U+{ord(char):04X} not allowed: {line!r}"
        assert any(char in HEBREW_LETTERS for char in line), f"no Hebrew letter in {line!r}"


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_lines_are_in_logical_order(file_name: str) -> None:
    # Visual-order (reversed) storage puts Hebrew final forms word-initially and
    # closing parentheses before opening ones; logical order does neither.
    for line in _lines(file_name):
        for index, char in enumerate(line[:-1]):
            if char in FINAL_FORMS:
                assert line[index + 1] not in HEBREW_LETTERS, f"medial final form in {line!r}"
        depth = 0
        for char in line:
            depth += {"(": 1, ")": -1}.get(char, 0)
            assert depth >= 0, f"')' before '(' in {line!r}"
        assert depth == 0, f"unbalanced parentheses in {line!r}"


def test_non_final_forms_do_not_end_plain_words() -> None:
    pattern = re.compile(r"[א-ת]*[כמנצ](?=$|[ .,:;!?()/%@&])")
    offenders = [line for file_name in MIXED_FILES for line in _lines(file_name) for word in pattern.findall(line) if len(word) > 1]
    assert offenders == []


# --- privacy ---


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_emails_and_urls_use_reserved_domains_only(file_name: str) -> None:
    for line in _lines(file_name):
        for token in line.split():
            core = token.strip("().,:;!?\"'")
            if "@" in core:
                local, _, host = core.partition("@")
                assert re.fullmatch(r"[a-z0-9.-]+", local) and RESERVED_HOST.fullmatch(host), line
                continue
            for match in DOMAIN_LIKE.finditer(core):
                host = match.group(0).lower().removeprefix("www.")
                assert RESERVED_HOST.fullmatch(host), f"non-reserved domain {match.group(0)!r} in {line!r}"
        if re.search(r"https?:|www\.", line):
            assert re.search(r"\.test(?![A-Za-z0-9])|example\.(?:com|org|net)", line), line


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_corpus_has_no_identity_or_phone_number_patterns_or_brand_names(file_name: str) -> None:
    for line in _lines(file_name):
        for run in re.findall(r"\d+", line):
            assert len(run) < 7, f"long digit run in {line!r}"
            if len(run) >= 5:
                assert not _is_valid_israeli_id(run), f"{run} passes the Israeli ID check digit: {line!r}"
        for joined in re.findall(r"\d+(?:[- ]\d+)+", line):
            assert len(re.sub(r"\D", "", joined)) < 9, f"phone/ID-like digit group in {line!r}"
        assert not BRAND_NAMES.search(line), f"vendor or product name in {line!r}"


# --- leakage ---


def test_corpus_sizes() -> None:
    assert len(_lines(TRAIN)) >= MIN_TRAIN_LINES
    assert EVAL_LINE_RANGE[0] <= len(_lines(EVAL)) <= EVAL_LINE_RANGE[1]


def test_mixed_files_share_no_line_with_any_packaged_corpus() -> None:
    seen: dict[str, str] = {}
    for file_name in (*S10B_FILES, *MIXED_FILES):
        for line in map(_nfc, _lines(file_name)):
            assert line not in seen, f"{line!r} is in both {seen[line]} and {file_name}"
            seen[line] = file_name


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_mixed_files_share_no_line_or_word_trigram_with_hocrgen_eval_corpus(file_name: str) -> None:
    fixture = _hocrgen_hashes()
    assert fixture["source"]["commit"] == "c8fb74eb5d0afedd812a0da69562e4610a0b3394"
    assert len(fixture["line_sha256"]) == fixture["source"]["lines"] == 100
    lines = _lines(file_name)
    assert not {_sha256(line) for line in lines} & set(fixture["line_sha256"])
    grams = {_sha256(" ".join(gram)) for gram in _word3_types(lines)}
    assert not grams & set(fixture["word3_sha256"])


@pytest.mark.parametrize("file_name", MIXED_FILES)
@pytest.mark.parametrize("protected", (S10B_EVAL, REFERENCE_EVAL))
def test_mixed_files_share_no_word_trigram_with_s10b_eval_text(file_name: str, protected: str) -> None:
    assert not _word3_types(_lines(file_name)) & _word3_types(_lines(protected))


def test_train_word_trigram_overlap_with_mixed_eval_is_low() -> None:
    eval_grams = _word3_types(_lines(EVAL))
    shared = _word3_types(_lines(TRAIN)) & eval_grams
    assert len(shared) / len(eval_grams) <= MAX_TRAIN_TO_EVAL_WORD3_SHARE


def test_train_and_eval_do_not_share_number_or_code_variants() -> None:
    train_skeletons = {_skeleton(line) for line in _lines(TRAIN)}
    assert [line for line in _lines(EVAL) if _skeleton(line) in train_skeletons] == []


def test_eval_characters_all_occur_in_train() -> None:
    assert set("".join(_lines(EVAL))) - set("".join(_lines(TRAIN))) == set()


# --- coverage spec ---


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_latin_line_share_is_in_target_band(file_name: str) -> None:
    lines = _lines(file_name)
    share = sum(any(char in LATIN for char in line) for line in lines) / len(lines)
    assert LATIN_LINE_SHARE[0] <= share <= LATIN_LINE_SHARE[1], share


@pytest.mark.parametrize("file_name", MIXED_FILES)
def test_line_lengths_match_the_s10b_train_mix(file_name: str) -> None:
    lengths = [len(line) for line in _lines(file_name)]
    assert max(lengths) <= MAX_LINE_CHARS
    long_share = sum(31 <= length <= 55 for length in lengths) / len(lengths)
    assert LONG_LINE_SHARE[0] <= long_share <= LONG_LINE_SHARE[1], long_share
    assert sum(36 <= length <= 47 for length in lengths) >= len(lengths) // 10
    assert MEDIAN_LENGTH_RANGE[0] <= statistics.median(lengths) <= MEDIAN_LENGTH_RANGE[1]


@pytest.mark.parametrize("file_name, column", ((TRAIN, 0), (EVAL, 1)))
def test_every_token_class_is_covered(file_name: str, column: int) -> None:
    counts = STATS.class_counts(list(_lines(file_name)))
    short = {name: (counts[name], minimum[column]) for name, minimum in MIN_CLASS_LINES.items() if counts[name] < minimum[column]}
    assert short == {}


def test_train_is_not_a_refilled_template() -> None:
    lines = _lines(TRAIN)
    openings: dict[str, int] = {}
    for line in lines:
        key = " ".join(line.split()[:2])
        openings[key] = openings.get(key, 0) + 1
    assert max(openings.values()) <= 25
    skeleton_share = len({_skeleton(line) for line in lines}) / len(lines)
    assert skeleton_share >= 0.97


# --- no-loss wrapping (same rule as S10b) ---


@pytest.mark.parametrize("template_id, font_file, size, width, _cap", WRAPPING_BODIES)
def test_no_word_is_wider_than_any_wrapping_body(template_id: str, font_file: str, size: int, width: int, _cap: int | None) -> None:
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    font = _font(font_file, size)
    for token in sorted({token for file_name in MIXED_FILES for line in _lines(file_name) for token in line.split()}):
        token_width = _rendered_width(draw, token, font)
        assert token_width <= width, f"{template_id}: {token!r} is {token_width}px > {width}px"


def test_archive_card_pages_never_truncate_wrapped_rows() -> None:
    max_rows_per_line = ARCHIVE_CARD_ROW_CAP // _recipe_for_template("archive_card").line_count
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    font = _font(PRINTED_FONT, 38)
    too_long = [
        line
        for file_name in MIXED_FILES
        for line in _lines(file_name)
        if len(_wrap_hebrew_text(draw, line, font, ARCHIVE_CARD_BODY_WIDTH)) > max_rows_per_line
    ]
    assert too_long == []


# --- generation smoke ---


def test_mixed_corpus_renders_on_every_governed_template(tmp_path: Path) -> None:
    # Two pages per template. The S11b/S12b guards raise on a token that would
    # cross its cell or column, so a clean run is the overflow check; only the
    # ledger may cap wrapped rows (the S10b known truncation).
    manifest = generate_batch(
        2 * len(GOVERNED_TEMPLATE_IDS), 13, tmp_path, list(GOVERNED_TEMPLATE_IDS),
        text_corpus_path=synthetic_data_path(f"texts/{TRAIN}"), emit_line_annotations=True,
    )
    assert validate_batch(tmp_path).sample_count == len(manifest.samples)
    templates = {sample.sample_id: sample.provenance.template_id for sample in manifest.samples}
    assert set(templates.values()) == set(GOVERNED_TEMPLATE_IDS)
    assert {sample.provenance.source_corpus for sample in manifest.samples} == {f"packaged:synthetic/texts/{TRAIN}"}
    pages = json.loads((tmp_path / LINE_ANNOTATIONS_FILENAME).read_text(encoding="utf-8"))["pages"]
    assert [page["sample_id"] for page in pages if page["truncated_segments"] and templates[page["sample_id"]] != "ledger"] == []
    body = [line["text"] for page in pages for line in page["lines"] if line["region"] in {"body", "table_cells"}]
    assert any(char in LATIN for text in body for char in text)
    assert any(char.isdigit() for text in body for char in text)


def test_corpus_card_records_current_line_counts_and_sha256() -> None:
    card = CORPUS_CARD_PATH.read_text(encoding="utf-8")
    for file_name in MIXED_FILES:
        digest = hashlib.sha256(synthetic_data_path(f"texts/{file_name}").read_bytes()).hexdigest()
        row = re.search(rf"\| `texts/{re.escape(file_name)}` \| [^|]+ \| (\d+) \| `([0-9a-f]{{64}})` \|", card)
        assert row, f"corpus card has no row for {file_name}"
        assert int(row.group(1)) == len(_lines(file_name))
        assert row.group(2) == digest, f"corpus card sha256 is stale for {file_name}"
