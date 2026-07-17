# Synthetic workbook fixtures

The files in `workbooks/` are small, fictional inputs used only by automated
tests. They are not authoritative data, raw snapshots, or examples of actual
contaminants.

The pair intentionally follows the current source-workbook contract:

- `contaminant_glossary.xlsx` has the required Introduction, Glossary,
  Footnotes, and Metadata sheets.
- `references.xlsx` has the required Sheet1 and Metadata sheets.
- Both declare schema version `1.0.0` and valid, deliberately old fictional
  workbook revisions.
- Reference `compound_name` values exactly match one synthetic glossary name.
  The source workbook does not contain `contaminant_id`; the later registry and
  crosswalk phase derives that production join key.
- Values cover a few useful source shapes without copying supervisor data:
  blanks, booleans, numbers, `N/A`, delimited text, footnotes, repeated
  references, and a private review marker.

Only extend these fixtures when a focused test needs another source-data shape.
Keep them deterministic, test-only, free of real data, and free of formulas or
external network requirements.

To regenerate the two workbooks intentionally from their reviewed definition:

```powershell
uv run --locked --extra dev python tests/fixtures/build_workbooks.py
```

Run `pytest tests/test_synthetic_workbooks.py` immediately afterward and review
the resulting binary changes before keeping them.

