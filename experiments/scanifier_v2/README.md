# Scanifier v2

Scanifier v2 adds phone-capture degradations to synthetic printed pages with line geometry. The code, config and previews are experimental, and the shipped priors are **uncalibrated**. OCR impact has not been measured on a held-out set yet.

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
page = d.thumb_occlusion(page, seed=104)
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
| `thumb_occlusion` | ellipse radius 0.06–0.15 of the short edge entering the top or bottom, with a configurable solid skin tone. This is a simple proxy, not a photographic hand. |
| `spatial_noise` | standard deviation 2–12 sRGB levels, variation 0.3–1.0 across an 8×8 interpolated random field. |
| `recompress` | downscale to at most 1280 pixels long edge, then JPEG quality 70–90 and 4:2:0 subsampling; returns a decoded raster. This approximates a delivery path, not a claim about a particular service's current encoder. |

`rotated_save` changes orientation and requires corresponding annotation rotation. All effects except `recompress` and `rotated_save` preserve raster dimensions and coordinates; occlusion can hide labels, so consumers must retain gold and decide how to handle visible text. `recompress` changes dimensions, so rescale annotations by the actual output width and height ratios. Apply page effects before `capture` to use its existing geometry mapping. The existing capture API supplies seedable motion blur, spatial defocus, rotation, dark/wood surround, signal-dependent noise and JPEG. Shutter speed and ISO are capture metadata, not direct pixel-space blur/noise parameters: there is no fitted 1/25–1/33 s or ISO 2000–3200 mapping here. Adobe Scan processing is likewise not emulated or claimed. Fit effect ranges only from authorized non-test captures or aggregate metadata, and retain calibration provenance separately.
