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
hocrsyngen generate --count 2 --seed 17 --output out/fixture-batch
```

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

## Development

```bash
python -m pytest
```
