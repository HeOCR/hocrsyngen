# Register: HeOCR calibration pack v1 captures

| Field | Value |
|---|---|
| **Set** | HeOCR calibration pack v1 (`HEOCR-CAL-V1`), pages P01–P10 |
| **Use** | **Calibration and dev only. Never test.** |
| **Purpose** | To fit scanifier v2's capture models to real phone captures: blur and defocus, noise against ISO, perspective and tilt, lighting and colour cast, JPEG, backgrounds, show-through and occlusion. Then to serve as a real-capture dev set, with exact labels, for the scanifier v2 ablation. |
| **Not this set** | PS-v1 (print-and-scan pack v1, every frame including its instruction sheet PS-00) is eval's untouched test set. No PS-v1 pixel is used to calibrate or select anything here. |
| **Decided by** | lead, with Shay's approval ("Yes, prepare it"), 2026-11-18 |

## What was printed

- **PDFs:**
  - `calibration_pack_v1.pdf`: pages P01–P08 on plain 80 g paper; P01 in colour.
  - `calibration_pack_v1_thin.pdf`: P09 and P10, which are P02 and P03 printed on thin paper (60–70 g).
  - Both are printed at 100% scale.
- **How they were made:** `make_pack.py`, rasterised at 600 dpi and placed losslessly. Their sha256s are in `summary.json`.
- **Labels:** every text line's logical-order text and box, in 600-dpi page pixels, is in `gt/Pnn.json`. So is every marker, slanted edge, grey step, colour patch and furniture box.
- **Text** (`pack_text.json`):
  - **Source:** htext pby-v3, its il_us subsets: text from Project Ben-Yehuda, public domain in Israel and the US. The htext outputs are CC0-1.0.
  - **Credit:** Text from Project Ben-Yehuda (https://benyehuda.org), prepared by Project Ben-Yehuda volunteers.
  - **Works:** one PBY work per block, 16 blocks.
  - **Filters:** every work eval reserves is excluded. No block shares a word 6-gram with any of eval's official CLEAN targets.
  - **CLEAN:** eval's official overlap check ran on this text before the PDF was finalised. The verdict is below.
  - **Selection:** the text was chosen by a synth-gen script outside this repository, because it reads eval's restricted reservation lists. Seed 20261132.

## Captures

- **Phones:** Pixel 9 Pro (`p9`), Pixel 4a (`p4a`) and Galaxy A33 (`a33`).
- **Shot list:** `shot_list.csv`, 120 frames plus 24 Telegram copies. The Hebrew sheet given to the photographer is `shot_sheet.pdf`.
- **File names:** `Pnn-<condition>-<phone>.jpg`. The page's QR code (`HEOCR-CAL-V1-Pnn`) and its ArUco ids (`4(n-1)` to `4(n-1)+3`) identify the page independently.
- **Kept as shot:** bad frames are never reshot or dropped; they are the point.
- **Originals:** exported at original quality with EXIF.

## Status

| Date | Event |
|---|---|
| 2026-11-18 | Pack designed and text selected. |
| 2026-11-18 | **eval: CLEAN.** pack_text.json sha256 `cd143ec8443b26056e84a29fc2ae5b6673f93e797f69fdbb747f6df0803cdf9f` (938 lines, 16 blocks) shares no word 6-gram with any official check_train_overlap target, the PS-00 sheet text, or the P-hist hold-out candidate pages; positive control passed. The verdict holds for this sha only. |
| 2026-11-18 | Rendered at 600 dpi: `calibration_pack_v1.pdf` sha256 `8a7f4c8cf1505e9301e414c33eecfe7ca27dadafc629b0dc98ade1d5a73fadf9`, `calibration_pack_v1_thin.pdf` sha256 `a8a6e52bdaa7dc060743d2e70c917c83b88f5385b6bf333c3ccb0a6d26bd6280`. All 40 markers and 10 QR codes decode from the PDFs. Handed to Shay for printing. |
| 2026-11-19 | **Addendum P11–P12 (pointed text)**, for fitting mark loss (lead approved; plan: `docs/niqqud_training_render_plan.md` §4). Text `addendum_text.json` sha256 `cc34b8af857a2655366fba2c22eb646a3c16b54dca087f747b5569867600ff61`: htext pby-v3 il_us PBY 3233, 5016, 6146 (fully pointed) and htext tanakh-v1 Judges 11 (WLC); PD in Israel and the US. These works and Judges 11 are excluded from every training pool. |
| 2026-11-19 | **eval: CLEAN** for the addendum text, sha `cc34b8af…` (388 word 6-grams, 0 shared with every official check_train_overlap target, PS-v1 refs, NQ1 pack refs and the D-bench text pool). The verdict holds for this sha only. |
| 2026-11-19 | Rendered at 600 dpi: `calibration_pack_v1_addendum.pdf` sha256 `4ac60160aeb862696b5cd18394cdfe95db08ce8563b93ee1acff29f673abbcf2`, plain 80 g paper, 100% scale. All 8 markers (ids 40–47) and both QR codes decode from the PDF. Shoot each page on each phone in conditions A, B, D, F and G. NQ1 captures are never calibration frames. |
