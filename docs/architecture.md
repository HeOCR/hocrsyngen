# Architecture

## Module Map

- `assets.py`: resolves packaged font, text, schema, and contract fixture resources.
- `io.py`: reads simple packaged manifests and computes file hashes.
- `manifest.py`: defines manifest constants and dataclasses for text metadata, page assets, provenance, controls, samples, and manifests.
- `generator.py`: loads governed fonts/text, resolves templates, renders deterministic page images, applies degradation, writes JPEGs, and assembles manifests.
- `validation.py`: validates generated batch directories, manifest schema, constants, text metadata, relative paths, SHA-256 hashes, and JPEG integrity.
- `cli.py`: exposes public commands and deterministic text/JSON reports.
- `schemas/`: contains `generation_manifest.schema.json`.
- `data/synthetic/`: contains governed fonts, font licenses, font manifest, and Hebrew text corpus.
- `data/contracts/`: contains packaged contract fixture batches for downstream integration tests.
- `tests/`: covers CLI contracts, generation behavior, validation behavior, installed-package resources, and wheel packaging resources.

## Data Flow

1. Load governed font manifest and text corpus.
2. Resolve template recipe.
3. Render deterministic page image.
4. Save relative JPEG asset.
5. Compute SHA-256.
6. Create `GenerationManifest` dataclasses.
7. Write `generation_manifest.json`.
8. Validate schema, constants, text metadata, relative paths, hashes, and JPEG dimensions.

## Current Public Surfaces

- CLI commands: `hocrsyngen templates`, `hocrsyngen contracts`, `hocrsyngen contracts export`, `hocrsyngen generate`, and `hocrsyngen validate`.
- `generation_manifest.json` v1.
- Packaged contract fixture `generation_manifest_v1_fixture_batch`.

## Stable Vs Internal Surfaces

Treat the CLI, manifest schema, and contract fixture as stable downstream surfaces. Treat private helpers and dataclasses as implementation details unless a future document explicitly promotes them to public API.

`hocrgen` should validate serialized manifests and fixture exports. It should not import private `hocrsyngen` Python internals.

## Dependency Model

- Package metadata declares Python 3.11+ as the source-compatibility floor.
- CI-supported and tested Python versions are currently 3.11 and 3.12. New Python minor versions should be added to the CI matrix, package classifiers, and support-policy docs together before being described as CI-supported.
- `jsonschema` for manifest schema validation.
- `Pillow` for image rendering and JPEG inspection.
- Pillow libraqm support is required for Hebrew RTL rendering.
- No baseline network, REST, GPU, LLM, diffusion, Torch, TensorFlow, or other heavyweight generative-model dependencies.

## Failure Modes

- Missing or invalid fonts.
- Missing text corpus.
- Missing Pillow libraqm support.
- Malformed manifest JSON.
- Manifest schema violations.
- Non-portable asset paths, including absolute paths, backslashes, or `..`.
- SHA-256 mismatch.
- Unreadable, truncated, or non-JPEG asset.
- JPEG dimensions that do not match the manifest.
- Non-NFC logical text.
- Provenance that does not match the governed template catalog.

## Extension Seams

- New templates and recipes.
- New governed fonts with provenance and license documentation.
- Richer Hebrew text corpora.
- Richer degradation presets.
- Future persona, style, and condition controls as synthetic parameter bundles.
- Future optional model-backed generation outside the baseline package.

## Current Risks And Open Questions

- More realistic Hebrew handwriting may require new metadata semantics before generator work begins.
- Additional layout metadata could affect manifest compatibility and may require versioned design.
- Font shaping coverage should be audited before broadening script or mixed-direction support.
