# Changelog

Generator-output changes for `hocrsyngen`, keyed by `GENERATOR_VERSION` (the
`generator_version` recorded on every manifest sample). Roadmap notations refer
to [docs/roadmap.md](docs/roadmap.md).

## S11c: printed book page templates (same generator version)

- Eight new templates: `book_page`, `book_page_two_column`, `commentary_page` and `book_title_page`, each also as a
  `_thumbnail_scan` variant (960 px round trip). Two new degradation presets are added (`book_scan_soft`,
  `book_scan_thumbnail`), and three OFL fonts (Frank Ruhl Libre, David Libre, Noto Rashi Hebrew). See
  [book_page_templates.md](docs/book_page_templates.md).
- They are supported by `generate --template-id` and `validate`, but are not governed templates, so `templates`,
  `contracts` and the hocrgen contract are unchanged.
- The governed templates' pages and manifests are byte-identical, so `GENERATOR_VERSION` stays
  `s14a-ledger-wrap-v1`.

## s14a-ledger-wrap-v1 (S14a)

- `ledger` pages truncate wrapped detail rows far less often (#85). The row
  number, date and amount columns hold short fixed-format values, so their
  spare width goes to the details column: column widths from the left are
  130, 140, 110 and 360 px (were 150, 170, 180 and 250 px). The details cell
  fits 316 px of text (was 206 px). The balance column is 10 px wider (144 px,
  ±12 px of table jitter) and still fits `4,980` at maximum drift.
- Ledger pages with `truncated_segments > 0`, on 200-page ledger-only batches
  at seed 14101:

  | Text corpus | `s10c-gold-complete-v1` | `s11b-ledger-fit-v1` | `s14a-ledger-wrap-v1` |
  | --- | --- | --- | --- |
  | S10b train (`hebrew_lines_train_v1.txt`) | 20.0% | 68.0% | 5.0% |
  | S13a train (`hebrew_mixed_lines_train_v1.txt`) | 27.0% | 89.0% | 4.5% |

  Details text per ledger page rises from 104 to 131 characters on the S13a
  train corpus (128 at `s10c-gold-complete-v1`). Lines wrap to fewer rows, so
  pages draw fewer rows (8.6 against 10.0 per page), with fewer number, date,
  amount and balance cells.
- Row capacity (10 rows), row height and the gold conventions are unchanged.
  `logical_order` and the line sidecar still hold only the drawn rows, and
  `truncated_segments` counts the rest.
- A details token is now rejected only when it is wider than 316 px, not
  206 px.
- Other templates are unchanged. A ledger page takes the same draws from the
  shared random stream as at `s11b-ledger-fit-v1`, so every non-ledger page of
  a mixed batch is byte-identical to `s11b-ledger-fit-v1` at the same seed.
  Each ledger page keeps its `s11b-ledger-fit-v1` source lines, identifiers
  and row values; only the details layout, and so the drawn rows, change.
- Validation still accepts `s11b-ledger-fit-v1` batches. Frozen batches
  generated at earlier versions are not regenerated.

## s11b-ledger-fit-v1 (S11b)

- `ledger` cells keep their text inside their columns (#78). The balance
  column grew from 74 to 134 px for values up to `4,980`, and the details
  column shrank from 310 to 250 px. Details text wraps at 206 px (was 282 px),
  which reserves the 22 px anchor inset, 18 px of horizontal jitter and 4 px
  of annotation padding.
- A details token wider than the cell is rejected with `ValueError` instead
  of being drawn across the column rule.
- Side effect, fixed in `s14a-ledger-wrap-v1`: more lines wrap past the
  10-row table, so most ledger pages lost trailing detail rows (#85). On the
  S10b train corpus the ledger page truncation rate rose from about 20% to
  about 68%.
- Other templates draw the same pages, but a ledger page that draws a
  different number of rows moves the shared random stream, so mixed batches
  differ from `s10c-gold-complete-v1` after it.

## S13b: typographic punctuation corpora (generator version unchanged, `s11b-ledger-fit-v1`)

- New packaged text only: `texts/hebrew_typographic_lines_train_v1.txt` and
  `texts/hebrew_typographic_lines_eval_v1.txt`, documented in
  [docs/typographic_text_corpus_card.md](docs/typographic_text_corpus_card.md).
  They add em dash, en dash, geresh, gershayim, typographic quotes and the
  ellipsis, which no earlier packaged corpus contains (#87). Use them with
  `--text-corpus`.
- No generator code changes. The existing packaged corpora are byte-identical,
  so are pages generated from them, and the default corpus is unchanged.

## S13a: mixed-script text corpora (generator version unchanged, `s11b-ledger-fit-v1`)

- New packaged text only: `texts/hebrew_mixed_lines_train_v1.txt` and
  `texts/hebrew_mixed_lines_eval_v1.txt`, documented in
  [docs/mixed_script_text_corpus_card.md](docs/mixed_script_text_corpus_card.md).
  Use them with `--text-corpus`.
- No generator code changes. Pages generated from the existing packaged
  corpora are byte-identical, and the default corpus is unchanged.

## s10c-gold-complete-v1 (S10c)

- Page-level gold is complete. `logical_order` now includes every drawn text
  element: the printed-letter stamp word `נבדק`, the three `אישור` signature
  captions, and the handwritten-note marginal note. The fixed reading order is
  documented in
  [generation_manifest_v1.md](docs/generation_manifest_v1.md#reading-order-of-logical_order).
- Uncapped printed and handwritten bodies stop at a computed line capacity
  (13–23 wrapped lines, depending on style and condition bundle) and report
  the rest as `truncated_segments`; gold holds exactly what is drawn. A body
  word wider than the body width is rejected with `ValueError` instead of being
  drawn off the page.
- `line_annotations.json` lines are emitted in logical order, and no current
  template emits `logical_line_index: null`.
- Page images are byte-identical to `d4a-realism-v2` for packaged-corpus
  batches. Only `logical_order` and `generator_version` change. On the seed-101
  evidence batch, scored characters rise from 12,939 to 13,870 (+931, +7.2%),
  and the manifest sha256 changes from `9b6e54f7…` to `c4b4ca4e…`.
- The packaged `generation_manifest_v1_fixture_batch` manifest is regenerated.
  Its page assets are unchanged.
- Validation still accepts `d4a-realism-v2` batches.

### S11a: sidecar regions (same generator version)

- `line_annotations.json` pages gain `regions` (typed region polygons and
  region reading order), and lines gain `region_index`. The schema id stays
  `hocrsyngen_line_annotations.v1`, and the change is additive. See
  [line_annotations_v1.md](docs/line_annotations_v1.md#regions-s11a).
- Page images, `logical_order`, and the manifest are unchanged, so
  `GENERATOR_VERSION` stays `s10c-gold-complete-v1`. The seed-101 evidence
  manifest is still `c4b4ca4e…`.

## d4a-realism-v2

- Baseline before `S10c`. Drawn stamp, caption, and marginal text was absent
  from `logical_order`.
