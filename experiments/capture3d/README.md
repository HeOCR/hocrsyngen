# 3D paper capture with Blender

This pilot photographs rendered TRAIN pages in four scenes. Desk and floor views use a loose A4 sheet. Book views bend both leaves around a spine. Letter views add a diagonal crease to a curled sheet. Each scene uses a subdivided mesh with paper thickness. A Cycles area light approximates a window, and some captures add a point flash or a physical phone shadow. The camera varies focal length, roll, perspective, depth of field, exposure and shutter motion. Radial lens distortion, signal-dependent sensor noise and JPEG compression are applied after rendering.

## Reproduce a batch

Install Blender 5.x and the OpenCV/NumPy dependencies outside Blender. On Apple Silicon, use `brew install --cask blender` and the default `--device METAL`. Select `--device CPU` on other systems. The scripts do not change the Blender user preferences on disk.

```sh
python -m pip install -r experiments/scanifier_v2/requirements.txt Pillow
python -m experiments.capture3d.batch screened/pages.json materials/assets.json pilot \
  --device METAL --size 720 960 --samples 16
```

The wrapper invokes Blender in background mode with `-P render.py`. It expects checksummed relative PNG paths in the source manifest and tagged CC0 files for the environment, desk and floor in `materials/assets.json`. The [pinned Poly Haven assets](assets.example.json) list the exact URLs and hashes used by the pilot. The geometry and materials for the edge props are procedural and CC0. [Poly Haven license](https://polyhaven.com/license)

The caller supplies `split: train-calibration`, SHA-256 pins for the pre-render text gate and font guard, and an ordered `pages` array. Each page has `id`, `image`, `sha256`, `font_sha256`, `seed`, `scene` (`desk`, `floor`, `book`, or `letter`), and `annotations`. A region has `id`, `kind`, `text`, and `bbox` in top-left pixel-edge coordinates. A word also has `line_id`. Use logical UTF-8 reading order and NFC. The input manifest binds checksummed artifacts from the caller's approved source pipeline.

Output line records retain the literal text. Word records bind each polygon to a `line_id` and zero-based logical `word_index`. Recover the word with `line["text"].split(" ")[word["word_index"]]`.

## Paired realism gallery

Pass `--realism-seed` to make a clean capture and a treated twin for each input.
Both arms share the paper stock, deformations, lighting, and shutter-centre
camera. The seed draws independently shuffled paper, fold, lighting and camera
recipes. The camera recipes include clean controls, individual effects and
combinations of sensor noise, near-lens flash, motion and optical defocus.
The scene adds deep crease valleys, intersecting folds, crumple and hinged
dog-ears. Six paper stocks and six lighting setups span warm and cool focused
lights, low side light, coloured ambient, and mixed key and fill.

```sh
python -m experiments.capture3d.batch screened/pages.json materials/assets.json paired \
  --device METAL --size 1200 1600 --samples 16 --realism-seed 553916
python -m experiments.capture3d.review paired local-gallery tessdata \
  --kraken /path/to/kraken --weights /path/to/model.safetensors --count 15
```

The review command rectifies the camera JPEG through its shutter-centre mesh.
It can read the captured pixels directly, with paper illumination equalised, or
with mild sharpening of the equalised image.
It then requires exact text for every line in both arms using Tesseract Hebrew
and the `heocr_modern_v1` checkpoint in `tessdata`. Optional Kraken adjudicates
disagreements. Any line still lacking two exact reads rejects the pair. Each
eligible geometry has its own six-marker raster check, and the batch requires
identical line and word projections across the pair. The local HTML shows each
pair side by side alongside its settings. The manifest preserves reader votes,
input and output hashes, physical parameters and geometry.
Use `--diagnostics` to save per-line votes on rejected pairs, or repeat
`--pair-id ID` in the batch command to retake selected scenes with their
original recipes.

## Developable office paper

Add `--developable-paper` and keep the same `--realism-seed`, ordered input
manifest, assets, and render settings. Both capture twins preserve the v2
lights, including the coordinates used to aim the flash, and all shutter and
sensor effects. Only the sheet model and paper shader change.
Pass `--frozen-optics GALLERY_MANIFEST` to replay the exact saved v2 profiles,
including any individual retakes, and fail the batch if the resulting optics
drift. The frozen manifest binds the source pages, assets, size and samples.

The sheet is planar between straight creases, with circular turn radii of
0.23–0.47 mm at creases and a broader circular band at a bound spine. Parallel
bands can make multiple folds or a diagonal turned corner without stretching
the UV. Mesh normals follow the analytic circle through each bend. At each
crease, slightly brighter fibres form a very narrow line in the sheet’s rest
coordinates. The unbevelled sheet is 0.10 mm thick.

The material uses roughness 0.91 and low specular reflectance. Anisotropic
fibre albedo and fine normal relief sit under subtle paper-tone variation. A
translucent lobe and a faint, blurred reverse-side impression model thin-sheet
transmission. The front label texture stays on the same UVs as its polygons.
The paired review command rectifies through the same piecewise-planar bands.
A separate UV-marker render must clear strictly less than one pixel for every
developable pair. The gallery can be kept entirely local for review.

## Geometry and validation

- UV boxes follow the actual triangulated mesh, including triangle crossings. The renderer projects those boundaries at the centre of the shutter and applies the same radial transform used for the JPEG.
- Camera rays test the page surface along the boundary and at interior samples. With the default visibility threshold, any sample outside the frame or obscured rejects the render. The manifest records the per-region sampled fractions. This is a sampled visibility check.
- Each scene's first case gets a separate CPU raster pass with six known UV fiducials. The pass disables shutter motion and depth of field. Detected marker centroids check the final distorted camera projection independently of the ray calculation. The pilot requires a maximum 2 px marker error.
- The batch records the Cycles version and build, selected device, declared seed, paper and camera settings, input and output hashes, per-render time, JPEGs and annotated polygons. It reports render-only and engine-pilot throughput, including the extra fiducial passes in the latter.

CC0 synthetic images and code. Blender runs as a separate GPL-licensed application. The pilot is for TRAIN/calibration only. Real reference photographs carry their separate source permissions. [Blender license](https://www.blender.org/about/license/)
