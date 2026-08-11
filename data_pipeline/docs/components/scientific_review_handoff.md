# Scientific Review Handoff

Phase 3.3a turns the scientific validator's machine-readable observations into
a self-contained supervisor review packet. It does not weaken scientific
format errors, approve proposed values, or edit either authoritative workbook.

## System position

```text
3.2 stable identities and relationships
        |
        v
3.3 literal scientific/source validation
        |
        +---- blocking scientific errors remain errors
        |
        v
3.3a pending-value warnings and supervisor review workbook
        |
        +---- data-only correction branch and reviewed evidence
        |
        v
3.3 revalidation must pass before authoritative data reaches 3.4
```

## Pending optional source descriptions

`source_notes_sources` is optional. A true blank cell (`None`) and an exact
zero-length string (`""`) both become canonical null. Each produces a
`pending_source_notes_sources` warning so unfinished text stays visible without
pretending that the row is scientifically invalid.

Whitespace-only text, leading/trailing whitespace, and non-text values remain
errors. There is no universal trimming step: identifiers, reference labels,
delimiters, enums, URLs, and placeholders retain their exact source meaning.

The current source contains six pending descriptions: `RHC-132` is a true
blank, while `RHC-133` through `RHC-137` contain zero-length strings.

## Identifier review is separate from format validation

The 3.3 rules still enforce:

- CASRN syntax and check digits;
- uppercase `14-10-1` InChIKey structure; and
- supported chemical-formula syntax and element symbols.

Phase 3.3a adds review visibility that those checks cannot provide:

| Source state | Canonical treatment | Review treatment |
| --- | --- | --- |
| Real identifier | Parsed only when its local syntax passes | External identity correctness remains a review/evidence concern |
| Blank CASRN/InChIKey | Unknown/null | `unknown_pending` completeness review |
| Allowed `NA`/`N/A` | Explicit `not_applicable` | `unverified_not_applicable` until a per-ID rationale is reviewed |
| Invalid identifier/formula | No successful validated value | Blocking `correction_required` review row |

This distinction means “permitted representation” never means “scientifically
verified.” The `RHC-071` total cis/trans InChIKey exception remains permitted
but appears in the review queue. The code performs no live name matching or
PubChem, CAS Common Chemistry, Wikidata, CompTox, or other network lookup.

## Review package

`build_scientific_review_package` accepts the successful 3.2
`ValidatedIdentityRelationships`, reads only its immutable snapshots, and
collects:

- every 3.3 finding, including blocking errors and non-blocking warnings;
- blocking CASRN, InChIKey, and formula review rows;
- every blank or explicitly not-applicable CASRN/InChIKey;
- every pending optional source description;
- independently supplied evidence proposals; and
- independently supplied records of reviewed mechanical cleanup.

Review rows use the stable contaminant ID, canonical field, and exact source
cell. They preserve current and proposed values side by side. A proposed value
requires a source system, source record ID, and direct HTTP(S) evidence URL.
Approved statuses additionally require explicit reviewer and date fields.

The explicit statuses are `proposed`, `needs_review`, `approved_value`,
`approved_not_applicable`, `unknown_pending`, `correction_required`, and
`resolved`. Formatting is never the decision.

## Supervisor workbook

`write_supervisor_review_workbook` writes only to the ignored generated-output
area by default:

```text
data/04_output/reviews/<data-release-id>/supervisor_review_3_3.xlsx
```

It contains:

| Sheet | Purpose |
| --- | --- |
| `Instructions` | Release context, decision meanings, and the complete workflow |
| `Identifier Review` | Blocking A findings plus blank and N/A CASRN/InChIKey review items |
| `Pending Sources` | Optional descriptions that remain null/pending |
| `Resolved Cleanup` | Separately supplied reviewed B/C correction records |

Generated source/finding columns and reviewer decision/evidence columns have
explicit names and a fixed order. The workbook is deliberately plain: it has
no Excel tables, AutoFilters, cell styling or colors, data validation, frozen
panes, wrapping, or custom row/column dimensions. It contains no cell formulas
and adds no sheet, comment, style, or value to an authoritative workbook. Its
writer uses a temporary sibling and one final replacement so a failed save does
not leave a completed-looking artifact.

## Review and correction workflow

```text
Generate review workbook
        |
        v
Reviewer records decision, evidence, name, date, and rationale
        |
        v
Maintainer applies only approved changes on a data-only branch
        |
        v
Changed workbook receives a new immutable workbook_revision
        |
        v
Rerun 3.1 -> 3.2 -> 3.3
        |
        v
Reconcile each review row as resolved, still_failing, or superseded
```

`reconcile_scientific_review_items` compares stable ID, canonical field, and
source row with later findings. It never edits Excel and never treats a filled
review cell alone as proof that authoritative data changed.

## Current authoritative review baseline

Before the separately preserved B/C cleanup is applied, 3.3a records:

- 21 errors: one alias delimiter, one CASRN, five formulas, and fourteen
  narrative values with surrounding whitespace;
- 57 warnings: six pending source descriptions, 32 blank CASRN/InChIKey
  fields, and 19 permitted-but-unverified CASRN/InChIKey N/A fields; and
- 63 supervisor review rows: six blocking scientific values, six pending
  sources, 32 blank identifiers, and 19 N/A identifiers.

The alias/whitespace corrections are preserved separately for a later
data-only branch. Phase 3.3a neither applies nor deletes them.

## Tests

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_scientific_review.py
```

The suite covers optional empty-string semantics, whitespace errors, review
statuses and evidence, identifier review categories, deterministic ordering,
frozen records, workbook sheets/headers/formula absence, reconciliation,
release-scoped output paths, authoritative counts, and protected-file
isolation.
