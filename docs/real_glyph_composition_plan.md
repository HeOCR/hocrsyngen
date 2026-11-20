# Real-Glyph Composition Plan

`S9a` is a design-only planning note for future real-glyph page composition in
`hocrsyngen`. It does not implement glyph composition, add `hletterscript` or
`hletterscriptgen` imports, change `generation_manifest.json` v1, change
validation semantics, add baseline dependencies, change CLI defaults, add
schemas, mutate packaged fixtures, or move downstream governance into this
repository.

The current implementation remains font-rendered: every generated page is
composed from packaged TTF fonts under `src/hocrsyngen/data/synthetic/fonts/`.
Manifest v1, the packaged `generation_manifest_v1_fixture_batch`, and the
`hocrgen` adapter checklist documented in `S6g` are unchanged by `S9a`.

## Motivation

`hocrsyngen` today approximates handwritten Hebrew through the
`gveret-levin-regular` TTF font. The `HeOCR/hletterscript` repository offers a
different answer to the handwriting-realism question that S5 left open:
per-writer letter-glyph image variants, deterministic, file-based, and staying
inside the no-network / no-GPU / no-LLM dependency boundary. Phase S9 scopes
that composition without ML.

For the upstream repository contracts and the full six-repo pipeline, see
[docs/repository_scope.md](repository_scope.md).

## Scope Boundary

Allowed in `S9a`:

- Human-readable design notes, contract sketches, and stop/reject gates under `docs/`.
- Cross-references from README, AGENTS.md, llms.txt, and related docs files.
- Naming external upstream dependencies without implementing upstream behavior.

Not allowed in `S9a`:

- New CLI flags, subcommands, schemas, fixtures, packaged data, generator
  behavior, validation behavior, baseline dependencies, or test changes.
- Any import of `hletterscript`, `hletterscriptgen`, or
  `public-domain-hand-written-hebrew-scans` Python code or runtime data.
- Any change to `generation_manifest.json` v1 constants, schema, or
  validation behavior.
- Any change to the packaged `generation_manifest_v1_fixture_batch` or its
  adapter contract assertions documented in `S6g`.

## Implementation Direction

When `HeOCR/hletterscript` reaches a populated, validated baseline corpus,
implementation slices `S9b` onward should:

- Introduce an additive `generation_manifest.v2` alongside (not replacing) v1.
- Consume `letter_set.v1` documents through file-based contracts only — never
  by importing `hletterscript` Python code or triggering network or LFS fetches
  at generation time.
- Keep real writer identity in `sample.provenance` (not `controls.persona`),
  consistent with ADR 0005 and
  [decisions/0006-real-glyph-provenance-boundary.md](decisions/0006-real-glyph-provenance-boundary.md).
- Extend the S8 wet-test family for glyph-batch quality signals without
  changing manifest v1 behavior.

Detailed field names, class names, CLI flags, and error-handling semantics
belong in the implementation PRs, not in this design note.

## Prerequisites

`S9b` and later slices are gated on `HeOCR/hletterscript` reaching a populated
baseline corpus of per-writer letter sets covering all 27 Hebrew letter forms,
with passing validation and stable LFS-tracked assets. See
[production_readiness.md](production_readiness.md) for the current state of
upstream readiness. Until those conditions are met, only `S9a` design-only
work is appropriate inside this repository.
