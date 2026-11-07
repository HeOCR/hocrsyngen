# Printed Glyph Bank v1

`S16a` defines `printed_glyph_bank.v1`, the file contract through which
`hocrsyngen` consumes glyph images cut from real scanned printed Hebrew pages.
The bank is produced outside this repository (the `hocrgen` glyph harvester
reads the real-source snapshots, their splits and rights records). `hocrsyngen`
never fetches, imports, or derives it; it only reads a bank directory.

The motivation is the real-print gap: on the 38 scored real printed pages the
release pipeline scores CER 0.898, while on font-rendered synthetic pages it
scores 0.020. Font-rendered glyphs look nothing like old letterpress. Composing
pages from real glyph images, while keeping exact gold for every placed glyph,
should move the training distribution toward real scans.

## Directory Layout

```text
<bank>/
  printed_glyph_bank.json     # index: bank metadata, sources, styles
  glyphs.jsonl                # one JSON object per glyph
  styles/<style_id>/glyphs/<glyph_id>.png       # grayscale crop (mode L)
  styles/<style_id>/glyphs/<glyph_id>.mask.png  # ink mask (mode 1 or L, ink = 255)
  styles/<style_id>/paper/<patch_id>.png        # ink-free paper patch (mode L)
```

All paths in the index and in `glyphs.jsonl` are relative POSIX paths under the
bank root, never absolute and never `..`.

## Index (`printed_glyph_bank.json`)

```jsonc
{
  "schema": "printed_glyph_bank.v1",
  "bank_id": "pgb-<short id>",
  "created_by": {"tool": "hocrgen.tools.glyph_harvest", "version": "...", "config_sha256": "<64 hex>"},
  "glyph_count": 123456,
  "glyphs_sha256": "<sha256 of glyphs.jsonl bytes>",
  "sources": [
    {"source_id": "wikisource_he_proofread", "snapshot": "...", "licence": "PD", "notes": "..."}
  ],
  "exclusions": ["test and validation split works", "the 38 scored reference pages", "..."],
  "styles": [
    {
      "style_id": "ws-1711486",            // one typeface/printing: normally one book
      "source_id": "wikisource_he_proofread",
      "work_id": "1711486",
      "licence": "PD",                     // PD, CC0-1.0 or CC-BY-4.0
      "attribution": null,                 // required text when licence is CC-BY-4.0
      "born_digital": false,
      "work_match_key": "commons_file:<sha1>", // hocrgen work-group key, for leakage registration
      "metrics": {
        "x_height_px": 22.0,               // median height of base-line-only letters (no ascender/descender)
        "line_pitch_px": 48.0,             // median baseline-to-baseline distance
        "letter_gap_px": [1.0, 3.0, 6.0],  // p10, median, p90 ink gap between letters inside a word
        "word_gap_px": [8.0, 12.0, 20.0],  // p10, median, p90 ink gap between words on a line
        "text_block_width_px": 1300,       // median line width of full lines
        "page_size_px": [1920, 2768],
        "ink_gray": 40,                    // median ink gray level (0..255)
        "paper_gray": 225                  // median paper gray level
      },
      "paper_patches": ["styles/ws-1711486/paper/p000.png"],
      "glyph_count": 4321
    }
  ]
}
```

## Glyph Records (`glyphs.jsonl`)

```jsonc
{
  "glyph_id": "ws-1711486-000123",
  "style_id": "ws-1711486",
  "char": "א",                     // exactly one Unicode code point, NFC
  "asset_path": "styles/ws-1711486/glyphs/ws-1711486-000123.png",
  "mask_path": "styles/ws-1711486/glyphs/ws-1711486-000123.mask.png",
  "size": [31, 40],                // crop width, height in px
  "ink_box": [3, 4, 28, 30],       // x0, y0, x1, y1 of the ink inside the crop (x1, y1 exclusive)
  "baseline_y": 30,                // y of the source line's baseline inside the crop
  "x_height_px": 22.0,             // x-height of the source word (median height of its x-height letters)
  "source": {"page_id": "...", "box_in_source": [x0, y0, x1, y1], "word_index": 17, "position_in_word": 2},
  "quality": {"method": "cc_word_alignment", "score": 0.91}
}
```

- `char` covers Hebrew letters including final forms, digits, and punctuation.
  Niqqud and cantillation are not separate glyphs in v1; harvesters skip words
  that carry them.
- `baseline_y` lets the composer seat every glyph on a common baseline: letters
  sit on it, final ך ן ף ץ and ק descend below it, ל rises above.
- `x_height_px` matters because one book often mixes type sizes and faces: body
  text, smaller commentary (often Rashi script) and larger headings. A composer
  keeps every line inside one size band (for example within ±12% of a target
  x-height), so the faces in one line don't mix.
- The style's `char_counts` maps each character to its glyph count.
- The crop keeps the original scan pixels, including paper around the ink. The
  mask marks the glyph's own ink only, so a neighbouring letter's stray ink
  inside the crop is not composited.
- `quality.score` is in `0..1`; consumers may set a minimum.

## Rights

Only scans that are public domain (Israel; US status recorded per source), CC0
1.0, or CC BY 4.0 enter a bank. Share-alike and non-commercial scan licences are
excluded. A glyph image carries its source scan's rights; the character identity
it is labelled with is a fact, not the text licence. Composed pages record every
style they use in a provenance sidecar so attribution can be honoured.
Restricted evaluation material (for example the tender pages) must never enter
a bank.

## Leakage

A bank must not contain glyphs from any page or work in a real evaluation or
validation split, nor from the 38 scored reference pages. Harvesters register
the works they used in `hocrgen`'s `synthetic_training_works.yaml` so later
splits keep those works in `train`.

## Consumer Notes (hocrsyngen S16b)

`hocrsyngen` validates a bank with
`src/hocrsyngen/schemas/printed_glyph_bank.schema.json` and the checks in
`src/hocrsyngen/glyph_bank.py`. The schema is open: extra fields are allowed.

- `bank_id` matches `pgb-[A-Za-z0-9._-]+`; `style_id`, `source_id` and
  `glyph_id` match `[A-Za-z0-9][A-Za-z0-9._-]*`.
- A source's `licence` is free text describing the source. The normative
  licence is each style's `licence`: `PD`, `CC0-1.0` or `CC-BY-4.0`, and
  `CC-BY-4.0` needs a non-empty `attribution`.
- `glyph_count` (bank and per style) and `char_counts`, when present, must
  match the glyph records exactly.
- `char` is the logical character as it appears in RTL text. A bracket cut
  from RTL text is therefore labelled with its logical character and shows the
  mirrored shape; composers draw it as is.
- `baseline_y` may lie outside the crop (`< 0` or `> height`), for example
  for a geresh cropped tightly above the baseline.
- `x_height_px` on a glyph record is optional for consumers; without it the
  style's `metrics.x_height_px` is assumed.
- `ink_box` must lie inside `size`, and the PNG sizes must equal `size`.
- The mask must cover every stroke of the glyph, including detached parts
  such as the left leg of ה, the foot of ג or the tail of ק. The composer
  rejects a glyph when more than 6% of the crop's dark pixels inside its
  `ink_box` fall outside its mask dilated by 1 px, because such a glyph draws
  a different letter. Dark means below background − 0.5 × (background − ink),
  measured on the crop itself.
- `metrics.x_height_px`, `line_pitch_px` and `text_block_width_px` must be
  positive; a style without measurable metrics must be left out of the bank,
  since one invalid style rejects the whole bank.
- `paper_patches` may be empty; the composer then synthesises grain (or uses
  white paper for a bitonal style).
- Paper patches should be clean paper: the composer uses only their high-pass
  texture and rejects patches with shadows, gradients, stains, sharp marks or
  straight streaks. A style whose `paper_gray` is 250 or more is treated as a
  bitonal render and gets plain white paper.
- `metrics.line_pitch_px` is the body type's baseline-to-baseline distance.
  The composer never uses less than 1.6 × `x_height_px`.
