# hocrgen Integration Contract

`hocrgen` should consume `hocrsyngen` through the installed-package CLI and serialized manifest/fixture contracts. It should not import private `hocrsyngen` internals.

## Stable Integration Commands

```bash
hocrsyngen templates --format json
hocrsyngen templates --format json --catalog-version v2
hocrsyngen contracts --format json
hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json
hocrsyngen generate --count N --seed S --output PATH --format json
hocrsyngen generate --count N --seed S --output PATH --rendering-coverage-report --format json
hocrsyngen validate PATH --format json
```

## Minimal Adapter Assertions

`hocrgen` adapter tests should assert the command contract at the JSON boundary, not Python internals.

For `hocrsyngen templates --format json`, assert:

- `schema_version == "template_catalog.v1"`.
- `templates` is a list.
- Each template has `template_id`, `recipe_id`, `layout_style`, `font_style`, `font_id`, and `degradation_preset`.
- The current packaged catalog includes `printed_letter`, `handwritten_note`,
  `archive_card`, and the stronger degradation variants
  `printed_letter_heavy_scan`, `handwritten_note_heavy_wear`, and
  `archive_card_faded_scan`.

For `hocrsyngen templates --format json --catalog-version v2`, assert:

- `schema_version == "template_catalog.v2"`.
- The payload validates against
  `src/hocrsyngen/schemas/template_catalog.schema.json`.
- Each v1 template entry field remains present.
- Each template also has `document_family`, `base_family`, `page_regions`,
  `annotation_types`, `identifier_types`, `layout_density`, and
  `review_features`.
- The current packaged catalog maps stronger variants to their base families:
  `printed_letter_heavy_scan -> printed_letter`,
  `handwritten_note_heavy_wear -> handwritten_note`, and
  `archive_card_faded_scan -> archive_card`.
- Validated manifest sample provenance can be joined to v2 catalog entries by
  `(template_id, recipe_id)` without importing private Python internals.

For `hocrsyngen contracts --format json`, assert:

- `schema_version == "contract_fixture_catalog.v1"`.
- The catalog contains fixture id `generation_manifest_v1_fixture_batch`.
- That fixture has `contract == "generation_manifest.v1"`.
- That fixture currently reports `sample_count == 2` and `page_count == 2`.
- `manifest_resource_path` ends with `generation_manifest.json`.

For `hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json`, assert:

- `schema_version == "contract_fixture_export.v1"`.
- `fixture_id == "generation_manifest_v1_fixture_batch"`.
- `contract == "generation_manifest.v1"`.
- `sample_count == 2` and `page_count == 2`.
- `manifest_path == "PATH/generation_manifest.json"` using the CLI argument string for `PATH`.
- The exported `PATH/generation_manifest.json` exists and validates.

For `hocrsyngen generate --count N --seed S --output PATH --format json`, assert:

- `schema_version == "generation_report.v1"`.
- `sample_count == N`.
- `page_count >= sample_count`.
- `output_path` echoes `PATH`.
- `manifest_path == "PATH/generation_manifest.json"` using the CLI argument string for `PATH`.

For `hocrsyngen generate --count N --seed S --output PATH --rendering-coverage-report --format json`, assert the same generation report fields plus:

- `rendering_coverage_report_path == "PATH/rendering_coverage_report.json"`.
- The sidecar has `report_version == "rendering_coverage_report.v1"`.
- The sidecar is advisory rendering coverage evidence outside manifest v1.

For `hocrsyngen validate PATH --format json`, assert on success:

- `schema_version == "validation_report.v1"`.
- `valid == true`.
- `sample_count` and `page_count` match the manifest.
- `path` echoes the original CLI argument string.

For invalid validation with `--format json`, assert:

- The process exits non-zero.
- `schema_version == "validation_report.v1"`.
- `valid == false`.
- `path` echoes the original CLI argument string.
- `error` is a non-empty deterministic string.

## hocrgen Responsibilities After Import

After receiving a valid `hocrsyngen` batch, `hocrgen` remains responsible for:

- Release eligibility.
- Synthetic caps.
- Source composition.
- Review.
- Privacy.
- Dedupe and leakage checks.
- Benchmark/reference handling.
- Release export.
- Publication.

## Layout Filtering Boundaries

Current layout filtering should use only stable CLI and manifest surfaces.
Before generation, `hocrgen` can inspect `hocrsyngen templates --format json` for
template ids, recipe ids, layout styles, font styles, font ids, and degradation
presets. It can inspect
`hocrsyngen templates --format json --catalog-version v2` for the richer
document-family catalog, including document family, base family, page regions,
annotation types, identifier types, layout density, and review features. After
generation, it can validate `generation_manifest.json` v1 and join each
sample's `(provenance.template_id, provenance.recipe_id)` pair to
`template_catalog.v2` for richer catalog metadata. Manifest v1 itself still
does not carry document family, font style, page regions, marginalia, stamps,
identifiers, density, or reviewability. Those fields should not be inferred from
private Python recipe, document, or drawing helpers.

The S3c stronger degradation variants are exposed as separate `template_id`
values because manifest v1 does not have a separate preset-selection field or
base-template field. Downstream grouping can now use `template_catalog.v2`
`base_family` metadata; the mapping is:

| Base family | Template ids |
| --- | --- |
| `printed_letter` | `printed_letter`, `printed_letter_heavy_scan` |
| `handwritten_note` | `handwritten_note`, `handwritten_note_heavy_wear` |
| `archive_card` | `archive_card`, `archive_card_faded_scan` |

## Persona, Style, And Condition Boundaries

Persona, style, and condition controls are synthetic generator parameter
bundles only, as defined in
[ADR 0005](decisions/0005-persona-style-condition-semantics.md). Current
manifest v1 controls do not carry real identity, authorship, medical,
psychological, sensitive-attribute, provenance, review, release, or publication
metadata.

S4b exposes deterministic synthetic style bundles through
`hocrsyngen generate --persona STYLE_ID`, using the existing manifest v1
`controls.persona` string slot. The supported ids are `style_standard_v1`,
`style_open_drift_v1`, and `style_compact_steady_v1`. `hocrgen` may treat these
as neutral generator-control ids after manifest validation, but should not infer
writer identity, authorship, provenance, review state, release eligibility, or
human attributes from them.

S4c exposes each deterministic synthetic rendering-control condition bundle
through `hocrsyngen generate --condition CONDITION_ID`, using the existing
manifest v1 `controls.condition` string slot. The supported ids are
`condition_standard_v1`, `condition_low_contrast_v1`, and
`condition_dense_spacing_v1`. `hocrgen` may treat these as neutral
generator-control ids after manifest validation, but should not infer identity,
authorship, provenance, medical, psychological, disability, sensitive-attribute,
review, release, or publication metadata from them. S4c does not add a
`condition` object or richer manifest v1 metadata. Dense spacing tightens
rendered body text line placement only; downstream tools should not infer that
template guide lines, form rows, archive card grids, stamps, marginalia, or
other scaffolding were rescaled.

Until a future public catalog, manifest/schema update, or explicit sidecar
artifact exposes richer control metadata, `hocrgen` should not infer persona,
style, or condition semantics from private Python recipe objects, drawing
helpers, filenames, or local implementation details. Downstream caps,
stratification, review, and release decisions remain `hocrgen` policy.

## Rendering Coverage Sidecar

S2e exposes an opt-in `rendering_coverage_report.v1` artifact beside generated
batches. It summarizes covered and missing governed fonts, templates, recipes,
degradation presets, Hebrew text features, mixed-direction evidence, RTL
rendering path evidence, Pillow/libraqm environment status, and page asset smoke
checks. The report uses manifest sample ids and relative portable page asset
paths, and it does not duplicate the manifest payload.

`hocrgen` may consume this report as advisory coverage evidence after validating
the batch manifest. It should not treat the sidecar as release governance,
review state, dedupe state, publication approval, or a replacement for manifest
validation.

## Candidate Lifecycle

1. `hocrsyngen` generates candidate synthetic batch.
2. `hocrsyngen` validates local batch contract.
3. `hocrgen` imports or ingests batch.
4. `hocrgen` applies dataset governance.
5. HeOCR receives only release-approved outputs.

## Post-S4d Production Readiness Dependencies

After S4d, `hocrsyngen` can generate and validate deterministic candidate
batches, but `hocrgen` still needs explicit downstream work before those
candidates can participate in governed dataset flows:

- installed-CLI import adapter and dry-run ingestion;
- release profiles, synthetic caps, and source-composition policy;
- review workflow and any future review evidence sidecar consumption;
- dedupe, leakage, benchmark/reference, release export, and publication gates;
- downstream utility and domain-shift measurement when real references exist.

`hocrsyngen` tracks supporting contract and documentation work in
[production_readiness.md](production_readiness.md) and [roadmap.md](roadmap.md).
The actual adapter, governance, caps, review workflow, and release behavior must
be implemented in `hocrgen`, not in this repository.

## Fixture Expectations For hocrgen Adapter Tests

- Export the packaged fixture through `hocrsyngen contracts export`, not by copying package internals directly.
- Validate the exported fixture with `hocrsyngen validate PATH --format json`.
- Assert the fixture id `generation_manifest_v1_fixture_batch`.
- Assert the manifest contract `generation_manifest.v1`.
- Preserve relative asset paths when importing.
- Recompute hashes or trust only after validation, depending on `hocrgen` policy.
- Treat the fixture as candidate synthetic input, not as a release payload.

## Risks And Open Questions

- `hocrgen` adapter tests should avoid assumptions about private Python dataclass names or package resource paths.
- Any future manifest field needed by `hocrgen` must be added through schema, docs, and tests, with versioning when required.
- Release profile rules and synthetic caps belong in `hocrgen`, not in `hocrsyngen`.
- Richer layout filtering, review evidence, and batch mix orchestration require
  future public contracts before downstream tools rely on them.
