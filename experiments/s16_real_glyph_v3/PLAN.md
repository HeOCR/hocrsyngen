# S16 v3 real-glyph synthesis

The first gallery covers modern print. The old-print track shares its source and text gate with the queued 5,000-crop C2 bank. Each track gets its own source manifest, spacing estimates and 20-triptych gallery.

## Source and rights

- Legacy `pgb-v1` and `pgb-v1b` remain quarantined. Exclude `pgb-v2` and `pgb-v2.1` from v3. Their manifests `3afd149b` and `490b8dd4` record NLI attribution for both and all five styles, respectively. All populated styles descend from NLI-API and both inherit the Brainin and Silman DEV faces.
- Opensrc found no C2 nomination with an explicit reservation release. The separate PD/PD TRAIN intake `91ecc298` offers 224 Montefiore, 25 Gordon and 50 Ha-Tekufah crops approved for local glyph extraction. The modern Gazette source has 69 cleared crops and its own narrow issuer-scan rights. Verify the contemporary source classification plus global rights for each modern crop before a CC0 gallery.
- Handwriting needs a scanned TRAIN source with exact writer, rights, glyph witnesses and an independently verified writer split. Keep allographs grouped by writer and letter. Use one writer per page, source-derived unit spacing and narrow baseline, size and shear jitter. Any contributor v3 samples must arrive with CC0 consent and an approved TRAIN split.
- Pair scan coordinates to literal independent witnesses. Record edition, physical scan, page or folio, source crop, glyph box and label hashes. Screen both source identities and newly authored CC0 text using the current #578/#581, delta, P-hist, pointed v5, C1 v0/v1 and DEV controls. Keep all held-out entities and matching ancestors outside both glyph and copy pools.

## Comparisons

1. Freeze the glyph placements and exact text. Use original isolated glyph ink and local paper tones for the raw arm.
2. Normalize local ink colour. Match stroke widths with bounded fractional morphology, preserving stroke cores. Blend only the background seam pixels with Poisson cloning over a shared paper texture and grain. Record the same placements and exact output hashes.
3. Pilot one small, text-free seam region with the retained SDXL base on MPS, pinned revision `462165984030d82259a11f4367a4eed129e94a7b`. Start at 0.20 strength. Clip generated pixels to the exact seam mask, with ink and the rest of the raster copied back byte-for-byte. Require fresh exact reader agreement. [SDXL inpainting API](https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/stable_diffusion_xl)
4. Gate both views on two Tesseract checkpoints and an independent Kraken reader. Normalize NFC and layout whitespace only. Compare to the original logical UTF-8 labels and keep each exact match. Show each real reference crop at its original byte hash. Report rejected cases, and use generated views only for TRAIN or calibration.
5. Grow the old-print track to the planned 5,000 C2 crops once the same source, font and text checks clear. Apply #158 scan realism with v3 flatbed/bound, the approved LookScanned photocopy profile and the old scanner at 5% each, and the round stains. Keep the current pointed font reservations enforced for any font-rendered controls.

## Per-instance variation

Use `hocrsyngen.printed_ink.extract_ink` from the `metrics` extra on
native-scale, gray-first glyphs. Estimate local paper brightness, normalise
it to white and keep the owned stroke with one soft antialias band. Multiply
the ink mask onto the page paper with `multiply_ink`. The optional old-print
paper grain is shared across the page and independent of each crop.

`hocrsyngen.printed_glyph_variance.vary_glyph` exposes **current**, **medium**
and **strong**. Current uses ±2.2% scale, ±1.4° rotation, up to 0.42 px elastic
displacement per axis and ±1 px stroke weight. Medium and strong apply 2×
and 2.75× to those four ranges and add small baseline and advance jitter.
Ink-intensity jitter stays within 5%. Apply the ink-only edge after warping
as well as at harvest. Use returned padding to retain the original
typographic origin before applying the recorded placement offsets. Seed the
transform independently of source selection. Repeated occurrences of the
same glyph share a set of quantized raster digests so duplicates can be
rejected.

Modern print uses the raw composite by default. Old print keeps background
normalisation around glyph patches. Compare each track's varied raster with
its same-source, same-spacing control. Require all three readers to agree
with the exact label and keep the median stroke-to-body-height gap within 10%
of the matched and full real TRAIN scan sets before accepting a preview.
Compare the 3–6 px ring with open paper using `hocrsyngen.halo_metrics`,
with an absolute target of two grey levels. Measure the real TRAIN reference
with the same tool and identify its exact source scope.

## Quote only

One matched old-print screen with three 5,000-visit continuations from the same checked parent and seed. Compare raw scan-glyph composites, classical seam smoothing and a seam-only SDXL subset. Match the exact train labels, physical-source groups, exposure and capture recipe across all arms. Use the same frozen real DEV controls and evaluate by edition. The same-day CPU3c ×32 planning rate of $0.9680/h gives a $1.21 cap for 75 minutes, including setup and readback. This cap is a time budget rather than an observed runtime for S16. Requote exact account capacity after freezing the jobs. No launch.
