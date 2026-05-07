# Learned Generation Packaging Boundary

This S5d document designs an optional packaging boundary for future
learned-generation experiments. It is documentation and planning only. It does
not add generator behavior, prototype code, public CLI output, manifest fields,
schemas, fixtures, packaged assets, baseline dependencies, model downloads,
network behavior, review workflow state, export behavior, or publication
behavior.

No downstream utility claim is made because no governed real-reference
evaluation was run.

## Boundary Goal

Goal: define how future ML-backed Hebrew handwriting or document-generation
experiments could be isolated from the `hocrsyngen` baseline package before any
optional prototype PR is allowed.

The design must keep the baseline install lightweight, deterministic, local,
and contract-compatible while leaving room for future optional experiments that
may need learned models, model-specific dependencies, evidence packets, or
separate packaging.

Non-goals:

- no learned-generation code in this PR;
- no exploratory code under `src/hocrsyngen/`;
- no `generation_manifest.json` v1 changes;
- no packaged contract fixture mutation;
- no new baseline runtime or test dependencies;
- no automatic model downloads, remote services, scraping, REST calls, or
  network access in baseline behavior;
- no GPU requirement for baseline generation, validation, tests, or CLI smoke
  commands;
- no LLM, diffusion, Torch, TensorFlow, model-runtime, or other heavyweight
  dependencies in baseline runtime or test extras;
- no `hocrgen` adapter, governance, review workflow, release caps, dedupe,
  export, publication, or release-readiness behavior;
- no claims of real authorship, real-writer identity, demographic category,
  medical condition, psychological condition, disability, sensitive attribute,
  source provenance, or living-person imitation.

## Location Options

Future optional learned-generation work may use one of these locations only
after the PR defines the dependency, artifact, cleanup, and contract boundary:

| Location | Allowed use | Requirements |
| --- | --- | --- |
| `docs/` | Design notes, experiment plans, evaluation reports, and reviewed findings. | Always allowed for S5d planning and evidence. |
| `experiments/learned_generation_v0/` | Local exploratory scripts, config templates, and non-packaged evidence helpers. | Must be excluded from baseline install assumptions, must not be imported by `src/hocrsyngen/`, and must document setup, cleanup, dependencies, assets, and outputs. |
| Future package extra such as `hocrsyngen[learned-experiments]` | Optional local experimentation using explicitly declared extra dependencies. | Requires a later ADR or design update, pinned optional dependencies, no baseline test dependency leakage, and skip-safe tests that do not require private data, model downloads, network, or GPU. |
| Separate package or repository | Heavier model runtime, training, benchmark orchestration, or artifact management. | Preferred when dependencies, model weights, datasets, compute, or governance needs exceed a small optional local experiment. |
| Versioned sidecar or catalog design | Public metadata for optional learned outputs or experiment evidence. | Must be explicitly designed, documented, schema-tested, and kept outside manifest v1 unless a future manifest version is approved. |

Learned-generation code does not belong in `src/hocrsyngen/` while it is
exploratory because that package is the baseline public generator. Code in
`src/hocrsyngen/` must remain installable and testable with the accepted
lightweight dependency policy, deterministic public CLI behavior, packaged
fixtures, and manifest v1 validation. Optional learned methods need evidence
that they are reproducible, dependency-isolated, provenance-safe,
contract-compatible, and useful before the baseline package should own any part
of them.

## Dependency Policy

The baseline dependency policy remains [ADR 0003](decisions/0003-baseline-dependency-policy.md):
runtime dependencies are limited to `jsonschema` and `Pillow`, and the accepted
test extra is `pytest`.

Allowed in baseline:

- Python standard library;
- current accepted runtime dependencies;
- current accepted test dependencies;
- local deterministic rendering, validation, and reporting code that is
  intentionally promoted by a later roadmap PR and remains within ADR 0003.

Allowed only in isolated optional experiments or separate packages:

- ML framework runtimes such as Torch, TensorFlow, JAX, ONNX Runtime, or
  model-specific inference packages;
- image-processing or numeric stacks needed only for experiments;
- model conversion, training, evaluation, or visualization tools;
- optional dataset loaders when their licenses, provenance, privacy, and
  redistribution limits are documented.

Forbidden in baseline runtime, test extras, public CLI requirements, and
packaged fixtures:

- network, REST, scraping, crawlers, remote generation services, or automatic
  downloads;
- GPU, CUDA, Metal, TPU, accelerator-specific runtimes, or hardware
  requirements;
- LLM, diffusion, Torch, TensorFlow, JAX, ONNX Runtime, or other heavyweight
  learned-generation dependencies;
- private datasets, private model weights, or setup that depends on hidden
  local files;
- dependency declarations that make baseline tests skip or fail unless optional
  learned-generation tooling is installed.

## Model, Data, And Asset Provenance

Any later learned-generation prototype must include a provenance packet before
assets, weights, datasets, generated intermediates, or review evidence are
committed or cited.

Minimum provenance table:

| Field | Required content |
| --- | --- |
| `asset_id` | Stable id used by the experiment. |
| `asset_kind` | Model weights, model config, training dataset, evaluation dataset, font, text corpus, rendered intermediate, generated sample, or review image. |
| `source` | Repository path or external source name/URL. |
| `author_or_publisher` | Named author/publisher when known, or `unknown` with reason. |
| `license` | Exact license or repository-governed synthetic status. |
| `training_data_provenance` | Known sources and collection method for trained models, or `unknown`. Unknown blocks bundling and supported claims. |
| `redistribution_allowed` | `yes`, `no`, or `unknown`; unknown blocks bundling. |
| `commercial_use_allowed` | `yes`, `no`, or `unknown`; unknown blocks production-facing integration. |
| `derivative_output_allowed` | `yes`, `no`, or `unknown`; unknown blocks generated-output publication claims. |
| `privacy_review` | Statement about private, personal, sensitive, or living-person handwriting risk. |
| `attribution_required` | Required attribution text or `none`. |
| `bundled_in_repo` | `yes` or `no`. |
| `project_synthetic_rationale` | Why the asset does not break `PROJECT-SYNTHETIC` disclosure. |

Model weights and datasets must not be redistributed from this repository
unless license, privacy, attribution, training-data provenance, derivative-use,
commercial-use, and redistribution terms are explicit and compatible. Large
weights or datasets should use external artifact management in a separate
package or repository, not baseline package data.

Automatic model downloads are not allowed in baseline behavior. Optional
experiments may document manual asset placement only when the asset source,
checksum, license, and expected local path are recorded, and when missing assets
fail with a clear message instead of attempting network access.

## Reproducibility Packet

A later optional learned-generation prototype PR must include a reproducibility
packet with:

- experiment goal and claim boundary;
- exact commands to run from a clean checkout;
- optional dependency installation instructions that do not affect baseline
  install or tests;
- model architecture id, model version, config id, and weight checksum;
- dataset ids, dataset versions, source checksums where available, and license
  notes;
- seeds and deterministic controls for sample selection, text selection,
  prompt/control construction if applicable, model stochasticity, postprocess
  transforms, degradation, style, condition, and evaluation sampling;
- environment assumptions, including CPU/GPU use, expected runtime, and
  platform-sensitive behavior;
- generated artifact paths and cleanup policy;
- visual review evidence and at least one comparison against the current
  deterministic handwritten-like baseline, S5b allograph plan, or S5c word/line
  assembly plan.

If a learned method has unavoidable nondeterminism, the prototype must record
it explicitly, pin all controllable seeds, and keep the method exploratory. It
cannot be promoted into baseline behavior while reproducibility depends on
hidden state, unpinned model versions, untracked stochastic services, private
data, or hardware-specific outputs.

## Deterministic Controls

Where learned methods interact with generated outputs, all controls must remain
seedable and inspectable:

- `batch_seed` selects the prototype run and sample ordering;
- `sample_index` identifies stable per-sample output;
- `text_case_id` identifies the logical-order Hebrew text fixture or generated
  phrase;
- `model_id`, `model_version`, `model_config_id`, and `weights_sha256` identify
  the learned component;
- `inference_seed` controls model stochasticity when the runtime supports it;
- `postprocess_seed` controls local cropping, placement, filtering, geometric
  perturbation, degradation, and composition;
- `style_control_id` and `condition_control_id` remain neutral synthetic
  controls when used;
- any allograph, word/line assembly, or layout controls compose through
  documented S5b/S5c-style ids or experimental sidecars, not hidden private
  code paths.

Source text must remain logical-order UTF-8 Hebrew, NFC-normalized, with RTL
metadata when it becomes generated sample text. Learned outputs must not
pre-reverse text, replace manifest truth with visual-order fragments, or hide
model substitutions that change the intended transcription.

## Manifest And Sidecar Boundary

S5d planning must not change manifest v1. Generated directories remain
candidate synthetic inputs only and are not release-ready dataset artifacts.

Manifest v1 compatibility rules:

- no learned-generation fields in `generation_manifest.json` v1;
- no `model`, `weights`, `dataset`, `writer`, `style`, `condition`, `review`,
  `release`, `evaluation`, or utility fields added to manifest v1;
- no mutation of `controls.persona` or `controls.condition` beyond current
  nullable string synthetic-control semantics;
- no private Python internals as a downstream integration boundary;
- no absolute paths or `..` segments in any manifest-participating asset path;
- no packaged fixture changes unless a future PR intentionally regenerates and
  updates all related contract tests and docs.

Optional learned-generation metadata belongs in one of these future surfaces:

- an explicitly experimental evidence sidecar under local `out/` paths;
- committed `docs/reports/s5d/...` evidence only when a later PR intentionally
  commits reviewed findings;
- a versioned public sidecar such as `learned_generation_evidence.v0` after a
  schema and compatibility design;
- a future catalog surface for optional model capabilities before generation;
- a future manifest/schema version only after a roadmap item approves that
  contract change.

Any sidecar must keep paths portable, use stable ids, name model/data checksums,
record license/provenance, and clearly state that review evidence is not
release governance.

## Claims And Evaluation

Allowed claims after a successful optional prototype:

- the optional experiment is isolated from baseline dependencies;
- the method is reproducible under recorded seeds, controls, weights, data, and
  commands, or its nondeterminism is explicitly bounded;
- visual reviewers found specific generated examples more or less plausible
  than named deterministic baselines;
- manifest v1 compatibility is preserved by keeping learned metadata outside
  the manifest;
- no downstream utility claim is made when governed real-reference evaluation
  was not run.

Claims not supported without governed real-reference evaluation:

- improved OCR/HTR CER or WER;
- reduced domain shift against real Hebrew handwriting;
- real writer realism, authorship match, identity consistency, or source
  provenance;
- demographic, medical, psychological, disability, or sensitive-attribute
  representation;
- dataset release readiness, publication suitability, or governed review
  acceptance.

Visual review must build on
[visual_inspection_rubric.md](visual_inspection_rubric.md) and S5 handwriting
review expectations. Downstream utility evidence belongs in `hocrgen`/HeOCR
when governed real references and ground truth exist.

## Criteria For Later Prototype PR

A later optional learned-generation prototype PR may proceed only when all of
these are true:

- prototype location is outside baseline package behavior;
- dependency isolation is documented and verified by baseline install/test
  commands;
- no learned-generation imports are reachable from `src/hocrsyngen/` baseline
  paths;
- model/data provenance and licensing table is complete;
- no automatic downloads or network access are required;
- no GPU is required for baseline commands;
- commands, seeds, controls, checksums, output paths, and cleanup policy are
  documented;
- generated outputs remain candidate synthetic inputs only;
- manifest v1 remains unchanged and optional metadata stays in a sidecar or
  local evidence packet;
- forbidden identity, authorship, health, disability, demographic, sensitive
  attribute, source-provenance, review, release, and utility claims are absent;
- visual review and baseline comparison plan are ready.

## Stop Or Refuse Criteria

Stop or refuse learned-generation work when any of these apply:

- dependency isolation cannot be proven;
- baseline runtime or test dependencies would gain heavyweight, networked, GPU,
  LLM, diffusion, Torch, TensorFlow, or model-runtime requirements;
- the method requires automatic downloads, remote services, scraping, private
  data, or hidden local assets;
- model weights, training data, evaluation data, or derived outputs have
  unclear provenance, incompatible licensing, privacy risk, or redistribution
  restrictions that conflict with the proposed use;
- generated outputs imply real-writer imitation, authorship, identity, source
  provenance, medical, psychological, disability, demographic, or
  sensitive-attribute claims;
- results are unreproducible and cannot be bounded as exploratory evidence;
- manifest v1 compatibility would be broken without an approved versioned
  contract;
- learned metadata leaks into filenames, manifests, CLI reports, catalogs, or
  docs as release, review, provenance, or utility claims;
- the work starts implementing `hocrgen` governance, review, caps, export,
  publication, or adapter behavior in this repository.

## Criteria For Closing S5

Phase S5 can close and move to S6 when:

- S5a acceptance criteria, S5b allograph planning, S5c word/line assembly
  planning, and this S5d learned-generation packaging boundary are merged;
- active S5 docs consistently state that generated outputs are candidate
  synthetic inputs only;
- baseline dependency, manifest v1, fixture, CLI, and `hocrgen` boundaries are
  protected;
- future prototype gates are explicit enough to decide proceed, hold, or stop
  without adding new planning PRs;
- unresolved release governance, downstream utility, review evidence,
  synthetic caps, and domain-shift measurement are tracked as S6 or external
  `hocrgen` responsibilities.
