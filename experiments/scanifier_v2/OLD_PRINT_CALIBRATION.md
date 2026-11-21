# Old-print scanner calibration

Use a public-domain physical copy and page images cleared against evaluation
reservations by the dataset owner. A catalog candidate alone is insufficient.
Preserve the full uncropped scan to measure edge and bar artifacts.

Create a private manifest with `purpose` set to
`cleared_public_domain_old_print_calibration` and a `leaves` array. Each
leaf needs `source_id`, `leaf_id`, `rights_url`, `clearance`, the documented
`capture_type`, and the local `recto` path. Use an unknown capture type when
scanner hardware cannot be identified. To measure show-through, attach the
actual `verso` of the same physical leaf plus `recto_box` and `verso_box`. Boxes
are four pixel-edge coordinates after EXIF orientation. Register the boxes
to corresponding physical page boundaries and orient both sides normally.
Do not substitute facing book pages. Binarized, tightly cropped, and
unpaired scans do not support all measurements.

```sh
python -m experiments.scanifier_v2.fit_old_print manifest.json private-report.json --seed 10497
```

The fitter detects continuous dark edge bands and interior bars in the
stored frame. Auditing their locations is necessary to exclude printed
rules and dark cover material. The duplex fitter estimates weak front-side
ink from the mirrored verso with an opacity, blur, and small translation.
An observation must reproduce on separate strips of the leaf and beat tests
at deliberately wrong placements. The search grid provides approximate
translations and blur. Missing support is recorded as absence of a fitted
observation.

The report contains private, candidate ranges when at least three distinct
physical leaves support an effect. After visual audit, the edge and bar
ranges use the parameter names of `scanner_edge_bars`, and the duplex ranges
use those of `show_through`. Pass `edge_sides=()` or `bar_axes=()` when the
corresponding style is disabled. Choose occurrence independently from the
conditional edge ranges. These estimates describe the scanned rasters,
including paper and processing. A flatbed-specific preset needs documented
hardware and an independent dev comparison. Neither the manifest nor the
report belongs in the source repository.
