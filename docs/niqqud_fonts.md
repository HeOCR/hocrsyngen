# Niqqud font probe: initial registry survey

This is an **incomplete inventory**, not an admission list. The accompanying
[CSV](niqqud_fonts.csv) inventories the 17 bundled files, with font name-table
versions, licences, sources and SHA-256s. The registry itself remains the
source of truth. Its `line_render` flag is a general rendering permission,
not a niqqud-quality verdict. Sources for the older packaged files point to
upstream projects; their exact upstream release/commit is not established here.

The [training render plan](niqqud_training_render_plan.md) selects 13 already
governed faces, excludes Cousine for pointed training, and separately uses
Frank Ruehl, Hadasim and Nachlieli CLM under GPL-2 with the Culmus font
exception. Its policy keeps those files outside the OFL-only package. Drugulin
CLM and Simple CLM are held out; `check_font` refuses them for training. Do not
render them, including in this probe. The probe also refuses the evaluation
bypass and checks embedded font names. The CSV's guard column records checks
on the bundled files, not a universal claim about other versions.

## Reproduce

Install `.[test,niqqud-probe]` in a development environment and ensure Pillow
is built with libraqm, then run from the checkout:

```sh
python scripts/niqqud/check_fonts.py --output samples/niqqud src/hocrsyngen/data/synthetic/fonts/*.ttf
python -m pytest tests/test_niqqud_font_probe.py
```

The small synthetic strings cover the standard points, shin/sin, dagesh,
holam, qamats qatan and two cantillation combinations. HarfBuzz shapes each
string; Pillow/RAQM makes the contact sheets. JSON reports missing cmap
entries, `.notdef`, dotted circles and rough bounding-box checks on simple
single-mark cases. Bounding-box checks are intentionally coarse, can flag
legitimate positioning and do not establish visual correctness. Combined
marks, substitutions and mark identity remain unchecked or inconclusive;
absence of an issue in a simple case is not admission evidence. The sheets
need review by a Hebrew typography expert. Check actual intended text coverage
and all intended variable-font instances separately.

## Recommendation and remaining work

Continue the existing, separately governed training plan; do not add a new
face on the strength of this preliminary probe. Cousine is rejected for
pointed training by that plan. Review Tinos and Arimo collisions described
there and the individual probe warnings before broadening use. The two Noto
Hebrew faces are useful controls but still need combination geometry and human
review. No new fonts have been admitted in this survey.

This survey does **not** yet cover all Google Fonts Hebrew families, all
Culmus families, Ezra SIL, Taamey or other open fonts. SIL identifies [Ezra SIL
2.51](https://software.sil.org/ezra/) as its final release and describes its
Hebrew shaping and OFL licence; [Culmus](https://culmus.sourceforge.io/) and
[Taamey Culmus](https://culmus.sourceforge.io/taamim/) are further official
sources. Each candidate still needs a per-file licence/version/source and hash,
held-out check, reproducible test and review. Complete that work before using
this document as the requested exhaustive inventory or changing the registry.

— niqfonts[openai/codex#shay-macbook-m4]@heocr/opensource
