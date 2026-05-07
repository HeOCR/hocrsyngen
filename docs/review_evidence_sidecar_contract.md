# Review Evidence Sidecar Contract

This S6e document defines a portable optional review evidence sidecar contract
for downstream visual and reviewer evidence about `hocrsyngen` candidate
synthetic batches. It is documentation and planning only. It does not add
generator behavior, manifest fields, schemas, packaged fixture changes,
dependencies, `hocrgen` adapter code, review workflow state, release caps,
export behavior, publication behavior, governance enforcement, release
eligibility, or utility claims.

The sidecar lives outside `generation_manifest.json` v1. It is optional
downstream evidence that can cite public `hocrsyngen` identifiers and reports
after a batch has been generated and validated. It is not a release gate by
itself and must not be treated as cap approval, utility proof, export approval,
publication approval, or HeOCR release eligibility.

## Ownership Boundary

`hocrsyngen` may document this sidecar contract and expose stable public ids
that downstream systems can cite:

- manifest v1 sample ids and page ids;
- template id and recipe id;
- `template_catalog.v2` document family and base family joins by
  `(template_id, recipe_id)`;
- degradation preset and font id;
- seed and sample index;
- source corpus;
- persona/style control and condition control;
- optional `rendering_coverage_report.v1` id or path when a coverage report was
  produced.

`hocrgen`/HeOCR own the actual review workflow:

- reviewer assignment and permissions;
- review queue state and reviewer state transitions;
- approval, rejection, hold, and escalation policy;
- thumbnail or visual evidence storage;
- reviewer notes and structured observations;
- privacy, dedupe, leakage, benchmark handling, source-composition, cap,
  release assembly, export, publication, and governance decisions;
- durable storage and access controls for sidecar records.

The sidecar is evidence for downstream governance. It is not governance itself.

## Contract Shape

A review evidence sidecar should be a downstream artifact with a stable id and
explicit version. The recommended contract id is
`review_evidence_sidecar.v1` until `hocrgen` versions a concrete machine schema.

Required top-level fields:

| Field | Requirement | Meaning |
| --- | --- | --- |
| `sidecar_id` | Required | Durable downstream id for this evidence packet. |
| `sidecar_version` | Required | Contract/version string, recommended `review_evidence_sidecar.v1`. |
| `owner_repository` | Required | Repository or system that owns the review record, usually `hocrgen` or HeOCR. |
| `created_at` | Required | Date or timestamp when the packet was recorded. |
| `candidate_batch_id` | Required | Downstream import id, batch id, or explicit batch path used for review. |
| `review_purpose` | Required | Purpose such as dry-run review, utility planning, cap rehearsal, or release-governance review. |
| `hocrsyngen_evidence` | Required | Public `hocrsyngen` ids and reports cited by the packet. |
| `review_scope` | Required | Reviewed sample/page ids and the strata the review claims to cover. |
| `review_decision` | Required | Reviewer state, decision category, reason codes, and limitations. |
| `limitations` | Required | Unreviewed strata, sparse evidence, missing sidecars, unresolved governance dependencies, and claim boundaries. |

Conditionally required fields use explicit paths. Implementations should not
move these fields between top-level and nested objects without versioning the
sidecar contract.

| Field path | Required when |
| --- | --- |
| `visual_evidence` | Any decision beyond `not_reviewed` or `diagnostic_only` cites visual review. |
| `review_decision.reviewer_notes` | A hold, rejection, send-back, or cap-affecting decision is recorded. |
| `review_decision.s6a_acceptance_refs` | The decision uses S6a downstream realism categories or rejection reasons. |
| `review_decision.s6c_warning_refs` | The decision cites diversity, domain-shift, repeated-pattern, or unreviewed-stratum warnings. |
| `review_decision.s6d_cap_decision_refs` | The evidence is used by, or attached to, a downstream cap decision record. |
| `hocrsyngen_evidence.rendering_coverage_report` | The review purpose claims coverage evidence from `rendering_coverage_report.v1`. |
| `review_decision.hold_owner` and `review_decision.unblock_condition` | `review_decision.decision_category` is `hold_for_calibration`. |
| `review_decision.rejection_reason_codes` | The decision category is `reject_for_downstream_release`, `send_back_to_generator_quality`, or `hold_for_calibration`. |

Optional fields:

- reviewer names, team ids, or role ids when downstream governance permits them;
- visual thumbnails, crops, screenshots, or page previews stored downstream;
- structured observations by page region, artifact type, Hebrew readability,
  layout plausibility, degradation, style, condition, or identifier visibility;
- links to downstream review tasks, dashboards, cap records, or utility packets;
- checksums for downstream thumbnail or evidence objects;
- prior sidecar ids when a review packet supersedes or amends earlier evidence.

## Public hocrsyngen Evidence

The sidecar must cite only public `hocrsyngen` identifiers and reports. It must
not inspect private Python recipes, drawing helpers, local filenames,
implementation dataclasses, private package resources, or generated image
layout details that are not exposed through a public contract.

Page references must use manifest v1 page ids exactly as serialized in each
sample's `pages[].page_id`. Current page ids include the sample id prefix, for
example `hocrsyngen-s00000017-000000-page-0001`. Do not shorten them to
`page_0001`, and do not invent compound forms such as
`sample_id/page_0001`. If downstream storage needs a display key, store it as a
separate display field and keep the canonical manifest page id for joins.

Permitted evidence fields:

- `manifest_sample_ids`;
- `manifest_page_ids`;
- `template_id`;
- `recipe_id`;
- `template_catalog_v2_join`, including `document_family` and `base_family`;
- `degradation_preset`;
- `font_id`;
- `seed`;
- `sample_index`;
- `source_corpus`;
- `persona` or style control id from `sample.controls.persona`;
- `condition` control id from `sample.controls.condition`;
- validation report status and path from `hocrsyngen validate PATH --format
  json`;
- generation report, export report, or command string when known;
- optional rendering coverage report id/path and covered/missing summary.

These fields identify what was reviewed. They do not prove realism, utility,
domain match, cap compliance, or release eligibility.

## Review Scope And Coverage

The sidecar should make the review sample explicit enough that downstream
decisions can be audited. At minimum, record:

- reviewed sample ids;
- reviewed page ids;
- review sampling method or selection rationale;
- reviewed strata by document family, base family, template id, degradation
  preset, font id, persona/style control, condition control, source corpus, and
  seed/sample-index range when those dimensions are present;
- unreviewed strata and why they were not reviewed;
- whether the packet covers generator-quality inspection, downstream realism
  acceptance, utility-planning review, cap-rehearsal review, release-governance
  review, or a narrower diagnostic smoke check.

If only a small fixture or smoke batch is reviewed, the limitations must say
that the review does not support broad diversity, utility, cap, domain-shift, or
release claims.

## Decision Vocabulary

Use separate fields for reviewer state, decision category, and reason codes.

Reviewer state values:

| State | Meaning |
| --- | --- |
| `not_reviewed` | The packet records ids or scope, but no visual review decision. |
| `in_review` | Review is open and not final. |
| `reviewed_for_generator_quality` | Pages were checked against the S3 visual inspection rubric. |
| `reviewed_for_downstream_realism` | Pages were checked against the S6a downstream realism rubric. |
| `reviewed_for_cap_rehearsal` | Review evidence is attached to S6d cap decision rehearsal. |
| `reviewed_for_release_governance` | Downstream release governance reviewed the slice. |
| `superseded` | A newer sidecar replaces this evidence packet. |

Decision category values should reuse the S6a vocabulary when downstream
realism is being reviewed:

- `accept_for_dry_run`;
- `eligible_for_utility_evaluation`;
- `hold_for_calibration`;
- `reject_for_downstream_release`;
- `send_back_to_generator_quality`.

For narrower packets, use `diagnostic_only` when the evidence supports only
infrastructure, import, display, or review-system smoke checks.

Reason codes should cite the S6a and S6d vocabularies where applicable. The
sidecar may also retain S6c warning ids such as `single_template_dominance`,
`single_base_family_dominance`, `style_control_skew`,
`condition_control_skew`, `unreviewed_stratum`, or
`synthetic_artifact_repetition`.

## Visual Evidence And Notes

Visual evidence belongs downstream. The sidecar should reference images,
thumbnails, crops, screenshots, or review UI artifacts stored in `hocrgen`,
HeOCR, or another governed downstream evidence store. It should not copy or
modify `hocrsyngen` page assets, and it should not write review metadata into
`generation_manifest.json` v1.

Recommended visual evidence fields:

- evidence id or URI in the downstream evidence store;
- referenced sample id and page id;
- evidence type such as full-page thumbnail, crop, screenshot, comparison panel,
  or reviewer attachment;
- generated page asset path from manifest v1, if needed for traceability;
- downstream thumbnail path or object id;
- optional checksum for the downstream evidence object;
- observation tags such as `hebrew_readability`, `layout_plausibility`,
  `clipping`, `overlap`, `artifact_repetition`, `degradation_legibility`,
  `identifier_visibility`, `style_consistency`, or `condition_effect`;
- concise reviewer notes or structured observations.

Reviewer notes should describe observable synthetic rendering evidence. They
must not assert real identity, authorship, medical condition, psychological
state, disability, sensitive attributes, demographic traits, or real-source
provenance.

## Example Sidecar

This example is illustrative, not a normative JSON schema.

```yaml
sidecar_id: review-heocr-s6dryrun-0004
sidecar_version: review_evidence_sidecar.v1
owner_repository: hocrgen
created_at: 2026-05-08
candidate_batch_id: hocrgen-import:hocrsyngen-batch-17
review_purpose: cap_rehearsal_visual_review
hocrsyngen_evidence:
  hocrsyngen_version: 0.1.0
  generation_command: hocrsyngen generate --count 2 --seed 17 --output out/s6e-dry-run --format json
  validation_report:
    status: valid
    path: reports/hocrsyngen-batch-17-validation.json
  rendering_coverage_report:
    path: reports/hocrsyngen-batch-17-rendering-coverage.json
  public_ids:
    - sample_id: hocrsyngen-s00000017-000000
      page_id: hocrsyngen-s00000017-000000-page-0001
      asset_path: assets/hocrsyngen-s00000017-000000/page_0001.jpg
      template_id: printed_letter
      recipe_id: printed_letter_form_v1
      document_family: printed_letter
      base_family: printed_letter
      degradation_preset: office_scan_soft
      font_id: alef-regular
      seed: 17
      sample_index: 0
      source_corpus: packaged_hebrew_lines_v1
      persona: style_standard_v1
      condition: condition_standard_v1
review_scope:
  reviewed_sample_ids:
    - hocrsyngen-s00000017-000000
  reviewed_page_ids:
    - hocrsyngen-s00000017-000000-page-0001
  reviewed_strata:
    base_family:
      - printed_letter
    persona:
      - style_standard_v1
    condition:
      - condition_standard_v1
  unreviewed_strata:
    - handwritten_note base family not present in reviewed slice
visual_evidence:
  - evidence_id: review-thumb-0004-0001
    sample_id: hocrsyngen-s00000017-000000
    page_id: hocrsyngen-s00000017-000000-page-0001
    evidence_type: full_page_thumbnail
    downstream_object: hocrgen-review-store:review-thumb-0004-0001.jpg
    observation_tags:
      - hebrew_readability
      - layout_plausibility
review_decision:
  reviewer_state: reviewed_for_downstream_realism
  decision_category: hold_for_calibration
  rejection_reason_codes:
    - insufficient_visual_evidence
  hold_owner: hocrgen-review-team
  unblock_condition: review at least one page from each imported base family
  reviewer_notes:
    - printed letter layout is readable, but only one base family was reviewed
  s6a_acceptance_refs:
    - downstream_realism_acceptance_rubric.md#acceptance-categories
  s6c_warning_refs:
    - unreviewed_stratum
  s6d_cap_decision_refs:
    - cap-heocr-s6dryrun-0001
limitations:
  - dry-run review only; no public release approval
  - no governed real-reference utility evaluation was run
  - cap decision remains downstream hocrgen governance
```

## Relationship To S6a, S6c, And S6d

S6e makes earlier S6 review evidence easier to retain and cite:

- S6a provides downstream realism categories, calibrated example classes,
  rejection reasons, and visual evidence expectations.
- S6c provides diversity and domain-shift warnings, including reviewed-stratum
  coverage and unreviewed-stratum risks.
- S6d provides cap decision statuses and reason codes that may cite review
  evidence.

The sidecar should retain references to those packets or reason ids when they
influence a review decision. It must not collapse them into one release
approval. A candidate can be reviewed and still have unmeasured utility,
unmeasured domain shift, missing cap approval, unresolved leakage checks, or no
release eligibility.

## What Belongs Outside hocrsyngen

These belong in `hocrgen`/HeOCR, not in the `hocrsyngen` baseline:

- review queues, assignments, permissions, and reviewer identity handling;
- review state transitions, approvals, holds, rejections, and escalations;
- visual evidence storage, thumbnail generation, screenshots, dashboards, and
  audit retention;
- cap decision records, release profiles, source-composition policy, and cap
  enforcement;
- real-reference benchmark selection, utility evaluation, leakage checks,
  dedupe, privacy review, export, publication, and public dataset payload
  governance;
- machine schema publication if downstream systems choose to implement this
  contract as JSON schema, database records, or API resources.

These may remain in `hocrsyngen`:

- deterministic candidate generation;
- manifest v1 validation and stable public ids;
- public CLI reports;
- `template_catalog.v2` metadata;
- optional `rendering_coverage_report.v1`;
- docs that define evidence boundaries and handoff expectations.

## Relationship To Future S6 Work

`S6f` should define candidate batch profile and mix handoff: how `hocrgen`
requests or records intended template, family, style, condition, degradation,
font, source-corpus, seed, and sample-index mixes before review and cap
decisions interpret a batch.

`S6g` should document the external `hocrgen` adapter checklist for importing
validated candidate batches, retaining public ids, linking optional sidecars,
and applying downstream governance without importing private `hocrsyngen`
internals.

S6e does not require either future item before this contract can be cited as
planning guidance. It simply keeps review evidence portable and outside
manifest v1.
