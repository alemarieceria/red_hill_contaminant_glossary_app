# Workbook Inventory

Phase 2.2 turns an accepted in-memory workbook pair into a deterministic,
read-only description of its source bytes and structure. It still publishes no
snapshot or manifest.

## Exact source fingerprint

`read_workbook` reads each source path into one byte image. The SHA-256 digest
and byte size are calculated from that image, and OpenPyXL reads formula
definitions and cached values from separate in-memory streams over the same
bytes. The resulting `WorkbookSnapshot` therefore ties its structure and
values to one exact source fingerprint.

## Inventory contents

`inventory_incoming_pair` accepts the `IncomingWorkbookPair` from Phase 2.1 and
returns a frozen `IncomingPairInventory`. It records:

- workbook filename, type, schema, revision, byte size, digest, warning count,
  populated-cell total, and formula total;
- ordered worksheets with physical dimensions and logical data-row counts;
- tables with ranges, bounds, headers, and declared and populated row counts;
- header text with exact coordinates and column positions; and
- formulas with coordinates, definitions, and cached-value presence.

Physical `max_row` is not treated as a data-row count. Excel formatting extends
the current authoritative worksheets to rows 1000 and 1001, so logical counts
use populated cells within the configured tabular columns.

## Completeness and failures

The inventory requires the supported sheets and tables and rejects missing,
duplicate, or unknown structure. Headers must be unique nonblank literal text,
required data regions must contain rows, and declared table ranges must be
internally consistent. Exact schema header allowlists and scientific values
remain Phase 3 responsibilities.

Failures raise `IncomingContractError` with workbook and structural context and
return no pair inventory. The operation never saves an Excel file or creates a
snapshot, manifest, report, cache, processed table, or website output.

Phase 2.3 consumes the successful pair inventory and publishes its exact bytes
as an [atomic raw snapshot](atomic_raw_snapshot.md).

## Implementation and tests

The reader fingerprint is implemented in
[`io_excel.py`](../../src/contaminant_pipeline/io_excel.py). Inventory records
and validation are in [`intake.py`](../../src/contaminant_pipeline/intake.py).
Focused tests are in
[`test_workbook_inventory.py`](../../tests/test_workbook_inventory.py) and
[`test_io_excel.py`](../../tests/test_io_excel.py).

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_io_excel.py tests/test_workbook_inventory.py
```
