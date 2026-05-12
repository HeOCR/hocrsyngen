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
`gveret-levin-regular` TTF font and the `handwritten_note` / `handwritten_note_*`
template family. The S5 handwriting research program documented allograph,
character-level, and word/line assembly prototype plans, then closed by
deferral because no accepted in-repo prototype or downstream evaluation
evidence exists.

The `HeOCR/hletterscript` repository provides a different external answer to
the same handwriting-realism question: per-writer letter-glyph image variants
extracted by `HeOCR/hletterscriptgen` from rights-clean scans in
`HeOCR/public-domain-hand-written-hebrew-scans`. Composing pages from those
glyph variants is deterministic, file-based, and stays inside the baseline
no-network / no-GPU / no-LLM dependency boundary. Phase S9 scopes that
composition without ML.

## Scope Boundary

`S9a` is acceptable inside `hocrsyngen` only when it stays inside the
following boundaries.

Allowed:

- Human-readable design notes, contract sketches, and stop/reject gates under
  `docs/`.
- Cross-references from `README.md`, `AGENTS.md`, `llms.txt`,
  `docs/README.md`, `docs/repository_scope.md`, `docs/architecture.md`,
  `docs/roadmap.md`, `docs/production_readiness.md`,
  `docs/research_program.md`, and `docs/handwriting_research_acceptance_criteria.md`
  so future readers can find the plan.
- Naming external upstream dependency labels (`H2a`, `H2b`, `H2c`) without
  implementing upstream behavior in this repository.

Not allowed in `S9a`:

- New CLI flags, subcommands, schemas, fixtures, packaged data, generator
  behavior, validation behavior, baseline dependencies, or test changes that
  depend on `letter_set.v1` consumption.
- Any import of `hletterscript`, `hletterscriptgen`, or
  `public-domain-hand-written-hebrew-scans` Python code or runtime data.
- Any change to `generation_manifest.json` v1 constants, schema, or
  validation behavior.
- Any change to the packaged `generation_manifest_v1_fixture_batch` or its
  adapter contract assertions documented in `S6g`.

## Upstream Contracts

`S9a` references the following upstream contracts. Implementation slices may
consume them only as files, never by importing the upstream Python code.

- [`HeOCR/public-domain-hand-written-hebrew-scans`](https://github.com/HeOCR/public-domain-hand-written-hebrew-scans)
  owns rights-curated page scans. Its `data/index/sources.jsonl` and
  `data/index/entries.jsonl` carry source-level and scan-level records, with
  per-scan license evidence (`PDM-1.0`, `LicenseRef-Public-Domain-Israel`,
  `LicenseRef-Public-Domain-Ukraine`, `CC-BY-SA-4.0`, and similar). Schemas
  live in that repo under `schemas/source.schema.json` and
  `schemas/entry.schema.json`.
- [`HeOCR/hletterscriptgen`](https://github.com/HeOCR/hletterscriptgen)
  owns the `letter_set.v1` JSON Schema (packaged in
  `src/hletterscriptgen/schemas/letter_set.schema.json`) and the
  `hletterscriptgen` CLI (`version`, `schema`, `validate`; `generate` is
  reserved). The `letter_set.v1` document is one record per writer with a
  per-letter map of variants. Each variant carries `asset_path`, SHA-256
  checksum, image metadata, and per-variant `source` rights that inherit
  from the upstream scan.
- [`HeOCR/hletterscript`](https://github.com/HeOCR/hletterscript) owns the
  published per-writer letter-glyph image dataset. Its `data/letters/<writer_id>/<letter_name>/`
  layout holds image bytes tracked by Git LFS. Indexes live in
  `data/index/writers.jsonl` and `data/index/entries.jsonl`. The repository is
  currently `v0.0.0-rc` with empty indexes; a populated baseline corpus is
  the external dependency `H2c` recorded in
  [production_readiness.md](production_readiness.md).

## Proposed Manifest v2 Boundary

Manifest v1 must remain bit-stable for existing font-rendered batches and for
the packaged `generation_manifest_v1_fixture_batch`. Real-glyph composition
introduces a separate additive surface.

The proposed direction for implementation slice `S9b`:

- Add a packaged schema `generation_manifest.v2` alongside (not replacing) the
  current v1 schema. v2 inherits all v1 constants and required fields and
  remains backward-compatible: a v2 batch that uses only packaged TTF fonts
  should be readable under both v1 and v2 validators.
- Introduce an optional discriminator
  `sample.provenance.glyph_source: "packaged_font" | "letter_set_v1"`.
  Existing samples implicitly map to `packaged_font`.
- When `glyph_source == "letter_set_v1"`, add:
  - `sample.provenance.writer_id` — opaque string id of the writer in the
    consumed `letter_set.v1` document.
  - `sample.provenance.glyph_variants` — ordered array of variant references
    used to render this sample, each with `letter`, `variant_id`,
    `asset_path` (relative to the batch directory or to a configured
    `--letter-set-root`), `sha256`, and `source.scan_entry_id` plus
    `source.license` carried verbatim from the upstream `letter_set.v1`
    document.
  - `sample.license_summary.licenses` — sorted unique set of every license
    that appears in any glyph variant of the sample, mirroring the
    `letter_set.v1` `license_summary.licenses` semantics.
- Introduce a parallel packaged fixture id
  `generation_manifest_v2_fixture_batch`. Do not mutate the v1 fixture.

Out of scope for `S9b`:

- Replacing or hiding any manifest v1 field.
- Embedding `letter_set.v1` schemas inside `hocrsyngen` rather than packaging
  a sibling reference. Cross-repo schema reuse should be by JSON document,
  not by Python import.

## Composer Interface

The current `src/hocrsyngen/generator.py` pipeline assumes one packaged TTF
font per sample. Real-glyph composition is a different rendering path:
deterministic per-letter variant selection from a `letter_set.v1` document,
baseline placement, kerning approximation, and reuse of the existing
degradation pipeline.

Implementation slice `S9c` should introduce a common `PageComposer` interface
with two implementations:

- `FontComposer` — the current font-rendered path, preserved bit-for-bit for
  manifest v1 batches.
- `GlyphComposer` — file-based glyph composition from a `letter_set.v1`
  source.

Determinism rules for `GlyphComposer`:

- Variant selection per (writer_id, letter, seed, sample_index) must be a
  pure deterministic function of those inputs and the variant ordering inside
  the `letter_set.v1` document. JSONL line order in the upstream document is
  the canonical variant ordering.
- Variant lookup must be defined for every Hebrew letter the sample's text
  uses, including final forms. A missing letter for the selected writer must
  be a hard error from the composer, not a silent fallback to a different
  writer.
- Optional within-line geometric perturbations (baseline drift,
  inter-character spacing) must be seeded from the same composer seed as
  variant selection.

Out of scope for `S9c`:

- Cross-writer variant blending inside a single sample. The default policy
  is one writer per sample; cross-writer composition is a later design
  question, not part of `S9c`.
- Any ML-backed glyph synthesis, shape interpolation, or stroke modeling.

## Asset-Location Boundary

`HeOCR/hletterscript` ships glyph image bytes through Git LFS. `hocrsyngen`
must never fetch from the network at generation time, so the location of the
glyph assets becomes an explicit input.

Implementation slices that consume `letter_set.v1` must:

- Accept an explicit local path to a checked-out `hletterscript` (for
  example a `--letter-set-root PATH` CLI flag) or to a single
  `letter_set.v1` document plus its asset root. Path discovery must be
  explicit; no implicit environment lookup, no shell expansion of remote
  URLs, no automatic LFS fetch.
- Validate that every `asset_path` in the consumed `letter_set.v1` resolves
  to a present file on disk with the recorded SHA-256, before any composer
  call begins.
- Refuse to operate on a `letter_set.v1` document whose asset bytes are
  missing or whose hashes do not match, with a deterministic error.

Implementation slice `S9g` ships a tiny embedded `letter_set.v1` fixture
inside `src/hocrsyngen/data/contracts/` so unit tests stay hermetic and CI
does not need Git LFS. That fixture covers the contract surface; it is not
a substitute for a real `hletterscript` checkout.

## Validation Extensions

Implementation slice `S9e` extends `src/hocrsyngen/validation.py` for v2
batches:

- Validate the manifest document against the packaged v2 schema.
- For every `sample` with `glyph_source == "letter_set_v1"`, verify that
  every `glyph_variants[]` entry resolves to a present asset (under the
  batch directory or the configured `--letter-set-root`), with a matching
  SHA-256.
- Verify that `sample.license_summary.licenses` is the sorted unique set of
  the licenses appearing in `sample.provenance.glyph_variants[].source.license`.
- Optionally, when a path to a `public-domain-hand-written-hebrew-scans`
  checkout is configured, verify that every
  `glyph_variants[].source.scan_entry_id` resolves to a known entry in
  `data/index/entries.jsonl`. This check is gated on the optional
  configuration and is never an automatic network resolution.

Out of scope for `S9e`:

- Any release-eligibility verdict. Rights propagation is recorded faithfully
  but is not interpreted as a release-eligible signal here.
- Importing `hletterscript` or `hletterscriptgen` Python code to validate.

## Wet-Test Extensions

Implementation slice `S9f` extends the existing S8 wet-test family for glyph
batches without changing manifest v1 behavior:

- `wet-analyze` adds writer-distribution warnings (one writer dominating a
  batch is a diversity concern) and per-glyph coverage summaries.
- `wet-review-template` adds optional review-worksheet columns for
  glyph-level artifacts (illegible glyph, swapped final form, baseline
  break, etc.).
- The static gallery (`wet-gallery`) surfaces per-glyph provenance and the
  per-sample `license_summary` so reviewers can see which writers and which
  upstream scans contributed to a sample.

Glyph-aware wet-test artifacts remain outside `generation_manifest.json` v1
and outside any release-governance claim.

## Persona / Condition vs. Provenance Reconciliation

The S4 persona/condition controls and
[ADR 0005](decisions/0005-persona-style-condition-semantics.md) forbid
representing controls as real identity, real authorship, medical,
psychological, sensitive-attribute, demographic, provenance, or release-
eligibility claims.

Real-glyph composition uses a real writer's hand. The clean separation:

- The selected writer is **provenance**, not a control. It lives in
  `sample.provenance.writer_id` plus the per-variant `source.scan_entry_id`,
  not in `controls.persona`.
- `controls.persona` and `controls.condition` continue to be neutral
  rendering-control bundles (spacing, baseline drift, degradation, ink
  pressure proxy) and continue to follow ADR 0005's forbidden-claims
  boundary.
- `writer_id` must be an opaque id from the consumed `letter_set.v1`
  document. It is not a public name, demographic label, or sensitive
  attribute, and `hocrsyngen` must not attach such attributes to it.

## Prerequisites And Gating

`S9b` through `S9h` are gated on the following upstream readiness, tracked
in [production_readiness.md](production_readiness.md):

- `H2a` — `HeOCR/public-domain-hand-written-hebrew-scans` reaches a stable
  index baseline with documented per-scan rights evidence for every entry
  referenced by upstream letter-glyph extractions.
- `H2b` — `HeOCR/hletterscriptgen` ships an extraction pipeline that
  produces conforming `letter_set.v1` documents with full rights carryover.
- `H2c` — `HeOCR/hletterscript` reaches a populated baseline corpus of
  per-writer letter sets covering all 27 Hebrew letter forms across
  multiple writers, with passing validation and stable LFS-tracked assets.

Until `H2c` is satisfied, only `S9a` design-only work is appropriate inside
this repository.

## Stop / Reject Gates

`S9` implementation slices must stop or be rejected when any of the
following holds:

- Real-glyph composition would require importing `hletterscript`,
  `hletterscriptgen`, or `public-domain-hand-written-hebrew-scans` Python
  code into `hocrsyngen`.
- The composer would require a network call, Git LFS fetch, or other
  non-file-based asset retrieval at generation time.
- Manifest v1 semantics, the packaged `generation_manifest_v1_fixture_batch`,
  or `S6g` adapter contract assertions would have to change to accommodate
  glyph composition.
- Per-variant rights would be broadened, relicensed, or omitted from
  `sample.license_summary`.
- The selected writer would be represented as a persona, condition, real
  identity, demographic label, or sensitive attribute, in violation of
  ADR 0005.
- Baseline package dependencies would expand into network, GPU, LLM,
  diffusion, Torch, TensorFlow, or other heavyweight generative-model
  stacks.
- Downstream governance behavior (release profiles, caps, review workflows,
  export, publication) would have to live inside `hocrsyngen` to make the
  slice work.

## Non-Goals

`S9` does not:

- Reopen Phase S5. S5 remains closed by deferral; `S9` is a separate
  phase that answers the handwriting-realism question externally rather
  than through in-repo ML synthesis.
- Implement Arabic or other non-Hebrew script support. Script abstraction
  is tracked separately under `S7b` / `S7c`.
- Move mix decisions (which writers a candidate batch samples from) into
  `hocrsyngen`. Mix ownership remains downstream in `hocrgen` per `S6d`
  and `S6f`. `hocrsyngen` accepts a writer-set selection as an input, it
  does not pick one on behalf of `hocrgen`.
- Make release-eligibility claims, downstream realism acceptance claims,
  OCR/HTR utility claims, or domain-match claims. Those gates remain
  downstream per `S6a`–`S6g`.
