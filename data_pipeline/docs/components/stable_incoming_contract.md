# Stable Incoming Workbook Contract

Phase 2.1 establishes the read-only boundary between the two mutable submission
files in `data/00_incoming` and later intake stages. It does not publish a raw
snapshot or create any generated files.

## Required inputs

`read_incoming_pair` accepts an incoming directory and defaults to the
centralized production location. It selects exactly these stable roles by
filename:

| Role | Required filename | Required `workbook_type` |
| --- | --- | --- |
| Glossary | `contaminant_glossary.xlsx` | `contaminant_glossary` |
| References | `references.xlsx` | `references` |

Unrelated directory entries do not affect selection. The function does not
rename or reassign files based on their internal Metadata.

Both files are read once through `io_excel.read_workbook`. That boundary closes
the Excel handles and returns immutable `WorkbookSnapshot` records containing
the workbook structure, values, formulas, resolved source path, and any
non-blocking reader warnings.

## Validation and output

The existing Metadata component extracts `workbook_type`, `schema_version`, and
`workbook_revision` from each snapshot. Compatibility requires the expected
workbook roles and one shared supported schema version. Revisions may differ
when one workbook is reused unchanged.

The derived `data_release_id` is the newer revision by calendar date and then
numeric same-day revision. An unsuffixed value is revision 1, so `-r10` is
newer than `-r2`.

A successful call returns a frozen `IncomingWorkbookPair` containing:

- the glossary snapshot;
- the references snapshot; and
- their validated `WorkbookCompatibility` and derived release ID.

Retaining both already-read snapshots allows the inventory stage to inspect the
same in-memory inputs without reopening mutable incoming files.

Phase 2.2 now adds an exact source fingerprint and deterministic structural
inventory to this result. See the [workbook inventory](workbook_inventory.md)
component for those rules.

## Failures and safety

`IncomingContractError` identifies a missing incoming directory, missing or
unreadable required workbook, invalid Metadata, or incompatible pair. Workbook
read and Metadata errors are chained as the underlying cause, and messages
retain the affected role and path. No partial incoming-pair result is returned.

This component never saves or modifies an authoritative workbook and creates
no manifest, snapshot directory, processed table, report, cache, or website
data. Atomic copying, manifests, collisions, retries, and CLI exposure remain
later tasks.

## Implementation and tests

The implementation is in
[`intake.py`](../../src/contaminant_pipeline/intake.py). Focused tests, including
the read-only authoritative integration check, are in
[`test_intake.py`](../../tests/test_intake.py).

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_intake.py
```
