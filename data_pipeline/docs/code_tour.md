# Python Pipeline Code Tour

## Who this guide is for

This guide helps a new developer understand where behavior lives and what to
read first. For a non-technical explanation of the workflow, begin with the
[pipeline overview](pipeline_overview.md).

The modules under `src/contaminant_pipeline/` form one installed Python
package. Most modules are not scripts to run individually. The command-line
entry point will eventually compose them into release commands.

## Recommended reading order

```text
config.py and paths.py
        |
        v
io_excel.py
        |
        v
metadata.py, identifiers.py, crosswalk.py, footnotes.py
        |
        v
intake.py
        |
        v
validate.py
        |
        v
scientific_validation.py
        |
        v
scientific_review.py
        |
        v
bootstrap_report.py
        |
        v
bootstrap_validation.py
        |
        v
registry_assets.py
        |
        v
schemas.py
```

This order follows the current bootstrap data flow rather than alphabetical
filename order.

## Current modules

| Module | Why it exists | Main input | Main output | Matching tests |
| --- | --- | --- | --- | --- |
| `config.py` | Defines workbook names, sheet/table names, schema versions, and release-ID rules once | Configuration values | Validated release IDs and constants | `test_config_paths.py` |
| `paths.py` | Defines repository and pipeline locations once | Release ID when needed | Consistent `Path` objects | `test_config_paths.py` |
| `io_excel.py` | Reads one exact workbook byte image without saving or keeping Excel files open | `.xlsx` path | Immutable `WorkbookSnapshot` with byte size and SHA-256 | `test_io_excel.py` |
| `metadata.py` | Confirms which workbook is which and whether the pair is compatible | Workbook snapshots | `WorkbookMetadata` and `WorkbookCompatibility` | `test_metadata.py` |
| `intake.py` | Reads and inventories the stable pair, atomically publishes raw bytes and deterministic JSON, and safely reconciles retries/collisions | Incoming directory or the preceding accepted-stage record | Immutable incoming, inventory, raw, manifest, and completed-intake records, or a contextual contract error | `test_intake.py`, `test_workbook_inventory.py`, `test_atomic_snapshot.py`, `test_intake_manifest.py`, `test_intake_collision.py`, `test_intake_end_to_end.py` |
| `identifiers.py` | Validates, bootstraps, and extends permanent contaminant IDs | Legacy or issued IDs | Immutable `RHC-NNN` mappings | `test_identifiers.py` |
| `crosswalk.py` | Resolves exact reference labels and explicit reviewed overrides | Glossary identities, reference labels, override mapping | Reference-label-to-ID entries | `test_crosswalk.py` |
| `footnotes.py` | Checks footnote definitions and contaminant usages | Glossary snapshot and usage sources | Validated definitions and usages | `test_footnotes.py` |
| `bootstrap_report.py` | Organizes counts and findings into stable maintainer-readable results | Counts, compatibility, findings | Immutable report and formatted text | `test_bootstrap_report.py` |
| `bootstrap_validation.py` | Runs all bootstrap relationship checks in dependency order | Two workbook snapshots and overrides | `ValidatedBootstrap`, or an error carrying the failed report | `test_bootstrap_validation.py` |
| `registry_assets.py` | Strictly loads, serializes, compares, and protects permanent CSV assets | Validated bootstrap or tracked CSV bytes | Registry/crosswalk records and deterministic CSV | `test_registry_assets.py` |
| `schemas.py` | Defines normalized field names, types, allowed values, ownership, null rules, and publication flags | Canonical field values | Validated immutable records | `test_schemas.py` |
| `validate.py` | Revalidates completed raw snapshots, enforces schema-specific headers, then validates release-aware stable identities and relationships | Completed intake or preceding validated contract | Frozen workbook contract and identity/relationship result, or contextual validation errors | `test_workbook_contract_validation.py`, `test_identity_relationship_validation.py` |
| `scientific_validation.py` | Validates literal scientific/source values and explicit N/A applicability after stable identities resolve | `ValidatedIdentityRelationships` | Frozen typed scientific values, or deterministic contextual findings | `test_scientific_validation.py` |
| `scientific_review.py` | Builds and reconciles stable supervisor review rows and writes a separate release-scoped workbook | `ValidatedIdentityRelationships`, optional evidence proposals, and cleanup records | Frozen review package, `.xlsx` handoff, or reconciliation statuses | `test_scientific_review.py` |
| `cli.py` | Provides the installed command-line boundary | Command-line arguments | Help now; pipeline commands later | `test_cli.py` |
| `__main__.py` | Makes `python -m contaminant_pipeline` invoke the CLI | Python module execution | CLI exit code | `test_cli.py` |

`test_bootstrap_end_to_end.py` is the final integration proof. It reads the real
workbooks, repeats bootstrap validation, compares the result with both tracked
assets, checks exact and override relationships, and proves failure remains
read-only.

## Planned modules

These files reserve clear homes for later pipeline stages but intentionally
contain no production behavior yet:

| Module | Planned responsibility | Phase |
| --- | --- | --- |
| `process.py` | Produce normalized canonical tables and reports | 3 |
| `compare.py` | Compare releases by permanent contaminant ID | 4 |
| `export_app_data.py` | Export deterministic public website data | 5 |

Do not assume a planned module works merely because its file exists. Each file
states its unimplemented status in its module docstring.

Phase 2.5 extends `intake.py` with a separate reconciliation layer. The focused
raw and manifest publishers still reject existing targets; the coordinator
validates history and decides whether to create, recover, reuse, or reject.

## Current execution path

The implemented bootstrap path is:

1. `read_workbook` reads and closes each authoritative workbook.
2. `validate_bootstrap_snapshots` validates Metadata compatibility.
3. The orchestrator extracts the glossary rows needed for relationships.
4. `bootstrap_contaminant_ids` creates the initial stable-ID mapping.
5. `build_reference_crosswalk` resolves exact labels and reviewed overrides.
6. `validate_footnote_relationships` checks definitions and usages.
7. `build_bootstrap_report` sorts findings and derives pass/fail status.
8. A passing run returns `ValidatedBootstrap`; a failing run raises
   `BootstrapValidationError` containing the full report.
9. `propose_registry_assets` converts a passing result into registry rows.
10. The strict asset loaders verify that the tracked CSVs match those rules.

The workbook reader and validators do not write Excel files. Asset freezing is
an explicit, separately tested operation and refuses to overwrite different
reviewed content.

The implemented routine incoming path currently stops in memory:

1. `read_incoming_pair` selects the two centralized stable filenames.
2. `read_workbook` reads and closes each workbook exactly once.
3. `extract_workbook_metadata` reads each declared Metadata table.
4. `validate_workbook_compatibility` confirms roles and schema compatibility
   and derives the combined release ID.
5. A passing run returns both snapshots in one frozen `IncomingWorkbookPair`;
   a failure raises `IncomingContractError` and creates no output.
6. `inventory_incoming_pair` verifies required structure and produces frozen
   workbook, worksheet, table, header, formula, row-count, and fingerprint
   records without publishing anything.
7. `publish_raw_snapshot` copies both accepted sources into a hidden sibling,
   verifies their fingerprints, and exposes the complete versioned pair with
   one directory rename.
8. `publish_intake_manifest` revalidates the raw pair, records explicit local
   Git provenance, serializes complete portable inventory JSON, and publishes
   it with one temporary-file rename.
9. `publish_or_reuse_intake` checks manifest history and existing final
   artifacts, then returns a frozen `created`, `recovered`, or `existing`
   result. Exact retries are read-only; conflicting identities fail closed.
10. `test_intake_end_to_end.py` runs that public sequence against authoritative
    read-only inputs and synthetic failure matrices, independently verifies
    snapshot/manifest output, and proves protected paths remain unchanged.

The implemented Phase 3 path currently adds structural, relationship, and
scientific-value gates:

1. `validate_workbook_contract` accepts only a completed `IntakePublication`.
2. It reads the two versioned raw workbooks once, never `data/00_incoming`.
3. Existing Metadata and inventory components recheck release identity,
   fingerprints, required sheets, tables, and populated regions.
4. The observed inventories must equal the completed intake inventories.
5. Schema `1.0.0` requires the exact approved glossary, footnote, Metadata, and
   reference header names; column order is non-semantic.
6. Success returns frozen raw snapshots and inventory to
   `validate_identity_relationships`; structural failure raises
   `WorkbookContractError` and creates no output.
7. The 3.2 gate loads registry and crosswalk state applicable to that release
   and resolves literal legacy IDs only through the registry.
8. It joins exact reference labels through eligible reviewed crosswalk rows and
   reuses the footnote validator with resolved stable IDs.
9. It reports exact duplicate name, CASRN, and InChIKey candidates as warnings
   without merging, and returns a frozen result when there are no errors.
10. Any error raises `IdentityRelationshipValidationError` with all safely
    collectible, deterministically sorted findings and creates no output.
11. `validate_scientific_fields` accepts only the completed 3.2 result and
    extracts values from the same immutable raw snapshots.
12. It validates CASRN check digits, InChIKey and chemical-formula syntax,
    classifications, strict types/nulls, counts, regulatory values, text, and
    HTTP(S) reference URLs.
13. Blank remains unknown while approved mixture/non-compound `NA` or `N/A`
    becomes an explicit `NotApplicable` value; the `RHC-071` total-isomer
    InChIKey exception is keyed only by stable ID.
14. Success returns frozen typed records with raw values and retained formula
    context. Errors raise `ScientificFieldValidationError` with all safely
    collectible sorted findings and create no output.
15. `inspect_scientific_fields` exposes the same deterministic findings for
    review-package construction without pretending a failing validation passed.
16. `build_scientific_review_package` turns scientific errors, pending source
    descriptions, blank identifiers, and permitted identifier N/A states into
    stable review rows with exact workbook cell context.
17. `write_supervisor_review_workbook` creates four explicit sheets only under
    the ignored release-scoped output directory; it never edits source Excel.
18. After approved data corrections, `reconcile_scientific_review_items`
    classifies prior rows as resolved, still failing, or superseded.

Excel-derived, processing, report, broader determinism, and CLI validation
remain unimplemented tasks 3.4 through 4.3. The current authoritative snapshot
reports 6 errors and 57 review warnings after the reviewed B/C cleanup in
glossary revision `20260810`. The supervisor handoff contains 63 review rows and
15 resolved-cleanup audit rows.

## Python conventions used here

- A leading underscore, as in `_extract_reference_rows`, means the function is
  an internal implementation detail rather than a public entry point.
- `@dataclass(frozen=True)` creates a small record whose fields cannot be
  reassigned after creation.
- `StrEnum` limits text to named allowed values such as `active` and `retired`.
- A `tuple` is used when returned collections should not be mutated.
- Pydantic models in `schemas.py` validate normalized field values and reject
  unexpected fields.
- `ValueError` means supplied data violates a focused rule.
- `BootstrapValidationError` is broader: it carries a complete failed report
  after independent bootstrap checks have run.
- Functions that serialize tracked data return `bytes` so newline, encoding,
  and repeatability rules can be tested exactly.

Comments and docstrings explain intent, boundaries, and safety decisions. The
tests provide executable examples of expected success and failure behavior.

## How tests are organized

Each focused production module has a similarly named test module. Tests cover:

- small successful examples;
- invalid input and complete error messages;
- deterministic ordering and immutable results;
- read-only behavior against synthetic fixtures; and
- authoritative integration checks against the current workbook pair.

Run all tests from `data_pipeline/`:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider
```

Run static checks:

```powershell
uv run --locked --extra dev ruff check .
uv lock --check
```

## Detailed references

- [Data contract](data_contract.md)
- [Canonical schema](canonical_schema.md)
- [Git and artifact policy](git_and_artifact_policy.md)
- [Immutable contaminant identifiers](components/immutable_contaminant_identifiers.md)
- [Reference crosswalk](components/reference_crosswalk.md)
- [Workbook Metadata compatibility](components/workbook_metadata_compatibility.md)
- [Stable incoming workbook contract](components/stable_incoming_contract.md)
- [Workbook inventory](components/workbook_inventory.md)
- [Atomic raw snapshot](components/atomic_raw_snapshot.md)
- [Intake manifest](components/intake_manifest.md)
- [Intake collision and retry behavior](components/intake_collision_and_retry.md)
- [Phase 2 intake acceptance tests](components/intake_acceptance_tests.md)
- [Workbook contract validation](components/workbook_contract_validation.md)
- [Identity and relationship validation](components/identity_relationship_validation.md)
- [Scientific field validation](components/scientific_field_validation.md)
- [Scientific review handoff](components/scientific_review_handoff.md)
- [Bootstrap validation report](components/bootstrap_validation_report.md)
- [Bootstrap validation](components/bootstrap_validation.md)
- [Durable registry assets](components/durable_registry_assets.md)
