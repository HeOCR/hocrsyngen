# AGENTS.md

Static instructions for agents working in this repository. Keep dynamic status in `.agent-plan.md`, repository maps in `llms.txt`, and long-form plans/specs in `docs/`.

## Setup And Test Commands

Use these exact local commands unless the repository configuration changes:

```bash
python -m pip install -e ".[test]"
python -m pytest
PYTHONPATH=src python -m hocrsyngen.cli templates
PYTHONPATH=src python -m hocrsyngen.cli contracts --format json
PYTHONPATH=src python -m hocrsyngen.cli generate --count 2 --seed 17 --output out/fixture-batch
PYTHONPATH=src python -m hocrsyngen.cli validate out/fixture-batch --format json
```

- There is no configured lint command unless one is added explicitly.
- Pillow with libraqm support is required for Hebrew RTL rendering tests.
- If tests fail because libraqm is missing, report that exact environmental blocker rather than weakening tests.

## Architectural Boundaries

- `hocrsyngen` owns deterministic candidate synthetic Hebrew OCR/HTR sample generation.
- `hocrgen` owns dataset orchestration, governance, validation, review, dedupe, release assembly, export, and publication.
- HeOCR owns public dataset payloads and releases.
- Upstream of the page-composition step lives in the parallel real-glyph chain
  `HeOCR/public-domain-hand-written-hebrew-scans` → `HeOCR/hletterscriptgen` →
  `HeOCR/hletterscript`. Today this chain is not consumed by `hocrsyngen`;
  future S9 work composes pages from `letter_set.v1` glyph variants and must
  use file-based contracts only.
- Do not import `hletterscript` or `hletterscriptgen` from `hocrsyngen`. If
  future S9 work consumes per-writer letter sets, it does so through the
  `letter_set.v1` document plus relative asset bytes, not by importing those
  repositories' Python code.
- Generated batches are candidate synthetic inputs, not release-ready dataset artifacts.
- Do not import `hocrgen` from `hocrsyngen`.
- Do not add network, REST, scraping, publication, release-governance, or dataset-export behavior to the `hocrsyngen` baseline.
- Do not add GPU, LLM, diffusion, Torch, TensorFlow, or other deep-learning dependencies to baseline package dependencies.
- `hocrgen` integration must use stable CLI, manifest, and contract-fixture boundaries, not private Python internals.
- Generated assets must be accompanied by `generation_manifest.json`.
- Manifest asset paths must remain relative portable POSIX paths, never absolute paths and never `..`.
- Manifest text must remain logical-order UTF-8 Hebrew, NFC-normalized, with Hebrew RTL metadata.
- Persona and condition controls are synthetic generator controls only; they are not real identity, medical, psychological, or authorship claims.
- Any new bundled font, text, or image asset must have explicit provenance and license documentation.
- Do not mutate packaged contract fixtures unless the contract fixture is intentionally regenerated and all related tests/docs are updated.

## Stable Public Surfaces

- CLI commands: `templates`, `contracts`, `contracts export`, `generate`, `validate`.
- Serialized manifest contract: `generation_manifest.json` v1.
- Packaged fixture id: `generation_manifest_v1_fixture_batch`.
- Treat private helpers and module internals as implementation details unless documented otherwise.

## Documentation And State Separation

- `AGENTS.md` = static rules only.
- `llms.txt` = compact repository map only.
- `.agent-plan.md` = dynamic current state and next actions.
- `docs/` = human-readable architecture, specs, plans, and decisions.
- `README.md` = user-facing entry point, not the full planning archive.

## Planning Hygiene

- Keep `docs/roadmap.md`, `docs/production_readiness.md`, and `.agent-plan.md`
  aligned when roadmap state changes.
- As of PR #38, `S4d` is the last merged roadmap item and Phase S4 is complete.
  Do not describe persona/style/condition controls as current work unless a new
  S4 follow-up is explicitly added.
- When a crucial production-readiness gap or high-lift quality item is found,
  either add a roadmap notation in `docs/roadmap.md` or record it as an
  external `hocrgen` dependency in `docs/production_readiness.md`.
- Do not implement `hocrgen` import, governance, release profiles, review
  workflows, synthetic caps, export, or publication in this repository. Document
  those as downstream dependencies and keep `hocrsyngen` focused on candidate
  generation, validation, contracts, and generator-quality evidence.

## Branch And PR Conventions

- Use branch names like `docs/...`, `refactor/...`, `feature/...`, or `test/...`.
- Documentation/planning PRs should not bundle feature implementation.
- PR summary should list files created/modified and tests run.
