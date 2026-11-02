# Changelog

Generator-output changes for `hocrsyngen`, keyed by `GENERATOR_VERSION` (the
`generator_version` recorded on every manifest sample). Roadmap notations refer
to [docs/roadmap.md](docs/roadmap.md).

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

## d4a-realism-v2

- Baseline before `S10c`. Drawn stamp, caption, and marginal text was absent
  from `logical_order`.
