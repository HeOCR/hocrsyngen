# Layout Metadata Design

This document defines the S3a design direction for document-layout metadata.
It is intentionally a planning document only: S3a does not change generator
behavior, CLI behavior, dependencies, packaged contract fixtures,
`generation_manifest.json` v1, or the manifest schema.

## Recommendation

Layout metadata should be introduced only through stable public boundaries.
S3a should not add undocumented fields to `generation_manifest.json` v1 because
the v1 schema rejects unknown fields and is already a downstream contract for
`hocrgen` integration.

The current stable metadata available to downstream consumers is:

- `hocrsyngen templates --format json`, which exposes template id, recipe id,
  layout style, font style, font id, and degradation preset.
- `generation_manifest.json` v1 provenance, which records template id, recipe
  id, degradation preset, font id, seed, sample index, and source corpus.
- Packaged contract fixtures exported through the CLI.
- Validation reports that prove a generated batch satisfies the manifest and
  asset contract.

Future richer layout metadata should use one of these explicit designs:

- A versioned manifest/schema change when metadata must travel with each
  generated sample.
- A future template or layout catalog contract when metadata describes generator
  capabilities before generation.
- A future optional batch-level sidecar artifact when metadata is review or
  evidence about generated outputs rather than core sample identity.
- `hocrgen`-side policy when the data is about release caps, source composition,
  review status, or dataset governance.

## Metadata Purpose

Layout metadata should help `hocrsyngen` and `hocrgen` answer practical
questions without importing private Python internals:

- Which document family or layout family a sample belongs to.
- Which governed template, recipe, font style, and degradation preset produced
  it.
- Whether a batch contains the intended mix of printed, handwritten-like, and
  overlay-like visual features.
- Which visible page regions or layout elements are present.
- Whether samples are easy for a human reviewer to inspect and reject when
  realism, Hebrew readability, or artifact control is weak.
- Which stable identifiers `hocrgen` can use to filter, cap, or balance
  candidate synthetic inputs before applying release governance.

The metadata is descriptive generator metadata. It must not imply real
identity, real authorship, medical state, psychological state, source
provenance, release readiness, or dataset eligibility.

## Layout Dimensions

Future layout metadata should use stable, coarse identifiers rather than
private drawing helper names or pixel-specific values. The important dimensions
are:

- Document family: administrative form, letter, notebook note, ledger,
  classroom-like note, archive card, receipt-like document, or other governed
  family names.
- Layout style: printed form, handwritten-like note, mixed printed and
  handwritten-like overlay, tabular layout, freeform note, or multi-region page.
- Text production mix: printed, handwritten-like, mixed printed annotation, or
  mixed handwritten-like annotation.
- Page regions: header, title, body, footer, form rows, table cells, signature
  area, margin, stamp area, identifier area, or review-only decoration.
- Marginalia and annotations: governed notes, underlines, arrows, corrections,
  ticks, or other synthetic marks that remain non-identity claims.
- Stamps and identifiers: synthetic stamps, form numbers, dates, ledger ids, or
  other deterministic identifiers that do not claim real provenance.
- Degradation presets: scan softness, blur, skew, grain, stains, creasing,
  contrast, brightness, and wear levels as governed preset ids.
- Density and structure: approximate line count, region count, text density,
  whitespace profile, table/grid presence, and page orientation where relevant.
- Reviewability: whether the layout has stable visual features a reviewer can
  assess for realism, Hebrew readability, clipping, overlap, excessive noise,
  and artifact control.

The first implementation that exposes these dimensions should prefer bounded
enumerations and stable ids. Free-text notes can exist in design docs and review
rubrics, but machine contracts should avoid open-ended labels unless the field
is explicitly documented as advisory.

## Stable Boundaries For hocrgen

`hocrgen` should filter and cap current `hocrsyngen` batches using only stable
public surfaces:

- Before generation, use `hocrsyngen templates --format json` to discover
  available template ids, recipe ids, layout styles, font styles, font ids, and
  degradation presets.
- During import, validate `generation_manifest.json` v1 and use manifest
  provenance fields for sample-level filtering.
- For contract tests, use `hocrsyngen contracts export` instead of package
  internals.

Future pre-generation family caps should be added through a documented catalog
surface. Future post-generation sample filters that require richer per-sample
metadata should use either a versioned manifest/schema update or an explicit
sidecar artifact. `hocrgen` should not inspect `SyntheticRecipe`,
`SyntheticDocument`, drawing helper names, package resource paths, or other
private Python implementation details.

`hocrgen` remains responsible for release eligibility, synthetic caps, source
composition, balancing, review, privacy, dedupe, leakage checks, release
assembly, export, and publication. Layout metadata can inform those policies,
but it must not encode them inside `hocrsyngen` baseline outputs.

## Manifest V1 Scope

These items must remain out of `generation_manifest.json` v1 until a versioned
schema change is planned and implemented with docs, validation, fixture, and
downstream compatibility updates:

- Rich layout family metadata beyond current template and provenance ids.
- Page-region geometry, bounding boxes, polygons, or reading-order regions.
- Review status, reviewer decisions, candidate rejection reasons, or dataset
  eligibility.
- Release caps, balancing rules, hocrgen import policy, or HeOCR publication
  policy.
- Environment probes, visual inspection scores, or coverage matrices.
- Claims about real document provenance, real writer identity, authorship,
  medical condition, psychological condition, or sensitive attributes.

If a future PR decides that per-sample layout metadata belongs in the manifest,
it must update the JSON schema, `generation_manifest_v1.md` or a successor
version document, validation behavior, tests, contract fixture expectations, and
`hocrgen` integration notes together.

## Future Implementation Sequence

The recommended implementation order after S3a is:

1. Design a small stable layout taxonomy with governed ids for document
   families, layout styles, page regions, annotation types, identifier types,
   and degradation presets.
2. Decide whether the first production surface is a template catalog expansion,
   a versioned manifest addition, or an optional sidecar artifact.
3. Add tests for that chosen public surface before changing generator output.
4. Add the first new document family recipe only after the metadata contract and
   validation implications are settled.
5. Add review rubrics and fixture guidance so realism improvements remain
   inspectable and reproducible.

S3a stops at this design. Template, schema, generator, fixture, and CLI changes
belong in later PRs so their compatibility impact can be reviewed deliberately.
