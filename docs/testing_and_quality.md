# Testing And Quality

## Commands

```bash
python -m pip install -e ".[test]"
python -m pytest
PYTHONPATH=src python -m hocrsyngen.cli templates
PYTHONPATH=src python -m hocrsyngen.cli contracts --format json
PYTHONPATH=src python -m hocrsyngen.cli generate --count 2 --seed 17 --output out/fixture-batch
PYTHONPATH=src python -m hocrsyngen.cli validate out/fixture-batch --format json
PYTHONPATH=src python -m hocrsyngen.cli wet-run --profile smoke --seed 17 --output out/wet-tests/smoke-17 --format json
PYTHONPATH=src python -m hocrsyngen.cli wet-gallery out/wet-tests/smoke-17 --output out/wet-tests/smoke-17/gallery --format json
```

There is no configured lint command unless one is added explicitly.

## GitHub Actions CI

The repository CI workflow runs on pull requests and pushes to `main`.

- Test matrix: Ubuntu and macOS runners on Python 3.11 and 3.12.
- Package metadata declares Python 3.11+ as the source-compatibility floor.
- CI-supported and tested Python versions are currently 3.11 and 3.12. New Python minor versions should be added to the CI matrix, package classifiers, and support-policy docs together before being described as CI-supported.
- CI installs native Pillow/libraqm/FriBiDi/Harfbuzz build dependencies before Python dependencies through `.github/scripts/install-native-pillow-deps.sh`.
- CI explicitly checks `PIL.features.check("raqm")` and fails with a libraqm requirement message if Hebrew RTL shaping support is unavailable.
- CI installs the package with `python -m pip install -e ".[test]"`.
- CI runs `python -m pytest` and the required CLI smoke commands from this document.
- A separate Ubuntu/Python 3.12 packaging job builds the sdist and wheel, installs the wheel in a clean virtual environment, verifies libraqm support, runs installed `hocrsyngen` CLI smoke commands including `contracts export` plus validation of the exported fixture, and uploads `dist/*` as a workflow artifact.

CI intentionally does not run linting until the repository adopts and documents a lint tool.

## Packaged Fixture Reproducibility

The packaged `generation_manifest_v1_fixture_batch` fixture is the stable contract
fixture for `generation_manifest.json` v1. Its expected regeneration inputs are:

- command: `PYTHONPATH=src python -m hocrsyngen.cli generate --count 2 --seed 17 --output out/fixture-batch`
- seed: `17`
- count: `2`
- sample ids: `hocrsyngen-s00000017-000000`, `hocrsyngen-s00000017-000001`
- template order: `printed_letter`, then `handwritten_note`
- source corpus: `packaged:synthetic/texts/hebrew_lines.txt`

The executable fixture reproducibility contract runs the documented CLI
generation path, compares the stable manifest fields from those inputs against
the packaged fixture, and validates both batches. Exact JPEG `sha256` values can
vary across Pillow/libjpeg/font rendering stacks, so fixture reproducibility
tests mask regenerated image hashes for cross-stack comparison while separately
pinning the committed packaged fixture hashes. The CLI contract tests also check
fixture catalog counts. Packaged fixture assets should only be regenerated when
the existing fixture is proven invalid or a deliberate contract update requires
it.

## Current Test Coverage

- CLI contracts.
- Generation determinism.
- Stable generated-batch drift guards for seed/sample ids, governed manifest
  fields, output layout, and page hash behavior across fixed and changed seeds.
- Manifest schema.
- Hebrew logical-order metadata.
- S2a Hebrew edge text fixture coverage for final forms, numerals, punctuation,
  dates, identifiers, and Latin fragments.
- S2b bidi and niqqud rendering fixture coverage for sparse/full niqqud,
  mixed Hebrew/Latin/numeric fragments, punctuation, rendered-asset smoke, and
  logical-order preservation.
- Packaged fonts and text.
- Visual smoke checks.
- Deterministic degradation preset coverage for stronger governed scan/wear
  variants exposed through the existing template catalog and manifest
  provenance fields, including directional blur/luminance checks plus minimum
  ink, stamp, ruled-region, and marginalia smoke thresholds.
- Deterministic S4b style bundle coverage for `style_standard_v1`,
  `style_open_drift_v1`, and `style_compact_steady_v1` through the existing
  `--persona` control slot, including repeatability, visual-difference smoke
  checks, invalid-control rejection, and forbidden-claim metadata checks.
- S4d batch-level style consistency coverage that verifies fixed-seed style
  profiles are reproducible across repeated generated batches and that
  supported style bundles remain visually distinguishable without manifest v1
  shape changes.
- S2e rendering coverage report coverage for the opt-in
  `rendering_coverage_report.v1` sidecar, including schema shape, covered and
  missing Hebrew rendering dimensions, portable evidence paths, asset smoke
  evidence, installed-package CLI behavior, and preservation of manifest v1.
- S3e `template_catalog.v2` coverage for richer public template metadata,
  including document family, base family, page regions, annotation types,
  identifier types, layout density, review features, schema validation,
  installed-package CLI behavior, JSON-only v2 output, and downstream joins
  from validated manifest template/recipe ids.
- S8b wet-test smoke run coverage for deterministic run artifact creation,
  retained generation/validation/template-catalog reports, portable
  `wet_test_run.json` paths, retained artifact checksums, supplemental
  non-default style/condition batch coverage, optional rendering coverage
  retention, structured failure reports, and preservation of manifest v1.
- S8d static gallery coverage for existing wet-test run artifacts, including
  relative image links, escaped logical Hebrew text and metadata, public
  sample/page/template/style/condition/degradation/font fields, installed-package
  CLI behavior, and preservation of manifest v1.
- S3f governed document-family coverage for the `ledger` template, including
  deterministic generation, manifest v1 provenance, validation acceptance, v1
  and v2 catalog exposure, downstream catalog joins, and visual smoke checks
  for table structure, ink, and synthetic correction marks.
- Deterministic S4c condition bundle coverage for `condition_standard_v1`,
  `condition_low_contrast_v1`, and `condition_dense_spacing_v1` through the
  existing `--condition` control slot, including repeatability,
  visual-difference smoke checks, composition with persona style bundles,
  invalid-control rejection, and forbidden-claim metadata checks.
- Validation errors.
- Installed package and wheel resource checks.
- Installed package and wheel public CLI smoke matrix for console-script and
  `python -m hocrsyngen.cli` entry points across `templates`, `contracts`,
  `contracts export`, `generate`, `validate`, and the operator-only
  `wet-run`, `wet-gallery`, and `evidence-run` wrappers.
- Baseline dependency audit coverage for declared runtime/test dependencies,
  accidental `hocrgen` imports, network/REST imports, GPU/LLM/diffusion/Torch/
  TensorFlow/deep-learning imports, and docs-to-`pyproject.toml` policy
  alignment.
- Hosted CI coverage for tests, required CLI smoke commands, libraqm availability,
  and package build/install checks.

## Manual Inspection Guidance

S3 human visual inspection guidance is documented in
[visual_inspection_rubric.md](visual_inspection_rubric.md). It covers layout
realism, Hebrew readability, artifacts, clipping, overlap, degradation
acceptability, inspectability of stamps/identifiers/marginalia/ruled regions,
and candidate rejection notes.

This guidance is not automated test coverage and is not a CI gate. It is a
manual review aid for generator-quality spot checks until any future review
sidecar or downstream acceptance workflow is explicitly designed.

S6 downstream realism acceptance guidance is documented in
[downstream_realism_acceptance_rubric.md](downstream_realism_acceptance_rubric.md).
It classifies candidate batches for downstream `hocrgen`/HeOCR dry runs,
benchmark experiments, holds, and release rejection after generator-quality
inspection has passed. It is not automated test coverage and does not create a
CI gate, manifest field, sidecar, release cap, or review workflow in this repo.

S6 downstream utility measurement guidance is documented in
[downstream_utility_measurement_contract.md](downstream_utility_measurement_contract.md).
It requires downstream real references, governed ground truth, split/leakage
controls, metric definitions, OCR/HTR run records, and synthetic-to-real
comparison before CER/WER or other utility claims are made. It is not automated
test coverage in this repo and does not add a benchmark runner, manifest field,
sidecar, dependency, release cap, adapter code, or CI gate to `hocrsyngen`.

S6 synthetic diversity and domain-shift guidance is documented in
[synthetic_diversity_domain_shift_metrics.md](synthetic_diversity_domain_shift_metrics.md).
It defines descriptive diversity summaries, repeated-pattern warnings, and
downstream real-reference comparison requirements. It is not automated test
coverage in this repo and does not add a metrics runner, manifest field,
sidecar, dependency, release cap, adapter code, benchmark runner, export
behavior, or CI gate to `hocrsyngen`.

S6 release cap handoff guidance is documented in
[release_cap_handoff_policy.md](release_cap_handoff_policy.md). It defines how
public `hocrsyngen` metadata and S6a/S6b/S6c evidence can support downstream cap
records while keeping cap decisions, source composition, release eligibility,
export, publication, and governance enforcement in `hocrgen`/HeOCR. It is not
automated test coverage in this repo and does not add cap enforcement, release
profiles, manifest fields, sidecars, dependencies, adapter code, export
behavior, publication behavior, or CI gates to `hocrsyngen`.

S6 review evidence sidecar guidance is documented in
[review_evidence_sidecar_contract.md](review_evidence_sidecar_contract.md). It
defines optional downstream evidence packets for reviewed sample/page ids,
reviewer state, decision categories, reason codes, visual evidence references,
reviewer notes, S6a category references, S6c warning references, S6d cap
decision references, limitations, and unreviewed strata. It is not automated
test coverage in this repo and does not add review workflow state, manifest
fields, schemas, dependencies, adapter code, export behavior, publication
behavior, release eligibility, or CI gates to `hocrsyngen`.

S6 candidate batch profile and mix handoff guidance is documented in
[candidate_batch_profile_mix_handoff.md](candidate_batch_profile_mix_handoff.md).
It defines optional downstream planning records for requested,
generated/observed, reviewed, capped/admitted, and released candidate mixes,
including required/preferred/excluded strata and mix gap reason codes. It is not
automated test coverage in this repo and does not add generator behavior,
manifest fields, schemas, dependencies, adapter code, orchestration, cap
enforcement, release profiles, export behavior, publication behavior, release
eligibility, or CI gates to `hocrsyngen`.

S6 external `hocrgen` adapter handoff guidance is documented in
[hocrgen_adapter_handoff_checklist.md](hocrgen_adapter_handoff_checklist.md).
It defines installed CLI commands, public JSON boundary assertions, import-flow
checks, evidence links, failure handling, and downstream-only responsibilities.
It is not automated test coverage in this repo and does not add adapter code,
manifest fields, schemas, dependencies, orchestration, review workflow, release
profiles, cap enforcement, export behavior, publication behavior, release
eligibility, or CI gates to `hocrsyngen`.

## Environmental Requirement

Pillow with libraqm support is required for Hebrew RTL rendering. If tests fail because libraqm is missing, report that exact environmental blocker and do not weaken tests.

For Hebrew rendering tests, Pillow must be built with libraqm enabled so that
Pillow can route bidirectional layout and OpenType shaping through the native
libraqm stack, including FriBiDi for bidirectional ordering and Harfbuzz for
glyph shaping. The generator keeps manifest text in logical-order NFC Hebrew
and passes that logical text to Pillow with `direction="rtl"`; it must not
pre-reverse text or bypass the shared RTL drawing path. Font shaping audit
coverage exercises both packaged font styles, `alef-regular` for printed
documents and `gveret-levin-regular` for handwritten-like documents, against
representative Hebrew, niqqud, mixed Hebrew/Latin/numeric fragments, and
punctuation. These tests use non-empty bounding boxes and coarse ink-pixel
checks instead of exact image hashes because raster output can vary across
Pillow, FreeType, libraqm, Harfbuzz, FriBiDi, and platform font stacks.

## Quality Gates

- Deterministic seed behavior.
- Stable generated-batch manifest identity and output layout for governed seeds.
- Portable relative paths.
- SHA-256 correctness.
- JPEG readability and dimensions.
- NFC text.
- Governed template/provenance match.
- Packaged fixture validity.
- Packaged fixture stable-field reproducibility from seed `17` and count `2`.
- Baseline dependency policy remains aligned across source imports,
  `pyproject.toml`, and dependency-policy docs.
- GitHub Actions CI remains aligned with CI-supported Python versions, package
  metadata, required CLI smoke commands, and the Pillow libraqm requirement.
- Rendering coverage reports remain opt-in sidecars outside
  `generation_manifest.json` v1 and keep evidence paths portable.

## Future Quality Gates

- Review sidecar artifacts for visual inspection evidence should follow the S6e
  contract and remain downstream optional evidence outside
  `generation_manifest.json` v1 unless a versioned schema update is designed.
- Candidate batch profile and mix records should follow the S6f contract and
  keep requested, generated/observed, reviewed, capped/admitted, and released
  layers separate outside `generation_manifest.json` v1.
- External `hocrgen` adapter tests should follow the S6g checklist and assert
  installed CLI JSON reports, manifest validation, relative path retention,
  `template_catalog.v2` joins, optional rendering coverage, and S6a-S6f
  evidence links at downstream boundaries.
- S7a script abstraction planning in
  [script_abstraction_design.md](script_abstraction_design.md) defines Hebrew
  regression expectations before implementation work starts. Future script
  abstraction tests must not weaken logical-order UTF-8 Hebrew, NFC
  normalization, RTL metadata, manifest v1 compatibility, or current validation
  semantics.
- Additional synthetic persona/style/condition consistency reports governed by
  [ADR 0005](decisions/0005-persona-style-condition-semantics.md), beyond the
  automated S4 style consistency checks now covered in the test suite.
- `hocrgen`-side utility measurement based on the S6b contract.
- `hocrgen`-side diversity and domain-shift evidence based on the S6c contract.
- `hocrgen`-side downstream realism acceptance workflow based on the S6a rubric.
- `hocrgen`-side release cap records and enforcement based on the S6d handoff
  policy.

## Handling Test Failures

- Do not weaken tests for environment problems.
- Install declared test dependencies with `python -m pip install -e ".[test]"` when dependencies are missing, then rerun tests.
- Record environmental blockers in the PR summary.
- For contract failures, identify whether the schema, fixture, generator, validation behavior, or docs need coordinated updates.
