# Reference Crosswalk

The reference crosswalk connects each distinct reference-workbook
`compound_name` review label to the glossary's permanent `RHC-NNN` identifier.
It keeps the original label for review while making `id_contaminant` the
production join key.

## Place in the pipeline

Phase 0B.1 creates the initial stable IDs from the glossary's legacy IDs.
Phase 0B.2 uses those identities to resolve reference labels in memory. It does
not normalize complete reference records or write a permanent crosswalk file.
Phase 0B.6 freezes the reviewed result as a tracked asset under
`data_pipeline/registry/`.

## Inputs and output

`build_reference_crosswalk` receives:

- glossary identities containing the exact glossary name and stable ID;
- reference review labels exactly as read from `compound_name`; and
- an explicit mapping from reviewed non-exact labels to existing stable IDs.

It returns an immutable tuple with one entry per distinct reference label. Each
entry contains the unchanged `refs_review_name`, its `id_contaminant`, and a
resolution method of `exact` or `override`. Entries are sorted by the original
review label, so workbook row order cannot change the result.

## Matching rules

1. Validate glossary names and IDs, including uniqueness.
2. Compare each reference label to glossary names with case-sensitive Python
   text equality. The component does not trim, change case, correct spelling,
   alter punctuation, or perform fuzzy matching.
3. Use a version-controlled override only when exact matching fails.
4. Reject overrides that target an unknown ID, replace an exact match, or are
   not used by the supplied reference labels.
5. Report every unresolved label together and stop.

The current reviewed override table is `REFERENCE_NAME_OVERRIDES` in
`crosswalk.py`. It maps the 21 known non-exact source labels directly to stable
IDs. Editing an authoritative workbook is not part of this component.

## Current workbook baseline

The read-only integration test observes:

| Item | Count |
| --- | ---: |
| Glossary identities | 152 |
| Reference rows | 406 |
| Distinct reference labels | 133 |
| Rows resolved by exact match | 343 |
| Rows resolved by 21 reviewed overrides | 63 |

All 406 current rows resolve. Repeated rows with the same review label share
one crosswalk entry.

## Failure behavior

The function raises `ValueError` for malformed records or IDs, blank names,
duplicate IDs, ambiguous duplicate glossary names, invalid or stale overrides,
and unresolved reference labels. Ambiguous glossary names and unresolved
reference labels are sorted and reported as complete groups instead of picking
a candidate.

Because the function only uses ordinary in-memory values, success and failure
cannot modify either workbook. The integration test also compares both files'
bytes before and after reading to prove this boundary.

## Implementation and tests

The implementation is in
[`crosswalk.py`](../../src/contaminant_pipeline/crosswalk.py). Its focused and
real-workbook tests are in
[`test_crosswalk.py`](../../tests/test_crosswalk.py).

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest tests/test_crosswalk.py
```
