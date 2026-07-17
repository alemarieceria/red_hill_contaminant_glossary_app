# Git and Artifact Policy

This policy defines which pipeline files belong in Git and which are generated
outside version control. Ignore rules implement this policy; they do not decide
it.

## Tracked files

Git tracks the inputs and instructions required to reproduce a release:

- The authoritative incoming workbooks at
  `data/00_incoming/contaminant_glossary.xlsx` and
  `data/00_incoming/references.xlsx`.
- The January historical workbook at
  `data/02_raw_snapshots/20260115/contaminant_glossary.xlsx`. This is a
  permanent comparison fixture and the only raw-snapshot exception.
- Python and website source code, tests, and synthetic test fixtures.
- Documentation, package configuration, dependency lock files, and automation
  configuration.
- Pipeline-owned durable assets at `registry/contaminant_registry.csv` and
  `registry/reference_crosswalk.csv`.

Incoming workbook updates are ordinary reviewed Git changes. Stable filenames
are retained so a data update replaces the intended input instead of creating
date-stamped copies in `00_incoming`.

## Generated files

Routine generated files do not belong in Git:

- Raw snapshots created after the January historical exception.
- Intake and release manifests.
- Processed and normalized tables.
- Validation, comparison, and provenance reports.
- Enrichment response caches and review-patch outputs.
- Generated website data under `public/data`.
- Static-build output, virtual environments, and Python or test caches.

Generated files must be reproducible from tracked inputs and code. A command
may replace disposable output only within its documented generated directory;
it must never overwrite a file in `data/00_incoming`.

## Release artifacts

Completed release bundles are published as GitHub Release attachments rather
than committed to the repository. A release bundle may contain the source
workbooks, hashes, manifest, normalized tables, reports, and website JSON needed
to reconstruct that release.

Git records the code, contracts, durable mappings, and input updates. GitHub
Releases retain packaged outputs without duplicating each generated release in
Git history.

## History and safety

- Preserve the existing repository commits; do not rewrite history to remove
  earlier pipeline or workbook changes.
- Preserve the January historical workbook even though later raw snapshots are
  generated.
- Never use ignore rules to hide either authoritative incoming workbook.
- Never commit local environments, caches, credentials, or secret environment
  files.
- Before changing ignore rules, verify each required tracked input remains
  visible to Git.

## Policy matrix

| Artifact | Location | Git policy | Long-term location |
| --- | --- | --- | --- |
| Current glossary workbook | `data/00_incoming/contaminant_glossary.xlsx` | Track | Git and release bundle |
| Current references workbook | `data/00_incoming/references.xlsx` | Track | Git and release bundle |
| January historical glossary | `data/02_raw_snapshots/20260115/contaminant_glossary.xlsx` | Track permanently | Git |
| Future raw snapshots | `data/02_raw_snapshots/<release-id>/` | Ignore | Recreated locally and packaged in releases |
| Manifests and processed tables | `data/01_manifest/`, `data/03_processed/` | Ignore | GitHub Release bundle |
| Reports, patches, and caches | `data/04_output/` | Ignore | GitHub Release bundle when applicable |
| Stable ID registry | `registry/contaminant_registry.csv` | Track | Git |
| Reference crosswalk | `registry/reference_crosswalk.csv` | Track | Git |
| Generated website JSON | `public/data/` | Ignore | Rebuilt during deployment and packaged in releases |
| Source, tests, configuration, and docs | Repository source paths | Track | Git |
| Release bundle archives | Release staging location | Ignore | GitHub Releases |

The corresponding ignore patterns are implemented separately in task 1.2.
