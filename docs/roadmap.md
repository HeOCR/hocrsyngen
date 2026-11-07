# hocrsyngen Roadmap


## S12d: plain evaluation composition

Proposed opt-in text-only composition keeps original text positions and records its provenance. Its conservative layout flags support screening, not a release or human-gold decision. Default rendering remains unchanged.

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
2. Treat `S7a` script abstraction design as complete. `S7a` is design-only and
   documented in
   [script_abstraction_design.md](script_abstraction_design.md): it identifies
   minimal future RTL-script abstraction boundaries while preserving
   Hebrew-first behavior, Hebrew RTL/NFC metadata guarantees, manifest v1
   compatibility, and current validation semantics. `S7b` and `S7c` remain
   planned but are not the current implementation track.
3. Advance Phase S8 wet-testing and generator-quality evidence. `S8a` defines
   the program in [wet_testing_program_plan.md](wet_testing_program_plan.md),
  `S8b` adds the first reproducible wet-test smoke run artifact generator,
  `S8c` adds the candidate evidence-run wrapper for downstream `hocrgen`
  preflight evidence, `S8d` adds the human-first static gallery over existing
  wet-test runs, `S8e` adds deterministic warning metrics over existing
  wet-test runs, and `S8f` adds a human review worksheet template generator
  and worksheet validator over existing wet-test runs without adding schemas,
  LLM/network dependencies, hocrgen behavior, release governance, or manifest
  v1 changes.
4. Keep generated batches classified as candidate synthetic inputs until
   `hocrgen` applies import governance, review, caps, dedupe, release assembly,
   export, and publication policy.
5. Make production-readiness gaps explicit in this roadmap or in a named
   external `hocrgen` dependency. Do not leave required release, review, or
   quality gates only in conversation notes.
6. Keep S5 closed through the deferral path recorded by S5e: this repo has planning
   gates and boundaries, but no accepted prototype or downstream evaluation
   evidence. Remaining S5 prototype/evaluation work is deferred to a future S5
   follow-up or external `hocrgen`/HeOCR work. Real-glyph composition from
   `HeOCR/hletterscript` is the external path that may eventually answer the
   handwriting-realism question S5 left open; it is tracked under Phase S9,
   not as a reopening of S5.
7. Keep S6 closed. S6a is complete in PR #48 and defines downstream realism
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
8. Treat Phase S9 (real-glyph page composition from `HeOCR/hletterscript`) as
   design-only. `S9a` is documented in
   [real_glyph_composition_plan.md](real_glyph_composition_plan.md) and does
   not implement composer code, change manifest v1, add `hletterscript` or
   `hletterscriptgen` imports, change baseline dependencies, or move downstream
   governance into this repository. Implementation work is gated on
   `hletterscript` reaching a populated, validated baseline corpus.
9. Advance Phase S10 recognizer training-data support for HeOCR's own
   recognizer (`heocr-engine` R3). `S10a` adds the opt-in
   `hocrsyngen_line_annotations.v1` sidecar and `--text-corpus`, documented in
   [line_annotations_v1.md](line_annotations_v1.md), without changing manifest
   v1 or default output bytes. `S10b` adds the project-authored training and
   eval corpora. `S10c` makes page-level gold complete under generator version
   `s10c-gold-complete-v1` (see [CHANGELOG.md](../CHANGELOG.md)).
10. Advance Phase S11 segmentation training-data support for `heocr-engine`
    R4. `S11a` adds region geometry and region reading order to the
    `hocrsyngen_line_annotations.v1` sidecar, without changing page bytes,
    gold, or the manifest.
11. Advance Phase S13 mixed-script training text for the next `heocr-engine`
    recognizer run (R3d). `S13a` adds packaged mixed Hebrew/Latin/digit train
    and eval corpora, documented in
    [mixed_script_text_corpus_card.md](mixed_script_text_corpus_card.md),
    without changing generator code, page bytes for existing corpora, or the
    manifest. `S13b` adds typeset Hebrew train and eval corpora that use em
    and en dashes, geresh and gershayim, typographic quotes and the ellipsis
    (HeOCR/hocrsyngen#87), documented in
    [typographic_text_corpus_card.md](typographic_text_corpus_card.md).

## Current Baseline After S7a

`S7a` - script abstraction design - is merged in PR #56. `S6h` - close S6 and
activate S7 script abstraction - is merged in PR #55.

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

Current status: `open`; `S7a` is done, and `S7b`/`S7c` are planned but not the
current implementation track.

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
  current validation semantics. Status: done in PR #56; design-only in
  [script_abstraction_design.md](script_abstraction_design.md), and must not
  implement Arabic support.
- `S7b` — Hebrew regression guard: add tests that prevent future script abstraction work from weakening Hebrew RTL/NFC/manifest guarantees. Status: planned.
- `S7c` — Arabic-ready feasibility note: document Arabic-specific shaping, metadata, font, and validation differences without implementing Arabic support. Status: planned.

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

## Phase S8 — Wet Testing And Generator-Quality Evidence

Current status: `active`.

Objective: build developer-owned wet-testing evidence for real generated
Hebrew OCR/HTR candidate batches, using deterministic code validation, human
review, optional LLM-assisted triage, and regression promotion while keeping
release governance downstream.

Scope:

- Define smoke, review, and soak wet-test levels.
- Generate reproducible wet-test evidence from existing public generator and
  validation behavior.
- Preserve code, human, and optional LLM evidence outside
  `generation_manifest.json` v1.
- Use human review as the primary qualitative signal.
- Treat LLM triage as optional advisory evidence only.
- Promote confirmed wet-test defects into focused automated regression tests.
- Do not add hocrgen behavior, release governance, export, publication,
  schemas before evidence shapes stabilize, baseline LLM/network dependencies,
  or manifest v1 changes.

Planned PR breakdown:

- `S8a` — Define wet-testing program plan: integrate developer-owned wet
  testing into the roadmap and keep detailed scope, acceptance criteria,
  evidence roles, staged implementation slices, and non-goals in
  [wet_testing_program_plan.md](wet_testing_program_plan.md). Status: done in
  PR #57; documentation/planning only.
- `S8b` — Wet-test smoke run artifact generator: add the first actual
  implementation slice, a small deterministic smoke-run artifact generator that
  reuses existing generation and validation behavior, captures public reports,
  writes `wet_test_run.json`, records report checksums, and avoids schemas,
  galleries, human review sidecars, LLM packets, hocrgen behavior, and manifest
  v1 changes. Status: done in PR #58.
- `S8c` — Candidate evidence-run handoff: add a single operator command that
  captures template/catalog reports, contract fixture export and validation,
  candidate batch generation and validation, rendering coverage, checksums, and
  `candidate_evidence_run_report.v1` for downstream `hocrgen` preflight runs
  while keeping release eligibility false and governance downstream. Status:
  done in PR #59.
- `S8d` — Human-first static gallery: generate a static HTML or Markdown review
  gallery over a wet-test run so developers and reviewers can inspect rendered
  pages, logical Hebrew text, public metadata, and later warnings without
  reading raw JSON. Status: done in PR #60.
- `S8e` — Deterministic warning metrics: add repeatable generator-quality
  warnings for coverage, duplicate text, blank/near-blank images, dimensions,
  ink-density ranges, catalog joins, and path/hash safety without claiming
  realism, utility, or release readiness. Status: done in PR #61.
- `S8f` — Human review sidecar: define and validate review worksheets or
  sidecars for pass/hold/reject decisions, severity, reason codes, notes, and
  regression-promotion flags outside manifest v1. Status: active in the S8f
  implementation PR. The `S8f` slice generates a CSV or JSON Lines human
  review worksheet template from an existing wet-test run, and validates a
  completed worksheet against the run's manifest-derived sample/page ids and
  the documented decision states, severity levels, and reason codes. It does
  not add schemas, LLM triage packets, wet-test reports, regression promotion,
  network/LLM/GPU dependencies, hocrgen behavior, release governance, or
  manifest v1 changes.
- `S8g` — LLM triage packet export: export bounded operator-run LLM review
  packets and prompts without adding baseline LLM clients, network calls, or
  pass/fail authority. Status: done in PR #65.
- `S8h` — Wet-test report: combine run metadata, code warnings, human review,
  optional LLM notes, top examples, and follow-up recommendations into a
  developer-facing generator-quality report with explicit non-release wording.
  Status: done in PR #66.
- `S8i` — Regression promotion and schema/CI decision: promote confirmed
  wet-test findings into small deterministic automated tests, and only then
  decide whether wet-test artifact schemas or a CI smoke profile are stable
  enough to adopt. Status: done in PR #67.
- `S8j` — Evidence-run downstream import readiness: let `evidence-run` select
  governed templates with repeatable `--template-id`, record the resolved
  `template_ids`, and emit the downstream-defined
  `hocrgen_hocrsyngen_provider_runtime.v1` block as
  `candidate_evidence_run_report.provider_runtime` with explicit `false`
  network/REST/GPU/LLM/diffusion flags. This lets `hocrgen
  hocrsyngen-preflight` validate an 80-sample printed/handwritten-like evidence
  root against its release/import model without manifest v1 changes. Release
  eligibility stays `false`; admission, caps, and synthetic target-scale
  closure remain `hocrgen` work. Status: done in PR #72.

Deliverables:

- Developer-owned wet-test run artifact.
- Human-inspectable generated-output gallery.
- Deterministic warning metrics.
- Human review sidecar or worksheet.
- Optional LLM triage packet export.
- Wet-test summary report.
- Regression-promotion process and at least one promoted test.

Exit criteria:

- A smoke wet-test run can be generated and validated deterministically.
- Human reviewers can inspect generated pages without reading raw JSON.
- Code metrics identify likely quality issues without unsupported realism or
  utility claims.
- Human findings are recorded outside manifest v1.
- Optional LLM triage is dependency-light and advisory only.
- At least one real wet-test finding has been promoted into automated
  regression coverage.

Risks/dependencies:

- Overbuilding wet-test infrastructure before evidence shapes stabilize can
  freeze poor artifact contracts.
- Visual metrics can be misleading if treated as realism gates instead of
  warning signals.
- LLM review can create false confidence unless it remains advisory and
  subordinate to human review.
- Large soak runs can become too expensive or noisy for normal CI.

## Phase S9 — Real-Glyph Composition From hletterscript

Current status: `open`; `S9a` is design-only, documented in
[real_glyph_composition_plan.md](real_glyph_composition_plan.md). No `S9` slice
changes `generation_manifest.json` v1 semantics for existing font-rendered
batches.

Objective: define and (later) implement a second deterministic page-composition
substrate that consumes per-writer Hebrew letter-glyph variants from
[`HeOCR/hletterscript`](https://github.com/HeOCR/hletterscript) `letter_set.v1`
sources, while preserving manifest v1 compatibility, the no-network / no-GPU /
no-LLM baseline policy, and downstream governance in `hocrgen`.

Implementation slices are gated on `HeOCR/hletterscript` reaching a populated,
validated baseline corpus. Until that condition is met, only design-only `S9a`
work is appropriate inside this repository. The design direction is documented
in [real_glyph_composition_plan.md](real_glyph_composition_plan.md).

## Phase S10 — Recognizer Training-Data Support

Current status: `open`.

Objective: let candidate batches feed line-level recognizer training (for
example Kraken/ketos runs in `HeOCR/heocr-engine` roadmap R3) through opt-in,
hash-bound artifacts, without changing manifest v1 or default output bytes.

Planned PR breakdown:

- `S10a` — Line annotations sidecar and external text corpora: add
  `--emit-line-annotations` (opt-in `line_annotations.json`,
  `hocrsyngen_line_annotations.v1`, final-page pixel polygons and left-to-right
  baselines mapped through page rotation, `logical_line_index` back-references,
  explicit `logical_join` separators, an `occluded` flag, and drawn text
  outside `logical_order` annotated with `logical_line_index: null`;
  schema plus `validate` checks) and `--text-corpus PATH` (recorded as
  `provenance.source_corpus` `external:sha256:<hex>` and as a run-record
  `text_corpus` block) on `generate` and `evidence-run`. Documented in
  [line_annotations_v1.md](line_annotations_v1.md), including the seed-101
  gold finding. Status: done in PR #73.
- `S10b` — Project-authored training line corpus: a large original Hebrew line
  corpus with a train/eval split, provenance documentation, and corpus checks,
  consumable through `--text-corpus`. Status: done in PR #74.
- `S10c` — Page-level gold completeness: every drawn text element is gold.
  The printed-letter stamp word, the three `אישור` signature captions, and
  the handwritten marginal note join `logical_order` in a documented reading
  order: title, body, stamp, margin, signatures right to left, footer. This
  happens under a `GENERATOR_VERSION` bump to `s10c-gold-complete-v1`
  (recorded in `CHANGELOG.md`; validation still accepts `d4a-realism-v2`) and
  a regenerated packaged fixture manifest. Page images are unchanged.
  - Capacity: printed and handwritten bodies get a computed cap (13–23
    wrapped lines) reported as `truncated_segments`, and an overlong body word
    is rejected, so nothing leaves the page. The archive-card (7) and ledger
    (10) caps are kept and documented.
  - Motivated by the `S10a` seed-101 finding: 200 drawn items (931
    characters) on 80/80 pages were missing from `logical_order`.
  - Stamp occlusion stays as realistic noise, flagged by `occluded`.
  - Seed-101 benchmark (manifest
    `c4b4ca4ed5b92080c0a4d13c4fa2da505080da11b37203ecb0d4fa1bcb164ec3`, pages
    byte-identical to the `d4a-realism-v2` batch):

  | Template | Pages | Gold lines before → after | Scored chars before → after (no spaces) | Added chars |
  |---|---|---|---|---|
  | printed_letter | 20 | 120 → 200 | 3,626 → 4,006 (3,101 → 3,481) | +380 (+10.5%) |
  | printed_letter_heavy_scan | 20 | 120 → 200 | 3,685 → 4,065 (3,147 → 3,527) | +380 (+10.3%) |
  | handwritten_note | 20 | 100 → 120 | 2,830 → 2,915 (2,416 → 2,501) | +85 (+3.0%) |
  | handwritten_note_heavy_wear | 20 | 100 → 120 | 2,798 → 2,884 (2,387 → 2,473) | +86 (+3.1%) |
  | TOTAL | 80 | 440 → 640 | 12,939 → 13,870 (11,051 → 11,982) | +931 (+7.2%) |

  Status: done in PR #75.

Exit criteria:

- A candidate batch can emit validated line geometry whose lines rebuild
  `logical_order` exactly.
- Page-level gold covers every drawn character.
- External corpora are identified by content hash, never by local path.
- Page-level answer keys cover all drawn text.

## Phase S11 — Segmentation Training-Data Support

Current status: `open`.

Objective: let candidate batches train a layout segmenter (for example a
blla-style model from `ketos segtrain`, `HeOCR/heocr-engine` roadmap R4) with
region geometry and region reading order, through the same opt-in, hash-bound
sidecar, without changing page bytes, gold, or the manifest.

Planned PR breakdown:

- `S11a` — Region geometry in the line annotations sidecar. Each page gains a
  `regions` list (`region_index`, `type`, `polygon`, `reading_order_index`,
  `line_indices`), and each line gains a `region_index` back-reference.
  - A region polygon is the padded, rotated box around the region's line text
    boxes and its drawn furniture: stamp ring, ledger table frame, signature
    rule, marginal underline.
  - The three printed-letter signature blocks are separate regions, right to
    left.
  - The change is additive under the same schema id, and `GENERATOR_VERSION`
    is not bumped.
  - The seed-101 evidence batch and a seed-17 seven-template batch are
    byte-identical to `bbcaf0e` apart from the sidecar.
  - Documented in [line_annotations_v1.md](line_annotations_v1.md#regions-s11a).
  - Status: done in PR #76.

Exit criteria:

- Every annotated line belongs to exactly one typed region whose polygon
  contains it, and region reading order agrees with `logical_order`.
- Region annotations never change page bytes or gold.

### S11b — Ledger cell fit (done in PR #78)

Prevent text in generated ledger cells from crossing column boundaries. Reserve
adequate width for numeric balances and reject an external corpus token that
cannot fit in its detail cell; preserve logical text and explicit truncation
reporting. Verify with mixed Hebrew/Latin and wide-token regression fixtures.
The change affects newly generated ledger pixels and does not retroactively
validate earlier batches.


## Phase S12 — Generator quality controls

`S12a` — Add an offline, deterministic quality check for a validated batch
with the line annotations sidecar. Report total and per-template counts of
truncated source segments, occlusion-flagged lines, affected pages and stable
page identifiers, plus the manifest and sidecar SHA-256 hashes. The command
must fail closed when the sidecar is absent or invalid. Optional explicit
nonnegative maximum thresholds cause a nonzero result when exceeded; report
only when omitted. Zero is a valid threshold. Invalid values, including bools
in the Python API, must be rejected. The report is based on recorded
annotations: flags do not establish visibility, correctness, quality acceptance
or release eligibility; schema and hash binding do not authenticate them.
No regeneration, silent filtering, manifest changes or governance behavior.
Status: done in PR #81.

`S12b` — Archive-card detail fit: prevent wide unbreakable body tokens from
crossing into labels, with deterministic mixed-script and width-boundary
regressions. Reject or handle oversized tokens without silently dropping or
misrepresenting rendered text; retain default contract boundaries. This fixes
a reproduced seed-17 body/label overlap. Status: done in PR #80.

`S12c` — Opt-in paired pre-photometric render. Retain the same composed page
and geometric rotation as the existing degraded JPEG, while capturing a PNG
before blur, grain and other photometric degradation. It is not a clean page:
stamps, furniture, stains and other composition marks remain. Bind the optional
pair to the page by hashes in a sidecar and validate it, preserve default output
bytes, and cover reproducibility, same-frame geometry and tampering with
fixture-backed tests. Status: done in PR #82.

S12 pass acceptance: reproduce and prevent the archive overflow; preserve default
JPEG/manifest/text with paired output and verify identical geometry; detect
recorded truncation and occlusion deterministically under user thresholds. Run
regression and full CI plus a 28-page smoke and visual inspection. Results do
not claim real OCR accuracy.

Combined 28-page smoke covered all seven templates with paired and unpaired
outputs: validation passed; manifests, line annotations and 28 JPEGs matched
byte-for-byte. A visual sample per template confirmed corresponding
compositions; this is not a full text audit. The quality check recorded 30
truncated segments and 20 occluded lines; zero ceilings returned nonzero.

## Phase S13 — Mixed-Script Training Text

Current status: `open`.

Objective: give HeOCR's recognizer training text that looks like the
mixed-direction lines of tender-style documents: Hebrew sentences with Latin
words and acronyms, alphanumeric codes, dates, numbers with units,
percentages, currency, reserved-domain emails and URLs, parenthesised English
terms and version strings. The S10b train corpus has Latin in only 382 of
9,359 lines. The corpora are consumed through `--text-corpus` (S10a) and stay
disjoint from every evaluation text, including `hocrgen`'s mixed-script
evaluation fixture (`HeOCR/hocrgen` PR #97).

Planned PR breakdown:

- `S13a` — Mixed-script training and eval corpora:
  `hebrew_mixed_lines_train_v1.txt` and `hebrew_mixed_lines_eval_v1.txt`,
  agent-authored, with a coverage spec, a corpus card, and tests. The tests
  cover leakage against all evaluation text (the `hocrgen` fixture through a
  hash-only fixture pinned at `c8fb74e`), NFC and logical order, the S10b
  no-loss wrapping rule, privacy rules, and minimum coverage per token class.
  No generator code changes. Documented in
  [mixed_script_text_corpus_card.md](mixed_script_text_corpus_card.md).
  Status: done (PR #84).
- `S13b` — Typographic punctuation corpora (#87):
  `hebrew_typographic_lines_train_v1.txt` and
  `hebrew_typographic_lines_eval_v1.txt`, agent-authored typeset Hebrew in
  which em and en dashes, geresh, gershayim, typographic quotes, the ellipsis
  and semicolons occur at realistic rates. The S10b and S13a corpora reject
  these characters and stay byte-identical. Tests cover the same leakage,
  order, wrapping and privacy rules as S13a, plus mark placement, rate bands
  and a glyph check in both packaged fonts. No generator code changes.
  Documented in [typographic_text_corpus_card.md](typographic_text_corpus_card.md).
  Status: in review.

Exit criteria:

- A recognizer run can train on mixed-script lines and evaluate on held-out
  mixed-script lines that share no line or skeleton with train, while train
  shares no line or word 3-gram with any other evaluation text.
- Every corpus token renders inside every template region that receives
  corpus text, with both packaged fonts.

## Phase S15 — Public-Domain Training Text

Current status: `planned`.

Objective: add real public-domain Hebrew text from Project Ben-Yehuda to
recognizer training, under the maintainer decisions in
[ADR 0007](decisions/0007-third-party-public-domain-training-text.md). Text is
an external, pinned corpus passed with `--text-corpus`; `hocrsyngen` stays
network-free and its packaged corpora are unchanged. (`S14a` is already used by
the `s14a-ledger-wrap-v1` generator fix.)

Planned PR breakdown:

- `S15a` — Intake plan: per-entry rights fields (`pd_israel`, `pd_us`, PBY's
  flag, creator death years, first publication year), what the catalogue can
  and cannot fill, text location, a proposed manifest licence value for
  `hocrgen` governance, attribution, real-scan eval exclusion, line-cutting and
  the niqqud split. Documented in
  [pby_public_domain_text_intake_plan.md](pby_public_domain_text_intake_plan.md).
  Docs only. Status: in review.
- `S15b` — Offline intake builder and pinned creator death years, in the
  repository the maintainer picks; emits corpus variants, the rights and line
  indexes, the eval exclusion list and the corpus card.
- `S15c` — Corpus-card input and manifest licence handling, once `hocrgen`
  governance has chosen an option.
- `S15d` — Training ablation in `heocr-engine` with and without PBY lines.

Exit criteria:

- Every PBY line used in training traces to a work with sourced rights fields,
  and `pd_israel` is true for all of them.
- A US-PD variant can be built from the same index without re-reading the dump.
- `hocrgen` can exclude every PBY training work from real-scan evaluation.

## Phase S16 — Real-Glyph Printed Book Pages

Current status: `open`.

Objective: close the real-print gap (CER 0.898 on 38 real scanned printed pages
against 0.020 on font-rendered synthetic pages) by composing training pages
from glyph images cut out of public-domain printed book scans, with exact
gold. The glyph harvester lives in `hocrgen`; `hocrsyngen` reads its output
through a file contract only.

Planned PR breakdown:

- `S16a` — Glyph bank contract `printed_glyph_bank.v1`: index, per-glyph
  records with crop, ink mask, baseline and source x-height, paper patches,
  per-style metrics, rights and leakage rules. Documented in
  [printed_glyph_bank_v1.md](printed_glyph_bank_v1.md), with the JSON schema in
  `src/hocrsyngen/schemas/printed_glyph_bank.schema.json`.
- `S16b` — Composer: `hocrsyngen compose-glyph-pages`, governed template
  `printed_book_glyph_page`, generator version `s16b-glyph-compose-v1`, line
  annotations and the `glyph_provenance.json` sidecar checked by `validate`.
  Documented in [glyph_page_composition.md](glyph_page_composition.md).
  Status: in review.
- `S16c` — Visual review and calibration on a full harvested bank, then an
  `heocr-engine` training ablation with and without composed pages, scored on
  the real printed reference pages.

Exit criteria:

- Composed pages validate, and every line's gold is its placed glyph sequence.
- Every composed page records the bank styles, licences and attribution it
  used.
- A training run that adds composed pages lowers real printed-page CER.
