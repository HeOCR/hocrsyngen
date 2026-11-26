> Historical development protocol. Public results: https://heocr.org/en/benchmarks.html

<!-- Copied from the HeOCR task workspace (s17a-scanifier/r8c-aug/README.md) on 2026-11-12. step0.sh needs bash >= 4 (associative array). Paths under diagnostics/ are local to that workspace. -->
# R8c scan augmentation: design and step 0 (stopped)

R7 checkpoint selection used development rows from two sources now reserved in line_verify. R7 and its verified descendants carry that exposure. Comparisons on those sources are selection-exposed.

This study examined confusions between letters with small gaps in an older scan. It tested degradations for a seeded share of real training lines, keeping share and strength configurable.

## Development reference audit

The audit checked the development references for *Kevar*, the Brainin Internet Archive scan and *Yedi'ot ha-Teva*. It found edition-text discrepancies, including one-letter differences in *Yedi'ot ha-Teva*. Those differences can add apparent errors across readers. The audit informed development only. Public accuracy reporting uses [registered real held-out benchmarks](https://heocr.org/en/benchmarks.html).

## What sets the Internet Archive scan apart

The scan combines a small letter band, visible sharpening artifacts, fine grain and speckle on a dark background. The inspection motivated separate controls for those properties and left blur off by default.

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

## Development disposition

The diagnostic did not reproduce the source-specific character confusions with a generic degradation. No R8c training followed. The typeface inspection found ambiguous gap shapes in both directions. This motivated source and typeface review instead of fitting a degradation to one scan.
