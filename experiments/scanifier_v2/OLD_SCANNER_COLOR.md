# Old color scanner

The opt-in `old_scanner_color` profile makes an RGB training view with warm
paper, visible grain, low-resolution glyph edges and a small seeded skew.
It accepts the same pixel-edge source annotations as [B&W photocopy](BW_PHOTOCOPY.md).
The companion JSON records the working raster size, sampled settings and
source-to-output geometry. Literal text and annotation order are retained.
An annotation that clips after rotation raises an error.

```sh
python -m experiments.scanifier_v2.old_scanner_color clean.png scan.png \
  --source-ppi 300 --seed 17 --annotations lines.json
```

Supply the source raster's actual PPI. Use a source of at least 160 PPI for
the full mixture. For direct vector rasterisation, pass
`rasterize(ppi)` to `old_scanner_color` with the same oriented page rendered at
the requested resolution. The raster path area-downsamples the source. The
result is nearest-neighbour upscaled back to the oriented source size,
preserving the coarser working grid.

## Severity sampling

A seeded draw picks a band and samples severity uniformly within it.
Parameters interpolate together between the band boundaries.

| Band | Default share | Severity | Working PPI |
|---|---:|---:|---:|
| Mild | 55% | 0–0.40 | 160–140 |
| Medium | 35% | 0.40–0.75 | 140–104 |
| Hard | 10% | 0.75–1.00 | 104–77 |

| Parameter | 0 | 0.40 | 0.75 | 1.00 |
|---|---:|---:|---:|---:|
| Base rotation | −0.3° | −0.7° | −1.15° | −1.6° |
| Rotation variance | ±0.2° | ±0.45° | ±0.8° | ±1.1° |
| Blur sigma at working resolution | 0.04 px | 0.055 px | 0.07 px | 0.08 px |
| Brightness multiplier | 1.01 | 1.03 | 1.055 | 1.08 |
| Contrast multiplier | 1.02 | 1.04 | 1.075 | 1.10 |
| Noise strength | 0.15 | 0.31 | 0.53 | 0.75 |
| Sepia strength | 0.08 | 0.20 | 0.42 | 0.64 |

Use `--severity` or `severity=` to fix a point. Review points are 0.20
(150 PPI), 0.575 (122 PPI) and 1.00 (77 PPI). The sampler draws symmetric
skew within the variance at the selected strength. Severity 1 and
`--nominal` hold the angle at −1.6° for aligned comparison and preserve the
original hard reference pixels for the same input and seed. The seed still
draws the grain.

## Look Scanned reference

The [MIT Community Edition notice][license] is pinned in the [B&W source
notes](BW_PHOTOCOPY.md#look-scanned-reference). The hosted [Canvas worker][worker]
accepts `sRGB` for the colorful setting. It rasterises at PPI divided by 72,
fills the background white, draws the page under centred rotation, and applies
blur, brightness, contrast and sepia in that order. Grayscale and border are
disabled. The worker then draws the rotated grayscale SVG specular noise tile
at the requested alpha. This changes paper saturation as well as luminance.
It keeps the result in color. The hosted worker uses a one-sided random
rotation offset. The aligned local comparison pins that draw to zero and the
profile's training sampler uses the symmetric variance printed in the UI.

The CPU profile approximates the browser grain with a seeded opacity field.
Its quantiles came from the procedural SVG rendered on authored flat swatches.
It alpha-blends the grain after sepia so grain stands out against both warm
paper and dark ink. The hosted worker and the Python profile were compared
locally on eligible TRAIN pages. No private reference photos or held-out images
entered fitting. The profile is opt-in.

[license]: https://github.com/lookscanned/lookscanned.io/blob/3565da992ae2355a6cd214b5339605cb935cc4b7/LICENSE
[worker]: https://lookscanned.io/_astro/apply-scan.worker-b3188640.js
