# Red Hill Contaminant Pipeline

This package is the Python foundation for validating and publishing the Red
Hill contaminant glossary. It currently reads the authoritative workbooks
without modifying them; validates workbook Metadata, permanent IDs, reference
relationships, and footnotes; produces deterministic bootstrap reports; and
strictly protects the tracked contaminant registry and reference crosswalk.

Workbook intake, normalization, release comparison, and website export commands
will be added in later phases. The current CLI displays help and does not yet
transform or publish data.

Run every command below from the `data_pipeline` directory.

## Choose your starting point

- **I want a plain-language explanation:** read the
  [pipeline overview](docs/pipeline_overview.md).
- **I maintain the workbooks:** read the [data contract](docs/data_contract.md)
  and [canonical schema](docs/canonical_schema.md).
- **I want to understand the Python:** follow the
  [code tour](docs/code_tour.md).
- **I need repository storage rules:** read the
  [Git and artifact policy](docs/git_and_artifact_policy.md).
- **I need one component's technical details:** use the
  [documentation index](docs/README.md).

## Current capabilities

The implemented foundation can:

- read `.xlsx` workbook contents into closed, immutable snapshots;
- validate workbook identity, schema compatibility, and release revisions;
- assign and protect `RHC-NNN` contaminant identifiers;
- resolve exact reference labels and explicit reviewed overrides without fuzzy
  matching;
- validate footnote definitions and contaminant usages;
- validate scientific field syntax and controlled values while retaining
  explicit unknown and not-applicable meanings;
- produce a separate release-scoped supervisor review workbook for unresolved
  scientific values, identifiers, and pending source descriptions;
- build deterministic pass/fail reports with counts and source context;
- load, serialize, and protect the durable registry and reference crosswalk;
- verify all current relationships against the authoritative workbooks without
  changing protected inputs or assets.

See the [pipeline overview](docs/pipeline_overview.md) for the completed and
planned workflow stages.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) for Python and dependency management.
- Python `>=3.11,<3.14`. The repository's `.python-version` selects Python 3.13
  for routine development.

Confirm that `uv` is available:

```powershell
uv --version
```

## Create the development environment

```powershell
uv sync --locked --extra dev
```

This command uses `.python-version`, creates or updates the ignored `.venv`,
installs the local package from `src/contaminant_pipeline`, and installs the
test and lint tools. `--locked` makes setup fail if `pyproject.toml` and the
tracked `uv.lock` disagree instead of silently rewriting the lockfile.

The normal environment contains:

- Runtime dependencies: pandas, openpyxl, and Pydantic.
- The `dev` extra: pytest and Ruff.
- Optional `enrichment` and `chemistry` extras: network and chemistry features
  reserved for later work. They are not needed for routine setup or testing.

## Check the command line

```powershell
uv run python -m contaminant_pipeline --help
```

The command should print usage beginning with `contaminant-pipeline`. Running
the module without arguments currently prints the same help and exits
successfully. Neither form reads, transforms, or writes the workbooks.

## Verify the foundation

Run the complete test suite:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider
```

Check the Python source and tests with Ruff:

```powershell
uv run --locked --extra dev ruff check .
```

Confirm that the dependency declaration still matches the tracked lockfile:

```powershell
uv lock --check
```

All commands should succeed. The tests include isolated installed-package and
CLI smoke checks. Verification should not change the authoritative workbooks or
create tracked pipeline outputs.

## Governing project rules

- [Data contract](docs/data_contract.md): workbook metadata, relationships,
  compatibility, and validation decisions.
- [Canonical schema](docs/canonical_schema.md): source-to-canonical fields,
  types, units, and publication status.
- [Git and artifact policy](docs/git_and_artifact_policy.md): tracked inputs,
  ignored outputs, snapshots, and release artifacts.

The [documentation index](docs/README.md) links the plain-language overview,
developer tour, and detailed component decisions.

## Troubleshooting

- **A command cannot find the project:** confirm the terminal is in the
  `data_pipeline` directory.
- **Python is unsupported:** use a Python version in `>=3.11,<3.14`; Python 3.13
  is the repository default.
- **The package, pytest, or Ruff is missing:** rerun
  `uv sync --locked --extra dev`.
- **Locked setup fails:** keep the full error output. A mismatch between
  `pyproject.toml` and `uv.lock` requires an intentional dependency review; do
  not bypass `--locked` or regenerate the lockfile as an incidental fix.
