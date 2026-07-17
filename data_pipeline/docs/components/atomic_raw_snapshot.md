# Atomic Raw Snapshot Publication

Phase 2.3 publishes an accepted `IncomingPairInventory` as one versioned raw
directory without ever exposing a one-workbook or unverified snapshot.

## Publication boundary

`publish_raw_snapshot` derives the final directory from the validated release
ID and raw-snapshot root. It stages only `contaminant_glossary.xlsx` and
`references.xlsx` in a uniquely named hidden sibling directory.

After copying, each staged file's byte size and SHA-256 must equal its Phase
2.2 inventory. The staging directory must contain exactly those two ordinary
files. One directory rename then changes the state from no final release path
to a complete verified pair.

A successful call returns a frozen `RawSnapshotPublication` containing the
original inventory, release ID, final directory, and both versioned workbook
paths. Later validation must read these snapshot paths rather than mutable
files under `data/00_incoming`.

## Failures and cleanup

The Phase 2.3 publisher refuses every existing final target without inspecting
or changing it. The Phase 2.5
[collision and retry layer](intake_collision_and_retry.md) verifies an existing
pair and safely reuses it only when both hashes match the accepted inventory.

Missing or changed sources, copy errors, fingerprint mismatches, unexpected
staging contents, and rename failures return no publication. The publisher
removes only its own staging directory and never deletes a final target that
appears during a race. A cleanup failure reports the exact leftover staging
path instead of broadening deletion.

The tracked January historical snapshot is preserved. Tests publish current
or synthetic sources only into disposable raw roots, and this component writes
no manifest, processed data, report, registry file, or website output.

Phase 2.4 now revalidates the published pair and writes its deterministic
[intake manifest](intake_manifest.md). Existing snapshot and manifest retries
remain Phase 2.5 work.

## Implementation and tests

The result and publisher are implemented in
[`intake.py`](../../src/contaminant_pipeline/intake.py). Focused filesystem,
failure-injection, race, authoritative-isolation, and Git-policy tests are in
[`test_atomic_snapshot.py`](../../tests/test_atomic_snapshot.py).

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_atomic_snapshot.py
```
