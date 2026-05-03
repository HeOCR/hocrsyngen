# generation_manifest.json v1

`generation_manifest.json` v1 is the stable serialized batch contract emitted by `hocrsyngen generate` and validated by `hocrsyngen validate`.

## Top-Level Fields

- `manifest_version`: must be `"1.0"`.
- `generator_name`: must be `"hocrsyngen"`.
- `license`: must be `"PROJECT-SYNTHETIC"`.
- `synthetic_disclosure`: describes the batch as generated synthetic Hebrew OCR/HTR candidate input.
- `samples`: list of generated samples.

## Sample Fields

- `sample_id`: stable deterministic id, currently shaped like `hocrsyngen-s00000017-000000`.
- `pages`: list of page assets.
- `text`: Hebrew logical-order text metadata.
- `generator_version`: generator implementation version string.
- `recipe_id`: governed recipe id and must match `provenance.recipe_id`.
- `provenance`: deterministic generation provenance.
- `license`: must be `"PROJECT-SYNTHETIC"`.
- `synthetic_disclosure`: sample-level synthetic disclosure.
- `controls`: synthetic controls object.

## Page Fields

- `page_id`: page id within the sample, currently `page_0001`.
- `asset_path`: relative portable POSIX path under the batch directory.
- `media_type`: must be `image/jpeg`.
- `sha256`: SHA-256 hash of the asset bytes.
- `width`: JPEG width in pixels.
- `height`: JPEG height in pixels.

## Text Metadata

- `logical_order`: logical-order UTF-8 Hebrew text.
- `script`: must be `Hebr`.
- `language`: must be `he`.
- `direction`: must be `rtl`.
- `unicode_normalization`: must be `NFC`.

## Provenance Fields

- `seed`: generation seed.
- `sample_index`: zero-based sample index.
- `template_id`: governed template id.
- `recipe_id`: governed recipe id.
- `degradation_preset`: governed degradation preset id.
- `font_id`: governed packaged font id.
- `source_corpus`: source corpus identifier.

## Controls

- `persona`: `string|null`.
- `condition`: `string|null`.

These are synthetic generator controls only. They are not real-writer, identity, medical, psychological, or authorship claims.

## Validation Behavior

Validation checks:

- JSON schema validation.
- Manifest and sample constant validation.
- Governed template and provenance validation.
- NFC logical text validation.
- Relative portable asset path validation.
- SHA-256 validation.
- JPEG format and dimension validation.

## Compatibility Rules

- v1 changes should be additive only unless a new version is introduced.
- `hocrgen` consumers should validate using the manifest contract, not private internals.
- New manifest fields require schema, docs, and tests updates.
- Breaking semantic changes require versioned design before implementation.

## Example Shape

```json
{
  "manifest_version": "1.0",
  "generator_name": "hocrsyngen",
  "license": "PROJECT-SYNTHETIC",
  "synthetic_disclosure": "Generated synthetic Hebrew OCR/HTR sample...",
  "samples": [
    {
      "sample_id": "hocrsyngen-s00000017-000000",
      "pages": [
        {
          "page_id": "page_0001",
          "asset_path": "assets/hocrsyngen-s00000017-000000/page_0001.jpg",
          "media_type": "image/jpeg",
          "sha256": "<sha256>",
          "width": 1200,
          "height": 1600
        }
      ],
      "text": {
        "logical_order": "<logical Hebrew text>",
        "script": "Hebr",
        "language": "he",
        "direction": "rtl",
        "unicode_normalization": "NFC"
      },
      "generator_version": "d4a-realism-v2",
      "recipe_id": "printed_letter_form_v1",
      "provenance": {
        "seed": 17,
        "sample_index": 0,
        "template_id": "printed_letter",
        "recipe_id": "printed_letter_form_v1",
        "degradation_preset": "office_scan_soft",
        "font_id": "alef-regular",
        "source_corpus": "packaged_hebrew_lines_v1"
      },
      "license": "PROJECT-SYNTHETIC",
      "synthetic_disclosure": "Generated synthetic Hebrew OCR/HTR sample...",
      "controls": {
        "persona": null,
        "condition": null
      }
    }
  ]
}
```
