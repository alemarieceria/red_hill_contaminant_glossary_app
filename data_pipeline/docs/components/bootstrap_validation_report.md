# Bootstrap Validation Report

This component gives bootstrap validation results one consistent in-memory
shape and a deterministic plain-text presentation. It can describe successful
counts, warnings, and row-level failures across names, IDs, references,
footnotes, and workbook compatibility.

## Place in the pipeline

Phases 0B.1 through 0B.3 implement individual ID, crosswalk, and Metadata
components. Phase 0B.4 defines how their eventual combined results are recorded
and displayed. Phase 0B.5 will read the real workbook snapshots, run the full
bootstrap validation, calculate the counts, and populate this report.

The report layer does not read Excel, repeat component validation, catch
unrelated errors, write CSV or JSON, add CLI behavior, or freeze the permanent
registry and crosswalk.

## Report contents

`BootstrapReportCounts` contains nine nonnegative integer counts:

- glossary rows;
- assigned contaminant IDs;
- distinct glossary names;
- reference rows;
- distinct reference labels;
- exact-match reference rows;
- override reference rows;
- footnote definitions; and
- glossary footnote usages.

`BootstrapFinding` records one observation using:

- a category: `names`, `ids`, `references`, `footnotes`, or `workbooks`;
- a severity: `info`, `warning`, or `error`;
- a stable code and concise message; and
- optional workbook, sheet, source-row, and source-value context.

Optional context is included only when the validation caller supplies it. The
report does not independently inspect or publish private canonical fields.

`BootstrapValidationReport` combines the counts, an optional successful
`WorkbookCompatibility`, sorted findings, and an automatically derived status.
The records and finding collection are immutable.

## Status and compatibility rules

Info and warning findings preserve a `passed` status. Any error produces
`failed`.

A successful compatibility result supplies the report's `data_release_id` and
cannot coexist with a workbook-category error. If compatibility is unavailable,
the report requires a workbook-category error and displays:

```text
data_release_id: unavailable
workbook_compatibility: unavailable
```

These rules prevent a report from claiming that workbook Metadata both passed
and failed.

## Deterministic construction and formatting

`build_bootstrap_report` receives already-computed counts, compatibility, and
findings. It validates record types, copies findings into an immutable tuple,
and sorts them by severity, category, code, location, source value, and message.
It preserves repeated findings because two source rows can have the same
problem.

`format_bootstrap_report` produces stable plain text containing status,
release/workbook compatibility, all counts, and all findings. It does not emit
Python object representations or memory addresses, so equal reports produce
equal text regardless of caller insertion order.

## Validation and failure behavior

Counts reject booleans, negative numbers, floats, text, and nulls. Finding
categories and severities must use their declared enums. Codes and messages
must be nonblank exact text without surrounding whitespace. Optional text
context must be meaningful when present, and source rows must be positive
integers.

The builder rejects invalid input record types and contradictory compatibility
sections before returning a report. It does not modify any caller collection or
workbook.

## Implementation and tests

The implementation is in
[`bootstrap_report.py`](../../src/contaminant_pipeline/bootstrap_report.py).
Focused tests are in
[`test_bootstrap_report.py`](../../tests/test_bootstrap_report.py).

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest tests/test_bootstrap_report.py
```
