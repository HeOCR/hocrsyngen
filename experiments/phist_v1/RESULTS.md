# P-hist round v1: results

Written 2026-11-19, after training, eval's audit2 selection (§5.1) and the modern-print guards (§5.3). The registration is [REGISTRATION.md](REGISTRATION.md). All figures are aggregates. `tasks/` is not a git repository, so scripts are pinned by sha256.

## Outcome

- **The round's model is arm r7's `heb_final`** (sha256 `f8090760b5b02d09cf4ddb435e7a5e34089f6f17cde9cfb6c67fd06c6f17ec02`). It has the lowest audit2 CER of the 20 candidates, 16.753%, against 20.261% for stock tessdata_best heb and 18.330% for R7, its start model.
- **The guard holds (§5.3):** on all 12 R-series dev lists it is better than stock, with the whole interval below 0. It does not lose modern print.
- **No test claim yet (§5.2).** The P-hist test has no references: they are a volunteer task that starts with Shay's volunteer launch. The lead ruled (2026-11-19) that no P-hist test claim is made before a registered run, and that run belongs to the default-model study after RC2. Until then the model card shows the dev figure only, next to stock.
- **audit2 is dev.** It chose the model, so its figures are optimistic for this model and are not a claim.

## 1. Training (§4)

| | |
|---|---|
| Run | heocr-remote `20261118-175353-bdbd` |
| Pod | RunPod **`cpu3c` × 16 vCPUs** (pod `nhdaotqvsb5h7f`), $0.48/h; total **$0.81** |
| Deviation | §4 registered a 32-vCPU `cpu3c` pod. None was available, so the run used the 16-vCPU fallback. Both arms still ran side by side on the same pod, at OMP_THREAD_LIMIT=4 each. The recipe and iterations are unchanged. |
| Inputs | manifest `inputs.json` sha256 `250de59de77f6fd1353d68f2ddb88b5a4858ed33855a536429d67f1993b8733e`; the pod verified the starter, both lists and both labels sha256 before training. `train_phist.sh` sha256 `b2115990…`, `stage_remote.py` `edf92d70…`, `v1/manifest.json` `fa8f370d…` |
| Pulled back | 32 files, all sha256 OK |

| Arm | Iterations | Exit | Timed out | Snapshots | best_train | Final train BCER |
|---|---|---|---|---|---|---|
| r7 | 76,946 / 76,946 | 0 | no | 8 | `heb_0.905_10296_47500` | 0.92% |
| stock | 76,946 / 76,946 | 0 | no | 8 | `heb_0.853_16353_74800` | 0.88% |

Training BCER selects nothing. The training data are as registered in §2: the per-book and per-set counts are in §2.1, the replay in §2.2 and the lists in §2.4.

## 2. Selection on audit2 (§5.1, amended)

- **Who and how:** eval scored the candidates. Each read the 38 audit2 page images (13 books, P-hist dev) with Tesseract `--psm 3` through heocr-engine's tesseract command.
- **Measure:** micro page CER under line_fold_v1 (`2e262710…`).
- **No failures:** 0 read failures and 0 empty pages for every model.
- **Cross-check (context only):** hocrgen `evaluate-references` primary.v1 at d4a3414, on the same pages.
- **Results file:** `tasks/eval-domains/intermediates/phist_v1_select/selection.json`.

| Arm | Candidate | Iteration | CER (selection) | primary.v1 (context) |
|---|---|---|---|---|
| r7 | snap_0010m | 9,400 | 17.196% | |
| r7 | snap_0020m | 19,800 | 17.074% | |
| r7 | snap_0030m | 30,500 | 17.092% | |
| r7 | snap_0040m | 40,400 | 17.520% | |
| r7 | snap_0050m | 48,900 | 16.861% | |
| r7 | snap_0060m | 57,700 | 17.480% | |
| r7 | snap_0070m | 65,100 | 16.847% | 19.488% |
| r7 | snap_0080m | 71,800 | 17.017% | |
| r7 | heb_best_train | 47,500 | 16.875% | |
| **r7** | **heb_final** | **76,946** | **16.753%** | **19.413%** |
| stock | snap_0010m | 8,900 | 17.764% | |
| stock | snap_0020m | 19,000 | 17.396% | |
| stock | snap_0030m | 29,000 | 17.206% | |
| stock | snap_0040m | 38,800 | 17.194% | |
| stock | snap_0050m | 48,600 | 16.960% | |
| stock | snap_0060m | 57,800 | 17.222% | |
| stock | snap_0070m | 65,400 | 16.920% | |
| stock | snap_0080m | 72,900 | 17.070% | |
| stock | heb_best_train | 74,800 | 16.924% | |
| stock | heb_final | 76,946 | 16.814% | 19.470% |
| *context* | stock tessdata_best heb (`dbaa827a`) | | *20.261%* | *22.457%* |
| *context* | R7 (`95faab81`) | | *18.330%* | *20.890%* |

- **The winner by the rule (lowest CER, ties earlier, then r7) is r7 `heb_final`.** The runner-up is stock-arm `heb_final` (+0.061 pt), then r7 snap_0070m (+0.094 pt).
- **primary.v1 gives the same top three in the same order.**
- **The two arms end within 0.06 pt of each other.** On audit2, starting from R7 rather than stock adds little once both have seen the round's data.
- **Snapshot spread:** the arms move by about ±0.4 pt between snapshots. The pick is a small margin over its neighbours, and audit2 (38 pages) cannot separate them reliably. The rule picks one anyway, as registered.

## 3. Guard: modern print (§5.3)

- **Rule:** office-print §4.3's. Every line of each list is read, and the output is scored with eval's `score_lines.py` (lstmeval on per-line index codes; lines a model cannot output are charged) under line_fold_v1.
- **Δ** = CER(model) − CER(stock) on the same lines, in points.
- **Interval:** paired bootstrap over lines, 10,000 resamples, numpy `default_rng(0)`, with edits and reference lengths drawn together. The interval shown is 95%.
- **Guard loss:** the upper bound is above +0.5 pt.
- **Script:** `tasks/r-series-guards/guards.py` (sha256 `9a8fa7d5bfacdc7c…`), run as power-scheduler unit `rseries_guards_v1`. Output: `r-series-guards/phist_v1_guards.json` (`6dafe12030f2c73c…`). `score_lines.py` sha256 `1b7e6fd8dc4710e9…`.
- **R7 is context;** it is not the subject of the guard.

| List | Lines | Stock | **heb_final** | Δ [95% CI] | R7 (context) | Δ R7 [95% CI] |
|---|---|---|---|---|---|---|
| olb_dev | 3,254 | 5.428 | **2.209** | −3.220 [−3.330, −3.112] | 2.934 | −2.494 [−2.613, −2.380] |
| olb_dev_v1_1 | 3,325 | 5.410 | **2.198** | −3.212 [−3.320, −3.104] | 2.924 | −2.486 [−2.601, −2.371] |
| reshumot_dev | 2,716 | 6.613 | **0.838** | −5.774 [−6.366, −5.264] | 7.789 | **+1.177 [+0.877, +1.471]** (would fail) |
| kevarpirezikhron00haco.heldout | 4,600 | 5.677 | **0.948** | −4.729 [−4.843, −4.622] | 0.850 | −4.827 [−4.937, −4.723] |
| yediothateva06bernuoft.heldout | 4,600 | 9.218 | **1.086** | −8.132 [−8.272, −7.998] | 1.333 | −7.885 [−8.022, −7.754] |
| brainin_v3 | 6,257 | 5.071 | **0.868** | −4.203 [−4.276, −4.130] | 0.635 | −4.436 [−4.511, −4.362] |
| brainin_nli | 4,046 | 10.450 | **1.271** | −9.179 [−9.354, −9.004] | 1.355 | −9.094 [−9.270, −8.923] |
| silman | 3,046 | 5.824 | **1.001** | −4.823 [−4.945, −4.704] | 1.001 | −4.823 [−4.947, −4.704] |
| rab_dev | 3,141 | 7.512 | **1.122** | −6.390 [−6.492, −6.289] | 1.896 | −5.616 [−5.716, −5.514] |
| ws_dev | 257 | 14.672 | **7.233** | −7.439 [−7.883, −7.018] | 8.030 | −6.642 [−7.082, −6.213] |
| bodek | 21 | 15.684 | **4.960** | −10.724 [−13.190, −8.739] | 6.166 | −9.517 [−12.067, −7.407] |
| sel | 3,000 | 7.549 | **1.005** | −6.544 [−6.723, −6.371] | 1.078 | −6.471 [−6.645, −6.304] |

- **No guard loss:** every upper bound is below 0, far under +0.5.
- **The replay did what it was for.** R7, the start model, would fail the guard on `reshumot_dev` (+1.18 pt against stock). After the round, with 52% Reshumot replay, heb_final is 5.8 pt better than stock there.
- **yediothateva** is reported only and does not bar (§5.3, data-collection's label audit: 3/32). It passes anyway.
- **These lists are dev.** R7, and so heb_final through it, trained on other parts of some of these books (the `.heldout` lists). So the guard shows that modern print is not lost; it is not an out-of-domain claim.

## 4. Reference dashes (§2.3, §6)

- **Why it matters:** the `r7` labels match line_fold_v1 exactly. Stock-start models carry one substitution per reference – or —.
- **R-series dev lists** (from office-print amendment 1, aggregate counts):

| List | – | — |
|---|---|---|
| kevarpirezikhron00haco.heldout | 696 | 0 |
| silman | 526 | 0 |
| brainin_v3 | 450 | 78 |
| sel | 395 | 4 |
| yediothateva06bernuoft.heldout | 362 | 7 |
| brainin_nli | 216 | 0 |
| reshumot_dev | 64 | 0 |
| olb_dev, olb_dev_v1_1, rab_dev, ws_dev, bodek | 0 | 0 |

- **audit2's references** (eval, e2d3d refs, 38 pages, NFC, 51,010 characters including page-join spaces):

| Character | Count | Pages holding it |
|---|---|---|
| – U+2013 en dash | 18 | 5 |
| — U+2014 em dash | 14 | 4 |
| - hyphen-minus (context) | 35 | 11 |
| ־ U+05BE maqaf (context) | 5 | 5 |

- **Under line_fold_v1** (the selection measure):
  - — folds to –, so audit2 holds **32 en dashes**;
  - ־ folds to -, so it holds **40 hyphens**;
  - – and - stay distinct.
- **Effect on the pick:** a stockfold-label model (the stock arm) can output neither –, nor — before folding. So it pays at most 32 substitutions, 0.06 pt of audit2's 50,714 scored reference characters. That is about the winner's margin over the stock arm, 0.061 pt, so the dash penalty alone could account for the stock arm's second place.

## 5. Not done in this round

- **§5.2, the P-hist test claim:** waits on the test references (volunteer launch) and the registered run of the default-model study. eval will score `heb_final` against R7 and stock with its paired page bootstrap, after the per-page decontamination against `phist_r7.list`'s labels (`bbdaade0…`).
- **Third arm** (the office-print winner, §3): not run. It needs the office-print A/B to finish (§4.2 is running at eval) and a registered amendment.
- **Release:** none from this report. The model goes into the default-model study as a candidate. A release follows the open-release rule and stock is reported beside it on every card.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
