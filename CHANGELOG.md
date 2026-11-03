# Changelog

Generator-output changes for `hocrsyngen`, keyed by `GENERATOR_VERSION` (the
`generator_version` recorded on every manifest sample). Roadmap notations refer
to [docs/roadmap.md](docs/roadmap.md).

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
