# Durable Registry Assets

Phase 0B.6 freezes the validated contaminant registry and reference crosswalk as
Git-tracked, human-reviewable CSV files. Later phases must load these files so a
workbook rename or reorder cannot silently recalculate identity.

## Tracked locations

```text
data_pipeline/registry/contaminant_registry.csv
data_pipeline/registry/reference_crosswalk.csv
```

These files are durable source inputs owned by the pipeline. They are not
generated release output and are intentionally visible to Git.

## Contaminant registry schema

| Column | Meaning |
| --- | --- |
| `id_contaminant` | Permanent unique `RHC-NNN` identifier |
| `id_legacy_cg` | Initial legacy CG ID; blank for future pipeline-issued records |
| `id_name` | Current descriptive review name, not an identity key |
| `status` | `active` or `retired` |
| `successor_id` | Optional existing survivor ID for a retired record |
| `issued_release_id` | Release in which the ID was first issued |
| `retired_release_id` | Required retirement release for retired records |

Active records have no retirement fields. Retired records remain permanently
and cannot reactivate. Retirement cannot precede issuance, and a successor must
be another ID present in the registry.

The initial asset contains 152 active rows mapping legacy IDs `1` through `152`
to `RHC-001` through `RHC-152`, issued in release `20260716`.

## Reference crosswalk schema

| Column | Meaning |
| --- | --- |
| `refs_review_name` | Exact original reference-workbook label |
| `id_contaminant` | Existing registry target |
| `resolution_method` | `exact` or `override` |
| `reviewed_release_id` | Release in which the resolution was reviewed |

The initial crosswalk contains 133 distinct labels: 112 exact matches and 21
reviewed overrides. All were reviewed in release `20260716`.

## Determinism and loading

Both assets use UTF-8 without a byte-order mark, LF newlines, standard CSV
escaping, and a final newline. Registry rows sort by numeric stable ID;
crosswalk rows sort by exact review label. Input or workbook row order therefore
cannot change the bytes.

Loaders require exact headers and validated records. They reject malformed
UTF-8, CRLF or missing final newlines, missing/extra columns, noncanonical
integers, duplicate IDs/labels, invalid lifecycle combinations, and crosswalk
targets absent from the registry.

## Transition protection

Registry transitions may update a descriptive name, retire an active ID, and
append contiguous IDs above the highest ID ever issued. They cannot remove an
issued ID, change its legacy value or issuance release, reactivate it, alter a
completed retirement, fill an old gap, or skip a newly issued number.

Crosswalk transitions retain every reviewed label. A label cannot disappear,
change target, change method, or rewrite its review release. New labels may be
added only when their target exists in the registry.

Scientific decisions about renames, retirement, merges, splits, or corrected
identity remain outside this mechanical protection.

## Atomic and idempotent freeze

`freeze_registry_assets` validates and serializes both files completely in
memory, stages them in one sibling directory, and publishes the directory with
one atomic rename. A staging failure is cleaned up.

An identical repeated freeze returns without rewriting either file. A partial
directory, unexpected file, or differing byte is a collision and is never
overwritten automatically.

## Implementation and tests

The implementation is in
[`registry_assets.py`](../../src/contaminant_pipeline/registry_assets.py).
Focused and authoritative tests are in
[`test_registry_assets.py`](../../tests/test_registry_assets.py).
[`test_bootstrap_end_to_end.py`](../../tests/test_bootstrap_end_to_end.py)
separately proves that a complete read-only bootstrap exactly reproduces the
loaded tracked rows without rewriting either CSV. This is bootstrap validation,
not the workbook intake and immutable snapshot behavior planned for Phase 2.

From `data_pipeline`, run:

```powershell
uv run --locked --extra dev pytest tests/test_registry_assets.py
```
