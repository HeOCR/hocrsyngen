# Repository Scope

## Mission

`hocrsyngen` generates synthetic Hebrew OCR/HTR sample batches with image assets, exact text ground truth, metadata, provenance, and synthetic disclosure. Its output is candidate synthetic input for downstream governance, not a release-ready dataset payload.

`hocrgen` is responsible for dataset governance, release profiles, review, dedupe, privacy, source acquisition, publication, export, and HeOCR handoff.

HeOCR is the public dataset payload and release repository.

## HeOCR Ecosystem Position

`hocrsyngen` is the page-composition step of a six-repository pipeline.
Upstream of `hocrsyngen` are the real-glyph chain repositories that turn
public-domain handwritten Hebrew scans into per-writer letter-glyph sets;
downstream of `hocrsyngen` are governance and release repositories.

| Repo | Owns | Relationship to `hocrsyngen` |
| --- | --- | --- |
| `HeOCR/public-domain-hand-written-hebrew-scans` | Rights-curated handwritten Hebrew page scans plus per-scan license evidence (JSONL indexes). | Upstream of `hletterscriptgen`. Not consumed directly by `hocrsyngen`. |
| `HeOCR/hletterscriptgen` | Code-only framework that extracts per-writer letter-glyph sets from those scans. Owns the `letter_set.v1` JSON Schema and CLI. | Tooling upstream of `hletterscript`. Not imported or consumed by `hocrsyngen`. |
| `HeOCR/hletterscript` | Per-writer Hebrew letter-glyph image dataset (LFS-stored) with rights inherited from upstream scans. Currently `v0.0.0-rc` with empty indexes. | Future S9 input substrate for `hocrsyngen` real-glyph composition. Not consumed today. |
| `HeOCR/hocrsyngen` (this repo) | Deterministic candidate synthetic Hebrew OCR/HTR page generation, manifest v1, validation, contract fixtures, and generator-quality evidence. | — |
| `HeOCR/hocrgen` | Dataset orchestration, governance, validation, review, dedupe, caps, release assembly, export, and publication. Consumes `hocrsyngen` only through installed CLI, manifest v1, and the packaged contract fixture. | Downstream. Must never be imported by `hocrsyngen`. |
| `HeOCR/HeOCR` and `HeOCR/HeOCRsynth` | Public real and synthetic dataset payloads and releases. | Further downstream. |

Today `hocrsyngen` composes pages only from packaged TTF fonts shipped under
`src/hocrsyngen/data/synthetic/fonts/`. Real-glyph composition from
`hletterscript` per-writer letter sets is design-only under Phase S9 and is
documented in
[real_glyph_composition_plan.md](real_glyph_composition_plan.md).

## In Scope For hocrsyngen

- Deterministic synthetic batch generation.
- Governed fonts and text corpora.
- `generation_manifest.json` contract.
- Validation of generated batches.
- Contract fixtures for downstream integration.
- Research planning for better synthetic Hebrew handwriting and document realism.

## Out Of Scope For hocrsyngen Baseline

- Live source acquisition.
- Public dataset release assembly.
- Hugging Face or GitHub dataset publication.
- Privacy review workflows.
- Real-source rights classification.
- Broad crawling.
- `hocrgen` runtime integration beyond stable manifest and CLI contracts.
- Baseline GPU or deep-learning generation stack.

## Boundary Decisions

Generated batches are candidate synthetic inputs. They must be imported into `hocrgen` and pass downstream governance before anything can become part of a public HeOCR release.

`hocrsyngen` should not import `hocrgen`. Integration is through the installed CLI, `generation_manifest.json` v1, and packaged contract fixtures. This keeps the generator lightweight and preserves a clear boundary between synthetic generation and dataset governance.

Persona, style, and condition controls are generator parameter bundles only.
They must not be represented as real identity, real authorship, medical,
psychological, sensitive-attribute, provenance, or release-eligibility claims.
The durable semantics are recorded in
[ADR 0005](decisions/0005-persona-style-condition-semantics.md).

## Current Implementation Facts

- The package lives under `src/hocrsyngen/`.
- The current public CLI exposes `templates`, `contracts`, `contracts export`, `generate`, and `validate`.
- The current manifest schema lives at `src/hocrsyngen/schemas/generation_manifest.schema.json`.
- The packaged contract fixture id is `generation_manifest_v1_fixture_batch`.
- The baseline dependencies are `jsonschema` and `Pillow`; test dependencies add `pytest`.

## Future Work

- Expand Hebrew rendering coverage without weakening the existing manifest contract.
- Add richer governed fonts and corpora only with provenance and license records.
- Plan style/persona/condition metadata before adding new manifest semantics,
  following [ADR 0005](decisions/0005-persona-style-condition-semantics.md).
- Keep optional ML-backed research paths isolated from the baseline package.
- Plan real-glyph composition from `HeOCR/hletterscript` letter sets through
  the design-only `S9a` track in
  [real_glyph_composition_plan.md](real_glyph_composition_plan.md) before any
  implementation. Real-glyph composition must remain additive over manifest
  v1, file-based (no network/LFS pulls inside `hocrsyngen`), and must preserve
  the existing baseline dependency boundary.

## Risks And Open Questions

- Hebrew RTL rendering depends on Pillow libraqm support in the local environment.
- More realistic handwriting may require optional research dependencies that must not contaminate baseline installs.
- Future schema additions need a compatibility plan so `hocrgen` adapters can validate predictably.
