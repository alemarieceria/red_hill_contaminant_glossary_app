from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from contaminant_pipeline.config import (
    GLOSSARY_WORKBOOK_FILENAME,
    GLOSSARY_WORKBOOK_TYPE,
    METADATA_SHEET_NAME,
    REFERENCES_WORKBOOK_FILENAME,
    REFERENCES_WORKBOOK_TYPE,
    WORKBOOK_SCHEMA_VERSION,
)
from contaminant_pipeline.intake import (
    IncomingContractError,
    IncomingWorkbookPair,
    read_incoming_pair,
)
from contaminant_pipeline.io_excel import (
    ExcelReadError,
    ExcelReadWarning,
    WorkbookSnapshot,
    read_workbook,
)
from contaminant_pipeline.paths import (
    INCOMING_DIR,
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    MANIFEST_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    PUBLIC_DATA_DIR,
    RAW_SNAPSHOTS_DIR,
)
from fixture_paths import (
    SYNTHETIC_GLOSSARY_WORKBOOK,
    SYNTHETIC_REFERENCES_WORKBOOK,
)


GENERATED_ROOTS = (
    MANIFEST_DIR,
    RAW_SNAPSHOTS_DIR,
    PROCESSED_DIR,
    OUTPUT_DIR,
    PUBLIC_DATA_DIR,
)


def _copy_fixture_pair(directory: Path) -> None:
    copyfile(
        SYNTHETIC_GLOSSARY_WORKBOOK,
        directory / GLOSSARY_WORKBOOK_FILENAME,
    )
    copyfile(
        SYNTHETIC_REFERENCES_WORKBOOK,
        directory / REFERENCES_WORKBOOK_FILENAME,
    )


def _metadata_values(
    snapshot: WorkbookSnapshot,
    **replacements: str,
) -> WorkbookSnapshot:
    sheets = []
    for sheet in snapshot.sheets:
        if sheet.name != METADATA_SHEET_NAME:
            sheets.append(sheet)
            continue

        keys_by_row = {
            int(cell.coordinate[1:]): cell.value
            for cell in sheet.cells
            if cell.coordinate.startswith("A")
        }
        cells = tuple(
            replace(cell, value=replacements[keys_by_row[int(cell.coordinate[1:])]])
            if cell.coordinate.startswith("B")
            and keys_by_row.get(int(cell.coordinate[1:])) in replacements
            else cell
            for cell in sheet.cells
        )
        sheets.append(replace(sheet, cells=cells))
    return replace(snapshot, sheets=tuple(sheets))


def _generated_state() -> tuple[object, ...]:
    state = []
    for root in GENERATED_ROOTS:
        state.append((root, root.exists()))
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            state.append(
                (
                    path,
                    path.is_dir(),
                    path.read_bytes() if path.is_file() else None,
                )
            )
    return tuple(state)


class GeneratedArtifactGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.generated_before = _generated_state()

    def tearDown(self) -> None:
        self.assertEqual(_generated_state(), self.generated_before)


class IncomingPairTests(GeneratedArtifactGuard):
    def test_reads_each_stable_fixture_once_and_returns_immutable_pair(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            _copy_fixture_pair(directory)
            unrelated = directory / "maintainer-notes.txt"
            unrelated.write_text("not an input", encoding="utf-8")
            original_files = {
                path.name: path.read_bytes() for path in directory.iterdir()
            }

            with patch(
                "contaminant_pipeline.intake.read_workbook",
                wraps=read_workbook,
            ) as reader:
                result = read_incoming_pair(directory)

            self.assertIsInstance(result, IncomingWorkbookPair)
            self.assertEqual(
                result.glossary_snapshot.path,
                (directory / GLOSSARY_WORKBOOK_FILENAME).resolve(),
            )
            self.assertEqual(
                result.references_snapshot.path,
                (directory / REFERENCES_WORKBOOK_FILENAME).resolve(),
            )
            self.assertEqual(
                result.compatibility.glossary_metadata.workbook_type,
                GLOSSARY_WORKBOOK_TYPE,
            )
            self.assertEqual(
                result.compatibility.references_metadata.workbook_type,
                REFERENCES_WORKBOOK_TYPE,
            )
            self.assertEqual(
                result.compatibility.glossary_metadata.schema_version,
                WORKBOOK_SCHEMA_VERSION,
            )
            self.assertEqual(
                result.compatibility.glossary_metadata.workbook_revision,
                "20000115",
            )
            self.assertEqual(
                result.compatibility.references_metadata.workbook_revision,
                "20000115-r2",
            )
            self.assertEqual(result.compatibility.data_release_id, "20000115-r2")
            self.assertEqual(
                [call.args[0] for call in reader.call_args_list],
                [
                    directory.resolve() / GLOSSARY_WORKBOOK_FILENAME,
                    directory.resolve() / REFERENCES_WORKBOOK_FILENAME,
                ],
            )
            with self.assertRaises(FrozenInstanceError):
                result.compatibility = result.compatibility
            self.assertEqual(
                {path.name: path.read_bytes() for path in directory.iterdir()},
                original_files,
            )

    def test_derives_the_newer_revision_at_the_intake_boundary(self) -> None:
        glossary = read_workbook(SYNTHETIC_GLOSSARY_WORKBOOK)
        references = read_workbook(SYNTHETIC_REFERENCES_WORKBOOK)
        cases = (
            ("20000116", "20000115-r10", "20000116"),
            ("20000115-r2", "20000115-r10", "20000115-r10"),
        )

        with TemporaryDirectory() as temporary_directory:
            for glossary_revision, references_revision, expected in cases:
                with self.subTest(expected=expected):
                    supplied = (
                        _metadata_values(
                            glossary,
                            workbook_revision=glossary_revision,
                        ),
                        _metadata_values(
                            references,
                            workbook_revision=references_revision,
                        ),
                    )
                    with patch(
                        "contaminant_pipeline.intake.read_workbook",
                        side_effect=supplied,
                    ):
                        result = read_incoming_pair(temporary_directory)

                    self.assertEqual(result.compatibility.data_release_id, expected)

    def test_preserves_non_blocking_reader_warnings(self) -> None:
        warning = ExcelReadWarning(
            message="example warning",
            sheet_name="Introduction",
            coordinate="A1",
        )
        glossary = replace(
            read_workbook(SYNTHETIC_GLOSSARY_WORKBOOK),
            warnings=(warning,),
        )
        references = read_workbook(SYNTHETIC_REFERENCES_WORKBOOK)

        with TemporaryDirectory() as temporary_directory:
            with patch(
                "contaminant_pipeline.intake.read_workbook",
                side_effect=(glossary, references),
            ):
                result = read_incoming_pair(temporary_directory)

        self.assertEqual(result.glossary_snapshot.warnings, (warning,))
        self.assertEqual(result.references_snapshot.warnings, ())


class IncomingPairFailureTests(GeneratedArtifactGuard):
    def test_rejects_a_missing_or_non_directory_input(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing"
            with self.assertRaisesRegex(
                IncomingContractError,
                "incoming directory does not exist",
            ):
                read_incoming_pair(missing)

            not_a_directory = Path(temporary_directory) / "file"
            not_a_directory.write_text("content", encoding="utf-8")
            with self.assertRaisesRegex(
                IncomingContractError,
                "is not a directory",
            ):
                read_incoming_pair(not_a_directory)

    def test_rejects_each_missing_required_filename_with_role_context(self) -> None:
        cases = (
            (
                "glossary",
                SYNTHETIC_REFERENCES_WORKBOOK,
                REFERENCES_WORKBOOK_FILENAME,
            ),
            (
                "references",
                SYNTHETIC_GLOSSARY_WORKBOOK,
                GLOSSARY_WORKBOOK_FILENAME,
            ),
        )
        for role, source, filename in cases:
            with self.subTest(role=role), TemporaryDirectory() as temporary_directory:
                directory = Path(temporary_directory)
                copyfile(source, directory / filename)
                original_files = {
                    path.name: path.read_bytes() for path in directory.iterdir()
                }

                with self.assertRaisesRegex(
                    IncomingContractError,
                    f"required {role} workbook",
                ) as raised:
                    read_incoming_pair(directory)

                self.assertIsInstance(raised.exception.__cause__, ExcelReadError)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in directory.iterdir()},
                    original_files,
                )

    def test_rejects_each_corrupt_workbook_with_role_context(self) -> None:
        for role, corrupt_filename in (
            ("glossary", GLOSSARY_WORKBOOK_FILENAME),
            ("references", REFERENCES_WORKBOOK_FILENAME),
        ):
            with self.subTest(role=role), TemporaryDirectory() as temporary_directory:
                directory = Path(temporary_directory)
                _copy_fixture_pair(directory)
                corrupt_path = directory / corrupt_filename
                corrupt_path.write_bytes(b"not an Excel workbook")
                original_files = {
                    path.name: path.read_bytes() for path in directory.iterdir()
                }

                with self.assertRaisesRegex(
                    IncomingContractError,
                    f"required {role} workbook.*{corrupt_filename}",
                ) as raised:
                    read_incoming_pair(directory)

                self.assertIsInstance(raised.exception.__cause__, ExcelReadError)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in directory.iterdir()},
                    original_files,
                )

    def test_rejects_workbook_contents_swapped_between_stable_names(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            copyfile(
                SYNTHETIC_REFERENCES_WORKBOOK,
                directory / GLOSSARY_WORKBOOK_FILENAME,
            )
            copyfile(
                SYNTHETIC_GLOSSARY_WORKBOOK,
                directory / REFERENCES_WORKBOOK_FILENAME,
            )
            original_files = {
                path.name: path.read_bytes() for path in directory.iterdir()
            }

            with self.assertRaisesRegex(
                IncomingContractError,
                "glossary workbook must declare workbook_type",
            ):
                read_incoming_pair(directory)

            self.assertEqual(
                {path.name: path.read_bytes() for path in directory.iterdir()},
                original_files,
            )

    def test_rejects_mismatched_or_unsupported_schema_versions(self) -> None:
        glossary = read_workbook(SYNTHETIC_GLOSSARY_WORKBOOK)
        references = read_workbook(SYNTHETIC_REFERENCES_WORKBOOK)
        cases = (
            (
                glossary,
                _metadata_values(references, schema_version="2.0.0"),
                "schema versions do not match",
            ),
            (
                _metadata_values(glossary, schema_version="2.0.0"),
                _metadata_values(references, schema_version="2.0.0"),
                "unsupported workbook schema version",
            ),
        )

        with TemporaryDirectory() as temporary_directory:
            for supplied_glossary, supplied_references, message in cases:
                with self.subTest(message=message):
                    with patch(
                        "contaminant_pipeline.intake.read_workbook",
                        side_effect=(supplied_glossary, supplied_references),
                    ):
                        with self.assertRaisesRegex(
                            IncomingContractError,
                            message,
                        ):
                            read_incoming_pair(temporary_directory)

    def test_rejects_invalid_metadata_with_role_and_path_context(self) -> None:
        glossary = _metadata_values(
            read_workbook(SYNTHETIC_GLOSSARY_WORKBOOK),
            workbook_revision="invalid",
        )
        references = read_workbook(SYNTHETIC_REFERENCES_WORKBOOK)

        with TemporaryDirectory() as temporary_directory:
            with patch(
                "contaminant_pipeline.intake.read_workbook",
                side_effect=(glossary, references),
            ):
                with self.assertRaisesRegex(
                    IncomingContractError,
                    "invalid glossary workbook Metadata.*contaminant_glossary.xlsx",
                ) as raised:
                    read_incoming_pair(temporary_directory)

        self.assertIsInstance(raised.exception.__cause__, ValueError)
        self.assertIn("release ID must have the form", str(raised.exception))


class AuthoritativeIncomingPairTests(GeneratedArtifactGuard):
    def test_current_pair_validates_without_modifying_protected_files(self) -> None:
        original_workbooks = {
            path: path.read_bytes()
            for path in (
                INCOMING_GLOSSARY_WORKBOOK,
                INCOMING_REFERENCES_WORKBOOK,
            )
        }
        generated_before = _generated_state()

        result = read_incoming_pair(INCOMING_DIR)

        self.assertEqual(
            result.compatibility.glossary_metadata.workbook_type,
            GLOSSARY_WORKBOOK_TYPE,
        )
        self.assertEqual(
            result.compatibility.references_metadata.workbook_type,
            REFERENCES_WORKBOOK_TYPE,
        )
        self.assertEqual(
            result.compatibility.glossary_metadata.schema_version,
            WORKBOOK_SCHEMA_VERSION,
        )
        self.assertEqual(
            result.compatibility.references_metadata.schema_version,
            WORKBOOK_SCHEMA_VERSION,
        )
        self.assertEqual(
            result.compatibility.glossary_metadata.workbook_revision,
            "20260716",
        )
        self.assertEqual(
            result.compatibility.references_metadata.workbook_revision,
            "20260716",
        )
        self.assertEqual(result.compatibility.data_release_id, "20260716")
        self.assertEqual(
            {path: path.read_bytes() for path in original_workbooks},
            original_workbooks,
        )
        self.assertEqual(_generated_state(), generated_before)


if __name__ == "__main__":
    unittest.main()
