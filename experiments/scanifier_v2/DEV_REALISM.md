# Source-matched realism probes

The archival API applies a complete, source-matched DEV fit and leaves the
front page's geometry intact. Recto and verso composition use authored text
and governed bundled fonts. Experimental gutter, platen and transmission
effects stay in DEV. The fitted phone training entry point is unchanged.

## Typography and reverse

```python
from hocrsyngen.print_typography import Paragraph, render_print_page
from experiments.scanifier_v2.archival_dev import archival_dev_view, render_verso
from experiments.scanifier_v2.dev_profiles import read_profile

recto = render_print_page(front_paragraphs, seed=21, source_type="book")
verso = render_verso(recto, different_back_paragraphs, seed=32,
                     source_type="green_book")
fits = {"green_book": {"base": read_profile(base_profile_path),
                       "duplex": conditional_duplex_fit}}
capture = archival_dev_view(recto, source_type="green_book", fits=fits, seed=51,
                            reverse=verso)
```

Pass sequences of `Paragraph(role, text)` records. Roles are `heading`, `body`,
`note` and `label`. Choose `book` or `gazette` for source-specific font, size
and weight pools. Headings and section labels are kept on one line. For body
and notes, full lines are justified by widening word gaps, with a cap of four
natural spaces. Final lines stay ragged. Pass `justify=False` to compare a
ragged control with the same text and sizes. Mixed-script, numeric and complex
punctuation lines stay in one RAQM run so adjacent bidi tokens are shaped
together. Input is NFC with single-space word separators. The renderer refuses
unsupported or clipped text and records logical lines, pixel-edge boxes,
baselines, font digests and realized sizes and weights.

Choose a distinct sequence of authored paragraphs for the reverse. The helper
uses a separate layout seed to shift the text block and vary the column width.
Its return value is in normal reading orientation. Scanifier mirrors it once,
warps it by the matched relative offset, scales the fitted blur by the raster
length, and applies a smooth local transmission field to the reverse ink.
That field is a DEV probe. The conditional opacity and blur come from the
source fit. Reverse text never enters the front label stream.

## Tone, texture and margins

Use the matching whole fit under `green_book`, `stuart_book` or
`gazette_archive`. The fits supply paper RGB, lighting, optical spread and
fitted noise amplitude, low-frequency mix and spatial variation. A zero-noise
fit stays zero. Keep the private fit digests with the resulting development
record. Supply the source's conditional duplex fit only when that source has
one. Use a base fit with the old unprotected edge and bar overlays disabled.

For a soft edge probe, pass `edge` with `side`, `width_fraction`, `darkness`,
`feather_px` and optionally `taper`. Use a lateral gutter for a bound book and a
platen fringe on an observed capture edge. The renderer supersamples the
shadow at 2× and confines it to the margin outside the union of the front
text boxes. There are no interior bars in this API. Omit `edge` and/or
`reverse` for controls using the same seed, fitted paper, optics and noise.

## Sparse black specks

Pass `specks=fit["parameters"]` to `archival_dev_view` for an optional
paper-dust comparison with the same page and seed. The raster effect protects
the annotated text boxes and preserves dimensions. Use
`degradations.sparse_black_specks` directly to apply the same effect to an
authorized Gazette candidate with its protected text boxes and render DPI.

Fit from authorized original TRAIN rasters with matching archival characteristics.
The fitter checks the scan hashes and native 300 dpi tags. It counts isolated black
components in blank 128 px tiles, estimates the 1–3 px diameter mix, subtracts the
Poisson shot term to estimate clustering and measures the margin-to-interior rate
ratio. Logged density is per 300 dpi megapixel. Fit inputs are a JSON list of
objects with relative `path`, lowercase `sha256` and `split` set to `train`.
Keep source records, fitted parameters and cropped comparisons in private QA.

```sh
python -m experiments.scanifier_v2.fit_specks train-scans.json /path/to/authorized/train
```

The effect stays inside v5's existing 500-visit Gazette section-label slice.
Pin the fit and seed and use the same setting for matched layouts. Record the
realized geometry and crop QA before admitting any affected visit.

## Candidate use

- Keep historical overlays and new historical fit combinations in DEV only.
- Use Gazette typography only on the existing, label-matched Gazette
  synthetic candidates. Preserve the downstream limit of 500 visits.
- Keep the downstream phone lane at no more than 10% of visits, with two
  oblique views per near view. Use the measured phone fit and geometry with
  no thumb proxy. Phone geometry, fitted optical distributions and annotations
  use the existing [phone training API](PHONE_TRAINING.md).

The trainer owns allocation and the eligibility of exact job inputs.
