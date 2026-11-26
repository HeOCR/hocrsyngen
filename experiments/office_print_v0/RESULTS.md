# Office-print v0, A/B v2: results

> Historical development record.

Written 2026-11-19, after training, the §4.1 checkpoint selection, eval's §4.2 document-level runs and the §4.3 guards. The registration is [REGISTRATION.md](REGISTRATION.md), with amendments 1 and 2. `tasks/` is not a git repository, so scripts are pinned by sha256.

## Outcome

The checks informed checkpoint and arm selection. Public results use [registered held-out sets of real documents](https://heocr.org/en/benchmarks.html).

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

## 3. Arm decision at document level (§4.2, run by eval)

The arms were also compared on HeOCR's synthetic document sets for selection; no synthetic-set figure is reported (Shay, 2026-11-20).

## 4. Guards

The line-level guards used development lists of real print. Their measurements remain in the development record.

## 5. Next

- **Eval's amendment run:** which arm, if any, enters was eval's and the lead's call.
- **Default-model study:** the office-print winner is a candidate for heocr's default model beside P-hist v1's model. That study selects on dev, then claims on held-out sets in its registered run.
- **Release:** none from this report. A release follows the open-release rule: Apache-2.0 weights, CC0 synthetic data and recipe, the decision-0016 Wikisource credit, and stock beside it on every card.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
