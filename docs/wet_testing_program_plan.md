# hocrsyngen Wet-Testing Program Plan

This document defines a developer-owned wet-testing program for `hocrsyngen`.
It is a sub-plan for generator-quality evidence, manual inspection, LLM-assisted
triage, and regression discovery. It is not a release-governance plan and does
not make generated batches release-ready dataset artifacts.

The plan is intentionally staged. The first implementation should not build a
large evaluation platform. It should define the evidence contract, then add only
the smallest tooling that helps developers and reviewers inspect real generated
outputs.

## Status

- Document status: planning proposal.
- Owner: `hocrsyngen` developers.
- Current scope: Phase S8 implementation guidance. `S8b` adds the first
  deterministic smoke run artifact generator; `S8c` adds the operator
  evidence-run wrapper needed for downstream `hocrgen` preflight evidence;
  `S8d` adds the human-first static gallery over existing wet-test runs; `S8e`
  adds deterministic warning metrics over an existing wet-test run; later human
  review, LLM triage, reporting, schema, and CI work remains deferred.
- Roadmap placement: Phase S8 - Wet Testing And Generator-Quality Evidence.
  `S8a` defines this program plan; `S8b` is the first actual implementation
  slice and adds the wet-test smoke run artifact generator; `S8c` adds the
  candidate evidence-run handoff wrapper; `S8d` adds the human-first static
  gallery; `S8e` adds deterministic warning metrics.

## Core Principle

Wet testing should answer this question:

Can `hocrsyngen` developers inspect, explain, and improve real generated Hebrew
OCR/HTR candidate batches using reproducible code evidence, human visual review,
and optional LLM-assisted triage?

Wet testing should not answer these questions:

- Is this batch accepted for public dataset release?
- Does this batch satisfy `hocrgen` release profiles or synthetic caps?
- Does this batch improve OCR/HTR CER/WER against governed real references?
- Should `generation_manifest.json` v1 carry downstream review, release,
  provider, adapter, or governance metadata?

Those questions remain downstream `hocrgen`/HeOCR responsibilities.

## Review Issues And Recommended Fixes

This plan replaces an earlier over-broad wet-testing outline. The following
review issues were raised against that outline, and each issue has a concrete
fix in this document.

### Issue 1: Too Much Machinery Up Front

Problem:

The earlier plan started with many commands, schemas, galleries, LLM packets,
human sidecars, reports, profiles, and regression promotion. That is too much
surface area before the team knows which evidence will actually be useful.

Recommended fix:

- Start with a planning document and evidence contract.
- Add one narrow harness command before adding analyzers, galleries, LLM packet
  generation, or report aggregation.
- Keep every follow-up slice independently useful and reviewable.
- Defer versioned schemas until real runs have exercised the JSON shape.

Applied plan:

The implementation sequence below starts with documentation, then a reproducible
run artifact generator, then a human-first gallery, then deterministic warning
metrics, then human review, then optional LLM triage, then reports, then
regression promotion.

### Issue 2: Invented `WT*` Notation Outside The Roadmap

Problem:

The earlier plan invented `WT1`, `WT2`, and similar names without establishing
whether wet testing belongs under S6, S7, or a new roadmap phase. That would
create planning drift.

Recommended fix:

- Do not treat `WT*` labels as PR notation.
- Use descriptive slice names inside this document only.
- Before code lands, update `docs/roadmap.md` with real repository notation.
- If the work is post-S6 evaluation evidence, explicitly say so.
- If the work is S7 support, tie it to S7 scope and Hebrew regression gates.

Applied plan:

This document uses descriptive implementation slices, and `docs/roadmap.md`
maps them to durable Phase S8 roadmap notation. The current planning PR is
`S8a`; the first implementation PR is `S8b`. The rejected pattern is ad hoc
`WT*` notation that bypasses the roadmap.

### Issue 3: Wet Testing Was Not Defined Clearly Enough

Problem:

The earlier plan mixed visual realism, Hebrew correctness, downstream readiness,
code metrics, LLM review, human review, and regression fixture mining without
defining what wet testing means.

Recommended fix:

Define wet testing as three distinct evidence loops:

- Code validation: deterministic checks that can run repeatedly and eventually
  become automated tests.
- Human review: the primary qualitative judgment of visual plausibility,
  Hebrew readability, layout problems, and artifact severity.
- LLM triage: optional advisory review that helps find suspicious examples for
  human inspection, never a pass/fail authority.

Applied plan:

This document separates smoke, review, and soak levels; separates code, human,
and LLM responsibilities; and defines explicit acceptance semantics for each
evidence type.

### Issue 4: LLM Review Was Over-Promoted

Problem:

LLM review can help find likely issues, but it is not reliable enough to be a
major validation pillar or a pass/fail gate.

Recommended fix:

- LLM review is optional and advisory.
- Baseline package dependencies must not include LLM clients, network calls, or
  hosted-model dependencies.
- The repository may export packets/prompts that an operator can review with an
  LLM outside the baseline package.
- Human review overrides LLM review whenever they disagree.

Applied plan:

LLM work is delayed until after harness, gallery, metrics, and human review
exist. It is scoped to packet export and structured advisory notes only.

### Issue 5: Human Review Was Too Vague

Problem:

"Human review sidecar" is not a plan. Human review needs sampling rules, reason
codes, decision semantics, and a clear path from finding to fix.

Recommended fix:

- Define sampling levels and minimum coverage expectations.
- Define decision states: `pass`, `hold`, and `reject`.
- Define severity: `P0`, `P1`, `P2`, and `info`.
- Define reason codes aligned with existing visual inspection and S6 realism
  language.
- Define what happens when a human reviewer finds a defect.

Applied plan:

The human review section below defines sampling, decisions, severity, reason
codes, required fields, and escalation behavior.

### Issue 6: Acceptance Criteria Were Missing

Problem:

The earlier plan named artifacts without saying what a successful wet-test run
means.

Recommended fix:

Define acceptance criteria per wet-test level:

- Smoke level: hard code gates only.
- Review level: code gates plus human review coverage.
- Soak level: code gates plus stability and repeated-pattern evidence.

Applied plan:

The acceptance criteria section below defines hard blockers, warning classes,
and human-review thresholds.

### Issue 7: Too Many Schemas Too Early

Problem:

Versioned schemas for every wet-test artifact may be useful later, but adding
schemas before real review cycles risks freezing poor shapes.

Recommended fix:

- Start with documented JSON examples and tests.
- Use explicit report version strings in generated artifacts.
- Promote an artifact to a schema only after at least one real human review
  cycle proves the shape is stable.

Applied plan:

The first implementation slice should create JSON artifacts with report version
strings and tests, but not new schema files. Schema promotion is a later slice.

### Issue 8: Smoke, Review, And Soak Levels Were An Afterthought

Problem:

The earlier plan mentioned smoke/review/soak late. These levels should drive
the design from the beginning because they define cost, expected evidence, and
CI suitability.

Recommended fix:

- Define three levels first.
- Keep smoke small and CI-compatible.
- Make review human-friendly and curated.
- Keep soak local/offline and explicitly non-CI by default.

Applied plan:

The wet-test levels below define scale, intended audience, artifact set, and
acceptance expectations before any tooling is proposed.

## Non-Goals

Wet testing must not add:

- `hocrgen` imports or private `hocrgen` coupling.
- Network, REST, scraping, hosted LLM, GPU, diffusion, Torch, TensorFlow, or
  other deep-learning dependencies to baseline package dependencies.
- Release-governance, dataset-export, review-workflow, cap-enforcement, or
  publication behavior.
- Changes to `generation_manifest.json` v1.
- Mutations to packaged contract fixtures unless a separate intentional fixture
  regeneration PR updates tests and docs.
- Arabic support, broader validation semantics, or script abstraction behavior.
- Claims of release eligibility, real authorship, medical status,
  psychological status, disability status, demographic status, or real-person
  handwriting imitation.

## Evidence Roles

### Code Validation

Code validation should be deterministic and repeatable. It should catch facts
that software can judge without pretending to judge realism.

Examples:

- Manifest schema validity.
- Asset path safety.
- Asset existence and SHA-256 integrity.
- JPEG readability and dimensions.
- Hebrew text NFC normalization.
- Logical-order text preservation.
- RTL/language/script metadata.
- Template/catalog join completeness.
- Coverage of requested template/style/condition/degradation strata.
- Duplicate text or repeated sample warnings.
- Blank or near-blank rendered image warnings.
- Ink-density and contrast smoke warnings.
- Possible clipping or overlap warnings where reliable enough.

Code validation can create hard failures for contract and integrity problems.
Visual-realism concerns should usually be warnings unless they are directly
measurable and already proven reliable.

### Human Review

Human review is the primary qualitative signal.

Human reviewers should judge:

- Hebrew readability.
- Layout plausibility.
- Obvious clipping or overlap.
- Whether degradation hides required text.
- Whether stamps, identifiers, ruled regions, tables, marginalia, or other
  visible structures remain inspectable.
- Whether generated examples feel too repetitive for the requested wet-test
  purpose.
- Whether metadata matches the visible page.
- Whether an example should become a regression fixture.

Human review should not judge release eligibility. It should judge generator
quality and defect severity from the `hocrsyngen` developer perspective.

### LLM Triage

LLM triage is optional and advisory.

LLM review may help identify:

- Pages likely to contain clipping.
- Pages likely to contain obvious visual artifacts.
- Repetitive-looking layouts.
- Metadata/image mismatches.
- Examples worth prioritizing for human review.

LLM review must not:

- Decide pass/fail alone.
- Override human review.
- Add baseline package dependencies.
- Send data over a network from baseline package code.
- Claim OCR/HTR utility or release readiness.

The repository may generate a packet and prompt for an operator to use with an
LLM outside the baseline package.

## Wet-Test Levels

### Level 1: Smoke

Purpose:

Fast sanity coverage suitable for local PR validation and possibly future CI.

Scale:

- Small fixed seed set.
- Every governed template at least once.
- Default style and condition.
- A tiny number of non-default style/condition examples.
- No human or LLM review required.

Expected artifacts:

- Generated batch.
- `generation_manifest.json`.
- Generation report when requested.
- Validation report.
- `template_catalog.v2`.
- Optional rendering coverage report.
- Wet-test run manifest.
- Checksums for retained reports.

Acceptance:

- All CLI commands complete successfully.
- Manifest validates.
- Assets exist.
- Paths are relative portable POSIX paths and do not contain `..`.
- Hashes match.
- Catalog joins are complete.
- No blank/near-blank hard blocker is detected.
- Warnings are allowed but must be summarized.

### Level 2: Review

Purpose:

Curated developer/human inspection of visual quality and Hebrew plausibility.

Scale:

- All governed templates.
- All supported style bundles.
- All supported condition bundles.
- Representative degradation variants.
- Multiple fixed seeds.
- Sample count sized for practical human review, not for statistical claims.

Expected artifacts:

- Everything from smoke.
- Static gallery.
- Human review worksheet or sidecar.
- Optional LLM triage packet.
- Wet-test metrics summary.

Acceptance:

- Smoke hard gates pass.
- Human review covers the required sample matrix.
- No unresolved `P0` human review findings.
- `P1` findings are either fixed, explicitly deferred, or converted into
  follow-up issues/roadmap items.
- Repeated warnings are summarized with examples.
- No release-readiness claim is made.

### Level 3: Soak

Purpose:

Larger deterministic local run for repeated-pattern detection, broad coverage,
and regression discovery.

Scale:

- Larger seed set.
- Larger count per governed template family.
- Style/condition/degradation combinations selected to avoid combinatorial
  explosion while still covering pairwise interactions.
- Not required in normal CI.

Expected artifacts:

- Everything from smoke.
- Aggregate wet-test metrics.
- Duplicate/repetition summaries.
- Coverage matrix.
- Top warning examples.
- Optional sampled gallery.

Acceptance:

- Smoke hard gates pass.
- Coverage holes are explained.
- Duplicate/repetition warnings are quantified.
- Top recurring warning classes are linked to examples.
- Any generator-quality blocker produces a follow-up PR, issue, or explicit
  deferral.

## Sampling Rules

Sampling should be deterministic and explainable.

Required dimensions:

- Template id.
- Recipe id.
- Document family.
- Style/persona control.
- Condition control.
- Degradation preset.
- Font id.
- Seed.
- Hebrew text feature class when detectable from existing public surfaces.

Initial smoke profile:

- Count: small, for example 7 to 14 pages.
- Seeds: one or two fixed seeds.
- Coverage: every governed template at least once.
- Controls: default style/condition plus at least one non-default combination.

Initial review profile:

- Count: human-manageable, for example 40 to 80 pages.
- Seeds: at least three fixed seeds.
- Coverage: every governed template, every supported style, every supported
  condition, and every stronger degradation template/preset.
- Sampling: pairwise combinations rather than full Cartesian explosion.

Initial soak profile:

- Count: larger local run, for example 250 to 1000 pages.
- Seeds: documented fixed range.
- Coverage: broad template/style/condition/degradation coverage.
- Sampling: deterministic stratified plan.

The exact counts should be finalized in the first implementation PR after
measuring runtime, artifact size, and gallery usability.

## Human Review Decisions

Decision states:

- `pass`: acceptable for generator-quality evidence in the wet-test context.
- `hold`: not clearly acceptable; needs another reviewer, more evidence, or a
  targeted generator fix.
- `reject`: unacceptable generator output for the tested scenario.

Severity:

- `P0`: hard blocker. The example shows an integrity, safety, or severe
  generator-quality failure.
- `P1`: serious defect. The batch should not be treated as a clean wet-test
  success until fixed or explicitly deferred.
- `P2`: moderate defect or repeated quality concern.
- `info`: observation, not a defect.

Initial reason codes:

- `invalid_manifest`
- `unsafe_asset_path`
- `missing_asset`
- `hash_mismatch`
- `blank_or_near_blank_page`
- `hebrew_not_readable`
- `text_clipped`
- `text_overlap`
- `layout_implausible`
- `degradation_obscures_text`
- `metadata_image_mismatch`
- `catalog_join_problem`
- `excessive_repetition`
- `style_condition_not_distinct`
- `forbidden_claim_risk`
- `reviewer_uncertain`

Required human review fields:

- Wet-test run id.
- Sample id.
- Page id.
- Asset path.
- Reviewer identifier or initials.
- Decision.
- Severity.
- Reason codes.
- Notes.
- Whether this example should become a regression fixture.

## LLM Triage Packet

The LLM packet should be generated only after a gallery and human review format
exist.

Packet contents:

- A sampled subset of pages.
- Page metadata already available through public `hocrsyngen` surfaces.
- Code warning summaries.
- The visual inspection rubric excerpt or pointer.
- A prompt that asks for likely issues and prioritization, not pass/fail.

Required prompt constraints:

- Do not judge release readiness.
- Do not infer real identity, medical status, psychological status, disability
  status, demographic status, or real authorship.
- Do not override human review.
- Mark uncertain findings as uncertain.
- Report only visible or metadata-supported concerns.

LLM output should be stored separately from human review:

- `llm_triage_notes.md` or equivalent operator-supplied artifact.
- Optional structured notes in a later slice after real use stabilizes the
  shape.

## Artifact Model

Initial wet-test output should be a directory, not a new manifest version.

Example shape:

```text
out/wet-tests/RUN_ID/
  batch/
    generation_manifest.json
    assets/
      ...
  reports/
    generation_report.json
    validation_report.json
    template_catalog_v2.json
    rendering_coverage_report.json
    wet_test_run.json
    wet_test_checksums.txt
  gallery/
    index.html
  review/
    human_review.csv
    llm_packet.json
    llm_prompt.md
  summary/
    wet_test_metrics.json
    wet_test_summary.md
```

Only the first implementation slice needs `wet_test_run.json` and checksums.
Other files appear in later slices.

The wet-test run artifact should record:

- Report version string.
- Command line.
- Package version.
- Python version.
- Platform summary.
- Pillow/libraqm availability.
- Seed set.
- Count.
- Requested profile.
- Output paths relative to the run root.
- Generated report paths.
- Validation report paths.
- Catalog report path.
- Optional rendering coverage report path.
- Checksums for retained reports.

Do not add these fields to `generation_manifest.json` v1.

## Acceptance Criteria

### Hard Blockers

A wet-test run fails its hard gate when any of these occur:

- CLI command failure.
- Manifest validation failure.
- Missing `generation_manifest.json`.
- Missing asset referenced by manifest.
- Absolute asset path.
- Asset path containing `..`.
- Asset hash mismatch.
- Catalog join failure for `(template_id, recipe_id)`.
- Non-NFC manifest text.
- Missing Hebrew script/language/direction metadata.
- Baseline package requires a forbidden dependency.

### Warning Conditions

A wet-test run may pass hard gates but still report warnings:

- Duplicate text or high repeated-line rate.
- Low coverage of requested strata.
- Possible blank/near-blank page.
- Possible clipping or overlap.
- Low contrast or excessive degradation.
- Style/condition examples that do not look visually distinct.
- Human `P2` observations.
- LLM advisory concerns.

Warnings must be summarized and linked to examples.

### Human Review Acceptance

A review-level wet-test run is acceptable when:

- Hard blockers are absent.
- Required human sampling coverage is complete.
- No `P0` finding remains unresolved.
- Each `P1` finding has one of:
  - a linked fix PR,
  - a linked follow-up issue or roadmap item,
  - an explicit deferral with reason.
- The report states that the result is generator-quality evidence only.

## Implementation Sequence

### S8a: Planning And Roadmap Placement

Purpose:

Decide where wet-testing implementation belongs in the roadmap before adding
new commands or artifacts.

Recommended changes:

- Add Phase S8 roadmap notation for wet-testing and generator-quality evidence.
- Map the first implementation slice to `S8b`.
- Keep implementation out of this planning slice.
- Keep manifest v1 unchanged.

Exit criteria:

- Roadmap notation exists for `S8a` and `S8b`.
- Scope boundaries are explicit.
- First code slice is named and bounded as `S8b`.

### S8b: Reproducible Wet-Test Run Artifact

Purpose:

Create the smallest useful wet-test harness.

Potential command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli wet-run --profile smoke --seed 17 --output out/wet-tests/smoke-17
```

Implemented smoke command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli wet-run --profile smoke --seed 17 --output out/wet-tests/smoke-17 --format json
```

The initial `smoke` profile generates one page for each governed template id
using the existing generation path, then generates one supplemental non-default
style/condition page under `control_batches/non_default_style_condition/`.
Both batches are validated through the existing validation path. The command
writes retained public reports under `reports/`:

- `generation_report.json`
- `validation_report.json`
- `non_default_style_condition_generation_report.json`
- `non_default_style_condition_validation_report.json`
- `template_catalog_v2.json`
- `wet_test_run.json`
- `wet_test_checksums.txt`

With `--rendering-coverage-report`, the generated batch also retains
`batch/rendering_coverage_report.json` and records it in `wet_test_run.json`.

The initial `wet_test_run.json` shape is documented rather than schema-backed:

```json
{
  "report_version": "wet_test_run.v1",
  "profile": "smoke",
  "status": "passed",
  "command_line": ["hocrsyngen", "wet-run", "--profile", "smoke", "--seed", "17", "--output", "out/wet-tests/smoke-17", "--format", "json"],
  "package": {"name": "hocrsyngen", "version": "0.1.0"},
  "environment": {"python_version": "3.12.11", "python_executable": "...", "platform": "...", "pillow_raqm": true},
  "config": {
    "seed": 17,
    "total_count": 8,
    "primary_count": 7,
    "supplemental_count": 1,
    "primary_template_ids": ["printed_letter", "handwritten_note", "archive_card", "ledger", "printed_letter_heavy_scan", "handwritten_note_heavy_wear", "archive_card_faded_scan"],
    "supplemental_controls": [
      {
        "batch_id": "non_default_style_condition",
        "template_ids": ["printed_letter"],
        "persona": "style_open_drift_v1",
        "condition": "condition_low_contrast_v1"
      }
    ],
    "primary_rendering_coverage_report": false,
    "output_path": ".",
    "batch_path": "batch"
  },
  "reports": {
    "template_catalog_v2_path": "reports/template_catalog_v2.json",
    "checksum_path": "reports/wet_test_checksums.txt",
    "checksum_file_includes_wet_test_run": true
  },
  "generated_batch": {
    "batch_id": "default_governed_templates",
    "manifest_path": "batch/generation_manifest.json",
    "sample_count": 7,
    "page_count": 7,
    "asset_paths": ["batch/assets/.../page_0001.jpg"]
  },
  "supplemental_batches": [
    {
      "batch_id": "non_default_style_condition",
      "manifest_path": "control_batches/non_default_style_condition/generation_manifest.json",
      "sample_count": 1,
      "page_count": 1,
      "template_ids": ["printed_letter"],
      "persona": "style_open_drift_v1",
      "condition": "condition_low_contrast_v1"
    }
  ],
  "validation": {"valid": true, "sample_count": 8, "page_count": 8},
  "artifact_checksums": {"batch/generation_manifest.json": "..."},
  "checksum_contract": {
    "algorithm": "sha256",
    "artifact_checksums_exclude": ["reports/wet_test_run.json", "reports/wet_test_checksums.txt"],
    "checksum_file_includes": ["batch/generation_manifest.json", "reports/wet_test_run.json"]
  },
  "scope": {
    "generator_quality_evidence_only": true,
    "release_ready_dataset_artifact": false,
    "manifest_v1_changed": false,
    "hocrgen_behavior_added": false,
    "human_review_included": false,
    "llm_triage_included": false
  }
}
```

If generation, report writing, or validation fails before a successful run can
be published, the command writes a failed `reports/wet_test_run.json` at the
requested output path with `status: "failed"`, `validation.valid: false`, and
the exception type/message. Successful runs are built in a temporary sibling
directory and renamed into place only after all retained artifacts are written.

Implementation outline:

- Add a CLI subcommand only if it can stay dependency-light and deterministic.
- Generate a smoke-profile batch using existing generator paths.
- Run or invoke existing validation logic.
- Capture `template_catalog.v2`.
- Optionally capture rendering coverage when requested.
- Write `wet_test_run.json`.
- Write checksums for retained reports and artifacts. The machine-readable
  `artifact_checksums` object intentionally excludes `wet_test_run.json`; the
  checksum sidecar includes the final `wet_test_run.json` digest.

Do not add:

- Gallery generation.
- Human review sidecars.
- LLM packet generation.
- New schemas.
- hocrgen integration behavior.

Tests:

- Smoke run creates expected directories and reports.
- Paths inside wet-test metadata are relative to the run root.
- Existing validation behavior is reused.
- The command does not mutate packaged fixtures.
- The command does not change manifest v1.

### S8c: Candidate Evidence-Run Handoff

Purpose:

Create the single-command operator wrapper needed when another repository, such
as `hocrgen`, needs a validated candidate batch plus enough public evidence to
inspect it without importing `hocrsyngen` internals.

Implemented command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli evidence-run --count 20 --seed 101 --format json
```

The command exports and validates the packaged contract fixture, captures
template and contract JSON reports, generates and validates a candidate batch,
writes optional rendering coverage, records `SHA256SUMS`, writes `RUN_NOTES.md`,
and emits `candidate_evidence_run_report.v1`. The report must keep
`release_eligible: false`; downstream `hocrgen` remains responsible for import
metadata, review, caps, release profiles, export, and publication governance.

Do not add:

- hocrgen adapter code or imports.
- Review, cap, export, release, or publication behavior.
- Manifest v1 fields.
- Network, LLM, GPU, or diffusion dependencies.

Tests:

- Evidence run creates the expected reports, checksum inventory, notes, and
  generated manifest.
- Installed package and wheel CLI smoke tests cover the command.
- Generated batch assets remain relative and portable.
- Release eligibility remains false.

### S8d: Human-First Static Gallery

Purpose:

Make generated wet-test output easy to inspect without reading raw JSON.

Potential command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli wet-gallery out/wet-tests/smoke-17 --output out/wet-tests/smoke-17/gallery
```

Implementation outline:

- Render dependency-light static HTML.
- Show page images and links to full images with relative, portable paths.
- Show sample id, page id, template id, recipe id, style, condition,
  degradation, font id, and manifest text.
- Escape HTML text and metadata safely, including logical-order Hebrew manifest
  text.
- Include warning sections only after source-backed warning metrics exist in a
  later S8 slice.
- Do not create human review sidecars, LLM triage packets, warning metrics,
  wet-test reports, schemas, hocrgen behavior, or manifest v1 changes.

Tests:

- Gallery generation succeeds for a generated fixture.
- Gallery paths are relative and portable.
- HTML escapes text and metadata.
- Gallery generation does not require network.

### S8e: Deterministic Warning Metrics

Purpose:

Add code metrics that can become regression tests.

Potential command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli wet-analyze out/wet-tests/smoke-17 --format json
```

Initial metrics:

- Coverage matrix.
- Duplicate text rate.
- Repeated sample/page warnings.
- Asset dimensions.
- Blank/near-blank smoke.
- Ink-density range.
- Catalog join completeness.
- Path/hash safety summary.

Implementation notes:

- Read an existing `wet_test_run.json`.
- Validate referenced batches and treat validation, hash, image-readability, and
  unsafe-path failures as hard blockers, not warning findings.
- Join manifests to `template_catalog.v2` by `template_id` and `recipe_id`.
- Emit a `wet_analysis_report.v1` JSON report on stdout; do not add a schema
  until real review cycles prove the shape is stable.
- Keep all metrics source-backed and explicitly scoped as generator-quality
  evidence only.

Do not claim:

- Realism acceptance.
- OCR/HTR utility.
- Release readiness.
- Domain match with real data.

Tests:

- Metrics are deterministic for a fixed fixture.
- Metrics flag intentionally corrupted or degenerate test fixtures.
- Metrics distinguish hard blockers from warnings.

### S8f: Human Review Sidecar

Purpose:

Record human qualitative judgments without changing manifest v1.

Potential command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli wet-review-template out/wet-tests/review-101 --output out/wet-tests/review-101/review/human_review.csv
```

Implementation outline:

- Generate CSV or JSON Lines template from manifest and gallery metadata.
- Use the decision states, severity levels, and reason codes from this document.
- Validate completed review files for required fields and known reason codes.
- Summarize pass/hold/reject counts.

Tests:

- Template includes all required sample/page ids.
- Review validation rejects unknown page ids.
- Review validation rejects unknown decision states or reason codes.
- Review validation does not change manifest v1.

### S8g: LLM Triage Packet Export

Purpose:

Prepare optional operator-run LLM review without adding LLM dependencies.

Potential command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli wet-llm-packet out/wet-tests/review-101 --output out/wet-tests/review-101/review
```

Implementation outline:

- Select a bounded sample from the gallery/run.
- Emit metadata and paths to images.
- Emit a Markdown prompt with constraints.
- Do not call any LLM API.
- Do not require network.

Tests:

- Packet is deterministic for fixed input.
- Packet size limits are enforced.
- Prompt includes no release-readiness language.
- Prompt includes forbidden-claim constraints.

### S8h: Wet-Test Report

Purpose:

Combine code metrics, human review, and optional LLM notes into a developer
summary.

Potential command:

```bash
PYTHONPATH=src python -m hocrsyngen.cli wet-report out/wet-tests/review-101
```

Report contents:

- Run metadata.
- Coverage matrix.
- Hard blockers.
- Warning summary.
- Human review summary.
- Optional LLM triage summary.
- Top examples by reason code.
- Suggested regression promotions.
- Follow-up recommendations.
- Explicit non-release statement.

Tests:

- Report fails when hard blockers exist.
- Report marks missing human review as incomplete for review profile.
- Report treats LLM notes as advisory.
- Report includes non-release disclaimer.

### S8i: Regression Promotion

Purpose:

Turn wet-test findings into durable automated tests.

Implementation outline:

- Add documented criteria for promoting a wet-test example.
- Add helper command or script only after manual process stabilizes.
- Keep promoted fixtures small.
- Prefer generated minimal fixtures over large committed assets.
- Link promoted tests to reason codes.

Examples:

- Clipping finding becomes a deterministic clipping smoke test.
- Duplicate text finding becomes duplicate-rate guard.
- Catalog mismatch becomes contract test.
- Excessive degradation finding becomes per-template visual smoke threshold.

### Later S8 Follow-Up: Schema Promotion And CI Profile

Purpose:

Stabilize artifacts only after real use.

Implementation outline:

- Promote `wet_test_run.json`, metrics, or report JSON to schemas only after
  real review cycles prove the shapes are stable.
- Add smoke profile to CI only if runtime and native rendering dependencies are
  stable.
- Keep review and soak profiles out of normal CI.

## First Implementation Recommendation

The first code PR should be the reproducible run artifact generator, not the
gallery, metrics engine, LLM packet, or report aggregator.

Recommended first code slice:

```text
S8b: Add wet-test smoke run artifact generator
```

Scope:

- One smoke-profile command.
- Reuse existing generation and validation behavior.
- Persist public CLI-style reports and checksums.
- Write documented `wet_test_run.json`.
- Add focused tests.
- No schemas yet.
- No human review.
- No LLM packet.
- No hocrgen behavior.
- No manifest v1 changes.

Why this is first:

- It creates reproducible evidence for every later step.
- It is small enough to review.
- It avoids freezing a bad report schema too early.
- It keeps the project inside current architectural boundaries.

## What To Ask Human Reviewers To Do

For the first review-level wet test, the reviewer should:

1. Open the gallery.
2. Inspect all examples with code warnings.
3. Inspect at least one example from every governed template.
4. Inspect at least one example from every supported style bundle.
5. Inspect at least one example from every supported condition bundle.
6. Inspect stronger degradation variants.
7. Mark each reviewed page as `pass`, `hold`, or `reject`.
8. Add reason codes for every `hold` or `reject`.
9. Mark examples that should become regression fixtures.
10. Avoid release-readiness language.

## How To Use Wet-Test Results

Use wet-test evidence to:

- Decide whether generator changes need follow-up.
- Find small deterministic regression tests.
- Improve visual inspection guidance.
- Find template/style/condition coverage gaps.
- Produce public-safe generator-quality evidence for downstream consumers.

Do not use wet-test evidence to:

- Publish datasets.
- Admit synthetic data into a release.
- Bypass `hocrgen` governance.
- Claim OCR/HTR utility.
- Claim real-world domain match.

## Open Decisions Before Code

Before implementing `S8b`, decide:

- Exact smoke profile size.
- Exact review profile size.
- Whether the first command should be a top-level CLI subcommand or a
  developer script.
- Whether generated galleries should be HTML, Markdown, or both.
- Whether human review should start as CSV, JSON Lines, or both.
- Which warnings are hard blockers in smoke profile.
- Which warnings remain advisory until human review validates them.

## Done Definition For This Program

The wet-testing program is mature enough for regular developer use when:

- A smoke run can be generated and validated deterministically.
- A human reviewer can inspect a gallery without reading raw JSON.
- Code metrics highlight likely quality issues without making unsupported
  realism claims.
- Human review findings can be recorded outside manifest v1.
- Optional LLM triage can be run without baseline LLM dependencies.
- A report can summarize hard blockers, warnings, human findings, and follow-up
  recommendations.
- At least one wet-test finding has been promoted into an automated regression
  test.
