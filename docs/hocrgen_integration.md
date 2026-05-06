# hocrgen Integration Contract

`hocrgen` should consume `hocrsyngen` through the installed-package CLI and serialized manifest/fixture contracts. It should not import private `hocrsyngen` internals.

## Stable Integration Commands

```bash
hocrsyngen templates --format json
hocrsyngen contracts --format json
hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json
hocrsyngen generate --count N --seed S --output PATH --format json
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
presets. After generation, it can validate `generation_manifest.json` v1 and
filter only on manifest provenance fields: template id, recipe id, degradation
preset, font id, seed, sample index, and source corpus. Manifest v1 does not
carry document family, font style, page regions, marginalia, stamps,
identifiers, density, or reviewability. Those fields require a future stable
catalog join, versioned manifest/schema change, or explicit sidecar artifact;
they should not be inferred from private Python recipe, document, or drawing
helpers.

The S3c stronger degradation variants are exposed as separate `template_id`
values because manifest v1 does not have a separate preset-selection field or
base-template field. Downstream grouping should use this documented public
mapping until a future catalog/schema exposes base-family metadata:

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

Until a future public catalog, manifest/schema update, or explicit sidecar
artifact exposes richer control metadata, `hocrgen` should not infer persona,
style, or condition semantics from private Python recipe objects, drawing
helpers, filenames, or local implementation details. Downstream caps,
stratification, review, and release decisions remain `hocrgen` policy.

## Candidate Lifecycle

1. `hocrsyngen` generates candidate synthetic batch.
2. `hocrsyngen` validates local batch contract.
3. `hocrgen` imports or ingests batch.
4. `hocrgen` applies dataset governance.
5. HeOCR receives only release-approved outputs.

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
