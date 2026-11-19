# Synthetic document generator: design note (draft for review)

Status: design only, 2026-11-19. Nothing here has been generated or run. Owner: synth-gen. Review: eval (gold format,
measures, D-bench pinning), pipeline (what it consumes), lead (merge, the open decisions in §10).

## 0. Why, and the one idea

The main use case of `heocr` is modern printed Hebrew in varied documents. These are mostly PDFs with tables,
footnotes, headings and numbered structure, plus Word, Excel and PowerPoint files. A production tender-extraction
pipeline is the motivating consumer.

Most of the hard cases in such files come from **the program that made the PDF**, not from the content:
- visual-order text layers;
- broken or private-use ToUnicode maps;
- Type3 fonts;
- words split into single glyphs;
- tables written as loose positioned text;
- headers and footers repeated on every page;
- digits reversed inside right-to-left runs.

D-bench sets A–E reproduce these effects with PDF bytes we wrote by hand. That gives exact control, but each effect is
only our model of what a producer does.

**The idea:** write CC0 documents from a source tree we generate, then let **real producers** make the PDFs, the way
real PDFs get made: Word, LibreOffice, Chrome, Ghostscript, print-to-image and OCR. The gold stays exact because we
wrote the source. What we must engineer is how the gold **survives** each producer (§3.3), and how we prove it did.

**Scope:**
- **In:** a source model, authoring writers, a matrix of producer drivers and post-chains, a gold-survival verifier,
  manifests, templates, a mix calibration and a pilot.
- **Out:** model training, any headline claim (synthetic is never the benchmark, §7), and anything that reads real
  corpus files (calibration uses aggregates that eval supplies, §4.2).

```text
 source tree (JSON)  ──►  authoring writers  ──►  producers  ──►  post-chains  ──►  verifier  ──►  set + manifest
 hdoc_tree.v1             DOCX XLSX PPTX         Word, LO,        gs re-distil,     gold survival,
 (gold lives here)        HTML Typst (ODT RTF)   Chrome, Typst…   image→PDF, OCR    colour twin,
                                                                                    weirdness census
```

## 1. The producer matrix

**Versions.**
- **Checked on this Mac (2026-11-19):**
  - Microsoft Word, Excel and PowerPoint 16.115;
  - LibreOffice 26.2.5.2;
  - Google Chrome 157.0.8103.80, plus Chromium.app;
  - Keynote and Numbers;
  - Tesseract, poppler `pdftotext`, pandoc and `cupsfilter`.
- **Not installed:** Pages, Ghostscript, qpdf/mutool, Typst, a TeX distribution, WeasyPrint and ocrmypdf.

**The weirdness column is a hypothesis per producer.** The pilot (§9) replaces it with a measured **weirdness census**.
For every output PDF, the census records:
- the producer and creator strings;
- the font types (TrueType, CID, Type3 or Type1) and whether ToUnicode is present;
- the share of private-use code points;
- the stream order, judged by D-bench's T2 signal and by the verifier's own reorder;
- whether there are space glyphs or spaces by position only;
- the glyph-run length (single-glyph runs mean split words);
- the table encoding (ruling paths present or not, cell text in one run or many);
- whether headers and footers repeat as text.

A hypothesis that the census does not confirm is dropped from the template mix, not forced.

| # | Producer | Automation, reproducibly | Expected weirdness (to be measured) | Priority |
|---|---|---|---|---|
| P1 | **Word for Mac** (16.115) | `osascript` drives Word: open DOCX → `save as` PDF (`format PDF`, "best for printing", the local Quartz route; **never the online-conversion option**, which uploads the document) → close without saving. A fresh Word process per batch, a timeout per document, and a watchdog for modal dialogs. The version is read from Info.plist into every manifest. Auto-update is paused during a run. | Quartz PDF, embedded TrueType subsets, mostly logical order. Footnote separators and repeated headers are drawn as text. Our numbering is laid out by Word itself (labels as Word renders them). The Mac route may differ from Windows Word's PDF route: the visual-order text layers D-bench check (a) looks for may be a Windows-only effect. | pilot |
| P1w | **Word for Windows** | Only on a Windows host with Office. There is none today: RunPod has no Windows, and CI Windows runners have no Office. Later, if a runner exists: PowerShell COM `ExportAsFixedFormat`. | Microsoft's own PDF writer: likely the main source of real visual-order Hebrew layers and of per-glyph runs. | later, needs a host |
| P2 | **LibreOffice** (26.2.5.2) | `soffice --headless -env:UserInstallation=file://<fresh dir> --convert-to 'pdf:writer_pdf_Export:{…}'` with pinned filter options (tagged or untagged, PDF/A on or off, embed fonts). The same version as a Linux build for pod-scale runs. | Logical order and good ToUnicode, usually. Its own DOCX import changes numbering and layout (D-bench check (b) knows where). Tables are positioned text with ruling paths. Optional tagged PDF gives a structure tree pipeline could use. | pilot |
| P3 | **Pages** | Not installed (free from the App Store). AppleScript `export … to PDF`. | Quartz PDF, Apple's text layout. Its DOCX import is lossy (numbering, notes). | optional |
| P3k | **Keynote / Numbers** (PPTX / XLSX in) | AppleScript `export … as PDF`. | Slides and sheets through Quartz. Text boxes become separate runs. | optional |
| P4 | **Google Docs export** | Needs a Drive API OAuth client on an account. **Not in v1**: no new accounts, and the existing project account would need an OAuth app (Shay's call, §10). | Its own layout engine; Skia-like PDFs. | deferred |
| P5 | **Chrome / Chromium print-to-PDF** from HTML | `chrome --headless=new --no-pdf-header-footer --print-to-pdf=… file://…`, pinned to a **Chrome for Testing** build (a versioned download, not the auto-updating browser). CSS paged media for size, margins and `@page` headers. | Skia PDF. Hebrew glyph runs may be stored in visual order, so the text layer may come out reversed in some readers. Table cells are separate runs; `thead` repeats on every page; a `position: running()` header repeats. | pilot |
| P5w | **WeasyPrint** from the same HTML | `uv run --with weasyprint==<pin>`; Pango and HarfBuzz from the pinned environment. | Pango shaping, logical-order ActualText-like runs; good paged-media support (footnotes `float: footnote`). | phase 2 |
| P6 | **Typst** (or LuaLaTeX) | The Typst binary, pinned by version and sha256, compiles a `.typ` source written from the tree. LuaLaTeX only through a pinned TeX Live container on a pod (a 4 GB+ install is not worth it locally). | A typesetter's PDF: ligatures, kerning, justified Hebrew, real footnotes. Reading order follows the source. | phase 2 |
| P7 | **macOS Quartz print** | `cupsfilter` (PDF to PDF through the Quartz filter), or printing a document through the macOS print system to "Save as PDF". | Re-encodes the fonts and may flatten text to a different encoding. It is the "printed to PDF" route of many office users. | phase 2 |
| P8 | **Ghostscript re-distil** | `gs -sDEVICE=pdfwrite` at a pinned version, with variants: default; `-dPDFSETTINGS=/screen`; `-dNoOutputFonts` (all text becomes vector paths); and a PostScript round trip (`ps2write`, then back). | The classic breaker of text layers: ToUnicode dropped or rebuilt, fonts turned to Type3, text turned to outlines (T6 everywhere, or a vector-only page). | phase 2, high value |
| P9 | **Print to image → PDF** | Rasterise any P1–P8 output with pinned poppler or pymupdf at 150, 200 or 300 dpi. Optionally degrade it with hocrsyngen's scan models (`office_scan`, `photocopy`, `phone_photo`; scanifier v2 when calibrated). Encode as JPEG at quality 50–95, then wrap it with `img2pdf` (lossless wrap) or re-print it through P7. Seeds drive everything. | Image-only pages (T5): the JPEG grain hazard of set E, scan noise, skew and lost thin rules. | pilot (clean 200/300 dpi only), phase 2 (scanifier) |
| P10 | **OCR'd layer** | `ocrmypdf` at a pinned version, over P9's output, with stock Tesseract `heb`, a correct OCR "sandwich" layer. Run with `-l eng` or a wrong page segmentation mode, the same tool gives a **real garbage layer** (T4), instead of our permuted one. | T1 with an OCR layer (`text_layer_is_ocr`), and T4: wrong letters in an invisible layer over a correct image. | phase 2 |

**Chains.**
- A document's producer route is a chain, for example `DOCX → P1 → P8(NoOutputFonts)` or `DOCX → P2 → P9(200 dpi,
  photocopy) → P10(eng)`.
- Every chain step records its tool, version, options and the sha256 of its input and output.
- The manifest stores the chain, so any T-class mix can be asked for by chain.

**Reproducibility tiers.**
- **Tier B (byte-reproducible):**
  - our writers (DOCX, XLSX, PPTX, HTML and Typst source);
  - P9 and P10 with pinned libraries;
  - P2, P5, P6 and P8 after metadata normalisation: CreationDate, ModDate and /ID are reset with a pinned `pikepdf` pass.
  - The pilot checks for each producer that two runs give identical bytes after that pass.
- **Tier V (version-reproducible):**
  - P1, P3, P3k and P7.
  - The same version gives the same layout, but not the same bytes.
- **Storing outputs.** Tier V outputs are kept as artifacts with their sha256. They are not regenerated: a D-bench pin
  stores the files themselves (§8). Tier B sets commit only the manifest and gold, as sets B–E do.

## 2. Formats in

| Source written from the tree | Producers | Notes |
|---|---|---|
| **DOCX** | P1, P2, P3, P1w | Our own WordprocessingML writer, extending the style of `heocr` `tests/synth/docx.py`. It writes real `numbering.xml` (abstractNum/num, `lvlRestart`, `startOverride`, Hebrew counting), styles, footnotes and endnotes, sections with different headers and footers, tables with `gridSpan` and `vMerge`, text boxes, columns and `bidi` paragraphs. No python-docx: we need every feature on purpose. |
| **DOCX, re-saved by a producer** | P1, P2 | Word or LibreOffice opens our DOCX and saves it as DOCX. The result is a *producer-written* DOCX, with rsids, its own run splitting and compatibility settings, for the `heocr` DOCX route. The gold is unchanged; the verifier re-reads the text. |
| **XLSX** | Excel (AppleScript), P2, P3k | Spreadsheet look (§4): right-to-left sheets (`rightToLeft`), merged cells, number formats (₪, %, dates), print areas, page setup with repeated title rows, and several sheets. Extends `tests/synth/xlsx.py`. |
| **PPTX** | PowerPoint (AppleScript), P2, P3k | Slide decks: title and bullet placeholders, tables and text boxes with RTL paragraphs. Extends `tests/synth/pptx.py`. |
| **HTML + CSS** | P5, P5w | The same tree written as semantic HTML (`h1`–`h4`, `ol` with `list-style-type: hebrew`, `table` with `rowspan`/`colspan`, footnotes as `aside`) with paged-media CSS. |
| **Typst** | P6 | The same tree as a Typst source. |
| ODT, RTF (optional) | P2 (`--convert-to odt|rtf`), P1 (save as) | Converted from the DOCX, not written directly. The gold rests on the tree, and the verifier checks the conversion. |
| **The PDFs out** | all | Every PDF from every chain, with its chain record. |

**Writers must agree.**
- The tree, not a writer, defines the document. Each writer has a test that its output, re-read by our own reader,
  gives back the tree's text and structure.
- Our own reader is a small, independent verifier, never `heocr`.
- Feature support differs by format. A tree feature a writer cannot express (for example footnotes in PPTX) is dropped
  for that writer and recorded as `not_expressible`. It is never faked.

## 3. The structure model and the gold

### 3.1 One source tree per document (`hdoc_tree.v1`, eval owns the gold format)

```text
document
  meta: template, look, seed, page size and orientation, columns, base font, text sources and licences
  furniture: header(s), footer(s) per section (first page, odd, even), page number format
  body: [block]
block :=
  heading {level 1-4, numbering ref?, text}
  paragraph {runs, align, numbering ref?, note anchors?}
  list {style: bullet | decimal | hebrew_letters | parenthesised, items: [block]}
  table {grid: rows x cols, cells: [{r, c, rowspan, colspan, header?, blocks}], ruled: all | header | rows | none,
         repeat_header?, spans_pages?}
  note {kind: footnote | endnote, anchor id, blocks}
  image_with_text {kind: chart | stamp-like mark | scanned table | logo-like emblem, text: [lines], labelled: bool}
  page_break | section_break {new furniture, columns, orientation}
run := {text (logical order, NFC), lang: he | en | num, style: b/i/u/size/font?, field?: page | numpages}
numbering := {abstract id, levels: [{format: decimal | hebrew1 | hebrew2 | lowerLetter | …, text pattern, start,
              restart}], instances: [{num id, startOverride?}]}
```

**Text content:**
- **Prose:** text comes from the open sources only:
  - htext CC0 (the `il_us` subset for anything public);
  - PD-IL Reshumot text (training and tuning only; its US status is not asserted, so it is excluded from a public CC0
    release unless lead rules otherwise, §10).
  - Text passes eval's official CLEAN check against reservations before any training use. Dev and test units are
    excluded at the pool level, as in the office-print pools.
- **Generated values, by seed:**
  - amounts (₪ before or after, thousands separators, decimals, negatives in parentheses);
  - dates (`1.1.2026`, `01/01/26`, Hebrew month names);
  - percentages and ranges;
  - phone numbers;
  - catalogue and item numbers (`3.2.1`);
  - Latin product names, e-mail addresses and URLs inside Hebrew sentences;
  - ID-like numbers. These are **made to fail the Israeli check digit**, so a generated ID can never be a real
    person's.
  - Names come from a generated pool, and authorities are generic (`משרד הדוגמה`).
- **Mixed RTL/LTR:** a run's `lang` is explicit in the tree. The gold is logical order. The expected visual order is
  computed by the verifier (python-bidi, both implementations as in set D), and never by `heocr`.

### 3.2 What the gold holds

| Gold layer | Content | Basis |
|---|---|---|
| blocks | id, type, level, logical-order text (NFC), section label, parent | tree (exact) |
| reading order | the sequence of body block ids; furniture and notes in their own sequences | tree (exact) |
| tables | the cell grid: row, column, spans, header flag and cell text; `repeat_header` | tree (exact) |
| notes | note id → anchor block id and offset; note text | tree (exact) |
| furniture | header and footer text per page | tree + producer (pages known only after layout) |
| section labels | the label each numbered block shows | **two bases:** `model` (our numbering model) and `producer` (what the producer rendered, read back, §3.3). Scored apart when they differ, as D-bench check (b) does. |
| pages | page of every block and line; line breaks; hyphenation | producer (observed, verified) |
| geometry | block and cell boxes per page, after layout | producer, through the colour twin (§3.3) |
| drawn text | blocks or runs that exist only as image or vector | chain (P8 `NoOutputFonts`, P9, `image_with_text`) |
| losses | text the producer did not render (clipped cells, overflow, missing glyphs) | verifier, marked `not_rendered`; readers are not expected to output it |

### 3.3 How the gold survives each producer, and how we prove it

The tree fixes the *what*. The producer decides the *where*: pages, lines, labels, clipping. Four checks close that gap.

1. **The colour twin (geometry, page assignment, clipping).**
   - For each document, the writer also emits a twin that differs only in colour. Every block, and every table cell, is
     coloured a unique near-black (RGB with the block index in the low bits; a range a human cannot see).
   - Colour does not change layout. The verifier confirms that by comparing glyph positions between the twin and the
     real PDF, which must be equal within 0.1 pt.
   - Rasterising the twin then gives each block's pixels: its boxes, its pages, and whether any of it is missing (a
     block whose pixel mass is far below its glyph count's expectation is `not_rendered`, for example text clipped by
     a fixed-height cell).
   - The twin is a verification artifact and is never shipped. It works for any producer that keeps colours: P1, P2,
     P3, P5, P6 and P7. P8–P10 inherit the geometry of their input.
2. **The producer's own export (labels, text).**
   - Word saves the same document as plain text (list labels included), and can freeze labels (`ConvertNumbersToText`
     on a copy).
   - LibreOffice exports text (`--convert-to txt:Text`).
   - Chrome's labels come from our CSS counters; they are checked against the PDF.
   - The exported labels become the `producer` label basis. Disagreements with the `model` basis are counted per
     numbering feature. That is the numbering check (b), repeated with real producers.
3. **Text-layer read-back (text survival).**
   - The verifier reads each PDF's text layer with two independent extractors (poppler, pymupdf), plus our own bidi
     reorder for visual-order layers.
   - It aligns the result to the gold blocks: every gold character is found, or explained (`not_rendered`, a drawn
     block, a missing glyph).
   - The read-back result is not gold. It is the evidence that the gold describes what is on the page, and it is what
     the weirdness census measures.
4. **Image read-back (sanity, sampled).**
   - Stock Tesseract on a rasterised sample of each chain's pages must reach a sane CER against the gold, as for set B.
   - A failure points at a font that did not embed, or a substitution.
   - `pdffonts` also checks that the embedded fonts are the requested ones, which catches silent substitution.

A document goes into a set only if all four pass. The share that fails, per producer and per feature, is itself a
pilot result. A producer that loses gold often is a finding, not something to hide.

## 4. Document templates by look, and the mix

### 4.1 Templates

Templates are placed by **look**, as decision 0018 does for units, not by origin.

| Template | Look | Typical tree |
|---|---|---|
| `tender` | a tender or call for bids | front-matter letter, definitions, 2–4 level numbered conditions with Hebrew sub-levels, a bill-of-quantities table spanning pages (merged headers, totals), forms in appendices, signature blocks, footnotes, header with a reference number, footer with a page counter |
| `report` | a report | title page, table of contents (a producer-updated field, so its gold is `producer` basis), headings 1–3, paragraphs, figures with Hebrew labels (charts as `image_with_text`), tables with notes, footnotes or endnotes, two-column sections |
| `form` | a form | labelled fields, underlines and boxes, checkboxes, tables with empty cells, small print, a stamp-like mark |
| `letter` | a letter | letterhead emblem, date and reference lines, `לכבוד`, subject (`הנדון:`), body, closing, generated signature |
| `gazette` | a gazette or notices page | two or three columns, numbered notices, small type, running headers, rules between columns |
| `deck` | a slide deck (PPTX) | title slide, bullet slides with 2 levels, a table slide, a chart slide with labels |
| `sheet` | a spreadsheet (XLSX) | RTL sheet, a header block, a budget or quantities table with formulas shown as values, merged title cells, repeated title rows when printed |

Each template has seeded variation: margins, fonts, sizes, ruled or unruled tables, column count, density, and the
share of mixed-direction runs.

### 4.2 Calibrating the mix to real documents (aggregates only)

**What is calibrated:**
- the template shares;
- the producer-chain shares;
- the T-class shares that result;
- the tables-per-page and cells-per-table distributions;
- the page-count distribution;
- the number density.

**Targets come from eval.** Eval measures them on the D-bench real **dev** split and sends them as an aggregate table:
- the producer and creator string histogram (normalised to producer families);
- the T2 rate per producer family;
- the T-class distribution;
- tables per page and cells per table, as quantiles;
- pages per document;
- the share of documents with footnotes, multi-column pages or repeated headers.

**Rules:**
- **Never test.** I never read the corpus files, only eval's table. The table is published in this repo only as
  aggregates, and only if eval agrees (D-bench §7).
- **Until the table arrives,** the pilot uses a flat mix.
- **A chain whose census result does not match the real producer family it stands for gets no weight.** For example,
  Mac Word may not reproduce Windows Word's visual order. The gap is reported.

## 5. Fonts

| Use | Fonts | Licence |
|---|---|---|
| **public and training** | Culmus (David CLM, Frank Ruehl CLM, Miriam CLM, Nachlieli, Hadasim, Simple, Shofar, Keter YG …); David Libre, Frank Ruhl Libre, Miriam Libre; Noto Sans/Serif/Rashi Hebrew; Alef, Heebo, Rubik, Assistant; Arimo, Tinos, Cousine (metric-compatible with Arial, Times New Roman and Courier New, so office layouts keep their line breaks) | OFL-1.1, Apache-2.0, and Culmus's GPL-2 **with the font exception** (embedding in a PDF does not make the document GPL). Lead to confirm the Culmus reading (§10). Every face is pinned by sha256, as in hocrsyngen's governed fonts. |
| **local only** | Microsoft and Office fonts (Arial, Times New Roman, David, Miriam, Narkisim, FrankRuehl as shipped with Office) | The lo_pdf rule: no derived file is public or used in training; aggregate scores may be public. These variants live only on this Mac, are never committed, and their manifests carry `local_only: true`. |

**Installing fonts for the producers.**
- Word and Keynote see only installed fonts.
- The open faces go into a dedicated user font folder, activated for the run. That needs Shay's OK (§9).
- LibreOffice and Chrome can use a private fontconfig directory instead.

**Hold-outs.**
- One open face per look family is held out of training (as Tinos is in office-print) and used only by tuning and gate
  sets.

## 6. Measures (proposed; eval owns the definitions)

Beyond character, word, line and page CER, the sets let eval score the following, all against the tree gold:

| Measure | Proposal |
|---|---|
| table structure | TEDS and TEDS-struct per table; cell-level F1 on (row, column, normalised text), exact and CER ≤ 5%; span accuracy for merged cells; a page-spanning table counted as one table |
| reading order | normalised Kendall tau between the gold and output block sequences, after block alignment; a separate count of body-furniture interleavings (a header read into the body) |
| headings and sections | heading recall and precision with level accuracy; section-label exact match per level, on both label bases (§3.2) |
| footnotes | attachment accuracy: note text found, and anchored to the right block; notes leaked into the body text |
| silent loss | the share of gold characters (and blocks) missing from the output **with no warning** from `heocr`; reported apart from losses it flags |
| numbers | exact match of every number, amount and date token (digits and separators), as in office-print's number misses; digit order in RTL runs |
| mixed direction | the share of lines whose LTR runs come out in the gold's logical order |
| classification | T-class confusion per producer chain (the census gives each page's true class) |

**All of these are proposals for eval to accept, change or reject.** None is used in a report before eval defines it.

## 7. Uses and splits

| Use | Split | Seeds | Notes |
|---|---|---|---|
| **tuning** (pipeline thresholds, repair rules) | `tune` | the open tuning base | Every threshold may be tuned here, as on D-bench layer 1. |
| **regression** (pipeline CI and release checks) | `regress` | a frozen base | Pinned by manifest sha in D-bench (§8); small (a few hundred pages); changes only by a new pin. |
| **training** (any future layout, table or reading-order component) | `train` | disjoint seed ranges | Never shares a seed, a held-out font or a held-out template variant with `tune`, `regress` or `gate`. Decontaminated text only. |
| **public CC0 dataset** | `release` | its own base | Open fonts, CC0 `il_us` text, generated values. Goes through hocrgen governance to the public synthetic dataset repository. |
| **gates** | `gate` | a fresh base drawn when the gate is registered (as amendment 6 did) | Generated once, pinned, never inspected before the gate runs. |

**Synthetic results are never a headline claim. Real data stays the benchmark.** Synthetic sets diagnose, tune and
regress. A gate may carry a synthetic cell only as a secondary cell, as the set D cell is agreed in principle.

**The D-bench generator rule.**
- D-bench requires that its generators are never used by training generators.
- This design has one generator serving both. It keeps the rule's intent through disjoint seeds plus held-out axes:
  fonts, template variants, and one producer version or chain per look.
- That amends the rule, so **eval and lead must accept it** (§10). The fallback is two code paths: D-bench pins a fork,
  and training never imports it.

## 8. Ownership and repositories

**Roles:**
- **synth-gen** generates. It owns the writers, the producer drivers, the verifier and the census.
- **eval** owns the gold format (`hdoc_tree.v1` and the gold layers), the measures, and which sets are pinned into
  D-bench.
- **pipeline** consumes: `tune` and `regress`, and the census for its classifier.
- **lead** merges and rules on §10.

**Where the code lives: a new public repository, proposed `HeOCR/hdocsyngen`.**
- hocrsyngen's scope is image and line samples. Its `AGENTS.md` keeps external application drivers and heavy
  dependencies out of its baseline.
- A document generator that drives Word, LibreOffice and Chrome is a different tool, with different pins.
- It uses hocrsyngen only through its CLI and file contracts (the scan models, for P9), never by importing it.
- The gold schema lives in that repository with eval as its required reviewer. A schema change needs eval's approval.

**How D-bench pins a set.**
- A file `dbench/synth/hdoc/<set>/PIN.json` records:
  - the hdocsyngen commit;
  - the seed base;
  - the chain list with tool versions;
  - the manifest sha256.
- **Tier B sets** commit the manifest and gold only, and are regenerated and validated before a run, like sets B–E.
- **Tier V sets** (Word, Pages, Keynote, Quartz) also store the produced files, in restricted-eval, with their sha256,
  because they cannot be regenerated byte for byte.
- Sets with `local_only` fonts never leave the Mac and are never pinned in a pushed repository. Only their aggregate
  scores are.

## 9. Pilot plan (after this note is reviewed)

**Scope.**
- **Inputs:** 48 source trees, 24 `tender` and 24 `report`, from a pilot seed base. Text comes from htext CC0 `il_us`,
  after eval's CLEAN check.
- **Fonts:** open fonts only.
- **Routes:**

  | Route | What it makes |
  |---|---|
  | DOCX → Word for Mac PDF | 48 PDFs |
  | DOCX → LibreOffice PDF | 48 PDFs |
  | HTML → Chrome for Testing PDF | 48 PDFs |
  | DOCX re-saved by Word and by LibreOffice | 96 DOCX |
  | Rasterised to image-only PDFs at 200 and 300 dpi, no scan model | a sample of 12 per producer |

  That is about 150 PDFs and 100 DOCX in all.

**Deliverables:**
- the writers (DOCX and HTML), the three drivers, the verifier (§3.3, all four checks) and the census;
- a pilot report, for lead, eval and pipeline, with:
  - the weirdness census per producer;
  - the gold-survival rate per producer and feature;
  - the label-basis disagreements per numbering feature;
  - the byte-reproducibility results;
  - stock Tesseract and `heocr` aggregate scores per chain, as a smoke test, not a claim;
  - a go or no-go for phase 2 (P5w, P6, P7, P8, P10, XLSX and PPTX, then scale).

**Cost and time.**
- **Compute:** local Mac only, no pod, $0.
  - Word export takes about 3–8 s a document. LibreOffice and Chrome take about 1–2 s.
  - The verifier rasterises colour twins at 150 dpi, about 1 s a page.
  - The pilot run is under an hour of wall time, queued through the power scheduler like any heavy job.
- **Building:** about two working days of synth-gen session time: writers about 0.75 day, drivers about 0.5,
  verifier and census about 0.75.
  - Eval's review of the gold schema and measures, and pipeline's first look, come on top of that.
- **At scale (indicative):**
  - 10,000 documents take about 15–20 h of Word on the Mac, in power-scheduler windows.
  - The LibreOffice, Chrome and Ghostscript routes run on a pod for a few dollars.
  - Word is the bottleneck, and the reason a Windows host would matter.

**What the pilot needs from Shay:**
1. **macOS Automation permission:** allow the terminal (or the runner process) to control Microsoft Word through
   AppleScript. This is a one-time system prompt that a session cannot answer.
2. **Word's file access:** Word for Mac is sandboxed. Shay grants it access to the pilot's working folder once, or
   the pilot works inside Word's container folder.
3. **Word version:** pause Microsoft AutoUpdate for the pilot, so all documents use 16.115.
4. **Fonts:** an OK to install the open Hebrew fonts into a user font folder (they are not installed today), so Word
   can use them.
5. **Downloads:** an OK to download a pinned Chrome for Testing build, and to install Ghostscript and qpdf with
   Homebrew for phase 2.

Nothing else: no accounts, and no money.

## 10. Open decisions

**For lead:**
1. The new repository `HeOCR/hdocsyngen`, or a subpackage in hocrsyngen.
2. Reshumot text in the public CC0 release: excluded (proposed), or included with its US status flagged.
3. The Culmus licence reading: GPL-2 with the font exception, so embedded output is free of the GPL.
4. Google Docs (P4): whether to create an OAuth client on the project account.

**For eval:**

5. Owning `hdoc_tree.v1` and the gold layers (§3), and the two label bases.
6. The measures (§6).
7. The aggregate dev table for calibration (§4.2), and whether it may be published.
8. The amendment to the D-bench generator rule (§7).

**For pipeline:**

9. What `regress` must contain for its CI (size, chains).
10. Whether the tagged-PDF structure tree (P2) and the census per page are useful inputs.

— synth-gen[claude/claude-code#shay-macbook-m4]@heocr/opensource
