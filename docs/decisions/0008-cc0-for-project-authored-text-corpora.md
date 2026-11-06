# ADR 0008 - CC0 for Project-Authored Text Corpora

## Status

Accepted (maintainer decision, 2026-11-06). Amended 2026-11-06 to cover
`hebrew_lines.txt`; see the amendment below.

## Context

The packaged training and evaluation text corpora S10b, S13a and S13b were
stated to be under the repository license (MIT). MIT is a software license,
and these files are data. Their Provenance sections say the text was authored
by AI agents (Claude Opus 5.5 sessions run in Claude Code) for HeOCR. Such
text may carry thin copyright or none. CC0 1.0 is the standard public-domain
dedication for data, and it fits that case.

## Decision

1. These files in `src/hocrsyngen/data/synthetic/texts/` are dedicated to the
   public domain under CC0 1.0 (`CC0-1.0`):
   - S10b: `hebrew_lines_train_v1.txt`, `hebrew_lines_eval_v1.txt`,
     `hebrew_lines_niqqud_train_v1.txt`, `hebrew_lines_niqqud_eval_v1.txt`;
   - S13a: `hebrew_mixed_lines_train_v1.txt`, `hebrew_mixed_lines_eval_v1.txt`;
   - S13b: `hebrew_typographic_lines_train_v1.txt`,
     `hebrew_typographic_lines_eval_v1.txt`;
   - the seed-101 reference `hebrew_lines.txt` (added by the amendment).
2. `texts/LICENSE-CC0-1.0.txt` holds the CC0 legal code and lists the files it
   covers.
3. The code stays MIT. The fonts keep their own licenses.

## Consequences

- The corpus files are unchanged byte for byte, so their sha256s and every
  `source_corpus` id stay the same.
- Generated manifests do not record the corpus license. `license` stays
  `PROJECT-SYNTHETIC` and `provenance.source_corpus` records only the corpus id,
  so manifest v1 does not change.
- The Provenance sections of the three corpus cards are unchanged. They still
  record that the text is AI-authored.
- A future project-authored corpus states its own license in its card.

## Amendment (2026-11-06)

As first accepted, this decision left out `hebrew_lines.txt`, the 19-line
eval-only seed-101 reference, because no record said who wrote it. Its history:

- 16 lines came from `hocrgen` B3b (HeOCR/hocrgen#14, 2026-04-17, branch
  `codex/b3b-synthetic-alpha-quality`). The PR calls them "curated Hebrew
  document-style" lines and gives no provenance note.
- 2 lines were added when the corpus was ported in the `hocrsyngen` bootstrap,
  G0a/G1a (#1, `069490a`, 2026-05-03, co-authored by the GitHub Copilot coding
  agent).
- 1 line was added in G2a (`3fd8c58`, 2026-05-03).

No third-party text was identified. On 2026-11-06 the maintainer confirmed the
file as project-authored, and it is now covered by the CC0 1.0 dedication. Its
bytes are unchanged (sha256 `ac7e1dc2…`), so its `source_corpus` id and every
manifest that names it stay the same.
