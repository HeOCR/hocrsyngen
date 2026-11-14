# `render-lines`: render given text lines with governed fonts

`hocrsyngen render-lines` renders lines that **the caller supplies** into single-line images. It writes logical-order labels and records provenance for every line. It is the entry point for rendered training lines, such as R9's born-digital Knesset text, that must use open-licence fonts with per-font provenance (decision 0018). Its output is synthetic, marked `synthetic: "rendered"` on every line, and never goes into an eval set.

It is separate from `generate`, which builds template pages and samples its own text. `render-lines` doesn't touch `generation_manifest.json` v1.

## Usage

```bash
hocrsyngen render-lines --input lines.jsonl --output out/ --seed 20261113 \
  [--font frank-ruhl-libre --font david-libre-regular ...] [--preset modern_print_scan_v1] \
  [--size-range 24 72 | --band-range 27 34 [--band-def otsu2pct|p5p95]] [--weight-range 400 400]
hocrsyngen render-lines --list-fonts
```

- **`--input`:** UTF-8 JSONL, one `{"id": ..., "text": ..., "group": ...}` per physical line, with text in logical order. `group` is optional, e.g. a sitting id. Ids must be filename-safe (`[A-Za-z0-9_.-]`, at most 200 characters) and unique.
- **Size:** give one of the two.
  - `--size-range`: font px, the default being 24–72.
  - `--band-range`: target ink-band px under `--band-def`. It is converted to a font size per face (and weight) by measuring a fixed calibration line, so every face lands in the same band on typical text.
- **`--weight-range`:** sampled, then clipped to each variable face's weight axis. Static faces keep their own weight, recorded as `weight: null`.
- **Groups:** lines that share a `group` share face, size or band, and weight, so a sitting reads like one document. Degradation is still drawn per line.
- **Python:** `hocrsyngen.line_render.render_lines(lines, output, seed=..., fonts=..., preset=..., size_range=... | band_range=..., weight_range=...)` does the same and returns the summary. The CLI is the stable surface. Pin the commit you used.

## Output

| File | Content |
|---|---|
| `lines/<id>.png` | greyscale line image |
| `lines/<id>.gt.txt` | the input text, NFC, whitespace-collapsed, logical order |
| `manifest.jsonl` | one `hocrsyngen_line_render.v1` record per line: `group`, `font_id`, `font` {id, file, sha256, license, license_file, variable_weight}, `size_px`, `size_mode`, `target_band_px`, `weight`, `ink_band_px`, `dark_density`, `preset`, `preset_params` (the values drawn for that line), `seed`, `line_seed`, `style_seed`, `synthetic: "rendered"`, `label_order: "logical"`, width and height |
| `summary.json` | lines in and rendered, `refused` (id, reason; per line, never silent), counts per font, number of groups, the preset definition, size or band range, weight range, seed, the font manifest's sha256 and the package version |

**Ink band.** Every line records two definitions, both measured on the final, degraded image.

- **`otsu2pct`, the default for `--band-def`:** `ink_band_px_otsu2pct` and `ink_band_frac_otsu2pct`.
  - This is the R9 face-stats definition (`tasks/r9-new-printed/face_stats/per_face_stats.py`, from r8c `measure.py`). Ink is a pixel at or below the line's Otsu threshold.
  - The band runs from the first to the last row with more than 2% ink, so ascenders, descenders, brackets and quotes are included.
  - The density is the ink share inside the band rows, times the first-to-last ink columns.
  - On 12 rendered lines it gives exactly the same band and density as `per_face_stats.measure()`.
- **`p5p95`:** `ink_band_px` and `dark_density`.
  - Dark is below the midpoint of the line's ink and paper grey.
  - The band is the rows between the 5th and 95th percentile of dark-pixel rows, about the letter body.

Band targeting fixes the font size from a typical calibration line. Each line's actual band then varies with its content, as on a real scan: a line with brackets, digits or quotes has a taller `otsu2pct` band than its target. Select on the recorded per-line band if you need a hard cut.

## Rules

- **Governed faces only.**
  - A face is usable only if `data/synthetic/fonts/manifest.yaml` lists it with `line_render: true`, a `license` id, a `license_file` next to it and a `sha256`.
  - The renderer checks each font file against its sha256 and refuses any face that doesn't match or isn't listed.
  - Nine faces are enabled, all OFL-1.1.
    - Alef, David Libre and Frank Ruhl Libre came with the package.
    - Noto Sans Hebrew, Noto Serif Hebrew, Assistant, Heebo, Rubik and Miriam Libre come from google/fonts at commit `3cb0866aebe5de40156f418a1750cb329e81ebdb`. Each file was checked against its git blob, each has its `OFL.txt` as `LICENSE-<Family>-OFL.txt`, and the source path is in the manifest notes.
  - Gveret Levin and Noto Rashi stay in the manifest for `generate`, but are off for line rendering.
  - **Coverage.** Every enabled face has the 27 letters, the basic niqqud (U+05B0–05BC, 05C1, 05C2, 05C7), the digits and common punctuation, including ־ ׳ ״ – —.
    - Only the two Noto faces have te'amim.
    - Rafe (U+05BF) is missing from Alef, Rubik and Miriam Libre.
    - A line with a mark its face lacks is refused.
  - **Default weights.** Several variable faces default to a light instance (Assistant 200, Noto Sans Hebrew 100, Rubik 300). The default `--weight-range 400 400` renders them at regular weight.
- **Bidi** is resolved by Pillow's libraqm backend with an RTL base direction:
  - digit and Latin runs stay left to right;
  - paired brackets are mirrored.

  Without libraqm the renderer refuses to run. `tests/test_line_render.py` checks glyph order by template matching on lines with numbers, brackets, Latin and dates. It also has a negative control: a naively reversed line must fail the same check.
- **Coverage.** A line with a character its assigned face can't draw (the glyph would be `.notdef`) is refused and listed in `summary.json`. It is never rendered as a box.
- **Balance.** Faces are assigned through a seeded permutation of the sorted group keys, or line ids when there are no groups, so per-face counts differ by at most one.
- **Determinism.** Face, size and weight come from sha256(seed:group-or-line:style). Every other draw for a line (ink, paper, preset values, grain pixels) comes from sha256(seed:id). A line therefore renders byte-identically in any batch with the same face set.

## Presets

All presets work at line level. `modern_print_scan_v1` (light) is the default, and the strength is a parameter, so a training run can test it separately.

| Preset | blur σ | grain std | ink / paper grey | JPEG q | downsample | ink spread | rotation |
|---|---|---|---|---|---|---|---|
| `none` | 0 | 0 | 0 / 255 | none | 1.0 | 0 | 0 |
| `modern_print_scan_v1` (default) | 0–0.4 | 0–4 | 0–40 / 225–255 | 85–95 | 1.0 | 0 | ±0.2° |
| `modern_print_scan_v1_medium` | 0.2–0.7 | 2–8 | 10–60 / 200–245 | 70–90 | 0.7–1.0 | 0 | ±0.4° |
| `modern_print_scan_v1_small_inky` | 0.3–0.8 | 2–8 | 0–50 / 190–240 | 65–85 | 0.5–0.75 | 0–1 px | ±0.4° |

`modern_print_scan_v1_small_inky` aims at the small, inked rendering that hurt R8b on Brainin IA. R8c step 0 found that loss came from face shape at small size, not from noise. For the per-face question, set `--band-range` and `--weight-range` before you raise the preset.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
