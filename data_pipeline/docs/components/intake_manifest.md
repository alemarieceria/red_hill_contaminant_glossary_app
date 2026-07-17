# Intake Manifest

Phase 2.4 records one verified raw-snapshot pair as deterministic, portable
JSON. Scientific validation remains later work; Phase 2.5 now owns retry and
collision decisions around this focused publisher.

## Manifest content

The intake manifest schema is independently versioned as `1.0.0`. Its exact
top-level keys are:

- `manifest_schema_version`;
- `data_release_id`;
- `source_git`; and
- `workbooks`.

The two workbook records appear in glossary-then-references order. They include
Metadata identity, size, SHA-256, release-relative snapshot path, aggregate
counts, and the complete Phase 2.2 worksheet, header, table, row, and formula
inventory. Absolute paths, source data rows, timestamps, usernames, and raw Git
status output are excluded.

JSON uses UTF-8, readable Unicode, two-space indentation, sorted object keys,
LF line endings, and one final newline. Equal manifest records therefore
serialize to equal bytes.

## Git provenance

`source_git` records only `state` and `head_commit`:

| State | Meaning |
| --- | --- |
| `commit` | HEAD is known and the repository is clean |
| `local` | HEAD is known but tracked or untracked work differs |
| `unknown` | Git, the repository, or a trustworthy HEAD/status is unavailable |

Git inspection uses local `rev-parse` and porcelain `status` commands only. An
unknown state does not block an otherwise valid manifest.

## Verification and publication

Before manifest publication, both versioned raw files are read again and their
sizes and SHA-256 hashes must match the accepted inventory. The raw directory
must contain exactly the two ordinary stable workbook files.

The complete JSON is written and read back through a hidden sibling temporary
file, then exposed with one atomic rename to
`data/01_manifest/<data_release_id>.json`. This focused publisher refuses
existing targets. The
[collision and retry layer](intake_collision_and_retry.md) validates and reuses
an exact existing manifest without rewriting it.

Failures remove only the attempt's temporary manifest. The already published
raw snapshot is preserved. Full intake orchestration requires both publication
results. Phase 2.5 coordinates raw-only recovery and exact completed retries.

## Implementation and tests

Git-state records, manifest building, serialization, and publication are in
[`intake.py`](../../src/contaminant_pipeline/intake.py). Focused tests are in
[`test_intake_manifest.py`](../../tests/test_intake_manifest.py).

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_intake_manifest.py
```
