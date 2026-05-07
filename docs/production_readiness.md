# Production Readiness Plan

This document makes the current readiness state explicit. It records what is
ready in `hocrsyngen`, what remains before generated batches can become
governed dataset inputs, and which roadmap items should carry the work.

## Current State After S5d

The last merged roadmap item is `S5d` - optional learned-generation packaging
boundary, squash-merged in PR #46. At this point
`hocrsyngen` can generate and validate deterministic candidate synthetic Hebrew
OCR/HTR batches through public CLI surfaces:

- `hocrsyngen templates --format json`
- `hocrsyngen templates --format json --catalog-version v2`
- `hocrsyngen contracts --format json`
- `hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json`
- `hocrsyngen generate --count N --seed S --output PATH --format json`
- `hocrsyngen validate PATH --format json`

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

## Crucial Missing Pieces

These items should be treated as required before using synthetic batches in a
governed dataset flow.

| Item | Owner | Roadmap tracking | Notes |
| --- | --- | --- | --- |
| `hocrgen` import/governance adapter | `hocrgen` | External dependency `H1a`; hocrsyngen supports it through S6 handoff docs | The adapter should consume installed CLI JSON and validated manifests, not private Python internals. |
| Release profiles and synthetic caps | `hocrgen` | External dependency `H1b`; hocrsyngen tracks handoff policy in `S6d` | Caps, balancing, review state, release assembly, export, and publication must stay out of `hocrsyngen`. |
| Review evidence sidecar | Shared contract, downstream use in `hocrgen` | `S6e` | Needed for durable reviewed sample ids, rejection reasons, and inspection evidence without changing manifest v1. |
| Candidate batch profile and mix handoff | Shared contract, orchestration in `hocrgen` | `S6f` | Defines how template/style/condition/seed mixes are requested, recorded, capped, and audited. |
| Downstream acceptance and utility gates | `hocrgen`/HeOCR with `hocrsyngen` metadata support | `S6a`, `S6b`, `S6c`, `S6d` | Needed to separate valid generation from release eligibility and measured OCR/HTR utility. |

## High-Lift Quality Work

These items are not blockers for candidate generation, but they are expected to
produce large quality or operational gains.

| Item | Roadmap tracking | Expected lift |
| --- | --- | --- |
| Rendering coverage report artifact | `S2e` | Makes Hebrew feature, template, degradation, style, and condition coverage inspectable outside manifest v1. |
| Richer template/catalog metadata | `S3e` | Lets downstream tools filter by document family, page regions, annotations, identifiers, density, and base family through a stable public boundary. |
| Additional governed document families | `S3f` | Done in PR #42; expands visual diversity beyond the earlier families and should help reduce overfitting to narrow synthetic layouts. |
| Handwriting realism research | `S5a` through `S5e`, future S5 follow-up, or external `hocrgen`/HeOCR work | Biggest expected visual-realism lift for handwritten-like OCR/HTR samples, but S5 produced planning gates and boundaries only. S5a is done in PR #43, S5b is done in PR #44, S5c is done in PR #45, S5d is done in PR #46, and S5e closes S5 by deferring remaining prototype/evaluation evidence out of the baseline package. |
| Downstream utility measurement | `S6b` | Proves whether synthetic batches improve CER/WER or expose model weaknesses against real references. |
| Diversity and domain-shift metrics | `S6c` | Helps detect synthetic over-representation, repeated artifacts, and gaps versus real Hebrew document distributions. |

## External hocrgen Dependency Labels

The following dependency labels are not `hocrsyngen` PR notation. They are short
names for cross-repository work that must be tracked in `hocrgen` or HeOCR
planning:

- `H1a` - Implement `hocrsyngen` installed-CLI import adapter in `hocrgen`.
- `H1b` - Define `hocrgen` release profiles, synthetic caps, and balancing rules.
- `H1c` - Add `hocrgen` review workflow support for candidate synthetic batches
  and any future review sidecar.
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
5. Apply manual review using `docs/visual_inspection_rubric.md`, recording notes
   outside `generation_manifest.json` v1.
6. Record which missing metadata, review evidence, caps, or mix controls would
   have changed the decision. Feed those gaps into `S2e`, `S3e`, `S6e`, and
   `S6f` before scaling batch size.

This rehearsal should prove integration behavior and expose review gaps. It
should not publish or export release-ready dataset payloads.
