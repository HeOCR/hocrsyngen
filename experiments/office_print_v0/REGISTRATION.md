# Office-print v0: arm registration

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

- **What:** 35,000 lines, a seeded sample (seed 20261120) of the anchor.
- **How:** each line raster goes through one of the §5.2 photometric models, `office_scan`, `photocopy` or `phone_photo` at 50:25:15 renormalised, from hocrsyngen `749069d`, with a seeded per-line skew of up to ±1° and the line's rectified crop. Double thickening is not used (lead, 2026-11-18).
- **Plan change:** line rasters replace PLAN §6's page rasters. The born-digital page geometry is not kept beside the lines, so a page-level homography has nothing to act on.
- **Gates:** the same gates as O1, with the undegraded line as the clean render.
- **Labels:** the anchor's own labels, unchanged.

### 2.5 Real scans: OLB Reshumot train

- **What:** a seeded sample (seed 20261121) of **60,000** lines from `olbreshumotlines_v1/train_list.txt`.
- **Source list:** 136,903 lines, sha256 `59b5d2d8c9bcea6c355709300a8be26b39aed3fa09cbd13445118497ef16f869`. eval's reservations hold none of its units.

### 2.6 Manifests (filled after the gates)

| List | Lines | sha256 |
|---|---|---|
| O1 accepted (all) | — | — |
| O1 sample | — | — |
| degraded anchor (accepted) | — | — |
| arm A list | — | — |
| arm B list, iteration order | — | — |
| office_val selection sample | — | — |

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

- **Rule:** neither arm may lose against stock on any R-series dev list.
- **Loss:** the whole 95% paired-bootstrap interval of CER(arm) − CER(stock) lies above 0, scored with `score_lines.py` under line_fold_v1.
- **Effect:** a guard loss bars the arm from qualifying, whatever its document-level figures.

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
- **Release:** if an arm qualifies, release follows the open-release rule (Apache-2.0 weights, CC0 synthetic data and recipe).

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
