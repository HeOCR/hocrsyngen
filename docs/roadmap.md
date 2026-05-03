# hocrsyngen Roadmap

This roadmap is specific to `hocrsyngen`. It complements `hocrgen` by focusing on deterministic synthetic generation, manifest contracts, validation, rendering quality, and research tracks.

## Current Critical Path

1. Merge this planning/agent-context PR.
2. Confirm `hocrgen` integration contract with fixture export and validation.
3. Add Hebrew rendering/spec coverage docs/tests before deeper generator changes.
4. Add style/persona controls only after manifest/metadata semantics are explicit.
5. Keep optional ML-backed synthesis separate from baseline dependencies.

## Phase S0 — Planning And Contract Foundation

Current status: `current`.

Objective: establish the repository's design, boundaries, contract docs, roadmap, and agent context before additional implementation proceeds.

Scope:

- S0a: agent-context architecture and planning docs.
- S0b: clarify public contracts and integration boundaries.
- S0c: document manifest v1 and validation behavior.

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

Current status: `planned`.

Objective: keep the current deterministic printed and handwritten-like templates stable while improving reproducibility and package contract confidence.

Scope:

- Keep current deterministic printed/handwritten-like templates stable.
- Improve documentation, fixture reproducibility, and installed-package contract tests as needed.
- Maintain no-network and no-heavy-dependency baseline.

Deliverables:

- Clear fixture regeneration procedure.
- Stronger installed-package CLI contract checks if gaps are found.
- Documented expected outputs for baseline commands.

Exit criteria:

- Baseline generation remains deterministic by seed.
- Contract fixture export and validation work from installed package and wheel.
- No baseline dependency expansion beyond lightweight local rendering/validation needs.

Risks/dependencies:

- Image output may vary if font rendering stack changes.
- Fixture updates require coordinated docs and tests.

## Phase S2 — Hebrew Rendering And Text-Quality Hardening

Current status: `planned`.

Objective: improve confidence that generated Hebrew text is rendered and represented correctly across important linguistic and layout cases.

Scope:

- Explicit RTL, bidi, NFC, niqqud, and mixed-direction coverage.
- Font-shaping audit.
- More deterministic fixtures for final forms, numerals, punctuation, sparse niqqud, Latin fragments, dates, and identifiers.
- Rendering coverage metadata may be planned, but schema changes require versioned design.

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

Current status: `future`.

Objective: make synthetic samples resemble believable Hebrew document families while keeping deterministic generation and manifest contracts intact.

Scope:

- More believable Hebrew document families.
- Administrative forms, notebooks, letters, ledgers, classroom-like notes, marginalia, stamps, identifiers, and mixed printed/handwritten overlays.
- Stronger degradation presets.
- Layout metadata and filtering strategy.

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

Current status: `future`.

Objective: add synthetic style and condition parameter bundles without implying real identity, health, psychology, or authorship.

Scope:

- Synthetic personas as generator parameter bundles, not real identities.
- Style controls: slant, spacing, pressure proxy, baseline drift, character variability, ligature/allograph choices, and line discipline.
- Condition controls: concentration/fatigue/stress-like rendering controls only; avoid psychological truth claims.
- Reproducibility and metadata rules.

Deliverables:

- Metadata semantics before implementation.
- Deterministic parameter bundle definitions.
- Tests for repeatability and disclosure.

Exit criteria:

- Persona and condition controls are documented as synthetic-only.
- Manifest changes, if any, are versioned or additive with tests.
- No real-writer imitation claims are introduced.

Risks/dependencies:

- Ambiguous wording could imply sensitive attributes or real authorship.
- Style consistency may require more detailed validation.

## Phase S5 — Handwriting Research Program

Current status: `future`.

Objective: explore higher-quality Hebrew handwriting synthesis while protecting the lightweight baseline package.

Scope:

- Character/allograph-level synthesis.
- Word/line assembly.
- Per-character and per-line geometric perturbations.
- Writer-style consistency.
- Optional ML-backed synthesis as a separate optional path.
- Evaluation against held-out real Hebrew handwriting through `hocrgen`/HeOCR benchmarks when available.

Deliverables:

- Research prototypes outside baseline dependencies.
- Evaluation notes and ablation results.
- Design proposal for any optional package or extra.

Exit criteria:

- Research paths remain isolated from baseline installs.
- Useful methods have reproducibility, provenance, and evaluation evidence.
- Downstream utility can be measured through `hocrgen` when references exist.

Risks/dependencies:

- Lack of sufficient real Hebrew handwriting references may limit evaluation.
- ML-backed approaches can complicate licensing, compute, and reproducibility.

## Phase S6 — Evaluation And Acceptance Gates

Current status: `future`.

Objective: define how synthetic batches are accepted, capped, inspected, and measured before downstream release consideration.

Scope:

- Define realism and OCR/HTR utility metrics.
- Human inspection rubrics.
- CER/WER utility only when ground truth exists downstream.
- Domain shift tracking.
- Synthetic should complement real data and remain capped by `hocrgen` release profiles.

Deliverables:

- Visual inspection rubric.
- Utility evaluation plan.
- Domain-shift tracking plan.
- `hocrgen` handoff expectations for caps and profiles.

Exit criteria:

- Evaluation distinguishes generator validity from release eligibility.
- Synthetic utility is measured downstream where appropriate.
- Release governance remains in `hocrgen`.

Risks/dependencies:

- Utility metrics can overfit to synthetic artifacts.
- Human realism rubrics need calibration against real references.

## Phase S7 — Script Abstraction / Arabic-Ready Future

Current status: `future`.

Objective: identify abstractions that could support Arabic or other RTL scripts without prematurely generalizing the Hebrew-first implementation.

Scope:

- Keep Hebrew first.
- Identify abstractions needed for future Arabic or other RTL scripts.
- Do not generalize prematurely.
- Avoid breaking Hebrew-specific validation.

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
