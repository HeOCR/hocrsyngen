# Printed Book Page Templates (S11c)

Book-page templates give a layout segmenter the pages it has never seen: dense printed books. They are for HeOCR's
R4f segmenter (`HeOCR/heocr-engine`).

## Why

- **The failure:** heocr-engine's R4d segmenter was trained only on letters, notes, archive cards and ledgers.
  - Its training lines have a median width of 0.07 of the page.
  - On 38 real Wikisource book pages it found a median of 165 "lines" against Tesseract's 27. It drew word-sized
    boxes and missed a fifth of the lines.
- **The real pages:** book lines are a median 0.35 of the page width, set as dense justified prose. Many books add
  two columns, running headers, footnotes or commentary blocks around a main text.

## Templates

| Template id | Recipe id | Base family | Degradation preset | Font id | Second font |
| --- | --- | --- | --- | --- | --- |
| `book_page` | `book_page_prose_v1` | `book_page` | `book_scan_soft` | `frank-ruhl-libre` | — |
| `book_page_thumbnail_scan` | `book_page_prose_thumbnail_v1` | `book_page` | `book_scan_thumbnail` | `david-libre-regular` | — |
| `book_page_two_column` | `book_page_two_column_v1` | `book_page_two_column` | `book_scan_soft` | `david-libre-regular` | — |
| `book_page_two_column_thumbnail_scan` | `book_page_two_column_thumbnail_v1` | `book_page_two_column` | `book_scan_thumbnail` | `frank-ruhl-libre` | — |
| `commentary_page` | `commentary_page_rashi_v1` | `commentary_page` | `book_scan_soft` | `frank-ruhl-libre` | `noto-rashi-hebrew` |
| `commentary_page_thumbnail_scan` | `commentary_page_rashi_thumbnail_v1` | `commentary_page` | `book_scan_thumbnail` | `david-libre-regular` | `noto-rashi-hebrew` |
| `book_title_page` | `book_title_page_frame_v1` | `book_title_page` | `book_scan_soft` | `frank-ruhl-libre` | — |
| `book_title_page_thumbnail_scan` | `book_title_page_frame_thumbnail_v1` | `book_title_page` | `book_scan_thumbnail` | `david-libre-regular` | — |

Each page draws its layout from the seeded randomizer.

- **`book_page`:**
  - an optional running header, with a centred title and the page number at either outer corner, or a page number
    at the bottom centre;
  - an optional rule under the header and an optional chapter title;
  - justified paragraphs, with or without a first-line indent, at body sizes from 22 to 40 px;
  - in about a third of pages, footnotes in a smaller, fainter size below a short rule.
- **`book_page_two_column`:** the same, in two justified columns at 20 to 32 px, with an optional vertical rule. Each
  column is its own `body` region, and the right column is read first.
- **`commentary_page`:**
  - a main text block of 34 to 44 px in the upper middle;
  - four commentary blocks set in Rashi script at 19 to 26 px: one on each side of the main text, and two columns
    below it.
- **`book_title_page`:** a single or double frame, with centred lines at mixed sizes: title, sub-lines and an imprint.

On top of that:
- **Scan edges:** about a third of pages get dark strips along one or two edges, like a book scanned open.
- **Thumbnail variants:** the `_thumbnail_scan` variants use `book_scan_thumbnail`.
  - After blur and grain, the page is downsampled to 960 px wide and back to the canvas. This is the detail of a
    Wikisource page image, while pixel positions, and so all geometry, stay put.

## Gold and regions

| Page part | Region type | Notes |
| --- | --- | --- |
| Running header and page number | `identifier_area` | one region; a bottom page number is a second one |
| Chapter title, title-page title | `title` | |
| Prose | `body` | one region per column |
| Commentary blocks | `margin` | one region each |
| Footnotes, title-page imprint | `footer` | |

- **Reusing region types:** the region types are the existing ones, so a segmenter trained on these and on the
  governed templates shares one class set.
- **`logical_order`:** each paragraph is one logical line, rebuilt from its wrapped lines with `space` joins.
  - A paragraph that runs out of room keeps only the drawn lines, and paragraphs that never start are not in gold.
  - The renderer never truncates a drawn logical line, so `truncated_segments` is 0.
- **Reading order:** header, title, columns right to left, commentary blocks, footnotes, then a bottom page number.
- **Justified lines:** these are drawn word by word. Their line polygon is the union of the word boxes, padded by
  `LINE_POLYGON_PADDING` (4 px), so line polygons stay tight.
- **`--plain-evaluation`:** rejected for book templates.

## Scope

- **Not governed:**
  - The templates are in `BOOK_TEMPLATE_IDS` and in `SUPPORTED_TEMPLATE_IDS`, which `generate --template-id` and
    `validate` accept.
  - They are not in `GOVERNED_TEMPLATE_IDS`, so the `hocrgen` contract, `templates`, `contracts` and rendering
    coverage are unchanged.
  - Adding them to the governed set is a `hocrgen` decision.
- **No version bump:** `GENERATOR_VERSION` is not bumped. The pages of the governed templates are byte-identical,
  because the new preset field and fonts are used only by book templates.
- **Only the main font is recorded:** the manifest records the main font id. The Rashi-script font of commentary
  pages is fixed by the recipe and listed above; manifest v1 has no field for a second font.

## Fonts

All three are SIL Open Font License 1.1. They were taken from `google/fonts` at commit
`86aced91de05cd4f96a06838124cca45be337b2b`, with each licence beside the font.

| Font id | File | Upstream path | sha256 |
| --- | --- | --- | --- |
| `frank-ruhl-libre` | `FrankRuhlLibre-wght.ttf` | `ofl/frankruhllibre/FrankRuhlLibre[wght].ttf` | `f9bf2696…a338a43` |
| `david-libre-regular` | `DavidLibre-Regular.ttf` | `ofl/davidlibre/DavidLibre-Regular.ttf` | `923f06e0…fb47b86e` |
| `noto-rashi-hebrew` | `NotoRashiHebrew-wght.ttf` | `ofl/notorashihebrew/NotoRashiHebrew[wght].ttf` | `4da0058f…c9eb126` |

- **Weights:** Frank Ruhl Libre and Noto Rashi Hebrew are variable fonts, rendered at their default Regular instance.
- **Licences:** `LICENSE-FrankRuhlLibre-OFL.txt`, `LICENSE-DavidLibre-OFL.txt` and `LICENSE-NotoRashiHebrew-OFL.txt`.
- **Trained models:** as with Alef and Gveret Levin, fonts are credited in any model trained on these pages, but the OFL
  does not reach the weights (heocr-engine decision 0010).

## Example

```bash
PYTHONPATH=src python -m hocrsyngen.cli generate --count 8 --seed 17 --output out/book-pages \
  --template-id book_page --template-id book_page_two_column --template-id commentary_page \
  --template-id book_title_page --text-corpus src/hocrsyngen/data/synthetic/texts/hebrew_lines_train_v1.txt \
  --emit-line-annotations
PYTHONPATH=src python -m hocrsyngen.cli validate out/book-pages --format json
```
