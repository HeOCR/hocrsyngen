# Fixed-geometry Scanifier training views

`training_views` applies one complete development fit per page view. It uses the existing optical spread and spatial noise renderer, with optional matched duplex ink or a measured scanner edge. The clean page and its annotations remain the source for line crops.

## Render one view

Bundle each base and any fitted overlay together. Use the DEV fit from the intended source, with the caller verifying source clearance and the exact file hashes. For a mixed old-print bank use the ordered Green, Stuart and Gazette fits from the [preset selection guide](https://github.com/HeOCR/heocr-agent-wiki/blob/cc4990043d956227cfcf4e3b4b73ecd6d1812b28/records/scanify/preset-selection/README.md). Keep existing frozen banks pinned to their original settings.

```python
from experiments.scanifier_v2.training_views import read_training_fit, render_training_view

bank = [
    read_training_fit('green', green / 'base.json', duplex=green / 'duplex.json'),
    read_training_fit('stuart', stuart / 'base.json', duplex=stuart / 'duplex.json'),
    read_training_fit('gazette', gazette / 'base.json', edge=gazette / 'edge.json'),
]
view, provenance = render_training_view(
    front, bank, recipe_version='old-print-v1', bank_seed=561201,
    source_sha256=front_asset_sha256, page_index=0, view_index=0,
    reverse=registered_reverse, include_edge=True, protected_boxes=line_boxes,
)
```

- Keep the reverse at the same size and registration as the front, in normal reading orientation. Supply it only for eligible source pairs where reverse ink belongs in the training target. The chosen base decides which duplex fit applies. Blur scales with the long edge and the existing transform mirrors the reverse.
- Enable the edge on a selected view where a Gazette-like fringe belongs in the target. Each edge attempt requires valid line boxes and rejects any overlap between an edge change and a protected box. The frozen calibration supported a narrow edge. The separately callable `scanner_edge_bars` also preserves the proposed interior-bar renderer for development experiments.
- Use zero-based page and view indexes and a bounded attempt index. The bank draw and each raster stage have separate SHA-256-derived seeds. Add `k` at the caller by taking the first `k` accepted view slots. The same slot will use the same seed tuple across different `k` values.
- Save the fitted view losslessly. Bind its emitted byte SHA-256, the original source and logical labels, the unchanged annotations, and the returned provenance alongside the generation manifest. Keep the source label checks and any applicability decision in the training job's audit scope.

## Dev QA sheet

The QA command replays the frozen fits on one project-authored front and an invented reverse, using the package's [Alef font](../../src/hocrsyngen/data/synthetic/fonts/LICENSE-Alef-OFL.txt). It writes a private contact sheet and the corresponding fit hashes, stage seeds, pixel counts and geometry checks. The fit files, original non-test captures and measurements stay with their private DEV records. The code performs no source acquisition.

```sh
python -m experiments.scanifier_v2.dev_training_qa PRIVATE_FITS NEW_PRIVATE_QA_DIR
```

| Fit | DEV evidence | Check on the invented page |
|---|---|---|
| Green | Same-leaf duplex fit with displaced and unrelated-reverse controls. | The mirrored ink is visible in an amplified difference panel. The page dimensions and seed tuple match the base. |
| Stuart | Separate DEV confirmation after the Green raster and duplex fits missed transfer limits. | The matching duplex overlay and raster give different contrast and spatial noise from Green. |
| Gazette | DEV fit of the processed raster and a full-frame dark fringe. | The edge appears only at the margin. The protected boxes keep the same pixels across the edge stage. |

Compare the amplified noise strip across flat patches. The Green and Stuart fits show spatially variable residual amplitude; the selected Gazette JPEG probe can quantize the flat-patch residual to zero. QA verifies stage behavior. OCR impact has not been measured on a held-out set yet.
