# Document Family Recipes

This document records governed document-family recipes exposed by
`hocrsyngen`. S3b adds the first new family recipe after the S3a layout
metadata boundary decision.

## Metadata Boundary

`generation_manifest.json` v1 is unchanged. Document-family filtering for S3b
uses the existing stable identifiers exposed by `hocrsyngen templates` and by
manifest v1 provenance:

- `template_id`
- `recipe_id`
- `layout_style`
- `font_id`
- `degradation_preset`

The `archive_card` and `ledger` template ids are stable v1 join keys for
downstream tools that need to treat those samples as document families. Richer
capability fields such as `document_family`, `page_regions`,
`annotation_types`, `identifier_types`, and `layout_density` are exposed through
`hocrsyngen templates --format json --catalog-version v2`. They must not be
added as undocumented manifest v1 fields.

## S3b Archive Card

The S3b governed recipe is:

| Field | Value |
| --- | --- |
| Template id | `archive_card` |
| Recipe id | `archive_card_identifier_v1` |
| Layout style | `multi_region_page` |
| Font style | `printed` |
| Font id | `alef-regular` |
| Degradation preset | `office_scan_soft` |

The recipe renders a compact archive-card-like page using only existing
packaged fonts, text corpus lines, degradation presets, and manifest v1
provenance. It includes a bordered card, header/title area, ruled body regions,
synthetic archive identifier, date-like label, footer identifier, and a
synthetic archive stamp. These elements are generator controls and visual
features only. They are not real-source provenance, release eligibility,
authorship, identity, or archive-origin claims.

`archive_card` is available for explicit generation:

```bash
PYTHONPATH=src python -m hocrsyngen.cli generate --count 1 --seed 37 --template-id archive_card --output out/archive-card
```

The default two-sample fixture regeneration command continues to cycle only the
existing `printed_letter` and `handwritten_note` templates so the packaged
manifest v1 contract fixture remains stable.

## S3f Ledger

The S3f governed recipe is:

| Field | Value |
| --- | --- |
| Template id | `ledger` |
| Recipe id | `ledger_table_v1` |
| Layout style | `tabular` |
| Font style | `printed` |
| Font id | `alef-regular` |
| Degradation preset | `office_scan_soft` |

The recipe renders a ledger-like Hebrew page using only existing packaged
fonts, text corpus lines, degradation presets, and manifest v1 provenance. It
includes a printed title, synthetic ledger identifier, date-like label, ruled
table grid, column headers, deterministic row numbers/dates/amounts, small
synthetic tick/correction marks, footer identifier, and page number. These are
generator controls and visual features only. They are not real accounting
records, real-source provenance, release eligibility, authorship, identity, or
institutional claims.

`ledger` is available for explicit generation:

```bash
PYTHONPATH=src python -m hocrsyngen.cli generate --count 1 --seed 53 --template-id ledger --output out/ledger
```

The default two-sample fixture regeneration command continues to cycle only the
existing `printed_letter` and `handwritten_note` templates so the packaged
manifest v1 contract fixture remains stable.

## S3c Degradation Presets

S3c expands governed degradation coverage through explicit template variants.
The variants use the existing `template_catalog.v1` and manifest v1 provenance
fields; they do not add manifest fields, schema changes, review status,
release eligibility, balancing policy, or publication behavior.

This is a manifest v1 compatibility compromise. The variant `template_id` values
carry both the document-family/layout identity and the selected degradation
preset because manifest v1 has no separate `base_template_id`,
`document_family`, or preset-selection field. Downstream consumers that need to
group variants by family should use the documented mapping below, not private
Python recipe names.

| Template id | Recipe id | Base family | Degradation preset |
| --- | --- | --- | --- |
| `printed_letter_heavy_scan` | `printed_letter_form_heavy_scan_v1` | `printed_letter` | `office_scan_heavy` |
| `handwritten_note_heavy_wear` | `handwritten_note_marginalia_heavy_wear_v1` | `handwritten_note` | `notebook_scan_heavy_wear` |
| `archive_card_faded_scan` | `archive_card_identifier_faded_scan_v1` | `archive_card` | `archive_scan_faded` |

The original templates and presets remain governed and unchanged:
`printed_letter` uses `office_scan_soft`, `handwritten_note` uses
`notebook_scan_worn`, and `archive_card` uses `office_scan_soft`. The default
fixture regeneration command still uses only `printed_letter` and
`handwritten_note`.

Reviewers should compare each stronger variant against its base family using the
human criteria in [visual_inspection_rubric.md](visual_inspection_rubric.md).
The short expectation is that stronger skew, blur, grain, or fading should be
visible while Hebrew text, stamps, identifiers, ruled regions, and marginalia
remain inspectable and free of incoherent clipping or overlap.

## Downstream Use

`hocrgen` can discover the recipe before generation through:

```bash
hocrsyngen templates --format json
```

After generation, `hocrgen` can filter validated manifest v1 samples by
`provenance.template_id` and confirm the matching governed recipe/provenance
fields. To group S3c variants and S3f families under manifest v1, `hocrgen`
should join the validated `(template_id, recipe_id)` pair to
`template_catalog.v2`, where `printed_letter_heavy_scan` has base family
`printed_letter`, `handwritten_note_heavy_wear` has base family
`handwritten_note`, `archive_card_faded_scan` has base family `archive_card`,
and `ledger` has base family `ledger`. Any richer durable per-sample metadata
still requires a future manifest/schema update or review sidecar as described
in [layout_metadata_design.md](layout_metadata_design.md).
