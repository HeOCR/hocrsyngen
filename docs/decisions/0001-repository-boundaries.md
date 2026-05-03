# ADR 0001 — Repository Boundaries

## Status

Accepted

## Context

The HeOCR ecosystem needs synthetic Hebrew OCR/HTR sample generation, downstream dataset governance, and public dataset release publication. Combining these responsibilities would blur generator validity with release eligibility and would make integration harder to test.

## Decision

`hocrsyngen` generates candidate synthetic batches. `hocrgen` governs and releases datasets. HeOCR publishes dataset outputs.

`hocrsyngen` must not import `hocrgen`. Integration must use stable CLI, manifest, and contract-fixture boundaries.

## Consequences

`hocrsyngen` can remain small, deterministic, and focused on candidate synthetic generation. `hocrgen` remains the authority for release profiles, review, dedupe, privacy, export, and publication.

Generated batches are not release-ready dataset artifacts by themselves.

## Follow-up

Keep `hocrgen` adapter tests pinned to installed CLI behavior, `generation_manifest.json` v1, and the packaged contract fixture.
