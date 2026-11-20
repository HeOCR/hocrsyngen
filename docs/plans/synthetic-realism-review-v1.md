# Synthetic realism review, round 1

Shay approved planning the review loop on 2026-11-20. A blind comparison with real scans gives the generator team a quick development signal. The downstream decision about OCR utility still comes from training comparisons scored once on registered, real held-out data under eval's protocol.

## First round

Use **50 trials** in the first session. Include 42 standard pairs, five real-vs-real controls and three obvious-synthetic attention checks. Each side has a full page and its corresponding body-line crop. Start with old-print flat scans, which have the narrowest reference-clearance request. Use 55 distinct real pages across the pairs and controls. Contrib owns the queue and its [pinned bundle and export contract](https://github.com/HeOCR/heocr-review/blob/c86cc83d2c408b5e59efe8418bcde8379ab16058/docs/specs/synth-realism.md).

| Generator ID | Version | Standard pairs | Parameters varied |
| --- | --- | ---: | --- |
| `hocrsyngen` | `r1-clean-book` | 11 | Plain white paper, no simulated scan edges or scan degradation |
| `scanifier-v2` | `r1-even-book` | 11 | Flat page, even illumination, light noise and blur |
| `look-scanned` | `r1-global-book` | 10 | Fixed frame, grayscale tone, fine grain, slight jitter and black border |
| `scanifier-v2` | `r1-uneven-book` | 10 | Flat page with less even illumination and stronger noise and blur |

Every variant uses the same generated book-page recipe with separate source page IDs. Both Scanifier profiles use zero camera angle and paper deformation and crop away the simulated surround. The [Look Scanned port](https://github.com/HeOCR/hocrsyngen/pull/136) uses unit scale and zero yellowing to match the grayscale session. Assemble the private old-print bundle once eval clears the exact full-page and crop assets. Training-line CLEAN is evidence for candidate selection. Eval clearance covers the full page and crop hashes the importer consumes.

Add Level 2 and modern print in a later matched session. The first Level 2 pilot learns historical paper and produces training lines. For its review arm, use cleared texture tiles in a seeded page-level hard-mask application. Verify source dimensions and protected pixels, inspect for seams, and run label-safety checks on the crop from the treated page. Freeze the page recipe and hashes. Keep these development derivatives outside the training ablation and PS-v2. Run phone-photo or line-only strata when cleared references and a compatible review format are available.

Freeze the generator ID, version and code revision, fully resolved render and augmentation settings, source input hashes, software versions and sampling rule. The `params_hash` is SHA-256 of the effective parameters, encoded as UTF-8 JSON with sorted keys, compact separators and finite numbers. Keep repeatable per-page seeds, source and derivative file hashes, and crop coordinates in the operator record. Bump the version for every changed recipe, with a dated entry explaining the hypothesis, exact settings that changed and previous version/hash. Use authored, development-only synthetic text and the existing held-out font guard.

## Real references and blindness

Request eval clearance through the lead on exact catalog IDs and source pages. For the first session, draw candidates from the audited historical-print training pool using openly licensed or public-domain IA copies. Modern-print training units can supply candidates for a later session. Before retrieving image bytes, get confirmation that the page is train or dev, that the work and page are outside reservations, and that the scan is cleared for this review. Verify the scan's rights and omit pages with private identifying details or branding that would make the pairing trivial. A cleared line does not clear its whole source page. A changed page or alternate scan needs clearance. Keep the ledger and lookup to physical paths private.

Match period and page type, column count, density, orientation and capture modality. Prefer unique reference pages spread across works and modern units. Avoid repeated source pages, alternate scans of the same page, and visible scan-site overlays. Fill only the pairs with suitable cleared matches and record gaps. Prepare both sides with the same flat-scan framing and comparable grayscale derivatives. Crop one unoccluded central body line from each displayed page with comparable padding. Check that both crops contain the intended entire line. Eval signs off on the exact prepared page and crop bytes. The local importer independently normalizes display assets and strips metadata.

Use opaque participant-facing IDs and never expose real/synthetic, generator ID, image names, metadata or source URLs to the reviewer. Keep the keyed answer mapping on the operator side. The Worker draws trials without replacement, independently randomizes left and right and retains the assigned side order. Avoid repeating any page in a session. The Worker locks the blind real choice before revealing origins and requesting the 0–10 match rating, applicable tags and optional comment. Keep incomplete choices separate from submitted feedback. Real-vs-real controls measure which examples the reviewer rejects and any side preference. Attention checks deliberately use conspicuous artifacts and contribute no generator observations.

## Bundle and handoff

Write `manifest.json` in contrib's `synth_realism_manifest.v1` format with the assets under `images/`. In that contract, the version field is `generator_version`. Validate the `synth_realism_clearance.v1` file against the SHA-256 supplied separately by the lead. Its train/dev references pin both exact image and crop bytes. Match both real sides of a real-vs-real control to their own clearance records. Use opaque IDs and exact asset digests, with no repeated pages. Use the contributor's local importer in dry-run mode before handing an immutable batch to the queue. Keep the clearance, operator crosswalk and reviewer export private. Deployment remains a separate lead decision.

## After each session

Read the private `synth_realism_dev.v1` export and join on opaque pair IDs. Verify the side key and reject inconsistent retries before using the fooling rate, defined as synthetic chosen as real divided by completed blind choices for standard trials. Keep counts and variant/stratum denominators alongside the rating distributions, tags and comments. Use the Worker’s separate control summaries and confirm that the reviewed sample is usable before proposing changes. These are subjective developer signals. Small groups or unmatched examples can drive apparent differences. Do not publish them as evidence of OCR performance.

Prioritize recurring explanations, pick one parameter hypothesis per follow-up arm where possible, and retain an unchanged control recipe with fresh samples. Record the rationale, previous/new version and hashes, parameter differences, seeds and resulting manifest digest. Use new cleared references for later comparison, or explicitly tag a repeated anchor so familiarity can be separated. Send each new batch only through the agreed queue contract. Real held-out results govern any claim that the change improves models.

A later small critic may use the approved review images and judgements. Freeze consent and data permissions, track uncertainty and disagreement, and split by underlying page, source work, generator run and version so near duplicates do not leak between groups. Test agreement with fresh human judgements in development and have Shay audit mistakes, edge cases and changes in the critic's preferences. The critic can suggest what to review next. Training gains and publication still follow the held-out evaluation rules.
