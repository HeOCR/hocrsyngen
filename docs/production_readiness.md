# Production Readiness Plan

This document makes the current readiness state explicit. It records what is
ready in `hocrsyngen`, what remains before generated batches can become
governed dataset inputs, and which roadmap items should carry the work.

## Current State After S6g

The last merged roadmap item is `S6g` - `hocrgen` adapter handoff checklist,
squash-merged in PR #54. `S6f` - candidate batch profile and mix handoff was
squash-merged in PR #53. `S6e` - review evidence sidecar contract was
squash-merged in PR #52. `S6d` - release cap handoff policy was squash-merged
in PR #51. `S6c` - synthetic diversity and domain-shift metrics - was
squash-merged in PR #50. `S6b` - downstream utility measurement contract - was
squash-merged in PR #49. `S6a` - downstream realism acceptance rubric - was
squash-merged in PR #48. `S5e` - close S5 planning and activate S6 evaluation
gates - was squash-merged in PR #47. At this point
`hocrsyngen` can generate and validate deterministic candidate synthetic Hebrew
OCR/HTR batches through public CLI surfaces:

- `hocrsyngen templates --format json`
- `hocrsyngen templates --format json --catalog-version v2`
- `hocrsyngen contracts --format json`
- `hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json`
- `hocrsyngen generate --count N --seed S --output PATH --format json`
- `hocrsyngen generate --count N --seed S --output PATH --rendering-coverage-report --format json`
- `hocrsyngen validate PATH --format json`
- `hocrsyngen evidence-run --count N --seed S`
- `hocrsyngen wet-gallery RUN_ROOT --output RUN_ROOT/gallery`
- `hocrsyngen wet-analyze RUN_ROOT --format json`
- `hocrsyngen wet-review-template RUN_ROOT --output RUN_ROOT/review/human_review.csv --format json`
- `hocrsyngen wet-review-validate RUN_ROOT REVIEW_PATH --format json`

The generator has governed templates including the S3f `ledger` family, stronger
degradation variants, style bundles, condition bundles, manifest v1 validation,
installed-package contract fixtures, Hebrew RTL/NFC rendering tests, S5a
acceptance criteria for future handwriting research, an S5b allograph and
character-level prototype plan, and an S5c word and line assembly prototype
plan, and an S5d learned-generation packaging boundary. S5 closes through the
documented deferral path: this repository has planning gates and boundaries, but
no accepted S5 prototype/evaluation evidence, ablation result, or downstream
utility measurement. A valid generated directory is still a candidate synthetic
input, not a release-ready dataset artifact.

For operator handoff runs, `hocrsyngen evidence-run` packages the catalog,
fixture export, generation, validation, rendering coverage, checksum inventory,
and candidate-only report capture into a single progress-logged command. It is
still generator evidence only: it does not create release eligibility, review
state, caps, export payloads, publication metadata, or downstream governance.

For human inspection of wet-test runs, `hocrsyngen wet-gallery` renders a static
HTML gallery over an existing `wet-run` artifact. It shows generated page images
or links plus public manifest metadata and logical Hebrew text. It is an offline
developer review aid only: it does not add warning metrics, human review
sidecars, release eligibility, export payloads, publication metadata, or
downstream governance.

For deterministic code analysis of wet-test runs, `hocrsyngen wet-analyze`
emits a `wet_analysis_report.v1` JSON report over an existing `wet-run`
artifact. It computes source-backed coverage, duplicate text, repeated id,
asset dimension, blank/near-blank image smoke, ink-density, catalog join, and
path/hash safety metrics while keeping hard blockers separate from warning
findings. It is generator-quality evidence only: it does not claim realism
acceptance, OCR/HTR utility, domain match, release eligibility, export
payloads, publication metadata, or downstream governance.

For human review of wet-test runs, `hocrsyngen wet-review-template` writes a
deterministic CSV or JSON Lines worksheet that lists every sample/page id from
the validated batches plus the documented review fields, decision states,
severity levels, and reason codes. `hocrsyngen wet-review-validate` then
validates a completed worksheet against the run's manifest-derived sample/page
ids and the known decision/severity/reason-code vocabulary. Both commands are
human-evidence aids only: they do not add review workflow state, schemas, LLM
triage, release eligibility, export payloads, publication metadata, or
downstream governance, and they do not change `generation_manifest.json` v1.

S6a adds downstream realism acceptance categories, calibrated example classes,
visual evidence expectations, rejection reasons, and release-eligibility
boundaries for `hocrgen`/HeOCR. S6b documents the utility measurement evidence
contract, but no CER/WER or OCR/HTR utility claim is established by this
repository until downstream governed real-reference evaluations are actually run.
S6c documents generator-batch diversity summaries, repeated-pattern warnings,
and downstream synthetic-to-real comparison requirements without adding
generator behavior or moving governance into this repository. S6d documents how
public `hocrsyngen` metadata and S6a/S6b/S6c evidence support downstream
`hocrgen`/HeOCR cap decisions without implementing caps, balancing, source
composition, release eligibility, export, publication, or governance enforcement
in this repository. S6e documents a portable optional review evidence sidecar
contract for retaining reviewed sample/page ids, visual evidence, reviewer
observations, decision categories, reason codes, and S6a/S6c/S6d references
outside `generation_manifest.json` v1. S6f documents a candidate batch profile
and mix handoff contract for requested, generated/observed, reviewed,
capped/admitted, and released mix layers outside manifest v1. S6g documents the
external `hocrgen` adapter handoff checklist for installed CLI import,
validation, public JSON boundary assertions, catalog joins, id/path retention,
optional S6a-S6f evidence links, failure handling, and downstream-only
governance responsibilities. Phase S6 is complete through S6g. The current
planning track is Phase S7, starting with design-only `S7a` script abstraction.
`S7a` is documented in [script_abstraction_design.md](script_abstraction_design.md)
and should preserve Hebrew-first behavior while identifying minimal future
RTL-script profile boundaries. It must not implement Arabic support, broaden
validation semantics, change manifest v1, or move downstream governance into
`hocrsyngen`.

## Crucial Missing Pieces

These items should be treated as required before using synthetic batches in a
governed dataset flow.

| Item | Owner | Roadmap tracking | Notes |
| --- | --- | --- | --- |
| `hocrgen` import/governance adapter | `hocrgen` | External dependency `H1a`; hocrsyngen supports it through completed S6 handoff docs including `S6g` | The adapter should consume installed CLI JSON and validated manifests, not private Python internals. |
| Release profiles and synthetic caps | `hocrgen` | External dependency `H1b`; hocrsyngen tracks handoff policy in `S6d` | Caps, balancing, source composition, review state, release eligibility, release assembly, export, and publication must stay out of `hocrsyngen`. |
| Review evidence sidecar | Shared contract, downstream use in `hocrgen` | `S6e` | Done in PR #52; defines durable reviewed sample/page ids, reviewer notes, visual evidence references, S6a category references, S6c warning references, and S6d cap decision references without changing manifest v1. |
| Candidate batch profile and mix handoff | Shared contract, orchestration in `hocrgen` | `S6f` | Done in PR #53; defines how template/style/condition/seed mixes are requested, observed, reviewed, capped, and audited outside manifest v1. |
| `hocrgen` adapter handoff checklist | Shared checklist, implementation in `hocrgen` | `S6g` | Done in PR #54; documents installed CLI import, validation, public JSON assertions, catalog joins, id retention, optional evidence links, failure handling, and downstream-only governance responsibilities. |
| Downstream acceptance, utility, diversity, and cap gates | `hocrgen`/HeOCR with `hocrsyngen` metadata support | `S6a`, `S6b`, `S6c`, `S6d` | `S6a` documents downstream realism acceptance categories, evidence expectations, rejection reasons, and the distinction between generator-quality review and release eligibility. `S6b` defines the utility measurement evidence contract and keeps CER/WER claims gated on real references downstream. `S6c` defines diversity and domain-shift evidence boundaries so repeated synthetic patterns and target-domain gaps are visible before dry-runs, utility evaluations, or release planning. `S6d` defines how those evidence packets feed cap decisions without overriding source-composition policy. |

## High-Lift Quality Work

These items are not blockers for candidate generation, but they are expected to
produce large quality or operational gains.

| Item | Roadmap tracking | Expected lift |
| --- | --- | --- |
| Rendering coverage report artifact | `S2e` | Makes Hebrew feature, template, degradation, style, and condition coverage inspectable outside manifest v1. |
| Richer template/catalog metadata | `S3e` | Lets downstream tools filter by document family, page regions, annotations, identifiers, density, and base family through a stable public boundary. |
| Additional governed document families | `S3f` | Done in PR #42; expands visual diversity beyond the earlier families and should help reduce overfitting to narrow synthetic layouts. |
| Handwriting realism research | `S5a` through `S5e`, future S5 follow-up, Phase S9 real-glyph composition, or external `hocrgen`/HeOCR work | Biggest expected visual-realism lift for handwritten-like OCR/HTR samples, but S5 produced planning gates and boundaries only. S5a is done in PR #43, S5b is done in PR #44, S5c is done in PR #45, S5d is done in PR #46, and S5e closes S5 by deferring remaining prototype/evaluation evidence out of the baseline package. The likely external resolution path is `Phase S9` real-glyph composition from `HeOCR/hletterscript` letter sets rather than ML-backed synthesis; that work is design-only and gated on `hletterscript` reaching a populated baseline corpus. |
| Real-glyph composition from `HeOCR/hletterscript` | `Phase S9` (design-only `S9a` today), gated on upstream `hletterscript` data readiness | Replaces today's TTF "handwritten-like" approximation with deterministic file-based composition of real per-writer Hebrew letter glyphs. Adds `generation_manifest.v2`, glyph-aware validation, and wet-test extensions while preserving the manifest v1 contract for existing batches. Documented in [real_glyph_composition_plan.md](real_glyph_composition_plan.md). |
| Downstream realism acceptance rubric | `S6a` | Done in PR #48; gives `hocrgen`/HeOCR reviewers a shared acceptance vocabulary for generated candidate batches before utility, caps, and review sidecar contracts are implemented. |
| Downstream utility measurement | `S6b` | Done in PR #49; defines how `hocrgen`/HeOCR must prove whether synthetic batches improve CER/WER or expose model weaknesses against real references before any utility claim is made. |
| Diversity and domain-shift metrics | `S6c` | Done in PR #50; helps detect synthetic over-representation, repeated artifacts, and gaps versus real Hebrew document distributions. |
| Release cap handoff policy | `S6d` | Done in PR #51; defines how public `hocrsyngen` metadata and S6a/S6b/S6c evidence support downstream cap decisions while keeping cap ownership, balancing, source composition, release eligibility, export, publication, and governance enforcement in `hocrgen`/HeOCR. |
| Review evidence sidecar contract | `S6e` | Done in PR #52; defines a portable optional downstream evidence packet for reviewed ids, decision categories, reason codes, visual references, limitations, and links to S6a/S6c/S6d evidence without creating review workflow state in this repo. |
| Candidate batch profile and mix handoff | `S6f` | Done in PR #53; defines a portable optional downstream planning record for requested, generated/observed, reviewed, capped/admitted, and released candidate mixes without creating generator behavior, release profiles, or governance state in this repo. |
| `hocrgen` adapter handoff checklist | `S6g` | Done in PR #54; turns the S6a-S6f evidence contracts into an external downstream adapter consumption checklist without implementing adapter behavior or schemas in this repo. |
| Wet-testing and generator-quality evidence | `S8a` through `S8i` | Active S8 work; `S8a` defines developer-owned smoke/review/soak wet-test evidence, `S8b` adds the deterministic smoke run artifact generator, `S8c` adds the candidate evidence-run wrapper, `S8d` adds the human-first static gallery, `S8e` adds deterministic warning metrics, `S8f` adds the human review worksheet template and validator, `S8g` adds the bounded LLM triage packet export, and `S8h` adds the `wet-report` command that aggregates run metadata, analysis warnings, optional human review, and optional LLM triage notes into a single developer-facing generator-quality report with a hardcoded non-release statement, without creating release-governance behavior, LLM dependencies, network calls, or manifest v1 changes. |

## Current Planning Track

`S7a` script abstraction design is complete in
[script_abstraction_design.md](script_abstraction_design.md). Phase S8 is the
current implementation track for wet testing and generator-quality evidence.
Phase S9 (real-glyph composition from `HeOCR/hletterscript`) is design-only;
`S9a` is documented in
[real_glyph_composition_plan.md](real_glyph_composition_plan.md) and remaining
S9 implementation slices are gated on `HeOCR/hletterscript` reaching a
populated, validated baseline corpus.
`S8a` defines the program in
[wet_testing_program_plan.md](wet_testing_program_plan.md), `S8b` is the
first implementation slice, `S8c` adds the downstream preflight evidence-run
wrapper, `S8d` adds the static gallery for human inspection of wet-test
outputs, `S8e` adds deterministic warning metrics over existing wet-test runs,
`S8f` adds the human review worksheet template and validator over existing
wet-test runs, and `S8g` adds the `wet-llm-packet` command that exports a
bounded Markdown prompt and structured JSON metadata packet for operator-run
LLM advisory review without adding LLM API clients, network calls, or
pass/fail authority. The deterministic wet-test, evidence-run, gallery,
analysis, review, and triage-packet commands reuse public generation and
validation behavior, retain public reports, and write or emit operator
evidence artifacts. This is not a production-readiness blocker or
release-readiness claim for current Hebrew candidate generation; generated
batches remain candidate synthetic inputs until downstream `hocrgen`
governance admits them.

## External hocrgen Dependency Labels

The following dependency labels are not `hocrsyngen` PR notation. They are short
names for cross-repository work that must be tracked in `hocrgen` or HeOCR
planning:

- `H1a` - Implement `hocrsyngen` installed-CLI import adapter in `hocrgen`.
- `H1b` - Define `hocrgen` release profiles, synthetic caps, and balancing rules.
- `H1c` - Add `hocrgen` review workflow support for candidate synthetic batches
  and S6e review evidence sidecar records.
- `H1d` - Run downstream utility and domain-shift evaluations against real
  references when references are available.

`hocrsyngen` may document the contract and provide fixtures, but it must not
implement these governance workflows in the baseline package.


## Recommended First Production Rehearsal

Use a dry-run flow before any real dataset release decision:

1. Export the packaged fixture through `hocrsyngen contracts export` and validate
   it from the installed package.
2. Generate a small candidate batch that covers all governed template ids and at
   least one non-default style or condition bundle.
3. Validate the batch with `hocrsyngen validate PATH --format json`.
4. Import the validated batch into a `hocrgen` dry-run adapter using only the
   manifest and public CLI reports.
5. Apply manual generator-quality review using
   `docs/visual_inspection_rubric.md`, then apply downstream realism acceptance
   using `docs/downstream_realism_acceptance_rubric.md`, recording notes outside
   `generation_manifest.json` v1.
6. If utility is being rehearsed, apply
   `docs/downstream_utility_measurement_contract.md`: require governed real
   references, ground truth, split/leakage controls, metric definitions, and
   synthetic-to-real comparison before any CER/WER or OCR/HTR utility claim is
   made.
7. If diversity or domain shift is being rehearsed, apply
   `docs/synthetic_diversity_domain_shift_metrics.md`: summarize candidate
   diversity from public manifest/catalog/coverage surfaces, record
   repeated-pattern warnings, and require governed real-reference comparison
   before any synthetic-to-real domain-shift claim is made.
8. Apply `docs/release_cap_handoff_policy.md` for any release rehearsal: record
   the downstream release profile, decision status, synthetic percentage and
   absolute limits, per-family/style/condition/source caps, reviewer state,
   reason codes, leakage checks, and limitations outside
   `generation_manifest.json` v1. Only a non-release infrastructure smoke test
   may omit cap rehearsal, and it should record `diagnostic_only` plus an
   explicit limitation that release caps were not evaluated.
9. Apply `docs/review_evidence_sidecar_contract.md` when visual review evidence
   is retained: cite reviewed sample/page ids, public provenance/catalog fields,
   reviewer state, decision category, rejection or hold reason codes, visual
   evidence references, S6a category references, S6c warning references, S6d cap
   decision references, limitations, and unreviewed strata outside
   `generation_manifest.json` v1.
10. Apply `docs/candidate_batch_profile_mix_handoff.md` when a downstream
   dry-run or release rehearsal has an intended candidate mix: record requested,
   generated/observed, reviewed, capped/admitted, and released layers
   separately; cite public `hocrsyngen` dimensions and S6a/S6c/S6d/S6e evidence
   references; and keep profile ownership, balancing, caps, release profiles,
   and governance in `hocrgen`/HeOCR.
11. Apply `docs/hocrgen_adapter_handoff_checklist.md` when implementing or
   rehearsing the external `hocrgen` adapter: assert public JSON boundaries,
   retain canonical manifest ids and relative asset paths, join
   `(template_id, recipe_id)` to `template_catalog.v2`, preserve source batch
   boundaries for S6f profiles, and fail closed on missing validation, assets,
   hashes, catalog joins, or required S6 evidence.
12. Record which missing metadata, diversity evidence, utility evidence, review
   evidence, caps, or mix controls would have changed the decision. Feed those
   gaps into `S2e`, `S3e`, completed S6 handoff docs, or external `hocrgen`
   dependencies before scaling batch size. Script-abstraction questions should
   feed `S7a` only when they concern design boundaries rather than downstream
   adapter implementation or governance.

This rehearsal should prove integration behavior and expose review gaps. It
should not publish or export release-ready dataset payloads.
