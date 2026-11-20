# ADR 0004 — Agent Context Separation

## Status

Accepted

## Context

Agents need static instructions, compact repository maps, current task state, and long-form planning context. Mixing these into one file makes instructions stale and hard to scan.

## Decision

`AGENTS.md` contains static rules. `llms.txt` contains a compact sitemap. `.agent-plan.md` contains dynamic current state. `docs/` contains long-form planning, specifications, architecture, and decisions. `README.md` remains the user-facing entry point.

## Consequences

Agents can quickly find the right level of context without confusing dynamic task state for durable project policy.

## Follow-up

Keep `.agent-plan.md` updated during active work, and move durable decisions into `docs/decisions/` instead of expanding agent instructions.
