# Portable Scanifier v2 presets

These files contain coarse renderer ranges for synthetic training and
development. The fixed-geometry presets keep page dimensions and annotation
coordinates. Pin the preset file and renderer revision when preparing a batch.

| Preset | Target |
|---|---|
| `phone_flat.json` | A mostly frontal handheld capture. |
| `phone_oblique.json` | Tone and optics for an angled handheld capture. It starts from the geometry already in the input raster. |
| `adobe_scan.json` | A processed document-mode raster with a clipped white background. |
| `archive_old.json` | A pale, processed archive scan of old print. |
| `flatbed_old.json` | A warmer color book-scan appearance. The filename is a renderer slot, and the ranges describe a book-scan proxy. |

Load any of the five files with the existing API. Supply a different explicit
seed for each page and view. The same input, preset, seed, and imaging stack
reproduce the raster.

```python
from experiments.scanifier_v2.dev_profiles import apply_profile, read_profile

page = apply_profile(clean, read_profile(preset_path), seed=page_view_seed)
page.save(output_png, format="PNG")
```

The presets contain no observed encoder tables. Use `recompress` with its
generic JPEG settings if the target is a JPEG delivery path. Keep the same
long edge for pairs with fixed-coordinate labels. If resizing, scale the
annotations with the output. For perspective, use the [capture pipeline](../README.md)
and its annotation map.

Optional overlays have their own range files and should use a separate seed:

- `duplex_show_through.json` is a conditional dose for a registered,
  normal-reading reverse render. Multiply `blur_fraction_long_edge` by the
  output long edge to get `blur_px`, capped at the transform's limit of 20.
  Pass `opacity` and `offset_fraction` to `show_through` after the book preset.
- `archive_edge_band.json` gives width, taper, and darkness for the
  `scanner_edge_bars` edge family. Select the appropriate side for the intended
  capture and disable bars with `bar_axes=()`. Apply only if the edge is part
  of the intended training view.

These are conditional appearances. Choose effect occurrence in the training
recipe, review crops before including them, and keep the clean original.
