# Workbook Contract Validation

Phase 3.1 is the structural quality gate between a completed intake and later
relationship, scientific, and canonical-value validation. It confirms that the
immutable raw workbooks still match their accepted release and contain exactly
the named columns supported by their declared schema.

## Input boundary

`validate_workbook_contract` accepts only a completed `IntakePublication`.
It resolves the two stable workbook filenames from that publication's
versioned raw snapshot directory; it never reads `data/00_incoming`.

The function reads each raw workbook once through the existing Excel boundary,
then reuses the Phase 2 incoming and inventory functions. Those functions
recheck:

- stable filenames and workbook roles;
- Metadata structure, revisions, compatibility, and release identity;
- the supported workbook schema;
- required sheets, tables, table bounds, and populated tabular regions; and
- exact byte size, SHA-256, and deterministic structural inventory.

The newly observed raw inventories must equal the completed intake inventories.
A missing, replaced, or modified raw workbook therefore cannot become a
validated Phase 3 input.

## Schema 1.0.0 header contract

The additional Phase 3.1 check compares named headers with the existing source
maps and Metadata contract:

| Workbook | Sheet or table | Required named columns |
| --- | --- | --- |
| Glossary | `Glossary` / `Table_1` | The 50 names in `GLOSSARY_HEADER_MAP` |
| Glossary | `Footnotes` | `id`, `text` |
| Glossary | `Metadata` / `MetadataTable` | `key`, `value` |
| References | `Sheet1` | `compound_name`, `source`, `link` |
| References | `Metadata` / `MetadataTable` | `key`, `value` |

Header names must match exactly, including case and whitespace. Missing,
renamed, duplicated, blank, non-text, and unknown named columns fail. Column
order is non-semantic: the same exact names may appear in another order, while
their physical positions remain recorded in inventory for later processing and
comparison.

Header contracts are selected explicitly by workbook schema version. A schema
that is unsupported—or is marked supported without its own header contract—
fails closed rather than borrowing another version's columns.

## Result and errors

A successful call returns frozen `ValidatedWorkbookContract` data containing:

- the completed intake publication;
- the newly read raw `IncomingWorkbookPair`;
- the newly calculated raw `IncomingPairInventory`;
- the validated `data_release_id`; and
- the workbook `schema_version`.

Later Phase 3 components can consume those retained immutable snapshots without
reopening Excel. Non-blocking Excel reader warnings remain attached to them.

Failures raise `WorkbookContractError` and return no partial validated result.
Messages identify the release and relevant workbook, sheet, table, or header
difference. When Phase 2 reading or inventory fails, the lower-level
`IncomingContractError` remains chained as the cause.

Validation is read-only. It does not save Excel, update a manifest or registry,
or create processed tables, reports, output bundles, public data, or CLI
behavior.

## Scope boundary

This component checks structure only. It does not validate IDs, reference or
footnote joins, scientific identifiers or values, formula results, URLs,
pesticide semantics, canonical records, reports, or exports. Those remain tasks
3.2 through 3.7. Command-line validation remains Phase 4.3.

## Tests

Focused tests cover successful synthetic and authoritative releases,
snapshot-only paths, deterministic frozen results, warning preservation,
header variations, structural failures, raw mutations, schema-contract
failures, exception chaining, and protected-file isolation.

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_workbook_contract_validation.py
```

Run the adjacent contract tests with:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_metadata.py tests/test_workbook_inventory.py tests/test_workbook_contract_validation.py
```
