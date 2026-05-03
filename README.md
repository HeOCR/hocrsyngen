# hocrsyngen

Synthetic Hebrew OCR/HTR sample generation for the HeOCR project.

This package owns deterministic synthetic sample generation. `hocrgen` remains
responsible for dataset orchestration, governance, validation, release assembly,
and export to `HeOCR` and `HeOCRsynth`.

## Scope

- Generate governed synthetic Hebrew OCR/HTR fixture batches.
- Emit `generation_manifest.json` with relative page assets.
- Preserve logical-order UTF-8 Hebrew text with RTL metadata.
- Keep the baseline package free of REST, GPU, LLM, diffusion, and network
  dependencies.

Generated directories are candidate synthetic inputs for later `hocrgen`
governance. They are not release-ready dataset payloads by themselves.

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
seed provenance, `PROJECT-SYNTHETIC` licensing, synthetic disclosure, and
optional persona/condition controls only.

`hocrsyngen validate PATH` checks `PATH/generation_manifest.json` against the
packaged manifest schema, verifies v1 constants and Hebrew RTL metadata,
confirms referenced page assets are portable paths under `PATH`, recomputes
asset SHA-256 values, and verifies JPEG dimensions match the manifest. The
command is read-only and returns a non-zero exit code with deterministic errors
when a generated batch is invalid.

## Development

```bash
python -m pytest
```
