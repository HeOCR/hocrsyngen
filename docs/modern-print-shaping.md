# Modern print font coverage and shaping

The modern line and office pools include ten additional SIL OFL 1.1 Hebrew
families. The [inventory](modern-print-font-expansion.csv) records design
period and use, weights, exact source revision, and checksums of each font
and license notice. The source date is the Google Fonts inclusion date.
Period notes distinguish historical design revivals from contemporary
designs. The original font and notice bytes are bundled unmodified.

The new families cover Hebrew letters and final forms, Latin letters,
digits, geresh, gershayim, maqaf, dashes and shekel. Individual faces
may have additional coverage or gaps. The renderer's font exclusion
registry still controls eligibility. A run that needs the old pool
can supply its earlier pinned manifest or an explicit list of faces.
A new default pool can change seeded assignments even when the seed
is reused.

## Render-time checks

Native Pillow RAQM shapes the logical string. The glyph guard uses the
same FreeType face in BASIC mode to compare each printable scalar with
the face's missing-glyph bitmap. This is a conservative check for tofu.
Rasterization refuses detached marks and bidi overrides. The line
renderer checks for ink and a clear canvas margin before degradations.
Batch refusals include a reason and omit both the image and label.

Office text and its token spans use the same NFC-normalized values.
Book and office lines where bidi runs can cross spaces are drawn as
whole native lines. Pure Hebrew lines can still use word spacing for
justification. The commentary renderer uses the page's body face for
a block whose text the Rashi face cannot cover, then wraps at the
actual face's metrics. The logical text stays intact.

The regression suite checks final forms, mixed Hebrew and LTR runs,
digits, rejected tofu cases, combining marks and normalization offsets.
The runtime dependency set remains the same. Independent HarfBuzz probes
are a development check. Its isolated directional runs complement the
renderer tests for mixed bidi order because the shaper does not resolve
bidi paragraphs on its own.

[Google Fonts source at the pinned revision](https://github.com/google/fonts/tree/06bfe0d62a98375cb09c942fa18e68bd32cff057/ofl)

[HarfBuzz shaping documentation](https://harfbuzz.github.io/what-harfbuzz-does.html)
