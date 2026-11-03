"""Report token-class coverage, length mix and leakage for the S13a mixed-script corpora.

Usage (from the repository root):

    python scripts/mixed_text_corpus_stats.py            # JSON report

Read-only and deterministic. The pass/fail checks live in
tests/test_mixed_script_text_corpus.py, which imports TOKEN_CLASSES from here
so the card, the report and the tests count the same thing.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXTS_DIR = ROOT / "src" / "hocrsyngen" / "data" / "synthetic" / "texts"
HOCRGEN_HASHES = ROOT / "tests" / "fixtures" / "hocrgen_bidi_synthetic_corpus.hashes.json"
MIXED_TRAIN = "hebrew_mixed_lines_train_v1.txt"
MIXED_EVAL = "hebrew_mixed_lines_eval_v1.txt"
PROTECTED_EVAL = ("hebrew_lines_eval_v1.txt", "hebrew_lines.txt")

_HEB = "א-ת"
_LATIN_TOKEN = r"[A-Za-z][A-Za-z0-9&.+-]*"
_MONTHS_HE = "ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר"
_MONTHS_EN = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_UNITS = (
    r"(?:GB|TB|MB|KB|GHz|MHz|Hz|Mbps|Gbps|kWh|kW|kVA|W|V|A|mAh|mm|cm|km|m|kg|g|ml|L|inch|lux|dB|bar"
    r'|מ"ר|מ"ק|ס"מ|מ"מ|ק"ג|ק"מ|קמ"ש|ליטר|מטר|גרם|טון|וואט|יח\')'
)

# Line-level token classes: a line counts once per class it contains.
TOKEN_CLASSES: dict[str, re.Pattern[str]] = {
    "latin_any": re.compile(r"[A-Za-z]"),
    "latin_word": re.compile(r"(?<![A-Za-z0-9])[A-Za-z][a-z]{2,}(?![A-Za-z0-9])"),
    "acronym": re.compile(r"(?<![A-Za-z0-9-])[A-Z]{2,6}s?(?![A-Za-z0-9])"),
    "latin_run_2plus": re.compile(rf"(?<![A-Za-z0-9]){_LATIN_TOKEN}[),:]? \(?{_LATIN_TOKEN}"),
    "latin_run_3plus": re.compile(rf"(?<![A-Za-z0-9]){_LATIN_TOKEN}[),:]? \(?{_LATIN_TOKEN}[),:]? \(?{_LATIN_TOKEN}"),
    "latin_at_start": re.compile(r"^[(\"']?[A-Za-z]"),
    "latin_at_end": re.compile(r"[A-Za-z][A-Za-z0-9]*[).,:;!?\"']*$"),
    "latin_in_middle": re.compile(rf"[{_HEB}].* \(?[\"']?[A-Za-z][^ ]* .*[{_HEB}]"),
    "alphanumeric_code": re.compile(
        r"(?<![A-Za-z0-9])(?=[A-Za-z0-9/-]*[A-Za-z])(?=[A-Za-z0-9/-]*\d)[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*"
    ),
    "date_slash": re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})(?![\d/])"),
    "date_dot": re.compile(r"(?<![\d.])\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})(?![\d.])"),
    "date_iso": re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)"),
    "date_month_year": re.compile(r"(?<![\d/.])(?:0?[1-9]|1[0-2])[/.]\d{4}(?![\d/.])"),
    "date_hebrew_month": re.compile(rf"(?:\d{{1,2}} )?ב?(?:{_MONTHS_HE}) \d{{4}}"),
    "date_latin_month": re.compile(rf"(?:\d{{1,2}} (?:{_MONTHS_EN})[a-z]* \d{{4}}|(?:{_MONTHS_EN})[a-z]* \d{{1,2}},? \d{{4}}|(?:{_MONTHS_EN})[a-z]* \d{{4}})"),
    "quarter_or_half": re.compile(r"(?<![A-Za-z0-9])[QH][1-4](?![A-Za-z0-9])"),
    "time_of_day": re.compile(r"(?<![\d:])(?:[01]?\d|2[0-3]):[0-5]\d(?![\d:])"),
    "number_with_unit": re.compile(rf"\d(?:[\d,.]*\d)? ?{_UNITS}(?![A-Za-z{_HEB}])"),
    "percent": re.compile(r"\d%"),
    "shekel_sign": re.compile("₪"),
    "nis": re.compile(r"(?<![A-Za-z])NIS(?![A-Za-z])"),
    "shekel_abbreviation": re.compile(r'ש"ח'),
    "foreign_currency": re.compile(r"(?<![A-Za-z])(?:USD|EUR)(?![A-Za-z])"),
    "email": re.compile(r"[a-z0-9.-]+@[a-z0-9-]+\.test(?![A-Za-z])"),
    "url_or_domain": re.compile(r"(?<![@A-Za-z0-9.-])(?:https?://)?(?:www\.)?[a-z0-9-]+\.test(?:/[A-Za-z0-9./-]*)?"),
    "parenthesised_latin": re.compile(r"\([^()]*[A-Za-z][^()]*\)"),
    "parenthesised_hebrew": re.compile(rf"\([^()A-Za-z]*[{_HEB}][^()A-Za-z]*\)"),
    "version_string": re.compile(r"(?<![A-Za-z0-9])v\d+(?:\.\d+)+|גרסה \d+(?:\.\d+)*|Rev\. ?[A-Z0-9]+|(?<![A-Za-z])V\d+\.\d+"),
    "section_number": re.compile(r"(?:סעיף|סעיפים|בסעיף|לסעיף|מסעיף|פרק|פריט|תת-סעיף) \d+(?:\.\d+)*"),
    "grouped_number": re.compile(r"\d{1,3}(?:,\d{3})+"),
    "hyphenated_prefix": re.compile(rf"[{_HEB}]-(?:\d|[A-Za-z])"),
    "slash": re.compile("/"),
    "colon": re.compile(":"),
    "ascii_double_quote": re.compile('"'),
    "gershayim_in_word": re.compile(rf'[{_HEB}]"[{_HEB}]'),
    "geresh_after_letter": re.compile(rf"[{_HEB}]'"),
    "digits_no_latin": re.compile(r"^(?=.*\d)[^A-Za-z]*$"),
    "plain_hebrew": re.compile(r"^[^A-Za-z0-9]*$"),
}


def lines(file_name: str) -> list[str]:
    return (TEXTS_DIR / file_name).read_text(encoding="utf-8").split("\n")[:-1]


def word_ngrams(line: str, size: int = 3) -> set[str]:
    words = line.split()
    return {" ".join(words[index : index + size]) for index in range(len(words) - size + 1)}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def class_counts(corpus: list[str]) -> dict[str, int]:
    return {name: sum(bool(pattern.search(line)) for line in corpus) for name, pattern in TOKEN_CLASSES.items()}


def _overlap(source: list[str], target_lines: list[str]) -> dict[str, float | int]:
    source_grams = set().union(*(word_ngrams(line) for line in source))
    target_grams = set().union(*(word_ngrams(line) for line in target_lines))
    return {
        "shared_lines": len(set(source) & set(target_lines)),
        "word3_types_in_target": len(target_grams),
        "word3_shared_types": len(source_grams & target_grams),
        "word3_shared_share": round(len(source_grams & target_grams) / max(1, len(target_grams)), 4),
    }


def _overlap_hashed(source: list[str], fixture: dict) -> dict[str, float | int]:
    source_grams = {sha256_text(gram) for line in source for gram in word_ngrams(line)}
    target_grams = set(fixture["word3_sha256"])
    return {
        "shared_lines": len({sha256_text(line) for line in source} & set(fixture["line_sha256"])),
        "word3_types_in_target": len(target_grams),
        "word3_shared_types": len(source_grams & target_grams),
        "word3_shared_share": round(len(source_grams & target_grams) / max(1, len(target_grams)), 4),
    }


def _describe(corpus: list[str]) -> dict:
    lengths = [len(line) for line in corpus]
    words = [len(line.split()) for line in corpus]
    counts = class_counts(corpus)
    histogram = Counter(min(length // 5 * 5, 55) for length in lengths)
    return {
        "lines": len(corpus),
        "characters": sum(lengths),
        "character_types": len(set("".join(corpus))),
        "chars_per_line": [min(lengths), statistics.median(lengths), round(statistics.mean(lengths), 1), max(lengths)],
        "words_per_line": [min(words), statistics.median(words), round(statistics.mean(words), 2), max(words)],
        "lines_31_55": sum(31 <= length <= 55 for length in lengths),
        "lines_36_47": sum(36 <= length <= 47 for length in lengths),
        "length_histogram": {f"{low}-{low + 4}" if low < 55 else "55": histogram[low] for low in sorted(histogram)},
        "latin_line_share": round(counts["latin_any"] / len(corpus), 3),
        "latin_characters": sum(char.isascii() and char.isalpha() for line in corpus for char in line),
        "token_class_lines": counts,
    }


def report() -> dict:
    train = lines(MIXED_TRAIN)
    eval_ = lines(MIXED_EVAL)
    fixture = json.loads(HOCRGEN_HASHES.read_text(encoding="utf-8"))
    protected = {name: [unicodedata.normalize("NFC", line) for line in lines(name)] for name in PROTECTED_EVAL}
    overlap = {}
    for label, corpus in (("train", train), ("eval", eval_)):
        for name, target in protected.items():
            overlap[f"{label} -> {name}"] = _overlap(corpus, target)
        overlap[f"{label} -> hocrgen bidi-synthetic-corpus.txt"] = _overlap_hashed(corpus, fixture)
    overlap["train -> hebrew_mixed_lines_eval_v1.txt"] = _overlap(train, eval_)
    return {"train": _describe(train), "eval": _describe(eval_), "overlap": overlap}


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, indent=2))
