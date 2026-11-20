# Pointed (niqqud) training renders: plan v1

Status: **plan, lead's decisions in** (2026-11-19, §6). Prepared during the RC2 gate window in light mode. The text
pool, the font list, the render units and small dry runs are done. Bulk renders and any training wait for eval to announce the end of the window. They then run as
power-scheduler units, or as a RunPod run that the lead approves.

Owner: synth-gen. Reviewer: heocr-lead.

Development record: nothing here is a measured accuracy. Performance on pointed print is not measured on a held-out
set yet. The only scored set for it is the niqqud print test NQ1, which eval scores once.

## 1. Text pool v1

The builder is `tasks/niqqud-train-v1/scripts/build_pool.py`, outside this repository, because it reads eval's
reservation lists. Its output is `pool/pool_v1.1.jsonl` (sha256 `1f7e62a3…`) with `pool_v1.1.counts.json`.

**v1.1** also drops the works of calibration pack v1 and of the P11–P12 addendum, and Judges 11 (§4). The lines
were refilled from other works, so the counts below are unchanged within a few lines.

**Sources.** Both are htext releases. Both are public domain in Israel, and each line records `il_us`.

| Source | File | Lines in pool |
|---|---|---|
| htext pby-v3, CC0 | `pby_lines_il_niqqud_v3.txt` (point density ≥ 0.5), sha256 `d436f87d…`, joined to the PBY work through `pby_line_index.v1` | 59,986 lines from 9,343 works |
| htext tanakh-v1 (WLC via morphhb) | `tanakh_lines_niqqud_v1.txt`, cantillation stripped; ׃ added at each verse end, as NQ1 and printed Bibles show it | 14,944 |

By genre: poetry 25,524; prose 16,539; Tanakh 14,944; reference 8,388; drama 5,845; article 1,708; fables 1,501;
memoir 298; letters 183. The il_us share is 0.21.

**Exclusions, in order:**

1. **Reserved works.** Every `eval_reservations_v1`–`v7` at restricted-eval `469cf15f`, via `reserved_works.py`.
   - PBY: the reserved ids plus every other PBY edition of the same work (title and authors). 549 lines dropped.
   - Tanakh: every chapter that a reserved range or its reserved parallel touches. This is wider than the verse rule.
     482 lines dropped.
2. **NQ1.** Any line sharing a word 6-gram with any of these:
   - the print pack's typeset references;
   - data-collection's v1 and v2 page texts (the withdrawn v1 works stay out);
   - this repository's `hebrew_lines_niqqud_eval_v1.txt`.

   Points are stripped and maqaf counts as a space before the check. The whole work of a hit line leaves the pool. 26
   lines hit, in 4 works, so 38,502 lines were dropped:
   - PBY 466 and 36886, two editions of Immanuel of Rome's *Mahbarot*;
   - PBY 5381, Ibn Ezra;
   - PBY 61040, Fleischmann.

   No Tanakh line hit once the reserved chapters were out.
3. **Characters and length.** Allowed: Hebrew letters, points, maqaf, geresh and gershayim, digits and common
   punctuation. Lines must be 12–90 base characters long.
4. **Calibration text.** The calibration pack v1 works, the addendum works (PBY 3233, 5016, 6146) and Judges 11,
   because calibration captures are dev.
5. **Pre-filter against eval's official targets** (`check_train_overlap.targets()`). 70 lines dropped: 50
   `rseries_dev_report`, 20 `pmod_holdout_plenary`. Counts only.

**Sampling.** Seeded order `sha256("20261119:niqqud-train-v1:" + line sha)`, at most 120 lines per work. Poetry is
capped at 55% of the PBY lines, and the targets are 60,000 PBY lines plus 15,000 Tanakh lines.

**CLEAN.** The pre-filters are mine. Only eval's `check_train_overlap` run on the rendered list counts. It runs before
any training.

**Not in v1:** nakdan-pointed prose (Dicta's model over unpointed PBY prose, as NQ1's `nakdan_prose` stratum).
- It is a GPU or MPS job, so heavy, and planned as a v2 add-on unit after the window.
- It uses other works, with the same exclusions.

## 2. Fonts

**Guard.**
- Drugulin CLM and Simple CLM are NQ1's held-out fonts and never appear in any training render.
- Faces come from `governed_faces()`. Since #123 it calls `check_font` on every face's id and file, so names, file
  names and sha256 are all refused.
- The generator paths were already guarded by #122.

**v1 faces.** 13 of the 15 governed faces:

| Faces | Lines they can draw |
|---|---|
| Frank Ruhl Libre, David Libre, Alef, Noto Serif Hebrew, Noto Sans Hebrew, Assistant, Arimo, Tinos, Tinos Bold | every pool line |
| Heebo, Rubik, Miriam Libre | 92%: they lack sof pasuq ׃ |
| Open Sans | 92%: it lacks ׃, ׳ and ״ |

- **Cousine Regular and Bold are dropped.** The dry run shows them broken on pointed text: monospace spacing, detached
  marks, and a box glyph on one line. Real pointed print is not set in monospace.
- **Mark check** on 40 pool lines per face, rendered with and without points and counting the extra ink components:
  - every face draws points as separate ink;
  - Tinos, Arimo and Cousine show fewer separate mark components, so some marks collide.

**Batching.** `render-lines` assigns faces in balance, then refuses lines the face can't draw. So the units split by
coverage:
- batch A: lines with ׃, ׳ or ״, on the 9 faces that cover all of them;
- batch B: all other lines, on all 13 faces.

**Culmus "seen" faces (lead: yes).** NQ1's other pages use three Culmus faces plus Noto Serif Hebrew. The
Culmus faces are Frank Ruehl CLM, Hadasim CLM and Nachlieli CLM. None of the three is a governed face, so no training
render has used them. NQ1's held-out-versus-seen font contrast only means something if the seen faces are in
training.
- **Done:** a pointed-render font manifest outside this package, `tasks/niqqud-train-v1/fonts/manifest.yaml`, read
  through `render_lines(manifest_path=...)`. It holds the 13 faces above plus Frank Ruehl CLM Medium and Bold,
  Hadasim CLM Regular and Bold, and Nachlieli CLM Light and Bold (v0.140, sha256-pinned).
  - **Licence:** GPL-2.0 with the Culmus font exception. The licence file is built from the fonts' own name table:
    the GPL text, the copyright notices and the exception.
  - **Why outside the package:** this package's wheel ships OFL faces only.
- **Share:** 6 of 19 faces in batch b, and 6 of 15 in batch a, so about a third of the lines.
- **Check:** they cover every character in the pool. An 18-line trial render shapes cleanly
  (`dryrun/sheet_culmus_v1.png`).

## 3. Render plan (after the window)

| Unit | Lines | Faces | Notes |
|---|---|---|---|
| `nqtrain_v1_a` | pool lines with ׃ ׳ ״ (6,137) | 15 (9 governed + 6 Culmus) | |
| `nqtrain_v1_b` | all other lines (68,793) | 19 (13 governed + 6 Culmus) | |

The unit script is `tasks/niqqud-train-v1/scripts/render_unit.py {a|b} OUT --band-range MIN MAX`. It pins the pool's
sha256 and refuses `HOCRSYNGEN_EVAL_RENDER=1`. A 9-line trial of each batch rendered with no refusals.

- **Presets,** split by seeded line id:

  | Preset | Share |
  |---|---|
  | `modern_print_scan_v1` | 50% |
  | `modern_print_scan_v1_medium` | 30% |
  | `modern_print_scan_v1_small_inky` | 20% |

  Phone-capture degradation comes from scanifier v2 once it is calibrated (§4). It is not part of v1.
- **Size:** `--band-range` in the R-series line height, `otsu2pct`; the exact range is matched to the current R recipe
  at unit build. Weight 400–700 where the face is variable.
- **Seed:** 20261119; every line's render derives from (seed, id).
- **Estimate:** about 75k PNGs, roughly 1–1.5 GB, and under an hour of single-core CPU. Not measured; the first unit
  logs its timing. Free disk now: about 22 GB.
- **Labels keep the points** (logical order, NFC; lead: we want models that output niqqud).
- **Unpointed replay:** the training mix keeps an unpointed replay share, so the model doesn't invent marks on
  unpointed text.
  - **What it is:** the current R recipe's unpointed lines, kept in full.
  - **Proposed ratio:** pointed lines at most a third of the list, so unpointed lines are at least twice the pointed
    add-on.
  - **Mark invention** is tracked on dev only: points per output letter on the unpointed dev sets, against the R
    recipe without the add-on.
  - The lead sets the exact ratio at recipe build.
- **NQ1 scoring** by eval: with points, and stripped.
- **After render:**
  1. eval's `check_train_overlap` on the whole rendered list, which must be CLEAN;
  2. a 200-line contact sheet per face for a visual check, done by me, with only unclear categories going to Shay;
  3. the lead picks the R recipe add-on, with selection on dev sets only.

  NQ1 is never used for selection.

**Dry run (done, 24 lines).** The first 12 PBY and the first 12 Tanakh pool lines, on all 15 faces, with preset
`modern_print_scan_v1`.
- 22 rendered. 2 were refused for ׃ on Rubik and Heebo, which is what the A/B batching handles.
- The visual check found the Cousine problem above.
- The superseded pool v1.0 file is in the Trash; its counts are kept as `pool_v1.0.counts.json`.
- Outputs are in `tasks/niqqud-train-v1/dryrun/`.

## 4. Scanifier v2 calibration for pointed text

The rule: calibration uses the calibration pack (`experiments/scanifier_v2/calibration_pack`, `HEOCR-CAL-V1`) only.
NQ1 frames and PS-v1 frames are never opened for calibration or selection.

**Gap.** Of the pack's 10 pages, only P05 is pointed (13 pt verse in Frank Ruhl Libre). Marks are the first casualty
of blur, noise, JPEG and Telegram's 1280 px recompression, and one pointed page at one size is too little to fit mark
loss.

**Calibration pack v1 addendum, P11–P12** (lead: approved; the lead puts it to Shay with his good-light NQ1 pass).
- **P11:** pointed prose at 10, 11 and 12 pt.
- **P12:** a two-column pointed Tanakh page at 10 pt.
- **Frame:** the same as the other pages (ArUco, QR, slanted edge, grey wedge).
- **Faces:** seen faces only, never Drugulin CLM or Simple CLM.
- **Text:** `tasks/niqqud-train-v1/addendum/addendum_text.json` (sha256 `cc34b8af…`), selected by
  `select_addendum_text.py`, all PD in Israel and the US:
  - P11: three fully pointed blocks (at least 0.7 points per letter) from htext pby-v3 il_us, PBY 3233, 5016 and
    6146, each about 520–660 base characters;
  - P12: Judges 11, 3,110 base characters, sof pasuq at each verse end.
  - Refused: reserved works and chapters, NQ1 6-grams, calibration v1 works, the books Neh, Ezra, Ezek and 1Chr, and
    any block with an official-target 6-gram (4 Tanakh runs).
  - These works and chapters left the training pool (v1.1).
  - The PDF is built only after eval's CLEAN on this sha.
- **Faces:** bundled OFL faces only, as the rest of the pack.
- **Shots:** each of the three phones in conditions A, B, D, F and G: steady, motion blur, low light, Telegram and
  Adobe Scan. These are the ones that remove marks.
- **Printing:** the pages can be printed in the same session as NQ1, but the captures are kept apart (different QR
  prefix, `HEOCR-CAL-V1-P11`).

**Fit.**
1. Register each calibration frame to its render through the homography from the ArUco markers.
2. For each mark, take the ink fraction inside its render mask (dilated), per condition and phone. This is the "mark
   survival" curve, measured against stroke width and point size.
3. Fit the scanifier's per-condition parameters (blur PSF, noise against ISO, JPEG or resize chain, binarisation for
   Adobe Scan) so that the survival distributions on synthetic renders of the same pages match the real frames
   (KS distance per mark class: dots, bars, shin and sin dots, dagesh).

All of this uses calibration frames only.

**Judging.** The scanifier-degraded pointed lines go in as an ablation against the v1 render-only lines. Selection is on
dev only. That means the calibration frames as real-capture dev, plus the R-series and P-mod dev sets. NQ1 is scored
once, by eval, on the final pick.

## 5. Queue after the window

| Step | Run as | Gate |
|---|---|---|
| `nqtrain_v1_a`, `nqtrain_v1_b` renders | scheduler units (CPU), or RunPod | eval announces the end of the RC2 window |
| eval CLEAN on the rendered list | eval | renders done |
| Culmus faces | done: task-local manifest (§2) | — |
| Nakdan prose v2 add-on | scheduler unit (MPS) | after the v1 renders |
| Calibration addendum P11–P12 | eval CLEAN on the text, then the PDF, then Shay prints | approved |
| Scanifier pointed fit and ablation | after the captures | dev only |

No unit is in `units.txt` yet: the window allows no new unit.

## 6. Lead's decisions (2026-11-19)

1. Add the Culmus seen faces (Frank Ruehl, Hadasim, Nachlieli CLM) to the pointed renders: done (§2).
2. Keep the points in the labels, with an unpointed replay share (§3).
3. Calibration addendum P11–P12 approved. Build the PDF after CLEAN; the lead puts it to Shay with the good-light NQ1
   pass.
4. Queue `nqtrain_v1_a` and `nqtrain_v1_b` as scheduler units after eval ends the window.

**Held-out-font trace,** answered before merge (eval has it):
- **No training list holds a Drugulin CLM or Simple CLM render.** The repro for #123 was a throwaway test manifest
  with one line, now in the Trash.
- **hdocsyngen pilot v0** (before hdocsyngen #6) set four documents in those fonts:
  - tender-20261126 (Simple CLM) and tender-20261129 (Drugulin CLM) are in D-bench set H, an eval set;
  - report-20361129 and report-20361138 stay in the task folder.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
