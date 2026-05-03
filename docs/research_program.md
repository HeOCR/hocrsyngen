# Research Program

This is a planning document only. It does not introduce research code or new generator behavior.

## Motivation

`hocrsyngen` should produce better synthetic Hebrew OCR/HTR samples, especially believable handwritten Hebrew, while supporting `hocrgen` and HeOCR as a bounded synthetic complement to governed dataset releases.

The research program should improve realism and utility without weakening the baseline contract: deterministic candidate batches, explicit provenance, synthetic disclosure, and no heavyweight baseline dependencies.

## Research Tracks

1. Deterministic typography and document simulation baseline.
2. Handwriting-like font and allograph expansion.
3. Character-level and stroke-like perturbation.
4. Word, line, and page assembly realism.
5. Persona-conditioned synthetic writing styles.
6. Condition controls such as fatigue, stress, and concentration as rendering parameters only.
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
- Persona metadata must not claim a real identity or imitate a living person.

## Condition Model Design

- Condition id is a rendering-control bundle.
- Example condition labels: careful, rushed, tired, distracted, formal, cramped.
- Conditions must map to measurable rendering parameters such as spacing, stroke variation proxy, baseline drift, line discipline, degradation, or layout density.
- Conditions must not be represented as mental-state assertions or medical claims.

## Evaluation Plan

- Contract validation for manifest, assets, hashes, JPEG dimensions, and text metadata.
- Visual inspection rubric for Hebrew text plausibility, layout believability, and artifact control.
- OCR/HTR utility once downstream benchmark references exist.
- Diversity metrics across templates, fonts, text, degradation, styles, and layout families.
- Ablation tests for style controls, degradation, and layout changes.
- Synthetic-to-real gap tracking through `hocrgen`/HeOCR benchmarks when available.

## Safety, Legal, And Provenance

- Synthetic disclosure is always present.
- No claims of real authorship.
- No imitation of a living person's handwriting.
- Asset licenses must be tracked.
- Generated data does not bypass `hocrgen` release governance.

## Open Questions

- What minimal metadata is needed before schema v2?
- How should Hebrew handwriting realism be evaluated without enough real reference data?
- How can optional ML generators be exposed without contaminating baseline package dependencies?
- Which style controls are useful to downstream OCR/HTR evaluation rather than merely visually varied?
- How should `hocrgen` cap or stratify synthetic persona/style groups in release profiles?
