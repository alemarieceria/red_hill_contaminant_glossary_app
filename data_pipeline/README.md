# Red Hill Contaminant Pipeline

This package is the Python foundation for validating and publishing the Red
Hill contaminant glossary. Its environment, installed package, workbook reader,
schemas, synthetic fixtures, and command-line entry point are ready. Workbook
processing and release commands will be added in later phases; the current CLI
does not transform or publish data.

Run every command below from the `data_pipeline` directory.

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
uv run pytest
```

Check the Python source and tests with Ruff:

```powershell
uv run ruff check .
```

Confirm that the dependency declaration still matches the tracked lockfile:

```powershell
uv lock --check
```

All commands should succeed. The tests include isolated installed-package and
CLI smoke checks. Verification should not change the authoritative workbooks or
create tracked pipeline outputs.

## Project rules

- [Data contract](docs/data_contract.md): workbook metadata, relationships,
  compatibility, and validation decisions.
- [Canonical schema](docs/canonical_schema.md): source-to-canonical fields,
  types, units, and publication status.
- [Git and artifact policy](docs/git_and_artifact_policy.md): tracked inputs,
  ignored outputs, snapshots, and release artifacts.

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
