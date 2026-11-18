# P-hist round v1: pre-registration

Written 2026-11-18, before any P-hist training. The round fine-tunes one Tesseract model for old Hebrew print (P-hist, decision 0017), using data-collection's audited pool and a Reshumot replay. All counts are aggregates, with no protected text. `tasks/` is not a git repository, so scripts are pinned by sha256.

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

### 2.3 Labels (lead, 2026-11-18)

Two label variants, both in logical order and NFC. The list order and lines are the same; only the labels differ.

| Variant | Folds | For start model |
|---|---|---|
| `r7` | ׳→' ״→" —→– | R7 (its unicharset has ־ and –) |
| `stockfold` | ׳→' ״→" —→- ־→- –→- | stock heb or the office-print winner (neither has ־ or –) |

- **No layer surgery** in either variant.
- **Scoring is line_fold_v1,** which folds ־→- ׳→' ״→" —→–, and keeps – and - distinct (eval, 2026-11-18).
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

## 3. Start model

- **Candidates:**
  - **R7.** It trained on 95k bynli_lines_v2 lines. data-collection's audit of its 6 largest books found 13 word errors in 192 lines, about 7%; 2 books fail the bar.
  - **The office-print v0 winner,** once the A/B is decided.
  - **Stock tessdata_best heb.**
- **Choice:** eval scores the three zero-shot on audit2 (P-hist dev), paired, after tonight's gate and once the office-print winner exists. The lowest CER wins.
- **Labels:** the winner fixes the label variant (§2.3).

## 4. Training (one heocr-remote cpu pod)

- **Recipe:** lstmtraining `--continue_from` the start model's LSTM, `--old_traineddata` and `--traineddata` the start model, lr 1e-4 with `--reset_learning_rate`, `--target_error_rate 0.01`, no eval list.
- **Iterations:** **76,946**, one pass of the list.
- **Snapshots:** every 20 minutes of wall time, as `.traineddata`.
- **Machine and build:** a 32-vCPU `cpu3c` pod, OMP_THREAD_LIMIT=4, tesseract 5.5.3 built from its tag (commit `db0ec62f…`). The pod checks every input hash before training.

## 5. Decision rule

### 5.1 Snapshot selection: audit2 only

- **Scoring:** eval scores every snapshot on audit2 with its P-hist scorer under line_fold_v1. The lowest CER is the round's model; ties go to the earlier snapshot.
- **Nothing else selects.**

### 5.2 Claim: P-hist test only

- **Sets:** on the 22-book P-hist test, at most 3 seeded pages per book, the selected model is scored against:
  - the start model;
  - stock tessdata_best heb, always reported.
- **Method:** eval's paired page-level bootstrap.
- **Claim:** the claim is the P-hist test CER difference with its interval.
- **Per-page decontamination:** a scored page needs 0 official 6-gram hits against every scored model's actual training labels (eval). Pages that fail are replaced by another seeded page of the same book.

### 5.3 Guard: modern print must not be lost

- The replay exists to keep modern print. So the selected model must not lose against stock on office-print §4.3's R-series dev lists, under the same non-inferiority rule: the upper bound of the paired bootstrap 95% interval of Δ CER is at most +0.5 pt.
- A guard loss on any list bars the claim of a general improvement. The P-hist result is still reported.
- The kevarpirezikhron, yediothateva and brainin lists are under data-collection's dev-unit label audit. If a list fails that audit, its guard result is reported but does not bar.

## 6. Reporting

Per-book and per-set counts, CER with intervals for the selected model, the start model and stock, the reference dash counts, the guard table, the pod run id, and every snapshot's audit2 CER.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
