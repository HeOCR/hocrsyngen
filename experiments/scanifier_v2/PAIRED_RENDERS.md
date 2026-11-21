# Born-digital render → degraded page pairs

Start with a rights-cleared, reservation-cleared print render, for example a
born-digital plenary protocol page. Freeze the clean raster, the page ID and
its gold text or line geometry before creating variants. Keep every view of the
same physical source or edition in the same dataset split.

For a scanner view, use the fixed-coordinate raster API. The reverse raster
is optional. Supply an eligible page in normal reading orientation and leave
mirroring to the transform. If you have no verified reverse, skip this step.

```python
from PIL import Image

from experiments.scanifier_v2.degradations import scanner_edge_bars, show_through

with Image.open(clean_path) as clean_image:
    clean = clean_image.convert("RGB")

page = clean
if reverse is not None:
    page = show_through(page, reverse, seed=show_through_seed)
page = scanner_edge_bars(page, seed=scanner_seed)
page.save(degraded_path, format="PNG")
```

Both transforms preserve the source dimensions and pixel-edge coordinates.
Reuse the clean page's text, boxes, baselines and polygons. Dark bands and
bars can cover text, so keep the original gold and record the visibility rule
used by the training consumer. The clean raster remains the pair target.

For a phone view, use `pipeline.capture` and its geometry map. With
`annotations` describing the clean raster, write the returned JPEG bytes
directly and map each annotation once.

```python
from experiments.scanifier_v2.geometry import transform_annotation
from experiments.scanifier_v2.pipeline import capture, read_config

photo = capture(clean, seed=photo_seed, config=read_config(config_path))
degraded_path.write_bytes(photo.jpeg)
warped_annotations = [transform_annotation(a, photo.warp) for a in annotations]
```

Record the clean and degraded asset hashes, stable source ID and split, source
rights and clearance, generator revision, effect order, arguments/profile hash
and seed for each stage. For phone views also record the realized warp. Preserve
logical-order Hebrew in labels. Use these pairs for training and development.
