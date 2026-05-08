# Script Abstraction Design

`S7a` is a design-only planning note for future RTL-script boundaries. It does
not implement Arabic support, change generator behavior, change
`generation_manifest.json` v1, change validation semantics, add dependencies,
or move downstream governance into `hocrsyngen`.

The current implementation remains Hebrew-first. The only supported manifest v1
text metadata is still:

- `script == "Hebr"`
- `language == "he"`
- `direction == "rtl"`
- `unicode_normalization == "NFC"`
- logical-order UTF-8 Hebrew in `text.logical_order`

Any future broader script support must preserve those guarantees until a
versioned public contract explicitly changes them.

## Design Goals

- Keep current Hebrew generation, rendering, validation, and manifest behavior
  stable.
- Identify the smallest future boundaries that could support another RTL script
  without requiring downstream tools to import private Python internals.
- Keep script-specific text, font, shaping, layout, and validation decisions
  explicit rather than inferred from filenames, Unicode ranges, or private
  helper names.
- Require Hebrew regression gates before any implementation broadens script
  support.

## Non-Goals

- No Arabic support is implemented by `S7a`.
- No new script id, language id, corpus, font, template, CLI option, schema
  field, sidecar, catalog field, or packaged fixture is added by `S7a`.
- No change is made to manifest v1 constants, schema constraints, validation
  behavior, CLI contracts, packaged fixtures, baseline dependencies, rendering
  coverage behavior, or `hocrgen` integration behavior.
- No network, REST, scraping, GPU, LLM, diffusion, Torch, TensorFlow, or other
  deep-learning dependency is introduced.

## Current Hebrew Contract

Current Hebrew behavior is the compatibility baseline, not a special case to be
watered down.

| Boundary | Current invariant |
| --- | --- |
| Manifest text metadata | `Hebr`, `he`, `rtl`, `NFC` constants in manifest v1. |
| Logical text | Logical-order UTF-8 Hebrew, NFC-normalized before serialization and validation. |
| Rendering | Pillow/libraqm RTL drawing path; text is not pre-reversed. |
| Validation | Rejects non-Hebrew manifest text metadata and non-NFC logical text. |
| Assets | Portable relative POSIX paths under the batch directory. |
| Provenance | Governed template, recipe, degradation, font, and source-corpus ids. |
| Downstream use | `hocrgen` consumes installed CLI JSON reports, manifests, fixtures, and public catalogs, not private internals. |

## Minimal Future Abstractions

The smallest future abstraction should be a script profile concept. This can be
implemented later as private Python data first, then promoted to a public
catalog or manifest contract only after a versioned compatibility decision.

A script profile should define:

- stable profile id;
- ISO 15924 script code;
- BCP 47 language tag or language family allowed for generated text;
- text direction;
- required Unicode normalization;
- logical-order ground-truth rule;
- allowed character inventory, including script-specific letters, combining
  marks, digits, punctuation, whitespace, and control-code exclusions;
- permitted mixed-script fragments and the cases where they are allowed, such
  as identifiers, dates, Latin abbreviations, or numeric fields;
- rendering/shaping requirements;
- allowed text corpus ids;
- allowed font ids and font license/provenance requirements;
- validation profile name;
- coverage dimensions needed before generation is considered inspectable.

The current implicit Hebrew profile would be equivalent to:

| Field | Hebrew baseline |
| --- | --- |
| profile id | `hebrew_v1` |
| script | `Hebr` |
| language | `he` |
| direction | `rtl` |
| normalization | `NFC` |
| logical-order rule | serialize logical-order Hebrew text exactly as the ground truth. |
| character inventory | Hebrew letters and marks needed by governed Hebrew corpora, plus explicitly allowed digits, punctuation, whitespace, and mixed Hebrew/Latin/numeric fragments covered by current tests. |
| shaping requirement | Pillow/libraqm path with RTL direction and no pre-reversal. |
| validation profile | manifest v1 Hebrew constants and NFC checks. |

This profile is descriptive for S7a. It is not a new public machine contract.

## Boundary Details

### Text Corpus Boundary

Future script work should treat text corpora as script-scoped assets with
explicit provenance. A corpus should declare its script profile, language,
normalization expectation, license/provenance, and whether it contains mixed
direction fragments. The generator should not infer support for a script merely
because a corpus contains characters from that script.

Current Hebrew text corpus behavior remains unchanged.

Future implementation must not treat metadata alone as proof that text belongs
to a script profile. The profile should make text admissibility testable before
generation and validation are broadened: unexpected control characters,
unplanned script mixing, unsupported combining marks, or unreviewed digit and
punctuation behavior should either be rejected or held behind an experiment-only
boundary until the profile and tests explicitly allow them.

### Font And Shaping Boundary

Fonts should remain governed assets with explicit provenance and license
documentation. Future script profiles need a script-specific shaping audit
before the font is used for generated assets. The audit should cover:

- whether the font supports the target script and relevant marks;
- whether Pillow/libraqm, FriBiDi, Harfbuzz, and FreeType produce the expected
  RTL layout and shaping behavior;
- whether visual smoke tests can detect empty, clipped, reversed, or
  uninspectable output;
- whether exact pixel hashes should remain avoided across platforms.

Current Hebrew font behavior and libraqm requirements remain unchanged.

### Template And Layout Boundary

Document templates should not become script-neutral by default. A future
template may be shared across scripts only after it declares which text slots,
labels, guides, stamps, identifiers, page regions, and review features are
compatible with each script profile.

Until that exists, current governed templates remain Hebrew templates. Future
script-specific templates should use new governed ids rather than silently
reusing Hebrew template ids with different semantics.

### Validation Boundary

Manifest v1 validation must keep enforcing the Hebrew constants. Future script
support has two acceptable paths:

- a new manifest version or successor schema that documents generated-sample
  script/language/direction semantics, validation behavior, schema constraints,
  fixture expectations, and `hocrgen` compatibility; or
- an explicitly additive catalog or sidecar that only advertises script
  capabilities or carries experiment evidence, is not accepted by manifest v1
  validation, and is clearly outside stable downstream ingestion.

The unacceptable path is broadening manifest v1 validation to accept more
script metadata without a versioned compatibility plan. A stable generated batch
with non-`Hebr` text metadata must not be accepted as manifest v1 merely because
a catalog or sidecar can describe another script profile.

### Public Discovery Boundary

If downstream tools later need to discover script capabilities before
generation, that discovery should use a documented public surface such as a
future catalog version. Downstream tools should not infer script capability from
private recipe classes, helper names, local data paths, filenames, or font file
names.

Any future public script catalog should identify supported profiles, allowed
template joins, allowed font/corpus ids, required rendering features, and
validation expectations. It should remain separate from release governance,
review state, caps, export, and publication.

### hocrgen Boundary

`hocrgen` remains the owner of import governance, review, caps, dedupe, release
assembly, export, and publication. Future script abstraction work in
`hocrsyngen` must not require `hocrgen` to import private Python internals.

For the current Hebrew baseline, `hocrgen` should keep asserting:

- manifest v1 Hebrew text metadata constants;
- validation success through `hocrsyngen validate`;
- portable relative asset paths;
- stable sample and page ids;
- public template catalog joins.

## Hebrew Regression Expectations

Before any implementation changes the script boundary, tests should prove that
the Hebrew baseline still rejects drift. `S7b` should cover at least:

- generated manifest samples still serialize `Hebr`, `he`, `rtl`, and `NFC`;
- validation still rejects changed script, language, direction, or normalization
  values in manifest v1;
- logical text remains NFC-normalized and logical-order;
- mixed Hebrew/Latin/numeric and niqqud cases still render through the RTL
  drawing path without pre-reversal;
- packaged fixture expectations and public CLI JSON reports remain compatible;
- no new baseline dependency class is introduced while adding script-boundary
  scaffolding.

These are regression gates for implementation work, not new behavior in `S7a`.

## Future Work

- `S7b` should add Hebrew regression tests before broader script scaffolding is
  implemented.
- `S7c` should document Arabic-specific differences in shaping, joining,
  marks, fonts, text normalization, language metadata, corpora, validation, and
  review needs without implementing Arabic support.
- Any later implementation PR should choose whether the script profile remains
  private scaffolding, becomes a public catalog, or requires a manifest version
  update before downstream tools rely on it.
