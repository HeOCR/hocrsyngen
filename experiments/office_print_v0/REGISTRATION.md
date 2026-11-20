# Office-print v0: arm registration

> Development / selection evidence; not a performance claim. Held-out results: https://heocr.github.io/benchmarks.html

Registered 2026-11-18, before either arm trains. This fixes the decision rule of [PLAN §2.3](PLAN.md#23-development-rule-fixed-in-the-arm-registration-pr-before-either-arm-trains) and the arms of PLAN §6 as they will run. Where this file and PLAN differ, this file holds. Nothing below may change after the first arm starts, except by a dated amendment in this file that says why.

Owner: synth-gen. Approver: heocr-lead (merges this PR before the arms start, after eval's registered gate run on the night of 2026-11-18).

## 1. Fixed heocr commits (lead, 2026-11-18)

| Column | heocr commit | Role |
|---|---|---|
| **Deciding** | `57e58deb3a230a86b07e9fdf110223cac9fbf471` (0.1.0rc1, the frozen release candidate, #90) | The arm decision (§4) is made here. A model would be swapped into the package as it stands at the release candidate. |
| **Model's own share** | `7f5e99ee70827f1dc080f3a5471d2307e8a548fd` (#64, the commit of the PLAN §2.2 diagnosis) | The gain at this commit is what the model adds without the later number handling. |
| **Information only** | heocr `main` at scoring time, its hash recorded in the result | Shown, never decides. |

Every arm, stock tessdata_best heb, and heocr with stock inside are scored at all three.

## 2. Data

All parts are built from text that passed the PLAN §4 decontamination. **eval's official `check_train_overlap` CLEAN on each arm's final list is a precondition for training it** (§5). The data manifests and their sha256s are filled in below once the gates have run. The lead checks they are filled before merging.

### 2.1 Text pool (built)

`tasks/office-print-v0/scripts/build_pool.py`:
- **Source:** reshumotlines_v2 clean3 (70,665 lines).
- **Removed, in this order:**
  1. eval's reservations, whole units (19,450 lines; heocr-restricted-eval main `3717535`, `eval_reservations_v1.json`);
  2. exact line hits on eval's D-bench text-pool and PS-v1 hash fixtures (379);
  3. lines with a word 6-gram in any S17a decontamination pool, under both tokenisations (1,033).
- **Split by a hash of the unit id** (`hocrsyngen.office_pages.holdout_units`, 5%):

| File | Lines | Units | sha256 |
|---|---|---|---|
| `pool_train.jsonl` | 45,980 | 107 | `96188a8e2ea67208b413191dc3feb5f97f3465fa9ec171685e0aaab21e5edd2f` |
| `pool_val.jsonl` (office_val text) | 3,823 | 8 | `7982b14b1c1533d1e0259f4d6242c52f35f3903ae3af5edde517496771110e91` |

No office_val unit appears in any training part.

### 2.2 Synthetic office lines, O1 (generated, gates running)

- **Generator:** hocrsyngen `749069d` (office_pages, halved speckle #108), `--seed 20261118 --pages 2200 --split train`, from `pool_train.jsonl`.
- **Output:** 129,716 line and cell crops.
- **Gates** (`tasks/office-print-v0/scripts/office_gates.py`, rule approved by the lead 2026-11-18). A crop is rejected if:
  - `glyph_no_ink` fires (S17a ink check, default thresholds), or the crop is flat (`flat_crop`);
  - or its darkness correlation with its clean render (same geometry, no photometric steps) is below 0.80;
  - or stock fails it (CER > 0.5), reads its clean render well (CER ≤ 0.2), and its correlation is below 0.90.

  `ink_outside` and `stray_cc` are counted, not rejecting.
- **O1** is a seeded sample (seed 20261118) of **120,000 accepted crops**, or every accepted crop if fewer remain.

### 2.3 Real anchor

- **What:** the reshumotlines_v2 line images of every `pool_train.jsonl` line, 45,980 lines.
- **Plan change:** PLAN §6 said 51,215. The office_val units and the fixture and 6-gram drops come out.

### 2.4 Degraded real anchor

- **What:** the first 35,000 gate-accepted lines of a seeded shuffle (seed 20261120) of the anchor. 41,000 are degraded so that enough are accepted.
- **How** (`tasks/office-print-v0/scripts/build_degraded_anchor.py`):
  - each line raster is upsampled ×2, because the anchor lines are about 49 px high, half the scale at which the §5.2 filters were set: a 3 px filter erases their 2 px strokes;
  - it is skewed by up to ±1° (seeded per line);
  - it goes through one of the §5.2 photometric models from hocrsyngen `749069d`: `office_scan`, `photocopy` or `phone_photo`, at 50:25:15 renormalised;
  - it is rescaled by the model's dpi range over 300;
  - a photocopy that would thicken twice is redrawn (lead, 2026-11-18).
- **Smoke test** (200 lines): 173 accepted. office_scan 112/112, phone_photo 31/32, photocopy 30/56: the correlation gate drops thinned and doubly darkened copies. The accepted part therefore holds fewer photocopies than 25%; the realised shares are reported.
- **Plan change:** line rasters replace PLAN §6's page rasters. The born-digital page geometry is not kept beside the lines, so a page-level homography has nothing to act on.
- **Gates:** the same gates as O1, with the undegraded line as the clean render.
- **Labels:** the anchor's own labels, unchanged.

### 2.5 Real scans: OLB Reshumot train

- **What:** a seeded sample (seed 20261121) of **60,000** lines from `olbreshumotlines_v1/train_list.txt`. Arm B recycles all of them (§3).
- **Source list:** 136,903 lines, sha256 `59b5d2d8c9bcea6c355709300a8be26b39aed3fa09cbd13445118497ef16f869`. eval's reservations hold none of its units.
- **Provenance:**
  - **Images:** scans of Reshumot (Sefer HaChukim, Kovetz HaTakanot), PD-IL under Copyright Act 2007 §6.
  - **Labels:** Hebrew Wikisource's ספר החוקים הפתוח (Open Law Book) text with the same wording (`label_source: wikisource_olb_same_wording`), licensed CC BY-SA 4.0. Every line records its page title, revision id and permalink (`attribution`, `attribution_url`, `olb_revision_id`).
- **Decision 0016 applies to both arms:**
  - weights stay Apache-2.0;
  - the model's NOTICE and card credit "Hebrew Wikisource contributors" (CC BY-SA 4.0) as a source of training text, naming `olbreshumotlines_v1` and its per-page permalinks;
  - no word list or dawg is built from this text (stock's own is kept);
  - if the line set's labels are ever published, they carry CC BY-SA 4.0 with attribution.

### 2.5a Known biases of the gates (measured 2026-11-18)

The gates keep what stays legible, so the accepted data under-represents the harshest degradation that was drawn. Read every result with that in mind.

| Set | Photocopy share drawn | Photocopy share accepted | Photocopy pass rate | All crops pass rate |
|---|---|---|---|---|
| O1 (train, all faces but Tinos) | 23.9% | 20.2% | 80.6% (24,948 / 30,953) | 95.2% (123,486 / 129,716) |
| degraded anchor (line rasters) | 27.8% | 18.4% | 57.6% (6,579 / 11,413) | 87.4% (35,848 / 41,000) |
| office_val (Tinos only) | 25.6% | 19.1% | 68.4% (20,514 / 29,990) | 91.4% (107,222 / 117,293) |

- **Photocopy is under-represented** against what was drawn: about 20% of O1 against 25% planned, and 18% of the degraded anchor. The lost lines are the thinned and doubly darkened copies, so arm A sees fewer of the heaviest copier artefacts than PLAN §5.2 intended.
- **Tinos (held out) loses more:** its thin serif strokes fail the photocopy gates more often, at 68.4% against 80.6% for the training faces. So office_val is somewhat cleaner than a draw of the same degradation on the training faces would be. Selection on office_val may therefore favour checkpoints that read cleaner copies.
- **The stock-fails rule is not a bias toward stock:** it rejects only when the clean render reads well and the similarity has dropped (§2.2). Stock's own misreads of legible numbers stay in.

### 2.6 Manifests (filled 2026-11-18 13:45)

- **Where:** everything is under `tasks/office-print-v0/` on the training machine; `lists_v1/manifest.json` holds the counts, seeds and sha256s below.
- **Format:** list entries are `.lstmf` paths, converted by R8b's `make_lstmf.py`, with labels in Tesseract's visual order. The logical labels stay beside each crop.

| List | Lines | sha256 |
|---|---|---|
| O1 accepted, all: `gen_v2/train/gates.jsonl` (accepted rows) | 123,486 of 129,716 | `d4afb0741c812d4d93da0b498fec93559a7ca0e76c7a8585c9f4425770e396ce` (gates file) |
| O1 sample: `lists_v1/o1.list` | 120,000 | `43349d75de16f9dbb9c6b07dce64c58266f791043481045b5ca500a27351a6e2` |
| degraded anchor: `anchor_deg_v2/manifest.jsonl` / `lists_v1/anchor_deg.list` | 35,848 of 41,000 accepted / first 35,000 | `58afe68ee128d1296453e349eb027f2fe6587882ef35a72d5e618c5be981bba7` / `95d4025619fba90efc5ecfa843d784319bb3d84415b0c2a62506a97ce311eb84` |
| anchor (clean3 lstmf of `pool_train.jsonl`) | 45,980 | within the arm lists; clean3 list `5ba5d5f291ad3bac505fd98088d0bdf11e3ccaa4c105aac34b70e7f8864b99e5` |
| OLB sample (arm A) | 60,000 | within `arm_a.list`; source `59b5d2d8…f869` |
| **arm A list: `lists_v1/arm_a.list`** | **260,980** | **`1b8171958bcf46a8642193e0941ad78ccf954768438dab1b88c5d85088f5b7e9`** |
| **arm B list, iteration order: `lists_v1/arm_b.list`** | **260,980** (all 182,883 real lines once, then 78,097 of a second shuffle) | **`e55ee2aa809be81706a2a980b429ec76e08ec46786ecc5e8194d0f15dd74fefe`** |
| office_val selection: `lists_v1/office_val_sel.list` | 5,000 | `1c3efe44f8f2265a0ffdb883f02ea98ae5dc632ce7fed0d60037d90d3533f426` |
| office_val gates: `gen_v2/office_val/gates.jsonl` | 107,222 of 117,293 accepted | `5148f558c8694122ba7a753f0f70ce33d56e8ee9b1bdaf59af3e4c28ee51416e` |

- **Iterations:** both arms train for 260,980 iterations, one pass over each list in its order.
- **Next:** these two lists go to eval for the official CLEAN (§5.2).

## 3. Arms

Both continue from **stock tessdata_best heb** (sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5`), with stock's unicharset and no layer surgery (PLAN §8.3).

| | Arm A | Arm B |
|---|---|---|
| Training lines | O1 + anchor + degraded anchor + OLB sample (about 261,000) | anchor + OLB train, real only |
| Order | one seeded shuffle (seed 20261122) of the whole list | real lines recycled: the anchor and all 136,903 OLB train lines in a seeded shuffle (seed 20261123), repeated with a fresh shuffle until the list holds as many lines as A's. No line repeats before every line has been used once |
| Iterations | one epoch of A's list (= its line count) | **the same number as A** |
| Recipe | lr 1e-4, a snapshot every 20 minutes; otherwise the R-series / S17a lstmtraining recipe (`--continue_from` stock, `--old_traineddata` stock) | identical |

- A against B measures what the synthetic part adds at equal compute.
- **Compute:** only through `tasks/power-scheduler`, on AC power, at most 2 heavy jobs. No arm starts until the lead relays that eval's registered gate run is done.

## 4. Decision rule

### 4.1 Checkpoint selection, office_val only

- **Set:** a fixed seeded sample (seed 20261124) of **5,000 gate-accepted office_val crops** (Tinos only, held-out units, the held-out table schema included).
- **Score:** line_fold_v1 CER, using `score_lines.py`, never lstmeval BCER.
- **Choice:** the lowest-CER snapshot of each arm is that arm's model. Ties go to the earlier snapshot.
- **Nothing else selects:** no D-bench cell, guard list or real dev set enters selection.

### 4.2 Arm decision, at document level

- **Sets:** D-bench synthetic B and C (eval's sets for selection), scored with eval's D-bench scorer (`gate.doc_units` / `report.py --synth`, line_fold_v1), with each arm's selected model in heocr's OCR route.
- **Qualifies for eval's amendment run:** an arm qualifies if, **at heocr 57e58de**, `gate.py`'s rule (paired bootstrap over documents, 10,000 resamples, seed 0, frozen margins) holds on all three cells (T5, T4, tables) against every baseline's recorded outputs.
- **Progress:** if neither arm qualifies, an arm still counts as progress when, at 57e58de:
  - its number recall beats heocr with stock inside on at least one cell (paired bootstrap lower bound above 0);
  - and no gate measure gets worse beyond its margin in any cell.

  Progress is reported, not sent to the gate.
- **A against B:** reported on the same cells at 57e58de, using the same bootstrap.
- **At 7f5e99e and at main:** the same tables, shown for information.

### 4.3 Guards, at line level on real print

- **Rule:** neither arm may lose against stock on any R-series dev list below.
- **Scoring:** both models read every line of the list (psm 7). Each is scored with `score_lines.py` under line_fold_v1. The list's CER is total edits over total reference characters, in percentage points.
- **Δ:** CER(arm) − CER(stock), on the same lines.
- **Interval:** a paired bootstrap over the list's lines, 10,000 resamples, seed 0, with both models' edits and reference lengths drawn together. The **upper bound** is the 97.5th percentile of Δ.
- **Guard loss: the upper bound is above +0.5 pt**, the gate's CER margin. The test is non-inferiority, in the same form as `gate.py`: the arm must show it is no more than 0.5 pt worse than stock on that list.
  - This is stricter than PLAN §2.3's "whole interval above 0" (lead, 2026-11-18). An arm whose interval is too wide to rule out a 0.5 pt loss also fails.
- **Effect:** a guard loss on any one list bars the arm from qualifying, whatever its document-level figures. Every list's Δ and interval are reported.

| List (`eval-domains/intermediates/r8b_score/lists`) | Lines | sha256 (prefix) |
|---|---|---|
| `olb_dev.list` | 3,254 | `4097a35c326786ad` |
| `olb_dev_v1_1.list` | 3,325 | `8e653dbc61c42532` |
| `reshumot_dev.list` | 2,716 | `7fb14f3c3019613f` |
| `kevarpirezikhron00haco.heldout.list` | 4,600 | `c175e7eb746d1a82` |
| `yediothateva06bernuoft.heldout.list` | 4,600 | `04401e9c4662cc2b` |
| `brainin_v3.list` | 6,257 | `23cc1db9deef9a00` |
| `brainin_nli.list` | 4,046 | `681214e9611f88b5` |
| `silman.list` | 3,046 | `68d10b15d1bad840` |
| `rab_dev.list` | 3,141 | `bd7793cd9235c8be` |
| `ws_dev.list` | 257 | `197547c00863300e` |
| `bodek.list` | 21 | `ccb4141a860f180a` |
| `sel.list` | 3,000 | `e0d3f2981109ba7d` |

### 4.4 Not used for anything

The print-and-scan pack PS-v1 (report-only at eval), the mid-century test set, the P-mod eval set, and every D-bench test document.

## 5. Preconditions, in order

1. Gates run on O1 and the degraded anchor; §2.6 is filled; the lead merges this PR.
2. **eval's official `check_train_overlap` passes on arm A's and arm B's final lists.** I send eval each list's path and sha256; a list counts as CLEAN only on eval's own run.
3. The lead relays that eval's registered gate run is done.
4. The arms are queued in the power scheduler, A first, then B.

## 6. Reporting

- **Columns:** every table shows stock tessdata_best, heocr with stock inside, arm A and arm B, at each of the three heocr commits.
- **Dashes:** the count of reference `–` in each scored set is given (PLAN §8.3).
- **Gate counts:** reported per rule, per degradation model and per number shape.
- **Release:** if an arm qualifies, release follows the open-release rule:
  - Apache-2.0 weights;
  - CC0 synthetic data and recipe;
  - the decision-0016 Wikisource credit in the NOTICE and card (§2.5).

## Amendment 1 (2026-11-18, before any arm started): arm lists rebuilt with real paths

- **What was wrong:** in the lists of §2.6, the 45,980 anchor lines and the 60,000 OLB lines named `.lstmf` files that do not exist. So did OLB's `train_list.txt`, which holds relative `.png` paths.
- **No data changed:**
  - same lines, same seeds, same order rules;
  - only the paths of the real parts and the two list hashes change.
- **The key lists are not training inputs.** clean3, the OLB lists and the R-series dev lists name s16c `.lstmf` paths only as keys. Tools read the `.png` or `.gt.txt` beside each key, and every run builds its own `.lstmf`.
- **Fresh conversion:**
  - all 45,980 anchor lines and all 136,903 OLB train lines, from their `.png` and logical `.gt.txt`;
  - into `tasks/office-print-v0/lists_v1/lstmf_real/`;
  - with the same `r8b-tesseract/scripts/make_lstmf.py` used for O1 and the degraded anchor (sha256 `540116b891b7b43ffa961c2a409f1ec56b13b6adc8a67fc329ad843075cbce88`; `tasks/` is not a git repository) and tesseract 5.5.3;
  - 182,883 of 182,883 converted.
- **Label check, every line:** each `.gt.txt` against its manifest text. **0 mismatches** in 45,980 anchor lines and 0 in 136,903 OLB train lines; no label is missing.
- **Guard:** `build_lists.py` now asserts that every path in every list exists.

- **Dash fold (amendment 1b, lead 2026-11-18):** ― (U+2015), – (U+2013) and — (U+2014) are written `-` in every *training* label.
  - **Count:** 5,684 lines were folded and reconverted: 2,434 anchor, 1,860 degraded anchor and 1,390 O1. OLB train labels hold none of the three.
  - **Why:** without the fold, stock's unicharset skipped those lines, mostly Hebrew year ranges like התשס"ה―2005, and at different rates in A and B.
  - **Scoring is unchanged:** `line_fold_v1` folds none of ― or – to `-` (— goes to –). As PLAN §8.3 says for –, a reference ― or – costs one substitution for every model, since stock's unicharset can output neither, so the comparison with stock is unaffected. A dash-folding profile would be eval's decision after the gate.
  - **Not folded:** the office_val selection keeps its reference labels.
- **How:** `fold_dashes.py` replaced each staged label with its folded copy; the source label files are untouched. The superseded `.lstmf` files were moved to `lists_v1/superseded_unfolded/`.
- **Labels hash:** the lists hold paths, so the folded labels are pinned by a second hash, the sha256 over each line's `.gt.txt` bytes in list order.

| List | Lines | list sha256 (replaces §2.6) | labels sha256 |
|---|---|---|---|
| **arm A: `lists_v1/arm_a.list`** | 260,980 | **`4bc44c7ddd2707c8967db94541faedb73625eb78648bf1866c3a1dccc53d53c9`** | **`accfe4bcb91620f73f899cd19d48834d0c1c545dc751f2990d91882944bc6c67`** |
| **arm B: `lists_v1/arm_b.list`** | 260,980 (182,883 real lines once, then 78,097 of a second shuffle) | **`c6aa4799c8a286365288242e86017167fc52f5f13fd4ecdfebef8a5394ef9332`** | **`9443d0b8e66d81a12d0255ac7d2ef88955ad4f5f32831cfef4fdc600083f4485`** |
| O1 / degraded anchor / office_val selection | unchanged | unchanged (§2.6) | `ea0f451c…eac4a` / `32b3e683…ffb2f` / `f80a5f0d…7ee40` |

- **Labels stock's unicharset still cannot encode, after the fold:** arm A 1,353 distinct lines (**0.52%**), arm B 493 (**0.27%**). They hold Latin letters, `□` and `”`, and lstmtraining skips them. Both arms keep `--max_iterations` 260,980.
- **Reference ― / – / — per scored set** (aggregate counts; report per PLAN §8.3):

| Set | Lines or docs | ― | – | — |
|---|---|---|---|---|
| D-bench T5 (B, C) | 82 docs | 1 | 121 | 3 |
| D-bench T4 (B) | 40 docs | 0 | 77 | 2 |
| D-bench tables (C) | 120 docs | 0 | 6 | 0 |
| office_val selection | 5,000 | 86 | 0 | 0 |
| `kevarpirezikhron00haco.heldout` | 4,600 | 0 | 696 | 0 |
| `silman` | 3,046 | 0 | 526 | 0 |
| `brainin_v3` | 6,257 | 0 | 450 | 78 |
| `sel` | 3,000 | 0 | 395 | 4 |
| `yediothateva06bernuoft.heldout` | 4,600 | 0 | 362 | 7 |
| `brainin_nli` | 4,046 | 0 | 216 | 0 |
| `reshumot_dev` | 2,716 | 0 | 64 | 0 |
| `olb_dev`, `olb_dev_v1_1`, `rab_dev`, `ws_dev`, `bodek` | — | 0 | 0 | 0 |

- **eval's CLEAN** (§5.2) runs on these two lists, checked by both their list and labels hashes.


## Amendment 2 (2026-11-18, before any arm started): decontaminated lists, lists_v2

- **Why:** eval's official CLEAN (check_train_overlap, §5.2) on the amendment 1 lists found hits. Both arms were **NOT CLEAN**:
  - arm A: 4,624 lines (1.8%);
  - arm B: 2,265 unique paths (3,231 list lines, 1.2%).
  - The ruling (lead) was to drop them, not justify them.
- **Hits by target** (aggregate counts only):
  - dbench_text_pool;
  - pmod_eval_pages, arm A only;
  - pmod_holdout_plenary;
  - midcentury_test_pages;
  - wave1, arm A only;
  - vendor_midcentury;
  - a few PS-v1 lines, R-series dev lines and OLB dev lines.

### Where the text came from

1. **`pool_v1` (§2.1):** the reshumotlines_v2 clean3 pool behind O1, the anchor and the degraded anchor.
   - **Hits:** 730 of 45,980 lines.
   - **By target:** dbench_text_pool 566, pmod_holdout_plenary 171, vendor_midcentury 8, PS-v1 6.
   - **Cause:** `build_pool.py` dropped lines on eval's reservations, the hash fixtures and the S17a pools, but never checked them against the official CLEAN targets.
2. **Page assembly (§2.2):** O1's hits on pmod_eval_pages (1,698) and wave1 (541) came from no single pool line.
   - Pool lines hit those two targets 0 times.
   - Joining and re-wrapping pool lines into cells makes new word 6-grams across line boundaries.
   - So a clean pool alone does not give clean crops.
3. **OLB train (§2.5):** 1,535 of 136,903 lines hit.
   - **By target:** vendor_midcentury 755, midcentury_test_pages 691, dbench_text_pool 660, pmod_holdout_plenary 359, PS-v1 8, OLB dev 2.

### Fix upstream, so future builds come out clean on their own

`tasks/` is not a git repository, so each script's sha256 is given.

| Script | sha256 | Change |
|---|---|---|
| `official_targets.py` | `a7c4b6c3…e9d53` | New. Wraps `check_train_overlap.targets()`: every target eval's CLEAN holds, restricted ones included. Counts only, never text. |
| `build_pool.py` | `5d741b17…a85cb9` | Drops a pool line that shares a word 6-gram with any official target. |
| `office_gates.py` | `b03bba24…f3e2ac` | Rejects a crop whose own text hits a target. This covers the cross-line 6-grams. |
| `build_lists.py` | `401837a1…18fe6` | `stage_real` drops OLB lines that hit; `lists_v2` is the rebuild below. |

### The rebuild: `lists_v2`

Nothing is regenerated and no `.lstmf` file changes; only the lists change.

1. **Drop:** every path in eval's drop file goes.
   - File: `eval-domains/intermediates/clean_office_print_v0/drop_paths.txt`, 5,507 paths, sha256 `597a7403a38fe7a051e062c3a8ae9975723725b16323727db3cffb112bd21b77`.
   - Per part: O1 2,683, anchor 730, degraded anchor 559, OLB 1,535.
   - Our own `decontam.py` on the amendment 1 lists gives the same 5,507 paths, with 0 differences.
2. **Trim rule:**
   - Arm A keeps its registered source mix. Every part is scaled by one factor, s = min over O1, anchor and degraded anchor of (clean lines / registered lines) = **0.977642**. O1 is the scarcest part.
   - Each part gets n = floor(registered × s) lines, drawn by a seeded sample (20261125). A part with exactly n clean lines keeps them all.
   - OLB has spare clean lines. It keeps its own sample seed, 20261121.
3. **Order:**
   - Arm A is shuffled with its registered seed, 20261122.
   - Arm B is all clean real lines (anchor + OLB), recycled with seeds 20261123 + cycle until it reaches len(A), as registered.
   - So the arms are equal in length, and the A/B still tests one variable.

| Part | Registered | Dropped | Clean | Arm A, lists_v2 | Share of A (registered → v2) |
|---|---|---|---|---|---|
| O1 | 120,000 | 2,683 | 117,317 | 117,317 | 0.4598 → 0.4598 |
| anchor | 45,980 | 730 | 45,250 | 44,951 | 0.1762 → 0.1762 |
| degraded anchor | 35,000 | 559 | 34,441 | 34,217 | 0.1341 → 0.1341 |
| OLB | 60,000 (sample of 136,903) | 1,535 of 136,903 | 135,368 | 58,658 | 0.2299 → 0.2299 |
| **arm A** | 260,980 | | | **255,143** | |
| **arm B** | 260,980 | | 45,250 anchor + 135,368 OLB = 180,618 | **255,143** (180,618 once, then 74,525 of a second shuffle) | |

| List | Lines | list sha256 (replaces amendment 1) | labels sha256 |
|---|---|---|---|
| **arm A: `lists_v2/arm_a.list`** | 255,143 | **`79c92cf2f92e763d1febd3a9e1778fe4a342053a25eab3f6a7e1acaaa67006c5`** | **`27dd590ea0d55f9ed7392f512cbd475b5442386e604332ae75db8427d674a298`** |
| **arm B: `lists_v2/arm_b.list`** | 255,143 | **`911443afb3035a7c5cff25865a37eaef655bd4e1f8d579eac6f628a3fb19100f`** | **`5d52e889d38362d31ffc2abf98892d1e837c70981349d1d604e83c54b86df3d2`** |

- **Iterations:** both arms train for **255,143** iterations, one pass over arm A's list (replaces 260,980 in §3).
- **Self-check:** `decontam.py` on both lists_v2 lists finds **0** hitting lines.
- **eval's official CLEAN (§5.2), 2026-11-18, unit office_clean_v2b:** **CLEAN**, 0 hits on every target, for arm A (`79c92cf2…`), arm B (`911443af…`) and the office_val selection (`d77a7fa7…`).
- **Labels stock's unicharset cannot encode,** which lstmtraining skips:
  - arm A: 1,352 lines (**0.53%**);
  - arm B: 501 distinct lines, 694 list lines (**0.27%**).
- **office_val selection, decontaminated (lead ruling):** selecting snapshots on text that overlaps the test targets is a soft leak, so hitting crops are dropped from the selection set too.
  - **Rule:** the same as the arms. A crop goes when its text shares a word 6-gram with an official CLEAN target (`decontam.py`). Order is kept.
  - **Hits:** 149 of 5,000 crops. pool_val itself has only 54 hitting lines; the rest are the cross-line 6-grams described above.
  - **By target:** pmod_eval_pages 82, dbench_text_pool 59, midcentury_test_pages 49, vendor_midcentury 31, wave1 22, pmod_holdout_plenary 14.

| Selection set | Lines | list sha256 | labels sha256 |
|---|---|---|---|
| amendment 1: `lists_v1/office_val_sel.list` | 5,000 | `1c3efe44f8f2265a0ffdb883f02ea98ae5dc632ce7fed0d60037d90d3533f426` | `f80a5f0d…7ee40` |
| **amendment 2: `lists_v2/office_val_sel.list`** | **4,851** | **`d77a7fa79c398208bfabe51db4cd982190bcdd9233eed5bbad1d1cec8ea88e51`** | **`7b0432ee2a183729f7df21f7d609f00bd0800314c77b0504a14dff5e828a88d8`** |

  - **Self-check:** `decontam.py` finds 0 hitting lines in the new set. eval's CLEAN re-run covers it too.
  - The §4.1 selection rule is otherwise unchanged.

### Where the arms run (lead, 2026-11-18)

- **Machine:** one heocr-remote `cpu` pod (RunPod `cpu3c`, 32 vCPUs, 64 GB). Both arms run side by side on it, so they share the same hardware.
- **Threads:** pinned at `OMP_THREAD_LIMIT=4` per arm.
- **Tesseract:** 5.5.3, built on the pod from the upstream tag (commit `db0ec62f…`; the annotated tag object is `6951ffe1…`). Any other version is refused.
- **Before training:** the pod checks the starter sha256, both lists' sha256 and both labels sha256.
- **Input category:** the real lines (anchor, degraded anchor, OLB) are Reshumot, PD-IL; US status is not asserted. They go under the `pd_scans` open root.
- **Pulled back per arm:**
  - the 20-minute snapshots as `.traineddata`, because §4.1 selects on them;
  - the final model;
  - the training log and the BCER trace.
- The pod type and run id will be recorded in the result report.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
