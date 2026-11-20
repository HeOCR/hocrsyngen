# Word And Line Assembly Prototype Plan

This S5c document plans a deterministic Hebrew word and line assembly
prototype. It is documentation and planning only. It does not add generator
behavior, prototype code, public CLI output, manifest fields, schemas, fixtures,
packaged assets, baseline dependencies, review workflow state, export behavior,
or publication behavior.

No downstream utility claim is made because no governed real-reference
evaluation was run.

## Prototype Boundary

The first S5c artifact is this plan under `docs/`. Any exploratory code, if a
later PR approves it, should live outside baseline package behavior in a clearly
named experimental area such as `experiments/word_line_assembly_v1/` or a
temporary artifact path documented by that PR.

Exploratory code does not belong in `src/hocrsyngen/` yet because the method has
not passed the S5a reproduction, provenance, visual review, comparison, and
contract gates. Word and line assembly can affect wrapping, text geometry,
manifest truth, and downstream assumptions; those effects need evidence before
the baseline package owns them as public behavior.

Promotion into baseline package code requires a later implementation PR that:

- keeps runtime and test dependencies within
  [ADR 0003](decisions/0003-baseline-dependency-policy.md);
- preserves `generation_manifest.json` v1 or explicitly designs a versioned
  public contract update;
- keeps packaged fixtures unchanged unless a deliberate contract fixture
  regeneration is approved;
- adds focused tests for deterministic controls, Hebrew text behavior,
  wrapping, visual smoke evidence, and forbidden-claim boundaries;
- documents any public catalog, sidecar, or CLI surface needed by downstream
  `hocrgen`.

## Experiment Goal And Non-Goals

Goal: determine whether deterministic, seed-controlled word spacing, line
spacing, baseline drift, slant, wrapping, and per-line geometric perturbation
can improve handwritten-like Hebrew line realism compared with the current
`handwritten_note`, `handwritten_note_heavy_wear`, existing style/condition
bundles, and S5b allograph ablations, while preserving logical-order ground
truth and manifest v1 compatibility.

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
- `assembly_profile_id`: selects word spacing, line spacing, wrapping, baseline
  drift, slant, and line-discipline bounds.
- `line_assignment_seed`: derives wrapping and line break choices from logical
  text, available line boxes, and the assembly profile.
- `word_spacing_seed`: derives per-gap spacing multipliers after line
  assignment.
- `line_geometry_seed`: derives per-line baseline drift, x/y offset, rotation,
  slant proxy, and line width perturbation.
- `character_interaction_seed`: derives only the line-level placement effects
  that interact with S5b allograph choices; it must not replace the S5b
  character-choice seed.
- `style_control_id`: optionally maps to existing neutral S4 style ids such as
  `style_standard_v1`, `style_open_drift_v1`, or
  `style_compact_steady_v1`.
- `condition_control_id`: optionally maps to existing neutral S4 condition ids
  such as `condition_standard_v1`, `condition_low_contrast_v1`, or
  `condition_dense_spacing_v1`.
- `allograph_set_id`: records whether the run uses `allograph_none_v1` or a
  planned S5b allograph set.

Derived seeds should be stable across Python processes and platforms. A future
prototype should derive them from a documented hash of the control tuple rather
than relying on process-randomized hashes.

## Bounded Sampling Plan

The first prototype evidence packet should be a bounded, stratified sample, not
a full cross product of templates, styles, conditions, allograph sets, text
cases, and geometry profiles. The first packet should answer a few review
questions well enough to proceed, hold, or stop.

Required minimum sample table:

| Pair id | Run id | Batch seed | Template | Style control | Condition control | Allograph set | Assembly profile | Text case | Purpose |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `final-spacing` | `baseline-final-spacing` | `17` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_none_v1` | `assembly_none_v1` | final forms | Paired no-assembly baseline. |
| `final-spacing` | `spacing-conservative` | `17` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_none_v1` | `assembly_spacing_conservative_v1` | final forms | Isolate word spacing and wrapping without character variation. |
| `final-spacing` | `spacing-repeat` | `17` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_none_v1` | `assembly_spacing_conservative_v1` | final forms | Repeatability check for structured choices; should match `spacing-conservative`. |
| `punctuation-drift` | `baseline-punctuation-drift` | `101` | `handwritten_note` | `style_open_drift_v1` | `condition_standard_v1` | `allograph_none_v1` | `assembly_none_v1` | punctuation | Paired no-assembly baseline. |
| `punctuation-drift` | `line-drift` | `101` | `handwritten_note` | `style_open_drift_v1` | `condition_standard_v1` | `allograph_none_v1` | `assembly_line_drift_v1` | punctuation | Baseline drift and per-line geometry without allographs. |
| `dense-niqqud` | `baseline-dense-niqqud` | `101` | `handwritten_note` | `style_compact_steady_v1` | `condition_dense_spacing_v1` | `allograph_none_v1` | `assembly_none_v1` | niqqud | Paired no-assembly baseline. |
| `dense-niqqud` | `dense-niqqud-wrap` | `101` | `handwritten_note` | `style_compact_steady_v1` | `condition_dense_spacing_v1` | `allograph_none_v1` | `assembly_dense_wrap_v1` | niqqud | Tight spacing, combining marks, and wrapping stress. |
| `mixed-direction` | `baseline-mixed-direction` | `4096` | `handwritten_note` | `style_standard_v1` | `condition_low_contrast_v1` | `allograph_none_v1` | `assembly_none_v1` | mixed direction | Paired no-assembly baseline. |
| `mixed-direction` | `mixed-direction-spacing` | `4096` | `handwritten_note` | `style_standard_v1` | `condition_low_contrast_v1` | `allograph_none_v1` | `assembly_spacing_conservative_v1` | mixed direction | Bidi fragments under non-default condition. |
| `heavy-wear` | `baseline-heavy-wear` | `4096` | `handwritten_note_heavy_wear` | `style_open_drift_v1` | `condition_standard_v1` | `allograph_none_v1` | `assembly_none_v1` | wrapping | Paired no-assembly baseline. |
| `heavy-wear` | `heavy-wear-drift` | `4096` | `handwritten_note_heavy_wear` | `style_open_drift_v1` | `condition_standard_v1` | `allograph_none_v1` | `assembly_line_drift_v1` | wrapping | Interaction with stronger wear and line structure. |
| `allograph-composition` | `baseline-allograph-composition` | `4096` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_simple_v1` | `assembly_none_v1` | final forms | Paired allograph-only baseline. |
| `allograph-composition` | `allograph-composed` | `4096` | `handwritten_note` | `style_standard_v1` | `condition_standard_v1` | `allograph_simple_v1` | `assembly_spacing_conservative_v1` | final forms | Interaction with planned S5b allograph choices. |

The evidence packet may add extra rows only when each row answers a named review
question. It should not expand into a full pairwise or cross-product matrix
until the small table above has produced useful, reproducible evidence.

Every non-default assembly row must have a paired `assembly_none_v1` row with
the same seed, template, style control, condition control, allograph set, and
text case. The paired rows are the comparison unit for visual review and
structured metrics. A non-default row without its pair is not acceptable
prototype evidence.

For the repeated rows, prove deterministic equality for structured prototype
choices such as line assignments, gap widths, line offsets, rotation, slant
proxy, wrapping decisions, and derived seeds. If raster bytes are expected to
vary across platforms, pin structured choices and image smoke metrics rather
than cross-platform JPEG hashes.

## Assembly Controls

The first viable direction should use conservative local geometric controls
that can be reviewed independently.

Word spacing controls:

- base gap width derived from the shaped line's measured Hebrew space width;
- per-gap multiplier bounded by the assembly profile;
- optional line-level compression factor for fitting logical words into the
  selected line box;
- minimum gap that prevents word collisions and preserves reviewer-readable
  word boundaries;
- maximum gap that prevents a line from looking like unrelated fragments;
- no insertion, deletion, reordering, or visual pre-reversal of source text.

Line spacing and baseline drift controls:

- base line spacing from the template/style bundle;
- per-line y offset with conservative bounds;
- low-frequency baseline drift, not per-character noise masquerading as line
  structure;
- collision checks against neighboring lines, ruled lines, stamps, identifiers,
  margins, and page edges;
- explicit rejection when drift makes lines overlap or hides primary content.

Slant and per-line geometric perturbation controls:

- line-level shear or slant proxy with bounded angle;
- line-level rotation within small handwritten-like limits;
- x offset and width scale per line;
- optional ink-pressure proxy only when it composes with existing style controls
  without adding new manifest semantics;
- no page-global skew that duplicates existing degradation presets unless the
  comparison row explicitly asks that question.

Line discipline and wrapping controls:

- wrapping operates on logical words and phrase fragments before rendering;
- line boxes remain inside the governed template's content region;
- the prototype records why a line break occurred: width limit, hard text case
  break, or profile-specific raggedness;
- overflow must be rejected or marked as a failure case instead of silently
  clipping text;
- optional ragged right/left behavior must be described as neutral line
  discipline, not as a writer identity signal.

Initial transform bounds should be conservative:

| Control | Conservative bound | Stress bound for rejection review |
| --- | --- | --- |
| Word gap multiplier | `0.85` to `1.20` | `0.70` to `1.45` |
| Per-line y offset | within `2 px` | within `5 px` |
| Baseline drift amplitude | within `2 px` over a line | within `5 px` over a line |
| Line rotation | within `1.0` degree | within `2.5` degrees |
| Slant proxy | within `3` degrees | within `7` degrees |
| Line width scale | `0.98` to `1.02` | `0.94` to `1.06` |

Stress bounds should appear only in named rows and should be reviewed as likely
rejection candidates, not as defaults.

Prototype assembly profiles should be explicit records, not just ids. The first
prototype should define these records exactly:

| Field | `assembly_none_v1` | `assembly_spacing_conservative_v1` | `assembly_line_drift_v1` | `assembly_dense_wrap_v1` |
| --- | --- | --- | --- | --- |
| `word_gap_multiplier_range` | `1.00..1.00` | `0.90..1.15` | `0.92..1.12` | `0.82..1.05` |
| `line_compression_range` | `1.00..1.00` | `0.98..1.01` | `0.98..1.02` | `0.94..1.00` |
| `min_gap_px` | existing renderer default | `0.75 * measured_space_px` | `0.75 * measured_space_px` | `0.60 * measured_space_px` |
| `max_gap_px` | existing renderer default | `1.35 * measured_space_px` | `1.30 * measured_space_px` | `1.15 * measured_space_px` |
| `line_y_offset_px_range` | `0..0` | `-1..1` | `-2..2` | `-1..1` |
| `baseline_drift_px_range` | `0..0` | `-1..1` | `-2..2` | `-1..1` |
| `line_rotation_deg_range` | `0..0` | `-0.4..0.4` | `-1.0..1.0` | `-0.3..0.3` |
| `slant_proxy_deg_range` | `0..0` | `-1.5..1.5` | `-3.0..3.0` | `-1.0..1.0` |
| `line_width_scale_range` | `1.00..1.00` | `0.99..1.01` | `0.98..1.02` | `0.96..1.00` |
| `raggedness_policy` | existing renderer behavior | deterministic end-gap variation only | deterministic end-gap plus x-offset variation | prefer tighter line fitting before overflow |
| `overflow_policy` | existing renderer behavior | reject line if any unbreakable unit exceeds box width after compression | reject line if any transformed line collides or exceeds box width | reject line if compression cannot fit without violating minimum gap |
| `intended_question` | Baseline comparison. | Does conservative spacing/wrapping improve line realism? | Does per-line drift help or create collisions? | Does dense layout remain readable with niqqud? |

The profile values above are initial prototype constraints. A later prototype PR
may tune them only by recording the changed profile id, the reason for the
change, and paired evidence against the original values.

## Deterministic Wrapping Algorithm

The first prototype should use a deterministic logical-token wrapping algorithm
before any rendering or visual-order operation. The algorithm should be simple
enough to implement with Python standard-library Unicode data and existing
Pillow/libraqm measurement.

Required steps:

1. Normalize source text to NFC and preserve that exact string as
   `text.logical_order`.
2. Split only explicit newline characters into hard paragraph breaks. Newlines
   may choose a new line box; they must not be serialized as visual-order
   fragments in manifest v1.
3. Scan each paragraph left-to-right in logical order and form Unicode
   character clusters. A cluster is one base codepoint plus following combining
   marks. Combining marks with Unicode category `Mn` or `Mc`, including niqqud,
   must attach to the previous base cluster. A leading combining mark is a
   deterministic rejection case for the text case.
4. Classify clusters into token runs:
   Hebrew letter runs, Latin letter runs, digit runs, mixed identifier runs,
   whitespace runs, punctuation runs, and other-symbol runs.
5. Treat whitespace runs as break opportunities and gap candidates. Multiple
   logical spaces may be collapsed for visual gap placement only when the
   evidence packet records both the logical span and the rendered gap count.
   The source text itself must not be rewritten.
6. Keep mixed identifiers, dates, decimal numbers, and alphanumeric ids
   unbreakable. Examples include `A12`, `2026-05-07`, `12/4`, and `AB-17`.
7. Attach opening punctuation such as `(`, `[`, `{`, and opening quotes to the
   following non-whitespace token when possible. Attach closing punctuation,
   sentence punctuation, Hebrew geresh/gershayim, commas, colons, semicolons,
   and final quote marks to the previous non-whitespace token when possible.
   If both sides are plausible, choose the attachment that avoids a line start
   with closing punctuation or a line end with opening punctuation.
8. Treat Hebrew maqaf or hyphen inside a Hebrew or identifier run as
   non-breaking for the first prototype. If this causes overflow, record the
   overflow instead of splitting the token.
9. Pack tokens into each line box in logical order using measured shaped width
   plus profile gap multipliers. Choose the earliest break that keeps the line
   within the target box while avoiding single-token orphan lines when another
   valid break exists.
10. Reject the sample or record an explicit failure row when any unbreakable
    token exceeds the available line width after the profile's allowed
    compression. Do not clip, squeeze beyond the profile bounds, or mutate the
    source text.

The evidence packet should record the token list and line assignment so a
reviewer can explain wrapping decisions without reverse-engineering raster
output.

## Interaction With S5b Allograph Choices

S5c builds on S5b but should not require S5b character variation to be visually
useful. The first S5c prototype should run most rows with `allograph_none_v1` so
reviewers can isolate line assembly from character-level shape changes.

When composed with S5b:

- line assignment and wrapping happen before per-character allograph selection;
- allograph choices use logical codepoint positions within the assigned line,
  not visual-order glyph positions;
- per-line transforms apply to the rendered line or line fragment after
  character choices are resolved;
- collision checks must include S5b wider or slanted variants;
- allograph metadata, if needed, remains in experimental evidence outside
  `generation_manifest.json` v1.

The composed row should compare `allograph_none_v1` and `allograph_simple_v1`
with the same text, seed, template, style, condition, and assembly profile. That
ablation isolates whether word/line assembly remains useful when allograph
variation is added.

## Hebrew-Specific Cases

The prototype must preserve logical-order UTF-8 Hebrew, NFC normalization, and
RTL metadata wherever text participates in generated samples or evidence.

Required cases:

- final forms: `ך`, `ם`, `ן`, `ף`, `ץ` must stay tied to their codepoints and
  should not be replaced, split, or moved across line breaks incorrectly;
- niqqud: combining marks must remain in logical order and visually associated
  with the intended base glyph after spacing, baseline drift, slant, and line
  transforms;
- punctuation: Hebrew punctuation, quotes, colons, parentheses, and end marks
  should remain coherent around Hebrew runs and not drift into impossible visual
  positions;
- mixed-direction fragments: Hebrew mixed with Latin, digits, dates, or
  identifiers should preserve existing bidirectional rendering assumptions and
  must not pre-reverse text;
- line wrapping: wrapping must operate on logical words/fragments and preserve
  the manifest text as the full logical source string, not as visual line
  fragments;
- overflow: long words, mixed identifiers, and niqqud-heavy fragments should be
  recorded as accepted, wrapped, or rejected by a deterministic rule;
- collisions: line perturbation must not collide with ruled lines, stamps,
  identifiers, marginalia, page borders, or adjacent handwritten lines.

## Assets, Provenance, And Forbidden Sources

Allowed inputs for the first prototype plan:

- existing packaged fonts and synthetic text corpus already governed by this
  repository;
- generated sample text compatible with the repository's synthetic disclosure;
- temporary rendered intermediates produced by documented prototype commands;
- planned S5b allograph sets only when their provenance and license notes are
  acceptable.

Every future prototype evidence packet must include a provenance table before
assets are committed, bundled, or cited as review evidence:

| Field | Required content |
| --- | --- |
| `asset_id` | Stable id used by the prototype evidence packet. |
| `asset_kind` | Font, text corpus, rendered intermediate, review image, or generated evidence sidecar. |
| `source` | Repository path or external source URL/name. |
| `author_or_publisher` | Named author/publisher when known, or `unknown` with reason. |
| `license` | Exact license or repository-governed synthetic status. |
| `redistribution_allowed` | `yes`, `no`, or `unknown`; unknown blocks bundling. |
| `derivative_use_allowed` | `yes`, `no`, or `unknown`; unknown blocks derived assembly assets. |
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

S5c planning must not change manifest v1. A later prototype may write temporary
evidence outside generated batches, but generated batch manifests must keep the
current contract:

- no new `assembly`, `line_geometry`, `word_spacing`, `writer`, `style`,
  `condition`, `review`, `release`, or evaluation fields in
  `generation_manifest.json` v1;
- no mutation of `controls.persona` or `controls.condition` beyond existing
  nullable string control semantics;
- no replacement of `text.logical_order` with visual-order line fragments;
- no absolute paths or `..` segments in any manifest-participating asset path;
- no private Python internals as the `hocrgen` integration boundary;
- no fixture changes unless a future PR intentionally regenerates and updates
  all related contract tests and docs.

If the prototype needs richer line assembly metadata, it should record that gap
and keep the metadata in an explicitly experimental sidecar until a versioned
public catalog, sidecar, or manifest/schema update is designed.

## Visual Review Evidence Plan

Review evidence should build on
[visual_inspection_rubric.md](visual_inspection_rubric.md) and add
handwriting-specific line assembly notes. It should remain outside manifest v1.

Record for each reviewed page:

- prototype run id, batch seed, sample index, text case id, template id, style
  control id, condition control id, allograph set id, assembly profile id, and
  page id;
- comparison image or structured reference to the no-assembly baseline;
- line assignment table with logical line index, source text span, line box,
  gap multipliers, y offset, rotation, slant proxy, and overflow result;
- whether Hebrew remains readable, RTL-coherent, unclipped, and visually tied to
  the intended line;
- whether final forms, niqqud, punctuation, mixed-direction fragments, and line
  wrapping remain plausible;
- whether word spacing and baseline drift look handwritten-like or mechanically
  repetitive;
- concise rejection notes for unreadability, clipping, collisions, broken RTL,
  impossible punctuation, broken combining marks, excessive raggedness,
  overflow, or forbidden implication.

The prototype should write an experimental evidence packet outside manifest v1.
The recommended path is
`out/word-line-assembly-evidence/<run_id>/assembly_evidence.json` for local
prototype output, or `docs/reports/s5c/<run_id>/assembly_evidence.json` only if
a later PR intentionally commits reviewed evidence. Do not package this path as
baseline data.

Minimum experimental JSON shape:

```json
{
  "evidence_version": "word_line_assembly_evidence.v0",
  "run_id": "spacing-conservative",
  "pair_id": "final-spacing",
  "batch_seed": 17,
  "sample_index": 0,
  "template_id": "handwritten_note",
  "style_control_id": "style_standard_v1",
  "condition_control_id": "condition_standard_v1",
  "allograph_set_id": "allograph_none_v1",
  "assembly_profile_id": "assembly_spacing_conservative_v1",
  "text_case_id": "final_forms",
  "source_text_sha256": "<sha256-of-logical-text>",
  "asset_provenance": [],
  "tokens": [
    {
      "token_index": 0,
      "logical_start": 0,
      "logical_end": 4,
      "token_class": "hebrew_run",
      "break_before": false,
      "break_after": true
    }
  ],
  "lines": [
    {
      "line_index": 0,
      "logical_start": 0,
      "logical_end": 24,
      "line_box": {"x": 120, "y": 260, "width": 820, "height": 48},
      "token_indices": [0, 1, 2],
      "gap_multipliers": [1.03, 0.97],
      "line_y_offset_px": 1,
      "baseline_drift_px": -1,
      "rotation_deg": 0.2,
      "slant_proxy_deg": -0.8,
      "line_width_scale": 1.0,
      "wrap_reason": "width_limit",
      "overflow_result": "accepted"
    }
  ],
  "comparison": {
    "paired_run_id": "baseline-final-spacing",
    "paired_assembly_profile_id": "assembly_none_v1"
  },
  "visual_review": {
    "review_status": "unreviewed",
    "notes": []
  },
  "claim_boundary": "No downstream utility claim is made because no governed real-reference evaluation was run."
}
```

Required evidence constraints:

- `logical_start` and `logical_end` are Python string indices into the NFC
  logical source text, not visual glyph indices.
- `line_box` values are local rendered-page coordinates for review only and are
  not manifest fields.
- `asset_provenance` uses the provenance table from this document.
- `visual_review.review_status` is limited to `unreviewed`, `accepted_for_plan`,
  `rejected_for_plan`, or `needs_follow_up`; it is not release review state.
- Every non-default assembly evidence packet must name its paired
  `assembly_none_v1` packet in `comparison`.
- Reviewers should not infer release eligibility from this evidence.

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
- visual review evidence and a no-assembly comparison plan are ready.

Proceed from prototype toward baseline implementation only when:

- repeated runs are reproducible;
- Hebrew-specific cases remain readable and logical-order compatible;
- word spacing, line spacing, baseline drift, slant, and wrapping are visibly
  useful compared with `handwritten_note`, `handwritten_note_heavy_wear`,
  existing style/condition controls, and S5b ablations;
- rejected examples have actionable causes rather than broad method failure;
- downstream metadata needs can be handled through an approved public catalog,
  sidecar, or versioned manifest path.

Hold as docs-only research when the direction is plausible but lacks sufficient
visual evidence, real-reference evaluation, asset provenance, or a stable public
contract path.

Stop or reject the direction when results are unreproducible, visually
unreadable, mechanically repetitive, licensing is unclear, dependencies leak
into the baseline, manifest v1 would need an unapproved change, wrapping breaks
logical-order truth, or the work implies real identity, authorship, sensitive
attributes, review acceptance, or release readiness.
