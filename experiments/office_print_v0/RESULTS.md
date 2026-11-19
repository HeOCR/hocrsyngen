# Office-print v0, A/B v2: results

Written 2026-11-19, after training, the §4.1 checkpoint selection, eval's §4.2 document-level runs and the §4.3 guards. The registration is [REGISTRATION.md](REGISTRATION.md), with amendments 1 and 2. All figures are aggregates. `tasks/` is not a git repository, so scripts are pinned by sha256.

## Outcome

- **Both arms qualify for eval's amendment run (§4.2).**
  - At heocr 57e58de, each arm's selected model inside heocr's OCR route meets `gate.py`'s rule on all three cells (T4, T5, scanned tables), against every recorded baseline.
  - All 10 D-bench cells pass for both arms.
- **Both arms pass every guard (§4.3).** On all 12 R-series dev lists each is better than stock, with the whole interval below 0.
- **Arm A** (synthetic office lines plus real lines) **beats arm B** (real lines only, same compute) on every cell where a difference is resolved: T4, T5 (at main), scanned tables, T6 and T3.
  - At 57e58de, T5 is not resolved. Arm A crashed on one document there, which was then charged as empty (§3).
  - **This is the A-against-B question the round was registered to answer:** at equal compute, the synthetic office part adds to the real lines.
- **Not a public claim.**
  - office_val is drawn from the training distribution (lead, 2026-11-19).
  - D-bench sets A, B and C are the open tuning sets heocr itself is developed against. They are not held out.
  - Any claim goes through eval's registered amendment run on held-out sets.

## 1. Training (§3, amendment 2)

| | |
|---|---|
| Run | heocr-remote `20261118-171942-dd68` |
| Pod | RunPod **`cpu3c` × 32 vCPUs** (pod `9bcjwzf9ar77hh`), $0.96/h; 3.49 h, **$3.39** |
| Inputs | manifest `inputs.json` sha256 `8f2bbd9a3e42061629c7e83f96517f3d64cf9d684a4d00c6e86deed58c6ec258`. The pod verified the starter (stock `dbaa827a…`), both lists_v2 lists and both labels sha256 before training |
| Pulled back | 33 files, all sha256 OK |

| Arm | Training lines | Iterations | Exit | Timed out | Snapshots | best_train | Training BCER |
|---|---|---|---|---|---|---|---|
| A | O1 + anchor + degraded anchor + OLB sample, 255,143 | 255,143 / 255,143 | 0 | no | 9 + best + final | `heb_0.582_29407_245100` | 0.58% |
| B | anchor + OLB, real only, 255,143 | 255,143 / 255,143 | 0 | no | 9 + best + final | `heb_0.030_5511_234100` | 0.03% |

- **Arm B's training BCER of 0.03% means nothing for selection.** B recycles 180,618 real lines, so it is partly scoring lines it has already seen. Selection uses office_val only (§4.1).

## 2. Checkpoint selection on office_val (§4.1)

- **Set:** `lists_v2/office_val_sel.list` (amendment 2: 4,851 crops, sha256 `d77a7fa7…`, eval CLEAN).
- **Scorer:** eval's `score_lines.py` under line_fold_v1 (`2e262710…`), every line, lines a model cannot output charged.
- **Script:** `tasks/office-print-v0/scripts/select_v2.py` (sha256 `1930ca5f67e2c59b…`), run as power-scheduler unit `office_ab_v2_select` after the gate.
- **Output:** `select_v2/selection.json` (`bb687c5359421b6c…`).
- **Rule:** lowest CER per arm; ties go to the earlier snapshot.

| Candidate | Iteration | A CER / WER | Candidate | Iteration | B CER / WER |
|---|---|---|---|---|---|
| snap_0020m | 28,600 | 2.660 / 11.03 | snap_0020m | 27,500 | 5.813 / 20.02 |
| snap_0040m | 56,700 | 2.388 / 9.47 | snap_0040m | 54,100 | 5.469 / 18.25 |
| snap_0060m | 85,000 | 2.201 / 8.43 | snap_0060m | 81,900 | 5.639 / 18.47 |
| snap_0080m | 112,400 | 1.866 / 7.06 | snap_0080m | 107,700 | 5.370 / 17.77 |
| snap_0100m | 140,400 | 1.681 / 6.24 | snap_0100m | 134,800 | 5.410 / 17.74 |
| snap_0120m | 166,300 | 1.551 / 5.84 | **snap_0120m** | **160,300** | **5.074 / 17.43** |
| snap_0140m | 193,900 | 1.514 / 5.61 | snap_0140m | 186,400 | 5.163 / 17.57 |
| **snap_0160m** | **222,700** | **1.375 / 5.20** | snap_0160m | 212,500 | 5.246 / 18.06 |
| best_train | 245,100 | 1.425 / 5.25 | best_train | 234,100 | 5.386 / 17.90 |
| snap_0180m | 249,600 | 1.525 / 5.63 | snap_0180m | 238,500 | 5.184 / 17.97 |
| final | 255,143 | 1.382 / 5.20 | final | 255,143 | 5.260 / 16.89 |
| *stock tessdata_best heb* | | *14.754 / 40.05* | | | |

- **Selected:**
  - arm A: `snap_0160m_222700`, sha256 `6275943bf68f3d44ecc32f8d4c4195c890c96602111542ebe1f0ae0d8a6a5201`;
  - arm B: `snap_0120m_160300`, sha256 `be342946852af312b357dec18b73f24e40f6adfd2938b8ec9789e4e3d55aeedd`.
- **The two arms' gap on office_val is expected.** office_val is office layout in a held-out face (Tinos), rendered and degraded like O1, so arm A has seen its distribution and B has not. The selection set picks snapshots; it is not evidence for A over B. §3 and §4 are.
- **Reference dashes:** office_val held 86 reference ― (U+2015) in its 5,000-crop form (amendment 1), and somewhat fewer after decontamination to 4,851. No stock-unicharset model can output ―, so every candidate pays the same substitution for each one.

## 3. Arm decision at document level (§4.2, run by eval)

- **Who and how:** eval ran it as power-scheduler unit `office42`. Each selected model sat inside heocr's OCR route (`extract(ocr_model=…)`) on D-bench synthetic sets A, B and C (951 items, every file checked against its committed manifest).
- **Commits:** heocr **57e58de** (the qualifying commit), 7f5e99e and main **72726af** (for information).
- **Baselines:** the recorded `dry-b88-synth` outputs.
- **Scope:** synthetic only. No dev or test item was read.
- **Aggregates:** `tasks/eval-domains/intermediates/office42/office42_agg.json`. The record is restricted-eval#70.

### 3.1 The gate rule

| heocr commit | Arm A | Arm B |
|---|---|---|
| **57e58de** (qualifying) | **meets the rule on T4, T5 and scanned tables; all 10 cells pass** | **meets the rule on T4, T5 and scanned tables; all 10 cells pass** |
| 7f5e99e (info) | T4 and T5 pass. Scanned tables fail on number misses against docling (upper bound 1.215 > 1.0); T6 fails | T4 and T5 pass. Scanned tables fail on number misses against docling (6.449 > 1.0); T6 fails |
| 72726af, main (info) | meets the rule on T4, T5 and scanned tables | meets the rule on T4, T5 and scanned tables |

7f5e99e's failures most likely belong to that commit, not to the arms: both arms fail there in the same cells, and both pass at 57e58de and at main. heocr default was not re-run at 7f5e99e here.

### 3.2 Per cell

CER % with number misses % in brackets; larger is worse. The interval is a 95% bootstrap over documents. "heocr default" is heocr at 57e58de with stock tessdata_best heb inside.

| Cell (documents) | Arm A @57e58de | Arm B @57e58de | Arm A @72726af | heocr default @57e58de | stock tessdata_best |
|---|---|---|---|---|---|
| T4 (40) | **1.04** [0.93, 1.15] (4.56) | 1.71 [1.50, 1.95] (7.06) | 1.04 (4.56) | 2.88 (20.16) | 9.07 (54.26) |
| T5 (82) | 3.36 [2.05, 5.13] (5.17) | **3.08** [2.36, 4.04] (5.42) | **2.75** [1.99, 3.73] (3.96) | 4.24 (13.28) | 11.49 (57.97) |
| Scanned tables (120) | **0.42** [0.35, 0.49] (0.55) | 1.25 [1.12, 1.39] (1.08) | 0.42 (0.55) | 1.58 (2.59) | 54.46 (85.85) |
| T6 (40) | **0.049** (0.056) | 0.089 (0.083) | 0.049 | 0.118 (0.222) | 96.16 (95.02) |
| T3 (151) | **0.077** (0.015) | 0.080 (0.015) | 0.077 | 0.109 (0.096) | 10.23 (55.05) |
| T1 (318) | 0.006 (0.003) | 0.006 (0.003) | 0.006 | 0.006 (0.003) | 9.76 (54.58) |

- **Scanned tables, rows not read:** A 0.58%, B 1.29%, heocr default 4.33%, stock 96.32%.
- **Arm B at 72726af** is identical to 57e58de in every cell.
- **The arms beat heocr with stock inside in every image cell,** on both CER and number misses. In T4, number misses fall from 20.2% to 4.6% (A).
- **T1 and T3 hardly depend on the model;** they come from the text layer.

### 3.3 A against B

Δ = A − B, a paired bootstrap over documents, with the same resamples, seed and rule as `gate.py`. The upper bound is the 97.5th percentile.

| Cell | Measure | Δ @57e58de (upper bound) | Δ @72726af (upper bound) |
|---|---|---|---|
| T4 | CER | −0.677 (−0.464) | the same |
| T4 | number misses | −2.503 (−1.398) | the same |
| T5 | CER | +0.280 (+1.642) | **−0.323 (−0.175)** |
| T5 | number misses | −0.249 (+2.603) | **−1.457 (−0.889)** |
| Scanned tables | CER | −0.834 (−0.703) | the same |
| Scanned tables | number misses | −0.529 (−0.238) | the same |
| Scanned tables | rows not read | −0.711 (−0.125) | the same |
| T6 | CER | −0.040 (−0.028) | the same |
| T3 | CER | −0.003 (−0.001) | the same |
| T1 | CER, number misses | 0 | 0 |

- **A is better than B wherever the interval excludes 0.**
- **The one unresolved cell, T5 at 57e58de, is a crash, not the model.**
  - At 57e58de and 7f5e99e, arm A hit heocr's path-guard `ContractError` on one T5 document (C/pdf_t5_office_numbers, number-dense office scan). gate.py charged it as empty.
  - Main 72726af carries the path-guard fix. There A reads it, and A beats B on T5 too.
  - Arm B never crashed.

## 4. Guards: real print, line level (§4.3)

- **Rule:** every line of each list read through eval's `score_lines.py` under line_fold_v1.
- **Δ** = CER(arm) − CER(stock tessdata_best heb) on the same lines.
- **Interval:** paired bootstrap over lines, 10,000 resamples, numpy `default_rng(0)`, with edits and reference lengths drawn together, shown at 95%.
- **Guard loss:** upper bound above +0.5 pt.
- **Script:** `tasks/r-series-guards/guards.py` (sha256 `9a8fa7d5bfacdc7c…`), run as unit `rseries_guards_v1` together with P-hist v1's §5.3. Output: `r-series-guards/office_ab_v2_guards.json` (`eaa743e4b26636bf…`).

| List | Lines | Stock | **A** | Δ A [95% CI] | **B** | Δ B [95% CI] |
|---|---|---|---|---|---|---|
| olb_dev | 3,254 | 5.428 | 1.902 | −3.527 [−3.637, −3.421] | 1.874 | −3.554 [−3.663, −3.449] |
| olb_dev_v1_1 | 3,325 | 5.410 | 1.905 | −3.505 [−3.612, −3.397] | 1.885 | −3.524 [−3.631, −3.417] |
| reshumot_dev | 2,716 | 6.613 | 0.866 | −5.747 [−6.252, −5.304] | 0.880 | −5.733 [−6.247, −5.288] |
| kevarpirezikhron00haco.heldout | 4,600 | 5.677 | 1.054 | −4.623 [−4.733, −4.520] | 1.081 | −4.596 [−4.686, −4.508] |
| yediothateva06bernuoft.heldout | 4,600 | 9.218 | 3.849 | −5.369 [−5.495, −5.248] | 4.103 | −5.116 [−5.228, −5.004] |
| brainin_v3 | 6,257 | 5.071 | 1.514 | −3.557 [−3.624, −3.489] | 1.866 | −3.205 [−3.268, −3.143] |
| brainin_nli | 4,046 | 10.450 | 4.224 | −6.226 [−6.384, −6.070] | 4.294 | −6.156 [−6.304, −6.005] |
| silman | 3,046 | 5.824 | 1.728 | −4.096 [−4.214, −3.983] | 1.479 | −4.345 [−4.457, −4.236] |
| rab_dev | 3,141 | 7.512 | 2.895 | −4.617 [−4.715, −4.520] | 2.792 | −4.720 [−4.810, −4.629] |
| ws_dev | 257 | 14.672 | 8.812 | −5.860 [−6.300, −5.439] | 8.854 | −5.818 [−6.195, −5.456] |
| bodek | 21 | 15.684 | 8.311 | −7.373 [−10.077, −4.750] | 8.311 | −7.373 [−10.104, −5.060] |
| sel | 3,000 | 7.549 | 2.520 | −5.029 [−5.181, −4.885] | 2.618 | −4.931 [−5.063, −4.802] |

- **No guard loss for either arm.**
- **On real print the arms are close.** Neither is better on every list: A is ahead on brainin_v3, yediothateva and sel; B on silman and rab_dev. The synthetic office part costs nothing on real print, and its gain shows on office documents (§3).
- **The guard lists' reference dash counts** are in amendment 1.

## 5. Next

- **Eval's amendment run:** both arms qualify (§4.2). Which arm, if any, enters is eval's and the lead's call. On every resolved comparison here, A is the stronger candidate.
- **Default-model study:** the office-print winner is a candidate for heocr's default model beside P-hist v1's model. That study selects on dev, then claims on held-out sets in its registered run.
- **Release:** none from this report. A release follows the open-release rule: Apache-2.0 weights, CC0 synthetic data and recipe, the decision-0016 Wikisource credit, and stock beside it on every card.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
