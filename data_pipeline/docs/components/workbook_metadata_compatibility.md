# Workbook Metadata Compatibility

This component validates the small `MetadataTable` that identifies each
authoritative workbook and determines whether the glossary and references can
be processed together.

## Place in the pipeline

The read-only Excel boundary first converts each `.xlsx` file into a
`WorkbookSnapshot`. Phase 0B.3 then extracts and validates Metadata from those
snapshots. Later bootstrap reporting can use the compatibility result alongside
the ID and reference-crosswalk results.

This component does not compare historical hashes, create raw snapshots or
manifests, validate contaminant relationships, or write to Excel. Historical
collision detection and intake persistence remain Phase 2 responsibilities.

## Required workbook structure

Each workbook must contain exactly one worksheet named `Metadata` with exactly
one Excel table named `MetadataTable`. The table may be positioned anywhere,
but its declared range must contain exactly these two columns and three rows:

| key | value |
| --- | --- |
| `workbook_type` | `contaminant_glossary` or `references` |
| `schema_version` | Currently `1.0.0` |
| `workbook_revision` | `YYYYMMDD` or `YYYYMMDD-rN` for `N >= 2` |

The three data rows may appear in any order. Keys and values must be literal,
nonblank text with exact capitalization and no surrounding whitespace.
Formulas, duplicate keys, missing keys, and additional keys are rejected.

## Inputs and outputs

`extract_workbook_metadata` receives one immutable `WorkbookSnapshot`. It
returns an immutable `WorkbookMetadata` containing `workbook_type`,
`schema_version`, and `workbook_revision`. It reads the table's declared range
and performs no file access itself.

`validate_workbook_compatibility` receives the extracted glossary and
references records. It returns an immutable `WorkbookCompatibility` containing
both records and their derived `data_release_id`.

## Compatibility and release ordering

A pair is compatible when:

- the glossary declares `contaminant_glossary`;
- the references workbook declares `references`;
- both schema versions are equal and supported; and
- both revisions follow the release-ID contract.

The revisions do not need to be equal. An unchanged workbook legitimately
retains an older revision.

The combined `data_release_id` is the newer revision. Comparison uses calendar
date followed by numeric same-day revision, with the unsuffixed form treated as
revision 1. Consequently, `20260716-r10` is newer than `20260716-r2`; ordinary
text sorting is not used.

## Errors and safety

Structural and value errors raise `ValueError` with workbook and Metadata-table
context. Pair errors distinguish incorrect workbook types, mismatched schemas,
unsupported schemas, and invalid revisions. A failure returns no compatibility
result and cannot partially alter either workbook.

The current authoritative pair declares:

| Workbook | Type | Schema | Revision |
| --- | --- | --- | --- |
| Contaminant glossary | `contaminant_glossary` | `1.0.0` | `20260716` |
| References | `references` | `1.0.0` | `20260716` |

Their derived release ID is `20260716`. The real-workbook test reads both files
and verifies their bytes are unchanged afterward.

## Implementation and tests

The implementation is in
[`metadata.py`](../../src/contaminant_pipeline/metadata.py). Focused and
read-only integration tests are in
[`test_metadata.py`](../../tests/test_metadata.py).

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest tests/test_metadata.py
```
