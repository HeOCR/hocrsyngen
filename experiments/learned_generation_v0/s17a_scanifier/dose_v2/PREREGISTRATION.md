# S17a dose arm: pre-registered decision rule

Written 2026-11-13, before any dose-arm training. It is pushed to hocrsyngen before the run starts, so the commit timestamp fixes it. Decision by heocr-lead: dose arm only, no ablation.

## Question

Does a second S17a set, added to the released R8b recipe, improve new-printed reading? This is the R9 question "does more S17a help".

## Arms

- **Control:** the released **r8b-main-fold**, `heb.traineddata` sha256 `8cb22dbe…6117`. It is the R8b `main` run's `heb_snap_final`, which heocr-eval selected under line_fold_v1. It was trained on `r8b-tesseract/data/train_main.list` (196,275 lines, sha256 `be972aa4…c102`), which includes s17a_addon_v1.1.
  - It is not retrained. That keeps a scheduler slot free for R9 (lead). Run-to-run training noise is therefore not separated from the arm effect. That is the same as in A/B v2, where each arm also ran once.
- **Dose arm:** `train_main.list` in its exact order, plus the accepted lines of **s17a_addon_v2**, inserted at positions seeded by 20261115. Main's relative order is asserted unchanged.
  - The recipe is R8b's `train.sh`: continue from R7 lr1e4 `heb_0.634_52608_117100`, R8 starter, lr 1e-4 with reset, target 0.01, no eval list.
  - It runs for one epoch, so iterations equal the list length.
  - Training goes through power-scheduler: AC only, a single job.

## s17a_addon_v2 (the added data)

- **Texts:** 20,000 Ben-Yehuda PD lines from `make_texts_v2.py` (seed 20261113; `texts.jsonl` sha256 `f5e6dd98…f6d5`). The following are excluded:
  - every work already in v1.1 (5,912 works);
  - every work tied to a bynli dev record or to the R8b dev and excluded units;
  - any line that shares a word 6-gram with:
    - the R8 dev list and the audit2 references;
    - every R-series dev, report and selection list, OLB dev v1 and v1.1 included;
    - eval's ngram_overlap targets;
    - the P-mod born-digital eval booklets;
    - **every held-out unit of midcentury_unit_split_v2**: test 90, dev 90 and dev_retired 5. For these, the pool is the PDF text layers, the 300 test-page prefills, the blind-pass prefills, the AI readings and the OLB dev text.
  - 35 held-out units have no local text: the 30 plenary dev units, and the 5 retired dev units, which have no text layer. They are excluded by provenance only. No S17a text or style crop comes from them.
- **Generation:** the run2 generator (`last.pt` `efdb5f82…8e3a`) with the same 870 train-book style crops as v1 (`addon_styles.txt` `cc701048…cf7d3`), seed 20261114.
  - The crops were restored from bynli_lines_v2 after pairs_v2 went to the Trash.
  - The restored crops reproduce v1 lines 0–9 byte-for-byte.
- **Gates:** the agreed gates, unchanged: `gates.py` with the v1 parameters.
- **Pre-train check:** heocr-eval runs `check_train_overlap.py` on the arm list and must report CLEAN before release to the scheduler.

## Checkpoint selection

The arm's checkpoint is the one with the lowest line_fold_v1 CER from `score_lines.py` on `r8b-tesseract/data/sel.list` (sha256 `e0d3f298…45f1ea`). The candidates are every checkpoint lstmtraining writes, every 20-minute snapshot and the final snapshot. This is the procedure that selected the control. Selection is decided before any gate set is scored.

## Primary: the OLB Reshumot dev gate

- **Set:** olbreshumotlines_v1_dev (manifest sha256 `e2101b58…9be7`), 3,254 lines from 55 units. This is the set that gated R8b's release.
- **Scoring:** `score_lines.py`, all lines charged, profile line_fold_v1 (`2e262710…d317`).
- **Statistic:** Δ = CER(control) − CER(arm), so a positive Δ means the arm is better. The interval is a 95% paired cluster bootstrap over `unit_id`, with 10,000 resamples and seed 0, as in `r8b_olb_gate.py`.
- **Primary view:** "all" lines. "Exact", "not_exact", the "excluded" view (no 6-gram shared with the arm's train list) and cap-60 are reported as sensitivity checks.
- **Rule: OLB win** means the lower bound of the 95% interval of Δ on "all" is above 0. If the "exact" stratum's Δ has the opposite sign to "all", the result is **unresolved** and goes back to the lead.

## Guard: no loss on any new-printed dev book

- **Books:** the five new-printed dev and report books we score:
  - Kevar and Yedi'ot ha-Teva, held-out lines only (each book minus its sel.list lines);
  - Brainin IA (the R8c dev unit and R8b's known limit);
  - Brainin NLI;
  - Silman.
- **Statistic:** per book, Δ_book = CER(control) − CER(arm) under line_fold_v1. The interval is a 95% paired page-cluster bootstrap (10,000 resamples, seed 0). For pages without an id, line clusters are used and recorded.
- **Rule: loss** on a book means the whole 95% interval of Δ_book lies below 0, i.e. the arm is worse beyond the interval.

## Decision

- **The arm wins** if, and only if, it is an OLB win **and** it loses on none of the five books.
- Otherwise the arm does not win, and the report gives the deltas as they are.
- No other set, view or checkpoint can turn a loss into a win after the fact.

### Confirmation run (added before training, heocr-lead 2026-11-13)

- If the arm wins under the rule above, R9 adopts the extra lines only after a confirmation run.
- The confirmation run retrains a control: main-fold's recipe on `train_main.list` reshuffled with a different seed. It is selected the same way (line_fold_v1 CER on sel.list). The arm is then re-scored against both controls.
- **The win stands** only if Δ = CER(retrained control) − CER(arm) still has its 95% unit-cluster lower bound above 0 on OLB v1_dev "all".
- If the arm loses or the result is unresolved, there is no confirmation run. The result is reported, and S17a dose stays at v1.1.

## Reported alongside, not deciding

- **Gate statistics** per sub-rule, and acceptance per style book and per character class.
- **Digit bias:** the digit share in the accepted v2 lines against v1.1:
  - lines with any digit, as a share of lines;
  - digits per 1k characters;
  - gate-2 rejections among lines with digits.
  This shows whether gate 2's anti-digit bias builds up.
- **Accept/reject sheets** per style book and per character class. Only unclear categories go to Shay as hard cases.
- **Report-only sets:** Bodek, reshumot dev (rendered), rab dev and ws dev.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
