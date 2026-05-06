# ADR 0003 — Baseline Dependency Policy

## Status

Accepted

## Context

`hocrsyngen` should be installable and testable as a lightweight deterministic generator. Research paths may eventually need heavier tools, but making them baseline requirements would complicate downstream use and packaging.

## Decision

The baseline stays lightweight. The accepted baseline runtime dependencies are `jsonschema` and `Pillow`; the accepted test extra dependency is `pytest`.

Package metadata declares Python 3.11+ as the source-compatibility floor. CI-supported and tested Python versions are currently 3.11 and 3.12. New Python minor versions should be added to the CI matrix, package classifiers, and support-policy docs together before being described as CI-supported.

It must not add network, GPU, LLM, diffusion, Torch, TensorFlow, or other deep-learning dependencies.

Optional research dependencies must be isolated in future extras, subpackages, experiments, or design documents.

## Consequences

Baseline users can generate and validate synthetic batches without heavyweight compute or network access. Research work must explicitly separate prototypes from production generator dependencies.

## Follow-up

Any proposal for learned generation must include dependency isolation, reproducibility, licensing, and evaluation plans before implementation.
