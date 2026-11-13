# `render-lines`: render given text lines with governed fonts

`hocrsyngen render-lines` renders lines that **the caller supplies** into single-line images. It writes logical-order labels and records provenance for every line. It is the entry point for rendered training lines, such as R9's born-digital Knesset text, that must use open-licence fonts with per-font provenance (decision 0018). Its output is synthetic, marked `synthetic: "rendered"` on every line, and never goes into an eval set.

It is separate from `generate`, which builds template pages and samples its own text. `render-lines` doesn't touch `generation_manifest.json` v1.

## Usage

```bash
hocrsyngen render-lines --input lines.jsonl --output out/ --seed 20261113 \
  [--font frank-ruhl-libre --font david-libre-regular ...] [--preset modern_print_scan_v1] \
  [--size-range 24 72 | --band-range 27 34] [--weight-range 400 400]
hocrsyngen render-lines --list-fonts
```

- **`--input`:** UTF-8 JSONL, one `{"id": ..., "text": ..., "group": ...}` per physical line, with text in logical order. `group` is optional, e.g. a sitting id. Ids must be filename-safe (`[A-Za-z0-9_.-]`, at most 200 characters) and unique.
- **Size:** give one of the two.
  - `--size-range`: font px, the default being 24–72.
  - `--band-range`: target ink-band px. It is converted to a font size per face (and weight) by measuring a calibration line, so every face lands in the same band.
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

**Ink band.** "Dark" means below the midpoint of that line's ink and paper grey. `ink_band_px` is the rows between the 5th and 95th percentile of dark-pixel rows, which is about the letter body: ascenders, descenders and specks are trimmed. `dark_density` is the dark pixels inside the band divided by band height × horizontal ink extent. Both are measured on the final, degraded image. Check this definition against your own before you compare numbers.

## Rules

- **Governed faces only.**
  - A face is usable only if `data/synthetic/fonts/manifest.yaml` lists it with `line_render: true`, a `license` id, a `license_file` next to it and a `sha256`.
  - The renderer checks each font file against its sha256 and refuses any face that doesn't match or isn't listed.
  - Today's faces are Alef, David Libre and Frank Ruhl Libre (OFL-1.1). Gveret Levin and Noto Rashi stay in the manifest for `generate`, but are off for line rendering.
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
