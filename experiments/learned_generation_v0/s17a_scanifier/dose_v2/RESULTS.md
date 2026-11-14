# S17a dose arm: result

**Verdict under the pre-registered rule ([PREREGISTRATION.md](PREREGISTRATION.md), fixed at cafb637, de3d590 and fa82869 before training): the arm does not win.**
- There is no OLB win: the 95% interval of Δ on "all" includes 0.
- There is one guard loss: Silman, where the whole 95% interval of Δ is below 0.
- By the pre-registration, there is **no confirmation run**, and the S17a dose **stays at v1.1** (the 18,627 lines already inside the released r8b-main-fold).

Δ = CER(control) − CER(arm), in percent CER; positive means the arm is better. The profile is line_fold_v1 (`2e262710…d317`), and every line is charged.
- **Control:** released r8b-main-fold (`8cb22dbe…6117`).
- **Arm:** `s17a-dose2`, the R8b recipe on `train_main.list` plus 18,553 s17a_addon_v2 lines.
- **Stock:** tessdata_best `heb`. It is a CER column on the same lines only; it never enters an interval or the decision.

## Training and selection

- **Training:** one epoch (214,828 iterations) through power-scheduler, AC only, one job, 2026-11-13 15:12–18:04 IST. lstmtraining exited 0 with "Finished!".
- **Selection:** line_fold_v1 CER on `sel.list` over all 30 checkpoints and snapshots ([results/sel_scores.tsv](results/sel_scores.tsv)). The selected checkpoint is **heb_snap_173254**, with CER 0.865 / WER 3.933, a unique minimum.
- **Packed model:** `heb.traineddata` sha256 `75772e0abe148a3c6dac52a8aa6bf580db927640179499a18c5273b40c3e4ace`.
- **Script bug, fixed here:** `select_dose.sh` stopped silently right after scoring `sel.list`.
  - Cause: under `set -o pipefail`, `sort | head -1` returned SIGPIPE, and `set -e` exited.
  - The selection scores were already written. I replaced `head` with `awk` and resumed from the pack step (`SKIP_SEL=1`). The selection rule and its inputs are unchanged.

## Primary: OLB Reshumot dev v1_dev (unit clusters, 10,000 resamples, seed 0)

| view | lines / units | control | arm | Δ [95% CI] | stock |
|---|---|---|---|---|---|
| **all** (deciding) | 3254 / 55 | 2.129 | 2.110 | +0.019 [−0.037, +0.052] | 5.428 |
| excluded (no 6-gram with arm train) | 3243 / 55 | 2.139 | 2.118 | +0.021 [−0.037, +0.056] | 5.440 |
| exact | 2028 / 54 | 0.735 | 0.714 | +0.021 [−0.019, +0.049] | 3.965 |
| not_exact | 1226 / 44 | 4.021 | 4.005 | +0.016 [−0.098, +0.066] | 7.415 |
| all_cap60 | 1484 / 55 | 1.473 | 1.480 | −0.007 [−0.059, +0.042] | 4.987 |
| excluded_cap60 | 1480 / 55 | 1.479 | 1.481 | −0.002 [−0.054, +0.045] | 4.994 |

- "Exact" has the same sign as "all", so the result is not unresolved. It is simply no win.
- Under the cap-60 views the small gain disappears. It comes from a few large units.

## Guard: new-printed dev books (page clusters)

| book | lines / pages | control | arm | Δ [95% CI] | rule | stock |
|---|---|---|---|---|---|---|
| Kevar (held-out) | 4600 / 210 | 0.757 | 0.764 | −0.007 [−0.022, +0.008] | — | 5.664 |
| Yedi'ot ha-Teva (held-out) | 4600 / 298 | 1.019 | 1.000 | +0.019 [0.000, +0.039] | — | 9.168 |
| Brainin IA | 6257 / 191 | 0.743 | 0.714 | +0.029 [+0.017, +0.041] | — | 5.071 |
| Brainin NLI | 4046 / 145 | 1.073 | 1.064 | +0.009 [−0.014, +0.030] | — | 10.450 |
| **Silman** | 3046 / 132 | 0.869 | 0.915 | **−0.046 [−0.070, −0.023]** | **loss** | 5.824 |

## Secondary (lead 2026-11-13, not deciding): exposed dev lines removed

- **OLB:** 11 lines share a word 6-gram with the arm's training list. Those are the "excluded" rows above, and nothing changes.
- **Guard books:** only Brainin IA has exposed lines, 62 of them (the same 62 eval found). Without them, Δ is +0.028 [+0.017, +0.041]. Kevar, Yedi'ot, Brainin NLI and Silman have 0 exposed lines, so their rows are identical to the deciding ones. The Silman loss is not an exposure artefact.

## Report-only sets

| set | lines / clusters | control | arm | Δ [95% CI] | stock |
|---|---|---|---|---|---|
| Bodek | 21 / 12 | 5.094 | 5.094 | +0.000 [−0.818, +0.588] | 15.684 |
| reshumot dev (rendered) | 2716 / 2716 | 1.179 | 1.301 | −0.122 [−0.202, −0.052] | 6.613 |
| rab dev | 3141 / 173 | 1.056 | 1.084 | −0.028 [−0.042, −0.013] | 7.512 |
| ws dev | 257 / 257 | 6.932 | 7.022 | −0.090 [−0.203, +0.021] | 14.672 |

The extra S17a lines also cost on two report-only sets, the rendered reshumot dev and rab dev, both outside the arm's style. These don't decide anything. They point the same way as Silman.

## Training-list overlap (eval's official `check_train_overlap.py`, before training)

- **New part:** 0 hits among the 18,553 `s17a2_*` lines.
- **Inherited part:** 282 hits (midcentury 116, R-series lists 158, OLB 13). This is exactly the hit set of R8b `train_main.list` under the fixed checker. The released control trained on the same lines.
- **Pre-train check by `build_dose_list.py`** ([results/train_dose.list.json](results/train_dose.list.json)): 0 hits in every pool, against a Kevar positive control of 188 hits.

## Reported alongside

- **Gates** ([results/gates_summary.json](results/gates_summary.json)): 18,553 of 20,000 accepted.
  - Gate 1 rejected 1,433 (ink_outside 837, stray_cc 725, glyph_no_ink 636; a line can trip more than one).
  - Gate 2 rejected 15, 14 of them by gate 2 alone.
  - Per style book, acceptance is 89–96%.
- **Sheets:** gate 1 rejects real faults, such as a hyphen drawn as "=", extra "?" marks and stray dots. The gate-2-only rejects are mostly correct lines the reader got wrong, including empty reads on dark-grey styles. Nothing was unclear enough to go to Shay.
- **Digit bias** ([results/digits.json](results/digits.json)):

  | | lines with a digit | digits / 1k chars |
  |---|---|---|
  | v1.1 accepted | 4.13% | 3.35 |
  | v2 generated | 2.40% | 1.82 |
  | v2 accepted | 2.22% | 1.62 |

  - Most of the drop is in the texts, not in the gates.
  - Gate 2 rejects 0.83% of digit lines against 0.06% of other lines. The bias is real, but it is small in absolute terms (4 lines).
  - A later text draw would need to favour digit-rich works.

## What this means for R9

More of the same S17a data (same generator, same 870 style crops, more Ben-Yehuda text) does not help new-printed reading beyond v1.1. Its only clear gain is on Brainin IA, and it costs on Silman. R9 keeps v1.1 as its S17a dose. The dose-arm model and its checkpoints stay local and are not released.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
