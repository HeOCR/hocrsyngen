# hocrsyngen

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

## CLI

```bash
hocrsyngen templates
hocrsyngen generate --count 2 --seed 17 --output out/fixture-batch
hocrsyngen validate out/fixture-batch
```

`hocrsyngen templates` prints one deterministic catalog line per packaged
synthetic template, including the template id, recipe id, layout style, font
style, resolved packaged font id, and degradation preset.

The command writes:

```text
out/fixture-batch/
  generation_manifest.json
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

The governed template contract currently packaged with `hocrsyngen` is:

| Template id | Recipe id | Degradation preset | Recipe font style | Packaged font id |
| --- | --- | --- | --- | --- |
| `printed_letter` | `printed_letter_form_v1` | `office_scan_soft` | `printed` | `alef-regular` |
| `handwritten_note` | `handwritten_note_marginalia_v1` | `notebook_scan_worn` | `handwritten_like` | `gveret-levin-regular` |

The packaged font id is resolved from the packaged default
`data/synthetic/fonts/manifest.yaml` by matching each governed recipe's font
style. Validation is anchored to this default governed catalog; custom Python
API generation inputs are outside the packaged validation contract.

Validation rejects a manifest when `provenance.template_id` is not one of the
packaged governed templates, when the sample-level `recipe_id` differs from
`provenance.recipe_id`, or when the provenance recipe, degradation preset, or
font id does not match the packaged contract for that template.

## Development

```bash
python -m pytest
```
