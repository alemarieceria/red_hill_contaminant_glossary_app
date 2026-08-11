# Identity and Relationship Validation

Phase 3.2 connects each structurally valid workbook row to durable project
identity. It runs after [workbook contract validation](workbook_contract_validation.md)
and before scientific-field validation.

## System position

```text
Completed immutable intake
        |
        v
3.1 workbook structure and exact headers
        |
        v
3.2 stable IDs, references, footnotes, duplicate candidates
        |
        v
3.3 scientific syntax, check digits, values, and URLs
```

`validate_identity_relationships` accepts only a
`ValidatedWorkbookContract`. It consumes the retained raw workbook snapshots
and never reads mutable `data/00_incoming` files. The registry and crosswalk
paths default to the tracked CSV assets but can be replaced by temporary test
assets. Validation never writes workbooks, registry assets, or output files.

## Release-aware identity

Schema `1.0.0` does not contain `RHC-NNN` directly. Each glossary row must
therefore supply a literal positive integer `CG ID #`. The validator joins
that legacy value to `registry.id_legacy_cg` and obtains the permanent
`id_contaminant`. It never derives identity from row position, name, CASRN, or
InChIKey.

Registry state is viewed as it existed at the selected data release:

- identities issued later are ignored;
- identities retired on or before the release cannot be current rows;
- every identity active at the release must occur exactly once; and
- an active schema-1.0.0 identity must have a legacy ID the workbook can carry.

Release comparisons use the shared `release_order_key`, including numeric
same-day revision ordering such as `-r2` before `-r10`.

A workbook name that differs from the registry review name is a warning, not a
new identity. The resolved `RHC-NNN` remains unchanged.

## Reference and footnote joins

Each populated reference row requires a literal, nonblank text
`compound_name`. The exact source characters are looked up only in crosswalk
entries reviewed on or before the selected release. There is no trimming,
case folding, punctuation repair, or fuzzy matching. Repeated citation rows
are retained. A reviewed label that differs from the current target glossary
name produces one informational finding per distinct label without invalidating
the join.

The validator reuses `validate_footnote_relationships` with the resolved stable
IDs. Definition and usage problems are translated into the common Phase 3.2
finding format. Whether pesticide values semantically require footnote `D`
remains Phase 3.4.

## Possible duplicate reporting

Exact case-sensitive names shared by distinct IDs are warnings. CASRN and
InChIKey strings are split only on the literal ` | ` delimiter and exact tokens
shared by distinct IDs are warnings. Exact placeholders `NA` and `N/A` are
excluded. Syntax, N/A applicability, and check-digit validity are enforced by
the following Phase 3.3 gate.

Each `DuplicateIdentityCandidate` retains the source value, affected stable
IDs, and source rows. These findings never merge rows, change an ID, or update
the workbooks or registry.

## Result and failure behavior

A successful `ValidatedIdentityRelationships` is frozen and retains:

- its validated 3.1 contract and release/schema identity;
- registry and crosswalk rows applicable to that historical release;
- resolved glossary identities and each reference relationship;
- validated footnote definitions and usages;
- duplicate candidates; and
- deterministically ordered warning and informational findings.

Every finding has a stable code, category, severity, message, and available
workbook, sheet, row, field, stable-ID, and source-value context. The validator
collects independent problems when it is safe to continue. Any error raises
`IdentityRelationshipValidationError` carrying all sorted findings and returns
no partial usable result. Warning- and info-only runs succeed.

The next gate is documented in
[scientific field validation](scientific_field_validation.md).

## Scope boundary

Phase 3.2 does not validate CASRN check digits, InChIKey structure, formula
results, chemical formulas, regulatory values, URLs, pesticide semantics,
canonical CSVs, reports, manifests, comparisons, exports, or CLI commands.

## Tests

From `data_pipeline`, run the focused tests with:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_identity_relationship_validation.py
```

The suite covers release ordering, snapshot-only reads, identity lifecycle,
exact and override reference joins, repeated citations, footnotes, error
aggregation, duplicate candidates, frozen results, and the authoritative
152-identity/406-reference baseline while auditing protected files.
