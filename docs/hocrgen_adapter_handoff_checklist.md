# hocrgen Adapter Handoff Checklist

This S6g document is an external implementation checklist for a future
`hocrgen` adapter that consumes `hocrsyngen` candidate synthetic batches. It is
documentation and planning only. It does not add adapter code, generator
behavior, manifest fields, schemas, packaged fixture changes, dependencies,
review workflow state, release caps, export behavior, publication behavior,
governance enforcement, release eligibility, or utility claims to
`hocrsyngen`.

The checklist tells downstream implementers how to consume `hocrsyngen` through
installed CLI commands, `generation_manifest.json` v1, public JSON reports,
`template_catalog.v2`, optional rendering coverage, and S6a-S6f evidence
contracts. It references the S6f candidate batch profile and mix handoff
contract instead of inventing new requested, observed, reviewed, capped, or
released profile fields.

## Ownership Boundary

`hocrsyngen` owns:

- deterministic candidate synthetic Hebrew OCR/HTR generation;
- `generation_manifest.json` v1 validation;
- public installed CLI commands and JSON reports;
- packaged contract fixture export;
- `template_catalog.v1` and `template_catalog.v2`;
- optional `rendering_coverage_report.v1`;
- planning docs that define evidence boundaries and public handoff
  expectations.

`hocrgen`/HeOCR own:

- adapter implementation, import ids, dry-run ids, batch ids, and audit ids;
- storage, access controls, review queues, visual evidence storage, and
  reviewer workflow state;
- release profiles, synthetic caps, balancing, source composition, and source
  admission policy;
- dedupe, privacy, leakage checks, benchmark/reference handling, and split
  policy;
- downstream realism acceptance, utility measurement, diversity/domain-shift
  comparison, cap records, and candidate profile records;
- release assembly, export, publication, public payload decisions, and
  governance enforcement.

No downstream adapter result should treat a valid `hocrsyngen` batch as a
release-ready dataset payload.

## Stable Installed CLI Inputs

Adapter tests and dry-runs should call the installed CLI. They should not import
private Python modules, dataclasses, recipes, drawing helpers, package resource
paths, or generated filenames that are not serialized in public reports.

Required command surfaces:

```bash
hocrsyngen templates --format json
hocrsyngen templates --format json --catalog-version v2
hocrsyngen contracts --format json
hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json
hocrsyngen generate --count N --seed S --output PATH --format json
hocrsyngen generate --count N --seed S --output PATH --rendering-coverage-report --format json
hocrsyngen validate PATH --format json
```

The adapter may also record the exact command strings used for audit. Command
strings are evidence, not governance approval.

## Public JSON Boundary Assertions

Adapter assertions should happen at public JSON boundaries.

For `hocrsyngen templates --format json`, assert:

- `schema_version == "template_catalog.v1"`;
- `templates` is a list;
- every template entry exposes the v1 public fields documented in
  [hocrgen_integration.md](hocrgen_integration.md).

For `hocrsyngen templates --format json --catalog-version v2`, assert:

- `schema_version == "template_catalog.v2"`;
- the payload validates against the public v2 schema when `hocrgen` vendors or
  references that schema;
- each v1 template field remains present;
- each template exposes `document_family`, `base_family`, `page_regions`,
  `annotation_types`, `identifier_types`, `layout_density`, and
  `review_features`;
- validated manifest `(template_id, recipe_id)` pairs can join to v2 catalog
  entries without private internals.

For `hocrsyngen contracts --format json`, assert:

- `schema_version == "contract_fixture_catalog.v1"`;
- fixture id `generation_manifest_v1_fixture_batch` is present;
- the fixture contract is `generation_manifest.v1`.

For `hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json`, assert:

- `schema_version == "contract_fixture_export.v1"`;
- `fixture_id == "generation_manifest_v1_fixture_batch"`;
- `contract == "generation_manifest.v1"`;
- the exported manifest exists at `PATH/generation_manifest.json`;
- the exported fixture validates through `hocrsyngen validate PATH --format
  json`.

For `hocrsyngen generate --count N --seed S --output PATH --format json`,
assert:

- `schema_version == "generation_report.v1"`;
- `sample_count == N`;
- `page_count >= sample_count`;
- `output_path` echoes the CLI argument string;
- `manifest_path == "PATH/generation_manifest.json"` using the CLI argument
  string.

For `hocrsyngen generate --count N --seed S --output PATH --rendering-coverage-report --format json`, assert the generation report fields above plus:

- `rendering_coverage_report_path == "PATH/rendering_coverage_report.json"`;
- the sidecar exists and has `report_version ==
  "rendering_coverage_report.v1"`;
- the sidecar is retained as advisory coverage evidence outside manifest v1.

For `hocrsyngen validate PATH --format json`, assert on success:

- `schema_version == "validation_report.v1"`;
- `valid == true`;
- `sample_count` and `page_count` match the manifest;
- `path` echoes the original CLI argument string.

For invalid validation with `--format json`, assert:

- the process exits non-zero;
- `schema_version == "validation_report.v1"`;
- `valid == false`;
- `path` echoes the original CLI argument string;
- `error` is a non-empty deterministic string.

## Import Flow Checklist

Use this sequence for the first `hocrgen` adapter dry-run:

1. Export the packaged fixture through `hocrsyngen contracts export`.
2. Validate the exported fixture through `hocrsyngen validate PATH --format
   json`.
3. Import the fixture using only `generation_manifest.json` v1, page assets,
   and public CLI reports.
4. Generate a small candidate batch through the installed CLI.
5. Validate the candidate batch before import.
6. Preserve manifest `sample_id` values exactly.
7. Preserve manifest `pages[].page_id` values exactly.
8. Preserve manifest `pages[].asset_path` values as relative portable POSIX
   paths and resolve them only under the validated batch root.
9. Recompute or verify asset hashes according to `hocrgen` policy after
   validation, and record the policy used.
10. Join each manifest `(provenance.template_id, provenance.recipe_id)` pair to
    `template_catalog.v2`.
11. Retain generation, fixture export, validation, and template catalog reports
    as downstream audit evidence.
12. Optionally retain `rendering_coverage_report.v1` when generated.
13. Assign downstream import ids and dry-run ids without replacing canonical
    manifest ids.
14. Record source batch boundaries before aggregating multiple generated runs.
15. Apply S6a-S6f evidence contracts as downstream evidence, not as
    `hocrsyngen` manifest extensions.

When S6f profile/mix evidence is needed, use
[candidate_batch_profile_mix_handoff.md](candidate_batch_profile_mix_handoff.md)
for the requested, generated/observed, reviewed, capped/admitted, and released
layers. Do not define alternate profile semantics in the adapter.

## Evidence Links

The adapter should preserve links to downstream evidence packets without making
those packets part of manifest v1.

| Evidence | Planning source | Adapter use |
| --- | --- | --- |
| Downstream realism acceptance | [downstream_realism_acceptance_rubric.md](downstream_realism_acceptance_rubric.md) | Link reviewed batch/sample/page decisions and rejection reasons after generator-quality review. |
| Utility measurement packet | [downstream_utility_measurement_contract.md](downstream_utility_measurement_contract.md) | Link CER/WER or OCR/HTR utility evidence only when governed real references, ground truth, splits, leakage controls, and metric definitions exist. |
| Diversity/domain-shift packet | [synthetic_diversity_domain_shift_metrics.md](synthetic_diversity_domain_shift_metrics.md) | Link diversity summaries, repeated-pattern warnings, unreviewed strata, and synthetic-to-real comparison evidence. |
| Release cap decision record | [release_cap_handoff_policy.md](release_cap_handoff_policy.md) | Link cap admission, reduction, hold, or rejection decisions owned by `hocrgen`/HeOCR. |
| Review evidence sidecar | [review_evidence_sidecar_contract.md](review_evidence_sidecar_contract.md) | Link reviewed sample/page ids, visual evidence references, reviewer notes, decision categories, reason codes, and limitations. |
| Candidate batch profile/mix record | [candidate_batch_profile_mix_handoff.md](candidate_batch_profile_mix_handoff.md) | Link requested, observed, reviewed, capped/admitted, and released mix layers without redefining S6f fields. |

## Failure Handling Checklist

The adapter should fail closed or mark the import unusable for the stated
downstream purpose when these conditions appear:

- validation JSON is missing, malformed, invalid, or reports `valid == false`;
- `generation_manifest.json` is missing;
- referenced assets are missing;
- asset hash verification fails or is skipped without a recorded downstream
  policy;
- manifest asset paths are absolute, contain backslashes, contain drive
  prefixes, escape the batch root, or contain `..`;
- required manifest fields are absent or unknown under manifest v1 validation;
- template, recipe, degradation preset, font id, source corpus, persona/style,
  or condition controls are unknown to the installed `hocrsyngen` public
  surfaces;
- `(template_id, recipe_id)` cannot be joined to `template_catalog.v2` when
  downstream logic needs document family, base family, layout density, or
  review features;
- source batch boundaries are missing for an S6f profile that aggregates
  multiple generated runs, styles, conditions, seeds, templates, or requested
  strata;
- S6a downstream realism evidence is missing for a purpose that requires
  reviewed realism acceptance;
- S6b utility evidence is missing when OCR/HTR utility claims or utility-based
  release decisions are requested;
- S6c diversity/domain-shift evidence is missing when broad coverage,
  target-domain match, repeated-pattern, or synthetic-to-real comparison claims
  are requested;
- S6d cap decision records are missing for release-cap rehearsal or release
  planning;
- S6e review evidence sidecars or equivalent downstream review records are
  missing for reviewed-mix, cap, or release-governance claims;
- S6f candidate batch profile records are missing when a requested mix,
  observed-vs-requested gap, cap rehearsal, or release planning claim depends
  on them.

Failure records should keep the original public ids and command/report
references that explain the failure. They should not patch manifests, rewrite
assets, or infer missing metadata from private `hocrsyngen` internals.

## Downstream-Only Responsibilities

The adapter implementation belongs in `hocrgen`, not `hocrsyngen`. The following
responsibilities must remain downstream:

- import ids, dry-run ids, review ids, cap decision ids, profile ids, release
  ids, and audit storage;
- storage layout, access controls, retention, and visual evidence stores;
- review workflow, reviewer assignment, reviewer permissions, reviewer notes,
  and state transitions;
- release profiles, synthetic caps, cap enforcement, balancing, source
  composition, and source admission decisions;
- dedupe, privacy review, leakage checks, benchmark/reference handling, split
  policy, and contamination handling;
- candidate batch orchestration across multiple `hocrsyngen generate`
  invocations;
- downstream realism acceptance, utility measurement, diversity/domain-shift
  comparison, review sidecar storage, cap records, and S6f profile storage;
- release assembly, export, publication, public dataset payload formation, and
  governance enforcement.

## Future Implementation Notes

S6g should not add adapter code in `hocrsyngen`. If downstream implementation
needs a machine-readable schema for imports, profiles, cap records, or adapter
state, that schema belongs in `hocrgen` or in a future explicitly scoped
versioned contract. It should not be added opportunistically to manifest v1 or
to the baseline generator package.

S7 script-abstraction work should start only after S6 is closed or a specific
S6 carry-forward is explicitly recorded. Adapter gaps found during S6g should be
tracked as downstream `hocrgen` dependencies unless they require a public
`hocrsyngen` contract change.
