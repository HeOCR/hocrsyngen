<!-- Copied from the HeOCR task workspace (s17a-scanifier/r8c-aug/README.md) on 2026-11-12. step0.sh needs bash >= 4 (associative array). Paths under diagnostics/ are local to that workspace. -->
# R8c scan augmentation: design and step 0 (stopped)

**Request (heocr-lead, 2026-11-12):** every R8 model reads Brainin's IA scan worse than R7, 0.743 vs 0.635 CER under line_fold_v1. The errors are small-gap letters: ה/ח, ר/ד, כ/ב. The lead wants a degradation for a seeded share of real train lines, a small A/B, and share and strength as parameters.

## What sets the IA scan apart

Line medians from my `scripts/measure.py`, 400 seeded lines per set (`intermediates/measure_v0.json`), alongside eval's `scan_texture.json`:

| | Brainin IA | Brainin NLI | R8 train | Kevar | Yedi'ot |
|---|---|---|---|---|---|
| line height px | **50** | 63 | 72 | 60 | 71 |
| letter band px | **31** | 42.5 | 37 | 35 | 39.5 |
| background grey | **165** | 211 | 208 | 211 | 199 |
| contrast | 122 | 73 | 131 | 163 | 121 |
| speckle / 1k bg px | **0.049** | 0.039 | 0.027 | 0 | 0.023 |
| fine grain (eval) | **3.01** | 2.02 | 2.56 | 2.78 | 2.32 |
| edge sharpness | **0.68** | 0.46 | 0.53 | 0.57 | 0.45 |
| smallest inner gap / band | 0.129 | 0.06 | 0.091 | 0.088 | 0.083 |

**How I read it:**
- IA is **not blurrier**. It is the sharpest set, and its inner gaps are not relatively smaller. So "blur that closes gaps" doesn't match the measurements, and blur becomes an optional knob, off by default.
- What does set IA apart, as eval also found:
  - **small source size:** a 31 px letter band, so a ה/ח gap is only 1–2 px wide;
  - **sharpening** on that small image (jaggy edges, possible JPEG/JP2 artefacts);
  - **fine grain** and **speckle** on a dark grey ground.
- Level darkening by itself should be a no-op, because Tesseract normalises each line's levels.

## Augmentation `scan_aug.py` (pre-rendered copies)

lstmtraining has no on-the-fly image augmentation, so for each picked line I write a degraded PNG plus .lstmf. The truth text is unchanged. The ops run in this order, each with its own strength knob:
1. **downscale** to a target letter band of 24–34 px, sampled per line (area resampling). The line is not upscaled back: Tesseract rescales it the way it rescales IA.
2. **unsharp mask** (radius 1, amount 0.5–1.2) to imitate the derivative's sharpening.
3. **JPEG** at quality 55–85.
4. **levels:** background to N(165, 8) and ink to about 40. Cheap, and expected to be a no-op.
5. **grain:** additive Gaussian, σ 2.5–4 grey levels, plus faint low-frequency mottling.
6. **speckle:** dark 1–6 px blobs at 0.04–0.12 per 1k px.
7. **gap-closing** (optional, off by default): Gaussian σ 0.4–0.7 at the reduced size.

**Parameters:**
- `--share p`: fraction of real train lines replaced by their augmented copy (default 0.3).
- `--strength k` in [0, 1]: scales every op's range. k = 1 is IA-like; k = 0.5 sits halfway to train.
- `--ops`: subset of the ops.
- `--seed`.

Each line's draw is seeded by `hash(seed, line_id)`, so it's reproducible.

**Scope:** real train crops only. `--include-synthetic` is off by default. No new text and no outside images: grain and speckle are procedural, so licences don't change. Brainin IA, Brainin NLI, Silman, Kevar and Yedi'ot are never in the input (`check_train_overlap` gate).

## Step 0: a cheap diagnostic before any training (about 1 h CPU)

1. **Property match:** run `measure.py` on 400 augmented train lines. Their medians should land near IA's on band, sharpness, grain and speckle.
2. **Failure reproduction, with no training:** augment the R8b dev units (*Kevar*, *Yedi'ot*), as dev copies only, never trained on. Score R7 and R8b-main on them with each op alone and then all ops together.
   - The right property is the one that makes R8b-main lose to R7 the way it does on IA: ה→ח and ר→ד confusions go up.
   - This picks the ops and the strength before any training run. If no op reproduces the R7 > R8b flip, I report that instead of training on a guess.

## A/B plan (after step 0, power scheduler only)

- **Arms:** R8b-main's exact recipe (start checkpoint, lr, list order, one epoch), with and without the augmentation.
  - The augmented arm replaces share p of the real lines at the same positions of the same seeded order, so line counts are equal.
  - One augmented arm at the (p, k) that step 0 picks. A second arm (other p) only if the lead wants a sweep point.
- **Selection and rule:**
  - Brainin IA is the target dev.
  - *Kevar* and *Yedi'ot* each must not lose to the control (the "doesn't lose on either book" rule).
  - Checkpoints are picked on Kevar + Yedi'ot combined, as for R8b. Brainin IA is reported, not selected on.
- **Report:**
  - Brainin NLI and Silman (report-only);
  - confusion counts for ה/ח, ר/ד, כ/ב on Brainin IA;
  - a page-cluster bootstrap within each book.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource

## Step 0 result (2026-11-12): no op reproduces the flip, so no training

`scripts/step0_report.py` → `diagnostics/step0_report.json`. All CERs are line_fold_v1. The degraded sets are the Kevar and Yedi'ot held-out lines (4,600 each), at k = 1, so harsher than IA.

| Set | Kevar R7 → R8b | Yedi'ot R7 → R8b |
|---|---|---|
| clean | 0.848 → 0.757 | 1.336 → 1.019 |
| downscale | 0.947 → 0.779 | 1.451 → 1.090 |
| unsharp | 1.049 → 0.791 | 1.354 → 1.002 |
| down + sharp | 1.353 → 0.832 | 1.541 → 1.100 |
| all | 1.548 → 0.847 | 1.703 → 1.128 |
| all + blur | 0.886 → 0.765 | 1.814 → 1.255 |
| levels, speckle, grain, jpeg | each within ±0.03 of clean | each within ±0.04 of clean |

Brainin IA: R7 0.635, R8b 0.743. Upscaled to a 37 px band: R7 0.629, R8b 0.762.

**What this shows:**
- R8b wins on every degraded copy, and by *more* as degradation grows. Downscaling and sharpening hurt R7 more than R8b.
- Upscaling IA does not close the gap.
- So the IA loss is not size, sharpening, grain, speckle, JPEG or levels as such.
- R8b's 399 extra edits on IA are mostly one-way substitutions: ה→ח 195 vs R7's 26, ר→ד 62 vs 22, כ→ב 58 vs 26. These three are about 60% of the gap.
- On the sheet (`diagnostics/ia_he_het_sheet.png`, 14 of the 159 lines where R8b reads ה as ח and R7 doesn't), Brainin's face has a heavy left leg on ה that nearly touches the roof.
- Brainin's NLI scan is the same book in another scan, at a 42.5 px band. There R8b beats R7 (1.073 vs 1.355), and its ה→ח count is low (42).
- So the failure needs both: this face's narrow ה gap *and* IA's small, ink-heavy rendering of it. On Kevar and Yedi'ot, whose faces have wider gaps, the same degradation doesn't trigger it.
- A generic degradation is the wrong lever. A gap-specific one (closing the ה/ר/כ gaps by 1–2 px) would need character boxes, which synthetic lines have, and would get its own diagnostic first.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource

## Decision (heocr-lead, 2026-11-12): stop R8c augmentation

Brainin IA stays a known R8b weakness: one scan of one book, already on the R8b card. R8b wins on the NLI scan of the same book. No gap-closing augmentation, since tuning to one scan would be overfitting. A read-only check follows of what taught R8b to read a near-closed ה as ח: faces, ה/ח label disagreements per source, and the nearest line sets.

The degraded dev copies and their score_lines folders went to the Trash; `scan_aug.py` can rebuild them from hocrsyngen `3b55d4a`. The kept files are `diagnostics/step0_report.json`, `diagnostics/ia_he_het_sheet.png` and `diagnostics/step0_outputs/`, which holds each set's raw lstmeval outputs and codes.json.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource

## Option 3 (read-only): where R8b learned "near-closed ה → ח" (2026-11-12)

**Method:** `scripts/he_het_labels.py`, written to `diagnostics/he_het_labels.json`.
- Up to 300 seeded lines per training book: 23,373 lines over 95 books.
- Each line was read with stock `tessdata_best` heb, which never trained on HeOCR data.
- ה/ח substitutions against the label were counted per book.
- The s17a lines are the control, since their labels are exact by construction.

| Source | lines | ח read as ה, per 1k ח | ה read as ח, per 1k ה |
|---|---|---|---|
| s17a add-on (control) | 300 | 49 | 2.9 |
| bynli (v2) | 8,181 | 67 | 4.4 |
| bynli_lines_v3 | 4,500 | 75 | 5.0 |
| reshumotlines_v1 | 10,381 | 1.3 | 0 |

**Reading the rates:**
- The reader's own bias is about 49 per 1k ח, which is the control.
- Three books stand far above it:

  | Book | ח read as ה, per 1k ח | train lines |
  |---|---|---|
  | sipurim00nombuoft | 515 | 1,291 |
  | NLI 990020308000205171 | 465 | 6,076 |
  | mabeothayehudims00raff | 310 | 4,137 |

- Next come miyarketetevel 147, tserorperaim 146, hegyoneshpinozah 136 and agadothatanaim 105.
- **Not label noise.** On the spot sheet (`diagnostics/het_open_sheet.png`) the labels match the print. These faces draw ח with a small gap at the top left, so a correct ח looks like ה.
- That is the mirror image of Brainin IA's ה, whose gap nearly closes.
- So R8b learned, correctly from its data, that an ה-like shape with a narrow gap can be ח.

**Which books look like IA:** `diagnostics/measure_books.json`, Euclidean distance over z-scored medians of band, contrast, bg_std, texture, speckle, sharpness, stroke and gap.
- Of the 10 train books nearest to Brainin IA, 3 are open-ח books: hegyoneshpinozah 136, agadothatanaim 105 and mabeothayehudims 310.
- sipurim ranks 11th.
- So the open-ח faces sit in the same size and sharpness range as IA.

**Conclusion:** this is a real typeface ambiguity, not a data error, so the next round has no label fix to make. If it matters later, options are:
- per-face balance, so open-ח books don't dominate the IA-like size range;
- more train books whose ה has a narrow gap;
- leaving it as a known limit.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
