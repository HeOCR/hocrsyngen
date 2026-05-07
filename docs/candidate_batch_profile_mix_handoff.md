# Candidate Batch Profile And Mix Handoff

This S6f document defines a candidate batch profile and mix handoff contract for
downstream dry-runs, review, cap rehearsal, utility planning, and release
planning. It is documentation and planning only. It does not add generator
behavior, manifest fields, schemas, packaged fixture changes, dependencies,
`hocrgen` adapter code, orchestration, review workflow state, release caps,
export behavior, publication behavior, governance enforcement, release
eligibility, or utility claims.

The profile lives outside `generation_manifest.json` v1. It is optional
downstream planning evidence that can state what mix was requested, what mix was
generated or observed, what was reviewed, what was capped or admitted, and what
was eventually released by downstream governance. It is not a release profile,
not a generator contract, and not approval to publish synthetic data.

## Ownership Boundary

`hocrsyngen` may document stable dimensions and public ids that downstream
systems can cite:

- manifest v1 sample ids and page ids, exactly as serialized;
- template id and recipe id;
- `template_catalog.v2` document family and base family joins by
  `(template_id, recipe_id)`;
- degradation preset;
- font id;
- seed and sample index range;
- source corpus;
- persona/style control from `sample.controls.persona`;
- condition control from `sample.controls.condition`;
- optional `rendering_coverage_report.v1` id or path;
- optional S6a downstream realism evidence references;
- optional S6c diversity/domain-shift warning references;
- optional S6d cap decision references;
- optional S6e review evidence sidecar references.

`hocrgen`/HeOCR own downstream behavior and policy:

- candidate-batch orchestration and batch planning;
- balancing, source composition, synthetic percentage caps, absolute caps, and
  stratum caps;
- release profiles and release eligibility;
- import ids, batch ids, dry-run records, review queues, review workflow state,
  reviewer assignment, and visual evidence storage;
- utility evaluations, benchmark/reference selection, split policy, leakage
  checks, dedupe, privacy review, release assembly, export, publication, and
  governance enforcement;
- final admission, reduction, hold, rejection, or publication decisions.

A profile can cite `hocrsyngen` evidence. It must not make `hocrsyngen` the
owner of downstream orchestration or release governance.

## Contract Purpose

The profile/mix handoff answers four narrow questions:

1. What synthetic candidate mix did downstream planning request or intend?
2. What mix was actually generated, imported, or observed from public
   `hocrsyngen` surfaces?
3. Which parts of that mix were reviewed, capped, admitted, held, or rejected?
4. Which gaps, limitations, and downstream dependencies remain before the mix
   can support broader dry-run, utility, domain-shift, cap, or release claims?

The profile should be durable enough for audit, but it is planning guidance
until `hocrgen` versions a concrete machine schema. It should be stored in
`hocrgen`/HeOCR records or future downstream sidecars, not in manifest v1.

## Profile Layers

Do not collapse requested, observed, reviewed, capped, and released state into a
single "approved mix" field. They answer different questions and have different
owners.

| Layer | Owner | Meaning | Valid conclusion |
| --- | --- | --- | --- |
| Requested mix | `hocrgen`/HeOCR planning | Intended target strata before or during generation/import. | Downstream wanted this shape for a stated purpose. |
| Generated or observed mix | Public `hocrsyngen` outputs plus downstream import records | Actual counts and strata found in validated manifests, catalog joins, reports, and import ids. | The candidate batch has this synthetic distribution. |
| Reviewed mix | `hocrgen`/HeOCR review workflow, optionally S6e sidecars | Which samples/pages/strata have retained visual or reviewer evidence. | These strata have review evidence for the stated purpose. |
| Capped or admitted mix | `hocrgen`/HeOCR release-cap governance, optionally S6d records | Which candidate slice was admitted, reduced, held, or rejected under cap policy. | This slice fits or fails the downstream cap decision for the stated purpose. |
| Released mix | HeOCR release governance | Final public payload composition after all release gates. | The released payload contains this approved synthetic slice. |

A generated/observed mix can match the requested profile and still be unreviewed,
over cap, utility-unmeasured, domain-shift-unmeasured, or release-ineligible.
Likewise, a reviewed mix can still be reduced or rejected by cap policy.

## Contract Shape

Recommended top-level contract id: `candidate_batch_profile_mix.v1`.

Required top-level fields:

| Field | Requirement | Meaning |
| --- | --- | --- |
| `profile_id` | Required | Durable downstream id for the candidate batch profile. |
| `profile_version` | Required | Contract/version string, recommended `candidate_batch_profile_mix.v1`. |
| `owner_repository` | Required | Repository or system that owns the profile, usually `hocrgen` or HeOCR. |
| `created_at` | Required | Date or timestamp when the profile was recorded. |
| `intended_downstream_purpose` | Required | Purpose such as import dry-run, visual review planning, cap rehearsal, utility planning, domain-shift rehearsal, release-profile planning, or public-release planning. |
| `candidate_batch_refs` | Required | One or more requested or observed source batch records with downstream import ids, paths, generation/export commands, validation reports, and explicit limitations when any source detail is unknown. |
| `target_counts` | Required | Target sample and page counts, or explicit diagnostic/smoke-test scope. |
| `requested_mix` | Required | Required, preferred, and excluded strata for the intended purpose. |
| `observed_mix` | Required when a batch exists | Counts from validated manifest/catalog/report evidence. |
| `mix_gap_summary` | Required | Gap records and reason codes comparing requested, observed, reviewed, capped, or released layers. |
| `claim_boundaries` | Required | Statement of what the profile does and does not support. |
| `limitations` | Required | Missing evidence, sparse strata, unknown source commands, unresolved downstream dependencies, and ownership boundaries. |

Conditionally required fields:

| Field path | Required when |
| --- | --- |
| `hocrsyngen_evidence` | Any observed/generated mix is recorded from `hocrsyngen` outputs. |
| `hocrsyngen_evidence.validation_report` or `candidate_batch_refs[].validation_report` | A concrete generated/imported batch is cited. Multi-source profiles should prefer per-source validation report references. |
| `hocrsyngen_evidence.template_catalog_v2_join` | Document family, base family, or any catalog-derived view is cited. This is effectively required for S6f profiles that compare requested or observed family/base-family mixes. |
| `hocrsyngen_evidence.rendering_coverage_report` | Coverage evidence, missing coverage, or rendering-coverage dimensions are cited. |
| `review_expectation` | The purpose is review planning, cap rehearsal, utility planning, domain-shift comparison, or release planning. |
| `reviewed_mix` | S6e review sidecars or reviewer coverage are cited. |
| `cap_relation` | The profile is used for release-cap rehearsal or release planning. |
| `cap_relation.s6d_cap_decision_refs` | Cap admission, reduction, hold, rejection, or release approval is cited. |
| `diversity_relation.s6c_warning_refs` | Diversity, domain-shift, repeated-pattern, or unreviewed-stratum warnings influence the profile. |
| `utility_relation.s6b_packet_refs` | OCR/HTR utility is cited, measured, or explicitly requested. |
| `released_mix` | The profile is attached to a public HeOCR release decision. |

Optional fields:

- owner team, review project, dashboard, or issue/PR references;
- profile supersedes/superseded-by links;
- `candidate_batch_ref` as a singular convenience field only for a narrow
  profile that cites exactly one source batch and does not aggregate across
  multiple generated/imported sources;
- expected split role for synthetic candidates, such as dry-run import,
  calibration, development, utility evaluation, review, release rehearsal, or
  public release;
- downstream real-reference profile id when domain-shift comparison is planned;
- per-stratum minimum or maximum thresholds when `hocrgen`/HeOCR policy defines
  them;
- confidence notes or reviewer calibration notes owned downstream.

## Public hocrsyngen Evidence

Profiles must cite only public `hocrsyngen` identifiers, fields, and reports.
They must not inspect private Python recipes, drawing helpers, implementation
dataclasses, private package resources, local filenames, or generated image
layout details that are not exposed through a public contract.

Permitted `hocrsyngen` evidence includes:

- `manifest_sample_ids`;
- `manifest_page_ids`;
- `template_id`;
- `recipe_id`;
- `template_catalog_v2_join`, including `document_family` and `base_family`;
- `degradation_preset`;
- `font_id`;
- `seed`;
- `sample_index` or sample-index range;
- `source_corpus`;
- `persona` or style control id from `sample.controls.persona`;
- `condition` control id from `sample.controls.condition`;
- validation report status and path from `hocrsyngen validate PATH --format
  json`;
- generation report, export report, or command string when known;
- optional rendering coverage report id/path and covered/missing summary;
- optional S6a, S6c, S6d, or S6e evidence references stored downstream.

These fields identify and summarize candidate synthetic evidence. They do not
prove realism, utility, domain match, cap compliance, release eligibility, or
publication approval.

## Source Batch References

S6f profiles should treat each generated or imported source batch as its own
auditable input. This matters because current public `hocrsyngen generate`
supports one batch-wide persona/style control and one batch-wide condition
control per invocation. A profile that aggregates multiple persona, condition,
template, or seed strata must therefore cite multiple public source batches or a
downstream import record that preserves those source batch boundaries. Do not
represent an aggregate multi-style or multi-condition profile as if it came from
one public generation command unless a future public CLI explicitly supports
that orchestration.

Each `candidate_batch_refs[]` entry should retain:

- source batch id or downstream import id;
- public generation or export command, when known;
- output path or downstream import path;
- validation report status and path;
- sample and page counts for that source;
- requested template ids or observed template ids;
- persona/style control used by that source, or `null`;
- condition control used by that source, or `null`;
- seed and sample-index range for that source;
- optional rendering coverage report path for that source;
- limitations such as `unknown_source_command` or
  `source_batch_boundaries_missing`.

Downstream systems may still compute one aggregate `observed_mix`, but that
aggregate must be traceable back to the individual source batch refs. If source
batch boundaries are unavailable, record a `source_batch_boundaries_missing`
limitation and avoid claims that depend on cross-source balancing.

## Requested Mix

The requested mix is downstream intent. It can be recorded before generation, at
import planning time, or after the fact when a dry-run needs a declared purpose.

At minimum, a requested mix should state:

- intended downstream purpose;
- target sample count and page count;
- required strata;
- preferred strata;
- excluded strata;
- template id, recipe id, document family, and base family expectations;
- style/persona control expectations;
- condition control expectations;
- degradation preset, font id, and source-corpus expectations;
- seed and sample-index policy;
- minimum review coverage expectation;
- relation to S6c diversity warnings and advisory thresholds;
- relation to S6d cap decisions and cap-policy limits;
- relation to S6e review sidecars and visual evidence retention;
- limitations and unresolved downstream dependencies.

The requested mix should distinguish hard requirements from preferences:

| Requirement class | Meaning | Example |
| --- | --- | --- |
| `required` | Missing or violating this stratum creates a profile gap. | At least one reviewed page from every base family present in the import. |
| `preferred` | Useful for planning but not necessarily blocking. | Include non-default style and condition slices when available. |
| `excluded` | Must not appear for the stated purpose. | Exclude a template family that is out of scope for a target dry-run. |

When a profile is exploratory or diagnostic, it can say the requested mix is
narrow by design. That limitation must travel with any later evidence packet.

## Observed Mix

The observed mix records what was actually present in generated or imported
candidate batches. It should be derived from public manifests, public catalog
joins, CLI reports, optional rendering coverage reports, and downstream import
ids.

Minimum manifest-derived observed mix views:

- sample and page counts by `template_id`;
- sample and page counts by `recipe_id`;
- sample and page counts by `degradation_preset`;
- sample and page counts by `font_id`;
- sample and page counts by source corpus;
- sample and page counts by persona/style control;
- sample and page counts by condition control;
- seed span and sample-index range;
- cross-strata counts for template id x degradation, template id x style,
  template id x condition, font x degradation, and seed range x template;

Catalog-derived observed mix views require a `template_catalog.v2` join:

- sample and page counts by `document_family` and `base_family`;
- cross-strata counts for base family x degradation, base family x style, and
  base family x condition;
- any family/base-family gap records or requested-vs-observed family
  comparisons;

Additional optional observed views:

- optional rendering coverage covered/missing summary when a coverage report is
  present;
- optional S6c warnings when a diversity/domain-shift packet exists.

The observed mix should record unknowns explicitly. For example, if the
generation command is unavailable but the manifest validates, record the
validated manifest fields and an `unknown_source_command` limitation.

## Reviewed Mix

The reviewed mix records what downstream reviewers actually inspected. It
should cite S6e review evidence sidecars when those exist. If review happened
without an S6e sidecar, the profile should still retain reviewed sample ids,
page ids, strata, limitations, and evidence references in downstream storage.

Minimum reviewed mix fields:

- reviewed sample ids and page ids;
- review sampling method or selection rationale;
- reviewed strata by base family, template id, degradation preset, font id,
  style/persona control, condition control, source corpus, and seed/sample-index
  range;
- unreviewed strata and why they were not reviewed;
- reviewer state or decision category when known;
- S6a acceptance category or rejection reason references when used;
- S6c warning references for unreviewed strata, repeated patterns, or skew;
- S6d cap decision references when review influenced cap admission, reduction,
  hold, or rejection;
- limitations when review supports only smoke checks or dry-run rehearsal.

Minimum review coverage expectations should be declared by downstream purpose.
For example, a smoke import may require only one page to render in the review
system, while cap rehearsal may require at least one reviewed page from each
base family and every non-default style or condition slice present in the
admitted subset.

## Capped, Admitted, And Released Mix

Cap and release decisions belong downstream. Profiles may cite those decisions,
but they must not define cap enforcement in `hocrsyngen`.

When a profile is used for cap rehearsal or release planning, record:

- release profile id and version, if one exists;
- target release, dry-run, or rehearsal purpose;
- synthetic percentage and absolute-count policy when downstream policy defines
  it;
- per-family, per-template, per-style, per-condition, per-degradation, per-font,
  or per-source limits when downstream policy defines them;
- admitted sample/page ids;
- reduced or excluded sample/page ids;
- hold owner and unblock condition when held;
- S6d cap decision id and reason codes;
- whether utility remains unmeasured under S6b;
- whether domain shift remains unmeasured under S6c;
- whether review evidence remains missing under S6e;
- explicit statement when no public release approval exists.

Released mix exists only after HeOCR release governance. A profile should not
include `released_mix` unless a downstream release record actually exists.

## Mix Gap Reason Codes

Profiles should use stable reason names for gaps between requested, observed,
reviewed, capped, and released layers. These reason names are planning guidance
until `hocrgen` versions a concrete workflow.

| Reason | Use when |
| --- | --- |
| `missing_stratum` | A required requested stratum is absent from the generated, observed, reviewed, capped, or released layer. |
| `overrepresented_template` | One template or recipe exceeds the requested mix, S6c advisory threshold, or downstream profile threshold. |
| `overrepresented_base_family` | One base family dominates the mix for a purpose that requires multi-family coverage. |
| `insufficient_non_default_style_coverage` | Non-default persona/style controls are missing or too sparse for the stated purpose. |
| `insufficient_non_default_condition_coverage` | Non-default condition controls are missing or too sparse for the stated purpose. |
| `unreviewed_requested_stratum` | A required or important requested stratum exists in the observed mix but has no review evidence. |
| `seed_concentration` | Evidence comes from too few seeds or too narrow a contiguous sample-index range for the claim. |
| `degradation_or_font_skew` | Degradation preset or font id distribution is too concentrated for the requested purpose. |
| `source_corpus_skew` | Source corpus distribution is too narrow or out of profile. |
| `coverage_report_missing` | The requested purpose cites rendering coverage but no coverage report is available. |
| `s6c_warning_unresolved` | S6c warnings relevant to the profile remain unresolved or only partially mitigated. |
| `review_sidecar_missing` | The profile expects S6e review evidence but no sidecar or equivalent downstream record exists. |
| `cap_conflict` | The requested or observed mix conflicts with S6d cap policy or downstream release profile rules. |
| `utility_evidence_missing` | The profile requests utility planning or claims but no governed S6b utility packet exists. |
| `domain_shift_unmeasured` | The profile requires synthetic-to-real comparison but no governed real-reference S6c comparison exists. |
| `downstream_profile_missing` | The downstream release profile, dry-run profile, or policy owner has not been recorded. |
| `governance_dependency_missing` | Review workflow, dedupe, privacy, leakage, benchmark handling, release assembly, export, publication, or release approval is missing. |
| `forbidden_claim_risk` | Profile text or downstream notes imply real identity, authorship, medical, psychological, disability, demographic, sensitive-attribute, or real-source provenance claims. |

Gap records should cite the layer where the gap appears, the affected stratum,
counts or shares when known, public `hocrsyngen` ids, and downstream evidence
references when available.

## Example Profile

This example is illustrative, not a normative JSON schema.

```yaml
profile_id: s6f-profile-heocr-dryrun-0001
profile_version: candidate_batch_profile_mix.v1
owner_repository: hocrgen
created_at: 2026-05-08
intended_downstream_purpose: cap_rehearsal_and_review_planning
candidate_batch_refs:
  - requested_batch_id: hocrgen-plan:s6f-dryrun-small
    observed_import_id: hocrgen-import:hocrsyngen-batch-17-standard
    generation_command: hocrsyngen generate --count 16 --seed 17 --template-id printed_letter --template-id handwritten_note --template-id archive_card --template-id ledger --persona style_standard_v1 --condition condition_standard_v1 --output out/s6f-standard --format json
    validation_report:
      status: valid
      path: reports/s6f-standard-validation.json
    sample_count: 16
    page_count: 16
    persona: style_standard_v1
    condition: condition_standard_v1
    seed_span:
      min_seed: 17
      max_seed: 17
      sample_index_range: 0-15
  - requested_batch_id: hocrgen-plan:s6f-dryrun-small
    observed_import_id: hocrgen-import:hocrsyngen-batch-18-open-drift
    generation_command: hocrsyngen generate --count 12 --seed 18 --template-id printed_letter --template-id handwritten_note --template-id archive_card --template-id ledger --persona style_open_drift_v1 --condition condition_low_contrast_v1 --output out/s6f-open-drift --format json
    validation_report:
      status: valid
      path: reports/s6f-open-drift-validation.json
    sample_count: 12
    page_count: 12
    persona: style_open_drift_v1
    condition: condition_low_contrast_v1
    seed_span:
      min_seed: 18
      max_seed: 18
      sample_index_range: 0-11
  - requested_batch_id: hocrgen-plan:s6f-dryrun-small
    observed_import_id: hocrgen-import:hocrsyngen-batch-19-compact
    generation_command: hocrsyngen generate --count 12 --seed 19 --template-id printed_letter --template-id handwritten_note --template-id archive_card --template-id ledger --persona style_compact_steady_v1 --condition condition_dense_spacing_v1 --output out/s6f-compact --format json
    validation_report:
      status: valid
      path: reports/s6f-compact-validation.json
    sample_count: 12
    page_count: 12
    persona: style_compact_steady_v1
    condition: condition_dense_spacing_v1
    seed_span:
      min_seed: 19
      max_seed: 19
      sample_index_range: 0-11
target_counts:
  requested_samples: 40
  requested_pages: 40
requested_mix:
  required:
    base_family:
      - printed_letter
      - handwritten_note
      - archive_card
      - ledger
    review_coverage:
      minimum_pages_per_base_family: 1
      include_non_default_style_controls: true
      include_non_default_condition_controls: true
  preferred:
    degradation_preset:
      - office_scan_soft
      - office_scan_heavy
      - notebook_scan_heavy_wear
      - archive_scan_faded
    seed_policy: avoid single-seed-only evidence for broad claims
  excluded:
    release_publication: true
hocrsyngen_evidence:
  template_catalog_v2_join: true
observed_mix:
  sample_count: 40
  page_count: 40
  base_family_counts:
    printed_letter: 10
    handwritten_note: 10
    archive_card: 10
    ledger: 10
  persona_counts:
    style_standard_v1: 16
    style_open_drift_v1: 12
    style_compact_steady_v1: 12
  condition_counts:
    condition_standard_v1: 16
    condition_low_contrast_v1: 12
    condition_dense_spacing_v1: 12
  seed_span:
    min_seed: 17
    max_seed: 20
    sample_index_range: 0-39
review_expectation:
  minimum_pages_per_base_family: 1
  minimum_pages_per_non_default_style: 1
  minimum_pages_per_non_default_condition: 1
reviewed_mix:
  s6e_sidecar_refs:
    - review-heocr-s6dryrun-0004
  reviewed_sample_ids:
    - hocrsyngen-s00000017-000000
  reviewed_page_ids:
    - hocrsyngen-s00000017-000000-page-0001
  unreviewed_strata:
    - base_family ledger has no reviewed page yet
diversity_relation:
  s6c_warning_refs:
    - unreviewed_stratum
cap_relation:
  s6d_cap_decision_refs:
    - cap-heocr-s6dryrun-0001
  decision_status: hold
mix_gap_summary:
  - reason_code: unreviewed_requested_stratum
    layer: reviewed_mix
    stratum: base_family=ledger
  - reason_code: cap_conflict
    layer: capped_or_admitted_mix
    stratum: release_profile=heocr_synthetic_rehearsal_v1
claim_boundaries:
  - dry-run and cap rehearsal only
  - no downstream utility claim is made
  - no public release approval is implied
limitations:
  - review evidence is sparse
  - cap decision remains downstream hocrgen governance
  - export and publication are out of scope
```

## Privacy, Provenance, And Forbidden Claims

Profile fields should describe synthetic generator controls and downstream
planning decisions only. They must not claim:

- real person identity or authorship;
- living-person handwriting imitation;
- medical, psychological, disability, demographic, sensitive-attribute, or
  human-state facts;
- real-source provenance for generated samples;
- release approval, publication approval, benchmark eligibility, utility proof,
  or domain match unless downstream governance records actually establish the
  narrower claim.

Persona/style and condition ids are neutral synthetic controls as defined by
ADR 0005. A profile may count them, require coverage of them, or cap them
downstream, but it must not reinterpret them as real identity, health,
authorship, or provenance metadata.

## Relationship To S6a, S6b, S6c, S6d, And S6e

S6f composes prior S6 planning artifacts without replacing them:

- S6a defines downstream realism categories, calibrated example classes, visual
  evidence expectations, and rejection reasons.
- S6b defines the evidence required before OCR/HTR utility claims can be made
  against governed real references.
- S6c defines diversity summaries, repeated-pattern warnings, domain-shift
  boundaries, and unreviewed-stratum risks.
- S6d defines how cap decisions should cite public `hocrsyngen` metadata and
  evidence packets without moving cap ownership into this repo.
- S6e defines optional review evidence sidecars for reviewed sample/page ids,
  reviewer notes, visual references, decision categories, reason codes, and
  limitations.

The S6f profile is the place to say what mix was intended and how the observed,
reviewed, capped, and released layers relate. It must not collapse those
separate contracts into a single release decision.

## Relationship To Future S6g

`S6g: hocrgen adapter handoff checklist` should reference this S6f profile
contract rather than inventing new profile semantics. S6g should focus on the
external `hocrgen` implementation checklist: installed CLI import, validation,
catalog joins, id retention, optional evidence links, dry-run rehearsal,
failure modes, and governance boundaries.

S6g should not implement adapter code in `hocrsyngen`, should not mutate
manifest v1, and should not redefine requested, observed, reviewed, capped, or
released mix fields. If downstream implementation discovers that a machine
schema is needed, that schema belongs in a versioned downstream contract or a
future explicitly scoped `hocrsyngen` planning item.

## What Belongs Outside hocrsyngen

These belong in `hocrgen`/HeOCR, not in the `hocrsyngen` baseline:

- batch profile storage and workflow state;
- profile selection, profile thresholds, release profiles, balancing, and caps;
- orchestration that requests multiple generated runs to satisfy a profile;
- import ids, dry-run ids, review ids, cap decision ids, and release ids;
- review workflow, reviewer notes, visual evidence storage, and decisions;
- real-reference metadata, domain-shift comparison, utility evaluation, leakage
  checks, dedupe, privacy review, export, publication, and public payload
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
