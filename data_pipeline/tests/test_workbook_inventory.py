from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import unittest

from contaminant_pipeline.config import (
    GLOSSARY_SHEET_NAME,
    GLOSSARY_TABLE_NAME,
    METADATA_SHEET_NAME,
    REFERENCES_SHEET_NAME,
)
from contaminant_pipeline.intake import (
    IncomingContractError,
    inventory_incoming_pair,
    read_incoming_pair,
)
from contaminant_pipeline.io_excel import CellSnapshot, TableSnapshot
from contaminant_pipeline.paths import (
    INCOMING_DIR,
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    MANIFEST_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    PUBLIC_DATA_DIR,
    RAW_SNAPSHOTS_DIR,
    REFERENCE_CROSSWALK_PATH,
    CONTAMINANT_REGISTRY_PATH,
)
from fixture_paths import SYNTHETIC_GLOSSARY_WORKBOOK


FIXTURE_INCOMING_DIR = SYNTHETIC_GLOSSARY_WORKBOOK.parent
GENERATED_ROOTS = (
    MANIFEST_DIR,
    RAW_SNAPSHOTS_DIR,
    PROCESSED_DIR,
    OUTPUT_DIR,
    PUBLIC_DATA_DIR,
)


def _worksheet(workbook_inventory, name):
    return next(sheet for sheet in workbook_inventory.worksheets if sheet.name == name)


def _replace_sheet(snapshot, name, transform):
    return replace(
        snapshot,
        sheets=tuple(
            transform(sheet) if sheet.name == name else sheet
            for sheet in snapshot.sheets
        ),
    )


def _replace_cell(sheet, coordinate, **changes):
    return replace(
        sheet,
        cells=tuple(
            replace(cell, **changes) if cell.coordinate == coordinate else cell
            for cell in sheet.cells
        ),
    )


def _tree_state():
    state = []
    for root in GENERATED_ROOTS:
        state.append((root, root.exists()))
        if root.exists():
            for path in sorted(root.rglob("*")):
                state.append(
                    (path, path.is_dir(), path.read_bytes() if path.is_file() else None)
                )
    return tuple(state)


class WorkbookInventoryTests(unittest.TestCase):
    def test_inventories_the_complete_synthetic_pair(self) -> None:
        pair = read_incoming_pair(FIXTURE_INCOMING_DIR)

        result = inventory_incoming_pair(pair)

        self.assertIs(result.incoming_pair, pair)
        self.assertEqual(result.data_release_id, "20000115-r2")
        glossary = result.glossary_inventory
        references = result.references_inventory
        self.assertEqual(
            [sheet.name for sheet in glossary.worksheets],
            ["Introduction", "Glossary", "Footnotes", "Metadata"],
        )
        self.assertEqual(
            [sheet.name for sheet in references.worksheets],
            ["Sheet1", "Metadata"],
        )
        self.assertEqual(glossary.size_bytes, len(SYNTHETIC_GLOSSARY_WORKBOOK.read_bytes()))
        self.assertEqual(
            glossary.sha256,
            sha256(SYNTHETIC_GLOSSARY_WORKBOOK.read_bytes()).hexdigest(),
        )
        glossary_sheet = _worksheet(glossary, GLOSSARY_SHEET_NAME)
        glossary_table = glossary_sheet.tables[0]
        self.assertEqual(glossary_table.name, GLOSSARY_TABLE_NAME)
        self.assertEqual(glossary_table.reference, "A1:AX4")
        self.assertEqual(glossary_table.header_row, 1)
        self.assertEqual(glossary_table.declared_data_row_count, 3)
        self.assertEqual(glossary_table.populated_data_row_count, 3)
        self.assertEqual(glossary_sheet.logical_data_row_count, 3)
        self.assertEqual(
            _worksheet(glossary, "Footnotes").logical_data_row_count,
            2,
        )
        self.assertEqual(
            _worksheet(glossary, METADATA_SHEET_NAME).logical_data_row_count,
            3,
        )
        self.assertEqual(
            _worksheet(references, REFERENCES_SHEET_NAME).logical_data_row_count,
            4,
        )
        self.assertEqual(
            _worksheet(references, METADATA_SHEET_NAME).logical_data_row_count,
            3,
        )
        self.assertEqual(glossary.formula_count, 0)
        self.assertEqual(references.formula_count, 0)
        self.assertEqual(glossary.warning_count, 0)
        self.assertEqual(references.warning_count, 0)
        self.assertEqual(
            glossary.populated_cell_count,
            sum(sheet.populated_cell_count for sheet in glossary.worksheets),
        )
        with self.assertRaises(FrozenInstanceError):
            result.data_release_id = "changed"

    def test_records_and_numerically_orders_formula_occurrences(self) -> None:
        pair = read_incoming_pair(FIXTURE_INCOMING_DIR)

        def add_formulas(sheet):
            cells = tuple(
                replace(cell, value=3, formula="=1+2")
                if cell.coordinate == "A2"
                else cell
                for cell in sheet.cells
            )
            return replace(
                sheet,
                max_row=10,
                cells=(CellSnapshot("A10", None, "=5+5"), *reversed(cells)),
            )

        glossary = _replace_sheet(
            pair.glossary_snapshot,
            "Introduction",
            add_formulas,
        )
        changed_pair = replace(pair, glossary_snapshot=glossary)

        result = inventory_incoming_pair(changed_pair)

        formulas = _worksheet(
            result.glossary_inventory,
            "Introduction",
        ).formulas
        self.assertEqual([formula.coordinate for formula in formulas], ["A2", "A10"])
        self.assertEqual([formula.definition for formula in formulas], ["=1+2", "=5+5"])
        self.assertEqual(
            [formula.has_cached_value for formula in formulas],
            [True, False],
        )
        self.assertEqual(result.glossary_inventory.formula_count, 2)

    def test_inventory_is_deterministic_for_shuffled_cells_and_tables(self) -> None:
        pair = read_incoming_pair(FIXTURE_INCOMING_DIR)
        first = inventory_incoming_pair(pair)

        def shuffle(snapshot):
            return replace(
                snapshot,
                sheets=tuple(
                    replace(
                        sheet,
                        cells=tuple(reversed(sheet.cells)),
                        tables=tuple(reversed(sheet.tables)),
                    )
                    for sheet in snapshot.sheets
                ),
            )

        shuffled = replace(
            pair,
            glossary_snapshot=shuffle(pair.glossary_snapshot),
            references_snapshot=shuffle(pair.references_snapshot),
        )

        second = inventory_incoming_pair(shuffled)

        self.assertEqual(first.glossary_inventory, second.glossary_inventory)
        self.assertEqual(first.references_inventory, second.references_inventory)


class WorkbookInventoryFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pair = read_incoming_pair(FIXTURE_INCOMING_DIR)
        self.generated_before = _tree_state()

    def tearDown(self) -> None:
        self.assertEqual(_tree_state(), self.generated_before)

    def test_rejects_missing_or_invalid_source_fingerprints(self) -> None:
        cases = (
            (replace(self.pair.glossary_snapshot, size_bytes=None), "byte size"),
            (replace(self.pair.glossary_snapshot, size_bytes=0), "byte size"),
            (replace(self.pair.glossary_snapshot, sha256=None), "SHA-256"),
            (replace(self.pair.glossary_snapshot, sha256="ABC"), "SHA-256"),
        )
        for snapshot, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(IncomingContractError, message):
                    inventory_incoming_pair(
                        replace(self.pair, glossary_snapshot=snapshot)
                    )

    def test_rejects_missing_duplicate_and_unknown_sheets(self) -> None:
        glossary = self.pair.glossary_snapshot
        cases = (
            (replace(glossary, sheets=glossary.sheets[:-1]), "missing sheets"),
            (replace(glossary, sheets=(*glossary.sheets, glossary.sheets[0])), "duplicate sheets"),
            (
                replace(
                    glossary,
                    sheets=(*glossary.sheets, replace(glossary.sheets[0], name="Unknown")),
                ),
                "unknown sheets",
            ),
        )
        for snapshot, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(IncomingContractError, message):
                    inventory_incoming_pair(
                        replace(self.pair, glossary_snapshot=snapshot)
                    )

    def test_rejects_missing_duplicate_and_unknown_tables(self) -> None:
        glossary = self.pair.glossary_snapshot
        sheet = next(item for item in glossary.sheets if item.name == GLOSSARY_SHEET_NAME)
        table = sheet.tables[0]
        cases = (
            (replace(sheet, tables=()), "expected tables"),
            (replace(sheet, tables=(table, table)), "duplicate table"),
            (replace(sheet, tables=(replace(table, name="Unknown"),)), "expected tables"),
        )
        for changed_sheet, message in cases:
            with self.subTest(message=message):
                snapshot = _replace_sheet(
                    glossary,
                    GLOSSARY_SHEET_NAME,
                    lambda unused, value=changed_sheet: value,
                )
                with self.assertRaisesRegex(IncomingContractError, message):
                    inventory_incoming_pair(
                        replace(self.pair, glossary_snapshot=snapshot)
                    )

    def test_rejects_malformed_and_impossible_table_ranges(self) -> None:
        glossary = self.pair.glossary_snapshot
        cases = (("not-a-range", "malformed range"), ("A1:B1", "impossible range"))
        for reference, message in cases:
            with self.subTest(reference=reference):
                snapshot = _replace_sheet(
                    glossary,
                    GLOSSARY_SHEET_NAME,
                    lambda sheet: replace(
                        sheet,
                        tables=(TableSnapshot(GLOSSARY_TABLE_NAME, reference),),
                    ),
                )
                with self.assertRaisesRegex(IncomingContractError, message):
                    inventory_incoming_pair(
                        replace(self.pair, glossary_snapshot=snapshot)
                    )

    def test_rejects_invalid_header_structures(self) -> None:
        glossary = self.pair.glossary_snapshot
        glossary_sheet = next(
            sheet for sheet in glossary.sheets if sheet.name == GLOSSARY_SHEET_NAME
        )
        first_header = next(
            cell.value for cell in glossary_sheet.cells if cell.coordinate == "A1"
        )
        cases = (
            (None, None, "nonblank literal text"),
            (1, None, "nonblank literal text"),
            (first_header, None, "duplicate header"),
            ("Calculated", "=1+1", "nonblank literal text"),
        )
        for value, formula, message in cases:
            with self.subTest(value=value, formula=formula):
                snapshot = _replace_sheet(
                    glossary,
                    GLOSSARY_SHEET_NAME,
                    lambda sheet: _replace_cell(
                        sheet,
                        "B1",
                        value=value,
                        formula=formula,
                    ),
                )
                with self.assertRaisesRegex(IncomingContractError, message):
                    inventory_incoming_pair(
                        replace(self.pair, glossary_snapshot=snapshot)
                    )

    def test_rejects_empty_blank_or_out_of_range_tabular_content(self) -> None:
        glossary = self.pair.glossary_snapshot
        references = self.pair.references_snapshot
        empty_references = _replace_sheet(
            references,
            REFERENCES_SHEET_NAME,
            lambda sheet: replace(
                sheet,
                cells=tuple(cell for cell in sheet.cells if cell.coordinate.endswith("1")),
            ),
        )
        with self.assertRaisesRegex(IncomingContractError, "no populated data rows"):
            inventory_incoming_pair(
                replace(self.pair, references_snapshot=empty_references)
            )

        blank_row = _replace_sheet(
            glossary,
            GLOSSARY_SHEET_NAME,
            lambda sheet: replace(
                sheet,
                cells=tuple(
                    cell
                    for cell in sheet.cells
                    if not cell.coordinate.endswith("2")
                ),
            ),
        )
        with self.assertRaisesRegex(IncomingContractError, "blank declared data row 2"):
            inventory_incoming_pair(replace(self.pair, glossary_snapshot=blank_row))

        outside = _replace_sheet(
            glossary,
            GLOSSARY_SHEET_NAME,
            lambda sheet: replace(
                sheet,
                max_column=51,
                cells=(*sheet.cells, CellSnapshot("AY2", "unexpected", None)),
            ),
        )
        with self.assertRaisesRegex(IncomingContractError, "outside required table"):
            inventory_incoming_pair(replace(self.pair, glossary_snapshot=outside))


class AuthoritativeWorkbookInventoryTests(unittest.TestCase):
    def test_inventories_current_files_without_modifying_or_publishing(self) -> None:
        protected_paths = (
            INCOMING_GLOSSARY_WORKBOOK,
            INCOMING_REFERENCES_WORKBOOK,
            CONTAMINANT_REGISTRY_PATH,
            REFERENCE_CROSSWALK_PATH,
        )
        protected_before = {
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in protected_paths
        }
        generated_before = _tree_state()

        pair = read_incoming_pair(INCOMING_DIR)
        result = inventory_incoming_pair(pair)

        for snapshot, inventory in (
            (pair.glossary_snapshot, result.glossary_inventory),
            (pair.references_snapshot, result.references_inventory),
        ):
            source_bytes = snapshot.path.read_bytes()
            self.assertEqual(inventory.size_bytes, len(source_bytes))
            self.assertEqual(inventory.sha256, sha256(source_bytes).hexdigest())
        glossary_sheet = _worksheet(
            result.glossary_inventory,
            GLOSSARY_SHEET_NAME,
        )
        references_sheet = _worksheet(
            result.references_inventory,
            REFERENCES_SHEET_NAME,
        )
        self.assertLess(
            glossary_sheet.logical_data_row_count,
            glossary_sheet.max_row,
        )
        self.assertLess(
            references_sheet.logical_data_row_count,
            references_sheet.max_row,
        )
        self.assertGreater(result.glossary_inventory.formula_count, 0)

        invalid_pair = replace(
            pair,
            glossary_snapshot=replace(pair.glossary_snapshot, sha256="invalid"),
        )
        with self.assertRaises(IncomingContractError):
            inventory_incoming_pair(invalid_pair)

        self.assertEqual(
            {
                path: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in protected_paths
            },
            protected_before,
        )
        self.assertEqual(_tree_state(), generated_before)


if __name__ == "__main__":
    unittest.main()
