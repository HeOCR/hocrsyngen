# HeOCR calibration pack v1

A printed pack for fitting scanifier v2's capture models to real phone photos. It replaces any use of test captures for calibration; see [REGISTER.md](REGISTER.md) for what the captures may be used for.

## Build

```bash
python3 experiments/scanifier_v2/calibration_pack/make_pack.py experiments/scanifier_v2/calibration_pack/pack_text.json experiments/scanifier_v2/calibration_pack
python3 experiments/scanifier_v2/calibration_pack/shot_sheet.py experiments/scanifier_v2/calibration_pack
```

The builds need Pillow with libraqm, OpenCV (`cv2.aruco`), PyMuPDF, and Google Chrome for printing the Hebrew sheet. The fonts are hocrsyngen's bundled OFL fonts.

## Pages

Every page has the same frame:

- four ArUco markers (`DICT_4X4_50`, 12 mm) in the corners;
- a QR page-id code;
- a bottom strip with a 14 mm slanted-edge square at 5° and a 6-step grey wedge.

With these, any frame gives its page, its homography, a local edge-spread function, and the grey levels at the page foot.

| Page | Layout | Fonts |
|---|---|---|
| P01 | Full target: nine slanted-edge squares on a 3 × 3 grid, a 12-step wedge, six colour patches, and text at 8, 10, 12 and 16 pt | Frank Ruhl Libre |
| P02 | Prose, one column, 11 pt, justified, indented paragraphs | David Libre |
| P03 | News: a 22 pt headline and two 9 pt columns with a rule | Frank Ruhl Libre, Tinos |
| P04 | Ruled table: numbers, dates, details, quantities and amounts | Assistant |
| P05 | Pointed verse, 13 pt, centred, in stanzas | Frank Ruhl Libre |
| P06 | Old print: a boxed main text with Rashi-script commentary around it | Frank Ruhl Libre, Noto Rashi Hebrew |
| P07 | Mixed: headings, a bold run, a bulleted list, body text and footnotes | Heebo, Noto Serif Hebrew |
| P08 | Large type: an 18 pt date and 22 pt body | Rubik, Alef |
| P09, P10 | P02 and P03 again, to print on thin paper for show-through | — |

## Conditions (shot sheet)

| Code | Condition |
|---|---|
| A | Straight down, good light, steady |
| B | Handheld at about 1/25–1/33 s (motion blur) |
| C | Angled at 30–45° (perspective, defocus gradient) |
| D | Very dim light, ISO about 2,000–3,200 |
| E | Straight down, saved as the phone saves it (orientation errors kept) |
| F | The A frame sent through Telegram "as photo" |
| G | Adobe Scan document mode |
| H | A thin-paper page lying on another printed page |
| I | A thumb over the margin |
| J | A dark table (`Jd`) or a wooden table (`Jw`) |

Who shoots what:

- **P01:** every condition on every phone.
- **P02–P08:** A plus three of the other conditions on each phone, rotated so that each page gets all of them over the three phones.
- **P09 and P10:** H on each phone.
