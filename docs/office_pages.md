# Office-print pages (`office-pages`)

`hocrsyngen office-pages --texts pool.jsonl --output out/ --seed N --pages K [--split train|val]` generates tender-
and notice-like page images with exact line and cell boxes, rectified line crops and logical labels. It implements
§3 (page families), §4 (numbers and labels) and §5.2 (degradation) of the office-print plan,
[experiments/office_print_v0/PLAN.md](../experiments/office_print_v0/PLAN.md). Code: `src/hocrsyngen/office_pages.py`.

## Input

A JSONL text pool, one `{"id", "unit_id", "text"}` per line, in logical order. A page draws consecutive lines of one
unit. The generator adds the structure, numbers, layout, image-only marks and degradation. It does not choose or
decontaminate the text: the caller passes a pool that is already clean (PLAN §4: clean3 minus eval's reservations,
with the office_val units removed for `train`; `holdout_units()` gives that split by a hash of the unit id).

## Page families (shares per PLAN §3)

| Family | What a page holds | Share |
|---|---|---|
| `running_text` | paragraphs, justified or ragged, one or two columns; most paragraphs open with a section label; dates, amounts, %, counts and in-sentence section references inserted in the split-triggering contexts (`ב-1.1.2026`, `(12%)`, `₪ 1,234`, `סך של … ש"ח`) | 25% |
| `numbered` | sections and sub-sections with 2-4 level labels leading the line (`3.1`, `12.4.1`, `2.2.4.`), `(א)` / `(1)` / `א.` sub-levels, hanging indents, tight or tab gaps, definitions, a schedule (תוספת) block | 30% |
| `tables` | a numbered heading, then one or two tables: grid, header-only, row lines or unruled; bill-of-quantity item numbers (`3.2.1`), amounts with ₪ before, after or in the header, %, dates, quantities, units, merged header cells, totals rows; notes under the table as numbered items | 35% |
| `front_matter` | a generated emblem, a generic authority (`משרד הדוגמה`, `הרשות לבדיקות`, …), phone and fax, date and reference lines, `לכבוד`, `הנדון: מכרז מס' 12/2026 – …`, body, closing, a generated signature, sometimes a generated stamp, a name from a generated pool and a title | 10% |

Every page also gets a header (most pages), a page counter (`עמוד 3 מתוך 12`, `- 3 -`, `3/12`, `3`) and sometimes a
footnote under a short rule. Emblems, signatures and stamps are generated shapes, never real ones, and are never
labelled. A line they overlap is masked out of the crops and counted (`masked_by_mark`).

## Numbers and labels

- Shape targets (share of generated numbers): section labels at line start 35%, dates 25%, short integers 15%,
  amounts 15%, percentages 10% (PLAN §4, 2026-11-18). In-sentence section references (`section_ref`), `(1)` sub-levels
  (`sub_num`) and phone numbers are counted apart. `summary.json` reports the realised mix. On a 200-page sample
  (seed 23): labels 32.5%, dates 21.6%, short integers 15.5%, amounts 18.4%, percentages 12.1%. 66% of text lines and
  65% of cells carry a number; 24% of text lines carry two or more (cells hold one by design).
- Every generated number is one token with the separators it shows. Its span in the label is recorded in
  `number_spans` as the part the evaluation's number pattern (`\d+(?:[.,/]\d+)*%?`) finds. The tests check that the
  pattern finds each span whole in the label, and that the drawn text has the same characters there.
- Labels are the drawn logical text with the signs stock heb lacks folded one-for-one, as `line_fold_v1` does: `״`→`"`,
  `׳`→`'`, `־`→`-`, `“ ” „`→`"`. The en and em dash are written `-` (PLAN §4). The page draws the real signs.

## Fonts

All governed faces (render-lines manifest). The office faces (Arimo, Cousine, Open Sans) are drawn three times as often
as the others. Tinos is held out: `train` never uses it, and `val` uses only it. The `payment_schedule` table schema is
held out of `train` too. A line with a character its face cannot draw is not drawn (`refused_missing_chars`).

## Degradation (page level, PLAN §5.2)

| Model | Geometry | Photometric | Share |
|---|---|---|---|
| `office_scan` | 200-400 dpi, skew up to ±3° | paper and ink levels, sometimes faint bleed-through, blur, noise, grey or Otsu or fixed-threshold binarisation, JPEG 70-92 | 50% |
| `photocopy` | 200-300 dpi, skew up to ±2° | 1-2 generations of contrast gain, stroke thickening or thinning, toner speckle (25-200 specks per million pixels, halved after dots fell inside letters like a dagesh), edge shadow and banding; thin rules drop out in places; blur, JPEG 75-92 | 25% |
| `phone_photo` | 150-250 dpi, a keystone of up to 6°, skew up to ±3° (what the app's deskew leaves), background outside the page | uneven light, vignetting, defocus or motion blur, noise, JPEG 60-85 | 15% |
| `clean` | 150-300 dpi | none | 10% |

The geometry is one homography per page. Line and cell boxes are mapped through it to quads on the degraded page, and
each crop is cut from the degraded page by its quad (`QUAD` transform), so a skewed line comes out straight while
carrying what a real line crop carries: neighbour ascenders, rule remnants and noise. A cell's crop reaches toward its
cell rectangle by a random share, so some cell crops hold border remnants.

The S17a gates and the stock read-back gate run on the generated lists, not here (PLAN §5.2, §7 step 5).

## Output

- `pages/<page>.png` and `pages/<page>.json` (every line's quad, kind, label, drawn text, number spans, sources, cell
  position and rectangle; the regions; the degradation parameters and the homography)
- `lines/<line>.png` and `lines/<line>.gt.txt`
- `manifest.jsonl` (one record per crop), `pages.jsonl` (one per page), `summary.json` (the realised mix, the targets,
  the font-manifest sha256)

Every random choice derives from (seed, page id), so a page renders identically in any batch.
