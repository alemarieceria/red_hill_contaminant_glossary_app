# Contaminant Pipeline Data Contract

Status: proposed; supervisor approval is required before authoritative workbook changes.

## Immutable contaminant identifiers

### Format

Every contaminant identifier is text in the form `RHC-NNN`, where `NNN` is exactly three decimal digits:

  - The valid range is `RHC-001` through `RHC-999`.
  - `RHC-000` is invalid.
  - The `RHC-` prefix is uppercase.
  - The numeric portion is zero-padded to three digits.
  - Leading or trailing whitespace is invalid.
  - Excel cells containing identifiers must be stored and read as text.

The validation regular expression pattern is `^RHC-[0-9]{3}$`, with the additional rule that the numeric portion cannot be zero.

Identifier capacity must be reviewed before `RHC-900` is issued. Expanding the identifier width requires an approved schema migration; identifiers must not be widened inconsistently.

### Lifecycle

An identifier belongs permanently to one contaminant record. It does not derive from the record's name, CASRN, workbook row, or sort order.

  - Renaming, reordering, or correcting descriptive information does not change the identifier when the contaminant identity remains the same.
  - A new contaminant receives the number after the highest identifier ever issued. Missing numbers and identifiers belonging to retired records are never reused.
  - A retired record keeps its identifier in the permanent registry with a retired status.
  - When records are merged because they describe the same entity, one existing identifier is selected as the survivor. The other identifiers are retired and their relationship to the survivor is recorded.
  - When one record is split into multiple scientifically distinct entities, the original identifier is retired and every resulting entity receives a new identifier.
  - If a correction shows that a record represented a different chemical identity, the old identifier is retired and a new identifier is issued.

Merge, split, and identity-change decisions require scientific review. The pipeline must report those situations rather than decide them automatically.

### Initial bootstrap proposal

The July glossary contains 152 unique legacy `CG ID #` values numbered 1 through 152. Phase 0B will propose converting those values directly:

```text
legacy CG ID # 1   -> RHC-001
legacy CG ID # 152 -> RHC-152
```

This proposal is based on the legacy identifier value, never the workbook row position. It does not become authoritative until reviewed and approved by the supervisor. The pipeline must not write the proposal into an authoritative
workbook.

### Decision examples

| Event | Required result |
| --- | --- |
| Rename `RHC-012` | Keep `RHC-012` |
| Reorder workbook rows | Keep every existing identifier |
| Retire `RHC-025` | Reserve `RHC-025` permanently |
| Add after the highest issued ID `RHC-152` | Issue `RHC-153` |
| Merge two records | Keep one reviewed survivor; retire the other ID |
| Split one record | Retire the parent; issue new IDs for all children |
| Correct a record to a different chemical identity | Retire the old ID; issue a new ID |
