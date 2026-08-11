# Contaminant Pipeline Overview

## Purpose

The data pipeline turns two maintained Excel workbooks into data that can
eventually be published on the Red Hill Contaminant Glossary website. Its job
is to make that process repeatable, reviewable, and safe.

The pipeline does not decide scientific questions. It checks that recorded
decisions are internally consistent and stops when a relationship is unknown
or ambiguous.

## Routine inputs

The routine workflow begins with two updated files supplied by the workbook
maintainer:

| Workbook | What it contains |
| --- | --- |
| `contaminant_glossary.xlsx` | Contaminant names, chemical information, classifications, regulatory values, notes, and footnotes |
| `references.xlsx` | Sources and links associated with contaminants |

The pipeline treats these workbooks as authoritative inputs. It reads them
without saving changes back to Excel. Historical data collection and optional
enrichment are separate activities and are not required for a routine release.

## The workflow in plain language

```text
Updated Excel workbooks
        |
        v
Read workbook structure and values without editing Excel
        |
        v
Check workbook identity, schema versions, and revisions
        |
        v
Load the permanent registry and reviewed reference crosswalk
        |
        v
Preserve an immutable snapshot and deterministic intake manifest
        |
        v
Safely reuse exact retries and reject conflicting release identities
        |
        v
Validate immutable raw workbook structure and exact schema headers
        |
        v
Resolve release-aware IDs, references, footnotes, and duplicate candidates
        |
        v
Future tasks: validate scientific values, normalize, compare, and export
```

## What is implemented now

The current foundation can:

1. Read both `.xlsx` files into immutable Python snapshots and close the files.
2. Validate each workbook's declared type, schema version, and revision.
3. Assign and validate permanent contaminant IDs in the form `RHC-NNN`.
4. Match reference review labels exactly or through an explicit reviewed
   override; it never uses fuzzy matching or silent spelling correction.
5. Validate footnote definitions and every contaminant-to-footnote link.
6. Produce a deterministic in-memory bootstrap report with counts and findings.
7. Strictly load and protect the permanent contaminant registry and reference
   crosswalk stored under `data_pipeline/registry/`.
8. Prove the complete current relationship set against the real workbooks with
   automated tests while confirming the protected files remain unchanged.
9. Read the two stable incoming filenames once and return their immutable
   snapshots only after their workbook roles, schemas, and revisions form a
   compatible pair.
10. Tie each snapshot to an exact byte size and SHA-256 digest and inventory
    required sheets, tables, headers, logical rows, and formulas without
    publishing generated files.
11. Copy the verified pair through a hidden staging directory and expose both
    workbooks together under the versioned raw-snapshot path with one atomic
    directory rename.
12. Revalidate the raw pair and publish deterministic portable JSON containing
    release identity, complete workbook inventory, hashes, sizes, revisions,
    and explicit clean/local/unknown Git provenance.
13. Treat an exact completed retry as a read-only no-op, recover an exact
    raw-only attempt by publishing its missing manifest, and reject release-ID
    or immutable workbook-revision collisions without overwriting history.
14. Prove the complete public intake chain against authoritative read-only
    inputs and disposable success, retry, recovery, collision, malformed-state,
    mutation, and atomic-failure scenarios while independently checking the
    published bytes and protected filesystem state.
15. Reopen only the completed intake's immutable raw snapshots, recheck their
    accepted identities and structure, and require the exact schema-specific
    named columns before later Phase 3 validation can process values.
16. Resolve each legacy workbook ID through the registry state applicable to
    that release, join exact reviewed reference labels and footnotes, and
    report possible exact name/CASRN/InChIKey duplicates without merging them.

The current command-line interface only displays help. Intake publication and
structural plus identity/relationship validation are available as package
code, but routine commands, scientific validation, normalization, comparison,
and website export are not yet implemented.

## Permanent identity and reviewed relationships

Names are useful to people but can change. The production join key is therefore
`id_contaminant`, a permanent value such as `RHC-012`.

The tracked registry records every issued ID, its current review name, and its
lifecycle. IDs are not recalculated from workbook row numbers, names, CASRNs,
or InChIKeys. Retired IDs remain reserved and cannot be reused.

The tracked crosswalk records how each exact reference-workbook label connects
to a permanent ID. A label either:

- exactly equals one glossary name; or
- appears in the explicit reviewed override mapping.

For example, the reviewed label `Benzo(a)pyrene` maps to `RHC-012`. The pipeline
does not infer that relationship; it preserves the recorded decision.

## What happens when something is wrong

The pipeline fails explicitly instead of guessing. Examples include:

- a missing or unsupported workbook schema version;
- a duplicate or invalid contaminant ID;
- an ambiguous glossary name;
- a reference label with no exact match or reviewed override;
- an unknown footnote ID;
- a removed, reused, or reactivated registry ID; or
- a tracked CSV whose bytes or columns do not follow the durable format.

Validation errors include enough context for a maintainer to locate the source
problem. A failed bootstrap does not return a persistable result and does not
modify the workbooks or reviewed registry assets.

## Tracked inputs and generated outputs

The repository intentionally tracks:

- both incoming authoritative workbooks;
- the permanent contaminant registry;
- the reviewed reference crosswalk;
- source code, tests, documentation, and the dependency lockfile.

Later pipeline-generated manifests, snapshots, processed tables, reports, and
website data use designated generated-data directories. The
[Git and artifact policy](git_and_artifact_policy.md) records which artifacts
belong in Git and which are recreated or published elsewhere.

## Key terms

| Term | Meaning in this project |
| --- | --- |
| Authoritative workbook | A maintained Excel file treated as the source value, not a file the pipeline silently rewrites |
| Metadata | The small worksheet table declaring workbook type, schema version, and revision |
| Schema | The agreed structure and meaning of fields and allowed values |
| Snapshot | A preserved input state used so later work does not depend on a changing incoming file |
| Registry | The permanent record of every issued contaminant ID and its lifecycle |
| Crosswalk | The reviewed mapping from a reference-workbook label to a permanent contaminant ID |
| Override | An explicit reviewed mapping used only when a reference label is not an exact glossary-name match |
| Canonical data | Consistently named and typed pipeline data produced from source workbook fields |
| Release | One validated, reproducible version of pipeline and website data |

## Safety rules for maintainers

- Update scientific content in the authoritative workbooks through the agreed
  workbook-maintenance process, not through pipeline code.
- Do not manually renumber `RHC-NNN` identifiers.
- Do not silently rewrite a reference review label to force a match.
- Treat the registry and crosswalk as reviewed durable data, not disposable
  output.
- Read a validation failure before attempting to publish anything.
- Keep private or supervisor-check fields out of public website exports unless
  the canonical schema explicitly marks them public.

## What comes next

The remaining implementation proceeds in stages:

| Stage | Intended outcome | Status |
| --- | --- | --- |
| Bootstrap relationships | Permanent IDs, reviewed joins, Metadata, footnotes, and tracked assets | Complete |
| Intake and snapshotting | Verify an incoming workbook pair, preserve immutable raw copies, and safely reconcile repeat attempts | Complete as package code; CLI remains later work |
| Normalization and validation | Structural and identity/relationship gates complete; scientific, processing, and reports remain | In progress |
| Comparison and release | Explain changes and orchestrate a complete release | Planned |
| Website export | Produce deterministic public JSON from allowlisted fields | Planned |
| Automation and handoff | CI, deployment, enrichment review, and maintainer procedures | Planned |

Until those stages are implemented, the project should not be described as a
complete one-command release pipeline.

## Where to read next

- Non-technical readers: continue with the
  [data contract](data_contract.md) for the governing rules.
- Workbook maintainers: read the [canonical schema](canonical_schema.md) for
  field meanings, units, and public/private status.
- Developers: use the [code tour](code_tour.md) for the module execution order
  and matching tests.
- Repository maintainers: read the
  [Git and artifact policy](git_and_artifact_policy.md).
