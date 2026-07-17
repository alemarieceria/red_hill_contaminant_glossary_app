# Bootstrap Validation

This component runs the Phase 0B rules together against two already-read
workbook snapshots. It confirms that the current glossary, reference, Metadata,
and footnote relationships form one coherent in-memory bootstrap.

## Place in the pipeline

The Excel reader first creates immutable `WorkbookSnapshot` values. Bootstrap
validation then coordinates the focused components created in 0B.1 through
0B.4. A passing result contains the complete relationships that 0B.6 freezes
as pipeline-owned assets.

This component does not open or save workbooks, normalize all canonical
fields, validate reference URLs or duplicate citations, interpret pesticide
status, write reports/manifests/snapshots, add CLI behavior, or persist the
registry and crosswalk.

## Execution order

`validate_bootstrap_snapshots` performs these steps:

1. Convert any non-blocking Excel-reader warnings into workbook warnings.
2. Extract and validate both Metadata tables and their compatibility.
3. Locate the glossary table and required name, legacy-ID, and footnote fields.
4. Generate the complete stable-ID mapping and join it back by legacy ID.
5. Validate exact glossary names and reject ambiguity.
6. Locate every populated reference row and resolve its review label through
   exact matching or the reviewed override mapping.
7. Count exact and override resolution methods across original reference rows.
8. Validate footnote definitions and each glossary footnote usage.
9. Populate all nine bootstrap counts and build the deterministic report.
10. Return complete relationships only when the report passes.

Independent checks continue after recoverable problems. A check whose
prerequisite is unavailable is not run, preventing one root error from creating
misleading downstream failures.

## Successful and failed outputs

A successful run returns immutable `ValidatedBootstrap` data containing:

- the passing `BootstrapValidationReport`;
- `WorkbookCompatibility` and its `data_release_id`;
- glossary name-to-ID identities;
- legacy-to-stable ID mappings;
- the reference crosswalk;
- footnote definitions; and
- per-contaminant footnote usages.

If any error finding exists, the function raises `BootstrapValidationError`.
The exception carries the complete failed report for future CLI presentation,
but no partial collection is returned as persistable validated data.

Known reviewed reference overrides create one informational finding per
distinct label. They remain visible for maintenance but do not fail validation.

## Footnote relationship rules

The `Footnotes` sheet must have exact `id` and `text` headers. Definitions must
be unique literal text. IDs follow `^[A-Z][A-Z0-9_-]*$`.

A blank glossary footnote cell means no usage. Otherwise the value must be
literal text containing comma-separated IDs. Whitespace around tokens is
trimmed while token order is preserved. Empty, duplicate, malformed, or unknown
tokens fail with glossary row and source-value context. Multiple contaminants
may use the same definition.

This phase confirms only that footnote relationships resolve. Phase 3 will
interpret special pesticide/footnote-D combinations during normalization.

## Current authoritative result

The current pair passes with release ID `20260716`:

| Report value | Count |
| --- | ---: |
| Glossary rows | 152 |
| Assigned IDs | 152 |
| Distinct glossary names | 152 |
| Reference rows | 406 |
| Distinct reference labels | 133 |
| Exact-match reference rows | 343 |
| Override reference rows | 63 |
| Footnote definitions | 4 |
| Footnote usages | 33 |

The 21 distinct reviewed override labels produce 21 informational findings.
Footnote usage counts are `A:15`, `B:10`, `C:6`, and `D:2`.

## Read-only guarantee

The orchestration function accepts snapshots rather than file paths and has no
file-writing behavior. The authoritative integration test compares both input
files byte-for-byte and checks the pipeline data-artifact directories before
and after validation.

## Implementation and tests

Footnote relationship behavior is implemented in
[`footnotes.py`](../../src/contaminant_pipeline/footnotes.py). Orchestration is
implemented in
[`bootstrap_validation.py`](../../src/contaminant_pipeline/bootstrap_validation.py).

Focused and integration tests are in
[`test_footnotes.py`](../../tests/test_footnotes.py) and
[`test_bootstrap_validation.py`](../../tests/test_bootstrap_validation.py).
The final Phase 0B integration proof is in
[`test_bootstrap_end_to_end.py`](../../tests/test_bootstrap_end_to_end.py). It
repeats the authoritative bootstrap, compares the result with both tracked
registry assets, proves exact and reviewed-override relationships, and checks
that an unmatched in-memory label fails without changing protected files.

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest tests/test_footnotes.py tests/test_bootstrap_validation.py
```
