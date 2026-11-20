"""Report punctuation-class coverage, length mix and leakage for the S13b typographic corpora.

Usage (from the repository root):

    python scripts/typographic_text_corpus_stats.py            # JSON report

Read-only and deterministic. The pass/fail checks live in
tests/test_typographic_text_corpus.py, which imports MARK_CLASSES and the
character constants from here so the card, the report and the tests count the
same thing.
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
TYPOGRAPHIC_TRAIN = "hebrew_typographic_lines_train_v1.txt"
TYPOGRAPHIC_EVAL = "hebrew_typographic_lines_eval_v1.txt"
PROTECTED_EVAL = ("hebrew_lines_eval_v1.txt", "hebrew_lines.txt", "hebrew_mixed_lines_eval_v1.txt")

EM_DASH, EN_DASH = "—", "–"
GERESH, GERSHAYIM = "׳", "״"
LEFT_DOUBLE, RIGHT_DOUBLE, LOW_DOUBLE = "“", "”", "„"
LEFT_SINGLE, RIGHT_SINGLE = "‘", "’"
ELLIPSIS = "…"
# The characters S13b adds; the S10b and S13a corpora reject all of them.
TYPOGRAPHIC_MARKS = frozenset(
    (EM_DASH, EN_DASH, GERESH, GERSHAYIM, LEFT_DOUBLE, RIGHT_DOUBLE, LOW_DOUBLE, LEFT_SINGLE, RIGHT_SINGLE, ELLIPSIS)
)
# In this typeset register, ASCII quotes are never used for quotation marks or
# for geresh/gershayim, and an ellipsis is never three full stops.
ASCII_STAND_INS = frozenset("'\"")

_HEB = "א-ת"

# Line-level classes: a line counts once per class it contains.
MARK_CLASSES: dict[str, re.Pattern[str]] = {
    "gershayim_in_word": re.compile(rf"[{_HEB}]{GERSHAYIM}[{_HEB}]"),
    "geresh_after_letter": re.compile(rf"[{_HEB}]{GERESH}"),
    "geresh_letter_numeral": re.compile(rf"(?<![{_HEB}])[{_HEB}]{GERESH}(?![{_HEB}])"),
    "geresh_foreign_sound": re.compile(rf"[גזצ]{GERESH}[{_HEB}]"),
    "em_dash": re.compile(EM_DASH),
    "en_dash": re.compile(EN_DASH),
    "en_dash_range": re.compile(rf"[0-9{_HEB}{GERESH}]{EN_DASH}[0-9{_HEB}]"),
    "en_dash_spaced": re.compile(f" {EN_DASH} "),
    "double_quotes": re.compile(f"{LEFT_DOUBLE}[^{RIGHT_DOUBLE}]+{RIGHT_DOUBLE}"),
    "low_double_quotes": re.compile(f"{LOW_DOUBLE}[^{RIGHT_DOUBLE}]+{RIGHT_DOUBLE}"),
    "single_quotes": re.compile(f"{LEFT_SINGLE}[^{RIGHT_SINGLE}]+{RIGHT_SINGLE}"),
    "ellipsis": re.compile(ELLIPSIS),
    "semicolon": re.compile(";"),
    "digits": re.compile(r"\d"),
    "latin": re.compile(r"[A-Za-z]"),
}
# The punctuation kinds counted for "how many kinds does one line carry".
MARK_KINDS = ("gershayim_in_word", "geresh_after_letter", "em_dash", "en_dash_range", "en_dash_spaced",
              "double_quotes", "low_double_quotes", "single_quotes", "ellipsis", "semicolon")


def lines(file_name: str) -> list[str]:
    return (TEXTS_DIR / file_name).read_text(encoding="utf-8").split("\n")[:-1]


def word_ngrams(line: str, size: int = 3) -> set[str]:
    words = unicodedata.normalize("NFC", line).split()
    return {" ".join(words[index : index + size]) for index in range(len(words) - size + 1)}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def has_typographic_mark(line: str) -> bool:
    return bool(TYPOGRAPHIC_MARKS & set(line)) or ";" in line


def mark_kinds(line: str) -> int:
    return sum(bool(MARK_CLASSES[name].search(line)) for name in MARK_KINDS)


def class_counts(corpus: list[str]) -> dict[str, int]:
    counts = {name: sum(bool(pattern.search(line)) for line in corpus) for name, pattern in MARK_CLASSES.items()}
    counts["no_typographic_mark"] = sum(not has_typographic_mark(line) for line in corpus)
    return counts


def _overlap(source: list[str], target_lines: list[str]) -> dict[str, float | int]:
    source_lines = set(map(unicodedata.normalize, ["NFC"] * len(source), source))
    source_grams = set().union(*(word_ngrams(line) for line in source))
    target_grams = set().union(*(word_ngrams(line) for line in target_lines))
    shared = source_grams & target_grams
    return {
        "shared_lines": sum(unicodedata.normalize("NFC", line) in source_lines for line in target_lines),
        "target_word3_types": len(target_grams),
        "shared_word3_types": len(shared),
        "shared_word3_share": round(len(shared) / len(target_grams), 4) if target_grams else 0.0,
    }


def _overlap_hashed(source: list[str], fixture: dict) -> dict[str, float | int]:
    source_lines = {sha256_text(unicodedata.normalize("NFC", line)) for line in source}
    grams = {sha256_text(gram) for line in source for gram in word_ngrams(line)}
    return {
        "shared_lines": len(source_lines & set(fixture["line_sha256"])),
        "target_word3_types": len(fixture["word3_sha256"]),
        "shared_word3_types": len(grams & set(fixture["word3_sha256"])),
    }


def _describe(corpus: list[str]) -> dict:
    lengths = [len(line) for line in corpus]
    chars = Counter("".join(corpus))
    counts = class_counts(corpus)
    return {
        "lines": len(corpus),
        "characters": sum(lengths),
        "character_types": len(chars),
        "chars_per_line": {"min": min(lengths), "median": statistics.median(lengths), "mean": round(statistics.mean(lengths), 1), "max": max(lengths)},
        "lines_31_55": sum(31 <= n <= 55 for n in lengths),
        "lines_36_47": sum(36 <= n <= 47 for n in lengths),
        "length_histogram": {f"{lo}-{lo + 4 if lo < 50 else 55}": sum(lo <= n <= (lo + 4 if lo < 50 else 55) for n in lengths) for lo in range(0, 55, 5)},
        "mark_counts": {char: chars[char] for char in sorted(TYPOGRAPHIC_MARKS | {";"})},
        "class_lines": counts,
        "class_shares": {name: round(count / len(corpus), 3) for name, count in counts.items()},
        "lines_by_mark_kinds": dict(sorted(Counter(mark_kinds(line) for line in corpus).items())),
    }


def report() -> dict:
    train, held_out = lines(TYPOGRAPHIC_TRAIN), lines(TYPOGRAPHIC_EVAL)
    fixture = json.loads(HOCRGEN_HASHES.read_text(encoding="utf-8"))
    leakage = {"train_to_eval": _overlap(train, held_out)}
    for name in PROTECTED_EVAL:
        leakage[f"train_to_{name}"] = _overlap(train, lines(name))
        leakage[f"eval_to_{name}"] = _overlap(held_out, lines(name))
    leakage["train_to_hocrgen_bidi_synthetic_corpus"] = _overlap_hashed(train, fixture)
    leakage["eval_to_hocrgen_bidi_synthetic_corpus"] = _overlap_hashed(held_out, fixture)
    return {"train": _describe(train), "eval": _describe(held_out), "leakage": leakage}


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, indent=2))
