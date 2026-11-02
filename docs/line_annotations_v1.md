# Line Annotations Sidecar v1

`S10a` adds an opt-in per-line geometry sidecar so generated pages can become
line-level recognizer training data (for example Kraken/ketos). It is written
next to `generation_manifest.json` and does not change manifest v1, its schema,
the packaged contract fixture, or any page asset.

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

The first three lines of seed-101 sample 0 (`printed_letter`):

```json
{
  "schema": "hocrsyngen_line_annotations.v1",
  "generation_manifest_sha256": "9b6e54f798fc6d131431e114716b2db12018c3bc4726369b4c749a7237182d20",
  "coordinate_space": "final_page_pixels",
  "pages": [
    {
      "sample_id": "hocrsyngen-s00000101-000000",
      "page_id": "hocrsyngen-s00000101-000000-page-0001",
      "page_sha256": "12d320d667074a881214bddb7ef42feb42298b5aa42007cbbf29b658051d756b",
      "width": 1200,
      "height": 1600,
      "lines": [
        {"line_index": 0, "logical_line_index": null, "logical_join": null, "occluded": true,
         "region": "stamp_area", "text": "נבדק",
         "polygon": [[337, 324], [398, 324], [398, 350], [337, 350]], "baseline": [[341, 342], [394, 342]]},
        {"line_index": 1, "logical_line_index": 0, "logical_join": null, "occluded": false,
         "region": "title", "text": "מכתב מנהלי",
         "polygon": [[775, 123], [1082, 122], [1082, 172], [775, 173]], "baseline": [[779, 167], [1078, 166]]},
        {"line_index": 2, "logical_line_index": 1, "logical_join": null, "occluded": true,
         "region": "body", "text": "בדיקת אותיות סופיות ךםןףץ נשמרה ברשימת הבקרה.",
         "polygon": [[218, 256], [1104, 252], [1104, 289], [218, 293]], "baseline": [[222, 283], [1100, 279]]}
      ]
    }
  ]
}
```

Page fields:

- `pages` follow manifest order (samples, then pages).
- `sample_id`, `page_id`, `page_sha256`, `width`, `height` match the manifest.

Line fields:

| Field | Meaning |
| --- | --- |
| `line_index` | `0..n-1` in drawing order. |
| `logical_line_index` | Index into `sample.text.logical_order.split("\n")`, or `null` for drawn text that `logical_order` does not contain (see below). Non-decreasing over the non-null lines. |
| `logical_join` | How this segment continues its logical line: `"space"` (wrapped body text, joined with one space) or `"cell"` (ledger cell, joined with `" \| "`). `null` on the first segment of a logical line and on every line with `logical_line_index: null`. |
| `occluded` | `true` when a stamp ring, an overlay stroke (ledger tick or correction, marginal stroke), or an overlay text box intersects this line's text box. |
| `region` | `title`, `body`, `footer`, `identifier_area`, `table_cells`, `stamp_area`, `signature_area`, or `margin` (the `template_catalog.v2` page-region vocabulary). |
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

## Drawn Text Outside `logical_order`

Some text is drawn on the page but is not part of `logical_order`. It is still
annotated, with its real `text` and `region`, `logical_line_index: null`, and
`logical_join: null`, so training can use the labels and the consumer decides:

| Template family | Text | Region |
| --- | --- | --- |
| `printed_letter`, `printed_letter_heavy_scan` | stamp word `נבדק` | `stamp_area` |
| `printed_letter`, `printed_letter_heavy_scan` | three `אישור` signature captions | `signature_area` |
| `handwritten_note`, `handwritten_note_heavy_wear` | marginal note `נבדק`, `להמשך`, or `עותק` | `margin` |

`archive_card` and `ledger` families draw no such text (the archive card's
`ארכיון` stamp is in `logical_order`).

## Occlusion

`occluded` is a cheap geometric test on pre-rotation text boxes, not pixel
analysis. A line is occluded when:

- a recorded overlay mark crosses its text box: stamp rings (printed letters
  and archive cards), ledger ticks and the correction stroke, and marginal
  strokes and arcs. A mark that decorates a line, such as a marginal note's
  underline, does not occlude that line;
- or its text box overlaps another line's text box and at least one of the two
  is outside `logical_order` (for example the stamp word under a body line).
  Lines in `logical_order` never occlude each other.

Occlusion is realistic and stays in the data. Body text under a stamp remains
in gold, and evaluators can split scores on the flag.

## Validation

`hocrsyngen validate` checks `line_annotations.json` whenever it is present:

- JSON schema;
- manifest hash;
- page ids, hashes, and dimensions in manifest order;
- contiguous `line_index`;
- NFC text;
- in-page coordinates;
- `logical_join` / `logical_line_index` consistency;
- the `logical_order` rebuild above.

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

- With both flags off, output is byte-identical to earlier releases.
- With `--emit-line-annotations`, the manifest and every page asset are
  byte-identical to a run without it; the sidecar is the only added file.
- The seed-101, 80-sample, four-template evidence batch reproduces manifest
  sha256 `9b6e54f798fc6d131431e114716b2db12018c3bc4726369b4c749a7237182d20`
  either way.

## Gold Finding (seed 101)

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

- **No clipping or truncation.** 0 of 440 lines leave the page, and no body
  line wraps. Every page's drawn lines rebuild its `logical_order` exactly.
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

`S10a` deliberately leaves `logical_order` and the manifest unchanged, so the
seed-101 benchmark stays stable. The fix is the separate follow-up slice
`S10c` in the [roadmap](roadmap.md).
