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

The `archive_card` template id is the stable v1 join key for downstream tools
that need to treat archive-card samples as a document family. Richer capability
fields such as `document_family`, `page_regions`, `annotation_types`,
`identifier_types`, and `layout_density` remain future catalog or schema work.
They must not be added as undocumented manifest v1 fields.

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

## Downstream Use

`hocrgen` can discover the recipe before generation through:

```bash
hocrsyngen templates --format json
```

After generation, `hocrgen` can filter validated manifest v1 samples by
`provenance.template_id == "archive_card"` and confirm the matching governed
recipe/provenance fields. Any richer filtering by page regions, identifiers,
reviewability, density, or annotations requires a future stable catalog version,
manifest/schema update, or review sidecar as described in
[layout_metadata_design.md](layout_metadata_design.md).
