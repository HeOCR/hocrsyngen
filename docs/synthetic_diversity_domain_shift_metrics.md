# Synthetic Diversity And Domain-Shift Metrics

This S6c document defines planning guidance for measuring candidate-batch
diversity in `hocrsyngen` and synthetic-to-real domain shift downstream in
`hocrgen`/HeOCR. It is documentation and planning only. It does not add
generator behavior, manifest fields, schemas, sidecars, packaged fixture
changes, dependencies, `hocrgen` adapter code, benchmark runners, review
workflow state, release caps, export behavior, publication behavior, or utility
claims.

The goal is to detect repeated synthetic patterns and over-representation before
candidate batches are used in downstream dry-runs, utility evaluations, or
release planning. Diversity evidence can be computed from public
`hocrsyngen` outputs. Domain-shift evidence requires downstream real-reference
comparison owned by `hocrgen`/HeOCR.

## Layered Metric Boundary

Keep these layers separate in evidence packets and review notes.

| Layer | Owner | Input evidence | Valid conclusion | Invalid conclusion |
| --- | --- | --- | --- | --- |
| Generator-batch diversity | `hocrsyngen` reports plus downstream summarization | Validated manifest v1, `template_catalog.v2`, optional `rendering_coverage_report.v1`, generation command, seeds, style/persona and condition controls | The candidate batch is broad or narrow across public synthetic dimensions. | The batch matches real data, improves OCR/HTR utility, or is release eligible. |
| Downstream realism acceptance | `hocrgen`/HeOCR | S6a reviewed pages, categories, visual notes, stable ids, target-domain context | The candidate is plausible enough for a specific downstream dry-run or hold/reject decision. | CER/WER utility, benchmark eligibility, caps compliance, or publication approval. |
| Downstream utility measurement | `hocrgen`/HeOCR | S6b real references, ground truth, split/leakage controls, OCR/HTR runs, metric definitions | Whether a candidate slice helps, stresses, or diagnoses OCR/HTR behavior against governed references. | Release eligibility or permission to publish synthetic data. |
| Synthetic-to-real domain shift | `hocrgen`/HeOCR | Real-reference metadata and measured synthetic-vs-real comparison strata | How synthetic candidates differ from target real distributions and where evidence is sparse. | Generator correctness, benchmark/reference eligibility, or public utility claims by itself. |
| Release profile and caps | `hocrgen`/HeOCR | Source composition, caps, review state, dedupe, leakage, privacy, export policy | Whether a candidate mix can enter governed release planning. | A new `hocrsyngen` generator contract. |

S6c depends on S6a and S6b. S6a defines realism acceptance vocabulary and review
evidence. S6b defines utility-evidence prerequisites and claim boundaries. S6c
adds diversity and domain-shift summaries so downstream systems can tell whether
a candidate batch is repeated, skewed, or mismatched before using it in those
later gates. It does not replace either gate.

## Public hocrsyngen Diversity Dimensions

Diversity summaries must use public, stable surfaces only. They should not read
private Python recipe objects, drawing helpers, filenames, or local
implementation details.

Available dimensions include:

- `template_id` from `sample.provenance.template_id`;
- `recipe_id` from `sample.provenance.recipe_id` and `sample.recipe_id`;
- `document_family` and `base_family` joined from `template_catalog.v2` by
  `(template_id, recipe_id)`;
- `degradation_preset` from `sample.provenance.degradation_preset`;
- `font_id` from `sample.provenance.font_id`;
- `seed` and `sample_index` from `sample.provenance`;
- sample id and page id;
- persona/style control from `sample.controls.persona`;
- condition control from `sample.controls.condition`;
- source corpus id from `sample.provenance.source_corpus`;
- rendering coverage sidecar dimensions when present, including covered and
  missing fonts, templates, recipes, degradation presets, Hebrew text features,
  mixed-direction evidence, RTL rendering path evidence, environment status,
  and page asset smoke evidence.

Text-level summaries may use `text.logical_order` for aggregate length, script
feature, punctuation, numeric, Latin-fragment, niqqud, and duplicate-text
checks, but they must preserve the manifest rule that text remains logical-order
UTF-8 Hebrew, NFC-normalized, and synthetic. Use the normalization rules below
for synthetic-only duplicate checks. Do not copy real benchmark transcriptions
into generated text analysis without downstream leakage review.

## Generator-Batch Diversity Summaries

These metrics can be computed without changing `generation_manifest.json` v1.
Use the metric ids below in downstream evidence packets so repeated reports are
comparable.

| Metric id | Layer | Computation rule | Required inputs | Output | Interpretation |
| --- | --- | --- | --- | --- | --- |
| `sample_count_by_dimension` | Generator-batch diversity | Count samples for each value of a named public dimension. Run separately for `template_id`, `recipe_id`, `base_family`, `document_family`, `degradation_preset`, `font_id`, persona/style control, condition control, source corpus, and seed range. | Manifest v1, optional `template_catalog.v2` join for family fields. | Table with dimension, value, sample count, and share of total samples. | Shows whether a batch is concentrated or broad for each public synthetic dimension. |
| `page_count_by_dimension` | Generator-batch diversity | Count pages for each value of the same named public dimensions. | Manifest v1 page lists, optional `template_catalog.v2` join. | Table with dimension, value, page count, and share of total pages. | Prevents multi-page future samples from hiding concentration in sample-level counts. Current samples may have one page each. |
| `largest_stratum_share` | Generator-batch diversity | For each named dimension, divide the largest stratum sample count by total sample count. | Output of `sample_count_by_dimension`. | Number in `[0, 1]` per dimension, plus largest value name. | High values indicate over-representation for that dimension. |
| `distinct_value_count` | Generator-batch diversity | Count distinct values present for each named dimension. Treat `null` persona/style and condition controls as explicit values. | Manifest v1, optional `template_catalog.v2` join. | Integer per dimension. | Low counts show narrow coverage even if the batch is valid. |
| `cross_stratum_count` | Generator-batch diversity | Count samples for required dimension pairs: `base_family` x `degradation_preset`, `base_family` x persona/style, `base_family` x condition, `font_id` x `degradation_preset`, and seed range x `template_id`. | Manifest v1, optional `template_catalog.v2` join. | Table with pair id, left value, right value, count, and share. | Finds hidden concentration across combinations that single-dimension counts miss. |
| `seed_span_summary` | Generator-batch diversity | Report minimum seed, maximum seed, number of distinct seeds, sample-index minimum, sample-index maximum, contiguous sample-index span length, and total samples. | `sample.provenance.seed`, `sample.provenance.sample_index`. | One row per batch and optionally per template/base family. | Shows whether evidence comes from a narrow contiguous generation slice. |
| `text_duplicate_rate` | Generator-batch diversity | Normalize synthetic `text.logical_order` with the S6c synthetic-text normalization profile, count exact duplicate normalized strings, and divide duplicate samples by total samples. A sample is duplicate when its normalized string was already seen earlier in the batch. | Manifest v1 text only. | Duplicate sample count, total sample count, duplicate rate, and duplicate groups. | Detects repeated synthetic text without comparing against real benchmark text. |
| `text_near_duplicate_groups` | Generator-batch diversity | After synthetic-text normalization, group texts with normalized token Jaccard similarity `>= 0.90` or normalized character 5-gram Jaccard similarity `>= 0.90`. Record algorithm and threshold. | Manifest v1 text only. | Group ids, sample ids, similarity rule, and maximum pairwise similarity. | Flags repeated text patterns while making the heuristic explicit and auditable. |
| `text_feature_presence` | Generator-batch diversity | For each sample, record presence of Hebrew final forms, niqqud, numerals, punctuation, mixed Hebrew/Latin fragments, dates, and identifier-like tokens. Aggregate counts and shares by batch and by base family. | Manifest v1 text only. | Table with feature, count, share, and optional stratum. | Shows whether text-level Hebrew features relevant to OCR/HTR are present or absent. |
| `text_length_bucket_share` | Generator-batch diversity | Bucket logical text by character count and token count using packet-declared bucket edges. At minimum report shortest, median, longest, and bucket shares. | Manifest v1 text only. | Bucket table and summary statistics. | Makes text-length concentration visible without requiring manifest changes. |
| `coverage_missing_count` | Generator-batch diversity | If `rendering_coverage_report.v1` exists, count covered and missing dimensions relevant to the declared packet purpose. | Optional rendering coverage report. | Covered count, missing count, and missing ids by dimension. | Turns the optional sidecar into explicit coverage evidence without making it a release gate. |
| `reviewed_stratum_share` | Downstream review coverage | For each diversity stratum present in the batch, count reviewed samples/pages and divide by stratum sample/page count. | Downstream review ids plus manifest/catalog join. | Table with stratum, total count, reviewed count, reviewed share. | Shows which diversity strata have visual evidence and which remain unreviewed. |
| `real_synthetic_stratum_delta` | Synthetic-to-real domain shift | For each comparable real-reference stratum, subtract real share from synthetic share and report absolute difference. Use real-only and synthetic-only denominators separately. | Governed real-reference metadata, synthetic packet metrics, split policy. | Table with stratum, real count/share, synthetic count/share, signed delta, absolute delta. | Identifies where synthetic candidates over- or under-represent target real distributions. |
| `real_synthetic_missing_strata` | Synthetic-to-real domain shift | List strata present in real references but absent in synthetic candidates, and strata present in synthetic candidates but absent in real references. | Governed real-reference metadata and synthetic packet metrics. | Two lists with counts and shares. | Distinguishes real coverage gaps from synthetic-only artifacts. |
| `real_synthetic_metric_separation` | Synthetic-to-real domain shift | When S6b utility metrics exist, report real-only, synthetic-only, and mixed results separately for each comparable stratum. Do not aggregate them into one headline number. | S6b utility packet plus governed real-reference metadata. | Metric table by source type and stratum. | Prevents mixed results from hiding domain shift or synthetic artifact overfitting. |

The first twelve metrics are generator-batch or downstream review-coverage
metrics. They do not require real references and do not prove domain match. The
last three metrics require downstream governed real-reference metadata. If those
real-reference inputs are missing, record domain shift as unmeasured.

### Required Summary Views

Every S6c evidence packet should include these generator-batch views:

- sample and page counts by `template_id`, `recipe_id`, `document_family`,
  `base_family`, `degradation_preset`, `font_id`, persona/style control, and
  condition control;
- percentage share of the largest stratum for each dimension;
- number of distinct values per dimension;
- cross-tabulation for important pairs such as `base_family` x
  `degradation_preset`, `base_family` x persona/style, `base_family` x
  condition, `font_id` x `degradation_preset`, and seed range x template;
- sample count per generated seed range and contiguous sample-index range;
- duplicate or near-duplicate `text.logical_order` counts after documented
  normalization;
- length buckets for logical text, such as short, medium, and long lines or
  samples;
- presence/absence summaries for Hebrew-specific features such as final forms,
  niqqud, numerals, punctuation, mixed Hebrew/Latin/numeric fragments, dates,
  and identifiers;
- rendering coverage sidecar covered/missing dimensions when the sidecar exists;
- review-sampling coverage, when downstream review has selected samples, showing
  which strata were reviewed and which were not.

These are descriptive summaries, not pass/fail generator validation. A narrow
batch can be valid and useful for a small dry-run. It must simply be recorded as
narrow so downstream systems do not overstate its evidence.

## Synthetic-Text Normalization For Diversity Checks

Text diversity checks must be reproducible and must not weaken the manifest text
contract. The S6c synthetic-text normalization profile is only for duplicate and
near-duplicate summary metrics; it does not alter manifest text, generated page
assets, OCR/HTR ground truth, or Hebrew rendering behavior.

Use this profile for `text_duplicate_rate` and `text_near_duplicate_groups`:

- require input `text.logical_order` to already be NFC-normalized by manifest
  validation;
- normalize again with Unicode NFC as a guard before comparison;
- preserve Hebrew letters, final forms, niqqud, digits, Latin letters, and
  punctuation;
- collapse all Unicode whitespace runs to one ASCII space and trim leading and
  trailing whitespace;
- preserve character case for Hebrew and Latin fragments;
- do not strip punctuation, digits, niqqud, dates, identifiers, or Latin
  fragments because those are meaningful OCR/HTR diversity signals;
- record the normalization profile id as `s6c_text_normalization_v1` in the
  evidence packet.

Near-duplicate grouping is advisory. A packet must record whether it used token
Jaccard similarity, character 5-gram Jaccard similarity, or both, plus the exact
threshold. If the implementation cannot compute near duplicates, it should
record `text_near_duplicate_groups` as omitted and still provide
`text_duplicate_rate`.

Do not compare generated `text.logical_order` directly to real benchmark
transcriptions inside `hocrsyngen`. Any real-text comparison belongs downstream
and must include the real-reference id, split role, access boundary, leakage
check, and whether the real text is allowed to influence synthetic batch
planning.

## Repetition And Over-Representation Warnings

Warn on patterns that can bias downstream dry-runs, utility measurements, or
release planning. S6f defines requested mixes for a particular candidate-batch
profile, but S6c packets should still use these default advisory severity bands
unless a downstream packet states a stricter project-specific threshold.

Severity labels:

| Severity | Meaning | Default action |
| --- | --- | --- |
| `info` | The metric is narrow but expected for a fixture, smoke test, or explicitly scoped dry-run. | Record the limitation; do not broaden the claim. |
| `warn` | The metric could bias review, dry-run, utility, or domain-shift interpretation. | Require reviewer note or downstream packet limitation before using the batch beyond smoke rehearsal. |
| `hold` | The metric is too concentrated, too sparse, or too unreviewed for the declared purpose. | Hold downstream utility, domain-shift, or release-planning use until the mix, review evidence, or packet purpose changes. |

Default advisory bands:

| Pattern | Metric evidence | `warn` band | `hold` band |
| --- | --- | --- | --- |
| `single_template_dominance` | `largest_stratum_share` for `template_id` | `> 0.50` for a multi-template purpose | `> 0.75` for a multi-template purpose |
| `single_base_family_dominance` | `largest_stratum_share` for `base_family` | `> 0.50` for a multi-family purpose | `> 0.75` for a multi-family purpose |
| `recipe_repetition` | `largest_stratum_share` for `recipe_id` or `cross_stratum_count` for recipe/base-family | `> 0.50` outside fixture use | `> 0.75` outside fixture use |
| `degradation_skew` | `largest_stratum_share` for `degradation_preset` | `> 0.60` when multiple degradation levels are claimed | `> 0.85` when multiple degradation levels are claimed |
| `font_skew` | `largest_stratum_share` for `font_id` | `> 0.70` when printed and handwritten-like comparison is claimed | `1.00` when printed and handwritten-like comparison is claimed |
| `style_control_skew` | `largest_stratum_share` for persona/style control and non-default style counts | Non-default style stratum has `< 5` samples or largest share `> 0.80` | Non-default style stratum has `0` samples when style comparison is claimed |
| `condition_control_skew` | `largest_stratum_share` for condition control and non-default condition counts | Non-default condition stratum has `< 5` samples or largest share `> 0.80` | Non-default condition stratum has `0` samples when condition comparison is claimed |
| `seed_contiguity_risk` | `seed_span_summary` | One seed or contiguous sample-index span supplies all evidence for a broad claim | Same plus no packet limitation |
| `duplicate_text` | `text_duplicate_rate` | `> 0.05` outside fixture/smoke use | `> 0.20` outside fixture/smoke use |
| `near_duplicate_text` | `text_near_duplicate_groups` | Any group covers `> 0.10` of samples outside fixture/smoke use | Any group covers `> 0.25` of samples outside fixture/smoke use |
| `text_feature_gap` | `text_feature_presence` | Required feature share is `0` for a declared OCR/HTR purpose | Required feature share is `0` and the packet still claims coverage for that feature |
| `unreviewed_stratum` | `reviewed_stratum_share` | Important stratum review share is `0` for dry-run acceptance | Important stratum review share is `0` for utility, domain-shift, or release-planning use |
| `coverage_sidecar_gap` | `coverage_missing_count` | Relevant sidecar dimension is missing for declared coverage purpose | Missing sidecar dimension is ignored while making a coverage claim |
| `synthetic_artifact_repetition` | S6a/S3 review notes plus reviewed ids | Repeated artifact appears in more than one reviewed stratum | Repeated artifact dominates a reviewed stratum or affects primary text/layout |

For intentionally tiny batches, such as the packaged fixture or smoke tests,
warning records may be `info` when the packet purpose says the batch is not
evidence for broad diversity, utility, domain shift, caps, or release planning.

Warning reason names:

- `single_template_dominance`: one `template_id` accounts for most of the
  candidate batch when the stated purpose requires multi-family coverage;
- `single_base_family_dominance`: one `base_family` dominates even when template
  ids vary through degradation variants;
- `recipe_repetition`: one `recipe_id` or recipe/base-family pair repeats
  enough to make reviewed pages visually interchangeable;
- `degradation_skew`: one degradation preset dominates, especially strong
  degradation that could teach OCR/HTR diagnostics about synthetic artifacts
  rather than real document variation;
- `font_skew`: one packaged font id dominates when the intended comparison
  spans printed and handwritten-like families;
- `style_control_skew`: one persona/style control dominates or a non-default
  style slice is too small to support separate review;
- `condition_control_skew`: one condition control dominates or a non-default
  condition slice is too small to support separate review;
- `seed_contiguity_risk`: a small contiguous seed/sample-index range is treated
  as broader evidence than it supports;
- `duplicate_text`: identical or near-identical logical text appears repeatedly
  outside a deliberate fixture or smoke-test use case;
- `text_feature_gap`: Hebrew features relevant to the intended OCR/HTR task are
  missing from the candidate slice;
- `unreviewed_stratum`: an important diversity stratum exists but has no visual
  review evidence;
- `coverage_sidecar_gap`: the optional rendering coverage report shows missing
  dimensions relevant to the intended downstream use;
- `synthetic_artifact_repetition`: visual review notes cite repeated mechanical
  noise, layout artifacts, stamp placement, row patterns, or degradation
  artifacts across samples.

Warnings should cite stable sample ids, page ids, public provenance fields,
joined catalog fields, metric id, metric value, threshold, severity, packet
purpose, and reviewed-image references stored downstream. Do not write warning
state into manifest v1.

## Domain-Shift Evidence

Generator variety is not domain-shift evidence. Domain-shift evidence compares
synthetic candidates against governed real references or release-domain metadata
owned by `hocrgen`/HeOCR.

Valid domain-shift evidence should state:

- real-reference benchmark or release-domain id and version;
- owner of real-reference metadata and ground truth;
- split role of each real and synthetic source;
- leakage and contamination controls, including whether any generated text was
  derived from real-reference transcriptions;
- comparable strata, such as document family, base family, degradation level,
  layout density, source domain, handwriting-like versus printed class, text
  length, Hebrew feature coverage, and review category;
- distribution summaries for real-only, synthetic-only, and mixed sources
  reported separately;
- sample counts and confidence/limitation notes for sparse strata;
- whether the comparison supports a dry-run, a calibration hold, a utility
  measurement, or only a diagnostic observation.

Invalid domain-shift evidence includes:

- claiming real-domain match because many synthetic template ids are present;
- using rendering coverage alone as proof that real distributions are covered;
- comparing synthetic candidates to private real data without split, leakage,
  provenance, and governance notes;
- reporting mixed real/synthetic aggregates without separate strata;
- treating a downstream domain-shift summary as release eligibility, synthetic
  caps approval, benchmark/reference eligibility, or CER/WER utility proof.

If no governed real references exist, the correct conclusion is: domain shift is
unmeasured. The candidate batch may still have generator-batch diversity
evidence.

## Downstream Evidence Packet Fields

Store S6c evidence in `hocrgen`/HeOCR systems or future sidecars, not in
`generation_manifest.json` v1. A packet should retain:

- packet id, owner repository, date, and evaluation purpose;
- source candidate batch path or downstream import id;
- `hocrsyngen` version and public CLI command used to generate or export the
  batch;
- validation report status and path from `hocrsyngen validate PATH --format
  json`;
- manifest sample ids, page ids, template ids, recipe ids, degradation presets,
  font ids, seeds, sample indexes, source corpus ids, persona/style controls,
  and condition controls;
- `template_catalog.v2` version and joined document family, base family, page
  regions, annotation types, identifier types, layout density, and review
  features;
- optional `rendering_coverage_report.v1` path and covered/missing dimension
  summary when present;
- diversity summary tables and warning reason names;
- metric ids, metric values, denominators, grouping dimensions, warning
  thresholds, severities, and any threshold override reason;
- text normalization profile id when text duplicate or near-duplicate metrics
  are reported;
- S6a downstream realism acceptance category, reviewed ids, reviewer notes, and
  hold or rejection reasons when available;
- S6b utility packet id when a real-reference utility run exists;
- real-reference benchmark or release-domain id, version, source-domain
  description, ground-truth owner, and split policy when domain shift is being
  measured;
- leakage and contamination check summary;
- real-only, synthetic-only, and mixed distribution comparisons reported
  separately by stratum;
- limitations, sparse strata, unreviewed strata, and whether domain shift is
  measured or unmeasured;
- explicit release decision status, if any, recorded separately from diversity,
  utility, and domain-shift evidence.

When domain-shift prerequisites are missing, include this boundary:
"No synthetic-to-real domain-shift claim is made because no governed
real-reference comparison was run."

## Contamination And Leakage Concerns

Diversity and domain-shift metrics often touch benchmark metadata. Downstream
systems must keep benchmark roles explicit:

- Do not use held-out real benchmark transcriptions to generate synthetic text
  for a candidate batch that will later be compared to the same benchmark.
- Do not tune template mixes, style controls, condition controls, degradation
  presets, review thresholds, OCR/HTR preprocessing, or release caps on the same
  real-reference test split used for final claims.
- Do not report domain-shift gaps against private or unreleased real references
  without provenance, privacy, split, and access-control notes.
- Keep training, augmentation, dry-run, calibration, development, review,
  benchmark, and release-use roles separate for both real and synthetic sources.
- Report whether a synthetic stratum was used for model training, robustness
  probing, benchmark stress testing, infrastructure dry-runs, or release
  rehearsal.
- If leakage cannot be ruled out, mark the comparison diagnostic only.

## Responsibilities Outside hocrsyngen

These belong in `hocrgen` or HeOCR:

- real-reference metadata selection and stewardship;
- benchmark split policy, leakage checks, and contamination audits;
- synthetic-to-real distribution comparison reports;
- OCR/HTR utility runs and CER/WER calculations;
- release profiles, synthetic caps, source composition, balancing, review
  workflow, dedupe, privacy, release assembly, export, publication, and public
  dataset payload decisions;
- dashboards, persistent evidence packets, and any machine-readable review or
  domain-shift workflow state.

These may remain in `hocrsyngen`:

- deterministic candidate generation;
- manifest v1 validation;
- public CLI reports and packaged fixture export;
- template catalog metadata and optional rendering coverage reports;
- docs that define handoff expectations, diversity dimensions, and boundary
  language for downstream evidence.

## Relationship To S6 Follow-Ups

Later S6 work should use this contract without moving downstream governance into
`hocrsyngen`:

- `S6d` defines release cap handoff policy so diversity and domain-shift
  evidence cannot override source-composition limits in
  [release_cap_handoff_policy.md](release_cap_handoff_policy.md).
- `S6e` defines review evidence sidecars for durable reviewed ids, rejection
  reasons, visual evidence, S6a category references, S6c warning references,
  and S6d cap decision references outside manifest v1 in
  [review_evidence_sidecar_contract.md](review_evidence_sidecar_contract.md).
- `S6f` defines candidate batch profiles and mix handoff so diversity summaries
  can be compared against an intended requested mix in
  [candidate_batch_profile_mix_handoff.md](candidate_batch_profile_mix_handoff.md).
- `S6g` should document the external `hocrgen` adapter checklist for installed
  CLI import, validation, governance, dry-run rehearsal, and evidence-packet
  retention.
