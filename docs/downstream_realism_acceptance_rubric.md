# Downstream Realism Acceptance Rubric

This S6a document defines downstream realism acceptance guidance for generated
candidate synthetic Hebrew OCR/HTR batches after they have already passed
`hocrsyngen` validation and generator-quality visual inspection. It is
documentation and planning only. It does not add generator behavior, manifest
fields, schemas, sidecars, fixture changes, dependencies, `hocrgen` adapter
code, review workflow state, release caps, export behavior, or publication
behavior.

The rubric is handoff guidance for `hocrgen`/HeOCR governance. It explains how
downstream reviewers can classify generated candidate batches, what evidence
should support those decisions, and which rejection reasons belong in downstream
release governance rather than in `hocrsyngen` outputs. It is not a versioned
machine contract, and the category and reason names below remain provisional
until a future `hocrgen` workflow or S6e review evidence sidecar makes them
stable.

## Relationship To Visual Inspection

[visual_inspection_rubric.md](visual_inspection_rubric.md) remains the S3
generator-quality checklist for rendered pages. It asks whether a page is
rendered coherently: readable Hebrew, plausible layout, intact page assets,
acceptable degradation, no clipping, and no obvious synthetic artifact failure.

This S6a rubric builds on that checklist but does not replace it. A downstream
candidate can fail here even when it passes generator-quality inspection. For
example, a page may render cleanly but still be too repetitive, too unlike the
target HeOCR release domain, unsupported by enough visual evidence, or unsuitable
under a release profile's synthetic cap. Conversely, a generator-quality failure
should be sent back to `hocrsyngen` follow-up and should not be reclassified as a
downstream policy decision.

Use this order:

1. Validate the batch with `hocrsyngen validate PATH --format json`.
2. Apply the S3 visual inspection rubric to selected rendered pages.
3. Apply this S6a downstream acceptance rubric in `hocrgen`/HeOCR governance.
4. Record release eligibility, caps, reviewer state, rejection status, and audit
   evidence outside `generation_manifest.json` v1.

## Acceptance Categories

Downstream review should classify each reviewed candidate batch, and optionally
each reviewed sample or page, into one of these categories.

| Category | Meaning | Allowed downstream use |
| --- | --- | --- |
| `accept_for_dry_run` | The batch is valid, visually coherent, and realistic enough for a non-public import, review, cap, dedupe, and utility rehearsal. | `hocrgen` dry-run adapter and governance rehearsal only. |
| `eligible_for_utility_evaluation` | The batch is realistic enough to be considered for controlled OCR/HTR utility evaluation, but only after S6b or downstream benchmark rules define reference handling, metrics, and claim boundaries. | Candidate input for later utility-evaluation planning; not approval for CER/WER claims or benchmark inclusion by itself. |
| `hold_for_calibration` | The batch is promising but lacks enough comparison evidence, reviewer agreement, target-domain alignment, or cap context. | Keep out of release assembly until evidence is added. |
| `reject_for_downstream_release` | The batch may be technically valid but should not enter governed release candidates because it fails downstream realism, diversity, evidence, cap, or policy expectations. | Do not use in public release payloads. |
| `send_back_to_generator_quality` | The batch shows rendering, layout, artifact, clipping, Hebrew readability, catalog, or asset problems covered by the S3 rubric. | Track as `hocrsyngen` generator-quality follow-up, not release governance. |

These categories are provisional downstream governance vocabulary. They must not
be written into `generation_manifest.json` v1, and downstream tools should not
treat their spelling as stable API until a future `hocrgen` workflow or S6e
review evidence sidecar versions them. A future S6e review evidence sidecar may
define a portable machine-readable place for reviewed sample ids, reviewer
notes, and rejection reasons, but this S6a document does not create that
sidecar.

## Calibrated Example Classes

Use calibrated example classes rather than a binary "realistic enough" judgment.
The goal is reviewer consistency across batches and across target HeOCR release
profiles.

### Strong Accept Class

A strong accept class is suitable for `accept_for_dry_run` and may make the
batch eligible for later utility-evaluation planning if real references exist
downstream. It does not approve benchmark use or utility claims by itself.

- Reviewed pages pass the S3 visual inspection rubric across the stated
  downstream review strata.
- The document family is recognizable without manifest lookup.
- Hebrew text is readable enough to support OCR/HTR task design.
- Degradation is visible but does not dominate the sample.
- Template, style, condition, seed, and text variation are not visibly
  repetitive across the reviewed slice.
- Synthetic disclosure and manifest provenance remain clear.
- The batch can be joined to stable public metadata such as
  `template_catalog.v2` without private implementation assumptions.

Example classes include a clean ledger slice with varied rows and readable
headers, an archive-card slice with inspectable identifiers and stamps, or a
handwritten-like note slice where line drift is plausible and main text remains
readable.

### Conditional Accept Class

A conditional accept class belongs in `hold_for_calibration` until more evidence
is available.

- Pages pass the generator-quality rubric, but only a narrow family/style/seed
  slice was reviewed.
- Heavy degradation looks plausible in isolation but needs comparison against
  real target references or lighter synthetic variants.
- The batch is visually useful for one target scenario but likely overrepresents
  a template, condition, style, or artifact pattern.
- Reviewer notes identify a recurring concern that is not severe enough to send
  back to generator-quality follow-up.
- Downstream caps or release profile rules have not yet been applied.

Example classes include a faded archive-card slice that is readable but close to
the lower legibility boundary, a dense-spacing condition slice that may
overrepresent tight text, or a handwritten-like note slice that needs comparison
against real handwriting references before utility claims are made.

### Reject Class

A reject class should become `reject_for_downstream_release` unless the issue is
actually a generator-quality problem.

- The reviewed slice is too repetitive across seeds, templates, text, visual
  artifacts, style controls, or degradation patterns.
- The batch is plausible as synthetic output but mismatched to the target HeOCR
  release domain or benchmark scenario.
- The visual evidence is too sparse to justify release eligibility.
- The sample mix would exceed synthetic caps or distort source composition.
- The batch could bias OCR/HTR evaluation toward synthetic artifacts rather than
  real Hebrew document variation.
- Review notes cannot cite stable public identifiers and visual reasons.

Example classes include a batch dominated by one easy printed form family when a
release profile needs broader domain coverage, a heavy-degradation slice whose
artifacts are too uniform across pages, or a style/condition mix that looks
coherent but would overfit a benchmark to a narrow synthetic rendering pattern.

## Visual Evidence Expectations

Downstream acceptance should be evidence-backed. The minimum evidence packet
belongs outside `hocrsyngen` manifest v1 and should cite only stable public
identifiers.

Recommended evidence fields:

- batch path or downstream import id;
- validation report status from `hocrsyngen validate PATH --format json`;
- generated command or source of the batch, including count, seed, template,
  persona/style, and condition controls when known;
- reviewed sample ids and page ids;
- manifest provenance fields: template id, recipe id, degradation preset,
  font id, seed, and sample index;
- optional `template_catalog.v2` joined metadata: document family, base family,
  page regions, annotation types, identifier types, layout density, and review
  features;
- optional rendering coverage report path when the batch was generated with
  `--rendering-coverage-report`;
- concise visual notes with rejection or hold reasons;
- reviewed image references or thumbnails stored in the downstream review
  system, not in `generation_manifest.json` v1;
- reviewer decision category and date inside `hocrgen`/HeOCR governance.

For a small dry-run batch, one reviewed page from each template id present, plus
any non-default style or condition slice, is only a smoke-triage minimum. It can
support `hold_for_calibration` or a narrow dry-run rehearsal note, but it is not
enough by itself to support release eligibility, utility-evaluation eligibility,
or a claim that repeated synthetic patterns have been ruled out.

Before a downstream acceptance decision is recorded, the review packet should
state the sampling strata used for the decision. At minimum, stratify reviewed
pages by document family or base family, degradation preset, style/persona
control, condition control, and seed range whenever those dimensions are present
in the candidate batch. If a stratum is not reviewed because the batch is too
small, record that limitation and use `hold_for_calibration` rather than an
acceptance category that implies broader evidence.

## Rejection Reasons

Use consistent rejection reason names so downstream review can be audited. These
reason names are planning guidance only until a future sidecar or `hocrgen`
workflow makes them machine-readable and versioned.

| Reason | Use when | Owner |
| --- | --- | --- |
| `generator_quality_failure` | The page has unreadable Hebrew, clipping, overlap, corrupt assets, broken layout, implausible artifacts, or other S3 visual inspection failures. | `hocrsyngen` follow-up. |
| `insufficient_visual_evidence` | Too few reviewed pages, missing reviewer notes, missing image references, or no stable ids support the decision. | `hocrgen`/HeOCR review workflow. |
| `target_domain_mismatch` | The batch is valid but does not match the intended HeOCR release or benchmark domain. | `hocrgen`/HeOCR release planning. |
| `over_represented_synthetic_pattern` | Template, style, condition, seed, degradation, text, or artifact patterns repeat too strongly. | `hocrgen` caps and S6c metrics. |
| `utility_unproven` | OCR/HTR benefit is claimed but no downstream benchmark reference or CER/WER evidence exists. | `hocrgen`/HeOCR evaluation. |
| `cap_or_mix_violation` | The candidate would exceed release profile caps or distort source composition. | `hocrgen` release governance. |
| `governance_gap` | Review state, dedupe, leakage, privacy, benchmark handling, export, or publication gates are missing. | `hocrgen`/HeOCR governance. |
| `forbidden_claim_risk` | Notes or metadata imply real identity, authorship, medical, psychological, disability, sensitive-attribute, or real-source provenance claims. | Shared policy; release decision downstream. |

Do not use downstream rejection reasons to hide generator defects. If the visual
problem is covered by [visual_inspection_rubric.md](visual_inspection_rubric.md),
record `generator_quality_failure` and cite the S3 visual issue.

## Generator Quality Versus Release Eligibility

`hocrsyngen` generator-quality review answers:

- Did the batch validate against manifest v1?
- Do page assets open, match hashes, and have expected dimensions?
- Is Hebrew logical-order metadata valid and rendered plausibly?
- Does the governed template family look coherent?
- Are degradation, clipping, overlap, and visible artifacts acceptable?
- Are generator controls represented only as synthetic controls?

Downstream release eligibility answers:

- Is this candidate useful for a specific HeOCR release, dry-run, or benchmark?
- Does the candidate mix fit release profiles and synthetic caps?
- Is there enough reviewed visual evidence for the intended use?
- Does the batch improve or stress OCR/HTR behavior against real references?
- Does it avoid overrepresenting synthetic artifacts or narrow domains?
- Has `hocrgen` handled review workflow, privacy, dedupe, leakage, benchmark
  selection, source composition, export, and publication policy?

Passing generator-quality review is necessary for downstream consideration. It
is not sufficient for release eligibility.

## hocrgen And HeOCR Responsibilities

The following belong in `hocrgen` or HeOCR, not in the `hocrsyngen` baseline:

- import adapter implementation;
- release profiles, synthetic caps, balancing, and source-composition policy;
- reviewer assignment, review workflow, decision state, and audit storage;
- review sidecar consumption once S6e defines a portable contract;
- dedupe, leakage, privacy, benchmark/reference selection, and utility
  measurement;
- release assembly, export, publication, and public dataset payload decisions;
- milestone-level decisions about whether generated synthetic batches complement
  real data for a specific HeOCR release.

The following can remain in `hocrsyngen`:

- deterministic candidate generation;
- manifest v1 validation;
- public CLI reports;
- template catalog metadata;
- optional rendering coverage reports;
- docs that define handoff expectations and generator-quality boundaries.

## S6 Follow-Up Links

This rubric intentionally leaves implementation and machine-readable review
contracts to later S6 items:

- `S6b` should define downstream utility measurement contracts for CER/WER only
  when real references exist.
- `S6c` should define diversity and domain-shift metrics that detect repeated
  synthetic patterns and synthetic-to-real gaps.
- `S6d` should define release cap handoff policy without moving governance into
  this repository.
- `S6e` should define any review evidence sidecar outside
  `generation_manifest.json` v1.
- `S6f` should define candidate batch profile and mix handoff.
- `S6g` should document the external `hocrgen` adapter implementation checklist.
