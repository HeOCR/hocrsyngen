# Testing And Quality

## Commands

```bash
python -m pip install -e ".[test]"
python -m pytest
PYTHONPATH=src python -m hocrsyngen.cli templates
PYTHONPATH=src python -m hocrsyngen.cli contracts --format json
PYTHONPATH=src python -m hocrsyngen.cli generate --count 2 --seed 17 --output out/fixture-batch
PYTHONPATH=src python -m hocrsyngen.cli validate out/fixture-batch --format json
```

There is no configured lint command unless one is added explicitly.

## GitHub Actions CI

The repository CI workflow runs on pull requests and pushes to `main`.

- Test matrix: Ubuntu and macOS runners on Python 3.11 and 3.12.
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
- Packaged fonts and text.
- Visual smoke checks.
- Validation errors.
- Installed package and wheel resource checks.
- Installed package and wheel public CLI smoke matrix for console-script and
  `python -m hocrsyngen.cli` entry points across `templates`, `contracts`,
  `contracts export`, `generate`, and `validate`.
- Baseline dependency audit coverage for declared runtime/test dependencies,
  accidental `hocrgen` imports, network/REST imports, GPU/LLM/diffusion/Torch/
  TensorFlow/deep-learning imports, and docs-to-`pyproject.toml` policy
  alignment.
- Hosted CI coverage for tests, required CLI smoke commands, libraqm availability,
  and package build/install checks.

## Environmental Requirement

Pillow with libraqm support is required for Hebrew RTL rendering. If tests fail because libraqm is missing, report that exact environmental blocker and do not weaken tests.

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
- GitHub Actions CI remains aligned with supported Python versions, required CLI
  smoke commands, and the Pillow libraqm requirement.

## Future Quality Gates

- Bidi and niqqud fixture suite.
- Rendering coverage report.
- Richer degradation coverage.
- Synthetic persona/style consistency checks.
- `hocrgen`-side utility measurement.

## Handling Test Failures

- Do not weaken tests for environment problems.
- Install declared test dependencies with `python -m pip install -e ".[test]"` when dependencies are missing, then rerun tests.
- Record environmental blockers in the PR summary.
- For contract failures, identify whether the schema, fixture, generator, validation behavior, or docs need coordinated updates.
