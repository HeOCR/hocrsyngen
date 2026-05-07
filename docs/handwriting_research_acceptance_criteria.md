# Handwriting Research Acceptance Criteria

This S5a document defines acceptance criteria for future Hebrew handwriting
research in `hocrsyngen`. It is planning guidance only. It does not add
generator behavior, manifest fields, schemas, fixtures, dependencies, review
workflow state, release policy, export behavior, or publication behavior.

## Scope Boundary

Handwriting research may explore higher-quality synthetic Hebrew handwritten
appearance, including allograph variation, character-level shape variation,
word and line assembly, geometric perturbation, writer-style consistency as a
synthetic control, and optional learned generation designs.

Research work is acceptable in `hocrsyngen` only when it stays inside one of
these boundaries:

- Human-readable design notes, experiment plans, evaluation reports, or
  prototype findings under `docs/`.
- Lightweight deterministic prototypes that do not affect baseline package
  installation, public CLI behavior, or existing generated output unless a
  later roadmap PR explicitly approves implementation.
- Optional experiments, extras, or separate packages designed before use for
  heavier methods.
- Stable public integration notes for `hocrgen` that use CLI reports,
  `generation_manifest.json` v1, template catalogs, and explicitly versioned
  sidecars only.

Research work is not acceptable when it adds release governance, review
workflow, synthetic caps, dedupe, export, publication, network collection,
scraping, or `hocrgen` adapter implementation to this repository.

Use this location boundary for future S5 PRs:

| Location | S5a acceptance | Notes |
| --- | --- | --- |
| `docs/` | Allowed for research plans, acceptance criteria, experiment reports, evaluation notes, and prototype findings. | This is the default home for S5 planning and evidence. |
| `.agent-plan.md`, `docs/roadmap.md`, `llms.txt`, README/docs indexes | Allowed for concise state, roadmap, and navigation updates. | Keep these surfaces short; do not duplicate full experiment reports. |
| `src/hocrsyngen/` | Not allowed for exploratory prototype code. | Code may move here only in a later implementation PR that explicitly promotes the method, preserves baseline dependency policy, updates tests/docs, and keeps public contracts compatible. |
| `src/hocrsyngen/data/` | Not allowed for unapproved research assets or reference handwriting. | Bundled assets require documented provenance, license, redistribution permission, and an intentional package-data decision. |
| `tests/` | Allowed only for contract, docs-consistency, or promoted implementation coverage. | Do not add tests that require private data, network access, heavyweight models, or exploratory assets. |
| `experiments/`, `prototypes/`, or optional extras | Allowed only after the PR defines the directory/package boundary and excludes it from baseline install assumptions. | These paths do not exist today; creating one requires an explicit plan for dependencies, artifacts, and cleanup. |

Prototype code is acceptable only when the PR answers all of these questions:

- Where does the prototype live, and why is that location outside baseline
  package behavior?
- Which public contract, if any, can observe it?
- Which commands reproduce it from a clean checkout?
- Which dependencies are needed, and are they absent from baseline runtime and
  test requirements?
- Which generated artifacts are disposable, and which are intended to become
  documented evidence?

## Baseline Package Boundary

S5 research must protect the lightweight baseline package described in
[ADR 0003](decisions/0003-baseline-dependency-policy.md).

Allowed baseline behavior:

- Keep runtime dependencies limited to the accepted lightweight local
  rendering and validation stack unless a future ADR changes the policy.
- Keep test dependencies aligned with the documented test extra.
- Use deterministic local algorithms when they are intentionally promoted in a
  later implementation PR.
- Keep optional research artifacts outside the default generated batch unless
  a versioned public sidecar is designed and tested.

Forbidden baseline behavior:

- Adding network, REST, scraping, GPU, LLM, diffusion, Torch, TensorFlow, or
  other deep-learning dependencies to baseline runtime or test dependencies.
- Requiring heavyweight compute, downloaded models, remote services, or private
  data to run baseline tests or CLI commands.
- Changing public CLI output, `generation_manifest.json` v1,
  `template_catalog.v2`, or packaged fixtures as a side effect of exploratory
  work.

## Reproducibility Requirements

Every research direction needs enough detail for another maintainer to rerun or
reject the experiment without hidden state.

Minimum requirements:

- Record the experiment goal, method, input assets, commands, environment,
  dependency boundary, and expected output artifacts.
- Record all seeds and deterministic controls used for sample selection,
  allograph choice, perturbation, degradation, style, condition, page assembly,
  and evaluation sampling.
- Keep source text in logical-order UTF-8 Hebrew, NFC-normalized, with RTL
  metadata when it becomes generated sample text.
- Use portable relative POSIX paths for any generated or referenced batch
  assets that participate in a manifest or sidecar.
- Make randomness explicit through seedable local generators. Hidden global
  random state is not acceptable for promoted prototypes.
- Document non-deterministic components separately. A method that cannot be
  reproduced must remain exploratory and cannot proceed to baseline
  implementation.

Proceeding beyond S5a requires a small reproducibility packet in the relevant
S5b/S5c/S5d PR: commands, seeds, control ids or parameters, input asset
provenance, and evaluation evidence.

## Licensing And Provenance Requirements

Any font, text, image, handwriting reference, model, generated intermediate, or
derived asset used by handwriting research must have explicit provenance and
license notes before it is committed, bundled, or cited as evaluation evidence.

Acceptance criteria:

- Bundled assets must have documented source, author or publisher when known,
  license, redistribution permission, and any attribution requirement.
- Text corpora must be compatible with synthetic generation use and must not
  introduce private or sensitive source text.
- Handwriting references must be licensed for the intended research use. They
  must not be used to imitate a living person or imply real authorship.
- Learned-generation models or weights, if ever considered, require license,
  training-data provenance, redistribution, commercial-use, privacy, and
  derivative-output analysis before any repository integration.
- Generated assets remain `PROJECT-SYNTHETIC` only when their inputs and
  derivation support that claim.

Reject a research direction when provenance is missing, licensing is ambiguous,
redistribution is incompatible, or reference data cannot be used without
implying real-source authorship.

## Forbidden Claims

Handwriting research must follow
[ADR 0005](decisions/0005-persona-style-condition-semantics.md).

Public docs, metadata, CLI reports, manifests, sidecars, filenames, and review
notes must not claim or imply:

- Real-writer identity, real authorship, source provenance, or living-person
  imitation.
- Medical, psychological, disability, demographic, sensitive-attribute, or
  human-state labels.
- That synthetic style consistency identifies a person, group, diagnosis,
  ability, demographic, or source collection.
- Release eligibility, review acceptance, or publication readiness.

Allowed wording should describe neutral observable rendering or generation
parameters: slant, spacing, baseline drift, stroke-width proxy, ink density,
allograph family, line discipline, character variability, scan contrast,
blur, and geometric perturbation.

## Manifest V1 Compatibility

S5 research must preserve `generation_manifest.json` v1 unless a later roadmap
item explicitly designs and tests a versioned contract update.

Compatibility criteria:

- Existing manifest v1 fields, constants, path rules, text metadata, provenance
  requirements, and controls semantics remain unchanged.
- `controls.persona` and `controls.condition` remain nullable string synthetic
  control slots, not identity, health, authorship, review, provenance, or
  release metadata.
- Richer handwriting-control metadata must first be exposed through a
  documented catalog, explicit sidecar, or future manifest/schema version.
- Packaged contract fixtures must not be mutated for exploratory research.
- `hocrgen` integration must continue to use installed CLI reports, manifests,
  catalogs, and documented sidecars, not private Python internals.

If an S5 prototype needs metadata that manifest v1 cannot represent, the PR
must document the gap and keep the metadata outside manifest v1 until a
versioned public surface is approved.

## Visual Review Gates

S5 prototypes must pass the S3 visual inspection expectations where applicable
and add handwriting-specific review notes before they can proceed.

A handwriting research sample is visually acceptable when:

- Hebrew text remains readable enough for a reviewer to identify intended
  lines, words, and major characters.
- RTL layout is coherent and text is not visually reversed, split into isolated
  glyphs, clipped, or displaced from its intended line.
- Character variation, allographs, slant, spacing, baseline drift, and
  perturbation read as plausible handwriting-like variation rather than
  repeated mechanical distortion.
- Word and line assembly preserve logical-order ground truth and do not create
  impossible spacing, overlaps, or broken joins that hide the primary text.
- Degradation and handwriting variation together do not erase document-family
  structure or primary content.
- Any repeated style profile is synthetic and bounded by neutral control ids or
  parameters.

Reject or stop a prototype when generated pages are unreadable, mechanically
repetitive, visibly reversed, clipped, dominated by artifacts, inconsistent
with Hebrew layout expectations, or likely to be mistaken for real-writer
imitation.

## Evaluation Dossier And Downstream Utility Gates

S5 work may report generator-quality evidence in this repository, but
downstream dataset acceptance and OCR/HTR utility remain `hocrgen`/HeOCR
responsibilities.

Before a research direction can proceed beyond docs-only planning, the PR must
include a minimum evaluation dossier:

- Evaluation question: state whether the work targets visual realism, Hebrew
  readability, OCR/HTR utility, diversity, domain-shift reduction, or robustness
  to degradation.
- Reproduction packet: list commands, seeds, control ids or parameters, input
  assets, environment assumptions, and output artifact locations.
- Comparison baseline: compare against current `handwritten_note`, style
  bundles, condition bundles, or a no-perturbation ablation.
- Sample coverage: include enough seed/template/control coverage to expose the
  changed behavior and at least one failure case or rejection example when one
  is found.
- Visual review evidence: record reviewed sample ids, page ids, template ids,
  review notes, and rejection reasons outside `generation_manifest.json` v1.
- Licensing/provenance evidence: cite every font, text, image, handwriting
  reference, model, or generated intermediate used by the experiment.
- Claim boundary: state which claims are supported and which are explicitly not
  supported, especially when real references or downstream ground truth are
  unavailable.

CER/WER utility is valid only when downstream ground truth references exist.

Use this decision gate for S5b/S5c/S5d follow-up:

| Decision | Required evidence |
| --- | --- |
| Proceed to a prototype PR | Reproduction packet, dependency boundary, asset provenance, comparison baseline, and visual review plan are complete. |
| Proceed from prototype toward baseline implementation | Prototype evidence is reproducible, visually acceptable, contract-compatible, dependency-compatible, and improves or clarifies the comparison baseline without forbidden claims. |
| Hold as docs-only research | Evidence is useful but lacks real-reference evaluation, sufficient visual review, stable asset provenance, or a clear public-contract path. |
| Reject or stop | Results are unreproducible, visually unacceptable, licensing is unclear, dependency isolation fails, manifest v1 would be broken, or the work implies forbidden identity/authorship/sensitive claims. |

When real references are unavailable, research can still proceed as prototype
work using visual review, deterministic smoke checks, and ablations, but it
must not claim measured downstream utility. In that case the PR must explicitly
say: "No downstream utility claim is made because no governed real-reference
evaluation was run."

## Criteria For S5b And S5c

S5b allograph and character-level prototypes may proceed when the PR plan:

- Uses deterministic, seed-controlled local variation.
- Keeps source text logical-order Hebrew and preserves final forms, niqqud,
  punctuation, mixed-direction fragments, and line wrapping assumptions.
- Documents allowed allograph sources or generated shapes with license and
  provenance.
- Provides visual review expectations and at least one ablation against current
  handwritten-like output.
- Avoids baseline heavyweight dependencies.

S5c word and line assembly prototypes may proceed when the PR plan:

- Defines seed-controlled spacing, baseline, slant, line-discipline, and
  geometric perturbation parameters.
- Preserves manifest v1 text truth and does not encode richer style semantics
  in manifest v1 fields.
- Includes visual checks for clipping, overlap, readability, RTL coherence,
  and document-family compatibility.
- Documents how any useful downstream signal could later be measured through
  `hocrgen` without adding governance or release behavior here.

S5d optional learned-generation packaging design may proceed only as design
work until dependency isolation, model/data licensing, reproducibility,
compute, evaluation, and baseline contamination risks are resolved.

## Stop Or Reject Criteria

Stop or reject a handwriting research direction when any of these apply:

- Required inputs have unclear provenance, incompatible licensing, or private
  data risk.
- The method depends on heavyweight or networked components without an
  isolated optional design.
- Results cannot be reproduced from recorded commands, seeds, controls, and
  assets.
- Visual review shows unreadable Hebrew, broken RTL behavior, clipping,
  impossible layout, or artifacts that dominate the sample.
- The method implies real identity, authorship, medical, psychological,
  disability, demographic, sensitive-attribute, or source-provenance claims.
- Manifest v1 compatibility would be broken without a versioned schema plan.
- Downstream utility is asserted without reference data, ground truth, or a
  documented `hocrgen`/HeOCR evaluation boundary.
- The work starts implementing `hocrgen` governance, review, caps, export,
  publication, or adapter behavior in this repository.
