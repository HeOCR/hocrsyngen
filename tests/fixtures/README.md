# Test Fixtures

Created by [Shay Palachy Affek](http://www.shaypalachy.com/).

## `hebrew_edge_text_corpus.txt`

Synthetic project-authored Hebrew edge text corpus for S2a test coverage.

The lines are test inputs only and are not real-source text, identity,
authorship, medical, psychological, governance, or release provenance claims.
They are covered by the repository license and are used to verify deterministic
logical-order text handling for final forms, numerals, punctuation, dates,
identifiers, and Latin fragments.

## `bidi_niqqud_rendering_corpus.txt`

Synthetic project-authored Hebrew bidi and niqqud rendering corpus for S2b test
coverage.

The lines are test inputs only and are not real-source text, identity,
authorship, medical, psychological, governance, or release provenance claims.
They are covered by the repository license and are used to verify deterministic
logical-order rendering inputs for sparse niqqud, fuller niqqud, mixed Hebrew/Latin/numeric fragments,
punctuation, and bidi-sensitive text.

## `hocrgen_bidi_synthetic_corpus.hashes.json`

Hash-only leakage fixture for S13a. It pins `HeOCR/hocrgen`
`docs/evaluation-fixtures/bidi-synthetic-corpus.txt` at commit
`c8fb74eb5d0afedd812a0da69562e4610a0b3394` and records the source file's sha256
and line count plus the sha256 of each NFC line and each word 3-gram. It holds
no source text. `tests/test_mixed_script_text_corpus.py` uses it to show that
the mixed-script corpora share no line or word 3-gram with that evaluation
corpus. Regenerate it with `scripts/external_corpus_hashes.py`.

## Credits

Created by [Shay Palachy Affek ](http://www.shaypalachy.com/) [[GitHub](https://github.com/shaypal5)]
