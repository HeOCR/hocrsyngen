# ADR 0006 - Real-Glyph Provenance Boundary

## Status

Accepted

## Context

Phase S9 introduces real-glyph page composition from `HeOCR/hletterscript`
per-writer letter sets. Each glyph in a generated sample comes from a specific
writer's hand. ADR 0005 established that `controls.persona` and
`controls.condition` must not carry real identity, real authorship, provenance,
or sensitive-attribute claims.

A real writer's `writer_id` is different in kind from a synthetic persona
bundle: it is a factual attribution to an upstream rights-bearing source, not a
generator tuning parameter. The manifest needs to record it faithfully for
rights propagation without conflating it with the synthetic control surface.

## Decision

Real writer identity is provenance, not a persona or condition control.

- `writer_id` belongs in `sample.provenance`, alongside `template_id`,
  `recipe_id`, `font_id`, and per-glyph `source` attribution. It is not placed
  in `controls.persona` or `controls.condition`.
- `controls.persona` and `controls.condition` continue to follow the
  forbidden-claims boundary in ADR 0005: they are neutral rendering-control
  bundles (spacing, baseline drift, degradation, ink pressure proxy) and must
  not be used to represent real authorship, real identity, demographic labels,
  or sensitive attributes.
- `writer_id` must be an opaque id sourced from the consumed `letter_set.v1`
  document. `hocrsyngen` must not attach public names, demographic labels,
  biographical information, or sensitive attributes to it.
- Per-glyph `source` rights (scan entry id, license) are carried verbatim from
  `letter_set.v1` into `sample.provenance.glyph_variants[].source`. They are
  factual provenance records, not release-eligibility claims.

## Consequences

- Manifest v2 design must place writer and per-glyph provenance under
  `sample.provenance`, not under `controls`.
- ADR 0005's forbidden-claims boundary is preserved intact for `controls.*`.
- Rights propagate faithfully through `sample.provenance` so `hocrgen` can
  apply release caps without `hocrsyngen` making eligibility judgements.
- This decision applies to all Phase S9 implementation slices. Any proposal to
  move writer identity into `controls.*` must amend this ADR first.
