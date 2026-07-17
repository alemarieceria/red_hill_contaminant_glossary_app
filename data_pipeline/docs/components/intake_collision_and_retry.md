# Intake Collision and Retry Behavior

Phase 2.5 makes repeated intake safe. A release ID comes from workbook
revisions, not from file hashes, so an existing release may be either the exact
same source pair or a conflicting reuse of an immutable identity.

## Pipeline position

This component runs after the incoming pair has passed the stable contract and
inventory stages. It coordinates the atomic raw-snapshot and manifest
publishers. A successful result is the boundary downstream code may use: both
the verified raw pair and its deterministic manifest exist and agree.

Its input is one `IncomingPairInventory`. Its output is a frozen
`IntakePublication` containing the inventory, raw publication, manifest
publication, disposition, and two booleans identifying which artifacts this
call created.

## Outcomes

- `created`: this call published the raw snapshot and completed the intake.
- `recovered`: an exact raw snapshot already existed and this call published
  its missing manifest.
- `existing`: both exact artifacts already existed, so the call returned them
  without copying or writing anything.

The original manifest bytes and Git provenance are retained on an exact retry.
Current Git state is not release identity and does not rewrite history.

## Identity and collision rules

Each workbook is identified by workbook type, workbook revision, byte size,
and SHA-256. The source pair is the fixed glossary-then-references tuple plus
the derived release ID.

Before publication, completed manifests are read as the release-history index.
Reusing the same workbook type and revision with a different size or hash is a
collision, even under another release ID. Reusing one unchanged workbook while
the other legitimately advances is allowed.

Existing raw files are independently hashed. Existing manifests must be
ordinary files, valid UTF-8 JSON with no duplicate keys, use the supported
schema and exact structure, have portable paths, and already be in canonical
deterministic form. For the current release, rebuilding with the manifest's
original Git record must reproduce its bytes exactly.

## Failure and race behavior

A manifest without its raw snapshot, damaged artifacts, malformed history, or
different identities fail closed. Existing files are never repaired, removed,
or overwritten by reconciliation.

If another attempt wins after preflight, the final artifact is inspected once.
An exact winner is reused; a different or malformed winner is preserved and
reported as a collision. There is no loop, sleep, lock file, or network call.

If raw publication succeeds and manifest publication fails, the verified raw
pair remains as a recoverable Phase 2.3 artifact. No completed intake result is
returned. The next identical call can publish only the missing manifest.
Temporary cleanup remains owned by the atomic publishers.

## Implementation and tests

The records, inspectors, history check, and `publish_or_reuse_intake` are in
[`intake.py`](../../src/contaminant_pipeline/intake.py). Focused tests are in
[`test_intake_collision.py`](../../tests/test_intake_collision.py).
The complete public-chain and protected-state proof is documented in the
[Phase 2 intake acceptance tests](intake_acceptance_tests.md) and implemented
in [`test_intake_end_to_end.py`](../../tests/test_intake_end_to_end.py).

Run them from `data_pipeline/`:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_intake_collision.py
```
