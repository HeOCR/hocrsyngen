# ADR 0003 — Baseline Dependency Policy

## Status

Accepted

## Context

`hocrsyngen` should be installable and testable as a lightweight deterministic generator. Research paths may eventually need heavier tools, but making them baseline requirements would complicate downstream use and packaging.

## Decision

The baseline stays lightweight. It must not add network, GPU, LLM, diffusion, Torch, TensorFlow, or other deep-learning dependencies.

Optional research dependencies must be isolated in future extras, subpackages, experiments, or design documents.

## Consequences

Baseline users can generate and validate synthetic batches without heavyweight compute or network access. Research work must explicitly separate prototypes from production generator dependencies.

## Follow-up

Any proposal for learned generation must include dependency isolation, reproducibility, licensing, and evaluation plans before implementation.
