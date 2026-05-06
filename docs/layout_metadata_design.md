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

The S3a boundary decision is:

- Pre-generation capability metadata belongs in a future versioned template or
  layout catalog surface. This is the right boundary for document family,
  layout style, supported page regions, annotation types, identifier types,
  production mix, and degradation preset capability.
- Durable per-sample layout metadata belongs in a future manifest/schema change,
  not in a sidecar, when downstream consumers need the metadata to stay attached
  to each generated sample after import.
- Batch-level review, audit, and coverage evidence belongs in a future optional
  sidecar artifact when the data describes inspection results or aggregate
  evidence rather than sample identity.
- Release caps, balancing rules, review status, dataset eligibility, and
  publication decisions belong in `hocrgen` policy, not in `hocrsyngen` baseline
  outputs.

The current stable metadata available to downstream consumers is:

- `hocrsyngen templates --format json`, which exposes template id, recipe id,
  layout style, font style, font id, and degradation preset.
- `generation_manifest.json` v1 provenance, which records template id, recipe
  id, degradation preset, font id, seed, sample index, and source corpus.
- Packaged contract fixtures exported through the CLI.
- Validation reports that prove a generated batch satisfies the manifest and
  asset contract.

The current stable surfaces are enough for coarse filtering by existing
template, recipe, font, and degradation ids. They are not enough for filtering by
document family, page regions, marginalia, stamps, identifiers, density, or
reviewability without a future catalog, manifest, or sidecar contract.

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

The minimum future taxonomy should be specified at the contract boundary before
implementation. The initial recommended fields are:

| Field | Scope | Example governed ids | Recommended boundary |
| --- | --- | --- | --- |
| `document_family` | Capability and per-sample identity | `administrative_form`, `letter`, `notebook_note`, `ledger`, `classroom_note`, `archive_card` | Catalog first; manifest/schema when emitted per sample |
| `layout_style` | Capability and per-sample identity | `printed_form`, `handwritten_note`, `mixed_overlay`, `tabular`, `freeform_note`, `multi_region_page` | Catalog first; manifest/schema when emitted per sample |
| `text_production_mix` | Capability and per-sample identity | `printed`, `handwritten_like`, `printed_with_handwritten_annotation`, `handwritten_like_with_printed_annotation` | Catalog first; manifest/schema when emitted per sample |
| `page_regions` | Capability and optional evidence | `header`, `title`, `body`, `footer`, `form_rows`, `table_cells`, `signature_area`, `margin`, `stamp_area`, `identifier_area` | Catalog for supported regions; sidecar for review evidence; manifest/schema only if required per sample |
| `annotation_types` | Capability and optional evidence | `marginal_note`, `underline`, `correction`, `tick`, `arrow`, `synthetic_stamp` | Catalog for supported annotations; sidecar for evidence |
| `identifier_types` | Capability and optional evidence | `form_number`, `date`, `ledger_id`, `archive_id`, `page_number` | Catalog for supported identifiers; manifest/schema only if identifiers become durable sample metadata |
| `degradation_preset` | Capability and per-sample provenance | Existing ids such as `office_scan_soft` and `notebook_scan_worn`; future ids for stronger wear presets | Existing catalog/provenance today; catalog and manifest/schema for future ids |
| `layout_density` | Capability and optional per-sample summary | `sparse`, `moderate`, `dense` | Catalog for intended density; manifest/schema if emitted per sample |
| `review_features` | Review evidence only | `has_stable_regions`, `has_visible_identifier`, `has_reviewable_annotations` | Sidecar or review rubric, not manifest v1 |

Future contracts may refine these ids, but they should not replace the coarse
categories with private helper names, local file names, or pixel-level drawing
parameters.

## Stable Boundaries For hocrgen

`hocrgen` should filter and cap current `hocrsyngen` batches using only stable
public surfaces:

- Before generation, use `hocrsyngen templates --format json` to discover
  available template ids, recipe ids, layout styles, font styles, font ids, and
  degradation presets.
- During import, validate `generation_manifest.json` v1 and use manifest
  provenance fields for sample-level filtering by template id, recipe id,
  degradation preset, font id, seed, sample index, and source corpus.
- For contract tests, use `hocrsyngen contracts export` instead of package
  internals.

Manifest v1 alone does not support filtering generated samples by document
family, font style, page regions, marginalia, stamps, identifiers, density, or
reviewability. Until a future contract exposes those fields, `hocrgen` can only
derive them by joining a validated manifest sample's template or recipe id
against a stable catalog snapshot that documents those capabilities.

Future pre-generation family caps should be added through a documented catalog
surface. Future post-generation sample filters that require durable richer
per-sample metadata should use a versioned manifest/schema update. Future
filters based on review or audit evidence should use an explicit sidecar
artifact. `hocrgen` should not inspect `SyntheticRecipe`, `SyntheticDocument`,
drawing helper names, package resource paths, or other private Python
implementation details.

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

## Sidecar Path And Reference Rules

Any future layout review, audit, or coverage sidecar must follow the same
portable reference policy as manifest v1 asset paths:

- relative POSIX paths only;
- no absolute paths;
- no drive-letter paths;
- no backslashes;
- no `..` path segments.

Sidecar references should use stable public identifiers such as manifest sample
ids, page ids, template ids, recipe ids, fixture ids, and relative asset paths.
They should not use local temporary paths, package resource paths, private
Python class names, drawing helper names, or platform-specific identifiers.

## Future Implementation Sequence

The recommended implementation order after S3a is:

1. Add a versioned template or layout catalog expansion for pre-generation
   capability metadata, using the coarse taxonomy in this document.
2. Add tests for that catalog surface before changing generator output.
3. Add the first new document family recipe only after the metadata contract and
   validation implications are settled.
4. Add a versioned manifest/schema change only when richer metadata must travel
   with generated samples after import.
5. Add an optional sidecar only for review, audit, or coverage evidence that is
   not core sample identity.
6. Add review rubrics and fixture guidance so realism improvements remain
   inspectable and reproducible.

S3a stops at this design. Template, schema, generator, fixture, and CLI changes
belong in later PRs so their compatibility impact can be reviewed deliberately.
