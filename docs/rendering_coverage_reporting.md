# Rendering Coverage Reporting Design

This document defines the S2d design direction for future Hebrew rendering
coverage reporting. It is intentionally a planning document only: S2d does not
change generator behavior, CLI behavior, dependencies, packaged contract
fixtures, `generation_manifest.json` v1, or the manifest schema.

## Recommendation

Future rendering coverage should be reported as a separate batch-level artifact,
tentatively named `rendering_coverage_report.json`.

The report should sit beside generated batch outputs when a future PR implements
it. It must not be embedded in `generation_manifest.json` v1 because the v1
schema rejects unknown fields and is already a stable downstream contract for
`hocrgen` integration. Keeping coverage evidence separate lets `hocrsyngen`
summarize rendering quality without making every generated batch manifest carry
test and environment audit metadata.

## Report Purpose

The report should answer these questions for a generated batch or governed test
fixture set:

- Which Hebrew rendering dimensions were exercised.
- Which generated samples or curated fixtures provided the evidence.
- Which packaged fonts, template styles, recipes, and rendering paths were
  covered.
- Whether the environment had the native shaping stack required for Hebrew RTL
  rendering.
- Which dimensions remain uncovered and should block claims of complete
  rendering coverage.

The report is coverage evidence, not release governance. `hocrgen` may consume
it in the future as advisory input, but `hocrgen` remains responsible for
dataset governance, validation, review, dedupe, release assembly, export, and
publication.

## Coverage Dimensions

Future reporting should summarize coverage across these dimensions:

- Fonts and font styles: packaged font ids, font styles, and the templates that
  selected them, including `alef-regular` for printed documents and
  `gveret-levin-regular` for handwritten-like documents.
- Templates and recipes: template ids, recipe ids, degradation presets, and the
  sample ids or fixtures that exercised each combination.
- Hebrew text features: final forms, punctuation, numerals, dates, identifiers,
  sparse niqqud, fuller niqqud, and NFC-normalized logical-order text.
- Bidi and mixed direction: Hebrew with Latin fragments, numeric fragments,
  punctuation, and direction-sensitive RTL-vs-LTR rendering evidence.
- Rendering path: evidence that text used the shared RTL drawing path and was
  passed to Pillow as logical-order text with `direction="rtl"`.
- Environment: Pillow libraqm availability and, where discoverable, the native
  FriBiDi and Harfbuzz shaping stack needed by libraqm.
- Asset smoke evidence: non-empty rendered output checks such as image
  dimensions, readable JPEGs, bounding boxes, and coarse ink-pixel thresholds.

The report should prefer stable identifiers and coarse coverage booleans over
pixel hashes. Exact raster output can vary across Pillow, FreeType, libraqm,
FriBiDi, Harfbuzz, libjpeg, and platform font stacks.

## Future Artifact Shape

The future artifact should be batch-level JSON with a small stable top-level
shape:

- `report_version`: version for the report contract, independent from manifest
  versioning. The first implementation should use
  `rendering_coverage_report.v1`.
- `generator_name` and `generator_version`: the generator identity that produced
  the evidence.
- `batch`: paths or ids that identify the generated batch under review without
  using absolute paths.
- `environment`: Pillow/libraqm and native shaping-stack evidence.
- `coverage`: summarized dimensions, covered values, missing values, and sample
  or fixture references.
- `limitations`: known gaps that prevent stronger coverage claims.

Per-sample references should point to existing manifest sample ids and relative
asset paths. The report should not duplicate the manifest payload and should not
be required for basic v1 manifest validation.

The first report contract should require all top-level fields above. Coverage
entries should use the same shape for every dimension:

- `covered`: stable identifiers or feature names found in the evidence.
- `missing`: stable identifiers or feature names expected by the current
  coverage policy but not found in the evidence.
- `evidence`: sample, fixture, or test references that justify the covered
  values.

The report should treat `missing` as an explicit result, not as an omitted field.
An empty `missing` list means the report builder looked for gaps in that
dimension and found none. A dimension that cannot be evaluated should be listed
in `limitations`.

Minimal example:

```json
{
  "report_version": "rendering_coverage_report.v1",
  "generator_name": "hocrsyngen",
  "generator_version": "d4a-realism-v2",
  "batch": {
    "manifest_path": "generation_manifest.json",
    "sample_count": 2,
    "page_count": 2
  },
  "environment": {
    "pillow_raqm": true,
    "shaping_stack": {
      "libraqm": "available",
      "fribidi": "available",
      "harfbuzz": "available"
    }
  },
  "coverage": {
    "fonts": {
      "covered": ["alef-regular", "gveret-levin-regular"],
      "missing": [],
      "evidence": [
        {
          "sample_id": "hocrsyngen-s00000017-000000",
          "asset_path": "assets/hocrsyngen-s00000017-000000/page_0001.jpg"
        }
      ]
    },
    "text_features": {
      "covered": ["final_forms", "punctuation", "numerals", "sparse_niqqud"],
      "missing": ["fuller_niqqud"],
      "evidence": [
        {
          "fixture_id": "generation_manifest_v1_fixture_batch",
          "sample_id": "hocrsyngen-s00000017-000000"
        }
      ]
    }
  },
  "limitations": [
    "The example omits direction-sensitive image comparison evidence."
  ]
}
```

The example is intentionally partial; it shows the required top-level shape and
per-dimension coverage semantics, not the full future coverage matrix.

## Path And Reference Rules

All paths stored in the report must follow the same portability policy as
manifest v1 asset paths:

- relative POSIX paths only;
- no absolute paths;
- no drive-letter paths;
- no backslashes;
- no `..` path segments.

Report references should use manifest sample ids, fixture ids, template ids,
recipe ids, font ids, and relative asset paths that already appear in stable
CLI, fixture, or manifest surfaces. The report should not introduce private
Python names, local temporary paths, or platform-specific resource paths as
identifiers.

## Out Of Manifest V1 Scope

Until a versioned schema change is intentionally planned, these fields must stay
out of `generation_manifest.json` v1:

- Rendering coverage summaries.
- Test fixture coverage matrices.
- Environment probes for Pillow, libraqm, FriBiDi, Harfbuzz, FreeType, or
  platform font stacks.
- Direction-sensitive image comparison results.
- Claims about coverage completeness or review status.
- `hocrgen` governance, release, export, publication, or dataset-readiness
  metadata.

Any future decision to add rendering metadata to a manifest must update the
schema, manifest docs, validation behavior, downstream compatibility notes, and
contract tests together.

## Implementation Sequence

The recommended future implementation sequence is:

1. Add an internal report builder that reads generated batch manifests and
   curated fixture evidence without changing generation output by default.
2. Add focused tests for report content using existing S2a, S2b, and S2c
   coverage fixtures.
3. Add a production surface only as an explicit opt-in command or flag after the
   artifact contract is tested and documented. The default `generate` command
   should continue to emit only the existing manifest and page assets unless a
   future PR deliberately changes that behavior.
4. Coordinate any downstream `hocrgen` use through the artifact boundary rather
   than private Python internals.

S2d stops at this design. The first implementation PR should remain separate so
that report contract details, CLI exposure, and downstream consumption can be
reviewed deliberately.
