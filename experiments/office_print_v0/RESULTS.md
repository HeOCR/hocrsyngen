# Office-print v0, A/B v2: results

> Development / selection evidence; not a performance claim. Held-out results: https://heocr.github.io/benchmarks.html

Written 2026-11-19, after training, the §4.1 checkpoint selection, eval's §4.2 document-level runs and the §4.3 guards. The registration is [REGISTRATION.md](REGISTRATION.md), with amendments 1 and 2. All figures are aggregates. `tasks/` is not a git repository, so scripts are pinned by sha256.

## Outcome

- **Both arms pass every guard (§4.3).** On all 12 R-series dev lists of real print, each is better than stock, with the whole interval below 0.
- **Synthetic sets:** the arms were also compared on HeOCR's synthetic document sets for selection; no synthetic-set figure is reported (Shay, 2026-11-20).
- **Not a public claim.** These are development and selection records. Any claim goes through a registered held-out run on real sets.

## 1. Training (§3, amendment 2)

| | |
|---|---|
| Run | heocr-remote `20261118-171942-dd68` |
| Pod | RunPod **`cpu3c` × 32 vCPUs** (pod `9bcjwzf9ar77hh`), $0.96/h; 3.49 h, **$3.39** |
| Inputs | manifest `inputs.json` sha256 `8f2bbd9a3e42061629c7e83f96517f3d64cf9d684a4d00c6e86deed58c6ec258`. The pod verified the starter (stock `dbaa827a…`), both lists_v2 lists and both labels sha256 before training |
| Pulled back | 33 files, all sha256 OK |

| Arm | Training lines | Iterations | Exit | Timed out | Snapshots |
|---|---|---|---|---|---|
| A | O1 + anchor + degraded anchor + OLB sample, 255,143 | 255,143 / 255,143 | 0 | no | 9 + best + final |
| B | anchor + OLB, real only, 255,143 | 255,143 / 255,143 | 0 | no | 9 + best + final |


## 2. Checkpoint selection on office_val (§4.1)

- **Set:** `lists_v2/office_val_sel.list` (amendment 2: 4,851 crops, sha256 `d77a7fa7…`, eval CLEAN).
- **Scorer:** eval's `score_lines.py` under line_fold_v1 (`2e262710…`), every line, lines a model cannot output charged.
- **Script:** `tasks/office-print-v0/scripts/select_v2.py` (sha256 `1930ca5f67e2c59b…`), run as power-scheduler unit `office_ab_v2_select` after the gate.
- **Output:** `select_v2/selection.json` (`bb687c5359421b6c…`).
- **Rule:** lowest CER per arm; ties go to the earlier snapshot. office_val is synthetic (rendered crops), so its scores are not reported.

- **Selected:**
  - arm A: `snap_0160m_222700`, sha256 `6275943bf68f3d44ecc32f8d4c4195c890c96602111542ebe1f0ae0d8a6a5201`;
  - arm B: `snap_0120m_160300`, sha256 `be342946852af312b357dec18b73f24e40f6adfd2938b8ec9789e4e3d55aeedd`.
- **Reference dashes:** office_val held 86 reference ― (U+2015) in its 5,000-crop form (amendment 1), and somewhat fewer after decontamination to 4,851. No stock-unicharset model can output ―, so every candidate pays the same substitution for each one.

## 3. Arm decision at document level (§4.2, run by eval)

The arms were also compared on HeOCR's synthetic document sets for selection; no synthetic-set figure is reported (Shay, 2026-11-20).

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
- **On real print the arms are close.** Neither is better on every list: A is ahead on brainin_v3, yediothateva and sel; B on silman and rab_dev. On these real lists the synthetic office part costs nothing.
- **The guard lists' reference dash counts** are in amendment 1.

## 5. Next

- **Eval's amendment run:** which arm, if any, enters was eval's and the lead's call.
- **Default-model study:** the office-print winner is a candidate for heocr's default model beside P-hist v1's model. That study selects on dev, then claims on held-out sets in its registered run.
- **Release:** none from this report. A release follows the open-release rule: Apache-2.0 weights, CC0 synthetic data and recipe, the decision-0016 Wikisource credit, and stock beside it on every card.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
