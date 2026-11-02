# Training Text Corpus Card (`hebrew_lines_*_v1`)

Packaged Hebrew text-line corpora for training HeOCR's own recognizer (R3) on
`hocrsyngen` synthetic pages, plus held-out evaluation lines. The checks
described here are enforced by `tests/test_training_text_corpus.py`.
`scripts/text_corpus_stats.py` reproduces the statistics.

## Files

Paths are relative to `src/hocrsyngen/data/synthetic/`. They are packaged in
the wheel via the existing `data/synthetic/texts/*.txt` package-data glob.

| File | Role | Lines | sha256 |
| --- | --- | --- | --- |
| `texts/hebrew_lines_train_v1.txt` | train | 7124 | `38cb73a2f2103d00e6fa5e53626ff6bc686da68550a532c2b59fbc621c0e3427` |
| `texts/hebrew_lines_eval_v1.txt` | held-out eval | 633 | `b792d64777379a1462910af121915dea613f8396362cfaae092683237ba54127` |
| `texts/hebrew_lines_niqqud_train_v1.txt` | optional niqqud train subset | 228 | `85365e86ce5474e8187dfc97573b58c5e225e1ed3eebf3f5511b126ba6c10ca9` |
| `texts/hebrew_lines_niqqud_eval_v1.txt` | optional niqqud held-out eval | 40 | `974ffa19251bcc1137a3baf908f22d2770d801a38d93456d6109bf6565de5640` |
| `texts/hebrew_lines.txt` | eval-only reference (unchanged; seed-101 benchmark text) | 19 | `ac7e1dc2c21d2506b93c26ce81cab3327baf217d82fb6620c1ddf6f597235fd6` |

The `_v1` files are frozen. Any content change ships as new `_v2` files
with a new card section, so engine runs can pin a path and a hash. The test
fails if this table's line counts or hashes drift from the packaged files.

## Engine Contract

Pass a file to the generator with `--text-corpus PATH`, the flag added by the
R3 line-annotation work. Resolve the installed path with:

```bash
python -c "from hocrsyngen.assets import synthetic_data_path; print(synthetic_data_path('texts/hebrew_lines_train_v1.txt'))"
```

- Render training pages from `hebrew_lines_train_v1.txt`. Render held-out
  pages from `hebrew_lines_eval_v1.txt`, plus `hebrew_lines.txt` for
  comparability with the seed-101 baseline.
- Niqqud is opt-in. To train with it, concatenate the main and niqqud train
  files into one corpus file; evaluate it separately with the niqqud eval file.
- The generator samples 3–5 lines per page (`_select_body_lines`). Seeing each
  training line about once takes roughly 1,800 pages.
- Every eval character also occurs in train (tested), so a codec built from
  train covers eval.

## Provenance

- **Authorship:** original text authored by AI agents (Claude Opus 5.5
  sessions run in Claude Code) for HeOCR, on 2026-11-02, under the
  `r3-train-corpus` task. No text was copied or closely paraphrased from
  published sources. The authoring brief forbade quoting or paraphrasing the
  Bible, liturgy, literature, proverbs, lyrics, laws, news, ads or real
  organisations' notices.
- **Method:** eight parallel authoring passes, one per document family:
  - administrative letters;
  - handwritten notes and marginalia;
  - notices;
  - forms;
  - receipts and ledgers;
  - community archives and minutes;
  - mixed-direction and everyday topics;
  - niqqud.

  A ninth pass of 115 lines was written directly to strengthen rare
  punctuation (`( ) ; + ! ?`). Each pass ran a checker after every batch.
  The checker enforces character set, NFC, rendered width, identifier rules
  and n-gram overlap with the 19 reference lines.

  The drafts were then merged and filtered by the same rules. Exact
  duplicates across families were removed (115), and the result was split as
  described below.
- **Register:** modern Hebrew document text in the families
  `hocrsyngen` renders: printed letters, handwritten-like notes, archive
  cards, ledgers, forms and notices.

## License

Project-authored synthetic text, covered by the repository license (MIT), like
the existing packaged text and test fixtures. Samples generated from it
carry the manifest licence tag `PROJECT-SYNTHETIC`. No third-party text is
included, so no third-party licence applies.

## Intended Use

- Training a Hebrew line recognizer from scratch on `hocrsyngen` pages
  (train files).
- Held-out evaluation on pages rendered from text the model never saw
  (eval files), alongside the 19 reference lines.

It is not intended as a language-modelling corpus. It makes no claim about the
real-world distribution of Hebrew documents.

## Normalisation And Character Set

- UTF-8, LF line endings, one line per row, no blank lines, single spaces,
  no surrounding whitespace. `load_text_corpus` returns the lines unchanged.
- Logical order, Unicode NFC. The 19-line reference file stays byte-for-byte
  as packaged. Its one niqqud line is not NFC on disk, so overlap checks use
  its NFC form; the generator NFC-normalizes manifest text in any case.
- **Geresh and gershayim use ASCII `'` and `"`**, not U+05F3/U+05F4. This
  matches the reference lines and the generator's own titles and ledger
  headers (`דו"ח`, `מס'`). U+05F3, U+05F4, maqaf U+05BE, en/em dashes and
  typographic quotes are rejected. The hyphen-minus `-` is the only dash.
- Allowed characters:
  - the 27 Hebrew letters (22 letters plus 5 final forms);
  - digits `0-9`;
  - ASCII Latin letters;
  - space;
  - `. , : ; ! ? ' " ( ) - / % +`;
  - the shekel sign `₪`.
- Niqqud appears only in the `niqqud` files. Allowed marks are
  U+05B0–U+05BC, shin/sin dots U+05C1/U+05C2 and qamats qatan U+05C7; every
  line in those files carries niqqud. Both packaged fonts cover these marks,
  and `tests/fixtures/bidi_niqqud_rendering_corpus.txt` already exercises
  them. About 60% of the subset is fully pointed and 40% sparsely pointed.
- Final forms appear only word-finally. Non-final כ מ נ צ never end a plain
  word, except before geresh/gershayim (`מס'`, `עמ'`) or a prefixed number
  (`כ-300`). Word-final non-final פ is allowed because loanwords such as
  `טרמפ` take it.

## Line-Width Budget

Widths are measured, not estimated from character counts. The test measures
every line with Pillow/libraqm (`textbbox`, `direction="rtl"`), the same call
the generator's word wrap uses, with the packaged fonts:

| Region | Font, size | Budget | Rule |
| --- | --- | --- | --- |
| `archive_card` body (narrowest free-text body, worst-case jitter) | Alef 38 | 498 px | whole line fits |
| `printed_letter` body | Alef 42 | 968 px | whole line fits |
| `handwritten_note` body | Gveret Levin 46 | 968 px | whole line fits |
| `ledger` "details" cell | Alef 30 | 282 px | every token fits |

Authoring used a 490 px card budget, leaving headroom for FreeType
differences between platforms. No corpus line wraps in a letter, note or
archive-card body.

The ledger details column is a 310 px table cell, and the generator wraps
body lines into several ledger rows by design. Making it the whole-line
budget would cap lines at about 3 words. So only single tokens are held to
it, which means nothing overflows the cell. The trade-off is that lines top
out at about 30 characters. That is shorter than the 36–47-character
reference lines, which render unwrapped only on letters and notes.

## Split

- Lines are grouped by a skeleton: digit runs become `0`, Latin runs become
  `a`. Lines that differ only in numbers or codes therefore share a group,
  and a group never straddles the split. Group order is fixed by sha256, and
  whole groups are taken for eval until 633 lines.
- Eval lines whose skeleton tokens have a Jaccard similarity of 0.7 or more
  with any train line moved to train (7 lines).
- Files are ordered by sha256 of the line, which interleaves the families
  deterministically.
- Eval family mix:

  | Family | Eval lines |
  | --- | --- |
  | admin letters | 102 |
  | handwritten notes | 94 |
  | archive/minutes | 90 |
  | forms | 86 |
  | mixed/everyday | 85 |
  | receipts/ledgers | 83 |
  | notices | 81 |
  | punctuation | 12 |

Tested guarantees:

- All five files are pairwise disjoint.
- No eval or reference line shares a skeleton with a train line.
- Train shares no word 3-gram with the 19 reference lines.

## Privacy

- No real people's names, ID numbers, phone numbers, emails, URLs or street
  addresses. Lines use roles (`הגזבר`, `הדייר מדירה 4`) and generic places
  (`חדר 12`, `המחסן הצפוני`).
- Tested identifier rules:
  - no digit run of 7 or more digits;
  - no dash- or space-joined digit group totalling 9 or more digits;
  - no `@`, URL or domain;
  - every 5–6-digit run, zero-padded to 9 digits, **fails** the Israeli ID
    check digit, so it cannot be a valid ID number.

## Statistics

From `python scripts/text_corpus_stats.py`:

| Metric | train | eval | niqqud train | niqqud eval | reference 19 |
| --- | --- | --- | --- | --- | --- |
| Lines | 7124 | 633 | 228 | 40 | 19 |
| Characters | 146504 | 12951 | 5481 | 968 | 783 |
| Word tokens | 28160 | 2493 | 775 | 141 | 137 |
| Word types | 10295 | 1784 | 643 | 128 | 118 |
| Type/token ratio | 0.366 | 0.716 | 0.830 | 0.908 | 0.861 |
| Hapax word types | 6468 | 1455 | 568 | 119 | 101 |
| Character types | 99 | 77 | 60 | 52 | 39 |
| Chars/line min/median/mean/max | 2/22/20.6/30 | 3/22/20.5/30 | 6/25/24.0/43 | 6/25/24.2/38 | 36/41/41.2/47 |
| Words/line min/median/mean/max | 1/4/3.95/8 | 1/4/3.94/12 | 1/3/3.4/6 | 1/3/3.5/6 | 6/7/7.2/9 |
| Lines with digits | 1887 | 165 | 21 | 5 | 1 |
| Lines with Latin | 323 | 26 | 0 | 0 | 0 |
| Lines with `'` (geresh) | 402 | 41 | 14 | 7 | 0 |
| Lines with `"` (gershayim/quotes) | 361 | 25 | 6 | 1 | 0 |
| Lines with `₪` | 140 | 20 | 0 | 1 | 0 |

Niqqud marks count toward the niqqud files' character lengths.

Train line-length histogram (characters):

| Characters | Lines |
| --- | --- |
| 0–4 | 69 |
| 5–9 | 289 |
| 10–14 | 503 |
| 15–19 | 1461 |
| 20–24 | 3236 |
| 25–29 | 1561 |
| 30–34 | 5 |

Train Hebrew letter frequencies (final forms listed separately):

| Letter | Count | Letter | Count | Letter | Count |
| --- | --- | --- | --- | --- | --- |
| ו | 11871 | מ | 5948 | ס | 2714 |
| י | 11546 | ש | 5115 | כ | 2490 |
| ה | 10932 | ח | 4055 | ג | 1686 |
| ל | 7391 | נ | 3958 | ן | 1555 |
| ר | 6833 | א | 3823 | צ | 1512 |
| ת | 6757 | ד | 3671 | ט | 1446 |
| ב | 6483 | ע | 3542 | ז | 1230 |
| | | ם | 3343 | ף | 536 |
| | | ק | 3325 | ך | 352 |
| | | פ | 2695 | ץ | 156 |

Train character classes:

| Class | Count |
| --- | --- |
| Hebrew letters | 114965 |
| Spaces | 21036 |
| Digits | 5204 |
| Punctuation and symbols | 4485 |
| Latin | 814 |

The 20 most frequent train words, with counts:

| Word | Count | Word | Count |
| --- | --- | --- | --- |
| את | 337 | ביום | 107 |
| על | 253 | מס' | 101 |
| לא | 243 | 3 | 99 |
| `-` | 184 | עם | 98 |
| של | 172 | ל"י | 90 |
| עד | 163 | כל | 83 |
| ₪ | 136 | נא | 77 |
| יש | 115 | אין | 75 |
| יום | 111 | הוועד | 68 |
| טופס | 63 | הנדון: | 56 |

Templating check: the most frequent two-word line opening (`נא לא`) occurs
11 times in about 7,600 lines. There are 6 near-duplicate pairs (token
Jaccard 0.8 or more) across the whole pool.

## Overlap

Each cell is the share of the target's n-gram types (tokens in parentheses)
that also occur in the source:

| Source → target | Shared lines | Word 1-gram | Word 2-gram | Word 3-gram | Char 5-gram types |
| --- | --- | --- | --- | --- | --- |
| train + niqqud train → reference 19 | 0 | 0.678 (0.708) | 0.076 (0.076) | 0.000 (0.000) | 0.679 |
| train → eval | 0 | 0.697 (0.779) | 0.158 (0.166) | 0.020 (0.020) | 0.652 |
| niqqud train → niqqud eval | 0 | 0.313 (0.369) | 0.040 (0.040) | 0.000 (0.000) | 0.281 |

Shared single words and character 5-grams are expected and needed: they
reflect a shared Hebrew vocabulary. Word 3-gram overlap with the reference
lines is zero and tested.

## Limitations

- **Single authoring source.** All text comes from AI agents, so the voice,
  topics and phrasing reflect that source and are narrower than real
  documents.
- **Short lines.** Lines are at most about 30 characters (see Line-Width
  Budget). Longer realistic lines are absent.
- **Narrow time period.** Dates and currencies (`ל"י`, `₪`) mix eras
  without historical consistency.
- **Unverified niqqud.** The pointing is agent-authored and was spot-checked,
  but not reviewed by a linguist.
- **No distribution claim.** Frequencies describe this corpus only.
- **Synthetic only.** The corpus is not a substitute for real-scan
  evaluation. Downstream measurement remains governed by
  `docs/downstream_utility_measurement_contract.md`.
