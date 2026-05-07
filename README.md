# hocrsyngen

[![CI](https://github.com/HeOCR/hocrsyngen/actions/workflows/ci.yml/badge.svg)](https://github.com/HeOCR/hocrsyngen/actions/workflows/ci.yml)

Synthetic Hebrew OCR/HTR sample generation for the HeOCR project.

This package owns deterministic candidate synthetic sample generation. `hocrgen`
remains responsible for dataset orchestration, governance, validation, release
assembly, and export to `HeOCR` and `HeOCRsynth`.

## Scope

- Generate governed synthetic Hebrew OCR/HTR fixture batches.
- Emit `generation_manifest.json` with relative page assets.
- Preserve logical-order UTF-8 Hebrew text with RTL metadata.
- Keep the baseline package free of REST, GPU, LLM, diffusion, and network
  dependencies.

Generated directories are deterministic candidate synthetic inputs for later
`hocrgen` governance. They are not release-ready dataset payloads by themselves.

## Project Documentation

- [Documentation index](docs/README.md)
- [Repository scope](docs/repository_scope.md)
- [Architecture](docs/architecture.md)
- [generation_manifest.json v1](docs/generation_manifest_v1.md)
- [hocrgen integration](docs/hocrgen_integration.md)
- [Production readiness](docs/production_readiness.md)
- [Roadmap](docs/roadmap.md)
- [Research program](docs/research_program.md)
- [Handwriting research acceptance criteria](docs/handwriting_research_acceptance_criteria.md)
- [Allograph and character-level prototype plan](docs/allograph_character_prototype_plan.md)
- [Word and line assembly prototype plan](docs/word_line_assembly_prototype_plan.md)
- [Learned generation packaging boundary](docs/learned_generation_packaging_boundary.md)
- [Testing and quality](docs/testing_and_quality.md)

## CLI

```bash
hocrsyngen templates
hocrsyngen templates --format json
hocrsyngen templates --format json --catalog-version v2
hocrsyngen generate --count 2 --seed 17 --output out/fixture-batch
hocrsyngen generate --count 2 --seed 17 --output out/fixture-batch --format json
hocrsyngen generate --count 2 --seed 17 --output out/fixture-batch --rendering-coverage-report
hocrsyngen validate out/fixture-batch
hocrsyngen validate out/fixture-batch --format json
```

`hocrsyngen templates` prints one deterministic catalog line per packaged
synthetic template, including the template id, recipe id, layout style, font
style, resolved packaged font id, and degradation preset.

Text output remains the default for human-facing CLI use. `hocrsyngen templates
--format json` emits the same governed template catalog as deterministic
machine-readable metadata for orchestration code that should not import
`hocrsyngen` internals. This abbreviated example shows the shape of the
machine-readable catalog:

```json
{
  "schema_version": "template_catalog.v1",
  "templates": [
    {
      "template_id": "printed_letter",
      "recipe_id": "printed_letter_form_v1",
      "layout_style": "printed_form",
      "font_style": "printed",
      "font_id": "alef-regular",
      "degradation_preset": "office_scan_soft"
    },
    {
      "template_id": "handwritten_note",
      "recipe_id": "handwritten_note_marginalia_v1",
      "layout_style": "handwritten_note",
      "font_style": "handwritten_like",
      "font_id": "gveret-levin-regular",
      "degradation_preset": "notebook_scan_worn"
    }
  ]
}
```

The JSON catalog is package metadata only. It does not change manifest v1 and
does not assemble, validate, export, or publish release payloads; those remain
`hocrgen` responsibilities.

`hocrsyngen templates --format json --catalog-version v2` emits the versioned
`template_catalog.v2` surface. The normative schema is
`src/hocrsyngen/schemas/template_catalog.schema.json`. The v2 catalog preserves
the v1 join keys and adds
`document_family`, `base_family`, `page_regions`, `annotation_types`,
`identifier_types`, `layout_density`, and `review_features` so downstream tools
can join validated manifest `template_id` and `recipe_id` provenance to richer
catalog metadata without importing private recipe internals. Manifest v1 remains
unchanged. The v2 catalog is JSON-only; `--catalog-version v2` must be used with
`--format json`.

The current `hocrsyngen` baseline is ready to generate validated candidate
synthetic batches with the governed document families added through S3f, while
S5 planning now defines acceptance gates plus docs-first allograph, word/line
assembly, and learned-generation packaging boundaries for future handwriting
research.
Readiness for public dataset use still depends on downstream `hocrgen` import
governance, review, caps, dedupe, release assembly, export, and publication
policy.

Text output remains the default generation behavior for human-facing CLI use;
successful generation does not print a report unless requested.
`hocrsyngen generate --count N --seed S --output PATH --format json` writes the
same deterministic batch and emits a deterministic machine-readable generation
report to stdout:

```json
{
  "schema_version": "generation_report.v1",
  "sample_count": 2,
  "page_count": 2,
  "output_path": "out/fixture-batch",
  "manifest_path": "out/fixture-batch/generation_manifest.json"
}
```

The generation report is CLI output only. It does not add manifest fields or
change manifest v1 compatibility.

`hocrsyngen generate --rendering-coverage-report` writes an opt-in
`rendering_coverage_report.json` sidecar beside the manifest. The sidecar uses
report version `rendering_coverage_report.v1` and summarizes covered and missing
Hebrew rendering dimensions for the generated batch, including governed fonts,
templates, recipes, degradation presets, text features, mixed-direction
evidence, RTL rendering path evidence, environment status, and page asset smoke
checks. It is coverage evidence outside manifest v1, not review, release,
export, or publication metadata. `hocrsyngen validate` does not require or
inspect the sidecar.

The command writes:

```text
out/fixture-batch/
  generation_manifest.json
  rendering_coverage_report.json  # only with --rendering-coverage-report
  assets/
    hocrsyngen-s00000017-000000/page_0001.jpg
    hocrsyngen-s00000017-000001/page_0001.jpg
```

Manifest v1 includes stable sample ids, relative image paths, logical-order
Hebrew text, script/language/direction metadata, generator version, recipe id,
seed/template/recipe/degradation/font provenance, `PROJECT-SYNTHETIC` licensing,
synthetic disclosure, and a required controls object with nullable
persona/condition values only. The governed template contract is enforced
through the existing `sample.recipe_id`, `sample.provenance.template_id`,
`sample.provenance.recipe_id`, `sample.provenance.degradation_preset`, and
`sample.provenance.font_id` fields; no extra manifest fields are required.

`hocrsyngen generate --persona STYLE_ID` selects a deterministic synthetic style
bundle and writes the selected id to `controls.persona`. Supported S4b style ids
are `style_standard_v1`, `style_open_drift_v1`, and
`style_compact_steady_v1`. These are neutral generator controls for rendering
parameters such as spacing, baseline drift, horizontal variance, and ink
pressure proxy; they are not identity, authorship, provenance, medical,
psychological, disability, demographic, review, release, or publication
metadata.

`hocrsyngen generate --condition CONDITION_ID` selects a deterministic synthetic
rendering-control condition bundle and writes the selected id to
`controls.condition`. Supported S4c condition ids are `condition_standard_v1`,
`condition_low_contrast_v1`, and `condition_dense_spacing_v1`. These ids describe
neutral rendering adjustments such as scan contrast, blur, brightness, and body
text line-spacing density. Dense spacing tightens rendered body text line
placement only; it does not rescale template guide lines, form rows, archive
card grids, stamps, marginalia, or other scaffolding. These ids are not
identity, authorship, provenance, medical, psychological, disability,
demographic, review, release, or publication metadata, and they do not add a
`condition` object or richer manifest v1 metadata.

`hocrsyngen validate PATH` checks `PATH/generation_manifest.json` against the
packaged manifest schema, verifies v1 constants and Hebrew RTL metadata,
verifies top-level constants (`manifest_version`, `generator_name`, `license`,
and `synthetic_disclosure`), verifies sample-level constants (`license`,
`synthetic_disclosure`, and `generator_version`), confirms each sample's
recipe/provenance fields match a governed packaged template contract, confirms
referenced page assets are portable paths under `PATH`, recomputes asset SHA-256
values, and verifies JPEG dimensions match the manifest. The command is
read-only and returns a non-zero exit code with deterministic errors when a
generated batch is invalid.

Text output remains the default validation report for human-facing CLI use.
`hocrsyngen validate PATH --format json` emits a deterministic
machine-readable validation report to stdout without changing manifest v1. The
`path` field echoes the original CLI argument string, not a resolved canonical
filesystem path:

```json
{
  "schema_version": "validation_report.v1",
  "valid": true,
  "sample_count": 2,
  "page_count": 2,
  "path": "out/fixture-batch"
}
```

Invalid batches keep the non-zero validation exit code and emit a deterministic
JSON error report to stdout when JSON output is requested. Validation errors
encoded in JSON leave stderr empty:

```json
{
  "schema_version": "validation_report.v1",
  "valid": false,
  "path": "out/fixture-batch",
  "error": "Missing manifest: out/fixture-batch/generation_manifest.json"
}
```

The governed template contract currently packaged with `hocrsyngen` is:

| Template id | Recipe id | Degradation preset | Recipe font style | Packaged font id |
| --- | --- | --- | --- | --- |
| `printed_letter` | `printed_letter_form_v1` | `office_scan_soft` | `printed` | `alef-regular` |
| `handwritten_note` | `handwritten_note_marginalia_v1` | `notebook_scan_worn` | `handwritten_like` | `gveret-levin-regular` |
| `archive_card` | `archive_card_identifier_v1` | `office_scan_soft` | `printed` | `alef-regular` |
| `ledger` | `ledger_table_v1` | `office_scan_soft` | `printed` | `alef-regular` |
| `printed_letter_heavy_scan` | `printed_letter_form_heavy_scan_v1` | `office_scan_heavy` | `printed` | `alef-regular` |
| `handwritten_note_heavy_wear` | `handwritten_note_marginalia_heavy_wear_v1` | `notebook_scan_heavy_wear` | `handwritten_like` | `gveret-levin-regular` |
| `archive_card_faded_scan` | `archive_card_identifier_faded_scan_v1` | `archive_scan_faded` | `printed` | `alef-regular` |

The packaged font id is resolved from the packaged default
`data/synthetic/fonts/manifest.yaml` by matching each governed recipe's font
style. Validation is anchored to this default governed catalog; custom Python
API generation inputs are outside the packaged validation contract.

Validation rejects a manifest when `provenance.template_id` is not one of the
packaged governed templates, when the sample-level `recipe_id` differs from
`provenance.recipe_id`, or when the provenance recipe, degradation preset, or
font id does not match the packaged contract for that template.

## Contract Fixture for hocrgen Integration

`hocrsyngen` packages a canonical generated batch fixture at:

```text
src/hocrsyngen/data/contracts/generation_manifest_v1/fixture-batch/
```

From a source checkout, reproduce the current fixture with:

```bash
PYTHONPATH=src python -m hocrsyngen.cli generate --count 2 --seed 17 --output src/hocrsyngen/data/contracts/generation_manifest_v1/fixture-batch
```

Downstream packages should discover and export this packaged fixture through the
installed `hocrsyngen` CLI instead of importing `hocrsyngen` internals:

```bash
hocrsyngen contracts
hocrsyngen contracts --format json
hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output out/fixture-batch
hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output out/fixture-batch --format json
```

The current contract fixture id is
`generation_manifest_v1_fixture_batch`. `hocrsyngen contracts --format json`
emits a deterministic package fixture catalog:

```json
{
  "schema_version": "contract_fixture_catalog.v1",
  "fixtures": [
    {
      "fixture_id": "generation_manifest_v1_fixture_batch",
      "contract": "generation_manifest.v1",
      "sample_count": 2,
      "page_count": 2,
      "resource_path": "data/contracts/generation_manifest_v1/fixture-batch",
      "manifest_resource_path": "data/contracts/generation_manifest_v1/fixture-batch/generation_manifest.json"
    }
  ]
}
```

`hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch
--output PATH --format json` copies the packaged fixture batch to a normal
filesystem directory, validates the exported batch with `validate_batch()`, and
emits a deterministic machine-readable export report:

```json
{
  "schema_version": "contract_fixture_export.v1",
  "fixture_id": "generation_manifest_v1_fixture_batch",
  "contract": "generation_manifest.v1",
  "sample_count": 2,
  "page_count": 2,
  "output_path": "out/fixture-batch",
  "manifest_path": "out/fixture-batch/generation_manifest.json"
}
```

This CLI/package boundary gives `hocrgen` a stable installed-package contract
without depending on private module names, resource layout helpers, or Python
objects inside `hocrsyngen`.

It contains `generation_manifest.json` v1 plus relative JPEG page assets for
two stable fixture samples, currently covering `printed_letter` and
`handwritten_note`. The fixture is contract evidence for downstream `hocrgen`
adapter tests and is candidate synthetic input only; it is not release-ready
dataset data. `hocrgen` should ingest or validate the fixture manifest,
preserve the relative asset contract, and then apply its own governance,
privacy, review, dedupe, split, cap, benchmark, release, and export gates.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest
```

The GitHub Actions CI workflow runs the test suite, required CLI smoke commands,
Pillow libraqm checks for Hebrew RTL rendering, and package build/install checks
on Ubuntu and macOS for Python 3.11 and 3.12.

See `docs/testing_and_quality.md` for the canonical Python support policy.
