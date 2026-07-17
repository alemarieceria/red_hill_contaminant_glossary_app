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
