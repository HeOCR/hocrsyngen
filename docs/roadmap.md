# hocrsyngen Roadmap

This roadmap is specific to `hocrsyngen`. It complements `hocrgen` by focusing on deterministic synthetic generation, manifest contracts, validation, rendering quality, and research tracks.

## Current Critical Path

1. Treat Phase S6 as complete through S6g, with S5e closing handwriting
   research by deferral and S3f/S4d remaining the completed capability
   milestones for governed document families and style/condition readiness.
   Together these leave deterministic document families, style, condition,
   degradation, manifest, validation, installed-package CLI contracts, S5
   research gates, allograph plus word/line assembly planning, optional
   learned-generation packaging boundaries, and the S6 downstream evaluation
   and acceptance handoff stack documented.
2. Advance Phase S7 with `S7a` script abstraction design as the current
   planning item. `S7a` is design-only and documented in
   [script_abstraction_design.md](script_abstraction_design.md): it identifies
   minimal future RTL-script abstraction boundaries while preserving
   Hebrew-first behavior, Hebrew RTL/NFC metadata guarantees, manifest v1
   compatibility, and current validation semantics.
3. Keep generated batches classified as candidate synthetic inputs until
   `hocrgen` applies import governance, review, caps, dedupe, release assembly,
   export, and publication policy.
4. Make production-readiness gaps explicit in this roadmap or in a named
   external `hocrgen` dependency. Do not leave required release, review, or
   quality gates only in conversation notes.
5. Keep S5 closed through the deferral path recorded by S5e: this repo has planning
   gates and boundaries, but no accepted prototype or downstream evaluation
   evidence. Remaining S5 prototype/evaluation work is deferred to a future S5
   follow-up or external `hocrgen`/HeOCR work.
6. Keep S6 closed. S6a is complete in PR #48 and defines downstream realism
   acceptance; S6b is complete in PR #49 and defines what evidence is required
   before any CER/WER or other OCR/HTR utility claim is made; S6c is complete
   in PR #50 and defines how to detect repeated synthetic patterns,
   over-representation, and synthetic-to-real comparison gaps before downstream
   dry-runs, utility evaluations, or release planning. S6d is complete in PR
   #51 and defines how public `hocrsyngen` metadata and S6a/S6b/S6c evidence
   feed downstream release cap decisions without moving cap ownership, source
   composition, release eligibility, export, publication, or governance
   enforcement into this repository. S6e is complete in PR #52 and defines an
   optional downstream review evidence sidecar for retaining reviewed
   sample/page ids, reviewer notes, visual evidence references, S6a category
   references, S6c warning references, and S6d cap decision references outside
   manifest v1. S6f is complete in PR #53 and defines optional downstream
   profile/mix evidence for requested, generated/observed, reviewed,
   capped/admitted, and released candidate mixes outside manifest v1. S6g is
   complete in PR #54 and documents the external `hocrgen` adapter checklist
   for installed CLI import, validation, public catalog joins, id retention,
   optional S6a-S6f evidence links, dry-run failure modes, and governance
   boundaries. Remaining adapter implementation and governance work is an
   external `hocrgen` dependency, not active `hocrsyngen` S6 work.

## Current Baseline After S6g

`S6g` - `hocrgen` adapter handoff checklist - is merged in PR #54.
`S6f` - candidate batch profile and mix handoff - is merged in PR #53.
`S6e` - review evidence sidecar contract - is merged in PR #52. `S6d` -
release cap handoff policy - is merged in PR #51. `S6c` - synthetic diversity
and domain-shift metrics - is merged in PR #50. `S6b` - downstream utility
measurement contract - is merged in PR #49. `S6a` - downstream realism
acceptance rubric - is merged in PR #48. `S5e` - close S5 planning and
activate S6 evaluation gates - is merged in PR #47.
The current baseline can generate and validate deterministic candidate batches
through public CLI JSON surfaces, and S5 handwriting research now has
explicit boundaries for reproducibility, provenance, licensing, forbidden
claims, manifest v1 compatibility, visual review, allograph planning,
word/line assembly planning, learned-generation packaging, and stop/reject
gates. This readiness does not make any generated batch release-ready.
`hocrgen` remains the owner of dataset import, release profiles, review, dedupe,
privacy, caps, benchmark handling, release export, and publication.
S6a adds downstream realism acceptance categories, calibrated example classes,
visual evidence expectations, rejection reasons, and the boundary between
generator-quality review and release eligibility. It does not approve utility
claims, benchmark/reference inclusion, release caps, or publication. S6b adds
the downstream utility measurement evidence contract for real-reference
prerequisites, CER/WER boundaries, split and leakage controls, evidence packets,
and `hocrgen`/HeOCR ownership. It does not establish any OCR/HTR utility claim
from this repository. S6c adds candidate-batch diversity summaries,
repeated-pattern warnings, and synthetic-to-real domain-shift evidence
boundaries. It does not establish domain match, cap compliance, release
eligibility, or publication readiness. S6d adds release cap handoff policy for
how public `hocrsyngen` metadata and S6a/S6b/S6c evidence can support downstream
cap records. It does not add cap enforcement, release profiles, source
composition, release eligibility, export, publication, or governance behavior to
this repository. S6e adds an optional downstream review evidence sidecar for
reviewed ids, reviewer state, decision categories, reason codes, visual evidence
references, S6a category references, S6c warning references, S6d cap decision
references, limitations, and unreviewed strata. It does not add review workflow
state, visual evidence storage, release eligibility, export, publication, or
governance behavior to this repository. S6f adds an optional downstream
candidate batch profile and mix handoff for requested, generated/observed,
reviewed, capped/admitted, and released mix layers. It does not add generator
behavior, release profiles, cap enforcement, orchestration, schemas, export,
publication, or governance behavior to this repository. S6g adds an external
`hocrgen` adapter handoff checklist for installed CLI import, validation,
public JSON assertions, `template_catalog.v2` joins, id/path retention, optional
S6a-S6f evidence links, failure handling, and downstream-only governance
responsibilities. It does not add adapter code, schemas, release workflows,
review workflows, caps, export, publication, or governance behavior to this
repository.

Phase S5 closes by deferral rather than evidence: the repository does not
contain accepted S5 prototype/evaluation evidence, ablation results, or
downstream utility measurements. Remaining S5 prototype/evaluation deliverables
are intentionally deferred out of the baseline `hocrsyngen` package. They may
return as a future S5 follow-up only if their dependency, provenance,
reproducibility, visual-evidence, and manifest-boundary gates are satisfied, or
they may be handled externally in `hocrgen`/HeOCR when governed references and
release workflows exist.

The production-readiness plan is tracked in
[production_readiness.md](production_readiness.md). Any future planning update
that identifies a crucial missing production or quality item must either add a
roadmap notation here or record the item as an external `hocrgen` dependency in
that document.

## Planning Notation

Every planned PR should have a notation tied to its roadmap phase. Use the phase letter/number plus a lowercase letter, for example `S2b`. Do not use numeric-only notations; this keeps roadmap notation distinct from GitHub PR numbers.

PR titles should start with the notation, for example `S2b: Add bidi and niqqud rendering fixtures`. If a PR changes scope during implementation, update this roadmap before or inside that PR so the notation remains accurate.

## Phase S0 — Planning And Contract Foundation

Current status: `done`.

Objective: establish the repository's design, boundaries, contract docs, roadmap, and agent context before additional implementation proceeds.

Scope:

- S0a: agent-context architecture and planning docs.
- S0b: clarify public contracts and integration boundaries.
- S0c: guard manifest v1 docs, schema, validation behavior, and fixture expectations against drift.

Planned PR breakdown:

- `S0a` — Planning foundation and agent context. Status: done in PR #17.
- `S0b` — Executable `hocrgen` integration contract tests for installed CLI, fixture export, generation reports, validation reports, and invalid validation JSON. Status: done in PR #19.
- `S0c` — Manifest/schema drift guard: verify `generation_manifest_v1.md`, schema constraints, validation errors, and fixture expectations stay aligned. Status: done in PR #20.
- `S0d` — Roadmap PR notation breakdown and handoff hygiene. Status: done.
- `S0e` — Post-S4d production-readiness roadmap alignment: make crucial
  missing pieces, high-lift quality work, and external `hocrgen` dependencies
  explicit after S4d. Status: done.

Deliverables:

- `AGENTS.md`, `llms.txt`, and `.agent-plan.md`.
- Scope, architecture, manifest, integration, roadmap, research, testing, and ADR docs.
- README documentation links.

Exit criteria:

- Docs are merged without runtime behavior changes.
- Tests still pass or environmental blockers are recorded.
- PR is labeled, non-draft, and contains validation evidence.

Risks/dependencies:

- Planning docs can drift if not updated when contracts change.
- Downstream `hocrgen` assumptions need explicit confirmation.

## Phase S1 — Baseline Deterministic Generator Hardening

Current status: `done`.

Objective: keep the current deterministic printed and handwritten-like templates stable while improving reproducibility and package contract confidence.

Scope:

- Keep current deterministic printed/handwritten-like templates stable.
- Improve documentation, fixture reproducibility, and installed-package contract tests as needed.
- Maintain no-network and no-heavy-dependency baseline.

Planned PR breakdown:

- `S1a` — Fixture reproducibility contract: document and test exact regeneration workflow for the packaged fixture without changing fixture assets unless intentionally regenerated. Status: done in PR #21.
- `S1b` — Installed CLI smoke matrix: strengthen installed-package command coverage for `templates`, `contracts`, `contracts export`, `generate`, and `validate`. Status: done in PR #22.
- `S1c` — Determinism drift guard: add focused tests that compare seed/sample ids, manifest fields, hashes, and output layout expectations for stable seeds. Status: done in PR #23.
- `S1d` — Baseline dependency audit: add or refine tests that fail on accidental `hocrgen`, network, GPU, LLM, diffusion, Torch, TensorFlow, or deep-learning baseline dependencies. Status: done in PR #24.
- `S1e` — GitHub Actions CI framework: run tests, required CLI smoke commands, libraqm checks, and package build/install validation on PRs and pushes to `main`. Status: done in PR #25.
- `S1f` — Python support policy alignment: document the Python 3.11+ metadata floor, CI-supported Python 3.11 and 3.12 versions, and drift guards that keep metadata, CI, and docs aligned. Status: done in PR #26.

Deliverables:

- Clear fixture regeneration procedure.
- Stronger installed-package CLI contract checks if gaps are found.
- Documented expected outputs for baseline commands.

Exit criteria:

- Baseline generation remains deterministic by seed.
- Contract fixture export and validation work from installed package and wheel.
- No baseline dependency expansion beyond lightweight local rendering/validation needs.
- Hosted CI runs the baseline test and packaging gates for supported Python versions.

Risks/dependencies:

- Image output may vary if font rendering stack changes.
- Fixture updates require coordinated docs and tests.
- Hosted runner package availability can affect Pillow libraqm setup.

## Phase S2 — Hebrew Rendering And Text-Quality Hardening

Current status: `done`.

Objective: improve confidence that generated Hebrew text is rendered and represented correctly across important linguistic and layout cases.

Scope:

- Explicit RTL, bidi, NFC, niqqud, and mixed-direction coverage.
- Font-shaping audit.
- More deterministic fixtures for final forms, numerals, punctuation, sparse niqqud, Latin fragments, dates, and identifiers.
- Rendering coverage metadata may be planned, but schema changes require versioned design.

Planned PR breakdown:

- `S2a` — Hebrew edge text corpus fixtures: add deterministic test inputs for final forms, numerals, punctuation, dates, identifiers, and Latin fragments. Status: done in PR #27.
- `S2b` — Bidi and niqqud rendering fixtures: add tests for sparse/full niqqud, mixed-direction text, punctuation placement, and logical-order preservation. Status: done in PR #28.
- `S2c` — Font shaping audit: document and test Pillow/libraqm behavior needed for current packaged fonts and RTL rendering. Status: done in PR #29.
- `S2d` — Rendering coverage report design: define coverage metadata/reporting expectations before any schema-affecting implementation. Status: done in PR #30.
- `S2e` — Rendering coverage report artifact: implement a separate
  `rendering_coverage_report.v1` batch artifact, outside manifest v1, that
  summarizes covered and missing Hebrew rendering dimensions for generated
  candidate batches. Status: done in PR #40.

Deliverables:

- Hebrew rendering fixture suite.
- Font shaping notes and environmental requirements.
- Test cases for logical order and metadata preservation.

Exit criteria:

- Coverage exists for key Hebrew text edge cases.
- Failures clearly distinguish environment issues from generator bugs.
- Any metadata additions have schema/docs/tests coverage.

Risks/dependencies:

- Pillow libraqm availability varies by environment.
- Mixed-direction rendering can expose visual/logical-order ambiguities.

## Phase S3 — Document-Layout Realism

Current status: `done`.

Objective: make synthetic samples resemble believable Hebrew document families while keeping deterministic generation and manifest contracts intact.

Scope:

- More believable Hebrew document families.
- Administrative forms, notebooks, letters, ledgers, classroom-like notes, marginalia, stamps, identifiers, and mixed printed/handwritten overlays.
- Stronger degradation presets.
- Layout metadata and filtering strategy.

Planned PR breakdown:

- `S3a` — Layout metadata design: decide what layout metadata is needed, which future public boundary should expose it, and how `hocrgen` should filter it. Status: done in PR #31.
- `S3b` — Hebrew document family recipes: add the first new governed document family only after S3a settles metadata and validation implications. Status: done in PR #32.
- `S3c` — Degradation preset expansion: add stronger deterministic degradation presets with tests and fixture review guidance. Status: done in PR #33.
- `S3d` — Visual inspection rubric: document human review criteria for layout realism, artifacts, Hebrew readability, and candidate rejection. Status: done in PR #34.
- `S3e` — Richer template catalog metadata: add a versioned public catalog
  surface for document family, base family, page regions, annotation types,
  identifier types, layout density, and review features before any downstream
  code relies on private recipe internals. Status: done in PR #41.
- `S3f` — Additional governed document families: add the next set of realistic
  Hebrew document families, such as ledgers, classroom-like notes, receipts, or
  mixed printed/handwritten overlays, through governed template ids and tests.
  Status: done in PR #42.

Deliverables:

- New documented templates and recipes.
- Visual review rubrics for layout realism.
- Degradation presets with deterministic tests.

Exit criteria:

- Layout additions are governed and reproducible.
- Validation continues to enforce portable assets and provenance.
- `hocrgen` can filter or cap new synthetic families using stable metadata.

Risks/dependencies:

- Layout metadata may require manifest evolution.
- More realism can increase fixture size and review cost.

## Phase S4 — Persona/Style/Condition Controls

Current status: `done`.

Objective: add synthetic style and condition parameter bundles without implying real identity, health, psychology, or authorship.

Scope:

- Synthetic personas as generator parameter bundles, not real identities.
- Style controls: slant, spacing, pressure proxy, baseline drift, character variability, ligature/allograph choices, and line discipline.
- Condition controls: neutral rendering-control presets only; avoid health,
  psychological, disability, sensitive-attribute, or human-state claims.
- Reproducibility and metadata rules.

Planned PR breakdown:

- `S4a` — Persona/style/condition semantics ADR: define allowed metadata, forbidden claims, validation expectations, and compatibility rules before implementation. Status: done in PR #35.
- `S4b` — Deterministic style parameter bundles: implement the smallest synthetic style controls that do not require schema breaking changes. Status: done in PR #36.
- `S4c` — Condition control bundles: add rendering-control-only condition presets after S4a, with tests proving public metadata follows the full forbidden-claims boundary in ADR 0005. Status: done in PR #37.
- `S4d` — Style consistency checks: add tests or reports that verify synthetic style controls are reproducible across a batch. Status: done in PR #38.

Deliverables:

- Metadata semantics before implementation.
- Deterministic parameter bundle definitions.
- Tests for repeatability and disclosure.

Exit criteria:

- Persona, style, and condition controls are documented as synthetic-only.
- Manifest changes, if any, are versioned or additive with tests.
- No real-writer imitation claims are introduced.

Risks/dependencies:

- Ambiguous wording could imply sensitive attributes or real authorship.
- Style consistency may require more detailed validation.

## Phase S5 — Handwriting Research Program

Current status: `done`.

Objective: explore higher-quality Hebrew handwriting synthesis while protecting the lightweight baseline package.

Scope:

- Character/allograph-level synthesis.
- Word/line assembly.
- Per-character and per-line geometric perturbations.
- Writer-style consistency.
- Optional ML-backed synthesis as a separate optional path.
- Evaluation against held-out real Hebrew handwriting through `hocrgen`/HeOCR benchmarks when available.

Planned PR breakdown:

- `S5a` — Handwriting research acceptance criteria: define experiment
  boundaries, reproducibility requirements, licensing constraints, and
  evaluation gates. Status: done in PR #43.
- `S5b` — Allograph and character-level prototype: explore deterministic
  allograph variation outside heavyweight model dependencies. Status: done in
  PR #44; plan tracked in
  [allograph_character_prototype_plan.md](allograph_character_prototype_plan.md).
- `S5c` — Word/line assembly prototype: test geometric perturbation and line
  assembly realism while preserving logical-order ground truth. Status: done in
  PR #45; plan tracked in
  [word_line_assembly_prototype_plan.md](word_line_assembly_prototype_plan.md).
- `S5d` — Optional learned-generation packaging design: design
  extras/subpackages/experiments for ML-backed generation without contaminating
  baseline dependencies. Status: done in PR #46; design tracked in
  [learned_generation_packaging_boundary.md](learned_generation_packaging_boundary.md).
- `S5e` — Close S5 planning and activate S6 evaluation gates: close S5 by
  explicitly deferring remaining prototype/evaluation evidence work out of the
  baseline package, record the post-S5 planning state, and make S6 active.
  Status: done in PR #47.

Deliverables:

- Research prototypes outside baseline dependencies.
- Evaluation notes and ablation results.
- Design proposal for any optional package or extra.

Exit criteria:

- Research paths remain isolated from baseline installs.
- Useful methods have reproducibility, provenance, and evaluation evidence, or
  unresolved prototype/evaluation work is explicitly deferred with a recorded
  reason and follow-up owner. S5 closed by the deferral path because no accepted
  prototype/evaluation evidence exists in this repo.
- Downstream utility can be measured through `hocrgen` when references exist.

Risks/dependencies:

- Lack of sufficient real Hebrew handwriting references may limit evaluation.
- ML-backed approaches can complicate licensing, compute, and reproducibility.

## Phase S6 — Evaluation And Acceptance Gates

Current status: `done`.

Objective: define downstream acceptance, caps, inspection evidence, and utility
measurement before any synthetic batch is considered for release.

Scope:

- Define realism and OCR/HTR utility metrics.
- Downstream acceptance rubrics that build on, but do not replace, the S3
  generator-quality visual inspection checklist.
- CER/WER utility only when ground truth exists downstream.
- Domain shift tracking.
- Synthetic should complement real data and remain capped by `hocrgen` release profiles.

Planned PR breakdown:

- `S6a` — Downstream realism acceptance rubric: define hocrgen/HeOCR
  acceptance categories, calibrated examples, review evidence, and release-gate
  rejection reasons that build on the S3 generator-quality visual inspection
  checklist. Status: done in PR #48; documented in
  [downstream_realism_acceptance_rubric.md](downstream_realism_acceptance_rubric.md).
- `S6b` — Downstream utility measurement contract: document how
  `hocrgen`/HeOCR benchmarks should consume `hocrsyngen` outputs for CER/WER
  only when references exist, how to separate generator validity, realism
  acceptance, benchmark/reference eligibility, utility measurements, and release
  eligibility, and which evidence packet fields are required before utility
  claims. Status: done in PR #49; documented in
  [downstream_utility_measurement_contract.md](downstream_utility_measurement_contract.md).
- `S6c` — Synthetic diversity and domain-shift metrics: define measurable
  candidate-batch diversity, repeated synthetic pattern warnings,
  over-representation signals, and synthetic-to-real gap tracking boundaries.
  Status: done in PR #50; documented in
  [synthetic_diversity_domain_shift_metrics.md](synthetic_diversity_domain_shift_metrics.md).
- `S6d` — Release cap handoff policy: document how public `hocrsyngen`
  metadata, S6a reviewed realism evidence, S6b utility packet ids, and S6c
  diversity/domain-shift packet ids support downstream `hocrgen`/HeOCR release
  cap decisions without moving caps, balancing, source composition, release
  eligibility, export, publication, or governance enforcement into this repo.
  Status: done in PR #51; documented in
  [release_cap_handoff_policy.md](release_cap_handoff_policy.md).
- `S6e` — Review evidence sidecar contract: define a portable optional sidecar
  for reviewed sample ids, page ids, rejection reasons, visual inspection
  evidence, S6a category references, S6c warning references, S6d cap decision
  references, and reviewer workflow boundaries without changing manifest v1.
  Status: done in PR #52; documented in
  [review_evidence_sidecar_contract.md](review_evidence_sidecar_contract.md).
- `S6f` — Candidate batch profile and mix handoff: define how `hocrgen` should
  request or record template/style/condition/seed mixes, synthetic caps, and
  dry-run audit summaries using public `hocrsyngen` metadata. Status: done in
  PR #53;
  documented in
  [candidate_batch_profile_mix_handoff.md](candidate_batch_profile_mix_handoff.md).
- `S6g` — `hocrgen` adapter handoff checklist: document the concrete external
  `hocrgen` implementation dependency for installed CLI import, validation,
  governance, and dry-run rehearsal without adding adapter code to
  `hocrsyngen`. Status: done in PR #54; documented in
  [hocrgen_adapter_handoff_checklist.md](hocrgen_adapter_handoff_checklist.md).
- `S6h` — Close S6 and activate S7 script abstraction: align planning docs so
  Phase S6 is closed after S6g and Phase S7 starts with design-only `S7a`.
  Status: done in PR #55; documentation/planning only.

Deliverables:

- Downstream acceptance and inspection-evidence rubric.
- Utility evaluation plan.
- Domain-shift tracking plan.
- `hocrgen` handoff expectations for caps and profiles.
- Optional review sidecar and batch-profile contract designs.
- External `hocrgen` adapter checklist.

Exit criteria:

- Evaluation distinguishes generator validity from release eligibility.
- Synthetic utility is measured downstream where appropriate.
- Release governance remains in `hocrgen`.

Risks/dependencies:

- Utility metrics can overfit to synthetic artifacts.
- Human realism rubrics need calibration against real references.

## Phase S7 — Script Abstraction / Arabic-Ready Future

Current status: `active`.

Objective: identify abstractions that could support Arabic or other RTL scripts without prematurely generalizing the Hebrew-first implementation.

Scope:

- Keep Hebrew first.
- Identify abstractions needed for future Arabic or other RTL scripts.
- Do not generalize prematurely.
- Avoid breaking Hebrew-specific validation.

Planned PR breakdown:

- `S7a` — Script abstraction design: identify minimal abstractions needed for
  future RTL scripts while preserving Hebrew-specific validation, logical-order
  UTF-8 Hebrew, NFC normalization, RTL metadata, manifest v1 compatibility, and
  current validation semantics. Status: active current planning item,
  design-only in [script_abstraction_design.md](script_abstraction_design.md),
  and must not implement Arabic support.
- `S7b` — Hebrew regression guard: add tests that prevent future script abstraction work from weakening Hebrew RTL/NFC/manifest guarantees.
- `S7c` — Arabic-ready feasibility note: document Arabic-specific shaping, metadata, font, and validation differences without implementing Arabic support.

Deliverables:

- Script abstraction notes.
- Compatibility analysis for manifest metadata.
- Hebrew regression gates before any broader script support.

Exit criteria:

- Hebrew behavior remains stable.
- Any future script work has explicit scope and tests.
- Validation semantics are not diluted.

Risks/dependencies:

- Arabic shaping and text metadata requirements differ from Hebrew.
- Premature generalization could weaken current Hebrew guarantees.
