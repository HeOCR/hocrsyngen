<!-- Copied from the HeOCR task workspace (s17a-scanifier/r8c-aug/README.md) on 2026-11-12. Step 0 is running; results go to heocr-lead before any training. step0.sh needs bash >= 4 (associative array). -->
# R8c scan augmentation: design (draft, waiting for lead's go)

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
