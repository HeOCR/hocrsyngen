# Release Cap Handoff Policy

This S6d document defines how `hocrsyngen` evidence should support downstream
release cap decisions in `hocrgen`/HeOCR without moving release governance into
this repository. It is documentation and planning only. It does not add
generator behavior, manifest fields, schemas, sidecars, packaged fixture
changes, dependencies, `hocrgen` adapter code, benchmark runners, review
workflow state, cap enforcement, release profiles, export behavior, publication
behavior, or release eligibility.

Generated batches remain candidate synthetic inputs. They are not release-ready
payloads, even when they validate, pass generator-quality visual inspection,
receive S6a downstream realism acceptance, have S6b utility evidence, or carry
S6c diversity/domain-shift evidence.

## Ownership Boundary

Release caps are downstream governance policy.

`hocrsyngen` may provide:

- deterministic candidate generation;
- `generation_manifest.json` v1 sample and page identifiers;
- manifest v1 provenance and synthetic control fields;
- public CLI reports;
- `template_catalog.v2` metadata for document family and base family joins;
- optional `rendering_coverage_report.v1` evidence;
- docs that explain which public fields can support downstream decisions.

`hocrgen`/HeOCR own:

- release profile definitions;
- source-composition policy;
- synthetic percentage and absolute caps;
- per-family, per-style, per-condition, per-degradation, or per-source limits;
- reviewer state and release approval;
- balancing, dedupe, privacy, leakage, benchmark handling, export,
  publication, and public dataset payload decisions;
- final reasons for admitting, holding, reducing, or rejecting synthetic
  candidate slices.

No `hocrsyngen` output should be interpreted as cap approval. Downstream systems
may compute cap evidence from public `hocrsyngen` surfaces, but cap decisions
must be recorded in `hocrgen`/HeOCR release governance.

## Cap Evidence From Public hocrsyngen Surfaces

Downstream cap packets should cite only stable public identifiers and reports.
They must not inspect private Python recipes, drawing helpers, filenames,
runtime internals, or generated image layout details that are not exposed
through a public contract.

Permitted `hocrsyngen` evidence includes:

- manifest v1 `sample_id` and `page_id`;
- `sample.provenance.template_id`;
- `sample.provenance.recipe_id` and `sample.recipe_id`;
- `template_catalog.v2` `document_family` and `base_family`, joined by
  `(template_id, recipe_id)`;
- `sample.provenance.degradation_preset`;
- `sample.provenance.font_id`;
- `sample.provenance.seed` and `sample.provenance.sample_index`;
- `sample.provenance.source_corpus`;
- persona/style control from `sample.controls.persona`;
- condition control from `sample.controls.condition`;
- optional `rendering_coverage_report.v1` path and covered/missing dimension
  summary;
- S6a reviewed realism evidence ids and decision category;
- S6b utility evidence packet ids;
- S6c diversity/domain-shift metric packet ids.

These fields are evidence inputs, not policy outputs. A batch can have complete
metadata and still be capped, downweighted, held, or rejected by downstream
release governance.

## Downstream Cap Decision Record

`hocrgen`/HeOCR must retain a cap decision record whenever synthetic candidate
batches are considered for release planning. The record must live outside
`generation_manifest.json` v1.

Minimum required fields:

- cap decision id, owner repository, date, and decision status;
- release profile id and release profile version;
- target release id, domain, or benchmark/rehearsal purpose;
- source candidate batch path or downstream import id;
- `hocrsyngen` version and generation/export command, or an explicit
  `unknown_source_command` limitation when the command cannot be recovered;
- validation report status and path;
- manifest sample ids and page ids admitted, reduced, held, or rejected;
- template id, recipe id, document family, base family, degradation preset,
  font id, seed/sample index range, source corpus, persona/style control, and
  condition control strata for the considered slice;
- source-composition policy, including intended real/synthetic source mix;
- synthetic percentage cap and synthetic absolute-count cap;
- decision status from the S6d decision-status vocabulary below;
- reason codes from the S6d reason-code vocabulary below;
- train/dev/test/review/release split role for real and synthetic sources;
- leakage and benchmark contamination check summary;
- limitations, sparse strata, unreviewed strata, and unresolved governance
  dependencies.

Conditionally required fields:

- per-family, per-base-family, per-template, per-style, per-condition,
  per-degradation, or per-source-corpus limits when the release profile defines
  those stratum caps;
- reviewer state, reviewed sample/page ids, and S6a acceptance or rejection
  references when the decision status is anything beyond `diagnostic_only`;
- S6b utility packet ids when utility evidence is cited, or
  `utility_unmeasured` when no governed real-reference utility packet exists;
- S6c diversity/domain-shift packet ids when diversity, domain shift, or cap
  risk is cited, or `domain_shift_unmeasured` when no governed real-reference
  comparison exists;
- reduction counts and excluded sample/page ids when decision status is
  `admit_reduced`;
- hold owner and unblock condition when decision status is `hold`;
- release approval reference when decision status is `admit_for_release`.

Optional enrichments:

- optional `rendering_coverage_report.v1` path and covered/missing summary;
- thumbnail or reviewed-image references stored in downstream review systems;
- dashboard or report links for S6a, S6b, or S6c evidence packets;
- reviewer names or team ids, if downstream governance permits storing them.

The record must explicitly say when a candidate slice is admitted only for a
dry-run, calibration, utility evaluation, or release rehearsal rather than a
public dataset release.

## Evidence Does Not Override Caps

S6a, S6b, and S6c evidence informs cap decisions. It does not override them.

Use this precedence model:

1. Generator validity from `hocrsyngen validate` is required before downstream
   consideration.
2. S3 generator-quality visual inspection and S6a downstream realism evidence
   can justify dry-run consideration or hold/reject decisions.
3. S6b utility evidence can support a claim that a reviewed synthetic slice
   helps, stresses, or diagnoses OCR/HTR behavior against governed real
   references.
4. S6c diversity/domain-shift evidence can reveal concentration, repeated
   patterns, target-domain gaps, or synthetic-to-real mismatches.
5. `hocrgen`/HeOCR release profile policy still decides whether synthetic
   sources are allowed, how much synthetic data is allowed, which strata are
   capped, and whether a candidate slice is eligible for a governed release.

High realism, useful CER/WER evidence, or broad diversity must not be used to
bypass source-composition caps. Diversity/domain-shift evidence may identify
cap risks, but it does not authorize release eligibility. Utility evidence must
not justify exceeding a release profile's synthetic limit or replacing required
real-source coverage.

## Decision Status And Reason Codes

Downstream systems should separate the decision status from the reason codes.
The decision status says what happened to the candidate slice. Reason codes say
why. These names are planning guidance until `hocrgen` versions a governance
workflow.

Decision status values:

| Status | Meaning |
| --- | --- |
| `diagnostic_only` | The slice may be used for infrastructure, import, or evidence dry-runs only. It is not release eligible. |
| `admit_for_dry_run` | The slice is admitted for non-public dry-run or release-rehearsal use under the stated caps. |
| `admit_for_utility_evaluation` | The slice is admitted for governed utility evaluation, but not for public release by this decision alone. |
| `admit_reduced` | A reduced subset is admitted because the full requested slice would exceed caps or source-composition policy. |
| `hold` | The slice is blocked pending missing review, utility, domain-shift, leakage, profile, or governance evidence. |
| `reject` | The slice must not be used for the target release profile or stated downstream purpose. |
| `admit_for_release` | The slice is admitted to a governed release candidate after downstream release governance has approved it. |

| Reason | Use when |
| --- | --- |
| `within_release_profile_cap` | Candidate slice fits the release profile's synthetic percentage, absolute, and stratum limits. |
| `synthetic_percentage_cap_exceeded` | The requested or imported slice would exceed the release profile's synthetic share. |
| `synthetic_absolute_cap_exceeded` | The candidate count would exceed an absolute synthetic item/page cap. |
| `source_composition_distortion` | Synthetic sources would distort the intended real/synthetic or source-family mix. |
| `family_or_template_cap_exceeded` | A document family, base family, template id, or recipe id would be overrepresented. |
| `style_or_condition_cap_exceeded` | Persona/style or condition controls would overrepresent a synthetic rendering pattern. |
| `degradation_or_font_cap_exceeded` | Degradation preset or font id concentration exceeds downstream policy. |
| `review_evidence_insufficient` | The candidate slice lacks enough reviewed sample/page evidence for the intended use. |
| `utility_evidence_unmeasured` | A utility claim is requested but no governed real-reference S6b packet exists. |
| `domain_shift_unmeasured` | Synthetic-to-real comparison is required but no governed S6c comparison exists. |
| `domain_shift_risk` | S6c evidence shows target-domain mismatch, sparse strata, or repeated synthetic patterns. |
| `leakage_or_contamination_risk` | Split, benchmark, training, calibration, or release-use boundaries are unclear or violated. |
| `governance_dependency_missing` | Review workflow, dedupe, privacy, release assembly, export, or publication gates are not ready. |

Reason records should cite the relevant sample ids, page ids, public provenance
fields, joined catalog fields, review packet ids, utility packet ids, diversity
packet ids, and release profile rule that drove the decision.

## Example Cap Decision Record

This example is illustrative, not a versioned machine schema. A real downstream
record should use `hocrgen`/HeOCR storage and identifiers.

```yaml
cap_decision_id: cap-heocr-s6dryrun-0001
owner_repository: hocrgen
date: 2026-05-08
decision_status: admit_reduced
target_release_id: heocr-synthetic-dry-run-2026q2
release_profile_id: heocr_synthetic_rehearsal_v1
release_profile_version: 1
source_candidate_batch: hocrgen-import:hocrsyngen-batch-17
hocrsyngen_version: 0.1.0
generation_command: hocrsyngen generate --count 40 --seed 17 --output out/s6d-dry-run --format json
validation_report:
  status: valid
  path: reports/hocrsyngen-batch-17-validation.json
included_sample_ids:
  - hocrsyngen-s00000017-000000
  - hocrsyngen-s00000017-000001
excluded_sample_ids:
  - hocrsyngen-s00000017-000018
  - hocrsyngen-s00000017-000019
strata:
  base_family:
    ledger: 10
    archive_card: 10
  persona:
    style_standard_v1: 12
    style_open_drift_v1: 8
  condition:
    condition_standard_v1: 14
    condition_low_contrast_v1: 6
  source_corpus:
    packaged_hebrew_lines_v1: 20
source_composition_policy: max_20_percent_synthetic_for_release_rehearsal
synthetic_percentage_cap: 0.20
synthetic_absolute_count_cap: 20
stratum_caps:
  base_family:
    ledger: 10
    archive_card: 10
  persona:
    style_open_drift_v1: 8
split_roles:
  synthetic: release_rehearsal
  real: review
review:
  state: reviewed_for_rehearsal
  s6a_packet_id: s6a-review-0007
utility:
  state: utility_unmeasured
domain_shift:
  s6c_packet_id: s6c-diversity-0012
  warnings:
    - single_base_family_dominance
leakage_check: no held-out benchmark transcriptions used for generation
reason_codes:
  - within_release_profile_cap
  - source_composition_distortion
  - domain_shift_risk
limitations:
  - dry-run only; no public release approval
  - utility unmeasured against governed real references
```

## Split, Leakage, And Benchmark Contamination

Release cap decisions can affect evaluation integrity. Downstream systems must
keep real and synthetic source roles separate.

Required controls:

- record whether every real and synthetic source is used for training,
  augmentation, dry-run import, calibration, development, review, benchmark,
  release rehearsal, or public release;
- do not tune release caps, template mixes, style mixes, condition mixes,
  degradation selection, OCR/HTR preprocessing, or reviewer thresholds on the
  same held-out real-reference split used for final claims;
- do not let generated text or synthetic pages contaminate real-reference test
  sets that are later used for real-data claims;
- do not generate synthetic text from held-out real benchmark transcriptions
  unless the affected benchmark is excluded from downstream claims;
- report real-only, synthetic-only, and mixed evidence separately in S6b and
  S6c packets;
- mark cap decisions diagnostic only when leakage or split-role boundaries
  cannot be ruled out.

A release profile cap may be strict even when leakage controls pass. Leakage
controls protect evidence integrity; they do not define how much synthetic data
belongs in a public release.

## Relationship To S6a, S6b, And S6c

S6d depends on the earlier S6 planning artifacts:

- S6a realism acceptance supplies reviewed ids, visual categories, and
  rejection or hold reasons that tell downstream release governance whether a
  candidate slice is plausible enough to consider.
- S6b utility measurement supplies packet ids and real-reference evidence that
  state whether OCR/HTR utility has been measured, remains diagnostic, or is
  unmeasured.
- S6c diversity and domain-shift metrics supply concentration warnings,
  reviewed-stratum coverage, and synthetic-to-real comparison evidence that can
  reveal cap risk.

These artifacts are inputs to cap decisions. They do not replace release
profiles, source-composition policy, reviewer approval, dedupe, privacy,
leakage, export, publication, or HeOCR public-release governance.

## Future S6 Follow-Ups

Later S6 items should build on this policy without changing ownership:

- `S6e` review evidence sidecar provides durable reviewed sample/page ids,
  rejection reasons, visual evidence references, S6a category references, S6c
  warning references, and S6d cap decision references that cap decisions can
  cite.
- `S6f` candidate batch profile and mix handoff defines how requested,
  generated/observed, reviewed, capped/admitted, and released
  template/style/condition/seed mixes are recorded before and after caps are
  applied in
  [candidate_batch_profile_mix_handoff.md](candidate_batch_profile_mix_handoff.md).
- `S6g` external `hocrgen` adapter checklist documents how `hocrgen`
  imports, validates, retains evidence, and applies governance without importing
  private `hocrsyngen` internals in
  [hocrgen_adapter_handoff_checklist.md](hocrgen_adapter_handoff_checklist.md).

Any future machine-readable cap decision format belongs in `hocrgen`/HeOCR or a
shared downstream governance contract, not in `generation_manifest.json` v1.
