# P-hist round v1: pre-registration

Written 2026-11-18, before any P-hist training. The round fine-tunes Tesseract for old Hebrew print (P-hist, decision 0017), using data-collection's audited pool and a Reshumot replay. All counts are aggregates, with no protected text. `tasks/` is not a git repository, so scripts are pinned by sha256.

## 1. Roles of the evaluation sets (lead, 2026-11-18)

| Role | Set | Used for |
|---|---|---|
| **P-hist dev** | audit2 (13 books) | choosing the start model (§3) and the snapshot (§5.1); nothing else |
| **P-hist test** | the P-hist hold-out v1, 22 books (eval_reservations_v3, heocr-restricted-eval#50) | the claim (§5.2); never for any choice |

- **Never selected on:** bynli v3 dev units, and any test page.
- **Five hold-out pages stay out of the scored set for good:** Qav ve-Naqi, Ohev Ger, Beit ha-Midrash and Sefer ha-Nezirim ×2. They share 6-grams with these lists and were already dropped by eval's earlier page check. eval records this.

## 2. Data

### 2.1 P-hist lines: data-collection's audited pool v1

- **Pool:** `tasks/phist-round/phist_pool_v1.json` (sha256 `f99e5239…`). It lists only books that passed the per-book label audit: at most 1 word error in 32 seeded lines (hocrgen#205 §3, §3a, §3b). Each set's manifest is pinned by sha256.
- **Drops:**
  - 0 lines are reserved by eval (`synth-reservations/reserved_works.py`, every eval_reservations_v*.json at restricted-eval e9c5d3a);
  - **76** lines share a word 6-gram with an official CLEAN target (`office-print-v0/scripts/official_targets.py`).
- **Lines kept: 36,946,** all square type and unpointed:

| Set | Book | Lines | Share of round |
|---|---|---|---|
| bynli_lines_v3 | zikhronotlebetda01reck | 6,099 | 7.93% |
| rablines_v1 | machzor-vitry-berlin-1889-97-gcopy | 6,077 | 7.90% |
| rablines_v1 | lekach-tov-buber-vilna-1884-vol3-5 | 6,063 | 7.88% |
| bynli_lines_v3 | afahleneemaniml00fngoog | 5,749 | 7.47% |
| bynli_lines_v3 | kolkitveylkatsen018800 | 5,712 | 7.42% |
| bynli_lines_v3 | seferhademaotmeo0000bern | 5,350 | 6.95% |
| rablines_v1 | toratan-shel-rishonim-frankfurt-1881 | 1,896 | 2.46% |

### 2.2 Replay: Reshumot anchor

- **Why:** the lead's per-book cap is 8% of the round. With 7 books, no book can be at or under 8% of the pool alone, since 1/7 = 14.3%. So the round adds replay (lead's ruling): a seeded (**20261129**) **40,000** of the 45,250 decontaminated Reshumot anchor lines of office-print v0 lists_v2.
- **Files:** the same `.lstmf` files office-print uses, with dash-folded labels, PD-IL.
- **Replay share: 51.98%.** Every P-hist book is uncapped and at or under 8%.
- **The share is high for a P-hist round.** The 8% cap forces it, and the lead accepts it.
- The replay share falls in the next round, when pool v2 (A1 capped lines, marker-free Tier B, Tur) arrives.

### 2.3 Labels (lead, 2026-11-18)

Two label variants, both in logical order and NFC. The list order and lines are the same; only the labels differ.

| Variant | Folds | For start model |
|---|---|---|
| `r7` | ׳→' ״→" —→– | R7 (its unicharset has ־ and –) |
| `stockfold` | ׳→' ״→" —→- ־→- –→- | stock heb or the office-print winner (neither has ־ or –) |

- **No layer surgery** in either variant.
- **Scoring is line_fold_v1** (`eval-domains/profiles/line_fold_v1.json`, sha256 `2e262710…`). It folds, on both reference and prediction, ־→- ׳→' ״→" “ ” „→" and —→–, and keeps – and - distinct (eval, 2026-11-18).
  - So `r7` matches the scorer exactly.
  - `stockfold` carries a **known dash penalty:** one substitution per reference – or —, the same cost stock pays. Reference – and — counts per scored set are reported with the results.
- **Train lines carrying the marks:**
  - ״ 726 (rab), ׳ 372 (rab);
  - ־ 553 (bynli), – 1,938 (bynli);
  - — 9.

### 2.4 Lists and CLEAN

- **List:** P-hist lines plus replay, one seeded shuffle (**20261130**), 76,946 lines.

| List (`tasks/phist-round-train/v1/`) | Lines | list sha256 | labels sha256 |
|---|---|---|---|
| `phist_r7.list` | 76,946 | `0cd3e7e8788f3c278ae9083f953a88f7319c70910d75423d0349733f7f72820c` | `bbdaade092892644bea4397061cbc1a88f9537a5f59412e12c0b0ab59c9cf33b` |
| `phist_stockfold.list` | 76,946 | `cce4c0051a8f6f80a16ad1c5cf012ba2654458db50ca1dac90188e6fc23cd93a` | `e42c639a5fdc71bfea06bb19622455d186cb77007155a94915ad930f4996cecf` |

- **eval's official CLEAN, 2026-11-18 19:14–19:17: CLEAN on both lists.**
  - check_train_overlap: every target 0.
  - The P-hist hold-out page check against all 66 candidate pages of groups A–C: the only shared pages are the 5 in §1, already out of scoring.
  - A positive control hit.
- **Scope:** group D's typed pages and the early-print pages moving to typed are checked when their text exists. A hit then drops the training line.
- **Scripts:** `phist-round-train/scripts/build_phist.py` and `r8b-tesseract/scripts/make_lstmf.py` (sha256 `540116b8…`), tesseract 5.5.3.

## 3. Arms (lead, 2026-11-18)

Two arms train now, in parallel, so the round does not wait for the office-print A/B. Selection comes after training (§5.1).

- **Third arm, later:** if the office-print A/B finishes, its winner is added as a third arm under the same rule. It is registered as an amendment before its run.
- **Zero-shot context:** the start models' zero-shot audit2 scores are reported as context. They select nothing.

| Arm | Start model | sha256 | List | Labels |
|---|---|---|---|---|
| **r7** | R7 (`r7-tesseract-real/models/r7/heb.traineddata`) | `95faab81fba6fe57…` | `phist_r7.list` | `r7` |
| **stock** | stock tessdata_best heb | `dbaa827aea6bc212…` | `phist_stockfold.list` | `stockfold` |

- **R7's data:** it trained on 95k bynli_lines_v2 lines. data-collection's audit of its 6 largest books found 13 word errors in 192 lines, about 7%; 2 books fail the bar.
- **Each arm keeps its start model's own unicharset,** with no layer surgery.
- **The two lists hold the same lines in the same order.** Only the dash and maqaf labels differ (§2.3).

## 4. Training (one heocr-remote cpu pod, both arms side by side)

- **Recipe, each arm:** lstmtraining `--continue_from` its start model's LSTM, `--old_traineddata` and `--traineddata` its start model, lr 1e-4 with `--reset_learning_rate`, `--target_error_rate 0.01`, no eval list.
- **Iterations:** **76,946**, one pass of its list.
- **Snapshots:** every **10 minutes** of wall time, each converted to `.traineddata` on the pod and pulled back. There's also a final model.
- **Machine and build:**
  - one 32-vCPU `cpu3c` pod, both arms on the same hardware;
  - OMP_THREAD_LIMIT=4 per arm;
  - tesseract 5.5.3 built from its tag (commit `db0ec62f…`);
  - every starter, list and labels sha256 is checked on the pod before training.
- **Scripts:**
  - `phist-round-train/remote/train_phist.sh`, staged by `phist-round-train/scripts/stage_remote.py` under the pd_scans open root;
  - the manifest sha256 goes in the result report.
- **Stop:** training stops at 11 h 20 min at the latest. A timed-out arm says so in its run.json and can be resumed from its final checkpoint.

## 5. Decision rule

### 5.1 Selection: audit2 only, after training

- **Scorer:** eval scores every snapshot of every arm on audit2 (P-hist dev) with its P-hist scorer, under line_fold_v1 with score_lines, not lstmtraining's BCER.
  - **Amendment (eval, 2026-11-18, before any snapshot was scored):** audit2 has page-level references only, with no line set, so score_lines cannot run on it.
    - **What runs instead:** each candidate reads the 38 audit2 page images with Tesseract `--psm 3` through heocr-engine's tesseract command, the same path as R6's and R7's audit2 scores.
    - **The selection measure:** micro page CER under line_fold_v1 (`eval-domains/profiles/line_fold_v1.json`, sha256 `2e262710…`): NFC, the profile's folds, whitespace runs collapsed, summed edits over summed reference characters.
    - **Candidates:** 20 in all, each arm's 8 snapshots plus heb_best_train and heb_final.
    - **Context only, selecting nothing:** stock tessdata_best heb and R7 are reported beside them, and so is hocrgen primary.v1.
    - The rule and the tie-break are unchanged.
- **Rule:** the **lowest audit2 CER over all snapshots of all arms** is the round's model. Ties go to the earlier snapshot, then to arm r7.
- **Nothing else selects.**

### 5.2 Claim: P-hist test only

- **Sets:** on the 22-book P-hist test, at most 3 seeded pages per book, the round's model is scored once against:
  - the start model;
  - stock tessdata_best heb, always reported.
- **Method:** eval's paired page-level bootstrap.
- **Claim:** the claim is the P-hist test CER difference with its interval.
- **Per-page decontamination:** a scored page needs 0 official 6-gram hits against every scored model's actual training labels (eval). Pages that fail are replaced by another seeded page of the same book.

### 5.3 Guard: modern print must not be lost

- The replay exists to keep modern print. So the selected model must not lose against stock on office-print §4.3's R-series dev lists, under the same non-inferiority rule: the upper bound of the paired bootstrap 95% interval of Δ CER is at most +0.5 pt.
- A guard loss on any list bars the claim of a general improvement. The P-hist result is still reported.
- **data-collection's dev-unit label audit, done (32 seeded lines each, word errors):**

  | List | Word errors | Effect |
  |---|---|---|
  | kevarpirezikhron | 0/32 | bars as usual |
  | brainin (IA) | 1/32 | bars as usual |
  | yediothateva | 3/32, failing on one-letter edition variants | the yediothateva guard result is **reported but does not bar** |

## 6. Reporting

Per-book and per-set counts, CER with intervals for the selected model, the start model and stock, the reference dash counts, the guard table, the pod run id, and every snapshot's audit2 CER.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
