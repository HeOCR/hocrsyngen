# Scanifier v2

Scanifier v2 adds phone-capture degradations to synthetic printed pages with line geometry. The code, config and previews are experimental. The default camera priors are **uncalibrated**. OCR impact has not been measured on a held-out set yet.

## Run on a small annotated batch

From the repository root, install hocrsyngen and the experiment's CPU dependencies.

```sh
python -m pip install -e '.[test]' -r experiments/scanifier_v2/requirements.txt
python -m hocrsyngen.cli generate --count 1 --seed 17 --template printed_letter \
  --text-corpus experiments/scanifier_v2/dev/text.txt --plain-evaluation \
  --emit-line-annotations --emit-paired-render --output out/scanifier-source
python -m experiments.scanifier_v2 out/scanifier-source out/scanifier-capture --seed 118
python -m hocrsyngen.cli validate out/scanifier-capture --format json
```

`--plain-evaluation` is the generator's text-only layout switch in this example. The text file above is a project-authored dev input. The capture command reads procedural generator batches, prefers their pre-photometric PNGs, and requires `--allow-source-jpeg` to fall back to existing JPEGs. Choose a source without baked scan effects when possible. The output must be a new directory. Standard `validate` checks its generation manifest and JPEGs. Consumers use the experimental `capture_annotations.json` for capture geometry.

The Python API `pipeline.capture(image, seed, config)` accepts a synthetic PIL page and returns JPEG bytes, a bidirectional geometry map, and the sampled settings. Use `geometry.transform_annotation(record, result.warp)` to transform polygons, boxes and baselines in the stored input raster's pixel-edge coordinates. The EXIF transform handles all eight orientations and is applied exactly once. Output rotation is baked into the raster and the JPEG carries no orientation or input metadata.

The opt-in [B&W photocopy profile](BW_PHOTOCOPY.md) produces one-bit PNG training views and mapped annotations.

## Stages and priors

Pass `--config path.json` to override any fields in [priors.json](priors.json). Continuous ranges are uniform `[min, max]`. Output size and JPEG quality ranges are inclusive integers. Use equal endpoints to fix a value, zero magnitude or probability to disable optional effects, and categorical weights to choose modes. Each stage has an independent seeded random stream. A fixed seed, inputs, config and imaging stack reproduce the same result.

| Stage | Parameters and units |
|---|---|
| Geometry | Pinhole pitch, yaw and in-plane roll in degrees, plus weighted 0°, 90°, 180° and 270° turns. Camera distance, curl and crumple amplitudes are in page long-edge units. Crumple frequency is cycles across the page. Framing uses an output long edge in pixels, short-to-long aspect ratio and a minimum margin in short-edge units. |
| Surround | Procedural dark table, grey floor and wood with sRGB channel ranges, texture amplitude, and configurable grain direction and count for wood. |
| Lighting | Linear exposure, directional gain gradient, vignetting and per-channel white-balance gains. Low-light mode jointly selects the exposure, noise and ISP denoise ranges. |
| Hard light | Independently sampled shadow stripe, square shadow or sun patch. Centre is fractional frame position, width is a fraction of the frame short edge, penumbra is pixels, and contrast is a linear gain. |
| Optics | Gaussian defocus with a directional variation, and line-spread motion blur. Sigma and motion length are in output pixels. |
| Sensor and ISP | Approximate signal-dependent shot and read noise in linear RGB, with variance `shot_noise × signal + read_noise²`. Edge-aware smoothing smears weaker details and subsequent unsharp masking adds halos. ISP sigmas are in pixels. |
| JPEG | Encoder quality, with weighted 4:4:4, 4:2:2 and 4:2:0 chroma sampling. |

The papers motivate effect families, and the numerical defaults are engineering priors chosen for a phone-size synthetic raster. No cited photos, datasets or learned weights are used.

- Perspective, paper deformation and unconstrained illumination are documented in [DewarpNet, Das et al., ICCV 2019](https://openaccess.thecvf.com/content_ICCV_2019/papers/Das_DewarpNet_Single-Image_Document_Unwarping_With_Stacked_3D_and_2D_Regression_ICCV_2019_paper.pdf).
- Hard-edged document shadows are treated in [Li et al., ICCV 2023](https://openaccess.thecvf.com/content/ICCV2023/papers/Li_High-Resolution_Document_Shadow_Removal_via_A_Large-Scale_Real-World_Dataset_and_ICCV_2023_paper.pdf).
- Signal-dependent noise and colour gains follow the model family described in [Brooks et al., CVPR 2019](https://openaccess.thecvf.com/content_CVPR_2019/html/Brooks_Unprocessing_Images_for_Learned_Raw_Denoising_CVPR_2019_paper.html). Hand shake, exposure and mobile low-light tradeoffs are discussed by [Liba et al., SIGGRAPH Asia 2019](https://research.google/pubs/handheld-mobile-photography-in-very-low-light/).
- Blur, ringing and JPEG provide degradation mechanisms in [Wang et al., ICCV Workshops 2021](https://openaccess.thecvf.com/content/ICCV2021W/AIM/papers/Wang_Real-ESRGAN_Training_Real-World_Blind_Super-Resolution_With_Pure_Synthetic_Data_ICCVW_2021_paper.pdf). The JPEG quality scale follows [libjpeg-turbo's encoder](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/doc/usage.txt).

## Ground truth

The geometry is the composition of EXIF orientation, two invertible piecewise-linear shears, and a camera homography. Raster sampling uses the inverse map at output pixel centres. Annotations split at shear knots before projection, so each polygon edge and open baseline follows the same map as the raster, including interior bends. Output boxes are integer `[left, top, right, bottom]` bounds rounded outward from the transformed polygon or from the transformed source box boundary (`box_polygon` where an explicit box was supplied). Coordinates describe pre-blur placement on continuous output pixel edges. Blur, noise and lighting alter legibility while retaining gold.

`hocrsyngen_phone_capture_annotations.v1` preserves the source line and region order, logical text, and non-geometric fields. Baselines retain source point order under quarter-turns. The sidecar names the coordinate space `final_page_pixel_edges`, binds to the source manifest and line sidecar plus the output manifest and each output JPEG by SHA-256, and records the source raster hash, config, seed, input EXIF tag and realised warp for each page. The manifest preserves source template provenance. The capture sidecar carries the new augmentation provenance.

## Fit from the registered print pack

Use a dedicated folder of original **HEOCR-CAL-V1 calibration** JPEGs named by the [shot list and addendum](calibration_pack/README.md). The fitter opens only registered names and requires matching ArUco page IDs before taking measurements. Capture photos, their EXIF, and private collection paths belong outside this repository.

**Use of the photos.** Calibration-pack frames feed calibration and development only. They never enter a training list. No PS-v1 or NQ1 photo (both are held-out test sets) is ever an input; the fitter's registered-name and ArUco checks refuse them.

```sh
python -m experiments.scanifier_v2.fit_calibration path/to/calibration-jpegs out/scanifier-fit
python -m experiments.scanifier_v2 out/scanifier-source out/scanifier-fitted \
  --seed 118 --config out/scanifier-fit/config.json
```

The fitter writes reusable ranges and a report of registered, rejected and missing frames, observation counts, and retained priors. Ranges use the 5th and 95th percentiles after the minimum observation count is met. Empty input produces the original priors with an uncalibrated report.

It estimates framing, pose with an assumed horizontal field of view, white-point exposure/cast, uneven lighting, native-pixel edge spread, wedge noise proxies, dark and wood surface colours, and IJG-equivalent JPEG quality where the quantization tables support it. Corner-marker failures, clipped targets and unusable observations reduce coverage. The pack is a designed set of conditions, so the fitter leaves occurrence rates at their priors. It also retains priors for curl/crumple, hard-light shapes, grey flooring, and ISP strengths, which need targeted calibration shots or pre/post-ISP pairs. Wedge measurements are proxies from processed JPEGs and are confounded by printing, resampling and the phone ISP.

## Developer previews

Three captures from one synthetic source page, with fixed seeds and declared [overrides](dev/cases.json). These are for visual inspection.

- [Window shadow stripe on wood](dev/previews/01-window-stripe/assets/000000.jpg)
- [Dim handheld quarter-turn on a dark table](dev/previews/02-dim-quarter-turn/assets/000000.jpg)
- [Sun patch on an upside-down page on grey flooring](dev/previews/03-sun-upside-down/assets/000000.jpg)

```sh
python -m experiments.scanifier_v2.dev_samples out/scanifier-previews
python -m pytest tests/test_scanifier_v2.py
```

The [dev text](dev/text.txt) and procedural textures were authored for this project and are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The previews are project-synthetic and use the bundled [Alef font under the SIL OFL](../../src/hocrsyngen/data/synthetic/fonts/LICENSE-Alef-OFL.txt). Preview bytes were generated with Python 3.12, Pillow 13.0.0 with libraqm, NumPy 2.5.5 and OpenCV 5.1.0 on macOS.

## Independent paper and scanner effects

`experiments.scanifier_v2.degradations` supplies opt-in, independently seeded RGB-to-RGB transforms. They do not mutate the input. The ranges below are uniform, inclusive engineering priors, **not calibrated estimates**; the user chooses an effect explicitly, so these defaults do not assert occurrence rates. A fixed seed, inputs, arguments and imaging stack give reproducible pixels. These transforms are for training and calibration only, not OCR evaluation. No PS-v1 or NQ1 pixels, including the PS-v1 instruction sheet, may be used for fitting or as reverse pages. Use a separately sourced eligible training/dev page for the reverse, and check source/edition exclusions downstream.

```python
from experiments.scanifier_v2 import degradations as d
from experiments.scanifier_v2.pipeline import capture, read_config

# front and back are PIL images from permitted training sources.
page = d.show_through(front, back, seed=101, opacity=(0.03, 0.10))
page = d.paper_tint(page, seed=102)
page = d.scanner_artifacts(page, seed=103)
page = d.spatial_noise(page, seed=105)
photo = capture(page, seed=106, config=read_config())
# Alternatively, simulate a size-limited JPEG delivery on a captured PIL image:
# delivered = d.recompress(captured_image, seed=107)
```

| Function | Default sampled ranges and meaning |
|---|---|
| `motion_blur` | linear blur length 1.4–8 output pixels, angle 0–180 degrees. |
| `edge_defocus` | Gaussian sigma 0.5–2.5 pixels, blended toward frame edges from radial onset 0.3–0.7. |
| `rotated_save` | choose uniformly among baked 0°, 90°, 180° and 270° counter-clockwise turns; specify `turns` to restrict choices. |
| `show_through(image, reverse, seed, ...)` | opacity 0.025–0.12, Gaussian blur 0.3–1.2 pixels, independent x/y offset −0.025–0.025 of width/height. `reverse` is resized and mirrored from its normal reading view; its darkness is the ink mask. |
| `paper_tint` | strength 0.03–0.16 multiplying RGB toward the supplied default warm tint `(238, 225, 198)`. |
| `scanner_artifacts` | one left or right edge 0.005–0.04 of width, 0–3 vertical bars each 0.002–0.015 of width, darkness 0.75–1.0. |
| `soft_scanner_edge` | supersampled gutter or platen shadow on an explicitly chosen side, with a feathered edge and a protected text box. |
| `spatial_noise` | standard deviation 2–12 sRGB levels, variation 0.3–1.0 across an 8×8 interpolated random field. |
| `recompress` | downscale to at most 1280 pixels long edge, then JPEG quality 70–90 and 4:2:0 subsampling; returns a decoded raster. This approximates a delivery path, not a claim about a particular service's current encoder. |

`rotated_save` changes orientation and requires corresponding annotation rotation. All effects except `recompress` and `rotated_save` preserve raster dimensions and coordinates. Consumers verify crop eligibility and retain the original labels. `recompress` changes dimensions, so rescale annotations by the actual output width and height ratios. Apply page effects before `capture` to use its existing geometry mapping. The existing capture API supplies seedable motion blur, spatial defocus, rotation, dark/wood surround, signal-dependent noise and JPEG. Shutter speed and ISO are capture metadata. Fit effect ranges only from authorized non-test captures or aggregate metadata, and retain calibration provenance separately.

See [source-matched realism probes](DEV_REALISM.md) for independent verso composition, fitted archive tone and spatial noise, and role-aware RTL typography.

## Development capture profiles

The [portable presets](presets/README.md) provide coarse training ranges for common capture targets.

Use `dev_profiles` for fixed-geometry degradation recipes. It applies
effective raster-domain white point and illumination gradient, defocus and
directional blur, spatially variable noise, and optional JPEG recompression.
The phone profiles cover near and oblique views separately. The Adobe profile
represents statistics of processed rasters and leaves JPEG off for PNG
endpoints. The old flatbed recipe is a prior, including opt-in reverse-page
show-through and dark scanner bars. Use an eligible reverse raster to enable
show-through. Use [phone training views](PHONE_TRAINING.md) to combine the
phone profiles with matched perspective, nonlinear line geometry and guarded
recognizer crops.
The development fitter emits exact profiles and a private report. Captures,
image measurements, and exact fit outputs stay outside the source repository.

```python
from experiments.scanifier_v2.dev_profiles import apply_profile, read_profile

profile = read_profile(private_profile_path)
rendered = apply_profile(front, profile, seed=sample_seed)
rendered.save(output_path, format="PNG")
```

Supply a separate seed for each training sample. The renderer falls back to
the profile seed when none is supplied. It works on the stored raster without
applying EXIF rotation. Optical widths and noise are in native pixels and
8-bit levels respectively. Rescaling afterwards changes both properties.
Save losslessly to preserve the simulated JPEG effects without a second encode.

The fitter takes an explicit local JSON allowlist. Each entry has a
`profile`, a physical `page` ID, an absolute `file` path, and a `split`
of `fit` or `check`. Its top-level `purpose` must be
`non_test_development_calibration`. Assign all views and derivatives of each
physical page to the same split before opening capture pixels. The check phase
compares the frozen profile's calibration probes against the reserved real
dev pages with empirical KS distance and Wasserstein-1. Keep its outputs,
the fitted profiles and the manifest private.

```sh
python -m experiments.scanifier_v2.fit_dev_profiles fit private-manifest.json private-profiles private-fit.json --seed 561201
python -m experiments.scanifier_v2.fit_dev_profiles check private-manifest.json private-profiles private-check.json --seed 829301
```

Paper and illumination use bright, flat interior patches. Noise uses
plane-detrended luma patches, a low-frequency power fraction and variation in
patch standard deviation. Printed transitions provide an effective edge width
and a native-pixel MTF50 proxy, right-censored at Nyquist. This is a
document-content estimator inspired by [Burns's slanted-edge method](https://www.imaging.org/common/uploaded%20files/pdfs/Papers/2000/PICS-0-81/1621.pdf),
without a standard edge target. Printed marks, motion, focus, resampling and ISP
cannot be uniquely separated. Likewise the processed noise model combines
sensor, paper, ISP and compression contributions rather than mapping ISO to raw
noise. See [Brooks et al.](https://arxiv.org/abs/1811.11127) for the raw-domain
distinction. JPEG profiles sample the observed quantisation tables and
subsampling together, following [libjpeg's table model](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/doc/usage.txt).
Isolating show-through requires registered, permitted recto–verso observations.
See [Tonazzini et al.](https://doi.org/10.1186/1687-6180-2013-58).
The fitter leaves this effect disabled for empirically fitted profiles
and emits the old flatbed recipe with `prior_only` status.

[Realism v2 preview](realism_v2_preview/README.md) shows twenty paired Hebrew
pages across duplex, photocopy, bound-book and phone treatments.

[Realism v3](realism_v3_preview/README.md) compares twenty new synthetic
treatments with real photocopy, flatbed and bound-volume crops.
