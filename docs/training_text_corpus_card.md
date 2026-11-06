# Training Text Corpus Card (`hebrew_lines_*_v1`)

Packaged Hebrew text-line corpora for training HeOCR's own recognizer (R3) on
`hocrsyngen` synthetic pages, plus held-out evaluation lines.

- `tests/test_training_text_corpus.py` enforces the checks described here.
- `scripts/text_corpus_stats.py` reproduces the statistics.

## Files

Paths are relative to `src/hocrsyngen/data/synthetic/`. They are packaged in
the wheel via the existing `data/synthetic/texts/*.txt` package-data glob.

| File | Role | Lines | sha256 |
| --- | --- | --- | --- |
| `texts/hebrew_lines_train_v1.txt` | train | 9359 | `a3f2f0db1bf48d8cdd618579af42ca36710cadf81cdc4d5e89d2dc6c192e6611` |
| `texts/hebrew_lines_eval_v1.txt` | held-out eval | 812 | `89e52f8b90cdbb8a276fbdaf96530afff2cc266e13ad6355c215c79e5a58d97f` |
| `texts/hebrew_lines_niqqud_train_v1.txt` | optional niqqud train subset | 228 | `85365e86ce5474e8187dfc97573b58c5e225e1ed3eebf3f5511b126ba6c10ca9` |
| `texts/hebrew_lines_niqqud_eval_v1.txt` | optional niqqud held-out eval | 40 | `974ffa19251bcc1137a3baf908f22d2770d801a38d93456d6109bf6565de5640` |
| `texts/hebrew_lines.txt` | eval-only reference (unchanged; seed-101 benchmark text) | 19 | `ac7e1dc2c21d2506b93c26ce81cab3327baf217d82fb6620c1ddf6f597235fd6` |

Once merged, `_v1` files are frozen. Any later content change ships as new
`_v2` files with a new card section, so engine runs can pin a path and a
hash. The test fails if this table drifts from the packaged files.

## Engine Contract

- **Passing a corpus.** Pass a file to the generator with `--text-corpus PATH`
  (S10a). Resolve the installed path with:

  ```bash
  python -c "from hocrsyngen.assets import synthetic_data_path; print(synthetic_data_path('texts/hebrew_lines_train_v1.txt'))"
  ```

  A packaged file is recorded as `provenance.source_corpus`
  `packaged:synthetic/texts/<name>`.
- **Which file for which pages.**
  - Training pages: render from `hebrew_lines_train_v1.txt`.
  - Held-out pages: render from `hebrew_lines_eval_v1.txt`.
  - Seed-101 comparison: also render `hebrew_lines.txt`.
- **Niqqud is opt-in.** To train with it, concatenate the main and niqqud
  train files into one corpus file. Evaluate it separately with the niqqud
  eval file.
- **Page count.** The generator samples 3–5 lines per page
  (`_select_body_lines`). Seeing each training line about once takes roughly
  2,300 pages.
- **Codec coverage.** Every eval character also occurs in train (tested), so
  a codec built from train covers eval.
- **Line-level ground truth.** Long lines wrap into two rendered rows on
  narrower bodies. The S10a line sidecar annotates the rendered segments, each
  with its own text, so line-level training data follows what is drawn.

## Provenance

**Authorship.** Original text authored by AI agents (Claude Opus 5.5
sessions run in Claude Code) for HeOCR, on 2026-11-02, under the
`r3-train-corpus` task. No text was copied or closely paraphrased from
published sources. The authoring brief forbade quoting or paraphrasing:

- the Bible or liturgy;
- literature, proverbs or lyrics;
- laws, news or ads;
- real organisations' notices.

**Method.** Two rounds of parallel authoring:

1. **Short lines (up to 30 characters).** Eight passes, one per document
   family:
   - administrative letters;
   - handwritten notes and marginalia;
   - notices;
   - forms;
   - receipts and ledgers;
   - community archives and minutes;
   - mixed-direction and everyday topics;
   - niqqud.

   An extra pass of 115 lines was written directly for rare punctuation
   (`( ) ; + ! ?`).
2. **Long lines (31–55 characters).** Seven passes over the same families,
   added after review so the length distribution covers the 36–47-character
   reference lines.

Each pass ran a checker after every batch. The checker enforces:

- character set;
- NFC;
- rendered width;
- identifier rules;
- n-gram overlap with the 19 reference lines.

The drafts were then merged and filtered by the same rules. Exact duplicates
across families were removed (115), and the result was split as described
below.

**Register.** Modern Hebrew document text in the families `hocrsyngen`
renders: printed letters, handwritten-like notes, archive cards, ledgers,
forms and notices.

## License

Project-authored synthetic text, dedicated to the public domain under CC0 1.0
(`CC0-1.0`; see `texts/LICENSE-CC0-1.0.txt` and
[ADR 0008](decisions/0008-cc0-for-project-authored-text-corpora.md)). The package code stays
under the repository license (MIT). The eval-only reference
`texts/hebrew_lines.txt` is not covered by the dedication and stays under the
repository license. Samples generated from the corpus carry the manifest
licence tag `PROJECT-SYNTHETIC`. No third-party text is included, so no
third-party licence applies.

## Intended Use

- Training a Hebrew line recognizer from scratch on `hocrsyngen` pages
  (train files).
- Held-out evaluation on pages rendered from text the model never saw
  (eval files), alongside the 19 reference lines.

It is not intended as a language-modelling corpus. It makes no claim about
the real-world distribution of Hebrew documents.

## Normalisation And Character Set

**File format**

- UTF-8, LF line endings, one line per row, no blank lines.
- Single spaces only, no surrounding whitespace. `load_text_corpus` returns
  the lines unchanged, and wrapped segments rejoin exactly with one space.

**Normalisation**

- Logical order, Unicode NFC.
- The 19-line reference file stays byte-for-byte as packaged. Its one niqqud
  line is not NFC on disk, so overlap checks use its NFC form. The generator
  NFC-normalizes manifest text in any case.

**Geresh and gershayim**

- These use ASCII `'` and `"`, not U+05F3/U+05F4. This matches the reference
  lines and the generator's own titles and ledger headers (`דו"ח`, `מס'`).
- Rejected characters: U+05F3, U+05F4, maqaf U+05BE, en/em dashes and
  typographic quotes. The hyphen-minus `-` is the only dash.

**Allowed characters**

- the 27 Hebrew letters (22 letters plus 5 final forms);
- digits `0-9`;
- ASCII Latin letters;
- space;
- `. , : ; ! ? ' " ( ) - / % +`;
- the shekel sign `₪`.

**Niqqud**

- Niqqud appears only in the `niqqud` files, and every line there carries it.
- Allowed marks: U+05B0–U+05BC, shin/sin dots U+05C1/U+05C2 and qamats qatan
  U+05C7.
- Both packaged fonts cover these marks, and
  `tests/fixtures/bidi_niqqud_rendering_corpus.txt` already exercises them.
- About 60% of the subset is fully pointed and 40% sparsely pointed.

**Final forms**

- Final forms appear only word-finally.
- Non-final כ מ נ צ never end a plain word. The exceptions are before
  geresh/gershayim (`מס'`, `עמ'`) and before a prefixed number (`כ-300`).
- Word-final non-final פ is allowed, as standard in loanwords (`טרמפ`).

## Wrapping And The No-Loss Rule

Every body region that receives corpus lines wraps them with the generator's
`_wrap_hebrew_text`. Titles, footers and ledger number columns are
generator strings, not corpus text. Wrapping splits only at spaces, and two
regions cap their rendered rows.

So "no character lost" means two things:

- no single word is wider than any region;
- a capped region never receives more rows than it draws.

The test calls the generator's own wrap function with the packaged fonts at
each region's worst-case width:

| Region | Font, size | Wrap width | Row cap | Tested rule | Train rows per line |
| --- | --- | --- | --- | --- | --- |
| `printed_letter` body | Alef 42 | 968 px | none | every word fits | 1: 9164, 2: 195 |
| `handwritten_note` body | Gveret Levin 46 | 968 px | none | every word fits | 1: 9068, 2: 291 |
| `archive_card` body | Alef 38 | 498 px (worst-case jitter) | 7 rows for 3 lines | every word fits; each line ≤ 2 rows | 1: 7124, 2: 2235 |
| `ledger` details cell | Alef 30 | 282 px | 10 rows for 5 lines | every word fits | 1: 2826, 2: 4990, 3: 1531, 4: 12 |

Letter, note and archive-card pages therefore never lose corpus text. Long
lines were authored against a 490 px card width, leaving headroom for
FreeType differences between platforms.

**Known ledger truncation (for S10c).** The ledger draws only the first 10
wrapped detail rows. Long lines wrap to 3–4 rows in its 282 px cell, so some
ledger pages drop trailing rows:

- **This train mix:** the estimated ledger page truncation rate is **21.4%**.
  That is the chance that 5 sampled lines wrap to more than 10 rows; see
  `scripts/text_corpus_stats.py`.
- **The 19 seed-101 reference lines:** **99.96%**.
- **Later versions:** `s11b-ledger-fit-v1` narrowed the cell to 206 px, and
  a 200-page ledger batch truncated on 68.0% of pages.
  `s14a-ledger-wrap-v1` widens it to 316 px, and the same batch truncates on
  5.0% (#85).

Only drawn rows enter the ledger's page text and the S10a line annotations.
Line-level training data stays consistent; page-level ledger text is
incomplete. The fix is the generator's ledger row capacity (S10c), not
shorter corpus lines: lines short enough for the ledger would not cover the
benchmark's line lengths.

## Split

- **Two pools.** Short lines and long lines are split separately. The short
  split is unchanged from the first round; long lines add 179 eval lines.
- **Grouping.** Each pool groups lines by a skeleton: digit runs become `0`,
  Latin runs become `a`. Lines that differ only in numbers or codes share a
  group, and a group never straddles the split.
- **Eval selection.** Group order is fixed by sha256, and whole groups are
  taken for eval up to the target size.
- **Moved to train.**
  - Eval lines whose skeleton tokens have a Jaccard similarity of 0.7 or more
    with a train line in the same pool (7 short lines).
  - Eval lines whose skeleton occurs in the other pool's train (none).
  - Eval lines containing a character train never shows (1 line).
- **File order.** Files are ordered by sha256 of the line, which interleaves
  the families deterministically.

Tested guarantees:

- All five files are pairwise disjoint.
- No eval or reference line shares a skeleton with a train line.
- Train shares no word 3-gram with the 19 reference lines.
- Every eval character occurs in train.

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
| Lines | 9359 | 812 | 228 | 40 | 19 |
| Characters | 240730 | 20415 | 5481 | 968 | 783 |
| Word tokens | 45406 | 3860 | 775 | 141 | 137 |
| Word types | 14195 | 2544 | 643 | 128 | 118 |
| Type/token ratio | 0.313 | 0.659 | 0.830 | 0.908 | 0.861 |
| Hapax word types | 8681 | 2000 | 568 | 119 | 101 |
| Character types | 101 | 78 | 60 | 52 | 39 |
| Chars/line min/median/mean/max | 2/23/25.7/55 | 3/23/25.1/54 | 6/25/24.0/43 | 6/25/24.2/38 | 36/41/41.2/47 |
| Words/line min/median/mean/max | 1/4/4.85/12 | 1/4/4.75/12 | 1/3/3.4/6 | 1/3/3.5/6 | 6/7/7.2/9 |
| Lines of 31–55 chars | 2235 | 179 | — | — | 19 |
| Lines in the reference range, 36–47 chars | 1445 | 118 | — | — | 19 |
| Lines with digits | 2435 | 205 | 21 | 5 | 1 |
| Lines with Latin | 382 | 32 | 0 | 0 | 0 |
| Lines with `'` (geresh) | 505 | 46 | 14 | 7 | 0 |
| Lines with `"` (gershayim/quotes) | 497 | 39 | 6 | 1 | 0 |
| Lines with `₪` | 255 | 33 | 0 | 1 | 0 |

Niqqud marks count toward the niqqud files' character lengths.

Line-length histogram, train and eval (characters per line):

| Characters | Train | Eval |
| --- | --- | --- |
| 0–4 | 69 | 5 |
| 5–9 | 289 | 15 |
| 10–14 | 503 | 62 |
| 15–19 | 1461 | 139 |
| 20–24 | 3236 | 277 |
| 25–29 | 1561 | 134 |
| 30–34 | 262 | 25 |
| 35–39 | 474 | 36 |
| 40–44 | 726 | 60 |
| 45–49 | 507 | 44 |
| 50–54 | 251 | 15 |
| 55 | 20 | 0 |

Train Hebrew letter frequencies (final forms listed separately):

| Letter | Count | Letter | Count | Letter | Count |
| --- | --- | --- | --- | --- | --- |
| ו | 19279 | מ | 9608 | ס | 4114 |
| י | 18947 | ש | 8907 | ג | 2678 |
| ה | 18508 | א | 6535 | ן | 2477 |
| ל | 12522 | ח | 6487 | צ | 2437 |
| ת | 11092 | נ | 6368 | ט | 2206 |
| ב | 11034 | ד | 5978 | ז | 1956 |
| ר | 10987 | ע | 5854 | ף | 826 |
| | | ם | 5548 | ך | 626 |
| | | ק | 5408 | ץ | 244 |
| | | פ | 4242 | | |
| | | כ | 4119 | | |

Train character classes:

| Class | Count |
| --- | --- |
| Hebrew letters | 188987 |
| Spaces | 36047 |
| Punctuation and symbols | 7632 |
| Digits | 7071 |
| Latin | 993 |

The 20 most frequent train words, with counts:

| Word | Count | Word | Count |
| --- | --- | --- | --- |
| את | 687 | ביום | 183 |
| על | 432 | יום | 159 |
| של | 416 | נא | 129 |
| לא | 360 | לפני | 125 |
| עד | 274 | מס' | 119 |
| יש | 219 | הוועד | 118 |
| ₪ | 206 | 3 | 113 |
| עם | 198 | אין | 103 |
| כל | 189 | ל"י | 97 |
| `-` | 184 | לפי | 93 |

**Templating checks.**

- Short lines: the most frequent two-word opening occurs 11 times in about
  7,600 lines, and there are 6 near-duplicate pairs (token Jaccard 0.8 or
  more).
- Long lines: the most frequent opening occurs 7 times in about 2,400 lines.

## Overlap

Each cell is the share of the target's n-gram types (tokens in parentheses)
that also occur in the source:

| Source → target | Shared lines | Word 1-gram | Word 2-gram | Word 3-gram | Char 5-gram types |
| --- | --- | --- | --- | --- | --- |
| train + niqqud train → reference 19 | 0 | 0.763 (0.781) | 0.119 (0.119) | 0.000 (0.000) | 0.754 |
| train → eval | 0 | 0.712 (0.805) | 0.195 (0.207) | 0.034 (0.034) | 0.716 |
| niqqud train → niqqud eval | 0 | 0.313 (0.369) | 0.040 (0.040) | 0.000 (0.000) | 0.281 |

Shared single words and character 5-grams are expected and needed: they
reflect a shared Hebrew vocabulary. Word 3-gram overlap with the reference
lines is zero, and this is tested.

## Limitations

- **Single authoring source.** All text comes from AI agents, so the voice,
  topics and phrasing reflect that source and are narrower than real
  documents.
- **Length mix.** Lines are at most 55 characters. Long lines (31–55) are
  about 24% of train, and the median line is 23 characters.
- **Ledger truncation.** Ledger pages can drop trailing wrapped rows (see
  Wrapping And The No-Loss Rule); this is tracked for S10c.
- **Narrow time period.** Dates and currencies (`ל"י`, `₪`) mix eras
  without historical consistency.
- **Unverified niqqud.** The pointing is agent-authored and was spot-checked,
  but not reviewed by a linguist.
- **No distribution claim.** Frequencies describe this corpus only.
- **Synthetic only.** The corpus is not a substitute for real-scan
  evaluation. Downstream measurement remains governed by
  `docs/downstream_utility_measurement_contract.md`.
