from collections import Counter
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
import unittest

from openpyxl.utils.cell import coordinate_to_tuple, get_column_letter

from contaminant_pipeline.bootstrap_report import (
    BootstrapFindingCategory,
    BootstrapFindingSeverity,
    BootstrapReportStatus,
)
from contaminant_pipeline.bootstrap_validation import (
    BootstrapValidationError,
    validate_bootstrap_snapshots,
)
from contaminant_pipeline.config import GLOSSARY_SHEET_NAME
from contaminant_pipeline.crosswalk import REFERENCE_NAME_OVERRIDES
from contaminant_pipeline.identifiers import BootstrapIdMapping
from contaminant_pipeline.io_excel import (
    CellSnapshot,
    ExcelReadWarning,
    read_workbook,
)
from contaminant_pipeline.paths import (
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    MANIFEST_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    RAW_SNAPSHOTS_DIR,
)
from contaminant_pipeline.schemas import GLOSSARY_HEADER_MAP
from fixture_paths import (
    SYNTHETIC_GLOSSARY_WORKBOOK,
    SYNTHETIC_REFERENCES_WORKBOOK,
)


def fixture_id_mappings(values):
    legacy_ids = tuple(values)
    if set(legacy_ids) != {901, 902, 903}:
        raise ValueError("fixture legacy ID set is incomplete")
    return tuple(
        BootstrapIdMapping(value, f"RHC-{value:03d}")
        for value in sorted(legacy_ids)
    )


def replace_cell(snapshot, sheet_name, coordinate, value, formula=None):
    sheets = []
    for sheet in snapshot.sheets:
        if sheet.name != sheet_name:
            sheets.append(sheet)
            continue
        cells = []
        replaced = False
        for cell in sheet.cells:
            if cell.coordinate == coordinate:
                cells.append(CellSnapshot(coordinate, value, formula))
                replaced = True
            else:
                cells.append(cell)
        if not replaced:
            cells.append(CellSnapshot(coordinate, value, formula))
        sheets.append(replace(sheet, cells=tuple(cells)))
    return replace(snapshot, sheets=tuple(sheets))


def glossary_header_coordinate(snapshot, source_header, row_number):
    sheet = next(
        sheet for sheet in snapshot.sheets if sheet.name == GLOSSARY_SHEET_NAME
    )
    header_cell = next(
        cell for cell in sheet.cells if cell.value == source_header
    )
    _, column = coordinate_to_tuple(header_cell.coordinate)
    return f"{get_column_letter(column)}{row_number}"


def data_artifact_inventory():
    roots = (MANIFEST_DIR, RAW_SNAPSHOTS_DIR, PROCESSED_DIR, OUTPUT_DIR)
    return tuple(
        sorted(
            str(path.relative_to(root))
            for root in roots
            if root.exists()
            for path in root.rglob("*")
        )
    )


class SyntheticBootstrapValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.glossary = read_workbook(SYNTHETIC_GLOSSARY_WORKBOOK)
        self.references = read_workbook(SYNTHETIC_REFERENCES_WORKBOOK)

    def validate_fixture(self, glossary=None, references=None):
        with patch(
            "contaminant_pipeline.bootstrap_validation.bootstrap_contaminant_ids",
            side_effect=fixture_id_mappings,
        ):
            return validate_bootstrap_snapshots(
                glossary or self.glossary,
                references or self.references,
                {},
            )

    def test_validates_the_synthetic_pair_end_to_end(self) -> None:
        result = self.validate_fixture()

        self.assertEqual(result.report.status, BootstrapReportStatus.PASSED)
        self.assertEqual(result.compatibility.data_release_id, "20000115-r2")
        self.assertEqual(result.report.findings, ())
        self.assertEqual(
            result.report.counts,
            result.report.counts.__class__(3, 3, 3, 4, 3, 4, 0, 2, 4),
        )
        self.assertEqual(len(result.glossary_identities), 3)
        self.assertEqual(len(result.reference_crosswalk), 3)
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "id_mappings", ())

    def assert_failed_category(self, callback, category):
        with self.assertRaises(BootstrapValidationError) as context:
            callback()
        self.assertEqual(context.exception.report.status, BootstrapReportStatus.FAILED)
        self.assertTrue(
            any(
                item.category is category
                and item.severity is BootstrapFindingSeverity.ERROR
                for item in context.exception.report.findings
            )
        )
        return context.exception.report

    def test_reports_an_invalid_legacy_id_set(self) -> None:
        legacy_header = next(
            header
            for header, field in GLOSSARY_HEADER_MAP.items()
            if field == "id_legacy_cg"
        )
        coordinate = glossary_header_coordinate(self.glossary, legacy_header, 3)
        glossary = replace_cell(
            self.glossary, GLOSSARY_SHEET_NAME, coordinate, 901
        )

        self.assert_failed_category(
            lambda: self.validate_fixture(glossary=glossary),
            BootstrapFindingCategory.IDS,
        )

    def test_converts_excel_reader_warnings_without_failing(self) -> None:
        warning = ExcelReadWarning(
            message="Synthetic reader warning",
            sheet_name=GLOSSARY_SHEET_NAME,
            coordinate="A2",
        )
        glossary = replace(self.glossary, warnings=(warning,))

        result = self.validate_fixture(glossary=glossary)

        self.assertEqual(result.report.status, BootstrapReportStatus.PASSED)
        report_warning = next(
            item for item in result.report.findings if item.code == "excel_read_warning"
        )
        self.assertEqual(report_warning.severity, BootstrapFindingSeverity.WARNING)
        self.assertEqual(report_warning.sheet, GLOSSARY_SHEET_NAME)
        self.assertEqual(report_warning.source_row, 2)

    def test_reports_ambiguous_glossary_names(self) -> None:
        glossary = replace_cell(
            self.glossary, GLOSSARY_SHEET_NAME, "A3", "Synthetic Alpha"
        )

        report = self.assert_failed_category(
            lambda: self.validate_fixture(glossary=glossary),
            BootstrapFindingCategory.NAMES,
        )

        self.assertTrue(
            any("ambiguous glossary names" in item.message for item in report.findings)
        )

    def test_reports_an_unresolved_reference_label(self) -> None:
        references = replace_cell(
            self.references, "Sheet1", "A2", "Unknown Synthetic"
        )

        report = self.assert_failed_category(
            lambda: self.validate_fixture(references=references),
            BootstrapFindingCategory.REFERENCES,
        )

        self.assertTrue(
            any("Unknown Synthetic" in item.message for item in report.findings)
        )

    def test_reports_incompatible_metadata(self) -> None:
        glossary = replace_cell(self.glossary, "Metadata", "B2", "2.0.0")

        report = self.assert_failed_category(
            lambda: self.validate_fixture(glossary=glossary),
            BootstrapFindingCategory.WORKBOOKS,
        )

        self.assertIsNone(report.compatibility)

    def test_reports_an_invalid_footnote_definition(self) -> None:
        glossary = replace_cell(self.glossary, "Footnotes", "A2", "bad")

        report = self.assert_failed_category(
            lambda: self.validate_fixture(glossary=glossary),
            BootstrapFindingCategory.FOOTNOTES,
        )

        issue = next(
            item
            for item in report.findings
            if item.category is BootstrapFindingCategory.FOOTNOTES
        )
        self.assertEqual(issue.sheet, "Footnotes")
        self.assertEqual(issue.source_row, 2)

    def test_reports_an_unknown_glossary_footnote_usage(self) -> None:
        footnote_header = next(
            header
            for header, field in GLOSSARY_HEADER_MAP.items()
            if field == "source_notes_footnote_ids"
        )
        coordinate = glossary_header_coordinate(self.glossary, footnote_header, 2)
        glossary = replace_cell(
            self.glossary, GLOSSARY_SHEET_NAME, coordinate, "UNKNOWN"
        )

        report = self.assert_failed_category(
            lambda: self.validate_fixture(glossary=glossary),
            BootstrapFindingCategory.FOOTNOTES,
        )

        issue = next(
            item
            for item in report.findings
            if item.category is BootstrapFindingCategory.FOOTNOTES
        )
        self.assertEqual(issue.sheet, GLOSSARY_SHEET_NAME)
        self.assertEqual(issue.source_row, 2)
        self.assertEqual(issue.source_value, "'UNKNOWN'")


class AuthoritativeBootstrapValidationTests(unittest.TestCase):
    def test_current_workbooks_produce_a_complete_passing_bootstrap(self) -> None:
        glossary_bytes = INCOMING_GLOSSARY_WORKBOOK.read_bytes()
        references_bytes = INCOMING_REFERENCES_WORKBOOK.read_bytes()
        artifacts_before = data_artifact_inventory()

        result = validate_bootstrap_snapshots(
            read_workbook(INCOMING_GLOSSARY_WORKBOOK),
            read_workbook(INCOMING_REFERENCES_WORKBOOK),
            REFERENCE_NAME_OVERRIDES,
        )

        self.assertEqual(result.report.status, BootstrapReportStatus.PASSED)
        self.assertEqual(result.compatibility.data_release_id, "20260716")
        self.assertEqual(
            result.report.counts,
            result.report.counts.__class__(
                152, 152, 152, 406, 133, 343, 63, 4, 33
            ),
        )
        override_findings = tuple(
            item
            for item in result.report.findings
            if item.code == "reference_label_override"
        )
        self.assertEqual(len(override_findings), 21)
        self.assertTrue(
            all(
                item.severity is BootstrapFindingSeverity.INFO
                for item in override_findings
            )
        )
        usage_counts = Counter(
            footnote_id
            for usage in result.footnote_usages
            for footnote_id in usage.footnote_ids
        )
        self.assertEqual(usage_counts, {"A": 15, "B": 10, "C": 6, "D": 2})
        self.assertEqual(
            tuple(item.footnote_id for item in result.footnote_definitions),
            ("A", "B", "C", "D"),
        )
        self.assertEqual(
            INCOMING_GLOSSARY_WORKBOOK.read_bytes(), glossary_bytes
        )
        self.assertEqual(
            INCOMING_REFERENCES_WORKBOOK.read_bytes(), references_bytes
        )
        self.assertEqual(data_artifact_inventory(), artifacts_before)


if __name__ == "__main__":
    unittest.main()
