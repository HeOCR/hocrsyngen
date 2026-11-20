# ADR 0005 - Persona, Style, And Condition Semantics

## Status

Accepted

## Context

Future roadmap work needs persona, style, and condition controls for synthetic
Hebrew OCR/HTR generation. The current manifest v1 contract already contains
`controls.persona` and `controls.condition`, but those fields are synthetic
controls only. The repository needs explicit semantics before implementation so
future metadata does not imply real people, real documents, health or
psychological states, authorship, provenance, or release eligibility.

S4a is a documentation and planning decision only. It does not change generator
behavior, CLI output, `generation_manifest.json` v1, schemas, packaged contract
fixtures, dependencies, validation behavior, review status, balancing policy,
release policy, or publication behavior.

## Decision

Persona, style, and condition controls are synthetic generator parameter bundles
only.

- `persona` means a deterministic synthetic parameter bundle or seed/control
  profile. It can group repeatable style, template, corpus, or rendering choices
  across generated samples. It is not a person, real identity, demographic
  profile, writer, or source.
- `style` means observable rendering parameters such as slant, spacing,
  pressure proxy, baseline drift, character variability, line discipline, and
  allograph or ligature choices. Style labels describe generated appearance, not
  authorship or identity.
- `condition` means a rendering-control preset only. Condition controls should
  prefer neutral, measurable labels tied to parameters such as spacing,
  baseline drift, density, degradation, stroke-variation proxy, or line
  discipline. They must not claim medical, psychological, disability, or
  sensitive personal states.

Future implementation must avoid claims about:

- real identity, real authorship, or living-person imitation;
- real-source provenance or document origin;
- medical diagnosis, health status, psychological state, disability, sensitive
  attributes, or demographic inference;
- release eligibility, review status, balancing decisions, or publication
  readiness.

Future public metadata must use stable documented boundaries:

- Pre-generation capability metadata belongs in a future versioned catalog
  surface when downstream tools need to discover available persona, style, or
  condition presets before generation.
- Durable per-sample metadata belongs in a future manifest/schema update when
  downstream tools need it attached to generated samples after import.
- Review, audit, or coverage evidence belongs in future explicit sidecar
  artifacts and must remain outside `generation_manifest.json` v1 unless a
  versioned schema update is designed.

The current manifest v1 controls remain compatible as `string|null` synthetic
control slots. New semantics, enumerations, or richer objects require docs,
schema, validation, fixture, and downstream compatibility updates before they
become machine contracts.

## Consequences

Future S4 implementation can add deterministic style controls without turning
synthetic controls into identity, authorship, health, psychology, provenance, or
release claims.

Documentation and tests should describe persona, style, and condition values as
generator controls. PRs that introduce new controls should include negative
coverage or review checks that prevent forbidden claims from appearing in public
metadata, docs, CLI reports, manifests, or fixtures.

`hocrgen` may use future documented catalog or manifest surfaces for filtering,
caps, and stratification, but release governance remains downstream. It should
not infer persona, style, or condition semantics from private Python internals.

## Follow-up

Before implementing S4b or later controls:

- define stable preset ids and allowed labels at the public boundary;
- keep any manifest changes additive or explicitly versioned;
- update `generation_manifest_v1.md` or a successor contract document, JSON
  schema, validation behavior, fixture expectations, tests, and
  `hocrgen_integration.md` together if per-sample metadata changes;
- keep optional learned or heavyweight generation paths out of baseline
  dependencies.
