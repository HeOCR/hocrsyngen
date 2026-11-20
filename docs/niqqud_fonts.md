# Hebrew fonts for pointed training

The [face inventory](niqqud_fonts.csv) pins the files, licences, sources,
registry IDs and shaping checks. The [contact sheets](../samples/niqqud/) use
invented letter sequences for font development. They contain no evaluation
material. OCR performance on these fonts is not measured on a held-out set yet.

## Fixed v1 faces

These are the exact 19 faces from `tasks/niqqud-train-v1/fonts/manifest.yaml`.
That manifest has SHA-256
`48e998f0f667d347b2d41ab188a8f6ccc05985d74fe49e227187ded008ac25ce`.
The six Culmus files matched the corresponding members of the 0.140 upstream
release byte for byte. The [training render plan](niqqud_training_render_plan.md#2-fonts)
describes the fixed manifest, the punctuation-based batches, and the separate
Culmus licences. This survey adds no v1 faces.

Heebo, Rubik, Miriam Libre and Open Sans lack sof pasuq (U+05C3). Open Sans
also lacks geresh (U+05F3) and gershayim (U+05F4). The CSV records meteg
(U+05BD) and rafe (U+05BF) for each exact file. v1 removes te'amim from its
Tanakh lines. The accent checks below inform later recipes that keep them.

| v1 face | Core probe | Accent stacks | Sheet |
|---|---|---|---|
| `alef-regular` | core substitution review | unsupported | [PNG](../samples/niqqud/v1/alef-regular-a32adcc.png) |
| `frank-ruhl-libre` | core placement or shaping flagged | unsupported | [PNG](../samples/niqqud/v1/frank-ruhl-libre-f9bf269.png) |
| `david-libre-regular` | core placement or shaping flagged | unsupported | [PNG](../samples/niqqud/v1/david-libre-regular-923f06e.png) |
| `noto-sans-hebrew` | core placement or shaping flagged | clear | [PNG](../samples/niqqud/v1/noto-sans-hebrew-7ef36a2.png) |
| `noto-serif-hebrew` | core probe clear | clear | [PNG](../samples/niqqud/v1/noto-serif-hebrew-93caef9.png) |
| `assistant` | core placement or shaping flagged | unsupported | [PNG](../samples/niqqud/v1/assistant-1c3b393.png) |
| `heebo` | core placement or shaping flagged | unsupported | [PNG](../samples/niqqud/v1/heebo-18f930b.png) |
| `rubik` | core placement or shaping flagged | unsupported | [PNG](../samples/niqqud/v1/rubik-1b3a743.png) |
| `miriam-libre` | core placement or shaping flagged | unsupported | [PNG](../samples/niqqud/v1/miriam-libre-9ea8501.png) |
| `arimo` | core probe clear | flagged | [PNG](../samples/niqqud/v1/arimo-e43898b.png) |
| `tinos-regular` | core probe clear | clear | [PNG](../samples/niqqud/v1/tinos-regular-60a0e8e.png) |
| `tinos-bold` | core probe clear | clear | [PNG](../samples/niqqud/v1/tinos-bold-393269d.png) |
| `open-sans` | core placement or shaping flagged | unsupported | [PNG](../samples/niqqud/v1/open-sans-3664364.png) |
| `frank-ruehl-clm-medium` | core placement or shaping flagged | flagged | [PNG](../samples/niqqud/v1/frank-ruehl-clm-medium-6c0ab8b.png) |
| `frank-ruehl-clm-bold` | core placement or shaping flagged | flagged | [PNG](../samples/niqqud/v1/frank-ruehl-clm-bold-0f83636.png) |
| `hadasim-clm-regular` | core substitution review | flagged | [PNG](../samples/niqqud/v1/hadasim-clm-regular-950cbb4.png) |
| `hadasim-clm-bold` | core substitution review | flagged | [PNG](../samples/niqqud/v1/hadasim-clm-bold-6966208.png) |
| `nachlieli-clm-light` | core substitution review | flagged | [PNG](../samples/niqqud/v1/nachlieli-clm-light-41a9ea4.png) |
| `nachlieli-clm-bold` | core substitution review | flagged | [PNG](../samples/niqqud/v1/nachlieli-clm-bold-4b43572.png) |

The HarfBuzz trace identifies TrueType components for Tinos and Arimo,
including the dot in dagesh and the holam in vav-holam. Both Tinos weights
showed the qubuts below bet and the nearby gimel clear in the contact sheet.
The probe did not reproduce a Tinos collision on this case set. Arimo's qamats
and tipcha (U+0596) bounding boxes overlapped in the two sampled lower stacks
at every checked weight. The Arimo sheet shows them touching in the heavier
examples. Keep Arimo in the fixed v1 pool and prefer another face for a future
slice that retains cantillation. The Tinos and Arimo checks cover the specific
contexts here and do not rule out collisions elsewhere.

## v2 recommendations

- **Admit Cardo Regular and Ezra SIL Regular** through the opt-in
  [v2 manifest](../src/hocrsyngen/data/synthetic/fonts/manifest.niqqud-v2.yaml).
  Both are upright OFL book faces with all surveyed punctuation, distinct vav
  holams and clear sampled accent stacks. Ezra SIL is a Biblical Hebrew design
  with a different treatment of the points from Cardo. Cardo comes from the
  pinned [Google Fonts directory](https://github.com/google/fonts/tree/869789e84da92782c144d83d69b64cec54905b5f/ofl/cardo).
  Ezra SIL 2.51 comes from [SIL's official release](https://software.sil.org/ezra/).
  SIL's bundled notice also covers the MIT/X11 licence for Hebrew layout logic.
- **Shortlist Taamey D, Taamey Ashkenaz Bold, Keter YG Medium, and Keter Aram
  Tsova** for a distinct Biblical or manuscript-style slice. The tested files
  showed positioned points and clear sampled stacks. Keep these GPL files with
  font exceptions in a separately governed, locally provisioned manifest if that
  slice is selected. Consult the exact files in the CSV and the [Taamey Culmus
  descriptions](https://culmus.sourceforge.io/taamim/index.html) and [Taamey D
  release](https://github.com/bdenckla/Taamey_D/releases/tag/v0.921-2).
- **Keep Ezra SIL SR as an alternate** for its distinct cantillation style if
  needed. It shares Ezra SIL's base design. Noto Rashi Hebrew is a candidate for
  a dedicated commentary slice. The default registry already uses it for
  commentary blocks and does not enable it for general line rendering.
- **Reject incomplete core coverage** for a general pointed pool. Hold faces
  with geometry or substitution flags, unverified licensing or plain Culmus
  GPL notices without a font exception. Decorative variants may support the
  points and still be poor choices for the book-print slice. Taamey Frank and
  Taamey David Bold, Keter YG Bold, and Shofar Demi-Bold should stay out of a
  cantillated slice because accents are blank or cannot be verified in shaping.
- **Exclude all weights** of Drugulin CLM and Simple CLM. The repository guard
  checks family, filenames and known SHA-256s. Culmus renamed the former
  Drugulin Bold Italic to Farissol, so the probe also refuses Farissol by name.
  Exclude monospace and proprietary faces, including Cousine, Miriam Mono CLM,
  Cascadia Code, Cascadia Mono and SBL's noncommercial fonts. See the [Culmus
  release notes](https://culmus.sourceforge.io/index.html) and [SBL terms](https://www.sbl-site.org/resources/fonts/).

The v2 manifest is an additions-only manifest. Pass it as `manifest_path` to
`render_lines()` to use these faces. To mix them with v1 faces in a future
recipe, put the entries and pinned files next to that recipe's manifest, as in
the v1 setup. `governed_faces()` verifies the bytes and notices before rendering.

## Inventory scope and reading the CSV

- Google Fonts covers every family marked open source with a `hebrew` subset in
  the [Google catalog metadata](https://fonts.google.com/metadata/fonts) on
  2026-11-20. Each eligible family uses one upright file closest to Regular in
  the [pinned Google Fonts tree](https://github.com/google/fonts/tree/869789e84da92782c144d83d69b64cec54905b5f).
  A variable font in this part of the survey uses its axis defaults. A catalog
  subset is a discovery signal even for fonts that turn out to have no points.
  Byte-distinct catalog and bundled versions have separate rows.
- Culmus covers [0.140](https://sourceforge.net/projects/culmus/files/culmus/0.140/),
  the [Taamey](https://culmus.sourceforge.io/taamim/index.html) and [Fancy](https://culmus.sourceforge.io/fancy/index.html)
  releases, the Unicode Hebrew faces in the [Ancient package](https://sourceforge.net/projects/culmus/files/ancient_fonts/AncientSemiticFonts-0.06-1/),
  and pointed variants listed in the [developers' area](https://culmus.sourceforge.io/developers.html).
  The release and family notices control the licensing entries. Frank Curled
  Lamed and Comix No2 Ext CLM are listed separately because both upstream links
  returned 404. Comix No2 Ext was published as Type 1, which the OpenType probe
  cannot shape directly. The developer variants with unverified licences remain
  outside training.
- Standalone sources include SIL, Taamey D and siblings, FiraGO, Mekorot,
  Dyslex-Kriyah, DejaVu, GNU FreeFont, Liberation and Linux Libertine. The
  [Open Siddur publisher's pack](https://opensiddur.org/help/fonts/) supplies
  the legacy BenOr Rashi, Mashkit, Shlomo, Shuneet and Mekorot files. The original
  Mashkit link returned 403 and the pack's claimed embedding exception could not
  be confirmed from the font, so that file remains out of training. The CSV
  enumerates these catalogs and sources as a dated snapshot.

`default_registry_family_ids` reports family membership.
`packaged_registry_id` matches exact bytes in the default registry.
`v1_manifest_id` and `v2_manifest_id` identify entries in the recipe manifests.
`guard_blocked` describes the repository guard separately from other exclusions.
`source_url` is a direct official font or archive link when bytes were checked.
For older bundled files of uncertain upstream revision, the source points to
recoverable repository bytes. `archive_member` identifies a font inside an
archive, and `sha256` hashes that font, independent of archive compression.
Empty evidence cells on excluded or unavailable rows mean they were not probed.

`core` covers U+05B0–U+05BC, shin/sin dots, and qamats qatan. The additional
coverage columns check for a nonempty nominal glyph at each code point.
`cantillation` covers all code points U+0591–U+05AF. `cantillation_shaped`
records whether the probe could identify visible marks when those code points
were shaped singly on bet. `cantillation_stack_probe` describes the three
multi-mark accent cases. A flag can indicate a geometry concern or an
unresolved glyph identity. For Shofar Demi-Bold, nominal outlines do not imply
visible shaped accents. `sheet` paths are relative to `samples/niqqud/`. A
single sheet can serve rows with identical font bytes.

## Reproduce the development checks

Install `.[test,niqqud-probe]` and use Pillow with libraqm. The checked sheets
were made with uharfbuzz 0.57.0 (HarfBuzz 15.0.0), fonttools 4.68.0 and
Pillow 13.0.0 with libraqm 0.11.0.

```sh
python scripts/niqqud/check_fonts.py --manifest "$NIQQUD_V1_MANIFEST" \
  --training-weights --output out/niqqud-fonts-v1
python scripts/niqqud/check_fonts.py \
  --manifest src/hocrsyngen/data/synthetic/fonts/manifest.niqqud-v2.yaml \
  --output out/niqqud-fonts-v2
python -m pytest tests/test_niqqud_font_probe.py tests/test_font_exclusion.py
```

To reproduce a survey row, recover its exact file using the source, member and
SHA-256 from the CSV. Pass the local file as a positional argument to
`check_fonts.py`. The tool uses the existing guard and refuses its eval bypass.
Use only open, proportional, unheld-out files. Every run writes a PNG and a JSON
trace. The published [v1 flags](../samples/niqqud/v1/probes.json) retain the
per-weight warnings and visible-accent checks for the fixed manifest.

HarfBuzz shapes NFC strings as Hebrew in RTL. The probe checks `.notdef`,
dotted circles and visible extents. It identifies each mark by comparing the
shaped cluster with a copy of the string that omits that mark. When a TrueType
composite contains the mark, it applies component transforms before checking
its box. Fused outlines that cannot be separated are marked inconclusive.
The geometry checks cover position relative to the base, shin/sin side, the
distinction between vav holam male and haser, and overlap with neighboring
letters or other marks. An overlap flag compares bounding boxes, which can
overlap even when the actual ink is separate. The flags help direct human
review. They do not generalize to all letters, contexts, weights or sizes.
The v1 variable files were checked at `wght` 400, 550 and 700, with other axes
at their defaults. Pillow/RAQM generates the sheets on the same file bytes.

— niqfonts[openai/codex#shay-macbook-m4]@heocr/opensource
