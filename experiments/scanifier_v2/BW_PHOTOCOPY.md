# B&W photocopy

The opt-in `bw_photocopy` profile emits a one-bit training view with old copier
stroke gain, thin-stroke dropout and granular toner defects. It records the
sampled parameters and source-to-output geometry for each page.

```sh
python -m experiments.scanifier_v2.bw_photocopy clean.png copier.png \
  --source-ppi 300 --seed 17 --annotations lines.json
```

Supply the source raster's actual PPI. The optional annotations are a JSON
array of records with `box` or `polygon` in source pixel-edge coordinates.
The output PNG has a companion JSON with the warp, working raster size and
mapped annotations. Text and other non-geometric fields are retained exactly.
The annotation transform raises when a labelled box would be clipped. Run
legibility checks before accepting a training view. Binarisation can still
erase a sufficiently faint character inside an in-frame annotation.

For vector pages, call
`bw_photocopy(image, source_ppi=300, seed=17, rasterize=render_at_ppi)`
with `render_at_ppi(ppi)` returning the same oriented page rendered at that
density. Direct rasterisation preserves PDF hairlines more closely. For raster
inputs the profile uses area downsampling. Both routes apply a clockwise
rotation on a fixed low-PPI canvas, grayscale and Gaussian blur, quantised
brightness and contrast, a seeded highlight overlay and optional toner
specks, then a threshold of 128. A nearest-neighbour upscale retains the
one-bit values at the oriented source dimensions.

## Nominal settings and per-page sampling

Use `--nominal` or `nominal=True` for a reference comparison. The seed selects
the noise field even at nominal settings. Page-to-page randomisation samples
each range uniformly. The rotation range changes the sampled angle between
pages, with zero extra rotation variance.

| Parameter | Nominal | Sampled range |
|---|---:|---:|
| Clockwise angle | 1.6° | 1.1–2.1° |
| Working PPI | 100 | 94–106 |
| Blur sigma at working resolution | 0.79 px | 0.70–0.88 px |
| Brightness multiplier | 0.88 | 0.86–0.90 |
| Contrast multiplier about mid-gray | 0.02 | 0.018–0.023 |
| Noise strength | 0.73 | 0.65–0.81 |
| Sparse black toner speck probability per working pixel | 0 | 0–0.0004 |

## Look Scanned reference

The open [Look Scanned Community Edition source][community] is MIT licensed,
copyright (c) 2022 seedgou. The [pinned MIT notice][license] applies to that
repository. Its Canvas path rasterises at the selected scale, centers and
rotates the page, applies blur, grayscale where requested, brightness, sepia
and contrast, then overlays noise and draws the optional border. That
revision exposes grayscale and sRGB.

The hosted site's B&W Canvas path was checked separately in the [served
worker][worker] (SHA-256
`25176de6aac97a3def6c95c5fbac303d7d29e12f217c17f32ea6f247937c8aa8`)
and [noise engine][engine]. The PDF scale is PPI divided by 72. At the
reference setting its centred clockwise rotation is 1.6° with zero variance.
The filter sequence is `blur(0.79px) grayscale(1) brightness(.88) contrast(.02)`
with sepia disabled. The filtered paper starts white. The worker overlays
the rotated, scaled noise tile at alpha .73. The engine builds the tile at
1000 × 1000 using fractal SVG turbulence (frequency .102, four octaves,
seed 15) and grayscale specular lighting (surface scale 15, constant
three times the noise setting, exponent 20, azimuth 3°, elevation 100°).
The border is disabled. The final worker threshold is
`(54*R + 183*G + 19*B) >> 8 >= 128`, with packed one-bit PNG available.

This profile is an independent CPU implementation. The correlated highlight
field approximates the hosted overlay using grayscale patch response on an
authored constant test image. The sampled black specks add an extra training
perturbation. The reference comparison exercised the hosted worker locally
on permitted TRAIN pages and used the same raster density and rotation in
the Python implementation. Pixel identity with the browser's rendering stack
is outside the profile contract. No held-out images or personal reference
captures enter its implementation or calibration.

[community]: https://github.com/lookscanned/lookscanned.io/tree/3565da992ae2355a6cd214b5339605cb935cc4b7
[license]: https://github.com/lookscanned/lookscanned.io/blob/3565da992ae2355a6cd214b5339605cb935cc4b7/LICENSE
[worker]: https://lookscanned.io/_astro/apply-scan.worker-b3188640.js
[engine]: https://lookscanned.io/_astro/scan-engine.fe769858.js
