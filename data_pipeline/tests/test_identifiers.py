from dataclasses import FrozenInstanceError
import unittest

from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

from contaminant_pipeline.config import (
    GLOSSARY_SHEET_NAME,
    GLOSSARY_TABLE_NAME,
)
from contaminant_pipeline.identifiers import (
    BootstrapIdMapping,
    INITIAL_LEGACY_ID_MAX,
    INITIAL_LEGACY_ID_MIN,
    bootstrap_contaminant_ids,
    contaminant_id_number,
    next_contaminant_id,
    validate_contaminant_ids,
)
from contaminant_pipeline.io_excel import WorkbookSnapshot, read_workbook
from contaminant_pipeline.paths import INCOMING_GLOSSARY_WORKBOOK
from contaminant_pipeline.schemas import GLOSSARY_HEADER_MAP


LEGACY_ID_SOURCE_HEADER = next(
    source_header
    for source_header, canonical_field in GLOSSARY_HEADER_MAP.items()
    if canonical_field == "id_legacy_cg"
)


def legacy_ids_from_glossary(snapshot: WorkbookSnapshot) -> tuple[object, ...]:
    """Return legacy IDs from the configured glossary table and header."""

    glossary = next(
        sheet for sheet in snapshot.sheets if sheet.name == GLOSSARY_SHEET_NAME
    )
    table = next(
        table
        for table in glossary.tables
        if table.name == GLOSSARY_TABLE_NAME
    )
    min_column, header_row, max_column, max_row = range_boundaries(
        table.reference
    )
    cells = {
        coordinate_to_tuple(cell.coordinate): cell.value
        for cell in glossary.cells
    }
    header_columns = {
        cells.get((header_row, column_number)): column_number
        for column_number in range(min_column, max_column + 1)
    }
    legacy_id_column = header_columns[LEGACY_ID_SOURCE_HEADER]

    return tuple(
        cells.get((row_number, legacy_id_column))
        for row_number in range(header_row + 1, max_row + 1)
    )


class ContaminantIdFormatTests(unittest.TestCase):
    def test_accepts_valid_identifiers(self) -> None:
        self.assertEqual(contaminant_id_number("RHC-001"), 1)
        self.assertEqual(contaminant_id_number("RHC-152"), 152)
        self.assertEqual(contaminant_id_number("RHC-999"), 999)

    def test_rejects_invalid_identifiers(self) -> None:
        invalid_values = (
            "RHC-000",
            "RHC-1",
            "RHC-0001",
            "rhc-001",
            " RHC-001",
            "RHC-001 ",
            1,
            None,
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    contaminant_id_number(value)

    def test_rejects_duplicate_identifiers(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate contaminant ID"):
            validate_contaminant_ids(["RHC-001", "RHC-001"])


class ContaminantIdAllocationTests(unittest.TestCase):
    def test_starts_at_one_when_none_have_been_issued(self) -> None:
        self.assertEqual(next_contaminant_id([]), "RHC-001")

    def test_uses_the_highest_issued_id_not_input_order_or_gaps(self) -> None:
        issued_ids = ["RHC-152", "RHC-001", "RHC-025"]

        self.assertEqual(next_contaminant_id(issued_ids), "RHC-153")

    def test_retired_ids_remain_reserved_when_in_the_registry(self) -> None:
        active_ids = ["RHC-001", "RHC-002"]
        retired_ids = ["RHC-003"]

        self.assertEqual(
            next_contaminant_id([*active_ids, *retired_ids]), "RHC-004"
        )

    def test_rejects_allocation_after_999(self) -> None:
        with self.assertRaisesRegex(ValueError, "range is exhausted"):
            next_contaminant_id(["RHC-999"])


class ContaminantIdBootstrapTests(unittest.TestCase):
    def test_maps_the_complete_initial_legacy_id_set(self) -> None:
        mappings = bootstrap_contaminant_ids(
            range(INITIAL_LEGACY_ID_MIN, INITIAL_LEGACY_ID_MAX + 1)
        )

        self.assertIsInstance(mappings, tuple)
        self.assertEqual(len(mappings), 152)
        self.assertEqual(mappings[0], BootstrapIdMapping(1, "RHC-001"))
        self.assertEqual(mappings[-1], BootstrapIdMapping(152, "RHC-152"))
        self.assertEqual(
            len({mapping.id_contaminant for mapping in mappings}),
            len(mappings),
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(mappings[0], "id_contaminant", "RHC-999")

    def test_is_deterministic_under_reordered_input_without_mutation(self) -> None:
        legacy_ids = list(
            range(INITIAL_LEGACY_ID_MAX, INITIAL_LEGACY_ID_MIN - 1, -1)
        )
        original_values = legacy_ids.copy()

        reordered_mappings = bootstrap_contaminant_ids(legacy_ids)
        ordered_mappings = bootstrap_contaminant_ids(
            range(INITIAL_LEGACY_ID_MIN, INITIAL_LEGACY_ID_MAX + 1)
        )

        self.assertEqual(reordered_mappings, ordered_mappings)
        self.assertEqual(legacy_ids, original_values)

    def test_rejects_non_integer_legacy_ids(self) -> None:
        invalid_values = (True, False, "1", 1.0, None, "")

        for value in invalid_values:
            with self.subTest(value=value):
                legacy_ids = list(
                    range(INITIAL_LEGACY_ID_MIN, INITIAL_LEGACY_ID_MAX + 1)
                )
                legacy_ids[0] = value

                with self.assertRaisesRegex(ValueError, "must be an integer"):
                    bootstrap_contaminant_ids(legacy_ids)

    def test_rejects_legacy_ids_outside_the_bootstrap_range(self) -> None:
        for value in (0, -1, 153, 999):
            with self.subTest(value=value):
                legacy_ids = list(
                    range(INITIAL_LEGACY_ID_MIN, INITIAL_LEGACY_ID_MAX + 1)
                )
                legacy_ids[-1] = value

                with self.assertRaisesRegex(ValueError, "between 1 and 152"):
                    bootstrap_contaminant_ids(legacy_ids)

    def test_rejects_duplicate_legacy_ids(self) -> None:
        legacy_ids = [
            *range(INITIAL_LEGACY_ID_MIN, INITIAL_LEGACY_ID_MAX + 1),
            INITIAL_LEGACY_ID_MIN,
        ]

        with self.assertRaisesRegex(ValueError, "duplicate legacy CG ID: 1"):
            bootstrap_contaminant_ids(legacy_ids)

    def test_rejects_an_incomplete_legacy_id_set(self) -> None:
        legacy_ids = range(INITIAL_LEGACY_ID_MIN, INITIAL_LEGACY_ID_MAX)

        with self.assertRaisesRegex(ValueError, "missing: 152"):
            bootstrap_contaminant_ids(legacy_ids)

    def test_real_glossary_bootstraps_without_modifying_the_workbook(
        self,
    ) -> None:
        original_bytes = INCOMING_GLOSSARY_WORKBOOK.read_bytes()

        snapshot = read_workbook(INCOMING_GLOSSARY_WORKBOOK)
        legacy_ids = legacy_ids_from_glossary(snapshot)
        mappings = bootstrap_contaminant_ids(legacy_ids)

        self.assertEqual(len(legacy_ids), 152)
        self.assertEqual(len(mappings), 152)
        self.assertEqual(mappings[0].id_contaminant, "RHC-001")
        self.assertEqual(mappings[-1].id_contaminant, "RHC-152")
        self.assertEqual(INCOMING_GLOSSARY_WORKBOOK.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
