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

```json
{
  "schema": "hocrsyngen_line_annotations.v1",
  "generation_manifest_sha256": "<sha256 of generation_manifest.json bytes>",
  "coordinate_space": "final_page_pixels",
  "pages": [
    {
      "sample_id": "hocrsyngen-s00000101-000000",
      "page_id": "hocrsyngen-s00000101-000000-page-0001",
      "page_sha256": "<same as the manifest page sha256>",
      "width": 1200,
      "height": 1600,
      "lines": [
        {
          "line_index": 0,
          "logical_line_index": 0,
          "region": "title",
          "text": "מכתב מנהלי",
          "polygon": [[775, 123], [1082, 122], [1082, 172], [775, 173]],
          "baseline": [[779, 167], [1078, 166]]
        }
      ]
    }
  ]
}
```

- `pages` follow manifest order (samples, then pages).
- `line_index` is `0..n-1` in drawing order, which is also logical order.
- `logical_line_index` is the index into
  `sample.text.logical_order.split("\n")` that the line belongs to. It is
  non-decreasing across `line_index`.
- `region` is one of `title`, `body`, `footer`, `identifier_area`,
  `table_cells`, `stamp_area` (the `template_catalog.v2` page-region
  vocabulary).
- `text` is NFC-normalized, logical-order Hebrew, exactly as drawn.

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

## Relation To `logical_order`

Group lines by `logical_line_index` (in `line_index` order) and join each group:

- with `" | "` when every line in the group has region `table_cells` (a ledger
  row is drawn as five cells and recorded in `logical_order` as
  `number | date | amount | details | balance`, in left-to-right column order);
- otherwise with a single space (a long body source line wrapped onto several
  physical lines).

Every `logical_order` line is produced exactly once by this rule, so the result
joined with `"\n"` reproduces `logical_order`. `hocrsyngen validate` enforces it.
When no line wraps and there are no ledger rows, which holds for every page of
the seed-101 evidence batch, the lines' `text` joined with `"\n"` is
`logical_order` verbatim. The wrap rule assumes source lines have no repeated
internal whitespace, which holds for corpora read by the generator's line
loader (lines are stripped, and wrapping splits on whitespace).

Text drawn on the page but absent from `logical_order` is **not** annotated:
the printed-letter stamp word and the three `אישור` signature captions, and the
handwritten-note marginal note (`נבדק`, `להמשך`, or `עותק`). See the gold
finding below.

## Validation

`hocrsyngen validate` checks `line_annotations.json` whenever it is present:
JSON schema, manifest hash, page ids/hashes/dimensions in manifest order,
contiguous `line_index`, NFC text, in-page coordinates, and the
`logical_order` reconstruction rule above.

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

Recording geometry never draws from the generator's random stream. With both
flags off, output is byte-identical to earlier releases, and with
`--emit-line-annotations` the manifest and every page asset are byte-identical
to a run without it; the sidecar is the only added file. The seed-101,
80-sample, four-template evidence batch reproduces manifest sha256
`9b6e54f798fc6d131431e114716b2db12018c3bc4726369b4c749a7237182d20` either way.

## Gold Finding: Occlusion And Unlisted Text, Not Clipping

A Tesseract spot check reported that "the ends of some lines are cut off". On
the seed-101 batch (80 pages: 20 each of `printed_letter`,
`handwritten_note`, `printed_letter_heavy_scan`,
`handwritten_note_heavy_wear`, 440 logical lines):

- **No clipping or truncation.** 0 of 440 lines leave the page, no body line
  wraps, and every page's drawn lines reproduce its `logical_order` exactly.
- **Stamp occlusion at line ends.** On the printed-letter family the stamp
  ellipse (drawn first, at the left of the body band) runs through 55 of 240
  printed lines on 39 of 40 printed pages, always in the leftmost quarter of the
  line, which is the end of an RTL line. The text is fully drawn on top, so the
  line labels stay correct, but engines read those words poorly. The
  handwritten family has no such overlap.
- **Text drawn but missing from `logical_order`.** All 80 pages carry such
  text, 200 items in total: `אישור` 120 times (3 per printed page), the stamp
  word `נבדק` 40 times, and marginal notes on handwritten pages (`נבדק` 15,
  `עותק` 14, `להמשך` 11). Page-level CER/WER therefore counts correct reads of
  this text as insertions. This is a page-level answer-key defect.

Fixing either issue changes rendered pages or `logical_order`, so it needs a
`GENERATOR_VERSION` bump and fixture review. It is tracked as `S10c` in the
[roadmap](roadmap.md), not done in `S10a`, so that `S10a` stays byte-identical.
