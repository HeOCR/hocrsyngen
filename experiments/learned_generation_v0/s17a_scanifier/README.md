# S17a scan-ifier and add-on build recipe

This is idea 1 of `docs/s17_real_texture_synthesis_ideas.md`: learn "clean render → real scan line" from HeOCR's own aligned real lines, then use it to turn public-domain text into scan-like training lines.

This folder holds the code **exactly as it ran** to build the two S17a add-on sets:
- `s17a_addon_v1`, 18,664 lines;
- `s17a_addon_v1.1`, 18,627 lines, the set R8b trains on.

The release can therefore point at a commit.

These are research scripts, not part of the `hocrsyngen` package. They need Torch, SciPy and Tesseract, which stay out of the package dependencies (see `AGENTS.md`). Nothing in `src/` imports them, and pytest doesn't collect them.

## Environment

- **Python:** 3.12 with torch 2.12.0, numpy 2.4.6, scipy 1.17.1 and Pillow 12.2.0 (with libraqm).
- **Tesseract:** 5.5.3, used to read lines back with the R7 model. Gate 2 also uses `tessdata_best` heb (`r5-tesseract-ft/models/best`).
- **Hardware:** generator training and generation ran on Apple `mps`.
- **Font:** the packaged `FrankRuhlLibre-wght.ttf` (OFL) from this repo.
- **Input paths** are hard-coded as they ran, under the HeOCR task workspace `~/agents/environments/opensource/projects/heocr/tasks/`:
  - `s16c-glyph-scale/outputs/lines/bynli_lines_v2`: the real line crops;
  - `r7-tesseract-real/models/r7` and `r5-tesseract-ft/models/best`;
  - the Ben-Yehuda dump in `s16c-glyph-scale/inputs/benyehuda-2026-03`;
  - the R8 dev lists and the scored references, used for decontamination.

## Recipe

Run every step from the task folder that holds `intermediates/` and `outputs/`, with `scripts/` set to this folder.

| Step | Command | Output (sha256) |
|---|---|---|
| 1. Pairs | `build_pairs_v2.py intermediates/pairs_v2 --workers 6` | `pairs_v2/pairs.jsonl` `6f542711…e309` |
| 2. Generator | `train_scanifier.py intermediates/pairs_v2 intermediates/run2 --iters 20000 --batch 16 --val-books 4` (seed 20261111, mps) | `run2/last.pt` `efdb5f82…8e3a` |
| 3. Texts | `make_texts.py intermediates/addon_texts --n 20000` (seed 20261111) | `texts.jsonl` `db7a96fa…e463` |
| 4. Generate | `generate.py intermediates/run2/last.pt intermediates/addon_gen --texts intermediates/addon_texts/texts.txt --style $(cat addon_styles.txt) --n 20000 --seed 20261112` | `g00000.png` … `g19999.png` |
| 5. Gates | `gates.py intermediates/addon_gen --book-of intermediates/pairs_v2/pairs.jsonl` | `gates.jsonl` `289f1378…c2571a`; 18,664 accepted |
| 6. Export v1 | `export_addon.py intermediates/addon_gen intermediates/addon_texts outputs/s17a_addon_v1` | `manifest.jsonl` `0cff6847d72f25cd…` |
| 7. lstmf | `r8-tesseract/scripts/make_lstmf.py runs/ab/addon_src runs/ab/addon_lstmf --workers 8`, where `addon_src/train/s17a/` holds symlinks to the v1 `lines/` | `addon_lstmf/train.list` |
| 8. v1.1 | `make_v1_1.py outputs/s17a_addon_v1 <s16c>/outputs/lines/bynli_lines_v3/manifest.jsonl runs/ab/addon_lstmf/train.list outputs/s17a_addon_v1.1` | `manifest.jsonl` `3f79461b6842b396…`, `train_lstmf.list` `b48131bd3ad504af…`, `r8b_decontam_drops.json` `648c80f8fed3a5fd…` |

**Style crops.** `addon_styles.txt` lists the 870 style crops used in step 4: 30 for each of the 29 pairs_v2 books (sha256 `cc701048…cf7d3`). All of them are train-split crops. None comes from a dev, scored, held-out or reserved scan.

**What was changed.**
- `make_v1_1.py` is the inline step that built v1.1 on 2026-11-12. I turned it into a script without changing its logic.
- The other scripts are byte-identical to the files that ran.
- The v1.1 `LICENSE` (CC0-1.0), `NOTICE`, `README.md` and `source_provenance.json` are documents written for the release, not generated.

## Reproduction check (2026-11-12)

Re-run from this code on the same machine:

| Step | Result |
|---|---|
| 3. Texts | `texts.jsonl` and `texts.txt` are byte-identical. |
| 4. Generate, first 200 lines | All 200 PNGs are byte-identical to the original run. All 192 accepted ones match the `image_sha256` values in the v1.1 manifest. |
| 5. Gates, on those 200 lines | Every gate field and every accept/reject decision is identical. |
| 6. Export v1 | `manifest.jsonl` and `summary.json` are identical. |
| 8. v1.1 | `manifest.jsonl`, `train_lstmf.list` and `r8b_decontam_drops.json` are byte-identical. 37 lines are dropped and 18,627 kept. |

**Not re-run:**
- steps 1–2, the pair build and the generator training, because training on mps is not bit-reproducible. The hashes of their outputs are in the recipe table.
- the full 20,000-line generate and gate passes.

## Provenance packet (`docs/learned_generation_packaging_boundary.md`)

| asset_id | asset_kind | source | author_or_publisher | license | training_data_provenance | redistribution / commercial / derivative | privacy_review | attribution_required | bundled_in_repo | project_synthetic_rationale |
|---|---|---|---|---|---|---|---|---|---|---|
| `s17a_run2_G` | model weights (U-Net G + style encoder, `last.pt`, sha256 `efdb5f82…8e3a`) | trained here by `train_scanifier.py`, from scratch | HeOCR maintainers | Apache-2.0 under the HeOCR weights policy when published (not yet published) | pairs_v2 only (row below); no pretrained weights | yes / yes / yes | none needed: printed public-domain books, no living-person handwriting | none | no | learned only from our own aligned PD crops |
| `pairs_v2` | training dataset (9,899 render/real pairs, `pairs.jsonl` sha256 `6f542711…e309`) | `build_pairs_v2.py` over the `bynli_lines_v2` train split | HeOCR (crops of the scans below) | the scans' PD status; crops CC0 | 29 train books; dev, scored and held-out books excluded | yes / yes / yes | as above | NLI scans: "From the collections of the National Library of Israel / מאוסף הספרייה הלאומית (NLI record <id>)" | no | real-scan texture source, labelled as such in the add-on NOTICE |
| `pby_2026_03` | text corpus | Project Ben-Yehuda public_domain_dump 2026-03 | Project Ben-Yehuda volunteers | public domain | n/a | yes / yes / yes | none needed (PD literature) | credit "Project Ben-Yehuda volunteers" | no | source text for synthetic lines |
| `frankruhl` | font | `src/hocrsyngen/data/synthetic/fonts/FrankRuhlLibre-wght.ttf` | its authors (see the packaged font docs) | OFL-1.1 | n/a | yes / yes / yes | n/a | per OFL | yes (already packaged) | clean render |
| `s17a_addon_v1.1` | generated samples (18,627 lines) | steps 3–8 | HeOCR maintainers | CC0-1.0 | from the rows above | yes / yes / yes | none needed | NLI credit in NOTICE | no | synthetic; never in an eval set |

Rights notes:
- Of the 29 style books, 6 are NLI scans under `public-domain-free-use` and 23 are university-digitised IA scans with an accepted rights justification.
- No Google-digitised scan is used.
- Per-book credits are in the v1.1 `NOTICE`.

## Isolation checks and known gaps

**Checks run for this PR:**
- `python -m pytest` passes without the experiment deps installed. `pytest` only collects `tests/`.
- No file under `src/hocrsyngen/` imports from `experiments/`, torch or scipy.
- `pyproject.toml` is unchanged, and `experiments/` is outside `packages.find` (`where = ["src"]`).
- No weights, datasets, caches or bulk images are committed. `addon_styles.txt` is a 870-line path list.

**Known gaps** (left as they ran, so that this commit is the one that built v1.1):
- The input paths are hard-coded to the HeOCR task workspace. Those inputs are not public yet. They become public through HeOCR releases: the R8b line sets and R7. Whether `last.pt` is published with the add-on is the lead's call.
- The scripts don't yet fail with a clear message when an input is missing.
- Training ran on mps (Apple GPU), which is not bit-reproducible. This keeps the method exploratory, per the boundary doc.
- **Evidence and baseline comparison:** the R8b A/B (S17a add-on vs control, same recipe and list order) improved CER on both clean held-out dev books. That's −0.017 on Kevar and −0.015 on Yedi'ot ha-Teva (page-cluster bootstrap, 95% CIs below zero). Details are in the HeOCR task notes.

**Cleanup:** the run's local intermediates (`addon_gen/`, `pairs_full/`, `pairs_v2/`) stay in the workspace until this PR merges. They then go to the Trash. The released add-on and `last.pt` are kept.

## Dose arm (s17a_addon_v2, 2026-11-13): no win

A second set of 18,553 S17a lines, added to R8b's list, was tested against the released r8b-main-fold under a rule written down before training ([dose_v2/PREREGISTRATION.md](dose_v2/PREREGISTRATION.md)). **The arm does not win.**
- On OLB Reshumot dev "all", Δ is +0.019 with a 95% CI of [−0.037, +0.052], which includes 0.
- Silman is a guard loss: Δ is −0.046, CI [−0.070, −0.023].

The S17a dose stays at v1.1, with no confirmation run. The full tables, with a stock tessdata_best column, are in [dose_v2/RESULTS.md](dose_v2/RESULTS.md). The pipeline is `make_texts_v2.py`, `restore_styles.py`, `export_addon_v2.py`, `gate_sheets.py`, `build_dose_list.py` and `dose_decide.py`.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
