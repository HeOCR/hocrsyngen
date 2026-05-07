# Research Program

This is a planning document only. It does not introduce research code or new generator behavior.

## Motivation

`hocrsyngen` should produce better synthetic Hebrew OCR/HTR samples, especially believable handwritten Hebrew, while supporting `hocrgen` and HeOCR as a bounded synthetic complement to governed dataset releases.

The research program should improve realism and utility without weakening the baseline contract: deterministic candidate batches, explicit provenance, synthetic disclosure, and no heavyweight baseline dependencies.

S5 handwriting research must satisfy
[handwriting_research_acceptance_criteria.md](handwriting_research_acceptance_criteria.md)
before moving from planning into prototypes or implementation. Those criteria
define experiment boundaries, reproducibility requirements, licensing
constraints, forbidden claims, manifest v1 compatibility, visual review gates,
downstream evaluation gates, and stop/reject conditions.

The first follow-up S5 direction is planned in
[allograph_character_prototype_plan.md](allograph_character_prototype_plan.md).
It keeps S5b docs-first and defines the prototype location boundary, bounded
sampling plan, deterministic allograph controls, Hebrew-specific cases, asset
provenance rules, visual evidence plan, and criteria for proceeding, holding, or
rejecting the direction.

The S5c follow-up is planned in
[word_line_assembly_prototype_plan.md](word_line_assembly_prototype_plan.md).
It keeps word and line assembly docs-first and defines deterministic spacing,
wrapping, baseline drift, slant, per-line perturbation, Hebrew-specific review
cases, S5b allograph interaction, manifest v1 boundaries, visual evidence, and
proceed/hold/stop gates.

The S5d follow-up is planned in
[learned_generation_packaging_boundary.md](learned_generation_packaging_boundary.md).
It keeps optional learned-generation work docs-first and defines experiment,
extra, subpackage, and separate-package boundaries for ML-backed methods without
contaminating baseline dependencies, manifest v1, packaged fixtures, or default
CLI/test behavior.

S5 is closed by deferral, not by accepted prototype or evaluation evidence. The
S5a through S5d documents define acceptance gates, prototype plans, and
packaging boundaries, but this repository does not contain accepted S5
prototype/evaluation evidence, ablation results, or downstream utility
measurements. Remaining handwriting prototype/evaluation work is intentionally
deferred to a future S5 follow-up or external `hocrgen`/HeOCR work; it should
not be treated as baseline `hocrsyngen` generator behavior.

## Research Tracks

1. Deterministic typography and document simulation baseline.
2. Handwriting-like font and allograph expansion.
3. Character-level and stroke-like perturbation.
4. Word, line, and page assembly realism.
5. Synthetic persona parameter bundles for repeatable generated styles.
6. Condition controls as neutral rendering parameters only.
7. Optional learned generation models as separate optional packages or experiments.
8. Evaluation and domain-shift measurement.

## Hebrew-Specific Issues

- RTL logical vs visual order.
- Final forms.
- Sparse and full niqqud.
- Mixed Hebrew, Latin, and numbers.
- Punctuation placement.
- Line wrapping.
- Baseline and word-spacing behavior.
- Handwriting variability.

## Persona Model Design

- Persona id is a synthetic generator seed/control bundle.
- A persona can define a stable style profile across a batch.
- Topic/register preferences may be used as synthetic corpus controls.
- Document-type preferences may guide template selection.
- Persona metadata must not claim a real identity, demographic profile,
  authorship, provenance, or living-person imitation.

## Condition Model Design

- Condition id is a rendering-control bundle.
- Condition labels should prefer neutral, measurable rendering descriptions over
  human-state labels.
- Conditions must map to measurable rendering parameters such as spacing, stroke
  variation proxy, baseline drift, line discipline, degradation, or layout
  density.
- Conditions must not be represented as mental-state assertions, disability
  claims, sensitive attributes, or medical claims.

The normative semantics for persona, style, and condition controls are recorded
in [ADR 0005](decisions/0005-persona-style-condition-semantics.md). Future
research prototypes should not promote richer control metadata into public
catalog, manifest, or sidecar contracts without a documented compatibility path.

## Evaluation Plan

- Contract validation for manifest, assets, hashes, JPEG dimensions, and text metadata.
- Visual inspection rubric for Hebrew text plausibility, layout believability, and artifact control.
- S5 handwriting-specific acceptance gates for allograph, character, word, and
  line assembly research. Remaining prototype/evaluation evidence is deferred
  unless a future follow-up satisfies the documented S5 gates.
- S6 downstream realism acceptance, review evidence, utility, diversity,
  domain-shift, and cap handoff gates, starting with `S6a`.
- OCR/HTR utility once downstream benchmark references exist.
- Diversity metrics across templates, fonts, text, degradation, styles, and layout families.
- Ablation tests for style controls, degradation, and layout changes.
- Synthetic-to-real gap tracking through `hocrgen`/HeOCR benchmarks when available.

## Safety, Legal, And Provenance

- Synthetic disclosure is always present.
- No claims of real authorship.
- No imitation of a living person's handwriting.
- No medical, psychological, disability, sensitive-attribute, demographic, or
  provenance claims from persona/style/condition controls.
- Asset licenses must be tracked.
- Generated data does not bypass `hocrgen` release governance.
- Research directions must stop when licensing, provenance, reproducibility,
  forbidden-claim, manifest-compatibility, or review-gate criteria are not met.
- Learned-generation directions must also stop when dependency isolation,
  model/data redistribution, automatic-download, network, GPU, baseline
  contamination, or governed real-reference evaluation boundaries are not met.

## Open Questions

- What minimal metadata is needed before schema v2?
- How should Hebrew handwriting realism be evaluated without enough real reference data?
- Which deferred handwriting prototype, if any, should return as a future S5
  follow-up rather than stay external to `hocrsyngen`?
- Which style controls are useful to downstream OCR/HTR evaluation rather than merely visually varied?
- How should `hocrgen` cap or stratify synthetic persona/style groups in release profiles?
