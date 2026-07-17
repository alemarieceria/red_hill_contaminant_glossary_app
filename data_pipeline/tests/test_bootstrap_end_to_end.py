from dataclasses import replace
import unittest

from openpyxl.utils.cell import coordinate_to_tuple

from contaminant_pipeline.bootstrap_report import (
    BootstrapFindingCategory,
    BootstrapFindingSeverity,
    BootstrapReportCounts,
    BootstrapReportStatus,
)
from contaminant_pipeline.bootstrap_validation import (
    BootstrapValidationError,
    validate_bootstrap_snapshots,
)
from contaminant_pipeline.config import REFERENCES_SHEET_NAME
from contaminant_pipeline.crosswalk import (
    REFERENCE_NAME_OVERRIDES,
    ReferenceResolutionMethod,
)
from contaminant_pipeline.io_excel import CellSnapshot, read_workbook
from contaminant_pipeline.paths import (
    CONTAMINANT_REGISTRY_PATH,
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    MANIFEST_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    PUBLIC_DATA_DIR,
    RAW_SNAPSHOTS_DIR,
    REFERENCE_CROSSWALK_PATH,
    REGISTRY_DIR,
)
from contaminant_pipeline.registry_assets import (
    RegistryStatus,
    load_crosswalk,
    load_registry,
    propose_registry_assets,
)
from contaminant_pipeline.schemas import REFERENCE_HEADER_MAP


def artifact_inventory() -> tuple[str, ...]:
    """Return generated pipeline paths without creating any directories."""

    roots = (
        MANIFEST_DIR,
        RAW_SNAPSHOTS_DIR,
        PROCESSED_DIR,
        OUTPUT_DIR,
        PUBLIC_DATA_DIR,
    )
    paths = {
        str(path)
        for root in roots
        if root.exists()
        for path in root.rglob("*")
    }
    paths.update(
        str(path) for path in REGISTRY_DIR.parent.glob(f".{REGISTRY_DIR.name}-*")
    )
    return tuple(sorted(paths))


def replace_reference_label(snapshot, original: str, replacement: str):
    """Return a snapshot with one source review label changed in memory."""

    review_header = next(
        header
        for header, canonical_name in REFERENCE_HEADER_MAP.items()
        if canonical_name == "refs_review_name"
    )
    sheets = []
    replaced = False
    for sheet in snapshot.sheets:
        if sheet.name != REFERENCES_SHEET_NAME:
            sheets.append(sheet)
            continue

        header_cell = next(
            cell
            for cell in sheet.cells
            if coordinate_to_tuple(cell.coordinate)[0] == 1
            and cell.value == review_header
        )
        review_column = coordinate_to_tuple(header_cell.coordinate)[1]
        cells = []
        for cell in sheet.cells:
            row, column = coordinate_to_tuple(cell.coordinate)
            if not replaced and row > 1 and column == review_column and cell.value == original:
                cells.append(CellSnapshot(cell.coordinate, replacement, None))
                replaced = True
            else:
                cells.append(cell)
        sheets.append(replace(sheet, cells=tuple(cells)))

    if not replaced:
        raise AssertionError(f"reference label was not found: {original!r}")
    return replace(snapshot, sheets=tuple(sheets))


class PhaseZeroBootstrapEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.glossary_snapshot = read_workbook(INCOMING_GLOSSARY_WORKBOOK)
        cls.references_snapshot = read_workbook(INCOMING_REFERENCES_WORKBOOK)

    def setUp(self) -> None:
        self.protected_bytes = {
            path: path.read_bytes()
            for path in (
                INCOMING_GLOSSARY_WORKBOOK,
                INCOMING_REFERENCES_WORKBOOK,
                CONTAMINANT_REGISTRY_PATH,
                REFERENCE_CROSSWALK_PATH,
            )
        }
        self.artifacts_before = artifact_inventory()

    def tearDown(self) -> None:
        for path, expected_bytes in self.protected_bytes.items():
            self.assertEqual(path.read_bytes(), expected_bytes, str(path))
        self.assertEqual(artifact_inventory(), self.artifacts_before)

    def validate_authoritative_pair(self):
        return validate_bootstrap_snapshots(
            self.glossary_snapshot,
            self.references_snapshot,
            REFERENCE_NAME_OVERRIDES,
        )

    def test_authoritative_bootstrap_is_repeatable_and_matches_assets(self) -> None:
        first = self.validate_authoritative_pair()
        second = self.validate_authoritative_pair()

        self.assertEqual(first, second)
        self.assertEqual(first.report.status, BootstrapReportStatus.PASSED)
        self.assertEqual(first.compatibility.data_release_id, "20260716")
        self.assertFalse(
            any(
                finding.severity is BootstrapFindingSeverity.ERROR
                for finding in first.report.findings
            )
        )
        self.assertEqual(
            first.report.counts,
            BootstrapReportCounts(152, 152, 152, 406, 133, 343, 63, 4, 33),
        )
        self.assertEqual(
            tuple(
                (mapping.id_legacy_cg, mapping.id_contaminant)
                for mapping in first.id_mappings
            ),
            tuple((number, f"RHC-{number:03d}") for number in range(1, 153)),
        )

        proposal = propose_registry_assets(first)
        registry = load_registry(CONTAMINANT_REGISTRY_PATH)
        crosswalk = load_crosswalk(REFERENCE_CROSSWALK_PATH, registry)
        self.assertEqual(registry, proposal.registry_entries)
        self.assertEqual(crosswalk, proposal.crosswalk_entries)

        identity_by_id = {
            identity.id_contaminant: identity.id_name
            for identity in first.glossary_identities
        }
        mapping_by_id = {
            mapping.id_contaminant: mapping.id_legacy_cg
            for mapping in first.id_mappings
        }
        self.assertEqual(len(registry), len(identity_by_id))
        for entry in registry:
            self.assertEqual(entry.id_name, identity_by_id[entry.id_contaminant])
            self.assertEqual(
                entry.id_legacy_cg, mapping_by_id[entry.id_contaminant]
            )
            self.assertEqual(entry.status, RegistryStatus.ACTIVE)
            self.assertEqual(entry.issued_release_id, "20260716")

    def test_exact_and_reviewed_override_relationships_are_frozen(self) -> None:
        validated = self.validate_authoritative_pair()
        registry = load_registry(CONTAMINANT_REGISTRY_PATH)
        crosswalk = load_crosswalk(REFERENCE_CROSSWALK_PATH, registry)
        identity_by_name = {
            identity.id_name: identity.id_contaminant
            for identity in validated.glossary_identities
        }
        exact_entries = tuple(
            entry
            for entry in crosswalk
            if entry.resolution_method is ReferenceResolutionMethod.EXACT
        )
        override_entries = {
            entry.refs_review_name: entry
            for entry in crosswalk
            if entry.resolution_method is ReferenceResolutionMethod.OVERRIDE
        }

        self.assertEqual(len(exact_entries), 112)
        self.assertEqual(len(override_entries), 21)
        self.assertEqual(validated.report.counts.exact_match_reference_rows, 343)
        self.assertEqual(validated.report.counts.override_reference_rows, 63)
        for entry in exact_entries:
            self.assertIn(entry.refs_review_name, identity_by_name)
            self.assertEqual(
                entry.id_contaminant, identity_by_name[entry.refs_review_name]
            )
        self.assertEqual(set(override_entries), set(REFERENCE_NAME_OVERRIDES))
        for label, target_id in REFERENCE_NAME_OVERRIDES.items():
            self.assertEqual(override_entries[label].id_contaminant, target_id)
            self.assertEqual(
                override_entries[label].resolution_method,
                ReferenceResolutionMethod.OVERRIDE,
            )
        self.assertEqual(
            override_entries["Benzo(a)pyrene"].id_contaminant, "RHC-012"
        )

    def test_unresolved_variant_fails_without_changing_protected_files(self) -> None:
        validated = self.validate_authoritative_pair()
        exact_label = next(
            entry.refs_review_name
            for entry in validated.reference_crosswalk
            if entry.resolution_method is ReferenceResolutionMethod.EXACT
        )
        unmatched_label = f" {exact_label}"
        changed_snapshot = replace_reference_label(
            self.references_snapshot, exact_label, unmatched_label
        )

        with self.assertRaises(BootstrapValidationError) as context:
            validate_bootstrap_snapshots(
                self.glossary_snapshot,
                changed_snapshot,
                REFERENCE_NAME_OVERRIDES,
            )

        report = context.exception.report
        self.assertEqual(report.status, BootstrapReportStatus.FAILED)
        unresolved = tuple(
            finding
            for finding in report.findings
            if finding.code == "unresolved_reference_relationship"
        )
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].category, BootstrapFindingCategory.REFERENCES)
        self.assertEqual(unresolved[0].severity, BootstrapFindingSeverity.ERROR)
        self.assertIn(repr(unmatched_label), unresolved[0].message)
        self.assertNotIn(unmatched_label, REFERENCE_NAME_OVERRIDES)


if __name__ == "__main__":
    unittest.main()
