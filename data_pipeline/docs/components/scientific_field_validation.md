# Scientific Field Validation

Phase 3.3 checks whether workbook values have the exact scientific and source
forms required by schema `1.0.0`. It runs only after stable identities,
references, and footnotes have resolved successfully.

## System position

```text
3.1 exact workbook structure
        |
        v
3.2 stable IDs and relationships
        |
        v
3.3 literal scientific values and URLs  <-- this component
        |
        v
3.3a pending-value warnings and supervisor review handoff
        |
        v
3.4 Excel formulas and independently checked derived meanings
        |
        v
3.5 canonical tables
```

`validate_scientific_fields` accepts only
`ValidatedIdentityRelationships`. It reads values from the immutable raw
snapshots retained by 3.1 and associates them with the stable IDs resolved by
3.2. It does not reopen mutable incoming workbooks, make network requests,
rewrite values, create output files, or change reviewed registry assets.

## Unknown versus not applicable

The gate keeps three meanings separate:

| Source state | Meaning |
| --- | --- |
| Blank cell | Unknown or not supplied; later canonical value is null |
| Exact `""` in an optional text field | Unknown or not supplied; later canonical value is null |
| Approved exact `NA` or `N/A` | The field does not apply; later canonical value is `not_applicable` |
| Malformed or misplaced placeholder | Validation error |

For chemical formula, CASRN, and InChIKey, an explicit not-applicable token is
allowed when `Primary` is `Mixture` or `Non-compound measurement`. Those rows
may still carry a real value: a registered mixture can have a CASRN, so the
classification permits N/A but does not require it.

`RHC-071` (`1,3-Dichloropropene, Total`) has one explicit InChIKey exception
because the total result covers cis and trans structures. Exceptions use the
stable ID, never the display name or row position. An ordinary
single-substance row cannot use these identifier/formula placeholders without
a documented stable-ID exception.

The five atom-count columns retain their older field-specific spelling: exact
`NA`. The `Halogenated` and `Saturated` fields use exact `N/A`.

## Validation rules

- CASRNs use canonical hyphenation and must pass the CAS check-digit
  calculation.
- InChIKeys must have the uppercase 27-character `14-10-1` form.
- Chemical formulas support schema-1.0.0 element symbols, positive atom
  counts, the workbook's charge notation, and literal ` | ` alternatives.
  This is syntax validation, not a claim that a formula identifies the right
  real-world substance.
- Multi-value fields split only on literal ` | `. Empty, repeated,
  whitespace-padded, alternate-delimiter, and mixed placeholder/real tokens
  fail rather than being cleaned silently.
- Classifications and other enumerations use exact documented spellings.
  Boolean fields accept only real Excel Booleans, not `0`, `1`, or text.
- Atom and functional-group counts reject Boolean, float, negative, and
  unsupported text values. Atom ranges must be ordered.
- Regulatory numbers must be finite and nonnegative. Only SMCL `6.5-8.5` and
  HDOH `AL = 0.015` or `AL = 1.3` receive their documented special types.
- Required text and reference-source values must be literal nonblank text with
  no surrounding whitespace. Reference links must be absolute HTTP(S) URLs
  with a host.
- The optional glossary `Sources` description accepts a true blank or exact
  zero-length string as null and emits a pending warning. Whitespace-only or
  padded text remains an error.
- Blank CASRN/InChIKey values emit unknown/pending warnings; permitted `NA` or
  `N/A` identifiers emit unverified-not-applicable warnings.

If a cell also has an Excel formula, 3.3 validates its retained cached value
and preserves the formula definition. Phase 3.4 decides whether formula use,
the cache, and an independent calculation agree.

## Result and failure behavior

A successful `ValidatedScientificFields` contains frozen contaminant and
reference records with source rows, stable IDs, raw values, formula
definitions, and parsed typed values. Nested mappings and returned collections
are immutable and deterministically ordered.

Independent problems are collected when safe. Any error raises
`ScientificFieldValidationError` carrying all sorted `ValidationFinding`
records; no partial successful result or production output is returned.
`inspect_scientific_fields` exposes the same frozen records and findings to the
3.3a review builder without converting a failed gate into success.

## Current authoritative status

The current 152-contaminant and 406-reference snapshot reaches this gate but
does not yet pass it. After the reviewed B/C cleanup in glossary revision
`20260810`, the read-only integration test records 6 errors and 57 warnings:

- one CASRN with an invalid check digit (`RHC-015`, source `207-916-6`);
- five chemical-formula `NA` values on rows not classified as mixtures or
  non-compound measurements;
- six pending `Sources` descriptions (`RHC-132` through `RHC-137`);
- 32 blank CASRN/InChIKey values; and
- 19 permitted but scientifically unverified CASRN/InChIKey N/A values.

The prior malformed alias delimiter and fourteen trailing-whitespace findings
are resolved in revision `20260810`; they remain documented as 15 audit rows in
that release's supervisor review workbook.

The mixture/non-compound CASRN and InChIKey `NA` representations are permitted,
but are not treated as scientifically verified. The pipeline reports defects
and review items without correcting the authoritative workbook automatically.
See the [scientific review handoff](scientific_review_handoff.md) for the
supervisor workflow.

## Scope boundary

Phase 3.3 does not check Excel formula presence or recompute derived values,
interpret pesticide/footnote-D consistency, produce canonical CSVs or reports,
run comparisons, export website JSON, or add CLI commands.

## Tests

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest -p no:cacheprovider tests/test_scientific_validation.py
```

The focused suite covers valid typed output, N/A applicability, CASRN and
InChIKey syntax, chemical formulas, delimiters, classifications, strict types,
counts, regulatory values, text, URLs, formula-context retention, aggregation,
immutability, snapshot-only operation, authoritative findings, and protected
file isolation.
