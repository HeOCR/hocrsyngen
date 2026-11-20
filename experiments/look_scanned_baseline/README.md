# Look Scanned baseline

A CPU-only global effects backend for page rasters. It is useful as a control for the Scanifier v2 scene pipeline and for diffusion. Run the experiment locally from the repository root with NumPy and Pillow installed.

```sh
python -m experiments.look_scanned_baseline input.png result.png --seed 17 \
  --effects experiments/look_scanned_baseline/r1-flat.json
```

The command emits the resolved parameters and actual page rotation as JSON. When deriving a line crop, call `apply_scan_effects` and use `ScannedPage.transform_points` on the source line polygon before cropping the output. The source points describe the stored raster, with the origin at the upper left. Use pre-photometric input for augmentation comparisons.

| Look Scanned control | Scanifier v2 | Global baseline |
| --- | --- | --- |
| Blur | Optical defocus, directional motion and spatially varying blur | Uniform Gaussian blur |
| Border | Page surround and margin in the projected scene | Optional one-pixel black border inside the frame |
| Brightness | Linear exposure, spatial gain and white balance | Global sRGB brightness multiplier |
| Color space | RGB scene and JPEG export | Explicit gray or sRGB processing |
| Contrast | Local denoising, sharpening and sRGB conversion | Independent global contrast around midpoint gray |
| Noise | Signal-dependent shot/read noise | Seeded page-wide monochrome Gaussian grain |
| Rotation and variance | Sampled camera roll and fitted scene frame | Clockwise rotation plus seeded uniform offset within a fixed raster frame |
| Scale | Output long edge and projection framing | Isotropic raster resampling before scan effects |
| Yellowish | RGB white balance gains | Independent sepia-strength control |

The Python port follows the Canvas renderer's filter order. Its noise approximates flat scan grain using a seeded Gaussian, its scale resamples an existing raster, and its border is a crisp inside stroke. The browser uses an SVG noise layer, chooses scale at PDF rasterization, and draws a canvas stroke. In the flat first-round profile, scale is 1 and yellowish is 0 to match grayscale derivatives. Color, stronger effects and alternative values can receive separate versioned profiles.

Adapted from Look Scanned, Copyright (c) 2022 seedgou. The upstream MIT text is in [LICENSE](LICENSE). The original Canvas renderer and PDF resolution implementation are pinned to [Look Scanned commit 3565da9](https://github.com/lookscanned/lookscanned.io/tree/3565da992ae2355a6cd214b5339605cb935cc4b7).
