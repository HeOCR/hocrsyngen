# Project Ben-Yehuda Public-Domain Text Intake Plan (`S15a`)

Status: **plan only.** This PR adds no text, code, or contract change.
Parent phase: S15, Public-Domain Training Text. Maintainer decisions:
[ADR 0007](decisions/0007-third-party-public-domain-training-text.md).

The goal is to add real Hebrew text from Project Ben-Yehuda (PBY) to the
recognizer's training text. The current training text is agent-authored
(S10b, S13a, S13b), which gives one voice, a modern register and short lines.
PBY adds:

- vocabulary breadth, including literary and archaic forms;
- natural character and word frequencies;
- long sentences that can be cut to any template width;
- a large niqqud-bearing source (poetry and children's literature).

## Maintainer decisions (2026-11-06)

These are recorded in ADR 0007:

1. Outside public-domain text is allowed for training.
2. Public domain in Israel is enough. US public-domain status is recorded per
   entry, so a corpus that is also public domain in the US can be built.
3. The share of outside text in the training mix is a hyperparameter, not a
   policy question.
4. A translation is public domain only if both the author and the translator
   are. Each has their own 70-year term in Israel.

## Source as read (read-only, 2026-11-06)

- **Repository:** `github.com/projectbenyehuda/public_domain_dump`, pinned at
  `master` commit `5e4277fead7b565f32cc4b352abd3565023a77d8` (2026-03-07,
  "10th release"). `VERSION` is `2026-03`.
- **LICENSE:** "Public domain". The files are free for any use without
  permission. Credit is requested, not required: "Project Ben-Yehuda
  volunteers", with a link to <https://benyehuda.org>. PBY also asks to be
  told about reuse, at the editor's address in the README.
- **README:** over 20,000 public-domain works, as UTF-8 plain text with
  diacritics (`txt/`), without them (`txt_stripped/`), and as HTML (`html/`).
  There is one directory per author, and release ZIPs are attached to the
  repository's releases. PBY also has an API, but it needs a key and this plan
  does not use it.
- **`pseudocatalogue.csv`:** 26,455 rows. IDs are unique. Columns:

  | Column | Content | Fill |
  | --- | --- | --- |
  | `ID` | PBY work id | all |
  | `path` | `/p<author>/m<work>`, the file stem under each format directory | all |
  | `title` | work title | all |
  | `authors` | author name(s) | 26,454 |
  | `translators` | translator name(s) | 1,814 |
  | `author_uris` | Wikidata URIs, `; `-separated when there are several (107 rows) | 23,855 (23,854 Wikidata); 862 distinct |
  | `translator_uris` | Wikidata URIs | 1,646 of the 1,814 translations |
  | `original_language` | ISO code; set exactly when there is a translator | 1,814 |
  | `genre` | an untranslated i18n key, `Translation missing: he.<genre>` | all |
  | `source_edition` | free-text bibliographic note on the edition PBY transcribed | 21,205 |

  Genre counts: poetry 13,140, article 7,213, prose 3,523, reference 1,192,
  memoir 502, letters 462, fables 254, drama 167, lexicon 2.

- **Text files:** sampled, not surveyed. Two works were spot-checked.
  - `txt/` and `txt_stripped/` are line-aligned: same line count, same breaks.
  - `txt/` prose carries sparse pointing (dagesh, shin and sin dots, a few
    vowels). Poetry is fully pointed.
  - `txt/` keeps footnote residue: bare footnote numbers, `↩`, entity
    fragments, and a stray U+FE0E.
  - Maqaf `־`, the en dash, the ellipsis and ASCII quotes all occur.

No text was copied into this repository.

## 1. Per-entry rights fields

There is one record per PBY work, in a `pby_rights_index.v1` JSONL file kept
next to the corpus (see §3). Rights are computed against an `as_of` year,
because public-domain status changes every 1 January.

| Field | Type | Meaning |
| --- | --- | --- |
| `pby_work_id` | int | `ID` |
| `pby_path` | str | `path` |
| `pby_dump_commit` | str | the pinned dump commit |
| `title` | str | `title` |
| `genre` | str | the `he.<genre>` suffix |
| `authors[]` | list | `{name, wikidata_qid, death_year, death_year_source}` |
| `translators[]` | list | the same shape; empty when the work is not a translation |
| `original_language` | str or null | `original_language` |
| `source_edition` | str or null | the raw `source_edition` |
| `source_edition_year` | int or null | a year parsed from `source_edition` (Gregorian, or a Hebrew year converted to its later Gregorian year) |
| `first_publication_year` | int or null | known first publication year; null unless a reviewed source gives it |
| `first_publication_year_source` | str or null | where it came from |
| `pd_israel` | bool | public domain in Israel as of `as_of` |
| `pd_israel_basis` | str | see below |
| `pd_us` | `true` / `false` / `"unknown"` | US status as of `as_of` |
| `pd_us_basis` | str | see below |
| `pby_public_domain` | bool | PBY's own flag (see below) |
| `pby_basis` | str | `public_domain_dump LICENSE @<commit>` |
| `as_of` | int | the calendar year the flags were computed for |

**`pby_public_domain` (PBY's own flag).** The dump has no per-work rights
column. Membership in `public_domain_dump` is PBY's assertion, and the
repository LICENSE says "Public domain". So every catalogue row gets `true`,
with that basis string. PBY's flag is recorded, but on its own it never sets
`pd_israel`.

**`pd_israel` and basis.** This is the plan's reading of the Copyright Act
2007: life plus 70 years, running to the end of the calendar year. It is not
legal advice.

| Basis | Rule | `pd_israel` |
| --- | --- | --- |
| `all_creators_died_by:<Y>` | every author and translator has a sourced death year ≤ `as_of` − 71 (≤ 1955 for 2026) | true |
| `creator_death_year_unknown` | some author or translator has no sourced death year | false |
| `creator_in_term` | some author or translator died after `as_of` − 71 | false |
| `anonymous_unresolved` | anonymous or unknown author (e.g. `אלמוני/ת`, 115 rows) | false until resolved by hand |

A translation needs both its authors and its translators to pass (decision 4).

**`pd_us` and basis.** US status is recorded so that a corpus that is also
public domain in the US can be built (decision 2). It never gates the Israeli
corpus.

| Basis | Rule | `pd_us` |
| --- | --- | --- |
| `published_before:<as_of − 95>` | `first_publication_year` or `source_edition_year` is before `as_of` − 95 (before 1931 for 2026) | true |
| `published_in_term` | `first_publication_year` is known and is `as_of` − 95 or later | false (pending review; see below) |
| `uraa_candidate` | published `as_of` − 95 or later, but every creator died before 1946 | `"unknown"` (flagged for legal review) |
| `unknown` | anything else | `"unknown"` |

- **Edition year as an upper bound.** `source_edition_year` is the year of the
  edition PBY transcribed, not first publication, so it is only an upper bound
  on first publication. A pre-1931 edition therefore proves pre-1931
  publication. For a translation, it bounds the translation's own publication.
- **`uraa_candidate`.** These are works that may never have had their US
  rights restored, because they were already public domain in Israel on
  1996-01-01. That needs a legal reading before anything relies on it.

## 2. What the catalogue fills, and what it cannot

| Field | From the catalogue | Gap and fill strategy |
| --- | --- | --- |
| Work id, path, title, genre | directly | none |
| Author and translator identity | `authors`, `translators`, `*_uris` | 2,600 rows have no author URI, and 168 translations have no translator URI. Resolve by hand (with a source) or exclude. |
| Death years | **no** | Look up Wikidata P570 for the 862 distinct author QIDs and the translator QIDs once, outside `hocrsyngen`. Pin the result as a reviewed `creators.json` (QID, death year, Wikidata revision id). Authors without QIDs need a death year by hand, or they are excluded. |
| First publication year | **no** | Usually unknowable from the dump. `source_edition` is often a later collected edition (for example a 1959 edition of a 19th-century poet). Only 3,477 of the 21,205 notes yield a parseable year, and 756 of those are before 1931. `first_publication_year` therefore stays null unless a reviewed source gives it. |
| Translation status | `translators`, `original_language` | complete; the two columns agree on every row |
| PBY flag | dump membership and LICENSE | complete, but not per-work evidence |
| Editorial layers (prefaces, notes, footnotes) | **no** | The HTML marks footnotes (`fn:` anchors), and `txt/` keeps their residue. Drop footnotes and notes at extraction (§7), so only the work's own text is used. |

**Expected effect.** `pd_israel` should be decidable for most rows once death
years are pinned. `pd_us` will be `true` for a minority: pre-1931 source
editions, plus works whose first publication year is sourced later. The rest
will be `"unknown"`. That is why the US corpus is a separate, smaller build.

## 3. Where the text lives

**Recommended: an external, pinned corpus passed with `--text-corpus`.** Do not
vendor PBY text into the `hocrsyngen` wheel.

- **The intake build runs outside `hocrsyngen`.** An offline script reads a
  local checkout of the dump at the pinned commit, plus the pinned
  `creators.json`. It writes:
  - `pby_lines_<variant>_v1.txt`: one line per row, in the S10b format;
  - `pby_rights_index.v1.jsonl`: §1, one row per work;
  - `pby_line_index.v1.jsonl`: line sha256, `pby_work_id` and `subset`
    (`plain` or `niqqud`);
  - a corpus card and a `SHA256SUMS` file.

  Variants: `il` (`pd_israel` true) and `il_us` (`pd_israel` true and `pd_us`
  true). Each variant has its own sha256, so the generator's existing
  `provenance.source_corpus` value, `external:sha256:<hex>`, already tells
  them apart.
- **`hocrsyngen` stays network-free.** It reads the file via `--text-corpus`
  as it does today, and records `external:sha256:…` in the manifest and the
  corpus sha256 in the run record. The generator needs no change to consume
  it.
- **Hosting is open.** Candidates are a separate HeOCR data repository, or an
  operator artifact under `hocrgen` governance. The maintainer decides.

**Why not vendor a pinned subset?**

- **Size.** The dump is about 900 MB. Even a useful subset is many megabytes
  of third-party text in every install.
- **Churn.** The mix share is a hyperparameter (decision 3) and the cut
  depends on template widths. Every change would be a `_v2` package release.
- **Rights recomputation.** Rights change with `as_of`. Recomputing them
  should not require a package release.

A tiny vendored test fixture of a few pre-1900 lines with their index rows may
be added later, so CI can test the line-index join without the network. It
would get its own card.

## 4. Manifest licence for pages rendered from PD text

Today `generation_manifest.json` v1 pins `license` to the constant
`PROJECT-SYNTHETIC` (schema `const`, pydantic `Literal`, and
`validation.py`). `hocrgen` maps it through `licenses.yaml` (`PROJECT-SYNTHETIC`,
`open`). Its `project_synthetic` source requires exactly that value. A page
rendered from PBY text is project-rendered, but its text is third-party public
domain.

**Options, for `hocrgen` governance to decide:**

| Option | Manifest change | `hocrgen` change | Trade-off |
| --- | --- | --- | --- |
| A. Keep `PROJECT-SYNTHETIC` | none | none; text rights live in the corpus card and indexes | Smallest change, but a release reading only the manifest cannot tell PD-text pages apart. |
| B. A new value, e.g. `PROJECT-SYNTHETIC-PD-TEXT` | additive enum (manifest v1.1 or v2); the generator sets it when the corpus card declares PD text | a new `licenses.yaml` id (`open`), accepted by `project_synthetic` or a new source | Visible at the licence layer. US vs Israel stays in the corpus variant, not the licence. |
| C. B, split by jurisdiction (`…-PD-IL-TEXT`, `…-PD-US-TEXT`) | as B, with two values | two ids | Most explicit, but it puts a per-corpus property into every sample. |

**Proposal: B.** One additive licence value. Jurisdiction is carried by the
corpus variant and the rights index. The generator learns that a corpus is PD
text from a machine-readable corpus card. It must not guess from the file
contents.

This needs a manifest contract bump with fixtures, schema and validation, and
a matching `hocrgen` change. Both are later PRs, after `hocrgen` governance
agrees. Until then, PBY text is used only for training runs whose pages are
not handed to `hocrgen` as release candidates.

## 5. PBY attribution

PBY requests credit, but does not require it. The plan gives it everywhere a
reader meets the text:

- **The PBY corpus card:** "Text from Project Ben-Yehuda
  (https://benyehuda.org), prepared by Project Ben-Yehuda volunteers", with the
  pinned dump commit and `VERSION`.
- **Downstream cards** (`hocrgen` dataset cards, HeOCRsynth cards, release
  notes) carry the same line whenever a batch used a PBY corpus. `hocrgen`
  owns those cards, so this is a handoff item.
- **Model cards** in `heocr-engine` carry it for any model trained on PBY
  lines.
- **Telling PBY.** Notifying PBY's editor about the reuse is an outward
  message. The maintainer decides whether and when to send it; agents do not.

## 6. Keeping PBY works out of a real-scan eval set

`hocrgen` E2d plans an evaluation set made only of real scans, with printed
and handwritten tracks (`HeOCR/hocrgen` #102). Printed books, and some
handwritten pages such as HASH letters or poems, may contain works that are
also in PBY.

- **Work-level exclusion list.** Each corpus build publishes
  `pby_excluded_works.v1.json`. It lists every `pby_work_id` in the corpus,
  with title, author QIDs and the corpus sha256, at corpus level. The
  generator need not record which line went to which page. Every PBY work in
  any training corpus is excluded from evaluation.
- **Text-overlap check.** Real-scan references carry no PBY ids, so `hocrgen`
  also checks n-gram overlap against the corpus line index. For example,
  reject a reference page that shares any word 8-gram, or more than a set
  share of word 3-grams, with PBY training lines. This is the same kind of
  leakage check the packaged corpora run. The thresholds are set in the
  `hocrgen` E2d contract.
- **Optional author-level exclusion** for the handwritten track, where one
  writer's style is the risk. That is the `hocrgen` reviewer's call.
- **Ownership.** `hocrgen` owns and enforces the exclusion. `hocrsyngen`
  documents it as an external dependency in `production_readiness.md`.

## 7. Line-cutting and the niqqud split

Extraction works per work, from `txt_stripped/` and `txt/`. The two are
line-aligned, so line *i* of one is line *i* of the other. A build asserts this
per work and drops works where it fails.

1. **Clean.**
   - Drop footnotes and notes: the HTML `fn:` targets and their residue in
     `txt/`.
   - Drop the title line and blank lines.
   - Drop lines with entity residue, URLs or Latin fragments.
   - Remove U+FE0E and other variation selectors.
   - Normalise to NFC, one space, LF.
2. **Character set.**
   - Keep Hebrew letters, digits and the S10b/S13b punctuation, including the
     S13b typographic marks.
   - Maqaf `־` is common in PBY, and missing from every packaged corpus (a
     known S13b gap). Keep it only after the glyph check in both packaged
     fonts that S13b ran.
   - Drop any line with other scripts or symbols. Do not substitute
     characters.
3. **Cut to template widths.**
   - Split prose at sentence ends, then pack words greedily into lines.
   - Poetry keeps verse lines, wrapping a long one at spaces.
   - Every output line must pass the S10b no-loss rule with the generator's
     own `_wrap_hebrew_text` and the packaged fonts. Every token must fit every
     region (`printed_letter` and `handwritten_note` at 968 px, `archive_card`
     at 498 px with at most 2 rows, and the current ledger details cell), and
     no capped region may get more rows than it draws. Reuse the region table
     in `tests/test_training_text_corpus.py`, not a copy.
   - Target the S10b length profile: at most 55 characters, 18–35% of lines
     at 31–55 characters, at least 10% at 36–47, median 18–30.
4. **Niqqud split.**
   - Compute the pointing density of each `txt/` line: the share of Hebrew
     letters carrying a mark in U+05B0–U+05BC, U+05C1, U+05C2 or U+05C7.
   - **Niqqud subset:** lines with density ≥ 0.5, taken from `txt/`. This
     matches the S10b niqqud files, where every line is pointed.
   - **Plain subset:** every other line, taken from `txt_stripped/`. This
     includes sparsely pointed prose, whose marks are aids, not full pointing.
   - Lines carrying cantillation (U+0591–U+05AF), meteg, rafe, or marks
     outside the S10b set go to the plain subset only.
   - The 0.5 threshold is a tunable default, and the build reports its
     histogram.
5. **Register and content.**
   - Record genre and approximate period per line, through the line index.
   - Start with a genre allowlist (prose, articles, memoir, letters, fables,
     poetry). Leave out reference and lexicon entries.
   - Run a reviewable content screen for offensive or dated material. Its
     thresholds are build parameters.
   - The mix share against the project corpora is set per training run
     (decision 3). An ablation against the current baseline should report the
     effect on modern administrative text, where older orthography (ktiv
     haser) could hurt.
6. **Leakage.** PBY lines must share no line or word 3-gram with any packaged
   evaluation text, or with the `hocrgen` fixtures (via the S13a hash-only
   fixture). This is the same check as S13a and S13b.

## Planned PR breakdown

- `S15a`: this plan and ADR 0007 (docs only).
- `S15b`: the offline intake builder and the pinned `creators.json`, in the
  repository the maintainer picks for hosting (§3). Its output is the corpus
  variants, the indexes, the exclusion list and the corpus card. No
  `hocrsyngen` code change.
- `S15c`: a machine-readable corpus card input and the licence handling
  agreed with `hocrgen` (§4). This is a manifest contract change, if
  governance chooses B or C.
- `S15d`: a training ablation in `heocr-engine` with and without PBY lines, at
  one or two mix shares.

Each needs its own review. Nothing here changes generator output, manifest v1
or packaged corpora.
