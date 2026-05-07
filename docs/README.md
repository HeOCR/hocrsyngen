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
- [downstream_realism_acceptance_rubric.md](downstream_realism_acceptance_rubric.md): S6a downstream `hocrgen`/HeOCR acceptance categories, calibrated example classes, visual evidence expectations, rejection reasons, and release-eligibility boundaries.
- [downstream_utility_measurement_contract.md](downstream_utility_measurement_contract.md): S6b downstream utility measurement contract for real-reference prerequisites, CER/WER boundaries, leakage controls, evidence packets, and `hocrgen`/HeOCR ownership.
- [synthetic_diversity_domain_shift_metrics.md](synthetic_diversity_domain_shift_metrics.md): S6c synthetic diversity and domain-shift metrics for candidate-batch summaries, repeated-pattern warnings, synthetic-to-real comparison requirements, leakage boundaries, and downstream ownership.
- [release_cap_handoff_policy.md](release_cap_handoff_policy.md): S6d release cap handoff policy for how public `hocrsyngen` metadata and S6a/S6b/S6c evidence support downstream cap decisions without moving caps, source composition, release eligibility, export, publication, or governance enforcement into this repo.
- [review_evidence_sidecar_contract.md](review_evidence_sidecar_contract.md): S6e portable optional downstream review evidence sidecar contract for reviewed sample/page ids, reviewer state, decision categories, reason codes, visual evidence references, S6a category references, S6c warning references, S6d cap decision references, limitations, and unreviewed strata outside manifest v1.
- [candidate_batch_profile_mix_handoff.md](candidate_batch_profile_mix_handoff.md): S6f candidate batch profile and mix handoff contract for requested, generated/observed, reviewed, capped/admitted, and released candidate mix layers, required/preferred/excluded strata, mix gap reason codes, and downstream ownership boundaries outside manifest v1.
- [hocrgen_adapter_handoff_checklist.md](hocrgen_adapter_handoff_checklist.md): S6g external `hocrgen` adapter handoff checklist for installed CLI import, public JSON boundary assertions, manifest id/path retention, `template_catalog.v2` joins, S6a-S6f evidence links, failure handling, and downstream-only governance responsibilities.
- [roadmap.md](roadmap.md): hocrsyngen-specific phases from planning foundation through Hebrew rendering, realism, research, completed S6 evaluation handoffs, and active S7 script-abstraction design planning.
- [research_program.md](research_program.md): planning track for believable synthetic Hebrew handwriting and document generation.
- [handwriting_research_acceptance_criteria.md](handwriting_research_acceptance_criteria.md): S5a boundaries, reproducibility, licensing, visual review, downstream evaluation, and stop/reject gates for handwriting research.
- [allograph_character_prototype_plan.md](allograph_character_prototype_plan.md): S5b deterministic allograph and character-level prototype boundary, bounded sampling plan, Hebrew cases, evidence plan, and proceed/stop gates.
- [word_line_assembly_prototype_plan.md](word_line_assembly_prototype_plan.md): S5c deterministic word and line assembly prototype boundary, spacing/wrapping controls, Hebrew cases, S5b interaction, evidence plan, and proceed/stop gates.
- [learned_generation_packaging_boundary.md](learned_generation_packaging_boundary.md): S5d optional learned-generation packaging boundary for experiments, extras, separate packages, model/data provenance, reproducibility, sidecars, and stop/refuse gates.
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
