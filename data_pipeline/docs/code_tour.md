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
| `io_excel.py` | Reads workbook content without saving or keeping Excel files open | `.xlsx` path | Immutable `WorkbookSnapshot` | `test_io_excel.py` |
| `metadata.py` | Confirms which workbook is which and whether the pair is compatible | Workbook snapshots | `WorkbookMetadata` and `WorkbookCompatibility` | `test_metadata.py` |
| `identifiers.py` | Validates, bootstraps, and extends permanent contaminant IDs | Legacy or issued IDs | Immutable `RHC-NNN` mappings | `test_identifiers.py` |
| `crosswalk.py` | Resolves exact reference labels and explicit reviewed overrides | Glossary identities, reference labels, override mapping | Reference-label-to-ID entries | `test_crosswalk.py` |
| `footnotes.py` | Checks footnote definitions and contaminant usages | Glossary snapshot and usage sources | Validated definitions and usages | `test_footnotes.py` |
| `bootstrap_report.py` | Organizes counts and findings into stable maintainer-readable results | Counts, compatibility, findings | Immutable report and formatted text | `test_bootstrap_report.py` |
| `bootstrap_validation.py` | Runs all bootstrap relationship checks in dependency order | Two workbook snapshots and overrides | `ValidatedBootstrap`, or an error carrying the failed report | `test_bootstrap_validation.py` |
| `registry_assets.py` | Strictly loads, serializes, compares, and protects permanent CSV assets | Validated bootstrap or tracked CSV bytes | Registry/crosswalk records and deterministic CSV | `test_registry_assets.py` |
| `schemas.py` | Defines normalized field names, types, allowed values, ownership, null rules, and publication flags | Canonical field values | Validated immutable records | `test_schemas.py` |
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
| `intake.py` | Inspect incoming workbooks and publish immutable raw snapshots | 2 |
| `validate.py` | Run complete structural, relationship, and scientific validation | 3 |
| `process.py` | Produce normalized canonical tables and reports | 3 |
| `compare.py` | Compare releases by permanent contaminant ID | 4 |
| `export_app_data.py` | Export deterministic public website data | 5 |

Do not assume a planned module works merely because its file exists. Each file
states its unimplemented status in its module docstring.

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
- [Bootstrap validation report](components/bootstrap_validation_report.md)
- [Bootstrap validation](components/bootstrap_validation.md)
- [Durable registry assets](components/durable_registry_assets.md)
