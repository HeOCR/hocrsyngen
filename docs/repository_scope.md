# Repository Scope

## Mission

`hocrsyngen` generates synthetic Hebrew OCR/HTR sample batches with image assets, exact text ground truth, metadata, provenance, and synthetic disclosure. Its output is candidate synthetic input for downstream governance, not a release-ready dataset payload.

`hocrgen` is responsible for dataset governance, release profiles, review, dedupe, privacy, source acquisition, publication, export, and HeOCR handoff.

HeOCR is the public dataset payload and release repository.

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

Persona and condition controls, when added, are generator parameter bundles only. They must not be represented as real identity, medical, psychological, or authorship claims.

## Current Implementation Facts

- The package lives under `src/hocrsyngen/`.
- The current public CLI exposes `templates`, `contracts`, `contracts export`, `generate`, and `validate`.
- The current manifest schema lives at `src/hocrsyngen/schemas/generation_manifest.schema.json`.
- The packaged contract fixture id is `generation_manifest_v1_fixture_batch`.
- The baseline dependencies are `jsonschema` and `Pillow`; test dependencies add `pytest`.

## Future Work

- Expand Hebrew rendering coverage without weakening the existing manifest contract.
- Add richer governed fonts and corpora only with provenance and license records.
- Plan style/persona/condition metadata before adding new manifest semantics.
- Keep optional ML-backed research paths isolated from the baseline package.

## Risks And Open Questions

- Hebrew RTL rendering depends on Pillow libraqm support in the local environment.
- More realistic handwriting may require optional research dependencies that must not contaminate baseline installs.
- Future schema additions need a compatibility plan so `hocrgen` adapters can validate predictably.
