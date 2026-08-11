# Pipeline Documentation

Choose the route that matches what you need to understand.

## Start here

- [Pipeline overview](pipeline_overview.md): What happens from updated Excel
  workbooks toward website-ready data, what is implemented, and what is still
  planned?
- [Python code tour](code_tour.md): Which module owns each behavior, in what
  order does the code execute, and which tests demonstrate it?

## Workbook and data rules

- [Data contract](data_contract.md): What rules must the data follow?
- [Canonical schema](canonical_schema.md): What does every normalized field
  mean, which units and null rules apply, and may it be published?
- [Git and artifact policy](git_and_artifact_policy.md): Which inputs and
  outputs belong in Git, and where do generated artifacts go?

## Implemented components

- [Immutable contaminant identifiers](components/immutable_contaminant_identifiers.md):
  How are permanent IDs validated, allocated, and bootstrapped?
- [Reference crosswalk](components/reference_crosswalk.md): How do reference
  review labels resolve to permanent IDs without guessing?
- [Workbook Metadata compatibility](components/workbook_metadata_compatibility.md):
  How are workbook identity, schema compatibility, revisions, and the combined
  release ID validated?
- [Stable incoming workbook contract](components/stable_incoming_contract.md):
  How are the two stable incoming filenames read once and returned as one
  validated, immutable in-memory pair?
- [Workbook inventory](components/workbook_inventory.md): How are exact source
  fingerprints, worksheet structure, logical rows, tables, headers, and
  formulas recorded without publishing files?
- [Atomic raw snapshot](components/atomic_raw_snapshot.md): How are both
  verified workbooks exposed together under one versioned directory while
  failed attempts remain invisible and narrowly cleaned up?
- [Intake manifest](components/intake_manifest.md): How are snapshot identity,
  complete structural inventory, and explicit Git provenance serialized and
  atomically published as portable deterministic JSON?
- [Intake collision and retry behavior](components/intake_collision_and_retry.md):
  How are exact retries reused, raw-only attempts recovered, and conflicting
  release or workbook-revision identities rejected without overwriting data?
- [Phase 2 intake acceptance tests](components/intake_acceptance_tests.md): How
  does the full public intake chain prove deterministic output, safe retries,
  failures, snapshot-only consumption, and protected-file isolation?
- [Workbook contract validation](components/workbook_contract_validation.md):
  How does Phase 3 revalidate immutable raw snapshots and enforce the exact
  schema-specific named columns before processing?
- [Bootstrap validation report](components/bootstrap_validation_report.md): How
  are counts, findings, status, and maintainer-readable output represented?
- [Bootstrap validation](components/bootstrap_validation.md): How are all
  bootstrap relationships validated together without modifying either
  workbook?
- [Durable registry assets](components/durable_registry_assets.md): How are
  permanent IDs and reviewed reference-label mappings stored and protected?

## Suggested reading paths

- **Non-technical reviewer:** pipeline overview, then data contract.
- **Workbook maintainer:** pipeline overview, canonical schema, then the
  relevant component document when validation reports a problem.
- **Developer:** code tour, component document, production module, then its
  matching tests.
- **Release maintainer:** Git and artifact policy now; an operational runbook
  will be added when the release CLI exists.
