import os
import unittest
from pathlib import Path

from contaminant_pipeline.config import (
    FOOTNOTES_SHEET_NAME,
    FOOTNOTES_HEADER_ROW,
    GLOSSARY_SHEET_NAME,
    GLOSSARY_TABLE_NAME,
    GLOSSARY_WORKBOOK_FILENAME,
    GLOSSARY_WORKBOOK_TYPE,
    GLOSSARY_WORKSHEET_NAMES,
    INTRODUCTION_SHEET_NAME,
    INTAKE_MANIFEST_SCHEMA_VERSION,
    METADATA_SHEET_NAME,
    METADATA_TABLE_NAME,
    REFERENCES_SHEET_NAME,
    REFERENCES_HEADER_ROW,
    REFERENCES_WORKBOOK_FILENAME,
    REFERENCES_WORKBOOK_TYPE,
    REFERENCES_WORKSHEET_NAMES,
    SUPPORTED_WORKBOOK_SCHEMA_VERSIONS,
    WORKBOOK_SCHEMA_VERSION,
    validate_release_id,
)
from contaminant_pipeline.paths import (
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    MANIFEST_DIR,
    OUTPUT_DIR,
    PIPELINE_ROOT,
    PROCESSED_DIR,
    PUBLIC_DATA_DIR,
    RAW_SNAPSHOTS_DIR,
    REPOSITORY_ROOT,
    manifest_path,
    output_release_dir,
    processed_release_dir,
    raw_snapshot_dir,
)


class ConfigTests(unittest.TestCase):
    def test_centralizes_current_workbook_structure(self) -> None:
        self.assertEqual(GLOSSARY_WORKBOOK_FILENAME, "contaminant_glossary.xlsx")
        self.assertEqual(REFERENCES_WORKBOOK_FILENAME, "references.xlsx")
        self.assertEqual(GLOSSARY_WORKBOOK_TYPE, "contaminant_glossary")
        self.assertEqual(REFERENCES_WORKBOOK_TYPE, "references")
        self.assertEqual(INTRODUCTION_SHEET_NAME, "Introduction")
        self.assertEqual(GLOSSARY_SHEET_NAME, "Glossary")
        self.assertEqual(FOOTNOTES_SHEET_NAME, "Footnotes")
        self.assertEqual(METADATA_SHEET_NAME, "Metadata")
        self.assertEqual(REFERENCES_SHEET_NAME, "Sheet1")
        self.assertEqual(
            GLOSSARY_WORKSHEET_NAMES,
            ("Introduction", "Glossary", "Footnotes", "Metadata"),
        )
        self.assertEqual(
            REFERENCES_WORKSHEET_NAMES,
            ("Sheet1", "Metadata"),
        )
        self.assertEqual(FOOTNOTES_HEADER_ROW, 1)
        self.assertEqual(REFERENCES_HEADER_ROW, 1)
        self.assertEqual(GLOSSARY_TABLE_NAME, "Table_1")
        self.assertEqual(METADATA_TABLE_NAME, "MetadataTable")
        self.assertEqual(WORKBOOK_SCHEMA_VERSION, "1.0.0")
        self.assertEqual(INTAKE_MANIFEST_SCHEMA_VERSION, "1.0.0")
        self.assertEqual(SUPPORTED_WORKBOOK_SCHEMA_VERSIONS, {"1.0.0"})

    def test_accepts_valid_release_ids(self) -> None:
        for value in ("20260713", "20260713-r2", "20260713-r10"):
            with self.subTest(value=value):
                self.assertEqual(validate_release_id(value), value)

    def test_rejects_invalid_release_ids(self) -> None:
        invalid_values = (
            None,
            20260713,
            "",
            "20260230",
            "20260713-r1",
            "20260713-r01",
            "20260713-R2",
            " 20260713",
            "20260713 ",
            "../20260713",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_release_id(value)


class PathTests(unittest.TestCase):
    def test_resolves_project_roots_and_incoming_workbooks(self) -> None:
        expected_pipeline_root = Path(__file__).resolve().parents[1]

        self.assertEqual(PIPELINE_ROOT, expected_pipeline_root)
        self.assertEqual(REPOSITORY_ROOT, expected_pipeline_root.parent)
        self.assertEqual(PUBLIC_DATA_DIR, REPOSITORY_ROOT / "public" / "data")
        self.assertEqual(
            INCOMING_GLOSSARY_WORKBOOK,
            PIPELINE_ROOT / "data" / "00_incoming" / GLOSSARY_WORKBOOK_FILENAME,
        )
        self.assertEqual(
            INCOMING_REFERENCES_WORKBOOK,
            PIPELINE_ROOT / "data" / "00_incoming" / REFERENCES_WORKBOOK_FILENAME,
        )
        self.assertTrue(INCOMING_GLOSSARY_WORKBOOK.is_file())
        self.assertTrue(INCOMING_REFERENCES_WORKBOOK.is_file())

    def test_paths_do_not_depend_on_current_working_directory(self) -> None:
        expected = RAW_SNAPSHOTS_DIR / "20260713-r2"
        original_working_directory = Path.cwd()

        try:
            os.chdir(PIPELINE_ROOT / "tests")
            self.assertEqual(raw_snapshot_dir("20260713-r2"), expected)
        finally:
            os.chdir(original_working_directory)

    def test_release_helpers_return_paths_without_creating_them(self) -> None:
        release_id = "20991231-r999"
        expected_paths = (
            RAW_SNAPSHOTS_DIR / release_id,
            PROCESSED_DIR / release_id,
            OUTPUT_DIR / release_id,
            MANIFEST_DIR / f"{release_id}.json",
        )

        self.assertFalse(any(path.exists() for path in expected_paths))
        self.assertEqual(raw_snapshot_dir(release_id), expected_paths[0])
        self.assertEqual(processed_release_dir(release_id), expected_paths[1])
        self.assertEqual(output_release_dir(release_id), expected_paths[2])
        self.assertEqual(manifest_path(release_id), expected_paths[3])
        self.assertFalse(any(path.exists() for path in expected_paths))

    def test_release_helpers_reject_traversal(self) -> None:
        for helper in (
            raw_snapshot_dir,
            processed_release_dir,
            output_release_dir,
            manifest_path,
        ):
            with self.subTest(helper=helper.__name__):
                with self.assertRaises(ValueError):
                    helper("../outside")


if __name__ == "__main__":
    unittest.main()
