# Typographic Text Corpus Card (`hebrew_typographic_lines_*_v1`)

Packaged typeset Hebrew text lines (`S13b`, #87), plus a disjoint held-out
evaluation file. The lines use the punctuation of printed Hebrew at realistic
rates:

- em and en dashes;
- geresh and gershayim;
- typographic quotation marks;
- the ellipsis;
- semicolons.

None of the earlier packaged corpora contains these characters. The S10b
([training_text_corpus_card.md](training_text_corpus_card.md)) and S13a
([mixed_script_text_corpus_card.md](mixed_script_text_corpus_card.md)) corpora
reject them on purpose and use ASCII stand-ins (`'`, `"`, `-`). A recognizer
trained only on those corpora never sees `—`, and writes `-` for it (#87).

- `tests/test_typographic_text_corpus.py` enforces the checks described here.
- `scripts/typographic_text_corpus_stats.py` reproduces the statistics and
  defines the mark classes that the tests count.

## Files

Paths are relative to `src/hocrsyngen/data/synthetic/`. They are packaged in
the wheel via the existing `data/synthetic/texts/*.txt` package-data glob.

| File | Role | Lines | sha256 |
| --- | --- | --- | --- |
| `texts/hebrew_typographic_lines_train_v1.txt` | train | 4822 | `5c385b4178b6f9eb62fdfa9af32f4a1d5a737cf700547ac9f67258d86f8360ce` |
| `texts/hebrew_typographic_lines_eval_v1.txt` | held-out eval | 418 | `3364283592492d8827ae94b8899ce44cecedf1281b4fbeb69f9d76b3e9a09a3c` |

Once merged, `_v1` files are frozen; a content change ships as `_v2`. The test
fails if this table drifts from the packaged files. The S10b and S13a files are
unchanged (byte-identical).

## Engine Contract

- **Passing it.** Use `--text-corpus PATH` (S10a), resolving the path as for
  S10b:

  ```bash
  python -c "from hocrsyngen.assets import synthetic_data_path; print(synthetic_data_path('texts/hebrew_typographic_lines_train_v1.txt'))"
  ```

  It is recorded as `provenance.source_corpus`
  `packaged:synthetic/texts/hebrew_typographic_lines_train_v1.txt`.
- **Mixing with S10b and S13a.** A run that wants all registers renders pages
  from each file separately, or concatenates the train files into one corpus
  file. In a concatenation the ASCII stand-ins (S10b, S13a) and the typographic
  forms (S13b) both occur, as they do in real documents. The forms are visually
  distinct in both fonts (see Fonts), so a model can learn both.
- **Held-out pages.** Render held-out typographic pages from
  `hebrew_typographic_lines_eval_v1.txt`. It shares no line or skeleton with
  train, and 0.8% of its word 3-gram types.
- **Codec coverage.** Every eval character occurs in train (tested), and every
  new character occurs in both files (tested). New relative to S10b and S13a:
  - `—` U+2014 and `–` U+2013;
  - `׳` U+05F3 and `״` U+05F4;
  - `“` U+201C, `”` U+201D, `„` U+201E, `‘` U+2018 and `’` U+2019;
  - `…` U+2026.
- **Page count.** 3–5 lines per page, so seeing each train line about once
  takes roughly 1,200 pages.

## Coverage Spec

Written before authoring; the tests hold the corpus to it.

**Placement rules (tested)**

- **Gershayim `״`** stands between two Hebrew letters: before the last letter
  of an acronym or abbreviation (`צה״ל`, `ד״ר`, `מע״מ`, `ש״ח`, `ע״פ`), or in a
  Hebrew numeral (`תשפ״ז`, `כ״ג בתשרי`).
- **Geresh `׳`** follows a Hebrew letter. Uses:
  - an abbreviation (`מס׳`, `עמ׳`, `גב׳`, `וכו׳`);
  - a letter numeral (`סעיף ג׳`, `יום ה׳`);
  - a foreign sound inside a word, after `ג`, `ז` or `צ` only (`ג׳ינס`, `צ׳ק`).
- **Em dash `—`** is spaced on both sides (` — `), or opens a dialogue line
  (`— ומה התוכנית לחורף?`, 143 train lines).
- **En dash `–`** is unspaced in ranges (`1948–1952`, `9:00–13:00`,
  `עמ׳ 12–14`), or spaced (` – `) as a sentence dash, which Israeli typesetting
  also uses.
- **Quotation marks** pair in logical order:
  - `“…”` is the usual style;
  - `„…”` is the less common traditional style;
  - `‘…’` is rare, for a term quoted inside a quotation.

  An opener comes first in the string. Bidi rendering draws it on the right.
- **Ellipsis `…`** is one character, attached to the word before it.
- **Final forms** occur only word-finally. Before `׳` or `״` the regular form
  is used (`עמ׳`, `מנכ״ל`).

**Realistic rates (tested in both files)**

Each band is the share of lines carrying the class.

| Class | Band | Train | Eval |
| --- | --- | --- | --- |
| Gershayim in a word | 22–45% | 30.7% | 28.0% |
| Geresh after a letter | 12–30% | 17.4% | 16.7% |
| Em dash | 10–25% | 16.2% | 15.1% |
| En dash (ranges and spaced) | 6–16% | 10.2% | 9.1% |
| `“…”` | 6–18% | 9.4% | 9.1% |
| Ellipsis | 2–10% | 4.2% | 3.6% |
| Semicolon | 2–10% | 4.8% | 5.0% |
| No typographic mark | 20–45% | 28.4% | 30.6% |

A typeset line carries one or two kinds of mark, not one of each. At most 3% of
lines may carry four or more kinds (train: 1 line; eval: 0).

**Line length**

The same target as S13a, matching S10b train:

- at most 55 characters;
- 18–35% of lines in the 31–55 band;
- at least 10% in the 36–47 benchmark range;
- median 18–30 characters.

Observed in train: 30% in 31–55, 14% in 36–47, median 26, max 54.

**Script mix**

Hebrew with digits (21.8% of train lines). Latin is incidental, in 5 train
lines (`A4`, `S–XL`); mixed-script text is S13a's job.

## Fonts

Both packaged fonts were checked by cmap (fontTools) and by rendering every new
character with Pillow and raqm, against the font's `.notdef` box:

- **Alef** (printed) has a real glyph for every new character.
- **Gveret Levin** (handwritten-like) has the same.
- No character had to be restricted. `tests/test_typographic_text_corpus.py`
  repeats the render check with Pillow only.

**Look-alikes.** Each typographic form was rendered next to its ASCII stand-in
at 48 px and compared pixel by pixel. Every pair differs. The pairs and the
differing-pixel counts (Alef / Gveret Levin):

| Pair | Alef | Gveret Levin |
| --- | --- | --- |
| `״` / `"` | 141 | 105 |
| `׳` / `'` | 70 | 29 |
| `–` / `-` | 50 | 56 |
| `—` / `–` | 24 | 80 |
| `“` / `”` | 81 | 53 |
| `…` / `...` | 40 | 89 |

The smallest differences are thin:
- `—` against `–` in Alef, which differ mainly in length;
- `׳` against `'` and `‘` against `’` in Gveret Levin.

Expect a recognizer to confuse them more often than other characters,
especially on degraded scans.

**Visual check.** Smoke pages were inspected by eye on an archive card and a
printed letter (see Wrapping). Every mark drew as a real glyph in correct
right-to-left order: `“קורא תמים”?`, `„המחסן … חדשה”.`, `ר״ל:`, `ב׳`, `צ׳ופר`
and `מסורת — 7`.

## Provenance

**Authorship.** Original text authored by AI agents (Claude Opus 5.5 sessions
run in Claude Code) for HeOCR on 2026-11-04, under the S13b task. Nothing was
scraped. No text was copied or closely paraphrased from real documents, books,
articles, laws, websites or songs. The brief forbade:

- real people, companies, brands and products;
- addresses, phone numbers and ID numbers;
- emails and URLs.

People appear as role titles (`היו״ר`, `המזכירה`), first names, or an initial
with a common surname (`ר׳ כהן`, `ד״ר ש׳`). Organisations are invented local
bodies: committees, clubs, a library friends' group, a community centre.

Well-known public acronyms and city names (`צה״ל`, `חו״ל`, `ביה״ס`, `תנ״ך`,
`ת״א`, `ב״ש`) appear only as ordinary vocabulary in neutral contexts
(`שירות בצה״ל`, `טיסה לחו״ל`). No line makes a factual or news claim about a
real institution.

**Method.**

1. **Authoring passes.** Eight parallel passes, one per document register,
   each written to a shared brief with the placement rules and rate bands
   above:
   - official letters and correspondence;
   - archive and catalogue descriptions;
   - public notices and community newsletters;
   - meeting minutes;
   - personal notes, diaries and dialogue;
   - ledger, accounts and inventory entries;
   - essays and reference prose;
   - regulations, instructions and forms.
2. **Checker.** Every pass ran a checker until it accepted every line. The
   checker enforces:
   - the character set and NFC;
   - the placement rules;
   - token width in every wrapping region, and at most 2 archive-card rows;
   - the S10b identifier rules and a brand denylist;
   - no line shared with any packaged corpus;
   - no word 3-gram shared with any evaluation text.

   Rejected lines were rewritten, not dropped.
3. **Merge.** Of 5,279 accepted lines, 6 exact duplicates (across passes) and
   33 near-duplicates were removed. Near-duplicates are lines with token
   Jaccard ≥ 0.8 on skeletons that share the same first word.

**Register.** Modern typeset Hebrew suited to the governed templates: letters,
notes, card fields, ledger details, minutes, notices and reference prose.

## License

Project-authored synthetic text under the repository license (MIT). Samples
generated from it carry `PROJECT-SYNTHETIC`. No third-party text is included.

## Normalisation And Character Set

- **Format and order.** UTF-8, LF, one line per row, single spaces, NFC,
  logical order.
- **No bidi controls.** None of U+061C, U+200E/F, U+202A–U+202E or
  U+2066–U+2069 occur (tested).
- **Logical order is tested three ways:**
  - final forms occur only word-finally;
  - parentheses and quotation marks are balanced;
  - every opener comes before its closer.
- **Allowed characters.** The S10b set without the ASCII stand-ins `'` and
  `"`, plus the ten new marks:
  - Hebrew letters (no niqqud), ASCII Latin and digits;
  - space and `. , : ; ! ? ( ) - / % +`, and `₪`;
  - `— – ׳ ״ “ ” „ ‘ ’ …`.

  In this register `׳ ״ “ ”` replace ASCII `'` and `"` everywhere. Three
  ASCII dots never stand in for `…`. The ASCII hyphen stays for prefixed
  numbers (`ב-2027`). Maqaf (U+05BE), `@` and `&` are not used.
- **Hebrew letter in every line.**

## Wrapping And The No-Loss Rule

The S10b rule applies, with the same regions and widths, imported from
`tests/test_training_text_corpus.py`:

- every token fits every region;
- an archive-card line wraps to at most 2 rows.

Letter, note and archive-card pages lose no corpus text. Ledger pages truncate
wrapped rows as for S10b and S13a; only drawn rows enter page text and the
line sidecar.

**Smoke batches.** Seed 1315 rendered 14 train pages and seed 1316 rendered 7
eval pages, across all seven governed templates.

- `validate` passes on both batches.
- `quality-check` reports truncation only on ledger pages.
- No S11b/S12b overflow guard fired.
- Every new mark except `‘ ’` reached the line-annotation gold of both
  batches. `‘ ’` is rare by design.
- A wrapped row can split a quotation across rows (`„המחסן` / `סגור עד הודעה
  חדשה”.`), exactly as S13a lines split parentheses. Line-level gold then has
  one opener or closer per row.

## Split

The split follows the S10b and S13a method:

1. **Grouping.** Lines are grouped by skeleton: digit runs become `0`, Latin
   runs become `a`, and the new marks are dropped. Number variants, code
   variants and punctuation-only variants therefore never straddle the split.
2. **Eval selection.** Whole groups are taken in sha256 order, separately for
   short (≤ 30) and long lines in their train proportions, up to 420 lines.
   Further groups are then added until each mark class has about 70% of its
   proportional eval share.
3. **Moved back to train.** Eval groups (5 lines) were moved back because a
   line in the group:
   - shared two or more word 3-grams with train;
   - had a skeleton-token Jaccard of 0.7 or more with a train line;
   - or carried a character train lacks.
4. **File order.** Files are ordered by the sha256 of each line.

## Leakage

Each cell gives the number of shared lines and the share of the target's word
3-gram types that also occur in the source:

| Source → target | Shared lines | Word 3-gram types shared |
| --- | --- | --- |
| typographic train → typographic eval | 0 | 11 of 1,305 (0.008; tested ≤ 0.05) |
| typographic train or eval → S10b eval, niqqud eval, `hebrew_lines.txt` | 0 | 0 (tested) |
| typographic train or eval → S13a mixed eval | 0 | 0 of 1,184 (tested) |
| typographic train or eval → `hocrgen` `bidi-synthetic-corpus.txt` | 0 | 0 of 155 (tested) |

- **Shared lines.** Both files share no line with any packaged corpus.
- **The `hocrgen` corpus.** It is checked through S13a's hash-only fixture,
  `tests/fixtures/hocrgen_bidi_synthetic_corpus.hashes.json`, pinned at
  `c8fb74e`.

## Privacy

- **No real identities:** no real people, companies, addresses, phone numbers
  or ID numbers.
- **No emails or URLs** (tested).
- **S10b identifier rules:**
  - no digit run of 7 or more digits;
  - no joined digit group totalling 9 or more digits;
  - no 5–6-digit run passes the Israeli ID check digit.
- **Brand guard.** S13a's denylist of well-known vendor and product names is
  tested. It is a guard, not a proof.

## Statistics

From `python scripts/typographic_text_corpus_stats.py`:

| Metric | train | eval |
| --- | --- | --- |
| Lines | 4822 | 418 |
| Characters | 127051 | 11222 |
| Character types | 68 | 60 |
| Chars/line min/median/mean/max | 4/26/26.3/54 | 8/26/26.8/49 |
| Lines of 31–55 / 36–47 chars | 1445 / 652 | 127 / 56 |
| Lines by number of mark kinds (0/1/2/3/4) | 1369 / 2376 / 961 / 115 / 1 | 129 / 202 / 84 / 3 / 0 |

Character counts for the new marks (train / eval):

| `״` | `׳` | `—` | `–` | `“` | `”` | `„` | `‘` | `’` | `…` | `;` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1698 / 130 | 1000 / 80 | 824 / 65 | 512 / 40 | 472 / 39 | 608 / 52 | 136 / 13 | 30 / 5 | 30 / 5 | 202 / 15 | 250 / 21 |

`”` closes both `“` and `„`.

Line-length histogram (characters per line):

| Characters | 0–4 | 5–9 | 10–14 | 15–19 | 20–24 | 25–29 | 30–34 | 35–39 | 40–44 | 45–49 | 50–55 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Train | 3 | 45 | 292 | 708 | 1025 | 1121 | 815 | 478 | 226 | 91 | 18 |
| Eval | 0 | 1 | 21 | 57 | 92 | 99 | 76 | 41 | 22 | 9 | 0 |

Coverage per mark class (lines containing the class, train / eval; the test
floors are about 75% of train and 60% of eval):

| Class | Lines | Class | Lines |
| --- | --- | --- | --- |
| Gershayim in a word | 1480 / 117 | En dash, range | 308 / 19 |
| Geresh after a letter | 841 / 70 | En dash, spaced | 183 / 19 |
| Geresh letter numeral `ג׳` | 547 / 49 | `“…”` | 453 / 38 |
| Geresh foreign sound `צ׳ק` | 86 / 9 | `„…”` | 135 / 13 |
| Em dash | 782 / 63 | `‘…’` | 30 / 4 |
| En dash, any | 490 / 38 | Ellipsis | 202 / 15 |
| Digits | 1053 / 79 | Semicolon | 233 / 21 |
| | | No typographic mark | 1368 / 128 |

**Templating checks.**

- No two-word opening occurs more than 9 times in train (tested ≤ 25). The
  most common are `— ומה` (dialogue) and `החלטה מס׳`.
- All 4,822 train lines have a unique skeleton (tested ≥ 97%).

## Limitations

- **Single authoring source.** All text comes from AI agents, so the voice and
  topics are narrower than real typeset documents.
- **Thin rare forms.** `‘…’` occurs in 30 train lines and the foreign-sound
  geresh in 86. A model sees them far less often than the common marks.
- **Thin look-alike margins.** Some typographic forms differ from their ASCII
  stand-ins by few pixels (see Fonts), so ASCII/typographic confusion will
  remain on degraded pages.
- **One quotation convention per style.** Quotes use `“…”` and `„…”` with `”`
  closing. Other conventions are not covered, for example gershayim used as
  quotation marks, or `”…“` as some Israeli typesetting uses.
- **No distribution claim.** Rates are chosen to be realistic and are tested;
  they describe this corpus only.
- **Synthetic only.** The corpus is not a substitute for real-scan evaluation.
  Downstream measurement remains governed by
  `docs/downstream_utility_measurement_contract.md`.
