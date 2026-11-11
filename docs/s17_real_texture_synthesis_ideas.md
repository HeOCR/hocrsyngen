# S17: real-texture synthetic data ideas (2026-11-11)

Status: proposals. Nothing here is built or measured yet, except where a later section says so.

## Why a new phase

S16 composed training pages from glyphs cut out of real printed scans. The results on real pages so far (heocr-engine `docs/baselines.md`, R3j/R5/R6/R7, and the R8 diagnosis in heocr-engine `tasks/r8-layout-diagnosis`):

- **Synthetic lines alone make Tesseract worse.** R5 fine-tuned tessdata_best `heb` on 50k S16c mix21 lines (real-glyph included), and it is slightly worse than its base on the 38 adjudicated pages and clearly worse on the 10 bank-disjoint pages (+0.041 CER).
- **Real scanned lines help.** R6 (13.6k real lines) and R7 (95k) are the first models to beat stock Tesseract (CER 0.226 → 0.209). R7 does not beat R6 on pages, though it has about seven times the lines.
- **The remaining page error is domain, not layout.**
  - Reading order and missed regions together cost about 0.01 CER.
  - One rabbinic responsa print (*Hut ha-Meshulash*, 1820, dense small type, 137 ״/׳ marks on one page) is 4 of 38 pages and about 45% of all errors.
  - Two books make up most of the error on the 10 hard pages: a fully pointed liturgical print (704 marks on 896 letters on one page) and the title pages of a Hasidic print.
  - In-domain, R7's main residual error is short deletions (1–19 letters inside lines it reads).

**Working hypothesis:** synthetic data can help only if it keeps real scan texture, or if it targets one of these gaps. It should always be added to R7-style real lines, never used alone.

## The eight ideas

Each entry gives the gap it targets and what would make it fail.

1. **Scan-ifier learned from our own aligned pairs (S17a).** `bynli_lines_v2` holds about 100k real line crops with exact edition text. Render the same text cleanly at a matching size, and train an image-to-image model from the clean render to the real crop. Condition it on a style crop from any book, labelled or not, so it can make lines in the style of rabbinic books we have no text for.
   - *Targets:* the realism gap behind R5, and domain coverage at scale.
   - *Fails if:* the model invents or drops glyphs, which turns into label noise. Human spot checks, plus an automatic text-consistency filter, are required before any training use.
2. **Surgery on real lines.** Cut words and letters out of real lines and recombine them within one book and page, so ink, paper and type match. Insert real ״/׳ crops to make abbreviation lines.
   - *Targets:* the realism gap and the missing characters, with exact labels by construction. It is the cheapest test of the real-texture hypothesis.
   - *Fails if:* seams between pieces become a shortcut the model learns.
3. **A foundry for each unlabelled rabbinic book.** Cluster connected components (most printed Hebrew letters are separate components) on PD scans from Commons and IA. Name each cluster by majority Tesseract vote, and send only ambiguous clusters to a human (hard cases only). The result is a glyph bank per typeface, so lines can be composed in exactly the rabbinic typefaces we fail on, with no edition text needed.
   - *Fails if:* clustering merges look-alike letters (ב/כ, ו/ז, ס/ם). Use cluster purity checks.
4. **Abbreviation compressor (the text side).** Rewrite PD text into rabbinic register by contracting standard phrases (אמר רבי → א״ר, זכרונו לברכה → ז״ל), and add reference shorthand (סי׳, ע״א, וכו׳, הנ״ל). Tesseract's LSTM learns letter context, so the register matters beyond glyph shape. It feeds ideas 1–3.
   - *Fails if:* the contraction rules produce text no printer would set. Calibrate the rules on Wikisource rabbinic transcriptions (decision 0016 allows that text).
5. **Niqqud transplant.** Harvest vowel marks from the 8 pointed prints already classified in the f8f editions file. Place them on real unpointed lines using pointed versions of the same text.
   - *Targets:* pointed liturgy and poetry, ahead of the niqqud character-set step.
   - *Guard:* the works behind the scored Seliḥot page (Open Siddur Project) stay out of every text source.
6. **Hallucination vaccine.** Cut ornaments, frames, vignettes, printer's marks, stains and bleed-through from PD title pages. Train on those crops labelled empty, and on real lines with ornaments pasted beside them.
   - *Targets:* insertions (0.021 CER) and title pages; one page was read as 371 letters against a reference of 225.
7. **Deletion drills.** Synthesize the conditions that likely cause R7's short deletions: tight letter spacing, touching letters, broken type, faint thin letters (י ו ן), and small type at low pixel height. Measure deletions on dev crops (psm 13) before and after. This ties into the R8 deletion item.
8. **Physical print-and-scan loop (wild).** Print synthetic rabbinic and pointed pages built from the idea-3 banks on cheap paper. Age them (sun, coffee, folding), then scan them on flatbeds and phones, possibly as a volunteer campaign. A few hundred pages are a realism ground truth for ideas 1 and 7, not a training set.

Left out on purpose: transcribing unlabelled rabbinic scans with a large vision-language model. It is not synthetic, and it breaks the rule that labels are edition text, never OCR output. It needs its own decision.

## How each idea is judged

- Always as an add-on to R7's real lines, against an R7-recipe control run on the same lines.
- Checkpoint selection and the verdict use held-out real dev, which includes at least one held-out rabbinic Index once R8's dev set exists. Never the 38 scored pages (heocr-engine decision 0012).
- No text from a scored work, in any edition, enters a text source. This uses the same 6-gram check as the R7 line set.
- Inputs follow the legal strategy and decisions 0014–0016. Code for learned models (ideas 1 and 3) stays outside `src/hocrsyngen/`, per [learned_generation_packaging_boundary.md](learned_generation_packaging_boundary.md).

## Order

1. Ideas 2 and 7 first. They are cheap and they test the real-texture hypothesis directly.
2. Idea 1, which has the largest upside (S17a, started 2026-11-11).
3. Ideas 3–6 once R8's rabbinic dev set exists.
4. Idea 8 only if ideas 1 or 7 need a realism ground truth.
