# Allograph And Character-Level Prototype Plan

This S5b document plans a deterministic Hebrew allograph and character-level
variation prototype. It is documentation and planning only. It does not add
generator behavior, prototype code, public CLI output, manifest fields, schemas,
fixtures, packaged assets, baseline dependencies, review workflow state, export
behavior, or publication behavior.

No downstream utility claim is made because no governed real-reference
evaluation was run.

## Prototype Boundary

The first S5b artifact is this plan under `docs/`. Any exploratory code, if a
later PR approves it, should live outside baseline package behavior in a clearly
named experimental area such as `experiments/allograph_character_v1/` or a
temporary artifact path documented by that PR.

Exploratory code does not belong in `src/hocrsyngen/` yet because the method has
not passed the S5a reproduction, provenance, visual review, comparison, and
contract gates. Moving code into `src/hocrsyngen/` would make maintainers reason
about public package behavior before there is enough evidence that the approach
is reproducible, visually useful, manifest-compatible, and worth supporting.

Promotion into baseline package code requires a later implementation PR that:

- keeps runtime and test dependencies within
  [ADR 0003](decisions/0003-baseline-dependency-policy.md);
- preserves `generation_manifest.json` v1 or explicitly designs a versioned
  public contract update;
- keeps packaged fixtures unchanged unless a deliberate contract fixture
  regeneration is approved;
- adds focused tests for deterministic controls, Hebrew text behavior, visual
  smoke evidence, and forbidden-claim boundaries;
- documents any public catalog, sidecar, or CLI surface needed by downstream
  `hocrgen`.

## Experiment Goal And Non-Goals

Goal: determine whether deterministic, seed-controlled allograph and
character-level shape variation can improve the handwritten-like appearance of
synthetic Hebrew samples compared with the current `handwritten_note` template
and existing style/condition bundles, without heavyweight model dependencies or
real-writer imitation.

Non-goals:

- no generator behavior in this PR;
- no `generation_manifest.json` v1 changes;
- no packaged contract fixture mutation;
- no new baseline dependencies;
- no network collection, scraping, model downloads, REST calls, GPU use, LLMs,
  diffusion models, Torch, TensorFlow, or other deep-learning dependencies;
- no `hocrgen` adapter, governance, review workflow, release caps, export, or
  publication behavior;
- no claims of real authorship, real-writer identity, demographic category,
  medical condition, psychological condition, disability, sensitive attribute,
  or source provenance.

## Deterministic Controls

A later prototype should expose all randomness through explicit local seeds and
stable control ids. Hidden global random state is not acceptable.

Minimum controls to record:

- `batch_seed`: selects the prototype run and sample ordering.
- `sample_index`: keeps per-sample variation stable inside a batch.
- `text_case_id`: identifies the Hebrew text fixture or generated phrase.
- `allograph_set_id`: selects the allowed character-shape family.
- `character_seed`: derives per-character allograph choices from
  `(batch_seed, sample_index, text_case_id, codepoint_index)`.
- `perturbation_seed`: derives local geometric perturbation choices such as
  x/y offset, scale, rotation, stroke-width proxy, and baseline offset.
- `style_control_id`: optionally maps to existing neutral S4 style ids such as
  `style_standard_v1`, `style_open_drift_v1`, or
  `style_compact_steady_v1`.
- `condition_control_id`: optionally maps to existing neutral S4 condition ids
  such as `condition_standard_v1`, `condition_low_contrast_v1`, or
  `condition_dense_spacing_v1`.

Derived seeds should be stable across Python processes and platforms. A future
prototype should derive them from a documented hash of the control tuple rather
than relying on process-randomized hashes.

## Sampling Plan

The first prototype evidence packet should be a bounded, stratified sample, not
a full cross product of every control dimension. A full cross product of the
dimensions below would create hundreds of artifacts before repeats, which is too
large for a first evidence packet and too easy to review poorly.

Required minimum sample table:

| Run id | Batch seed | Template | Style control | Condition control | Allograph set | Text case | Purpose |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline-standard` | `17` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_none_v1` | final forms | No-variation baseline. |
| `simple-repeat-a` | `17` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_simple_v1` | final forms | Conservative variation against baseline. |
| `simple-repeat-b` | `17` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_simple_v1` | final forms | Repeatability check; should match `simple-repeat-a` by structured choices. |
| `wide-stress` | `101` | `handwritten_note` | `style_open_drift_v1` | `condition_standard_v1` | `allograph_wide_v1` | punctuation | Stress variation without added degradation. |
| `dense-niqqud` | `101` | `handwritten_note` | `style_compact_steady_v1` | `condition_dense_spacing_v1` | `allograph_simple_v1` | niqqud | Combining-mark and tight-spacing check. |
| `low-contrast-mixed` | `4096` | `handwritten_note` | `style_standard_v1` | `condition_low_contrast_v1` | `allograph_simple_v1` | mixed direction | Readability under existing low-contrast condition. |
| `heavy-wear-wrap` | `4096` | `handwritten_note_heavy_wear` | `style_open_drift_v1` | `condition_standard_v1` | `allograph_simple_v1` | wrapping | Interaction with stronger wear and line wrapping. |

The evidence packet may add extra rows only when each row answers a named review
question. It should not expand into a full pairwise or cross-product matrix
until the small table above has produced useful, reproducible evidence.

For the repeated rows, prove deterministic equality for structured prototype
choices such as selected allograph ids, derived seeds, line assignments, and
transform parameters. If raster bytes are expected to vary across platforms, pin
structured choices and image smoke metrics rather than cross-platform JPEG
hashes.

## Variation Approach

The first viable direction should use lightweight local shape variation with a
small explicit allograph table, not an open-ended "jitter every character"
strategy.

Minimal prototype scope:

| Group | Codepoints | Required variants | Reason |
| --- | --- | --- | --- |
| Common letters | `א`, `ב`, `ה`, `ו`, `י`, `ל`, `מ`, `ש`, `ת` | base plus one conservative generated variant | High-frequency coverage without touching every letter first. |
| Final forms | `ך`, `ם`, `ן`, `ף`, `ץ` | base plus one conservative generated variant | Proves final forms remain tied to their codepoints. |
| Stress subset | `א`, `ל`, `ם`, `ש` | one wider or more slanted variant | Exposes failure modes before expanding the method. |

Variant table records should have this shape:

| Field | Meaning |
| --- | --- |
| `allograph_set_id` | Stable set id, such as `allograph_simple_v1`. |
| `codepoint` | Logical Unicode codepoint, not a visual-order glyph index. |
| `variant_id` | Stable variant id within the set, such as `alef_base` or `alef_open_01`. |
| `source_kind` | `packaged_font_transform` or `synthetic_shape_definition`. |
| `transform_bounds` | Bounded local transform parameters allowed for the variant. |
| `notes` | Short review note explaining the visible intended difference. |

Initial transform bounds should be conservative: horizontal and vertical offsets
within 1.5 px at the prototype render scale, width/height scale within 0.94 to
1.06, rotation within 2 degrees, and baseline offset within 2 px. Wider stress
variants may double those limits only in `allograph_wide_v1` rows and must be
reviewed as rejection candidates, not as defaults.

The prototype should choose one variant per logical codepoint occurrence using
the derived character seed after line assignment but before rendering that
line's character shapes. It must not pre-reverse text or replace the
logical-order source text. If Pillow/libraqm shaping is used for the baseline
line, the prototype must document whether it overlays transformed synthetic
glyph crops after shaping or renders per-codepoint shapes directly. Per-codepoint
direct rendering is acceptable only as an experiment and must be reviewed for
broken niqqud, bidi, and punctuation behavior before any promotion.

All choices should be inspectable in a prototype sidecar or evidence table
outside manifest v1. The prototype must include the no-variation ablation from
the sampling plan to isolate whether allograph choices add value beyond current
style and condition controls.

The prototype should start with generated or parametrically transformed shapes
from already-governed local assets when possible. Any new source glyphs, fonts,
images, handwriting references, or derived assets require explicit provenance
and license notes before being committed or bundled.

## Hebrew-Specific Cases

The prototype must preserve logical-order UTF-8 Hebrew, NFC normalization, and
RTL metadata wherever text participates in generated samples or evidence.

Required cases:

- final forms: `ך`, `ם`, `ן`, `ף`, `ץ` must stay tied to their codepoints and
  should not be replaced with non-final forms or Latin-like placeholders;
- base letters with sparse niqqud must preserve combining marks in logical
  order and keep marks visually associated with the intended base glyph;
- punctuation should remain coherent around Hebrew runs and not be pulled into
  impossible visual positions by per-character offsets;
- mixed-direction fragments with Hebrew, Latin, digits, dates, or identifiers
  should preserve the existing bidirectional rendering assumptions and must not
  pre-reverse text;
- line wrapping must operate on logical text and then apply character variation
  inside the selected line boxes, not mutate source text to fit a visual line;
- variation must avoid clipping or collisions at line starts, line ends,
  baselines, ruled lines, stamps, identifiers, and marginalia.

## Assets, Provenance, And Forbidden Sources

Allowed inputs for the first prototype plan:

- existing packaged fonts and synthetic text corpus already governed by this
  repository;
- tiny parametric transforms derived from generated synthetic glyphs;
- newly generated synthetic shape definitions created in-repo with explicit
  documentation and no claim of real handwriting source;
- openly licensed fonts or glyph assets only after license, source,
  redistribution, attribution, and derivative-use terms are documented.

Every future prototype evidence packet must include a provenance table before
assets are committed, bundled, or cited as review evidence:

| Field | Required content |
| --- | --- |
| `asset_id` | Stable id used by the prototype evidence packet. |
| `asset_kind` | Font, text corpus, synthetic shape definition, rendered intermediate, or review image. |
| `source` | Repository path or external source URL/name. |
| `author_or_publisher` | Named author/publisher when known, or `unknown` with reason. |
| `license` | Exact license or repository-governed synthetic status. |
| `redistribution_allowed` | `yes`, `no`, or `unknown`; unknown blocks bundling. |
| `derivative_use_allowed` | `yes`, `no`, or `unknown`; unknown blocks derived allograph assets. |
| `attribution_required` | Required attribution text or `none`. |
| `bundled_in_repo` | `yes` or `no`. |
| `project_synthetic_rationale` | Why the asset does not break `PROJECT-SYNTHETIC` disclosure. |

Forbidden inputs:

- private handwriting samples;
- scraped handwriting images or unlicensed datasets;
- living-person handwriting references used for imitation;
- assets with unclear redistribution or derivative-output rights;
- medical, psychological, disability, demographic, or sensitive-attribute
  labels as source classes or control names;
- downloaded model weights or remote generation services;
- any source that would make `PROJECT-SYNTHETIC` disclosure inaccurate.

## Manifest V1 Compatibility

S5b planning must not change manifest v1. A later prototype may write temporary
evidence outside generated batches, but generated batch manifests must keep the
current contract:

- no new `allograph`, `writer`, `style`, `condition`, `review`, `release`, or
  evaluation fields in `generation_manifest.json` v1;
- no mutation of `controls.persona` or `controls.condition` beyond existing
  nullable string control semantics;
- no absolute paths or `..` segments in any manifest-participating asset path;
- no private Python internals as the `hocrgen` integration boundary;
- no fixture changes unless a future PR intentionally regenerates and updates
  all related contract tests and docs.

If the prototype needs richer allograph metadata, it should record that gap and
keep the metadata in an explicitly experimental sidecar until a versioned public
catalog, sidecar, or manifest/schema update is designed.

## Visual Review Evidence Plan

Review evidence should build on
[visual_inspection_rubric.md](visual_inspection_rubric.md) and add
handwriting-specific notes. It should remain outside manifest v1.

Record for each reviewed page:

- prototype run id, batch seed, sample index, text case id, template id, style
  control id, condition control id, allograph set id, and page id;
- comparison image or structured reference to the no-variation baseline;
- whether Hebrew remains readable, RTL-coherent, unclipped, and visually tied to
  the intended line;
- whether final forms, niqqud, punctuation, mixed-direction fragments, and line
  wrapping remain plausible;
- whether variation looks natural enough to continue or mechanically repetitive
  enough to reject;
- concise rejection notes for unreadability, clipping, collisions, broken RTL,
  impossible punctuation, broken combining marks, or forbidden implication.

At least one ablation should compare the same text, seed, template, style, and
condition with `allograph_none_v1` versus the proposed allograph set. Reviewers
should not infer release eligibility from this evidence.

## Claim Boundary

Allowed claims after a successful prototype:

- the method is deterministic under the recorded seeds and controls;
- the method preserves manifest v1 compatibility when used outside manifest
  metadata;
- visual reviewers found specific generated examples more or less plausible
  than the current handwritten-like baseline;
- the method is or is not worth a later implementation PR based on recorded
  evidence.

Claims not supported without governed real-reference evaluation:

- improved OCR/HTR CER or WER;
- reduced domain shift against real Hebrew handwriting;
- real writer realism, authorship match, or identity consistency;
- demographic, medical, psychological, disability, or sensitive-attribute
  representation;
- dataset release readiness or publication suitability.

## Proceed, Hold, Or Stop Gates

Proceed to a later prototype implementation PR only when:

- the prototype location, commands, dependencies, generated artifacts, and
  cleanup policy are documented;
- the bounded sampling plan and deterministic controls are complete;
- all input assets have acceptable provenance and licensing recorded in the
  required provenance table;
- no baseline dependency, manifest v1, fixture, or public CLI contamination is
  introduced;
- visual review evidence and a no-variation comparison plan are ready.

Proceed from prototype toward baseline implementation only when:

- repeated runs are reproducible;
- Hebrew-specific cases remain readable and logical-order compatible;
- allograph variation is visibly useful compared with `handwritten_note` and
  existing style/condition controls;
- rejected examples have actionable causes rather than broad method failure;
- downstream metadata needs can be handled through an approved public catalog,
  sidecar, or versioned manifest path.

Hold as docs-only research when the direction is plausible but lacks sufficient
visual evidence, real-reference evaluation, asset provenance, or a stable public
contract path.

Stop or reject the direction when results are unreproducible, visually
unreadable, mechanically repetitive, licensing is unclear, dependencies leak
into the baseline, manifest v1 would need an unapproved change, or the work
implies real identity, authorship, sensitive attributes, review acceptance, or
release readiness.
