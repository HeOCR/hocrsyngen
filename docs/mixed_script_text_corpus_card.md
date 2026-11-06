# Mixed-Script Text Corpus Card (`hebrew_mixed_lines_*_v1`)

Packaged mixed Hebrew/Latin/digit text lines (`S13a`) for training HeOCR's
recognizer on the mixed-direction lines found in tender-style documents, plus
a disjoint held-out evaluation file. It complements the S10b corpus
([training_text_corpus_card.md](training_text_corpus_card.md)), which has Latin in
only 382 of 9,359 train lines.

- `tests/test_mixed_script_text_corpus.py` enforces the checks described here.
- `scripts/mixed_text_corpus_stats.py` reproduces the statistics and defines
  the token classes that the tests count.

## Files

Paths are relative to `src/hocrsyngen/data/synthetic/`. They are packaged in
the wheel via the existing `data/synthetic/texts/*.txt` package-data glob.

| File | Role | Lines | sha256 |
| --- | --- | --- | --- |
| `texts/hebrew_mixed_lines_train_v1.txt` | train | 5810 | `203df9e896efad7825b69442e39dba5b489df0db053bc61cd762cae032e9a37d` |
| `texts/hebrew_mixed_lines_eval_v1.txt` | held-out eval | 401 | `45a81fff1105ba347c2e80ebfe5cafa0c4e3763975279709c0b9af7a0eedaa88` |

Once merged, `_v1` files are frozen; a content change ships as `_v2`. The test
fails if this table drifts from the packaged files.

## Engine Contract

- **Passing it.** Use `--text-corpus PATH` (S10a), resolving the path as for
  S10b:

  ```bash
  python -c "from hocrsyngen.assets import synthetic_data_path; print(synthetic_data_path('texts/hebrew_mixed_lines_train_v1.txt'))"
  ```

  It is recorded as `provenance.source_corpus`
  `packaged:synthetic/texts/hebrew_mixed_lines_train_v1.txt`.
- **Mixing with S10b.** A run that wants both registers renders pages from
  each file separately, or concatenates the two train files into one corpus
  file. Concatenated, Latin lines are 2,747 of 15,169 (18.1%).
- **Held-out pages.** Render held-out mixed-script pages from
  `hebrew_mixed_lines_eval_v1.txt`. It shares no line or skeleton with
  train, and 2.9% of its word 3-gram types. The `hocrgen` mixed-script
  evaluation recipe (`HeOCR/hocrgen` PR #97) stays a separate, untouched
  benchmark.
- **Codec coverage.** Every eval character occurs in train (tested). The only
  characters new relative to S10b are `@` and `&`.
- **Page count.** 3–5 lines per page, so seeing each train line about once
  takes roughly 1,450 pages.

## Coverage Spec

Written before authoring; the tests hold the corpus to it.

**Script mix**

- 30–45% of lines contain Latin letters (tested; observed 40.7% train, 40.1%
  eval).
- About 45% contain digits or symbols but no Latin, and about 15% are plain
  Hebrew in the same domain.

**Token classes**

Every class below is required, with a minimum line count in both files (see
`MIN_CLASS_LINES`; floors are about 75% of the observed train count):

- Latin words, acronyms, and runs of 2+ and 3+ Latin words.
- Latin at the start, middle and end of a line.
- Alphanumeric codes.
- Dates in several formats: `12/03/2027`, `12.03.27`, ISO `2027-03-12`,
  `03/2027`, Hebrew month names, Latin month names, quarters and halves
  (`Q3 2027`, `H1`), and times of day.
- Numbers with units (`512 GB`, `3.2 GHz`, `40 מ"ר`, `15 ק"ג`), percentages,
  and grouped numbers (`12,500`).
- Currency: `₪`, `NIS`, `ש"ח`, `USD`/`EUR`.
- Emails and URLs in reserved domains.
- Parenthesised English terms and parenthesised Hebrew asides.
- Version strings (`v2.4.1`, `גרסה 3.1.0`, `Rev. B`) and section references.

**Bidi-relevant punctuation**

Parentheses, slashes, hyphens (including Hebrew prefixes `ב-2027`, `כ-300`),
colons, ASCII double quotes, and geresh/gershayim as ASCII `'` `"` (S10b rule)
all occur in hundreds of lines; see Statistics.

**Line length**

The target is to match S10b train:

- at most 55 characters;
- 18–35% of lines in the 31–55 band (S10b: 24%);
- at least 10% in the 36–47 benchmark range;
- median 18–30 characters.

Observed in train: 31% in 31–55, 14% in 36–47, median 27, max 55.

## Fonts

Both packaged fonts were checked by cmap and by rendering every glyph:

- **Alef** (printed) covers printable ASCII U+0021–U+007E and `₪`, with real
  ink for every glyph.
- **Gveret Levin** (handwritten-like) covers the same.

No character had to be restricted for glyph coverage. Two limitations apply:

- **Width, not glyphs, is the binding constraint.** The ledger details cell is
  206 px at Alef 30, and the generator raises on a wider token (S11b).
  - That rules out `example.com` emails: `a@example.com` is 218 px.
  - Emails and URLs therefore use short invented labels under the reserved
    `.test` TLD (`q@kz.test`, `www.mkz.test`). Each token is about 12
    characters at most, and `https://` fits only with a one-letter label.
  - Real tender emails and URLs are longer. Long addresses are out of scope
    until a ledger cell widens or a corpus can be scoped to templates.
- **Glyph look-alikes.** Alef uses old-style figures, so `0`/`o` and `1`/`l`
  look nearly identical. Codes in the corpus mix letters and digits, and a
  recognizer will confuse these pairs on Alef pages.
  - In Gveret Levin, `[]`/`{}` and `|`/`/` look alike. None of these brackets
    or pipes is in the character set.

## Provenance

**Authorship.** Original text authored by AI agents (Claude Opus 5.5 sessions
run in Claude Code) for HeOCR on 2026-11-03, under the S13a task. No text was
copied or closely paraphrased from real tenders, laws, regulations,
catalogues, websites or any client material. The brief forbade:

- real people, companies, government bodies, products and brands;
- addresses, phone or ID numbers;
- real emails and URLs.

Product and model names are invented (`Norvexa 20`, `Lumivo X2`). Generic
technical vocabulary and standards (`PDF`, `USB-C`, `Wi-Fi`, `UPS`,
`ISO 9001`, `IP65`) are used as vocabulary.

**Method.**

1. **Main passes.** Eight parallel authoring passes, one per document family:
   - tender notices and conditions;
   - IT specifications;
   - pricing and payment;
   - contact and online submission;
   - construction and engineering;
   - contract clauses;
   - minutes and clarification Q&A;
   - logistics and catalogues.
2. **Top-up passes.** Two passes centred on the classes the first round
   under-covered:
   - dates and schedules;
   - currency, versions, URLs and codes.
3. **Checker.** Every batch went through a checker that enforces:
   - the character set and NFC;
   - token width in the ledger cell, and at most 2 archive-card rows;
   - the reserved-domain and identifier rules;
   - a brand denylist;
   - no line or word 3-gram shared with any evaluation text.

   Rejected lines were rewritten, not dropped.
4. **Merge.** Of 6,336 accepted lines, 52 exact duplicates and 73
   near-duplicates were removed (token Jaccard ≥ 0.8 on skeletons with the
   same first word).

**Register.** Modern Hebrew procurement and project text: headings,
table-cell fragments, form labels with values, clauses, notes and Q&A.

## License

Project-authored synthetic text, dedicated to the public domain under CC0 1.0
(`CC0-1.0`; see `texts/LICENSE-CC0-1.0.txt` and
[ADR 0008](decisions/0008-cc0-for-project-authored-text-corpora.md)). The package code stays
under the repository license (MIT). Samples generated from it carry
`PROJECT-SYNTHETIC`. No third-party text is included.

## Normalisation And Character Set

- **Format and order.** UTF-8, LF, one line per row, single spaces, NFC,
  logical order.
- **No bidi controls.** None of U+061C, U+200E/F, U+202A–U+202E or
  U+2066–U+2069 occur (tested).
- **Logical order is tested two ways.**
  - Final forms occur only word-finally. Reversed Hebrew would put them
    word-initially.
  - Parentheses are balanced and opened before they close.
- **Allowed characters.** The S10b set plus `@` and `&`:
  - Hebrew letters (no niqqud), ASCII Latin and digits;
  - space and `. , : ; ! ? ' " ( ) - / % + @ &`;
  - `₪`.

  The S10b rejected look-alikes (U+05F3, U+05F4, maqaf, dashes, typographic
  quotes) stay rejected.
- **Hebrew letter in every line.** Every line contains at least one Hebrew
  letter, so no line is Latin-only.

## Wrapping And The No-Loss Rule

The S10b rule is applied with the same regions and widths, imported from
`tests/test_training_text_corpus.py`:

- every token fits every region;
- an archive-card line wraps to at most 2 rows.

| Region | Wrap width | Train rows per line |
| --- | --- | --- |
| `printed_letter` body (Alef 42) | 968 px | 1: 5778, 2: 32 |
| `handwritten_note` body (Gveret Levin 46) | 968 px | 1: 5752, 2: 58 |
| `archive_card` body (Alef 38) | 498 px | 1: 3434, 2: 2376 |
| `ledger` details cell (Alef 30) | 206 px | 1: 343, 2: 2809, 3: 2176, 4: 459, 5: 23 |

Letter, note and archive-card pages lose no corpus text.

**Ledger truncation.** The ledger draws 10 wrapped detail rows for 5 lines.
Since S11b narrowed the cell to 206 px, most mixed lines need 2–3 rows.

- The estimated ledger page truncation rate is **88%** for this train file,
  by Monte Carlo over 5-line samples.
- The same estimate gives **69%** for S10b train. The S10b card's 21.4%
  predates S11b.

Only drawn rows enter page text and the line sidecar, so line-level training
data stays consistent. The fix belongs in ledger row capacity, not shorter
lines.

`s14a-ledger-wrap-v1` widens the details cell to 316 px (#85). On a 200-page
ledger batch from this train file, pages with truncation fall from 89.0% to
4.5%.

**Smoke batches.** Seed 1313 rendered 28 train pages and seed 1314 rendered
14 eval pages, across all seven governed templates.

- `validate` passes on both batches.
- `quality-check` reports truncation only on ledger pages (3 of 4 and 2 of 2).
- No S11b/S12b overflow guard fired.
- Visual inspection confirmed correct bidi order. It covered:
  - `סעיף 3.1(ד)`, `64%` and `v10.2.1`;
  - Latin at line start and end;
  - parentheses split across wrapped rows.
- Pages from the existing packaged corpora are byte-identical to `origin/main`
  (`ce9d993`). The check generated 14 pages each from `hebrew_lines.txt`,
  S10b train and S10b eval.

## Split

The split follows the S10b method:

1. **Grouping.** Lines are grouped by skeleton (digit runs to `0`, Latin runs
   to `a`), so number and code variants never straddle the split.
2. **Eval selection.** Whole groups are taken in sha256 order, separately for
   short (≤ 30) and long lines. Further groups are then added until each token
   class has about 70% of its proportional eval share.
3. **Moved back to train.** Eval lines are moved back when they:
   - have a skeleton-token Jaccard of 0.7 or more with a train line;
   - carry a character train lacks;
   - share two or more word 3-grams with train.
4. **File order.** Files are ordered by the sha256 of each line.

## Leakage

Each cell is the share of the target's word 3-gram types that also occur in
the source:

| Source → target | Shared lines | Word 3-gram types shared |
| --- | --- | --- |
| mixed train → mixed eval | 0 | 34 of 1,184 (0.029; tested ≤ 0.05) |
| mixed train → `hebrew_lines_eval_v1.txt` (S10b eval) | 0 | 0 of 2,236 (tested 0) |
| mixed train → `hebrew_lines.txt` (19 reference lines) | 0 | 0 of 99 (tested 0) |
| mixed train → `hocrgen` `bidi-synthetic-corpus.txt` | 0 | 0 of 155 (tested 0) |
| mixed eval → the three files above | 0 | 0 (tested) |

- **Shared lines.** Both files share no line with any packaged corpus, S10b
  train included.
- **The `hocrgen` corpus is not vendored.**
  - `tests/fixtures/hocrgen_bidi_synthetic_corpus.hashes.json` pins it at
    `HeOCR/hocrgen@c8fb74eb5d0afedd812a0da69562e4610a0b3394` (file sha256
    `b3256734…`, 100 lines).
  - The fixture stores only the sha256 of each NFC line and each word
    3-gram.
  - `scripts/external_corpus_hashes.py` regenerates it.
- **Phrases avoided.** Authoring also avoided that corpus's tail phrases and
  its `A-17`/`B-24` codes.

## Privacy

- **No real identities.** No real people, companies, government bodies,
  addresses, phone numbers or ID numbers. Roles stand in (`ועדת המכרזים`,
  `Project Manager`).
- **Reserved domains only.**
  - Emails match `local@label.test`, and every domain-like token is under
    `.test` or `example.com/org/net`.
  - Any `http`/`www` occurs only with such a domain.
- **S10b identifier rules.**
  - no digit run of 7 or more digits;
  - no joined digit group totalling 9 or more digits;
  - no 5–6-digit run passes the Israeli ID check digit.
- **Brand guard.** A denylist of well-known vendor and product names is
  tested. It is a guard, not a proof.

## Statistics

From `python scripts/mixed_text_corpus_stats.py`:

| Metric | train | eval |
| --- | --- | --- |
| Lines | 5810 | 401 |
| Characters | 157199 | 10710 |
| Word tokens / types | 29210 / 9828 | 1987 / 1405 |
| Character types | 106 | 103 |
| Chars/line min/median/mean/max | 4/27/27.1/55 | 8/26/26.7/53 |
| Lines of 31–55 / 36–47 chars | 1801 / 814 | 124 / 54 |
| Lines with Latin | 2365 (40.7%) | 161 (40.1%) |
| Latin characters | 17229 (S10b train: 993) | 1214 |
| Hebrew letters / digits / punctuation and symbols / spaces | 94936 / 13114 / 8520 / 23400 | 6431 / 910 / 569 / 1586 |

Line-length histogram (characters per line):

| Characters | 0–4 | 5–9 | 10–14 | 15–19 | 20–24 | 25–29 | 30–34 | 35–39 | 40–44 | 45–49 | 50–55 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Train | 4 | 96 | 202 | 694 | 1248 | 1466 | 1023 | 577 | 286 | 131 | 38 |
| Eval | 0 | 12 | 19 | 46 | 103 | 111 | 80 | 48 | 18 | 6 | 3 |

Coverage per token class (lines containing the class, train / eval):

| Class | Lines | Class | Lines |
| --- | --- | --- | --- |
| Latin word (3+ letters) | 1405 / 102 | Currency `₪` | 329 / 25 |
| Acronym | 739 / 50 | `NIS` | 48 / 4 |
| Latin run of 2+ words | 742 / 54 | `ש"ח` | 86 / 7 |
| Latin run of 3+ words | 136 / 11 | `USD` / `EUR` | 57 / 4 |
| Latin at line start | 716 / 47 | Email (`.test`) | 120 / 9 |
| Latin in line middle | 773 / 55 | URL or domain (`.test`) | 82 / 5 |
| Latin at line end | 760 / 58 | Parenthesised Latin | 318 / 28 |
| Alphanumeric code | 471 / 26 | Parenthesised Hebrew | 147 / 7 |
| Date `dd/mm/yyyy` or `dd/mm/yy` | 125 / 6 | Version string | 181 / 8 |
| Date `dd.mm.yyyy` or `dd.mm.yy` | 109 / 8 | Section reference | 156 / 11 |
| ISO date | 55 / 4 | Grouped number `12,500` | 361 / 23 |
| Month/year `03/2027` | 74 / 8 | Hebrew prefix + digit/Latin `ב-2027` | 527 / 49 |
| Hebrew month name | 72 / 8 | Slash | 389 / 30 |
| Latin month name | 69 / 4 | Colon | 1623 / 103 |
| Quarter or half `Q3`, `H1` | 66 / 3 | ASCII `"` | 492 / 23 |
| Time of day | 197 / 12 | Gershayim in a word `מע"מ` | 451 / 22 |
| Number with unit | 413 / 20 | Geresh after a letter `מס'` | 338 / 21 |
| Percentage | 317 / 25 | Digits, no Latin | 2470 / 170 |
| | | Plain Hebrew (no digits, no Latin) | 975 / 70 |

**Templating checks.**

- No two-word opening occurs more than 10 times in train (tested ≤ 25).
- 5,765 of 5,810 train lines have a unique skeleton (tested ≥ 97%).

## Limitations

- **Single authoring source.** All text comes from AI agents, so the voice and
  topics are narrower than real procurement documents.
- **Reused names.** Some invented names and example codes recur across
  families, about 15 uses each for the most common (`Norvexa`, `Talvi-X`,
  `2027/A/031`).
- **Short addresses only.** Emails and URLs are short by construction (see
  Fonts), and none is long like real ones.
- **Length tail.** Latin-heavy lines wrap sooner on the archive card, so the
  45–55-character tail (169 lines) is thinner than S10b's (778).
- **Ledger truncation.** Ledger page-level text truncates often (see Wrapping
  And The No-Loss Rule).
- **No distribution claim.** Frequencies describe this corpus only.
- **Synthetic only.** The corpus is not a substitute for real-scan
  evaluation. Downstream measurement remains governed by
  `docs/downstream_utility_measurement_contract.md`.
