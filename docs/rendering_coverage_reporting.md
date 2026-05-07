# Rendering Coverage Reporting

This document defines the S2d design direction and S2e implementation contract
for Hebrew rendering coverage reporting. S2e adds an opt-in
`rendering_coverage_report.v1` sidecar artifact outside `generation_manifest.json`
v1. It does not change manifest v1, manifest validation, dependencies, or
packaged contract fixtures.

## Recommendation

Rendering coverage is reported as a separate batch-level artifact named
`rendering_coverage_report.json`.

The report sits beside generated batch outputs only when requested with
`hocrsyngen generate --rendering-coverage-report`. It must not be embedded in
`generation_manifest.json` v1 because the v1 schema rejects unknown fields and
is already a stable downstream contract for `hocrgen` integration. Keeping
coverage evidence separate lets `hocrsyngen` summarize rendering quality
without making every generated batch manifest carry test and environment audit
metadata.

## Report Purpose

The report answers these questions for a generated batch:

- Which Hebrew rendering dimensions were exercised.
- Which generated samples provided the evidence.
- Which packaged fonts, templates, recipes, degradation presets, and rendering
  paths were covered.
- Whether the environment had Pillow libraqm support required for Hebrew RTL
  rendering.
- Which dimensions remain uncovered and prevent stronger coverage claims.

The report is coverage evidence, not release governance. `hocrgen` may consume
it as advisory input, but `hocrgen` remains responsible for dataset governance,
validation, review, dedupe, release assembly, export, and publication.

## Coverage Dimensions

The report summarizes coverage across these dimensions:

- Fonts: packaged font ids selected by generated samples.
- Templates, recipes, and degradation presets: governed template catalog values
  exercised by the batch.
- Hebrew text features: final forms, punctuation, numerals, dates, identifiers,
  Latin fragments, sparse niqqud, fuller niqqud, and NFC-normalized
  logical-order text.
- Bidi and mixed direction: Hebrew with Latin fragments, numeric fragments, and
  punctuation.
- Rendering path: logical-order text, RTL text metadata, and shared RTL drawing
  path evidence.
- Environment: Pillow libraqm availability and, where discoverable, native
  FriBiDi and Harfbuzz shaping-stack status.
- Asset smoke evidence: readable JPEGs, declared dimension matches, and coarse
  non-empty ink checks. A smoke dimension is covered only when every referenced
  page asset in the batch passes that check.

The report uses stable identifiers and coarse coverage booleans rather than
pixel hashes. Exact raster output can vary across Pillow, FreeType, libraqm,
FriBiDi, Harfbuzz, libjpeg, and platform font stacks.

## Artifact Shape

The artifact is batch-level JSON with this top-level shape:

- `report_version`: `"rendering_coverage_report.v1"`, independent from
  manifest versioning.
- `generator_name` and `generator_version`: the generator identity that produced
  the evidence.
- `batch`: relative batch references and generated sample/page counts.
- `environment`: Pillow/libraqm and native shaping-stack evidence.
- `coverage`: summarized dimensions, covered values, missing values, and sample
  references.
- `limitations`: known gaps that prevent stronger coverage claims.

Per-sample references point to manifest sample ids and relative asset paths. The
report does not duplicate the manifest payload and is not required for basic v1
manifest validation.

Coverage entries use the same shape for every dimension:

- `covered`: stable identifiers or feature names found in the evidence.
- `missing`: stable identifiers or feature names expected by the current
  coverage policy but not found in the evidence.
- `evidence`: typed sample references that justify the covered values. Evidence
  may include strings, booleans, numbers, or string lists depending on the
  dimension.

The report treats `missing` as an explicit result, not as an omitted field. An
empty `missing` list means the report builder looked for gaps in that dimension
and found none. A dimension that cannot support stronger claims should be listed
in `limitations`. Per-sample text evidence lists only the features actually
detected in that sample; it must not copy batch-level feature coverage onto
unrelated samples.

The normative machine-readable schema is
`src/hocrsyngen/schemas/rendering_coverage_report.schema.json`.

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
      "libraqm": "0.10.5",
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
          "asset_path": "assets/hocrsyngen-s00000017-000000/page_0001.jpg",
          "font_id": "alef-regular"
        }
      ]
    },
    "text_features": {
      "covered": ["final_forms", "punctuation", "numerals"],
      "missing": ["latin_fragments", "sparse_niqqud", "fuller_niqqud"],
      "evidence": [
        {
          "sample_id": "hocrsyngen-s00000017-000000",
          "asset_path": "assets/hocrsyngen-s00000017-000000/page_0001.jpg",
          "covered": ["final_forms", "punctuation", "numerals"]
        }
      ]
    }
  },
  "limitations": [
    "text_features missing coverage: latin_fragments, sparse_niqqud, fuller_niqqud"
  ]
}
```

The example is intentionally partial; it shows the required top-level shape and
per-dimension coverage semantics, not the full coverage matrix.

## CLI Behavior

The default `generate` command continues to emit only `generation_manifest.json`
and page assets:

```bash
hocrsyngen generate --count 2 --seed 17 --output out/fixture-batch
```

To write the sidecar:

```bash
hocrsyngen generate --count 2 --seed 17 --output out/fixture-batch --rendering-coverage-report
```

When JSON output is requested with the sidecar flag, the generation report adds
`rendering_coverage_report_path`:

```json
{
  "schema_version": "generation_report.v1",
  "sample_count": 2,
  "page_count": 2,
  "output_path": "out/fixture-batch",
  "manifest_path": "out/fixture-batch/generation_manifest.json",
  "rendering_coverage_report_path": "out/fixture-batch/rendering_coverage_report.json"
}
```

`hocrsyngen validate` remains scoped to `generation_manifest.json` v1. It does
not require or inspect `rendering_coverage_report.json`.

## Path And Reference Rules

All paths stored in the report must follow the same portability policy as
manifest v1 asset paths:

- relative POSIX paths only;
- no absolute paths;
- no drive-letter paths;
- no backslashes;
- no `..` path segments.

Report references should use manifest sample ids, template ids, recipe ids,
font ids, and relative asset paths that already appear in stable CLI or
manifest surfaces. The report should not introduce private Python names, local
temporary paths, or platform-specific resource paths as identifiers.

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

## Implementation Notes

S2e implements the first report builder and CLI surface. The report summarizes
coarse covered and missing values for governed fonts, templates, recipes,
degradation presets, Hebrew text features, mixed-direction evidence, RTL
rendering path evidence, environment probes, and asset smoke checks. Text
feature detectors use explicit v1 semantics: final Hebrew letter code points,
punctuation characters, decimal digits, `dd/dd/dddd`-style dates,
Latin-prefixed or Hebrew/archive identifier patterns, Latin code points, any
Hebrew combining mark for sparse niqqud, and at least one token with four or
more Hebrew combining marks for fuller niqqud. It uses stable manifest sample
ids and relative page asset paths. It avoids pixel hashes and does not make
release, review, or completeness claims.

Any downstream `hocrgen` use should consume the sidecar artifact boundary, not
private Python internals.
