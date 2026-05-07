# Documentation Index

This directory holds human-facing design, architecture, specification, roadmap, research, testing, and decision records for `hocrsyngen`.

## Repository Context Files

- [AGENTS.md](../AGENTS.md): static, actionable rules for agents. It should not contain roadmap narrative, current PR state, or task lists.
- [llms.txt](../llms.txt): compact repository sitemap for agents. It should not contain planning narrative or task state.
- [.agent-plan.md](../.agent-plan.md): dynamic immediate execution state and next actions. It should stay short and be updated as active work changes.
- [docs/](./): long-form human-readable architecture, specifications, plans, research notes, testing strategy, and decisions.
- [README.md](../README.md): user-facing entry point. It should link to deeper docs instead of becoming the full planning archive.

## Docs Map

- [repository_scope.md](repository_scope.md): product boundaries between `hocrsyngen`, `hocrgen`, and HeOCR.
- [architecture.md](architecture.md): current module map, data flow, public surfaces, dependencies, failure modes, and extension points.
- [generation_manifest_v1.md](generation_manifest_v1.md): serialized `generation_manifest.json` v1 contract and validation expectations.
- [hocrgen_integration.md](hocrgen_integration.md): stable downstream integration contract for `hocrgen`.
- [production_readiness.md](production_readiness.md): current production-readiness state,
  crucial missing pieces, high-lift quality work, and external `hocrgen`
  dependencies before candidate batches become governed dataset inputs.
- [rendering_coverage_reporting.md](rendering_coverage_reporting.md): design and implemented contract for opt-in Hebrew rendering coverage reports outside manifest v1.
- [layout_metadata_design.md](layout_metadata_design.md): design direction for future document-layout metadata and hocrgen filtering boundaries.
- [document_family_recipes.md](document_family_recipes.md): governed document-family recipes and their current catalog/manifest boundaries.
- [visual_inspection_rubric.md](visual_inspection_rubric.md): human review criteria for S3 layout realism, Hebrew readability, artifacts, and candidate rejection.
- [roadmap.md](roadmap.md): hocrsyngen-specific phases from planning foundation through Hebrew rendering, realism, research, evaluation, and future script abstraction.
- [research_program.md](research_program.md): planning track for believable synthetic Hebrew handwriting and document generation.
- [handwriting_research_acceptance_criteria.md](handwriting_research_acceptance_criteria.md): S5a boundaries, reproducibility, licensing, visual review, downstream evaluation, and stop/reject gates for handwriting research.
- [testing_and_quality.md](testing_and_quality.md): test commands, current coverage, environmental requirements, quality gates, and failure handling.
- [decisions/](decisions/): accepted ADR-style design decisions, including persona/style/condition semantics.
- [decisions/0005-persona-style-condition-semantics.md](decisions/0005-persona-style-condition-semantics.md): normative semantics and forbidden-claim boundaries for synthetic persona, style, and condition controls.

## Suggested Reading Order

1. Start with [README.md](../README.md) for user-facing CLI and fixture examples.
2. Read [repository_scope.md](repository_scope.md) to understand ownership boundaries.
3. Read [architecture.md](architecture.md) and [generation_manifest_v1.md](generation_manifest_v1.md) before changing code or contracts.
4. Read [hocrgen_integration.md](hocrgen_integration.md) before touching downstream adapter assumptions.
5. Read [testing_and_quality.md](testing_and_quality.md) before running or changing tests.
6. Read [roadmap.md](roadmap.md), [production_readiness.md](production_readiness.md), [research_program.md](research_program.md), and [decisions/](decisions/) for planning context.

Coding agents should also read [AGENTS.md](../AGENTS.md), [llms.txt](../llms.txt), and the current [.agent-plan.md](../.agent-plan.md) before editing.
