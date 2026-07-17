# Contaminant Pipeline Data Contract

## Operating model

The two updated Excel workbooks in `data/00_incoming` are the only external
data inputs required for a routine release. The pipeline treats them as
authoritative source data, reads them without modification, and creates its
registry, crosswalk, validation, normalized, and website outputs outside the
workbooks. The historical data-collection and enrichment workflow is optional
future work and is not a release prerequisite.

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

### Initial bootstrap mapping

The July glossary contains 152 unique legacy `CG ID #` values numbered 1 through 152. Phase 0B will map those values directly:

```text
legacy CG ID # 1   -> RHC-001
legacy CG ID # 152 -> RHC-152
```

This mapping is based on the legacy identifier value, never the workbook row
position. The pipeline records the mapping in its tracked registry and adds the
stable ID to derived outputs; it does not need to write the ID into an
authoritative workbook.

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

## Workbook Metadata and versions

### Metadata sheet and table

Both authoritative workbooks must contain a worksheet named `Metadata`. The
worksheet must contain one Excel table named `MetadataTable` with exactly two
columns named `key` and `value`.

For schema version `1.0.0`, the table contains exactly these three keys:

| key | Required value |
| --- | --- |
| `workbook_type` | `contaminant_glossary` in the glossary workbook; `references` in the references workbook |
| `schema_version` | `1.0.0` |
| `workbook_revision` | A release-style identifier such as `20260713` or `20260713-r2` |

Keys and values are stored as text. Keys are unique and nonblank. Missing,
duplicate, blank, or unknown keys are invalid for schema version `1.0.0`. Row
order has no meaning, and formatting must not carry metadata meaning.

### Version meanings

The three version concepts have different responsibilities:

- `schema_version` identifies the workbook structure and field meanings that
  the pipeline supports. Both workbooks in one pipeline run must declare the
  same supported schema version. The initial supported version is `1.0.0`.
- `workbook_revision` identifies the data-release event in which that
  authoritative workbook file last changed. The two workbook revisions may
  differ when one workbook is reused unchanged.
- `data_release_id` identifies the combined glossary-and-references release.
  It is derived by the pipeline and recorded in manifests, processed outputs,
  app data, release directories, and GitHub Releases. It is not a fourth value
  that must be copied into both workbooks.

### Workbook revision format

A workbook revision uses one of these forms:

```text
YYYYMMDD
YYYYMMDD-rN, where N is an integer greater than or equal to 2
```

The date portion must be a real calendar date. The first accepted combined
release on a date uses the unsuffixed form, which is implicitly revision 1.
`-r1` is invalid. A second accepted combined release on that date uses `-r2`,
then `-r3`, and so on. Revision suffixes belong to the combined release
sequence for that date, not to separate per-workbook counters.

The text format is `^[0-9]{8}(?:-r(?:[2-9]|[1-9][0-9]+))?$`, followed by the
real-calendar-date check. Leading or trailing whitespace, omitted zero padding,
uppercase `R`, and leading zeroes in the revision number are invalid.

Every workbook file changed in one data-update pull request uses the same new
workbook revision. A workbook that did not change retains both its earlier
revision and its existing file contents.

### Combined data release ID

The pipeline derives `data_release_id` from the newer of the two workbook
revisions. Revisions are ordered first by calendar date and then by revision
number, treating the unsuffixed form as revision 1. At least one input workbook
therefore has a `workbook_revision` equal to the derived `data_release_id`.

Examples:

| Glossary revision | References revision | Derived data release ID | Meaning |
| --- | --- | --- | --- |
| `20260713` | `20260713` | `20260713` | Both workbooks changed in the first July 13 release |
| `20260805` | `20260713` | `20260805` | Only the glossary changed |
| `20260805` | `20260805-r2` | `20260805-r2` | References changed in a second release on August 5 |

The comparison uses the tuple `(calendar date, revision number)`, where an
unsuffixed revision has revision number 1. It does not use ordinary text
sorting.

### Compatibility and collision rules

The workbooks are compatible for intake only when:

- Each workbook declares its expected `workbook_type`.
- Both declare the same schema version and the pipeline supports that version.
- Both workbook revisions are valid. They are not required to be equal.
- Later relationship validation confirms that references and footnotes resolve
  against the selected glossary.

Compatibility does not require equal workbook revisions. An unchanged
workbook retains its previous revision and file contents when paired with a
new revision of the other workbook.

For each `workbook_type`, a previously used `workbook_revision` must always
identify the same file hash. Reusing that type and revision with different file
contents is an error. A `data_release_id` must also identify one stable pair of
source workbook revisions and hashes; it cannot be reused for a different
combined release.

The release manifest will record:

- The derived `data_release_id`
- Both workbook types and revisions
- Both source file names, sizes, and SHA-256 hashes
- The source Git commit, or an explicit local/unknown state

### Authoritative-workbook boundary

The pipeline reads and validates Metadata but never adds, changes, or removes
Metadata in an authoritative workbook. Pipeline-owned manifests and derived
outputs are written outside `data/00_incoming`.

### Contract decision cases

| Input or event | Required result |
| --- | --- |
| Both workbooks declare `1.0.0` and valid types and revisions | Continue to relationship validation |
| One workbook is unchanged while the other has a newer revision | Accept the differing revisions and derive the newer one as `data_release_id` |
| A second accepted release occurs on the same date | Use the next combined suffix, beginning with `-r2` |
| A Metadata key is missing, duplicated, blank, or unknown | Reject the workbook |
| A revision has an invalid date or suffix | Reject the workbook |
| Workbook types are missing, reversed, or unknown | Reject the workbook pair |
| Schema versions differ or are unsupported | Reject the workbook pair |
| A workbook type and revision are reused with a different hash | Report a collision and reject intake |
| A data release ID is reused for a different source pair | Report a collision and reject intake |

## Reference relationships

### Production relationship

`contaminant_id` is the only production join key between contaminants and
references. Each reference row belongs to exactly one contaminant, and one
contaminant may have zero, one, or many reference rows. A reference ID must
resolve to exactly one contaminant in the selected release.

`compound_name` remains on every reference row as a human-readable review
label. It is not a fallback key. If the label disagrees with the current
glossary name, validation reports the mismatch without changing or inferring
the ID.

The canonical reference fields are `contaminant_id`, `compound_name`, `source`,
and `link`. All four are required and nonblank in normalized output. `link`
must be an absolute `http` or `https` URL.

### Initial crosswalk

The pipeline creates the initial crosswalk from the current glossary and
references workbooks without modifying either file:

1. Build the contaminant registry from the glossary's immutable IDs.
2. Group reference rows by their exact `compound_name` text.
3. Propose an ID only when that text equals one unique glossary name.
4. Apply a tracked, version-controlled override for each known non-exact name.
5. Reject any name that has neither one exact match nor one override, or whose
   override points to a missing ID.
6. Write resolved IDs to derived reference output, never back to Excel.

Matching is case-sensitive and punctuation-sensitive. The pipeline does not
trim, case-fold, remove punctuation, fuzzy-match, or select from multiple
candidates. The tracked override is the durable resolution for known spelling,
capitalization, punctuation, or alternate-name variants. If a future workbook
introduces a new unresolved name, the run fails with the name and source row in
the validation report so the pipeline's crosswalk can be corrected explicitly.

Repeated rows with the same reference name are allowed and receive the same
resolved contaminant ID. Duplicate `source` and `link` pairs for the same ID are
reported rather than silently removed.

### Reference decision cases

| Input | Required result |
| --- | --- |
| One exact glossary-name match | Use that contaminant's ID |
| One tracked override to an existing ID | Use the override and retain the original review label |
| No exact match and no override | Reject and report the unresolved row |
| More than one possible contaminant | Reject; never guess |
| Override points to an absent ID | Reject the stale override |
| ID resolves but review label differs from the current glossary name | Report a label mismatch; keep joining by ID |
| Several references resolve to one ID | Accept the one-to-many relationship |

## Null and controlled-value semantics

### Null states

The pipeline preserves three different meanings:

| Source value | Canonical meaning |
| --- | --- |
| Blank cell | Unknown or not supplied; canonical null |
| Boolean `FALSE` | Explicitly reviewed false; canonical `false` |
| Text `N/A` | The field does not apply; canonical not-applicable state |

A blank boolean is not converted to `false`, and `N/A` is not converted to a
blank. Whitespace-only text is invalid rather than meaningful data. The legacy
atom-count token `NA` is accepted only in the `C`, `N`, `F`, `Cl`, and `Br`
source columns and maps explicitly to the canonical not-applicable state.

### Pesticide status

The source `Pesticide` cell and footnote D produce exactly one canonical
`pesticide_status` value:

| Source state | Canonical value |
| --- | --- |
| Boolean `TRUE` without footnote D | `pesticide` |
| Text `Contaminant` with footnote D | `pesticide_product_contaminant` |
| Blank with footnote D | `pesticide_product_contaminant` |
| Boolean `FALSE` without footnote D | `not_pesticide` |
| Blank without footnote D | `unknown` |
| Text `N/A` without footnote D | `not_applicable` |

`Contaminant` without footnote D is invalid. Footnote D combined with `TRUE`,
`FALSE`, or `N/A` is invalid. This makes the footnote and normalized value
consistent while preserving the existing blank-plus-D source case.

### Footnote relationship

Footnotes form a separate relationship:

```text
contaminant_id -> footnote_id -> footnote text
```

The `Footnotes` sheet contains unique, nonblank `id` and `text` columns.
Footnote IDs use `^[A-Z][A-Z0-9_-]*$`. The glossary `Footnotes` cell is blank
for no footnotes or a comma-separated list of IDs. Parsing trims whitespace
around comma-separated tokens while rejecting empty tokens, duplicates,
unknown IDs, and other delimiters. Output stores an ordered list of IDs and
exports each footnote text once.

## Canonical schema and publication

The complete schema, allowed values, ownership, units, null behavior, source
mapping, and public allowlist are defined in
[`canonical_schema.md`](canonical_schema.md). Only fields marked public may be
written to website JSON. A source field that is absent from the allowlist stays
private, and every newly encountered column defaults to private until the
schema explicitly supports it.

## Schema-change protocol

### Change classes

| Change | Schema effect | Pipeline behavior |
| --- | --- | --- |
| Value or row changes within the existing contract | No schema-version change | Validate and process normally |
| Documentation clarification with no data meaning change | Patch increment | Existing data remains compatible |
| New optional field with defined type, null rules, and privacy | Minor increment | Support old and new minor versions when practical |
| Removed or renamed required field; changed type, unit, identifier, allowed values, formula meaning, or relationship | Major increment | Require an explicit migration and updated tests |

Schema versions use semantic versioning: `MAJOR.MINOR.PATCH`. A field rename is
never handled by silently accepting both spellings; its migration identifies
the old name, new name, supported transition versions, and deterministic value
mapping.

### Unknown structures

Adding, removing, reordering, or renaming a required sheet, table, Metadata key,
or column is a structural change. The pipeline inventories the input before
processing. Unknown columns remain private but still block publication until
their presence is recorded in a supported schema version; missing or changed
required fields block all processing. Meaning may not exist only in formatting,
cell color, comments, or formulas without documented canonical behavior.

A schema update records:

- The affected workbook, sheet, table, and field.
- Its purpose, canonical name, type, owner, units, allowed values, null policy,
  derivation, and publication status.
- The semantic-version change and compatibility range.
- Any migration for existing records.
- Tests for accepted data and each new failure mode.

The updated spreadsheets remain the routine external input. Supporting a new
structure is a pipeline-maintenance task, not an approval gate in the release
workflow.
