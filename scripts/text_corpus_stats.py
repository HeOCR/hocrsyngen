"""Report statistics and n-gram overlap for the packaged Hebrew text corpora.

Usage (from the repository root):

    python scripts/text_corpus_stats.py            # JSON report
    python scripts/text_corpus_stats.py --top 40   # longer frequency tables

Read-only and deterministic. The pass/fail checks live in
tests/test_training_text_corpus.py; this script only measures.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
TEXTS_DIR = SRC_DIR / "hocrsyngen" / "data" / "synthetic" / "texts"
FILES = {
    "train": "hebrew_lines_train_v1.txt",
    "eval": "hebrew_lines_eval_v1.txt",
    "niqqud_train": "hebrew_lines_niqqud_train_v1.txt",
    "niqqud_eval": "hebrew_lines_niqqud_eval_v1.txt",
    "reference_eval_19": "hebrew_lines.txt",
}
NIQQUD = {chr(code) for code in range(0x05B0, 0x05BD)} | {"ׁ", "ׂ", "ׇ"}


def _lines(name: str) -> list[str]:
    return (TEXTS_DIR / FILES[name]).read_text(encoding="utf-8").split("\n")[:-1]


def _char_class(char: str) -> str:
    if "א" <= char <= "ת":
        return "hebrew_letter"
    if char in NIQQUD:
        return "niqqud"
    if char.isdigit():
        return "digit"
    if char.isascii() and char.isalpha():
        return "latin"
    if char == " ":
        return "space"
    return "punctuation_symbol"


def _ngrams(items: list[str], size: int) -> list[tuple[str, ...]]:
    return [tuple(items[index : index + size]) for index in range(len(items) - size + 1)]


def _word_ngrams(lines: list[str], size: int) -> list[tuple[str, ...]]:
    return [gram for line in lines for gram in _ngrams(line.split(), size)]


def _char_ngrams(lines: list[str], size: int) -> list[str]:
    return [line[index : index + size] for line in lines for index in range(len(line) - size + 1)]


def file_stats(lines: list[str], top: int) -> dict:
    words = [word for line in lines for word in line.split()]
    chars = Counter("".join(lines))
    lengths = [len(line) for line in lines]
    word_counts = [len(line.split()) for line in lines]
    class_counts = Counter()
    for char, count in chars.items():
        class_counts[_char_class(char)] += count
    return {
        "lines": len(lines),
        "characters": sum(lengths),
        "word_tokens": len(words),
        "word_types": len(set(words)),
        "type_token_ratio": round(len(set(words)) / max(1, len(words)), 4),
        "hapax_word_types": sum(1 for count in Counter(words).values() if count == 1),
        "character_types": len(chars),
        "chars_per_line": {
            "min": min(lengths),
            "median": statistics.median(lengths),
            "mean": round(statistics.mean(lengths), 2),
            "max": max(lengths),
        },
        "words_per_line": {
            "min": min(word_counts),
            "median": statistics.median(word_counts),
            "mean": round(statistics.mean(word_counts), 2),
            "max": max(word_counts),
        },
        "line_length_histogram_chars": {
            f"{start}-{start + 4}": sum(1 for length in lengths if start <= length <= start + 4)
            for start in range(0, max(lengths) + 1, 5)
        },
        "character_class_counts": dict(sorted(class_counts.items())),
        "lines_with": {
            "digits": sum(any(char.isdigit() for char in line) for line in lines),
            "latin": sum(any(char.isascii() and char.isalpha() for char in line) for line in lines),
            "geresh_apostrophe": sum("'" in line for line in lines),
            "gershayim_double_quote": sum('"' in line for line in lines),
            "shekel_sign": sum("₪" in line for line in lines),
            "niqqud": sum(any(char in NIQQUD for char in line) for line in lines),
        },
        "hebrew_letter_frequency": {
            char: chars[char] for char in (chr(code) for code in range(0x05D0, 0x05EB))
        },
        "top_characters": [[char, count] for char, count in chars.most_common(top)],
        "top_words": [[word, count] for word, count in Counter(words).most_common(top)],
    }


def overlap(source: list[str], target: list[str]) -> dict:
    """How much of ``target`` is already covered by ``source``."""

    report: dict = {"shared_lines": len(set(source) & set(target))}
    for size in (1, 2, 3):
        source_types = set(_word_ngrams(source, size))
        target_grams = _word_ngrams(target, size)
        target_types = set(target_grams)
        report[f"word_{size}gram"] = {
            "target_types_seen_in_source": round(len(target_types & source_types) / max(1, len(target_types)), 4),
            "target_tokens_seen_in_source": round(
                sum(gram in source_types for gram in target_grams) / max(1, len(target_grams)), 4
            ),
        }
    source_char5 = set(_char_ngrams(source, 5))
    target_char5 = set(_char_ngrams(target, 5))
    report["char_5gram_target_types_seen_in_source"] = round(
        len(target_char5 & source_char5) / max(1, len(target_char5)), 4
    )
    return report


def wrap_report(lines: list[str]) -> dict:
    """Wrapped-row counts per body region and the ledger page truncation rate.

    Uses the generator's own wrap function at each region's worst-case width.
    The ledger draws at most 10 detail rows for 5 sampled lines; the rate is the
    probability that 5 lines drawn independently from ``lines`` wrap to more than
    10 rows (exact convolution, a close approximation of sampling without
    replacement for corpora this size).
    """

    sys.path.insert(0, str(SRC_DIR))
    from PIL import Image, ImageDraw, ImageFont

    from hocrsyngen.generator import _wrap_hebrew_text

    fonts_dir = SRC_DIR / "hocrsyngen" / "data" / "synthetic" / "fonts"
    regions = {
        "printed_letter": ("Alef-Regular.ttf", 42, 968),
        "handwritten_note": ("GveretLevin-Regular.ttf", 46, 968),
        "archive_card": ("Alef-Regular.ttf", 38, 498),
        "ledger": ("Alef-Regular.ttf", 30, 282),
    }
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    report: dict = {}
    for region, (font_file, size, width) in regions.items():
        font = ImageFont.truetype(str(fonts_dir / font_file), size)
        rows = Counter(len(_wrap_hebrew_text(draw, line, font, width)) for line in lines)
        report[f"{region}_rows_per_line"] = {str(count): rows[count] for count in sorted(rows)}
    ledger_rows = {int(count): number for count, number in report["ledger_rows_per_line"].items()}
    distribution = {0: 1.0}
    for _ in range(5):
        step: dict[int, float] = Counter()
        for total, probability in distribution.items():
            for count, number in ledger_rows.items():
                step[total + count] += probability * number / len(lines)
        distribution = step
    report["ledger_page_truncation_rate"] = round(sum(p for total, p in distribution.items() if total > 10), 4)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--top", type=int, default=25, help="rows in frequency tables")
    args = parser.parse_args()
    corpora = {name: _lines(name) for name in FILES}
    train_all = corpora["train"] + corpora["niqqud_train"]
    report = {
        "files": {name: file_stats(lines, args.top) for name, lines in corpora.items()},
        "wrapping": {
            "train": wrap_report(corpora["train"]),
            "reference_eval_19": wrap_report(corpora["reference_eval_19"]),
        },
        "overlap": {
            "train_vs_reference_eval_19": overlap(train_all, corpora["reference_eval_19"]),
            "train_vs_eval": overlap(corpora["train"], corpora["eval"]),
            "niqqud_train_vs_niqqud_eval": overlap(corpora["niqqud_train"], corpora["niqqud_eval"]),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
