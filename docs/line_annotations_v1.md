# Line Annotations Sidecar v1

`S10a` adds an opt-in per-line geometry sidecar so generated pages can become
line-level recognizer training data (for example Kraken/ketos). It is written
next to `generation_manifest.json` and does not change manifest v1, its schema,
the packaged contract fixture, or any page asset. `S11a` adds region geometry
and region reading order (see Regions) so a layout segmenter can be trained on
the same pages.

```bash
hocrsyngen generate --count 80 --seed 101 --output out/batch \
  --template-id printed_letter --template-id handwritten_note \
  --emit-line-annotations
hocrsyngen evidence-run --count 80 --seed 101 --emit-line-annotations
hocrsyngen validate out/batch
```

Normative schema: `src/hocrsyngen/schemas/line_annotations.schema.json`.

## Why A Sidecar

[layout_metadata_design.md](layout_metadata_design.md) reserves durable
per-sample layout metadata for a future manifest version. Line geometry is a
derived training artifact, not sample identity: it is only useful together with
the exact page bytes it was measured on. The sidecar therefore binds itself to
one manifest by content hash (`generation_manifest_sha256`) and to each page by
`page_sha256`, and stays opt-in so default batches are unchanged.

## Payload

Three lines and three of the seven regions of seed-101 sample 0
(`printed_letter`, generator `s10c-gold-complete-v1`):

```json
{
  "schema": "hocrsyngen_line_annotations.v1",
  "generation_manifest_sha256": "c4b4ca4ed5b92080c0a4d13c4fa2da505080da11b37203ecb0d4fa1bcb164ec3",
  "coordinate_space": "final_page_pixels",
  "pages": [
    {
      "sample_id": "hocrsyngen-s00000101-000000",
      "page_id": "hocrsyngen-s00000101-000000-page-0001",
      "page_sha256": "12d320d667074a881214bddb7ef42feb42298b5aa42007cbbf29b658051d756b",
      "width": 1200,
      "height": 1600,
      "truncated_segments": 0,
      "lines": [
        {"line_index": 0, "logical_line_index": 0, "logical_join": null, "occluded": false,
         "region": "title", "region_index": 0, "text": "מכתב מנהלי",
         "polygon": [[775, 123], [1082, 122], [1082, 172], [775, 173]], "baseline": [[779, 167], [1078, 166]]},
        {"line_index": 1, "logical_line_index": 1, "logical_join": null, "occluded": true,
         "region": "body", "region_index": 1, "text": "בדיקת אותיות סופיות ךםןףץ נשמרה ברשימת הבקרה.",
         "polygon": [[218, 256], [1104, 252], [1104, 289], [218, 293]], "baseline": [[222, 283], [1100, 279]]},
        {"line_index": 5, "logical_line_index": 5, "logical_join": null, "occluded": false,
         "region": "stamp_area", "region_index": 2, "text": "נבדק",
         "polygon": [[337, 324], [398, 324], [398, 350], [337, 350]], "baseline": [[341, 342], [394, 342]]}
      ],
      "regions": [
        {"region_index": 0, "type": "title", "reading_order_index": 0, "line_indices": [0],
         "polygon": [[771, 119], [1086, 118], [1086, 176], [771, 177]]},
        {"region_index": 1, "type": "body", "reading_order_index": 1, "line_indices": [1, 2, 3, 4],
         "polygon": [[214, 252], [1108, 248], [1109, 497], [215, 501]]},
        {"region_index": 2, "type": "stamp_area", "reading_order_index": 2, "line_indices": [5],
         "polygon": [[219, 265], [445, 264], [445, 392], [219, 393]]}
      ]
    }
  ]
}
```

Page fields:

- `pages` follow manifest order (samples, then pages).
- `sample_id`, `page_id`, `page_sha256`, `width`, `height` match the manifest.
- `truncated_segments` counts wrapped body segments that the template's body
  cap left undrawn (see Body Capacity And Truncation). It is always `0` for
  uncapped templates.

Line fields:

| Field | Meaning |
| --- | --- |
| `line_index` | `0..n-1` in logical (reading) order: sorted by `logical_line_index`, ties in drawing order. |
| `logical_line_index` | Index into `sample.text.logical_order.split("\n")`. `null` means drawn but not in page gold. Since `s10c-gold-complete-v1` no template emits `null`; it remains valid for decorative text a future template might draw. Non-decreasing over the non-null lines. |
| `logical_join` | How this segment continues its logical line: `"space"` (wrapped body text, joined with one space) or `"cell"` (ledger cell, joined with `" \| "`). `null` on the first segment of a logical line and on every line with `logical_line_index: null`. |
| `occluded` | `true` when a stamp ring, an overlay stroke (ledger tick or correction, marginal stroke), or an overlay text box intersects this line's text box. |
| `region` | `title`, `body`, `footer`, `identifier_area`, `table_cells`, `stamp_area`, `signature_area`, or `margin` (the `template_catalog.v2` page-region vocabulary). |
| `region_index` | `S11a`: index into the page's `regions` of the one region holding this line. Present exactly when the page has `regions`. |
| `text` | NFC-normalized, logical-order Hebrew, exactly as drawn. |
| `polygon`, `baseline` | See Coordinates. |

## Coordinates

- Integer pixels in the final degraded JPEG (`width` x `height`), origin
  top-left, `x` right, `y` down.
- Geometry is measured before degradation and mapped through every geometric
  degradation step. Today that is only the page rotation
  (`Image.rotate(angle, expand=False)` about the canvas centre); blur, grain,
  contrast, and brightness keep pixel positions.
- `polygon` is the rotated text bounding box padded by 4 px, as four points
  clockwise from the top-left corner.
- `baseline` is the rotated typographic baseline as two points ordered
  **left-to-right in pixel x**, regardless of the RTL reading direction. Kraken
  derives line orientation from baseline direction, so a right-to-left baseline
  would flip the extracted line image.
- Points are clamped into the page. No line in the seed-101 evidence batch
  needed clamping.

## Regions (S11a)

Each page lists its laid-out text regions in `regions`, so a segmenter (for
example `ketos segtrain`) can learn region types and region reading order next
to line geometry.

| Field | Meaning |
| --- | --- |
| `region_index` | `0..n-1` in reading order: regions sorted by their first `line_index`. |
| `type` | The region name its lines carry in `region`. |
| `polygon` | See Region Polygons. Four points clockwise from the top-left corner, integer final-page pixels. |
| `reading_order_index` | Position of the region in `logical_order` reading order, `0..k-1`. `null` only for a region whose lines all have `logical_line_index: null`; no current template has one, so today it equals `region_index`. |
| `line_indices` | Strictly increasing `line_index` values of the region's lines. |

What a region is:

- Lines of one region type form one region, except where the generator lays
  out separate blocks of one type. Today that is only the three printed-letter
  signature blocks, which are three `signature_area` regions in reading order
  right to left.
- Regions per render family, in `region_index` order:

  | Family | Regions |
  | --- | --- |
  | `printed_letter` | `title`, `body`, `stamp_area`, 3 × `signature_area`, `footer` |
  | `handwritten_note` | `title`, `body`, `margin`, `footer` |
  | `archive_card` | `title`, `identifier_area` (card id and date), `body`, `table_cells` (the four field labels), `stamp_area`, `footer` |
  | `ledger` | `title`, `identifier_area` (ledger id and date), `table_cells` (header row and every row cell), `footer` (footer text and page number) |

- Reading the regions in `reading_order_index` order, and each region's
  `line_indices` in order, visits every line in `line_index` order. Each
  region therefore covers a contiguous run of `logical_order` lines, and the
  `logical_order` rebuild works region by region.

### Region Polygons

A region polygon is the pre-rotation axis-aligned box around:

- the text bounding boxes of its lines;
- the region furniture the generator draws for it, where there is any. That is
  the stamp ring (printed letters, archive cards), the ledger table frame, each
  signature rule, and the marginal note's underline stroke;

padded by 8 px and mapped through the page rotation like line polygons, then
clamped into the page. Line polygons pad by 4 px, so every line polygon lies at
least 4 px inside its region polygon before rounding. `validate` checks
containment with 1 px tolerance.

Why this choice:

- Only the stamp ring, ledger frame, and signature rules are drawn boxes. The
  body, title, identifier, label, and footer areas have no drawn outline: the
  layout fixes their right anchor and wrap width but not a box. A "layout
  column" box would be a guess, so those regions use their lines' extent.
- The archive card's ruled columns are not used as region boxes: its stamp ring
  crosses the column rule and its footer sits inside the body column.
- The handwritten note's two scribble arcs under the margin note are overlay
  marks, not text, and are not part of the margin region.

Overlap: regions overlap only where the page itself overlaps. On printed
letters the stamp region lies over the left end of the body region, as the
stamp ring does on the page. On the seed-17 seven-template batch and the
seed-101 evidence batch, no two other regions' polygons intersect.

## Rebuilding `logical_order`

No heuristics are needed. In `line_index` order, skip lines with
`logical_line_index: null`; a line with `logical_join: null` starts its logical
line, and every later line appends its `text` after the separator its
`logical_join` names (`"space"` → `" "`, `"cell"` → `" | "`). Joining the rebuilt
lines in `logical_line_index` order with `"\n"` reproduces `logical_order`
exactly, for every governed template. `hocrsyngen validate` enforces this.

Where it applies:

- A long body source line wrapped across physical lines: the first segment has
  `logical_join: null`, the rest `"space"`.
- A ledger row, drawn as five cells and recorded in `logical_order` as
  `number | date | amount | details | balance` (left-to-right column order):
  the first cell `null`, the rest `"cell"`.
- When nothing wraps and there are no ledger rows (every page of the seed-101
  evidence batch), the non-null lines' `text` joined with `"\n"` is
  `logical_order` verbatim.

The wrap rule assumes source lines have no repeated internal whitespace, which
holds for corpora read through the generator's line loader (lines are
stripped, and wrapping splits on whitespace).

## Body Capacity And Truncation

The sidecar holds only segments that were actually drawn, each with its own
text. Segments that are never drawn appear nowhere in it, and the page's
`truncated_segments` field counts them. Every template builds `logical_order`
from the drawn segments, so text past a cap is missing from the page and from
gold alike, and the round trip always holds.

| Template family | Body cap (wrapped lines) | Why |
| --- | --- | --- |
| `printed_letter` | 13–23, computed: 16 with standard style and condition | Worst-case body top plus y jitter and font height must stay 8 px above the signature rules (y = 1344). |
| `handwritten_note` | 13–23, computed: 16 with standard style and condition | Same rule against the highest possible footer (y = 1480). |
| `archive_card` | 7 | Fixed cap, kept as is. The card body could fit about 10 lines, but raising the cap would change pages of existing archive batches. |
| `ledger` | 10 | Fixed cap, kept as is. Ten 86 px rows fill the table, so this is its geometric capacity. |

The computed cap is lowest with `style_open_drift_v1` (82/94 px lines) and
highest with `style_compact_steady_v1` plus `condition_dense_spacing_v1`. For
printed and handwritten bodies, a source line cut by the cap keeps its drawn
segments, rejoined with a space, as its `logical_order` line.

- The packaged and `S10b` corpora never reach the printed or handwritten cap:
  4 or 3 source lines of at most about 60 characters wrap to 8 lines or fewer.
- The ledger cap binds even with the packaged corpus, at about 4 truncated
  segments per page. A ledger detail cell is 282 px wide, so each source line
  wraps into about 3 rows.
- A body word wider than the printed or handwritten body (968 px) raises
  `ValueError` instead of being drawn off the page. Archive and ledger cells
  sit far enough from the left edge that no realistic word leaves the page.

## Drawn Text And Reading Order

Since `s10c-gold-complete-v1`, every drawn text element is in `logical_order`
and carries a `logical_line_index`. That includes the printed-letter stamp
word, the three `אישור` captions, and the handwritten marginal note. The fixed
reading order is documented in
[generation_manifest_v1.md](generation_manifest_v1.md#reading-order-of-logical_order).

`d4a-realism-v2` sidecars (S10a) emitted these lines with
`logical_line_index: null`, because that version left them out of
`logical_order`.

## Occlusion

`occluded` is a cheap geometric test on pre-rotation text boxes, not pixel
analysis. A line is occluded when:

- a recorded overlay mark crosses its text box: stamp rings (printed letters
  and archive cards), ledger ticks and the correction stroke, and marginal
  strokes and arcs. A mark that decorates a line, such as a marginal note's
  underline, does not occlude that line;
- or its text box overlaps another line's text box and at least one of the two
  is overlay text: region `stamp_area`, `margin`, or `signature_area` (for
  example the stamp word under a body line). Main-flow lines never occlude
  each other.

Occlusion is realistic and stays in the data. Body text under a stamp remains
in gold, and evaluators can split scores on the flag.

On seed 101 the flag marks 90 lines, all on printed-family pages: 62 body or
title lines and 28 stamp words.

- Of the 62 main-flow lines, 59 are crossed by the stamp ring's centreline and
  3 lie within the ring's 2 px stroke half-width.
- 28 of the 62 also overlap the stamp word's text box; those stamp words are
  the 28 occluded `stamp_area` lines.
- An earlier ring-sampling estimate of 55 counted only the inward-drawn
  stroke.

No handwritten-family line is marked.

## Validation

`hocrsyngen validate` checks `line_annotations.json` whenever it is present:

- JSON schema;
- manifest hash;
- page ids, hashes, and dimensions in manifest order;
- contiguous `line_index`;
- NFC text with no surrounding whitespace and no control or bidi control
  characters;
- in-page coordinates, and baselines whose x never decreases from first to
  last point;
- `logical_join` / `logical_line_index` consistency;
- the `logical_order` rebuild above;
- regions (S11a), when present. Either every page has `regions` and every line
  a `region_index`, or none do. `region_index` must be contiguous. Every line
  must be in exactly one region, of the same type, and its back-reference must
  match. Each region polygon must contain its line polygons (1 px tolerance).
  `reading_order_index` must follow the rule above, and the regions must walk
  the lines in `line_index` order.

## Schema Id And Compatibility

`S11a` keeps the schema id `hocrsyngen_line_annotations.v1`. The change is
purely additive: `regions` on pages and `region_index` on lines. Every S10
field keeps its meaning and value, and removing the two new fields from an
S11a sidecar gives exactly the sidecar the previous code wrote for the same
batch.

- The JSON schema lists both fields as optional, so `validate` still accepts
  sidecars written before `S11a`. The writer always emits them.
- The schema is closed (`additionalProperties: false`), so a hocrsyngen build
  from before `S11a` rejects an S11a sidecar in `validate`. Validate a batch
  with the hocrsyngen version that wrote it, or a newer one.
- `heocr-engine` `prepare-kraken-data` reads only the fields it needs and
  ignores the new ones. Its main branch (`51dc868`) accepts S11a sidecars
  unchanged.
- `GENERATOR_VERSION` is not bumped. Page bytes, `logical_order`, and the
  manifest are unchanged, which matches `S10a`, which also added the sidecar
  without a version bump.

## External Text Corpora

`--text-corpus PATH` (on `generate` and `evidence-run`) samples body lines from
a UTF-8 file with one line per row instead of the packaged corpus.

- `provenance.source_corpus` keeps `packaged:synthetic/texts/<name>` for files
  in the packaged texts directory, and records `external:sha256:<hex>` for any
  other file, so manifests never carry local paths. Manifest v1 and its schema
  are unchanged.
- The generation report and the candidate evidence-run report gain a
  `text_corpus` object (`source_corpus`, `sha256`), and `RUN_NOTES.md` gains a
  `text_corpus` line. These keys appear only when `--text-corpus` is used.
- `line_annotations_path` likewise appears in both reports only with
  `--emit-line-annotations`.

## Determinism

Recording geometry never draws from the generator's random stream:

- `--emit-line-annotations` never changes the manifest or any page asset. The
  sidecar is the only added file.
- Under `s10c-gold-complete-v1`, the seed-101, 80-sample, four-template
  evidence batch has manifest sha256
  `c4b4ca4ed5b92080c0a4d13c4fa2da505080da11b37203ecb0d4fa1bcb164ec3`.
  Its pages are byte-identical to the `d4a-realism-v2` batch (manifest
  `9b6e54f7…`).
- Recording regions (`S11a`) draws nothing and never uses the random stream.
  The seed-101 evidence batch and a seed-17, 28-sample, seven-template batch
  are byte-identical to `bbcaf0e` (before `S11a`) except for
  `line_annotations.json`. The manifest sha256 is still `c4b4ca4e…`.

## Gold Finding (seed 101, `d4a-realism-v2`; resolved in `S10c`)

This section records what `S10a` measured on `d4a-realism-v2` output. `S10c`
put the missing text into `logical_order`. The before/after table is in the
[roadmap](roadmap.md) `S10c` entry.

A Tesseract spot check reported that "the ends of some lines are cut off". The
seed-101 batch has 80 pages, 20 per template, and 440 logical lines. Measured
with this sidecar:

| Template | Pages | Scored lines (chars) | Drawn, unscored lines (chars) | Pages with unscored text | Occluded scored lines (pages) |
| --- | --- | --- | --- | --- | --- |
| `printed_letter` | 20 | 120 (3,626) | 80 (380) | 20 | 31 (20) |
| `printed_letter_heavy_scan` | 20 | 120 (3,685) | 80 (380) | 20 | 31 (20) |
| `handwritten_note` | 20 | 100 (2,830) | 20 (85) | 20 | 0 (0) |
| `handwritten_note_heavy_wear` | 20 | 100 (2,798) | 20 (86) | 20 | 0 (0) |
| **Total** | 80 | 440 (12,939) | 200 (931) | 80 | 62 (40) |

- **No clipping, and no truncation on these four templates.** 0 of 440 lines
  leave the page, no body line wraps, and every page reports
  `truncated_segments: 0`. Every page's drawn lines rebuild its
  `logical_order` exactly. This batch has no `archive_card` or `ledger` pages,
  whose capped bodies do truncate (see Body Capacity And Truncation).
- **What "cut off" was.** On printed letters the stamp ring lies across the
  left end of the body band, which is where RTL lines end. The text is drawn on
  top and stays in gold, but engines misread it. These lines now carry
  `occluded: true`.
- **Gold defect: drawn but unscored text.** 931 drawn characters on 80 of 80
  pages are not in `logical_order`. That is about 7% of the 12,939 scored
  characters: 10.4% on printed letters and 3.0% on handwritten notes. The
  items:
  - `אישור` 120 times;
  - stamp `נבדק` 40 times;
  - marginal notes 40 times (`נבדק` 15, `עותק` 14, `להמשך` 11).

  Page-level CER/WER charges an engine that reads them correctly with
  insertions.

`S10a` deliberately left `logical_order` and the manifest unchanged. `S10c`
fixed the gold under the new generator version `s10c-gold-complete-v1`.

## Ledger cell fit (S11b)

The ledger detail column is narrower to leave room for balance numbers. A corpus
containing a token wider than that column fails generation with a clear error;
tokens are not silently split or clipped. Wrapped segments beyond the ten-row
capacity are still counted in `truncated_segments`, and gold records only drawn
segments. Existing batches do not inherit this fix; regenerate and validate them.
