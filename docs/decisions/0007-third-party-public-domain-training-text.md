# ADR 0007 - Third-Party Public-Domain Training Text

## Status

Accepted (maintainer decisions, 2026-11-06). Implementation is planned, not
done; see [the S15a plan](../pby_public_domain_text_intake_plan.md).

## Context

Every packaged training corpus so far is project-authored (S10b, S13a, S13b),
so samples carry `PROJECT-SYNTHETIC` and no third-party text. Project
Ben-Yehuda publishes a public-domain dump of more than 26,000 Hebrew works.
Using that dump raises four questions: whether outside text is allowed at all,
which jurisdictions must clear it, how much of it to use, and how to treat
translations.

## Decision

1. Outside public-domain text is allowed for training.
2. Public domain in Israel is enough. US public-domain status is recorded per
   entry, so builds that are also public domain in the US remain possible.
3. The share of outside text in the training mix is a hyperparameter, not a
   policy question.
4. A translation is public domain only if both the author and the translator
   are. Each has their own 70-year term in Israel.

## Consequences

- Outside text enters through an external, pinned corpus passed with
  `--text-corpus`. `hocrsyngen` keeps its no-network rule.
- Every entry carries per-work rights fields with sources. PBY's own flag is
  recorded but is not enough on its own.
- The manifest licence for pages rendered from outside text is a
  `hocrgen`-coordinated contract question. Until it is settled, `license` stays
  `PROJECT-SYNTHETIC` and such pages are not handed to `hocrgen` as release
  candidates.
- Outside works used for training are listed, so `hocrgen` can keep them out
  of any real-scan evaluation set.
