# Office print v0: synthetic training data for a model that beats stock heb on modern office print

**Status:** plan for review (heocr-lead). Nothing is generated or trained before the lead approves it.
**Task:** heocr-lead, 2026-11-18, approved by Shay. It serves decisions 0019 and 0020, the `heocr` pipeline's OCR route.
**Owner:** synth-gen. heocr-eval owns every gate, split and overlap check. Data-collection owns the real lines.

## 1. Why

- **Where stock stands.** The `heocr` OCR route runs stock Tesseract `heb` (tessdata_best, sha256 `dbaa827a…abdae5`) by default, because none of our models beats it on modern scans.
- **The weakest gate cells are all modern-print OCR:** PDF T5 (image-only), PDF T4 (garbage layer, read through OCR) and scanned tables.
- **What is actually open is number recall, not CER** (heocr-eval, 2026-11-18, synthetic set `synth-2026-11-17-main`, heocr at `7f5e99e`). heocr already beats stock on CER in all three cells. Its number recall is below the best baseline in each cell by more than the 1-point margin. §2.1 has the figures.
- **So this work is aimed at numbers first:** dates, amounts, ₪, %, section numbers, and digits in table cells.
- **What S17 and the R-series taught:**
  - Our models were trained toward mid-century books.
  - More data of the same kind stops helping. The S17a dose arm gained nothing over v1.1 and lost on Silman (hocrsyngen#101).
  - What is missing is the **office look**: office fonts, numbered structure, tables, numbers, and office-scan, photocopy and phone degradation.

## 2. What "beats stock" means

**The judge is eval's registered D-bench release gate** (`dbench_release_gate_2026-11-17`; README registered at `bca7cb1`, sha256 `bffb2f40…6c01`, amendments 1–3; frozen `gate.py` and `measures.py`, `line_fold_v1`).
- **Rule (§6).** For each cell, each baseline and each gate measure, Δ = heocr − baseline, oriented so that larger is worse for heocr, with a paired bootstrap over documents (10,000 resamples, seed 0).
  - A comparison passes when the 97.5th percentile of Δ is at most the margin. This is beat-or-tie, as non-inferiority, against **every** baseline.
  - A cell passes only if every comparison in it passes.
  - Margins: CER +0.5 pt; number recall 1.0 pt; rows read 1.0 pt; rows silent +0.5 pt; silent loss +0.5 pt.
- **Baselines:** stock Tesseract (tessdata_best `heb`, psm 3), docling, markitdown, pymupdf4llm, and the production tender-extraction pipeline.
- **How a model gets in.** A new model inside heocr's OCR route is a dated amendment plus a run on a fresh synthetic set: the D-bench generators with new seeds. A test-split veto can only hold a cell back. eval runs it; I never read the test split, `eval_refs/` or any `runs/*test*`.

### 2.1 Target cells and where they stand (synthetic `synth-2026-11-17-main`, heocr `7f5e99e`; aggregates from eval)

| Cell (docs) | Gate measures | stock | docling | pymupdf4llm | heocr (stock inside) | Open |
|---|---|---|---|---|---|---|
| **PDF T5** image-only: `B/pdf_t5_scan`, `C/pdf_t5_office`, `C/pdf_t5_office_numbers` (82) | CER, number recall, silent loss | CER 11.5, NR 42.0, silent 10.4 | CER 81.5, NR 77.6 | CER 81.1, NR 84.0 | CER 7.0, **NR 74.8**, silent 4.1 | NR: about 9 pt below pymupdf4llm |
| **PDF T4** garbage layer: `B/pdf_t4_garbage` (40) | the same | CER 9.1, NR 45.8, silent 8.0 | NR 70.4 | | CER 6.0, **NR 68.6**, silent 2.1 | NR: about 2 pt below docling |
| **Scanned tables**: `C/pdf_t5_table`, `_faint`, `_merged` (120) | CER, NR, rows read, rows silent, silent loss | CER 54.5, NR 14.2, rows read 3.7 | NR 95.0, rows read 2.5 | | CER 18.1, **NR 87.0**, rows read 66.9, rows silent 2.8 | NR: 8 pt below docling |

Number recall is not a cell of its own. It is the number-recall measure inside each cell, against every baseline.

### 2.2 First step: is the number gap the recogniser's?

Synthetic data for the recogniser only helps if the missed numbers are **misread**, not **missing**. Before any page generation, I score heocr's own outputs on sets B and C, the open tuning ground. Every missed gold number goes into one class:
- **misread:** the number's region was read, but digits, order, separators or the ₪ or % sign are wrong. The recogniser can fix these.
- **absent:** nothing was output where the number is. This is segmentation, routing or a dropped cell, which this work can't fix.
- **split or joined:** the number is broken across tokens, or glued to a neighbour. This is mixed: the recogniser's spacing and the pipeline's tokenisation.

The class counts per cell go to the lead and to pipeline. **If most of the gap is absent, I report that before generating anything,** because the fix then belongs in heocr, not in the model.

#### 2.2.1 Result (2026-11-18, synth-2026-11-17-main, heocr 7f5e99e; counts only)

The scripts are [`diagnosis/numgap.py`](diagnosis/numgap.py) and [`diagnosis/number_assembly.py`](diagnosis/number_assembly.py). They import eval's frozen `measures.py` (`NUM`, `fold`, `clean`) and build the reference as `gate.doc_units` does. They reproduce the gate's number recall exactly for every reader and cell: heocr 74.75 / 68.60 / 87.01, docling 77.61 / 70.44 / 95.02, pymupdf4llm 84.00. The outputs ([json](diagnosis/numgap_synth-2026-11-17-main.json), [txt](diagnosis/number_assembly_synth-2026-11-17-main.txt)) hold counts only.

**The gap is mostly number assembly, not recognition and not missing regions.**
- **What fails.** Most of heocr's missed numbers are dates (`dd.mm.yyyy`), section numbers (`3.1`) and multi-level section numbers (`1.2.3`).
- **What the output holds.** For almost all of them, every digit group is there, but **with whitespace between the groups and in reversed order**. This is Tesseract's right-to-left word reordering, after the line was split into separate words at the dots. Stock does the same.
- **What is truly missing.** Numbers with no digit group in the output at all are rare: 8 dates in T5, 4 in T4, 12 in tables.

| Cell | Ref numbers | heocr misses | Reversed with spaces (dates, sections) | NR if all of those were joined (upper bound) | Other misses (ints, amounts, %) | Target (best baseline − 1 pt) |
|---|---|---|---|---|---|---|
| T5 | 8,032 | 2,028 | 1,636 (20.4 pt) | 95.1 | 320 (4.0 pt) | 83.0 |
| T4 | 3,596 | 1,129 | 932 (25.9 pt) | 94.5 | 178 (5.0 pt) | 69.4 |
| Scanned tables | 5,103 | 663 | 167 (3.3 pt) | 90.3 | 416 (8.2 pt) | 94.0 |

**What follows:**
1. **A pipeline fix comes first:** rejoining a numeric run that Tesseract split and reversed in an RTL line. It is cheap and deterministic, and by this bound it closes T5 and T4 on its own. It belongs to pipeline (HeOCR/heocr) and is reported to them. It needs its own false-join check, so it must not glue separate numbers.
2. **The recogniser part is real but smaller:**
   - the spaces it puts inside numbers (that is what lets Tesseract split them), which the training labels teach it not to do;
   - wrong digits in table cells: in tables the other misses are 8.2 pt, while reversed numbers are only 3.3 pt. A perfect joiner still leaves tables at 90.3, below 94.0, so tables need better digit reading too.
3. **This plan continues, re-aimed:**
   - lines dense in dates, section numbers and amounts, labelled with no space inside a number;
   - table cells with short integers, amounts and percentages;
   - every gain is measured with heocr's joiner on and off, so the model's own share is visible.

### 2.3 Development rule (fixed in the arm-registration PR, before either arm trains)

- **Checkpoint selection:** line_fold_v1 CER on `office_val` (§5.3), my synthetic held-out set, as the R-series does.
- **Arm decision, at document level:** sets B and C, scored with eval's D-bench scorer (`gate.doc_units` / `report.py --synth`, `line_fold_v1`), with heocr at a fixed commit and the arm's model in the OCR route.
  - The arm **qualifies for eval's amendment run** if, on all three cells, `gate.py`'s rule holds against every baseline's recorded outputs.
  - If no arm reaches that, an arm still counts as progress when its number recall beats heocr with stock inside on at least one cell (paired bootstrap over documents, lower bound above 0), and no gate measure gets worse beyond its margin in any cell. That is reported, and it is not sent to the gate.
  - B and C are what the cells are measured on, regenerated with new seeds at gate time. eval allows using them for selection, and notes that gains measured on them overstate real-world gains (§6a).
- **Guards, at line level on real print, no loss against stock:** the R-series dev lists (`eval-domains/intermediates/r8b_score/lists`, dev only), scored with `score_lines.py` under `line_fold_v1`, never lstmeval BCER. They include OLB Reshumot dev v1_dev, Kevar and Yedi'ot held-out lines, Brainin IA, Brainin NLI and Silman. A loss means the whole 95% interval of CER(model) − CER(stock) lies above 0.
- **Not used for anything:** the print-and-scan pack PS-v1 is report-only at eval, and the mid-century test set and the P-mod eval set are off-limits.
- **Reporting:** every table shows stock tessdata_best, heocr with stock inside, and the arms.

## 3. Pages

Generated page images come with exact line, cell and region boxes and the logical text. Line crops are cut from the page after degradation, so a crop holds what a real scan's line holds: ruling remnants, neighbour ascenders and stamp ink.

- **Nothing copies D-bench (eval, 2026-11-18).** The gate's fresh set comes from the D-bench generators (`dbench/synth`), with their layouts, templates, seeds and text pool. Training on look-alikes would make the synthetic gate measure memorisation of eval's own generator. So:
  - I don't read or reuse that code, its layouts, its templates or its seeds;
  - every template here is written from the families below;
  - the text comes only from §4;
  - the degradation is my own (§5.2).
- **Never used:** `out_c/lo_pdf`, and anything rendered with Arial Unicode MS.

| Family | Content | Share of pages |
|---|---|---|
| **Running text** | legislation, regulation and notice text in paragraphs; justified and ragged-left; one and two columns | 30% |
| **Numbered structure** | sections and sub-sections: `1.`, `1.1`, `1.1.1`, `(א)`, `(1)`, `א.`; hanging indents; definitions lists; תוספת/schedule blocks | 25% |
| **Tables** | **ruled** (full grid, header-only, row lines only) and **unruled** (aligned columns). Cells hold amounts (`1,234,567.89`), ₪ before or after, %, dates (`dd.mm.yyyy`, `dd/mm/yy`, `d.m.yyyy`), quantities, item numbers and short Hebrew labels. Merged header cells, totals rows, and mixed RTL and LTR columns | 30% |
| **Letter and tender front matter** | letterhead block, date line, `לכבוד`, subject line (`הנדון:`), reference numbers (`מכרז מס' 12/2026`), closing, signature area | 15% |

- **On every page:**
  - headers and footers, page counters (`עמוד 3 מתוך 12`, `- 3 -`, `3/12`), and the occasional footnote rule;
  - **image-only elements, never labelled as text:** letterhead emblems (generated geometric marks, never a real state or ministry emblem), signatures (generated pen strokes) and round or rectangular stamps (generated, with generated text that is labelled only where it is legible, and otherwise masked out of line crops).
- **No real names and no impersonation:**
  - No real ministry logo, no real emblem, no real person's name in signatures.
  - Names in front matter come from a generated pool. Ministry or authority names are generic ("משרד הדוגמה", "הרשות לבדיקות").
  - Generated ID-like numbers are never written as ת"ז. Every number field is random.

## 4. Text

| Source | Use | Licence basis |
|---|---|---|
| **Reshumot law and regulation text: the train split of reshumotlines_v2 `clean3`, minus every reserved booklet** (data-collection; born-digital Sefer HaChukim and Kovetz HaTakanot, publisher glyph layer; 51,215 of 70,665 lines remain, §4 decontamination) | running text, numbered sections, table labels | §6 (laws and regulations), `pd_israel.basis = s6_official_text` |
| **Generated tender-like structure** | section skeletons, table schemas, front matter, page counters | ours, CC0 |
| **Generated numbers** | amounts, ₪, %, dates, quantities, reference numbers, phone and fax formats | ours, CC0 |

- **Why this source and not htext (heocr-htext, 2026-11-18):**
  - htext-cc0 holds no legislation yet. Its knesset-laws builder (1948–77, from an OCR text layer) is still an unreviewed plan (HeOCR/htext#6).
  - reshumotlines_v2 is modern wording with exact labels from the glyph layer: 2.69M characters, 47.5% of lines with a digit, 14.6% numeric-heavy.
  - Per-line provenance comes from its manifest: `id`, `unit_id`, `source_id`, `entry_id`, `series`, `booklet_number`, `publish_date`, `page`, `printed_page_number`, `label_source`.
  - knesset-laws can be added later as a versioned source once it is published. Its OCR-layer text would need a label-noise check first.
- **Same text twice.** The synthetic pages reuse anchor text in new layouts, fonts and degradation. Text is drawn by `unit_id`. Units held out for `office_val` (§5.3) are removed from the anchor and from the degraded anchor too, so no `office_val` text is ever trained.
- **Number distribution, chosen on purpose:**
  - at least 35% of table cells and 15% of running-text lines carry a number;
  - dates are spread from 1990 to 2030;
  - amounts run from 1 to 10^9, with and without decimals and thousands separators;
  - ₪ comes before and after the number, and as `ש"ח`;
  - percentages are integers and decimals.
- **Labels:** the logical string. Signs that stock's unicharset lacks are folded exactly as `line_fold_v1` folds them (`״`→`"`, `׳`→`'`, `־`→`-`). They are still drawn as real ״ and ׳ glyphs, so the model learns to read them.
  - The en dash `–` is left out of the label text: it is not in stock's unicharset, and adding it would need layer surgery. Labels write `-` instead. See §8.3 for how the scorer charges it.
  - The cost is that a reference `–` is charged, as it is for stock today. This is stated in the report.
- **Decontamination, before rendering and again on every final list:**
  - **Exclusion by provenance, whole units:** everything in eval's `eval_reservations_v1.json` (heocr-restricted-eval#31; identifiers only). It covers:
    - the print-and-scan pack PS-v1 (PBY works 2218, 2020, 6755 and 21983; ק"ת 12566–12574, ס"ח 3570–3579, י"פ 15133);
    - the mid-century test, dev and retired-dev units (185);
    - the P-mod eval and holdout units (302);
    - **the D-bench text pool's 83 born-digital booklets;**
    - the P-hist and line_verify ids.
    All R-series and OLB dev lists are excluded too, and data-collection's DROPS chain is honoured (clean3, including the 19 vendor-hit lines).
  - **What that removes (measured 2026-11-18):**
    - 19,450 of clean3's 70,665 lines, from 47 booklets, most of them in the D-bench pool, which reshumotlines_v1/v2 already shared with training text. **51,215 lines remain**, and every part of this mix uses only them.
    - OLB Reshumot train: 0 of 136,903 lines are reserved.
    - **Starting from stock has a side benefit:** neither arm has ever trained on D-bench pool text. R8b and R9 have, through reshumotlines.
  - **Hash fixtures:** the D-bench pool and PS-v1 fixtures (htext leakage format: NFC lines and word 3-grams) are also checked against the text pool, on top of the provenance exclusion.
  - **Word 6-gram exclusion** against the same pools, under both tokenisations, as in S17a `make_texts_v2.py`.
  - **eval's `check_train_overlap.py` on every final list.** A list counts as CLEAN only when the official run passes; eval is adding PS-v1 and the D-bench pool as targets. I send each list with its path and sha256.

## 5. Fonts, degradation and validation

### 5.1 Fonts (iron rule: free fonts only; licence and sha256 in the manifest)

- **In the repository:** David Libre, Frank Ruhl Libre, Miriam Libre, Alef, Assistant, Heebo, Rubik, Noto Sans Hebrew and Noto Serif Hebrew (all OFL).
- **To add, office-metric equivalents from google/fonts at a pinned commit:**
  - **Arimo** (Arial-metric), **Tinos** (Times-metric, Regular and Bold) and **Cousine** (Courier-metric, Regular and Bold), all OFL-1.1 in google/fonts (they moved from Apache-2.0 to OFL there), all with full Hebrew including te'amim;
  - **Open Sans** Hebrew (OFL);
  - Liberation is not in google/fonts, so it is left out; Arimo is the same design lineage.
  - In HeOCR/hocrsyngen#104 (google/fonts `7af0d90`; Shay's go 2026-11-18), with a coverage check and a bidi test for each, as in #100. Open Sans lacks rafe, te'amim, ׳ and ״, so lines with those signs are refused on it.
- **Never used:** proprietary faces (Arial, Arial Unicode MS, system David, Narkisim, Miriam, Times New Roman, FrankRuehl CLM, or any Windows or Office font). The manifest refuses any face it doesn't list (render-lines rule).
- **Held-out face:** one family, **Tinos** (both weights), is used only in `office_val`, to measure how well the model reads a face it has not trained on.
- **Font overlap with the gate, declared.** D-bench renders with Alef, David Libre and Frank Ruhl Libre (eval). These are real-world faces, and eval allows them. This mix trains on all three. The gate's synthetic sets therefore share faces with training, though not templates, text or degradation. The line-level guards on real print (§2.3) are where unshared faces are measured.

### 5.2 Degradation (page level, seeded, recorded per page)

| Model | What it does | Share |
|---|---|---|
| **office_scan** (new, from `office_scan_soft`/`_heavy`) | 200–400 dpi; skew ±3°; mild blur; grey-level or Otsu binarisation; JPEG 70–92; small bleed-through | 50% |
| **photocopy** (new) | 1–2 generations; contrast up; toner speckle; stroke thickening or thinning; edge shadow and banding; dropout of thin rules | 25% |
| **phone_photo** (new) | perspective warp (≤6°), uneven light and vignetting, mild motion or defocus blur, 150–250 effective dpi, JPEG 60–85, then the app's deskew or crop | 15% |
| **clean** (born-digital raster, 150–300 dpi) | no degradation, the T4 case of a clean page with a bad layer | 10% |

- **Calibration on train-side real pages only:**
  - the ink band height and density (otsu2pct, data-collection's measure);
  - stroke width;
  - blur and noise estimates;
  - matched against the train split of the OLB Reshumot scans and the reshumotlines_v2 rasters, never dev or test.
- **From S17:**
  - **The S17a gates come along:** glyph_no_ink, ink_outside and stray_cc, plus a stock-heb read-back gate that drops lines nobody could read (CER > 0.5) and is reported per class. Gate-2 digit bias is reported, as in S17a.
  - **The learned scanifier is not reused.** It learned mid-century book style.

### 5.3 Held-out validation (dev and synthetic only, never test)

- **office_val** (synthetic, selection): 2,000 pages, from:
  - held-out Reshumot units (by `unit_id`, about 5% of clean3 train text; removed from every training part);
  - generator seeds of their own;
  - the held-out face (Tinos);
  - one held-out table schema family;
  - all four degradation models.
  It is scored as lines (line_fold_v1) and as pages, through the `heocr` CLI with the model in the OCR route, for number recall and table cells.
- **Dev counterparts (eval, 2026-11-18).** The real dev split has no T4, T5 or scanned-table documents (its files are T1, DOCX, T6 and DOC). So the document-level counterparts are the synthetic sets B and C (§2.3), and the line-level ones are the R-series dev lists.
- **No gate test document, no D-bench §5.1 template and no print-and-scan-pack page** is used to tune anything.

## 6. Mix, sizes and training

| Part | Lines | Notes |
|---|---|---|
| **O1 synthetic office lines** | 120,000 (from about 6,000 pages; cells count as lines) | §3–5 |
| **Real modern anchor: reshumotlines_v2 clean3 minus reservations** | 51,215 (minus the `office_val` units, about 5%) | born-digital Reshumot lines (data-collection), as in R9 |
| **Real modern anchor, degraded** | 35,000 lines, from the same pages' rasters run through §5.2 | real layout and real typesetting with synthetic degradation (§8.2) |
| **Real scans: OLB Reshumot train scanned lines** | 60,000 (seeded sample of 136,903) | anti-forgetting for real scan noise |
| **Total (arm A)** | about 264,000 | |

- **Order:** seeded shuffle of the whole list, as lstmtraining reads in order. Add-ons are inserted at random positions.
- **Arms.** Two, run in the two scheduler slots once they free up.
  - **A:** continue from **stock tessdata_best heb**, using its unicharset with no layer surgery. Training uses the full mix, lr 1e-4, one epoch, a snapshot every 20 minutes, the R-series recipe otherwise.
  - **B (lead's decision, §8):** real-only, the anchor plus OLB train, continued from stock. It runs **the same number of iterations as A**: the real lines are recycled in a second seeded shuffle, using all 136,903 OLB train lines before any line repeats. So A against B tells what the synthetic part adds at equal compute.
- **Compute:** about 264k iterations per arm, so about 3.5 h per arm on this machine (the dose arm ran 214,828 iterations in 2 h 51 min). Training runs **only through tasks/power-scheduler, on AC power, with at most 2 heavy jobs**. Both slots are busy now, so generation and lists come first.
- **Registration.** The arm decision rule (§2.3) is pushed as its own commit before either arm starts, as in the S17a dose arm.

## 7. Deliverables and order

1. **This plan**, reviewed by the lead.
2. **Fonts PR:** Arimo, Tinos, Cousine and Open Sans (HeOCR/hocrsyngen#104; Shay's go given 2026-11-18).
3. **Number-gap diagnosis (§2.2)** on sets B and C: misread, absent, or split/joined, per cell. It goes to the lead and pipeline. It decides whether the rest goes ahead as planned.
4. **hocrsyngen PR, `office_pages`:**
   - the page families of §3;
   - the degradation models of §5.2;
   - tests for bidi in tables and numbers, exact boxes after skew, and the label folds.
5. **Generation, gates, sheets and decontamination**, then eval's official CLEAN on every list.
6. **The arm-registration PR,** then training through the scheduler.
7. **The result PR** with stock on every set.

**Release:** if it passes, the model ships openly (Apache-2.0 weights, CC0 data), under the open-release rule. The synthetic data and recipe ship with it.

## 8. Decisions (heocr-lead, 2026-11-18)

1. **Arm B is real-only, continued from stock.** It is the clean ablation: A against B shows what the synthetic part adds. R8b main-fold lost to stock on modern T5, so it is not a base here.
2. **Degraded real Reshumot rasters are inside the iron rule.**
   - **Why:**
     - They are faithful images of official §6 documents.
     - The font software is never copied, embedded or redistributed: only page images are used, as with any scan of a printed page.
     - R9 already trains on the same rasters under the legal strategy (2026-11-10).
   - **If Shay later rules otherwise,** the degraded-anchor part and the clean3 rasters come out of the mix, and the arms are re-registered.
3. **En dash: stock's character set is kept, with no layer surgery,** in v1.
   - **How `line_fold_v1` treats dashes.** It folds `—` (em dash) to `–` (en dash) and `־` (maqaf) to `-`. It does **not** fold `–` to `-`. Its `not_folded` entry says the sets write a spaced dash and a joining maqaf or hyphen consistently.
   - **So the charge exists.** A reference `–` or `—` costs one substitution whenever a model outputs `-`, and neither stock nor arm A or B can output `–`. Both sides pay it equally, so the comparison with stock is unaffected.
   - **The report** gives the count of reference `–` in each scored set.
4. **Fonts.** Shay gave his own go in this session on 2026-11-18. Arimo, Tinos, Cousine and Open Sans are in the fonts PR (google/fonts `7af0d90`).

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
