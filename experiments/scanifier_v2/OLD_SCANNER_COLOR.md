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

Supply the source raster's actual PPI. For direct vector rasterisation, pass
`rasterize(ppi)` to `old_scanner_color` with the same oriented page rendered at
the requested resolution. The raster path area-downsamples the source. The
result is nearest-neighbour upscaled back to the oriented source size,
preserving the coarser working grid.

| Parameter | Nominal | Seeded range |
|---|---:|---:|
| Base rotation | −1.6° | −1.9° to −1.3° |
| Rotation variance | ±1.1° | ±0.8° to ±1.3° |
| Working PPI | 77 | 72–88 |
| Blur sigma at working resolution | 0.08 px | 0.04–0.32 px |
| Brightness multiplier | 1.08 | 1.04–1.12 |
| Contrast multiplier | 1.10 | 1.04–1.16 |
| Noise strength | 0.75 | 0.65–0.83 |
| Sepia strength | 0.64 | 0.52–0.76 |

`--nominal` fixes the table values and holds the angle at −1.6° for aligned
comparisons. The seed still draws the grain. The training sampler chooses each
range uniformly and draws a symmetric jitter within its sampled variance.

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
entered fitting. The profile is experimental and has no default training dose.

[license]: https://github.com/lookscanned/lookscanned.io/blob/3565da992ae2355a6cd214b5339605cb935cc4b7/LICENSE
[worker]: https://lookscanned.io/_astro/apply-scan.worker-b3188640.js
