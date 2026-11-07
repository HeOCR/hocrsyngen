# Real-Glyph Book Page Composition (S16b)

`S16b` composes scanned printed Hebrew book pages from glyph images cut out of
real public-domain scans. The input is a `printed_glyph_bank.v1` directory
([printed_glyph_bank_v1.md](printed_glyph_bank_v1.md), `S16a`). The output is
a normal candidate batch with exact gold for every line.

Why: the recognizer scores CER 0.020 on font-rendered synthetic pages and
0.898 on 38 real scanned printed pages (Tesseract scores 0.237 on those
pages). Font glyphs look nothing like old letterpress, so this composer puts
real letterpress glyphs in the training distribution.

```bash
hocrsyngen compose-glyph-pages --glyph-bank BANK --count 200 --seed 16 \
  --output out/glyph-batch [--text-corpus FILE] [--min-glyph-score 0.6] \
  [--style-id ws-1711486-f1 ...] [--provenance-glyph-ids]
hocrsyngen validate out/glyph-batch
```

Code: `src/hocrsyngen/glyph_bank.py` (bank loader and validator) and
`src/hocrsyngen/glyph_compose.py` (the composer). The composer uses Pillow only,
reads files only, and imports nothing from `hocrgen`.

## Outputs

| File | Content |
| --- | --- |
| `generation_manifest.json` | Manifest v1. Template `printed_book_glyph_page`, recipe `printed_book_glyph_page_v1`, `font_id` `real_glyph_bank`, `degradation_preset` `book_scan_glyph_v1`, `generator_version` `s16b-glyph-compose-v1`. Pages vary in size, so each page records its own `width` and `height`. |
| `assets/<sample_id>/page_0001.jpg` | RGB JPEG page, quality 70–90. |
| `line_annotations.json` | `hocrsyngen_line_annotations.v1` with regions, unchanged schema. The `heocr-engine` loader reads it as it is. |
| `glyph_provenance.json` | `hocrsyngen_glyph_provenance.v1` ([schema](../src/hocrsyngen/schemas/glyph_provenance.schema.json)). It is bound to the manifest by hash. It records the bank id and `glyphs.jsonl` hash and the rights fields of every style used (licence, attribution, source, work). Each page gets its style, glyph counts per source page, the number of synthesised double marks, and the sampled degradation parameters. `--provenance-glyph-ids` adds each page's sorted unique glyph ids. |

The JSON summary on stdout (`glyph_composition_report.v1`) gives pages, lines,
characters and glyphs. It gives corpus lines skipped for style-independent
reasons, and for each style: weight, band sizes, renderable corpus lines,
lines skipped for missing glyphs with the top missing characters, and pages,
lines and characters composed. It also lists styles excluded for having too
little renderable text, and counts of words too wide for a column and of
glyphs rejected for broken masks.

The template is governed: `validate` checks its recipe, font and preset like
any other template. It also requires `generator_version`
`s16b-glyph-compose-v1` and a valid `glyph_provenance.json` whenever the
manifest has a composed sample. `templates` lists the template only with
`--include-composed`, because `generate` cannot render it. The default
`templates` output and every font-rendered page are unchanged.

## Page Recipe

All randomness comes from one `random.Random` per page, seeded with
`hocrsyngen-glyph-page:<seed>:<index>`. A page is therefore the same whatever
the batch count.

1. **Style.** One style (one book's typeface) per page. Styles are drawn with
   weights equal to their usable body-band glyph count, capped at 3× the
   median, so one large book cannot dominate. A style needs at least 100
   renderable corpus lines; others are excluded and reported.
2. **Size bands.** One book mixes body type, smaller commentary and larger
   headings. A line only draws glyphs whose `x_height_px` is within ±12% of
   the band target. Each glyph is scaled by target / `x_height_px`, bounded to
   ±8%, then by the page scale with ±1.5% jitter. The body band target is the
   style's `metrics.x_height_px`. A heading band exists when at least 60
   glyphs are 1.3× larger or more; it is used for running titles and section
   headings. Corpus coverage is computed inside the band that draws the line.
3. **Glyph screening, per band.** A glyph whose ink width or height (in
   x-heights) is outside 0.6–1.6× its character's median is dropped as a
   mislabelled fragment. So is a glyph whose mask misses part of its own ink.
   "Dark" is measured against the crop itself: a pixel is dark when it is
   below background − 0.5 × (background − ink). Background is the crop's
   92nd percentile and ink is the 10th percentile under the mask. The glyph is
   rejected when more than 6% of the dark pixels inside its ink box lie
   outside the mask dilated by 1 px. That catches a lost stroke, such as the
   detached leg of ה (it would draw ד) or the foot of ג, without firing on
   light ink or grey antialiased edges. A crop whose ink is less than 16
   levels darker than its paper is also rejected. Every band glyph image is
   read once at planning time for this check.
   Stroke-weight banding then removes bold (or hairline) variants that leak
   from headings or emphasis into the same face and size. A glyph's weight is
   2 × ink mass under its mask ÷ mask boundary length, in x-heights, where ink
   mass is the normalised darkness, so thicker or blacker strokes both read
   heavier. The band norm is the median weight of the band's Hebrew letters.
   Each character gets a factor, its own median over the norm, clamped to
   0.85–1.15: a letter may be slightly heavier by design, but a letter that is
   bold everywhere cannot set its own norm. A glyph is kept when its weight
   over norm × factor is within 0.85–1.15 (on the full bank, visibly bold
   variants sit at about 1.12–1.2). Each page then draws a weight
   target of 0.95–1.05 and prefers variants near it (Gaussian preference,
   spread 0.08), so a page reads as one lighter or heavier printing. The
   summary reports `body_band_weight_dropped` and
   `heading_band_weight_dropped` per style.
4. **Page geometry.** The page is the style's page size times the page scale
   (0.9–1.15, a DPI-like change) ±2%. Column width is the style's
   `text_block_width_px` (scaled, ±5%). Two columns are used when two fit into
   80–88% of the page width; real probe banks report column widths of about
   550 px on 1920 px pages. Margins are centred with a small recto/verso
   gutter shift. Line pitch is `max(line_pitch_px, 1.6 × x_height_px)`
   (scaled, −2%…+4%), so ascenders and descenders of adjacent lines do not
   collide.
5. **Furniture.** A running header (70% of pages): the page number at the
   outer corner, a centred short title, or both. They are two lines on one
   baseline in one `title` region, in right-to-left reading order. Pages
   without a header page number put one in a centred `footer` 60% of the
   time. Page numbers are digits when the band has them (70%) or Hebrew
   numerals (gematria). A centred section heading opens the body on 15% of
   pages that start a fresh paragraph and have a heading band.
6. **Text.** Paragraphs join 3–10 corpus lines, drawn without replacement
   within a page. 60% of pages open mid-paragraph with no indent. Lines are
   filled greedily. Full lines are justified by stretching word gaps (±15%
   variation, exact total). A line that would need more than
   max(4 × median word gap, 2.5 × x-height) per gap stays ragged. A
   paragraph's last line is ragged and right aligned. First lines have an RTL
   indent (1.4–3 x-heights per page) on the right. Column 1 (right) fills
   before column 2, and a paragraph carries over between columns.
7. **Glyph placement.** Right to left. Each glyph's ink box follows the
   previous one at a sampled letter gap: the style's p10/median/p90 as a
   triangular distribution, ±0.4 px. Letters may touch or overlap by up to a
   quarter of the narrower ink width. Word gaps come from the style's
   word-gap distribution. Each occurrence draws a random variant and never
   repeats the previous glyph for two identical adjacent letters. The
   glyph's `baseline_y` sits on the line baseline with ±1 px vertical jitter.
8. **Bidi.** Words keep logical order; the composer applies a reduced Unicode
   Bidirectional Algorithm for an RTL paragraph (W1–W7, N1–N2). Number runs
   such as `1948`, `13:40` or `50%` are placed left to right inside the RTL
   line. Lines with a Latin run across a space, or a mirrored character
   inside an LTR run, are skipped (`unsupported_bidi`). Brackets in RTL
   context are drawn with the glyph labelled with the logical character,
   which a harvest from RTL text shows in its mirrored shape.
9. **Paper.** A smooth base tone (`paper_gray` ±2% per page) carries fine
   grain from the patches' high-pass part only (patch − GaussianBlur(patch,
   8)). The high-pass of every patch has the same mean, is rescaled to a
   standard deviation of 3 grey levels and clipped to ±10, so randomly flipped
   and offset tiles meet without a visible edge, even with contrast stretched.
   At load time a patch is rejected when its low-pass part has a standard
   deviation above 4 or a range above 24 (shadows, gradients, stains). It is
   also rejected for sharp marks (more than 0.2% of pixels beyond ±20) or for
   a row or column whose mean is off by more than 2 levels (page edges,
   rules, fold lines, scanner streaks). A style with no usable patch gets
   synthesised grain. A smooth illumination field multiplies the paper: a
   gentle gradient plus 2–5 large Gaussian blobs, 1–5% deep. 20% of pages get
   a soft binding shadow on one edge. Styles with `paper_gray` ≥ 250 are
   renders of bitonal scans: their paper stays pure white, with no grain,
   illumination, tint, show-through or sensor noise, and contrast and
   brightness never dim it.
10. **Compositing.** Each glyph crop is normalised so
   its own paper is white (divided by its 92nd percentile). It is turned into
   darkness and applied only inside its mask (dilated 1 px and feathered), so
   a neighbour's stray ink in the crop is never drawn. Overlapping darkness
   combines by maximum. The page is paper × (1 − darkness). Ink keeps the
   crop's own tone times a page factor (0.86–1.06) and a ±4% glyph factor.
11. **Degradation.** Show-through (45%, not on bitonal styles): the page's
    own ink layer, mirrored, shifted, blurred and at 4–10% opacity. Ink bleed
    (15%): a blend with a 3 px max filter. Speckles (35%): small dots kept
    12 px away from every line. Warm paper tint (55%, not on bitonal styles).
    Then rotation of ±0.7°, Gaussian blur 0.15–0.6, faint half-resolution
    sensor noise, contrast and brightness, and JPEG quality 70–90. Rotation is
    the only geometric step.

## Gold Guarantees

- Each physical line is one `logical_order` line (`logical_join: null`).
  `logical_order` is the lines in reading order joined by `\n`: header items
  right to left, heading, column 1, column 2, footer. Line text is NFC, with
  single spaces between words.
- Every placed glyph is recorded with the index of the gold character it
  renders. `_check_line_gold` fails composition unless each non-space
  character of the line text is drawn by exactly one glyph, or by exactly two
  for a synthesised double mark. No glyph may sit on a space or outside the
  text. A glyph's bank `char` must equal its gold character. The only allowed
  substitution is ״ or `"` built from two adjacent ׳ or `'` glyphs, and only
  when the band has no glyph for the double mark itself.
- Nothing else is drawn as text. Show-through is a faint mirrored copy of the
  page's own ink, and speckles stay at least 12 px from every line's ink box.
- The line polygon is the union of the line's visible glyph ink boxes plus
  the baseline, padded by 4 px and mapped through the page rotation with the
  generator's `_rotated_point`. The baseline runs left to right at the line's
  baseline y. Ink boxes come from the scaled, feathered mask (level ≥ 24), so
  they cover what was composited. Regions are `title` (running header and
  heading, one region each), `body` (one region per column) and `footer`.
- Corpus lines with niqqud or other combining marks, control or format
  characters, or unsupported bidi are skipped before any style is chosen. So
  are lines with any character missing from the style's body band. The report
  counts both.

## Limitations

- No niqqud, cantillation, Rashi-script-specific handling or ligatures in
  v1. A style that mixes square and Rashi faces at similar x-heights still
  mixes them in one line; banks must split faces into styles (as the probe
  does for `ws-1711486-f0`/`-f1`).
- Glyph labels are trusted. The screening above catches broken masks and
  size outliers, not a well-formed glyph with the wrong label.
- Layout is one or two columns of running text with header and footer.
  Footnotes, commentary blocks around a main text, tables, drop capitals and
  hyphenation are not modelled. Text that does not fit stays off the page and
  out of gold, so `truncated_segments` is always 0.
- Spacing comes from per-style distributions with no letter-pair kerning, so
  touching letter pairs are random rather than typeface-specific.
- Page bytes depend on Pillow's resampling and JPEG encoder. Determinism holds
  for one Pillow version, as for the font generator.
- The text corpus is the S13b typographic train corpus by default. Its
  typographic dashes and quotes are rare in old books, so most of its lines
  are skipped for real banks (about 90% on the probe bank). Skipping is safe:
  gold never holds a character the bank cannot draw. A style is only
  excluded when fewer than 100 corpus lines remain.

## Choosing A Text Corpus

Many banks have no digits, typographic dashes, curly quotes, ellipses or ₪.
Every corpus line using one of them is skipped for that style. The summary's
`styles[].skipped_missing_glyph` and `styles[].top_missing_chars` show which
characters cost the most lines for each style. To give such styles more and
more varied text, pass a corpus that matches what old books print:

- `--text-corpus src/hocrsyngen/data/synthetic/texts/hebrew_lines_train_v1.txt`
  (S10b) has plain Hebrew lines with little typographic punctuation.
- A pinned external public-domain corpus (S15 Project Ben-Yehuda text) fits
  old book pages best. It is recorded as `external:sha256:<hex>`, as for
  `generate`.
- Lines with niqqud are skipped in v1 whatever the corpus.
