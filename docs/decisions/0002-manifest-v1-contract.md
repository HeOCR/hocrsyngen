# ADR 0002 — Manifest v1 Contract

## Status

Accepted

## Context

Downstream consumers need a stable serialized representation of generated synthetic batches without depending on Python implementation details.

## Decision

`generation_manifest.json` v1 is the stable serialized contract. The stable public surfaces are the CLI, manifest schema, and packaged contract fixture.

Private Python helpers and dataclasses are not downstream contracts unless future documentation explicitly promotes them.

Schema changes require docs and tests updates. Non-additive changes require versioning or a documented compatibility plan.

## Consequences

Downstream tools can validate manifests and fixture exports consistently. Internal implementation can evolve as long as serialized behavior and documented public surfaces stay compatible.

## Follow-up

Before adding new manifest fields, update `generation_manifest_v1.md`, the JSON schema, validation behavior, and tests together.
