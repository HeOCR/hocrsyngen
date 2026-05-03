# hocrgen Integration Contract

`hocrgen` should consume `hocrsyngen` through the installed-package CLI and serialized manifest/fixture contracts. It should not import private `hocrsyngen` internals.

## Stable Integration Commands

```bash
hocrsyngen templates --format json
hocrsyngen contracts --format json
hocrsyngen contracts export --fixture-id generation_manifest_v1_fixture_batch --output PATH --format json
hocrsyngen generate --count N --seed S --output PATH --format json
hocrsyngen validate PATH --format json
```

## hocrgen Responsibilities After Import

After receiving a valid `hocrsyngen` batch, `hocrgen` remains responsible for:

- Release eligibility.
- Synthetic caps.
- Source composition.
- Review.
- Privacy.
- Dedupe and leakage checks.
- Benchmark/reference handling.
- Release export.
- Publication.

## Candidate Lifecycle

1. `hocrsyngen` generates candidate synthetic batch.
2. `hocrsyngen` validates local batch contract.
3. `hocrgen` imports or ingests batch.
4. `hocrgen` applies dataset governance.
5. HeOCR receives only release-approved outputs.

## Fixture Expectations For hocrgen Adapter Tests

- Export the packaged fixture through `hocrsyngen contracts export`, not by copying package internals directly.
- Validate the exported fixture with `hocrsyngen validate PATH --format json`.
- Assert the fixture id `generation_manifest_v1_fixture_batch`.
- Assert the manifest contract `generation_manifest.v1`.
- Preserve relative asset paths when importing.
- Recompute hashes or trust only after validation, depending on `hocrgen` policy.
- Treat the fixture as candidate synthetic input, not as a release payload.

## Risks And Open Questions

- `hocrgen` adapter tests should avoid assumptions about private Python dataclass names or package resource paths.
- Any future manifest field needed by `hocrgen` must be added through schema, docs, and tests, with versioning when required.
- Release profile rules and synthetic caps belong in `hocrgen`, not in `hocrsyngen`.
