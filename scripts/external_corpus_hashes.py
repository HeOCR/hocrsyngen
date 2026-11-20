"""Write a hash-only leakage fixture for an external evaluation corpus.

Usage (from the repository root):

    python scripts/external_corpus_hashes.py PATH \
        --repository HeOCR/hocrgen \
        --source-path docs/evaluation-fixtures/bidi-synthetic-corpus.txt \
        --commit <full sha> \
        --output tests/fixtures/<name>.hashes.json

The fixture records the source file's sha256 and line count, plus the sha256 of
every NFC line and every word 3-gram (words joined by one space). No source
text is stored, so tests can check leakage against a corpus that lives in
another repository without vendoring it or fetching it at test time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def corpus_hashes(lines: list[str]) -> dict[str, list[str]]:
    normalized = [unicodedata.normalize("NFC", line) for line in lines]
    trigrams = {
        " ".join(words[index : index + 3])
        for words in (line.split() for line in normalized)
        for index in range(len(words) - 2)
    }
    return {
        "line_sha256": sorted({_sha256(line) for line in normalized}),
        "word3_sha256": sorted(_sha256(gram) for gram in trigrams),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.path.read_bytes()
    lines = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    fixture = {
        "source": {
            "repository": args.repository,
            "path": args.source_path,
            "commit": args.commit,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "lines": len(lines),
        },
        "normalization": "NFC lines; word 3-grams are whitespace-split words joined by one space; sha256 of UTF-8",
        **corpus_hashes(lines),
    }
    args.output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
