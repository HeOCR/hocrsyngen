# Downstream Utility Measurement Contract

This S6b document defines how `hocrgen`/HeOCR should measure whether
`hocrsyngen` candidate synthetic batches help or stress OCR/HTR evaluation. It
is documentation and planning only. It does not add generator behavior, manifest
fields, schemas, sidecars, packaged fixture changes, dependencies, `hocrgen`
adapter code, benchmark runners, review workflow state, release caps, export
behavior, publication behavior, or utility claims.

The contract is a handoff boundary. `hocrsyngen` can generate deterministic
candidate batches, validate `generation_manifest.json` v1, expose public CLI
reports, and document what evidence downstream systems must retain. `hocrgen`
and HeOCR own real-reference selection, benchmark eligibility, OCR/HTR model
runs, CER/WER calculation, leakage controls, release decisions, and any public
claims about utility.

## Measurement Questions

Permitted downstream utility questions are narrow and evidence-bound:

- Does adding a reviewed synthetic candidate slice expose OCR/HTR failure modes
  that are also visible in real Hebrew references?
- Does a synthetic candidate slice improve or stress model evaluation when
  compared against a real-reference benchmark with governed ground truth?
- Does performance on synthetic candidates correlate with performance on
  comparable real document families, degradation levels, writing styles, or
  layout classes?
- Does a candidate mix reveal overfitting, brittleness, or robustness gaps
  without changing the real-reference benchmark definition?
- Does a synthetic slice support dry-run evaluation infrastructure before real
  references are available, while making no utility claim?

These questions must be answered in `hocrgen`/HeOCR. A valid `hocrsyngen` batch,
visual inspection pass, downstream realism acceptance category, or dry-run model
run is not enough to claim OCR/HTR utility.

## Layered Gate Model

Keep the gates separate and record which gate a batch has reached.

| Gate | Owner | Required evidence | What it does not prove |
| --- | --- | --- | --- |
| Generator validity | `hocrsyngen` | `hocrsyngen validate PATH --format json` succeeds; assets, hashes, manifest v1, logical-order Hebrew, and governed provenance are valid. | Realism, benchmark eligibility, utility, release eligibility. |
| Generator-quality visual inspection | `hocrsyngen` guidance, human review | Reviewed pages pass [visual_inspection_rubric.md](visual_inspection_rubric.md) for readability, layout coherence, clipping, artifacts, and family plausibility. | Downstream target-domain fit, utility, caps, release eligibility. |
| Downstream realism acceptance | `hocrgen`/HeOCR | S6a category, sampled visual evidence, stable ids, rejection/hold reasons, and target-domain context. | CER/WER validity, benchmark eligibility, release eligibility. |
| Benchmark/reference eligibility | `hocrgen`/HeOCR | Governed real references, ground-truth text, split policy, leakage checks, benchmark definition, and comparison strata. | Utility results, release eligibility. |
| Utility measurement | `hocrgen`/HeOCR | OCR/HTR run records, CER/WER or other metric outputs, metric configuration, reference version, synthetic-to-real comparison, and limitations. | Release eligibility or permission to publish synthetic data. |
| Release eligibility | `hocrgen`/HeOCR | Review workflow, caps, source composition, dedupe, privacy, leakage, benchmark handling, export, publication policy, and release approval. | A new `hocrsyngen` generator contract. |

Utility claims may begin only after the benchmark/reference eligibility and
utility measurement gates are both satisfied. S6a realism acceptance is a
dependency for utility evaluation planning, but it does not replace this S6b
contract.

## Required Downstream Prerequisites

Before making any CER/WER or OCR/HTR utility claim, downstream evaluation must
have:

- a named real-reference benchmark or evaluation set owned by `hocrgen`/HeOCR;
- governed ground-truth text for the real references and a documented text
  normalization policy;
- a split policy that distinguishes train, development, validation, test,
  calibration, review, and release-use roles;
- leakage checks between generated synthetic text, real-reference text, model
  training data, tuning data, and benchmark ground truth;
- the OCR/HTR model, version, configuration, and decoding settings used for the
  run;
- metric definitions for CER, WER, or any alternate utility metric, including
  tokenization and Hebrew normalization decisions;
- synthetic candidate batch provenance from public `hocrsyngen` surfaces:
  validation report, manifest sample ids, template ids, recipe ids, degradation
  presets, font ids, seed/sample indexes, and controls;
- downstream realism acceptance evidence from S6a, including reviewed sample ids
  and page ids;
- synthetic-to-real comparison strata, such as document family, base family,
  degradation level, style/persona control, condition control, layout density,
  and source-domain target;
- a recorded limitation statement when references are sparse, non-comparable, or
  not release-governed.

If any required prerequisite is missing, downstream tools may run infrastructure
or dry-run experiments, but the evidence packet must say that no downstream
utility claim is made.

## CER/WER Boundaries

CER/WER is valid for a downstream OCR/HTR utility claim only when predictions
are compared against governed real ground truth. Synthetic-only CER/WER may be
recorded as diagnostic smoke evidence, but it must not be described as measured
real-world utility.

Invalid CER/WER claims include:

- CER/WER computed only from `hocrsyngen` manifest `text.logical_order` and
  synthetic pages, then described as evidence of real OCR/HTR utility;
- CER/WER from a synthetic-only run with no comparable real-reference baseline;
- CER/WER from references that were used for model training, prompt tuning,
  manual calibration, benchmark design, or synthetic text generation without a
  leakage disclosure and split exclusion;
- CER/WER that mixes real and synthetic references without stratified reporting;
- CER/WER improvements reported without the model version, normalization policy,
  decoding settings, sample counts, and confidence/limitation notes;
- utility claims inferred from `hocrsyngen validate`, visual review, S6a
  acceptance, or rendering coverage alone.

Synthetic-only CER/WER can still be useful as a diagnostic smoke test. It must
be labeled as synthetic diagnostic evidence, not as measured downstream utility.

## Contamination And Leakage Controls

`hocrgen`/HeOCR must prevent synthetic batches from contaminating benchmark
evidence:

- Do not place generated candidate text or page assets into a benchmark test set
  that is later used to claim performance on real data.
- Do not tune OCR/HTR preprocessing, decoding, model selection, thresholds, or
  release caps on the same real-reference split used for final utility claims.
- Do not generate synthetic text from held-out real benchmark transcriptions
  unless the evaluation explicitly excludes that benchmark from claims.
- Keep synthetic dry-run, calibration, development, and test roles distinct.
- Record whether synthetic candidates were used for model training,
  augmentation, robustness probing, benchmark stress testing, or release
  rehearsal; these are different uses with different claim boundaries.
- Report real-only, synthetic-only, and mixed results separately whenever a run
  includes more than one source type.

When leakage cannot be ruled out, downstream systems should mark the result as
diagnostic only and avoid CER/WER utility claims.

## Synthetic-To-Real Comparison

A utility packet should compare synthetic candidates to real references rather
than reporting synthetic numbers in isolation.

Recommended comparisons:

- real-reference baseline CER/WER before adding or evaluating synthetic
  candidates;
- synthetic diagnostic CER/WER by template, base family, degradation preset,
  style/persona, condition, and seed range;
- real-reference CER/WER for comparable document families or target domains;
- mixed-run results with real and synthetic strata reported separately;
- error-type notes for Hebrew-specific issues such as RTL ordering, final forms,
  niqqud, punctuation placement, mixed Hebrew/Latin/numeric text, line wrapping,
  and handwritten-like spacing;
- evidence that a synthetic failure mode corresponds to a real-reference failure
  mode before it is used to justify release or model decisions.

If no comparable real references exist, the only valid conclusion is that
utility remains unmeasured.

## Evidence Packet Fields

Store utility evidence in `hocrgen`/HeOCR systems, not in
`generation_manifest.json` v1. A complete packet should include:

- packet id, owner repository, date, and evaluation purpose;
- source candidate batch path or downstream import id;
- `hocrsyngen` version and public CLI command used to generate or export the
  batch;
- validation report status and path from `hocrsyngen validate PATH --format
  json`;
- manifest sample ids, page ids, template ids, recipe ids, degradation presets,
  font ids, seeds, sample indexes, and controls;
- optional `template_catalog.v2` joined metadata and optional
  `rendering_coverage_report.v1` path when present;
- S6a downstream realism acceptance category, reviewed ids, reviewer notes, and
  any hold or rejection reasons;
- benchmark/reference id, version, source-domain description, ground-truth
  owner, and text normalization policy;
- split role for every real and synthetic source used in the run;
- leakage and contamination check summary;
- OCR/HTR model id, version, configuration, decoder settings, preprocessing,
  and runtime environment when relevant;
- metric definitions, including CER/WER tokenization, normalization, ignored
  characters, and aggregation method;
- real-only, synthetic-only, and mixed results reported separately by stratum;
- confidence notes, sample counts, known limitations, and whether the packet
  permits a utility claim;
- explicit release decision status, if any, recorded separately from utility.

The packet should include this exact boundary when prerequisites are missing:
"No downstream utility claim is made because no governed real-reference
evaluation was run."

## Responsibilities Outside hocrsyngen

These belong in `hocrgen` or HeOCR:

- import adapter implementation and dry-run orchestration;
- real-reference dataset selection and ground-truth stewardship;
- benchmark split policy, leakage checks, and contamination audits;
- OCR/HTR runner orchestration and metric calculation;
- CER/WER reporting, confidence intervals, aggregation, and claims review;
- synthetic-to-real comparison dashboards or reports;
- release profiles, caps, balancing, review workflow, dedupe, privacy,
  release assembly, export, publication, and public dataset payload decisions.

These may remain in `hocrsyngen`:

- deterministic candidate generation;
- manifest v1 validation;
- public CLI reports and packaged fixture export;
- template catalog metadata and optional rendering coverage reports;
- docs that define handoff expectations, quality boundaries, and evidence
  requirements.

## Relationship To S6 Follow-Ups

S6b depends on S6a because downstream utility should not be measured for a
candidate batch that has not passed generator-quality inspection and downstream
realism acceptance for the intended use. S6b does not replace S6a and does not
approve release eligibility by itself.

Later S6 work should build on this boundary:

- `S6c` defines diversity and domain-shift metrics that explain whether
  synthetic candidates cover or distort real-reference distributions in
  [synthetic_diversity_domain_shift_metrics.md](synthetic_diversity_domain_shift_metrics.md).
- `S6d` defines release cap handoff policy so utility evidence does not override
  source composition and synthetic cap decisions in
  [release_cap_handoff_policy.md](release_cap_handoff_policy.md).
- `S6e` defines review evidence sidecars for durable reviewed ids, rejection
  reasons, visual evidence, S6a category references, S6c warning references,
  and S6d cap decision references outside manifest v1 in
  [review_evidence_sidecar_contract.md](review_evidence_sidecar_contract.md).
- `S6f` should define candidate batch profiles and mix handoff so utility
  packets can state what template/style/condition/seed mix was requested.
- `S6g` should document the external `hocrgen` adapter checklist for installed
  CLI import, validation, governance, and dry-run rehearsal.
