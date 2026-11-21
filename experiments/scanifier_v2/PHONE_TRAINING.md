# Phone capture training views

Use this S10d path when an annotated page will supply candidate recognizer
crops. It combines a measured page quadrilateral with the matching Scanifier
optical and encoding endpoint. The existing registered calibration and
synthetic capture commands can continue to operate independently.

## Fit geometry on non-test captures

Stage an explicitly approved, private set of paired source renders and real
captures in one directory. Record a JSON allowlist with
`purpose: non_test_phone_calibration` and a `pairs` array. Each row supplies
`page_id`, `split` (`fit` or `check`), `profile` (`phone_flat`,
`phone_oblique` or `adobe_scan`), plus `source`, `capture`, `source_sha256`,
and `capture_sha256`. Use relative paths within that directory. Keep all
captures of one physical page in the same split. Reserve check pages before
fitting. Use authorized development or training-side pairs exclusively.

```sh
python -m experiments.scanifier_v2.fit_phone_training private/pairs.json private/phone-bank.json
```

The fitter registers source and capture landmarks, checks their spread, and
tests a smooth bow against the plane using separate spatial cells. It adds a
local paper shadow when the fit transfers to separate blank-paper tiles. A
reserved margin around the output frame leaves space for the whole page and
retains its projective shape, including for fits from real crops that lost
page corners. The bank contains measurement and source identities only.
Keep the bank, source allowlist and comparisons in private project storage.

## Render and crop

```python
import json

from experiments.scanifier_v2.dev_profiles import read_profile
from experiments.scanifier_v2.phone_training import phone_line_crop, render_fitted_phone_view

with open("private/phone-bank.json", encoding="utf-8") as stream:
    bank = json.load(stream)
profile = read_profile("private/phone_oblique.json")
view = render_fitted_phone_view(page, page_lines, profile, bank, seed=sample_seed)
for index, line in enumerate(view.lines):
    crop, rejection = phone_line_crop(view, index)
    if rejection is None:
        save_candidate(crop, line, view.parameters)
```

Supply a complete upright training page with its line ink bounds in raster
pixel-edge coordinates. Include line baselines and labels when available.
The warp moves continuous line guides and raster samples together. The
extractor deskews each line's chord and keeps the remaining curvature and
local projective scale. It rejects clipped, underresolved and neighboring-line
crops. Original labels and reading order travel with the warped annotations.
Use the applicable downstream manifest and retain reasons for omitted crops.

The fitted endpoints reuse spatial light, blur and noise measurements. Phone
JPEG uses the observed tables and sampling, with one encode and decode on the
page. Adobe is a processed-raster endpoint without a JPEG stage. Optical
widths scale from native capture dimensions to the output frame. Save crops
losslessly.

Use the explicit `render_phone_view` parameters for a controlled crease
and sharpening probe. A crease changes the page surface and its shading.
Sharpening changes the effective edge response after blur and noise.
Enable either in a training recipe when authorized non-test captures support
that setting. The fitted renderer uses supported smooth bow and leaves both
the crease and independent sharpening off.
