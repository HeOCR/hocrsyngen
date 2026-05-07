# generation_manifest.json v1

`generation_manifest.json` v1 is the stable serialized batch contract emitted by `hocrsyngen generate` and validated by `hocrsyngen validate`.

The normative machine-readable schema is `src/hocrsyngen/schemas/generation_manifest.schema.json`. This document explains the contract and records validation semantics; if this document and the schema disagree, fix both before changing generator behavior.

All v1 objects currently set `additionalProperties: false` in the schema. Consumers should reject unknown fields unless a future additive schema update explicitly permits them.

The exact v1 synthetic disclosure string is:

```text
Generated synthetic Hebrew OCR/HTR sample. It is candidate synthetic input for hocrgen governance and is not real-source provenance.
```

## Top-Level Fields

- `manifest_version`: must be `"1.0"`.
- `generator_name`: must be `"hocrsyngen"`.
- `license`: must be `"PROJECT-SYNTHETIC"`.
- `synthetic_disclosure`: must be the exact v1 synthetic disclosure string.
- `samples`: list of generated samples. The current schema allows an empty array; generator output is expected to contain the requested generated samples.

## Sample Fields

- `sample_id`: stable deterministic id matching `^hocrsyngen-s[0-9]{8}-[0-9]{6}$`.
- `pages`: list of page assets with at least one page.
- `text`: Hebrew logical-order text metadata.
- `generator_version`: non-empty generator implementation version string. Current validation requires the package's current generator version.
- `recipe_id`: non-empty governed recipe id and must match `provenance.recipe_id`.
- `provenance`: deterministic generation provenance.
- `license`: must be `"PROJECT-SYNTHETIC"`.
- `synthetic_disclosure`: must be the exact v1 synthetic disclosure string.
- `controls`: synthetic controls object.

## Page Fields

- `page_id`: non-empty canonical page id exactly as serialized in the
  manifest. Current generated page ids include the sample id prefix, for
  example `hocrsyngen-s00000017-000000-page-0001`. Consumers must not derive
  canonical page ids from asset filenames such as `page_0001.jpg`, and should
  treat any display key or storage key as separate downstream metadata.
- `asset_path`: relative portable POSIX path under the batch directory. The schema pattern is `^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+$`; validation also rejects paths that resolve outside the batch directory.
- `media_type`: must be `image/jpeg`.
- `sha256`: lowercase hex SHA-256 hash of the asset bytes matching `^[0-9a-f]{64}$`.
- `width`: JPEG width in pixels, integer `>= 1`.
- `height`: JPEG height in pixels, integer `>= 1`.

## Text Metadata

- `logical_order`: non-empty logical-order UTF-8 Hebrew text and must be NFC-normalized.
- `script`: must be `Hebr`.
- `language`: must be `he`.
- `direction`: must be `rtl`.
- `unicode_normalization`: must be `NFC`.

## Provenance Fields

- `seed`: integer generation seed.
- `sample_index`: zero-based integer sample index.
- `template_id`: non-empty governed template id.
- `recipe_id`: non-empty governed recipe id.
- `degradation_preset`: non-empty governed degradation preset id.
- `font_id`: non-empty governed packaged font id.
- `source_corpus`: non-empty source corpus identifier.

## Controls

- `persona`: `string|null`.
- `condition`: `string|null`.

These are synthetic generator controls only. They are not real-writer, identity, medical, psychological, or authorship claims.
Persona, style, and condition semantics are governed by
[ADR 0005](decisions/0005-persona-style-condition-semantics.md): current v1
controls are `string|null` synthetic control slots, not richer machine-readable
identity, health, authorship, provenance, review, or release metadata.

S4b deterministic style bundles are selected through the existing
`hocrsyngen generate --persona STYLE_ID` option and are serialized only as
`controls.persona`. Supported style bundle ids are `style_standard_v1`,
`style_open_drift_v1`, and `style_compact_steady_v1`. These ids describe
synthetic rendering parameters such as line spacing, baseline drift, horizontal
line-position variance, and ink pressure proxy; they do not add a `style` field
or any richer manifest v1 metadata.

S4c deterministic condition bundles are selected through the existing
`hocrsyngen generate --condition CONDITION_ID` option and are serialized only as
`controls.condition`. Supported condition bundle ids are
`condition_standard_v1`, `condition_low_contrast_v1`, and
`condition_dense_spacing_v1`. These ids describe synthetic rendering-control
parameters such as scan contrast, blur, brightness, and line-spacing density.
Dense spacing tightens rendered body text line placement only; it does
not rescale template guide lines, form rows, archive card grids, stamps,
marginalia, or other scaffolding. These ids do not add a `condition` object or
any richer manifest v1 metadata.

## Validation Behavior

Validation checks:

- JSON schema validation.
- Manifest and sample constant validation.
- Governed template and provenance validation.
- NFC logical text validation.
- Relative portable asset path validation.
- SHA-256 validation.
- JPEG format and dimension validation.

The governed template contract currently requires:

| Template id | Recipe id | Degradation preset | Packaged font id |
| --- | --- | --- | --- |
| `printed_letter` | `printed_letter_form_v1` | `office_scan_soft` | `alef-regular` |
| `handwritten_note` | `handwritten_note_marginalia_v1` | `notebook_scan_worn` | `gveret-levin-regular` |
| `archive_card` | `archive_card_identifier_v1` | `office_scan_soft` | `alef-regular` |
| `ledger` | `ledger_table_v1` | `office_scan_soft` | `alef-regular` |
| `printed_letter_heavy_scan` | `printed_letter_form_heavy_scan_v1` | `office_scan_heavy` | `alef-regular` |
| `handwritten_note_heavy_wear` | `handwritten_note_marginalia_heavy_wear_v1` | `notebook_scan_heavy_wear` | `gveret-levin-regular` |
| `archive_card_faded_scan` | `archive_card_identifier_faded_scan_v1` | `archive_scan_faded` | `alef-regular` |

## Compatibility Rules

- v1 changes should be additive only unless a new version is introduced.
- `hocrgen` consumers should validate using the manifest contract, not private internals.
- New manifest fields require schema, docs, and tests updates.
- Breaking semantic changes require versioned design before implementation.
- Richer persona, style, or condition metadata requires a documented catalog,
  sidecar, or manifest/schema update before it becomes a public machine
  contract.
- Richer S3e template metadata is exposed through `template_catalog.v2`, not
  through new manifest v1 fields. Consumers can join validated
  `provenance.template_id` and `provenance.recipe_id` to
  `hocrsyngen templates --format json --catalog-version v2`.
- Optional learned-generation metadata, if ever explored, must stay outside
  manifest v1 in an explicitly designed experiment packet, sidecar, catalog,
  optional package, or separate repository until a versioned contract update is
  approved. Manifest v1 must not gain model, weights, dataset, evaluation,
  review, release, writer, identity, authorship, or provenance claims as a side
  effect of learned-generation research.
- Downstream release cap policy, source composition, reviewer state, release
  eligibility, export, publication, and governance enforcement remain outside
  manifest v1. S6d release cap decisions may cite manifest sample/page ids,
  public provenance fields, controls, `template_catalog.v2`, optional rendering
  coverage, and downstream evidence packet ids, but those decisions must be
  stored in `hocrgen`/HeOCR governance records or future downstream contracts.
- Downstream review evidence sidecars remain outside manifest v1. S6e review
  sidecars may cite manifest sample/page ids, public provenance fields,
  controls, `template_catalog.v2`, optional rendering coverage, S6a categories,
  S6c warnings, and S6d cap decision references, but review workflow state,
  visual evidence storage, reviewer notes, approvals, holds, rejections,
  release eligibility, export, publication, and governance enforcement must be
  stored downstream in `hocrgen`/HeOCR records or future downstream contracts.
- Downstream candidate batch profile and mix records remain outside manifest v1.
  S6f profiles may cite manifest sample/page ids, public provenance fields,
  controls, `template_catalog.v2`, optional rendering coverage, and
  S6a/S6c/S6d/S6e evidence references when recording requested,
  generated/observed, reviewed, capped/admitted, or released mix layers. Profile
  ownership, balancing, orchestration, caps, release profiles, release
  eligibility, export, publication, and governance enforcement must be stored
  downstream in `hocrgen`/HeOCR records or future downstream contracts.
- Downstream adapter import state remains outside manifest v1. S6g adapter
  checklists may require `hocrgen` to retain canonical manifest sample/page ids,
  relative asset paths, validation reports, generation reports, fixture export
  reports, `template_catalog.v2` joins, optional rendering coverage, and S6a-S6f
  evidence links, but import ids, dry-run ids, adapter workflow state, storage,
  review, caps, export, publication, and governance enforcement must be stored
  downstream.

## Example Shape

```json
{
  "manifest_version": "1.0",
  "generator_name": "hocrsyngen",
  "license": "PROJECT-SYNTHETIC",
  "synthetic_disclosure": "Generated synthetic Hebrew OCR/HTR sample. It is candidate synthetic input for hocrgen governance and is not real-source provenance.",
  "samples": [
    {
      "sample_id": "hocrsyngen-s00000017-000000",
      "pages": [
        {
          "page_id": "hocrsyngen-s00000017-000000-page-0001",
          "asset_path": "assets/hocrsyngen-s00000017-000000/page_0001.jpg",
          "media_type": "image/jpeg",
          "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
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
      "synthetic_disclosure": "Generated synthetic Hebrew OCR/HTR sample. It is candidate synthetic input for hocrgen governance and is not real-source provenance.",
      "controls": {
        "persona": null,
        "condition": null
      }
    }
  ]
}
```

This example is schema-shaped and copyable JSON. It is not a complete valid batch by itself because the placeholder SHA-256 must match an actual JPEG asset on disk.
