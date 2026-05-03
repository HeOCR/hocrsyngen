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

## Current Test Coverage

- CLI contracts.
- Generation determinism.
- Manifest schema.
- Hebrew logical-order metadata.
- Packaged fonts and text.
- Visual smoke checks.
- Validation errors.
- Installed package and wheel resource checks.
- No baseline `hocrgen`, network, GPU, or deep-learning dependency.

## Environmental Requirement

Pillow with libraqm support is required for Hebrew RTL rendering. If tests fail because libraqm is missing, report that exact environmental blocker and do not weaken tests.

## Quality Gates

- Deterministic seed behavior.
- Portable relative paths.
- SHA-256 correctness.
- JPEG readability and dimensions.
- NFC text.
- Governed template/provenance match.
- Packaged fixture validity.

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
