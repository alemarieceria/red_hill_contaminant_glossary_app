from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from openpyxl.utils.cell import get_column_letter

from contaminant_pipeline.config import (
    GLOSSARY_WORKBOOK_TYPE,
    METADATA_SHEET_NAME,
    METADATA_TABLE_NAME,
    REFERENCES_WORKBOOK_TYPE,
    WORKBOOK_SCHEMA_VERSION,
)
from contaminant_pipeline.io_excel import (
    CellSnapshot,
    TableSnapshot,
    WorkbookSnapshot,
    WorksheetSnapshot,
    read_workbook,
)
from contaminant_pipeline.metadata import (
    WorkbookCompatibility,
    WorkbookMetadata,
    extract_workbook_metadata,
    validate_workbook_compatibility,
)
from contaminant_pipeline.paths import (
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
)
from fixture_paths import (
    SYNTHETIC_GLOSSARY_WORKBOOK,
    SYNTHETIC_REFERENCES_WORKBOOK,
)


VALID_ROWS = (
    ("workbook_type", GLOSSARY_WORKBOOK_TYPE),
    ("schema_version", WORKBOOK_SCHEMA_VERSION),
    ("workbook_revision", "20260716"),
)


def metadata_snapshot(
    *,
    rows=VALID_ROWS,
    headers=("key", "value"),
    table_reference="A1:B4",
    tables=None,
    start_row=1,
    start_column=1,
    formula_coordinate=None,
    sheet_count=1,
) -> WorkbookSnapshot:
    """Build an in-memory snapshot without creating an Excel file."""

    cells = []
    for row_offset, values in enumerate((headers, *rows)):
        for column_offset, value in enumerate(values):
            if value is None:
                continue
            coordinate = (
                f"{get_column_letter(start_column + column_offset)}"
                f"{start_row + row_offset}"
            )
            cells.append(
                CellSnapshot(
                    coordinate=coordinate,
                    value=value,
                    formula="=\"computed\""
                    if coordinate == formula_coordinate
                    else None,
                )
            )

    if tables is None:
        tables = (TableSnapshot(METADATA_TABLE_NAME, table_reference),)
    sheets = tuple(
        WorksheetSnapshot(
            name=METADATA_SHEET_NAME,
            max_row=start_row + len(rows),
            max_column=start_column + 1,
            tables=tuple(tables),
            cells=tuple(cells),
        )
        for _ in range(sheet_count)
    )
    return WorkbookSnapshot(
        path=Path("example.xlsx"),
        sheets=sheets,
        warnings=(),
    )


def workbook_metadata(
    workbook_type,
    revision="20260716",
    schema=WORKBOOK_SCHEMA_VERSION,
) -> WorkbookMetadata:
    return WorkbookMetadata(workbook_type, schema, revision)


class MetadataExtractionTests(unittest.TestCase):
    def test_extracts_metadata_by_declared_range_and_ignores_row_order(
        self,
    ) -> None:
        snapshot = metadata_snapshot(
            rows=(VALID_ROWS[2], VALID_ROWS[0], VALID_ROWS[1]),
            table_reference="C2:D5",
            start_row=2,
            start_column=3,
        )

        result = extract_workbook_metadata(snapshot)

        self.assertEqual(
            result,
            WorkbookMetadata(
                workbook_type=GLOSSARY_WORKBOOK_TYPE,
                schema_version=WORKBOOK_SCHEMA_VERSION,
                workbook_revision="20260716",
            ),
        )

    def test_metadata_records_are_immutable(self) -> None:
        metadata = workbook_metadata(GLOSSARY_WORKBOOK_TYPE)
        compatibility = WorkbookCompatibility(
            metadata,
            workbook_metadata(REFERENCES_WORKBOOK_TYPE),
            "20260716",
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(metadata, "workbook_revision", "20260717")
        with self.assertRaises(FrozenInstanceError):
            setattr(compatibility, "data_release_id", "20260717")

    def test_rejects_missing_or_duplicate_metadata_sheets(self) -> None:
        for count in (0, 2):
            with self.subTest(sheet_count=count):
                with self.assertRaisesRegex(ValueError, "exactly one 'Metadata'"):
                    extract_workbook_metadata(
                        metadata_snapshot(sheet_count=count)
                    )

    def test_rejects_missing_wrong_or_extra_tables(self) -> None:
        cases = (
            (),
            (TableSnapshot("OtherTable", "A1:B4"),),
            (
                TableSnapshot(METADATA_TABLE_NAME, "A1:B4"),
                TableSnapshot("OtherTable", "D1:E2"),
            ),
        )

        for tables in cases:
            with self.subTest(tables=tables):
                with self.assertRaisesRegex(ValueError, "exactly one 'MetadataTable'"):
                    extract_workbook_metadata(metadata_snapshot(tables=tables))

    def test_rejects_a_malformed_table_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "malformed MetadataTable range"):
            extract_workbook_metadata(
                metadata_snapshot(table_reference="not-a-range")
            )

    def test_rejects_wrong_table_dimensions(self) -> None:
        cases = (
            ("A1:C4", "exactly two columns"),
            ("A1:B5", "three data rows"),
        )

        for reference, message in cases:
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(ValueError, message):
                    extract_workbook_metadata(
                        metadata_snapshot(table_reference=reference)
                    )

    def test_rejects_altered_or_reversed_headers(self) -> None:
        for headers in (("value", "key"), ("Key", "value"), ("key", None)):
            with self.subTest(headers=headers):
                with self.assertRaisesRegex(ValueError, "headers must be exactly"):
                    extract_workbook_metadata(
                        metadata_snapshot(headers=headers)
                    )

    def test_rejects_formula_backed_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "literal text, not formulas"):
            extract_workbook_metadata(
                metadata_snapshot(formula_coordinate="B2")
            )

    def test_rejects_invalid_metadata_keys(self) -> None:
        cases = (
            (
                (VALID_ROWS[0], VALID_ROWS[1], ("other", "value")),
                "missing 'workbook_revision'; unknown 'other'",
            ),
            (
                (VALID_ROWS[0], VALID_ROWS[1], VALID_ROWS[1]),
                "duplicate Metadata keys",
            ),
            (((None, "value"), VALID_ROWS[1], VALID_ROWS[2]), "nonblank text"),
            (((1, "value"), VALID_ROWS[1], VALID_ROWS[2]), "nonblank text"),
            (((" key", "value"), VALID_ROWS[1], VALID_ROWS[2]), "whitespace"),
        )

        for rows, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    extract_workbook_metadata(metadata_snapshot(rows=rows))

    def test_rejects_invalid_metadata_values(self) -> None:
        cases = (
            (None, "nonblank text"),
            ("", "nonblank text"),
            (1, "nonblank text"),
            (" references", "whitespace"),
        )

        for value, message in cases:
            with self.subTest(value=value):
                rows = (("workbook_type", value), *VALID_ROWS[1:])
                with self.assertRaisesRegex(ValueError, message):
                    extract_workbook_metadata(metadata_snapshot(rows=rows))

    def test_rejects_an_invalid_workbook_revision(self) -> None:
        rows = (*VALID_ROWS[:2], ("workbook_revision", "20260716-r1"))

        with self.assertRaisesRegex(ValueError, "release ID must have the form"):
            extract_workbook_metadata(metadata_snapshot(rows=rows))


class MetadataCompatibilityTests(unittest.TestCase):
    def test_accepts_equal_revisions(self) -> None:
        result = validate_workbook_compatibility(
            workbook_metadata(GLOSSARY_WORKBOOK_TYPE),
            workbook_metadata(REFERENCES_WORKBOOK_TYPE),
        )

        self.assertEqual(result.data_release_id, "20260716")

    def test_uses_the_newer_calendar_date(self) -> None:
        result = validate_workbook_compatibility(
            workbook_metadata(GLOSSARY_WORKBOOK_TYPE, "20260717"),
            workbook_metadata(REFERENCES_WORKBOOK_TYPE, "20260716-r9"),
        )

        self.assertEqual(result.data_release_id, "20260717")

    def test_orders_same_day_revision_suffixes_numerically(self) -> None:
        result = validate_workbook_compatibility(
            workbook_metadata(GLOSSARY_WORKBOOK_TYPE, "20260716-r2"),
            workbook_metadata(REFERENCES_WORKBOOK_TYPE, "20260716-r10"),
        )

        self.assertEqual(result.data_release_id, "20260716-r10")

    def test_rejects_non_metadata_records(self) -> None:
        valid_glossary = workbook_metadata(GLOSSARY_WORKBOOK_TYPE)
        valid_references = workbook_metadata(REFERENCES_WORKBOOK_TYPE)
        cases = (
            (object(), valid_references, "glossary Metadata"),
            (valid_glossary, object(), "references Metadata"),
        )

        for glossary, references, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_workbook_compatibility(glossary, references)

    def test_rejects_reversed_unknown_or_duplicated_workbook_types(self) -> None:
        cases = (
            (REFERENCES_WORKBOOK_TYPE, GLOSSARY_WORKBOOK_TYPE),
            ("unknown", REFERENCES_WORKBOOK_TYPE),
            (GLOSSARY_WORKBOOK_TYPE, GLOSSARY_WORKBOOK_TYPE),
        )

        for glossary_type, references_type in cases:
            with self.subTest(
                glossary_type=glossary_type,
                references_type=references_type,
            ):
                with self.assertRaisesRegex(ValueError, "workbook must declare"):
                    validate_workbook_compatibility(
                        workbook_metadata(glossary_type),
                        workbook_metadata(references_type),
                    )

    def test_rejects_mismatched_schema_versions(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema versions do not match"):
            validate_workbook_compatibility(
                workbook_metadata(GLOSSARY_WORKBOOK_TYPE, schema="1.0.0"),
                workbook_metadata(REFERENCES_WORKBOOK_TYPE, schema="2.0.0"),
            )

    def test_rejects_a_mutually_unsupported_schema_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported workbook schema"):
            validate_workbook_compatibility(
                workbook_metadata(GLOSSARY_WORKBOOK_TYPE, schema="2.0.0"),
                workbook_metadata(REFERENCES_WORKBOOK_TYPE, schema="2.0.0"),
            )

    def test_revalidates_revision_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "release ID must have the form"):
            validate_workbook_compatibility(
                workbook_metadata(GLOSSARY_WORKBOOK_TYPE, "20260716-r1"),
                workbook_metadata(REFERENCES_WORKBOOK_TYPE),
            )


class MetadataWorkbookIntegrationTests(unittest.TestCase):
    def test_synthetic_workbooks_allow_unequal_revisions(self) -> None:
        glossary = extract_workbook_metadata(
            read_workbook(SYNTHETIC_GLOSSARY_WORKBOOK)
        )
        references = extract_workbook_metadata(
            read_workbook(SYNTHETIC_REFERENCES_WORKBOOK)
        )

        result = validate_workbook_compatibility(glossary, references)

        self.assertEqual(glossary.workbook_revision, "20000115")
        self.assertEqual(references.workbook_revision, "20000115-r2")
        self.assertEqual(result.data_release_id, "20000115-r2")

    def test_authoritative_workbooks_validate_without_file_changes(self) -> None:
        glossary_bytes = INCOMING_GLOSSARY_WORKBOOK.read_bytes()
        references_bytes = INCOMING_REFERENCES_WORKBOOK.read_bytes()

        glossary = extract_workbook_metadata(
            read_workbook(INCOMING_GLOSSARY_WORKBOOK)
        )
        references = extract_workbook_metadata(
            read_workbook(INCOMING_REFERENCES_WORKBOOK)
        )
        result = validate_workbook_compatibility(glossary, references)

        self.assertEqual(
            glossary,
            WorkbookMetadata(GLOSSARY_WORKBOOK_TYPE, "1.0.0", "20260810"),
        )
        self.assertEqual(
            references,
            WorkbookMetadata(REFERENCES_WORKBOOK_TYPE, "1.0.0", "20260716"),
        )
        self.assertEqual(result.data_release_id, "20260810")
        self.assertEqual(
            INCOMING_GLOSSARY_WORKBOOK.read_bytes(), glossary_bytes
        )
        self.assertEqual(
            INCOMING_REFERENCES_WORKBOOK.read_bytes(), references_bytes
        )


if __name__ == "__main__":
    unittest.main()
