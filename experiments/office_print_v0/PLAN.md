# Office print v0: synthetic training data for a model that beats stock heb on modern office print

**Status:** plan for review (heocr-lead). Nothing is generated or trained before the lead approves it.
**Task:** heocr-lead, 2026-11-18, approved by Shay. It serves decisions 0019 and 0020, the `heocr` pipeline's OCR route.
**Owner:** synth-gen. heocr-eval owns every gate, split and overlap check. Data-collection owns the real lines.

## 1. Why

- **Where stock stands.** The `heocr` OCR route runs stock Tesseract `heb` (tessdata_best, sha256 `dbaa827a…abdae5`) by default, because none of our models beats it on modern scans.
- **The weakest gate cells are all modern-print OCR:**
  - PDF T5 office-font scans;
  - scanned tables;
  - T4;
  - number recall against Docling (dates, amounts, ₪, %).
- **What S17 and the R-series taught:**
  - Our models were trained toward mid-century books.
  - More data of the same kind stops helping. The S17a dose arm gained nothing over v1.1 and lost on Silman (hocrsyngen#101).
  - What is missing is the **office look**: office fonts, numbered structure, tables, numbers, and office-scan, photocopy and phone degradation.

## 2. What "beats stock" means

The final judge is **eval's registered D-bench release gate** (proposal §5.4: beat or tie every baseline in every format and class). This plan only names the cells this work targets. **The exact cell definitions, measures and current stock values come from heocr-eval, and §2.1 is filled from their reply before review.**

### 2.1 Target cells (gate, test split, eval-only)

| Gate cell | Measure | Baseline to beat |
|---|---|---|
| PDF T5, office-font scans | CER/WER in reading order (`line_fold_v1`) | stock heb (and every baseline) |
| Scanned tables | table cells, text and position | stock heb, Docling |
| T4 (garbage layer → OCR) | CER/WER in reading order | stock heb |
| Number recall | exact numbers and amounts (dates, ₪, %, amounts) | Docling, stock heb |

- I do not read the test split, eval_refs/ or any runs/*test*.
- The gate is run by eval, once, on the model the dev rule (§2.2) picked.

### 2.2 Development rule (fixed before any training run, at the arm-registration PR)

- **Selection:** a checkpoint is picked on the synthetic held-out `office_val` only (§5.1), by line_fold_v1 CER, as the R-series does.
- **Primary dev decision, on each dev counterpart eval names for the four cells:** Δ = CER(stock) − CER(model).
  - The model "beats stock on dev" when the 95% paired cluster bootstrap lower bound of Δ is above 0 on the T5-office and table counterparts.
  - On the number counterpart, the measure is number exact-match recall. The model must not lose there: the upper bound of Δrecall(stock − model) must not be above 0.
  - The bootstrap uses 10,000 resamples, seed 0, and clusters by document or page.
- **Guards, no loss against stock:**
  - OLB Reshumot dev v1_dev;
  - the new-printed dev books: Kevar and Yedi'ot held-out lines, Brainin IA, Brainin NLI, Silman.
  A loss means the whole interval of CER(model) − CER(stock) lies above 0.
- **Only a model that passes on dev goes to eval's gate run.**
- **Reporting:** every table shows stock tessdata_best next to the model, plus R8b main-fold.

## 3. Pages

Generated page images come with exact line, cell and region boxes and the logical text. Line crops are cut from the page after degradation, so a crop holds what a real scan's line holds: ruling remnants, neighbour ascenders and stamp ink.

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
| **Reshumot law and regulation text: the train split of reshumotlines_v2 `clean3`** (data-collection; born-digital Sefer HaChukim and Kovetz HaTakanot, publisher glyph layer) | running text, numbered sections, table labels | §6 (laws and regulations), `pd_israel.basis = s6_official_text` |
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
  - **Exclusion by provenance:** every text tied to eval's reserved sets. That covers the new print-and-scan pack, the mid-century set (test, dev, dev_retired), D-bench §5.1 synthetic documents and their templates, P-mod eval booklets, and all R-series and OLB dev lists. It also honours data-collection's DROPS chain (reshumotlines_v2 clean3, and the 19 vendor-hit lines).
  - **Word 6-gram exclusion** against the same pools, under both tokenisations, as in S17a `make_texts_v2.py`.
  - **eval's `check_train_overlap.py` on every final list.** A list counts as CLEAN only when the official run passes. I send each list with its path and sha256.

## 5. Fonts, degradation and validation

### 5.1 Fonts (iron rule: free fonts only; licence and sha256 in the manifest)

- **In the repository:** David Libre, Frank Ruhl Libre, Miriam Libre, Alef, Assistant, Heebo, Rubik, Noto Sans Hebrew and Noto Serif Hebrew (all OFL).
- **To add, office-metric equivalents from google/fonts at a pinned commit:**
  - **Arimo** (Arial-metric), **Tinos** (Times-metric) and **Cousine** (Courier-metric), all Apache-2.0 with Hebrew glyphs;
  - **Open Sans** Hebrew (OFL);
  - **Liberation Sans** if its release carries Hebrew (OFL).
  - Each gets a coverage check and a bidi test, as in #100. **Downloading them needs Shay's own go**, as the #100 download did.
- **Never used:** proprietary faces (Arial, Arial Unicode MS, system David, Narkisim, Miriam, Times New Roman, FrankRuehl CLM, or any Windows or Office font). The manifest refuses any face it doesn't list (render-lines rule).
- **Held-out face:** one face (proposal: **Tinos**) is used only in `office_val`, to measure how well the model reads a face it has not trained on.

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
- **Dev counterparts:** whatever eval names for each gate cell (§2.2), scored only after the arm is fixed.
- **No gate test document, no D-bench §5.1 template and no print-and-scan-pack page** is used to tune anything.

## 6. Mix, sizes and training

| Part | Lines | Notes |
|---|---|---|
| **O1 synthetic office lines** | 120,000 (from about 6,000 pages; cells count as lines) | §3–5 |
| **Real modern anchor: reshumotlines_v2 clean3** | 70,665 | born-digital Reshumot lines (data-collection), as in R9 |
| **Real modern anchor, degraded** | 35,000 of the clean3 page rasters run through §5.2 | real layout and real typesetting with synthetic degradation; see §8 question 2 |
| **Real scans: OLB Reshumot train scanned lines** | 60,000 (seeded sample of 136,903) | anti-forgetting for real scan noise |
| **Total** | about 286,000 | |

- **Order:** seeded shuffle of the whole list, as lstmtraining reads in order. Add-ons are inserted at random positions.
- **Arms.** Two, run in the two scheduler slots once they free up.
  - **A:** continue from **stock tessdata_best heb**, using its unicharset with no layer surgery. Training uses the full mix, lr 1e-4, one epoch, a snapshot every 20 minutes, the R-series recipe otherwise.
  - **B (lead's decision, §8):** the same as A without O1 and the degraded anchor, so it is real-only. Continued from stock, it tells whether the synthetic part is what helps.
- **Compute:** about 286k iterations (one epoch), so about 4 h per arm on this machine (the dose arm ran 214,828 iterations in 2 h 51 min). Training runs **only through tasks/power-scheduler, on AC power, with at most 2 heavy jobs**. Both slots are busy now, so generation and lists come first.
- **Registration.** The arm decision rule (§2.2) is pushed as its own commit before either arm starts, as in the S17a dose arm.

## 7. Deliverables and order

1. **This plan**, reviewed by the lead.
2. **Fonts PR:** Arimo, Tinos, Cousine, Open Sans and Liberation, after Shay's go for the download.
3. **hocrsyngen PR, `office_pages`:**
   - the page families of §3;
   - the degradation models of §5.2;
   - tests for bidi in tables and numbers, exact boxes after skew, and the label folds.
4. **Generation, gates, sheets and decontamination**, then eval's official CLEAN on every list.
5. **The arm-registration PR,** then training through the scheduler.
6. **The result PR** with stock on every set.

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
4. **Fonts.** Arimo, Tinos, Cousine and Open Sans are downloaded only after Shay's own go in this session. A relayed approval is not enough. Until then the work stays at plan and code with the faces already in the repository.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
