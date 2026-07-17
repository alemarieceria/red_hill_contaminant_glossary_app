# Phase 2 Intake Acceptance Tests

Phase 2 is accepted only when the incoming contract, inventory, atomic raw
publisher, manifest publisher, and collision/retry coordinator work together.
The focused component tests remain the best place to diagnose one rule; this
suite proves the complete package boundary.

## What the suite proves

`test_intake_end_to_end.py` runs the public sequence:

1. `read_incoming_pair`;
2. `inventory_incoming_pair`;
3. `publish_or_reuse_intake`.

It verifies authoritative creation, independent raw hashes and manifest JSON,
deterministic publication into separate roots, untouched exact retry, raw-only
recovery, source independence after publication, same-release collisions,
malformed history, hidden staging behavior, final revalidation, and
representative early contract failures.

Atomic failure matrices cover raw temporary creation, both workbook copies,
raw rename, manifest temporary creation, write, read-back verification, and
manifest rename. No failed path returns a completed intake. Temporary outputs
are absent after ordinary failures, while an exact raw pair remains available
for recovery when only manifest publication fails.

## Isolation

Every test snapshots the bytes, sizes, and nanosecond modification times of the
two authoritative incoming workbooks, tracked January snapshot, registry CSVs,
`pyproject.toml`, and `uv.lock`. It also records the complete real generated
trees. All publications occur in disposable directories, and teardown requires
the protected and generated state to match exactly.

The authoritative acceptance case inspects actual local Git state without
requiring a clean worktree. Mutation and failure matrices use synthetic copies;
the suite uses no network, sleeps, real concurrent processes, or production
generated paths.

## Run the tests

From `data_pipeline/`:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_intake_end_to_end.py
```

Phase 2 produces package-level intake behavior. A routine intake CLI remains
later work, and Phase 3 owns scientific validation and normalized processing.
