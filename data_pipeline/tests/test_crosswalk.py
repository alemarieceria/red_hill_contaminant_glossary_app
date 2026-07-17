from dataclasses import FrozenInstanceError
import unittest

from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

from contaminant_pipeline.config import (
    GLOSSARY_SHEET_NAME,
    GLOSSARY_TABLE_NAME,
    REFERENCES_SHEET_NAME,
)
from contaminant_pipeline.crosswalk import (
    REFERENCE_NAME_OVERRIDES,
    GlossaryIdentity,
    ReferenceCrosswalkEntry,
    ReferenceResolutionMethod,
    build_reference_crosswalk,
)
from contaminant_pipeline.identifiers import bootstrap_contaminant_ids
from contaminant_pipeline.io_excel import WorkbookSnapshot, read_workbook
from contaminant_pipeline.paths import (
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
)
from contaminant_pipeline.schemas import (
    GLOSSARY_HEADER_MAP,
    REFERENCE_HEADER_MAP,
)


GLOSSARY_NAME_HEADER = next(
    header
    for header, field in GLOSSARY_HEADER_MAP.items()
    if field == "id_name"
)
LEGACY_ID_HEADER = next(
    header
    for header, field in GLOSSARY_HEADER_MAP.items()
    if field == "id_legacy_cg"
)
REFERENCE_NAME_HEADER = next(
    header
    for header, field in REFERENCE_HEADER_MAP.items()
    if field == "refs_review_name"
)


def _sheet_cells(snapshot: WorkbookSnapshot, sheet_name: str) -> dict:
    sheet = next(sheet for sheet in snapshot.sheets if sheet.name == sheet_name)
    return {
        coordinate_to_tuple(cell.coordinate): cell.value for cell in sheet.cells
    }


def _real_glossary_identities(
    snapshot: WorkbookSnapshot,
) -> tuple[GlossaryIdentity, ...]:
    sheet = next(
        sheet for sheet in snapshot.sheets if sheet.name == GLOSSARY_SHEET_NAME
    )
    table = next(
        table for table in sheet.tables if table.name == GLOSSARY_TABLE_NAME
    )
    min_column, header_row, max_column, max_row = range_boundaries(
        table.reference
    )
    cells = _sheet_cells(snapshot, GLOSSARY_SHEET_NAME)
    columns = {
        cells.get((header_row, column)): column
        for column in range(min_column, max_column + 1)
    }
    rows = tuple(
        (
            cells.get((row, columns[GLOSSARY_NAME_HEADER])),
            cells.get((row, columns[LEGACY_ID_HEADER])),
        )
        for row in range(header_row + 1, max_row + 1)
    )
    stable_ids = {
        mapping.id_legacy_cg: mapping.id_contaminant
        for mapping in bootstrap_contaminant_ids(
            legacy_id for _, legacy_id in rows
        )
    }
    return tuple(
        GlossaryIdentity(
            id_name=name,
            id_contaminant=stable_ids[legacy_id],
        )
        for name, legacy_id in rows
    )


def _real_reference_labels(snapshot: WorkbookSnapshot) -> tuple[object, ...]:
    sheet = next(
        sheet for sheet in snapshot.sheets if sheet.name == REFERENCES_SHEET_NAME
    )
    cells = _sheet_cells(snapshot, REFERENCES_SHEET_NAME)
    name_column = next(
        column
        for (row, column), value in cells.items()
        if row == 1 and value == REFERENCE_NAME_HEADER
    )
    return tuple(
        cells[(row, name_column)]
        for row in range(2, sheet.max_row + 1)
        if (row, name_column) in cells
    )


class ReferenceCrosswalkBehaviorTests(unittest.TestCase):
    def test_resolves_exact_and_override_labels_deterministically(self) -> None:
        identities = [
            GlossaryIdentity("Beta", "RHC-002"),
            GlossaryIdentity("Alpha", "RHC-001"),
        ]
        labels = ["Beta variant", "Alpha", "Alpha"]
        overrides = {"Beta variant": "RHC-002"}
        original_identities = identities.copy()
        original_labels = labels.copy()
        original_overrides = overrides.copy()

        entries = build_reference_crosswalk(identities, labels, overrides)

        self.assertEqual(
            entries,
            (
                ReferenceCrosswalkEntry(
                    "Alpha", "RHC-001", ReferenceResolutionMethod.EXACT
                ),
                ReferenceCrosswalkEntry(
                    "Beta variant",
                    "RHC-002",
                    ReferenceResolutionMethod.OVERRIDE,
                ),
            ),
        )
        self.assertIsInstance(entries, tuple)
        self.assertEqual(identities, original_identities)
        self.assertEqual(labels, original_labels)
        self.assertEqual(overrides, original_overrides)

    def test_records_and_default_overrides_are_immutable(self) -> None:
        identity = GlossaryIdentity("Alpha", "RHC-001")
        entry = ReferenceCrosswalkEntry(
            "Alpha", "RHC-001", ReferenceResolutionMethod.EXACT
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(identity, "id_name", "Beta")
        with self.assertRaises(FrozenInstanceError):
            setattr(entry, "id_contaminant", "RHC-002")
        with self.assertRaises(TypeError):
            REFERENCE_NAME_OVERRIDES["new label"] = "RHC-001"

    def test_reports_every_unresolved_variant_without_normalizing(self) -> None:
        identities = [GlossaryIdentity("Alpha-beta", "RHC-001")]
        variants = ["alpha-beta", "Alpha beta", "Alpha-beto", " Alpha-beta"]

        with self.assertRaises(ValueError) as context:
            build_reference_crosswalk(identities, variants, {})

        message = str(context.exception)
        self.assertIn("unresolved reference labels", message)
        for variant in variants:
            self.assertIn(repr(variant), message)


class ReferenceCrosswalkValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identities = [GlossaryIdentity("Alpha", "RHC-001")]

    def test_rejects_invalid_glossary_records_names_and_ids(self) -> None:
        cases = (
            ([object()], "GlossaryIdentity"),
            ([GlossaryIdentity(" ", "RHC-001")], "nonblank text"),
            ([GlossaryIdentity("Alpha", "rhc-001")], "RHC-NNN"),
        )

        for identities, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                with self.assertRaisesRegex(ValueError, expected_message):
                    build_reference_crosswalk(identities, ["Alpha"], {})

    def test_rejects_duplicate_glossary_ids(self) -> None:
        identities = [
            GlossaryIdentity("Alpha", "RHC-001"),
            GlossaryIdentity("Beta", "RHC-001"),
        ]

        with self.assertRaisesRegex(ValueError, "duplicate contaminant ID"):
            build_reference_crosswalk(identities, ["Alpha"], {})

    def test_reports_all_ambiguous_glossary_names(self) -> None:
        identities = [
            GlossaryIdentity("Beta", "RHC-001"),
            GlossaryIdentity("Alpha", "RHC-002"),
            GlossaryIdentity("Beta", "RHC-003"),
            GlossaryIdentity("Alpha", "RHC-004"),
        ]

        with self.assertRaises(ValueError) as context:
            build_reference_crosswalk(identities, ["Alpha"], {})

        self.assertEqual(
            str(context.exception),
            "ambiguous glossary names: 'Alpha', 'Beta'",
        )

    def test_rejects_blank_or_nontext_reference_labels(self) -> None:
        for label in ("", " ", None, 1):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "nonblank text"):
                    build_reference_crosswalk(self.identities, [label], {})

    def test_rejects_invalid_override_labels(self) -> None:
        for label in ("", " ", None):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "override label"):
                    build_reference_crosswalk(
                        self.identities, ["Variant"], {label: "RHC-001"}
                    )

    def test_rejects_invalid_or_absent_override_targets(self) -> None:
        cases = (
            ("bad-id", "RHC-NNN"),
            ("RHC-002", "absent from glossary"),
        )

        for target, expected_message in cases:
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, expected_message):
                    build_reference_crosswalk(
                        self.identities,
                        ["Variant"],
                        {"Variant": target},
                    )

    def test_rejects_an_override_for_an_exact_match(self) -> None:
        with self.assertRaisesRegex(ValueError, "replaces an exact match"):
            build_reference_crosswalk(
                self.identities, ["Alpha"], {"Alpha": "RHC-001"}
            )

    def test_rejects_an_unused_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "unused override label"):
            build_reference_crosswalk(
                self.identities, ["Alpha"], {"Variant": "RHC-001"}
            )


class RealWorkbookCrosswalkTests(unittest.TestCase):
    def test_current_reference_labels_all_resolve_without_file_changes(
        self,
    ) -> None:
        glossary_bytes = INCOMING_GLOSSARY_WORKBOOK.read_bytes()
        references_bytes = INCOMING_REFERENCES_WORKBOOK.read_bytes()

        glossary = read_workbook(INCOMING_GLOSSARY_WORKBOOK)
        references = read_workbook(INCOMING_REFERENCES_WORKBOOK)
        identities = _real_glossary_identities(glossary)
        labels = _real_reference_labels(references)
        entries = build_reference_crosswalk(
            identities, labels, REFERENCE_NAME_OVERRIDES
        )
        entries_by_label = {entry.refs_review_name: entry for entry in entries}

        self.assertEqual(len(identities), 152)
        self.assertEqual(len(labels), 406)
        self.assertEqual(len(entries), 133)
        self.assertEqual(
            sum(
                entry.resolution_method is ReferenceResolutionMethod.EXACT
                for entry in entries
            ),
            112,
        )
        self.assertEqual(
            sum(
                entry.resolution_method is ReferenceResolutionMethod.OVERRIDE
                for entry in entries
            ),
            21,
        )
        self.assertEqual(
            sum(
                entries_by_label[label].resolution_method
                is ReferenceResolutionMethod.EXACT
                for label in labels
            ),
            343,
        )
        self.assertEqual(
            sum(
                entries_by_label[label].resolution_method
                is ReferenceResolutionMethod.OVERRIDE
                for label in labels
            ),
            63,
        )
        self.assertEqual(
            INCOMING_GLOSSARY_WORKBOOK.read_bytes(), glossary_bytes
        )
        self.assertEqual(
            INCOMING_REFERENCES_WORKBOOK.read_bytes(), references_bytes
        )


if __name__ == "__main__":
    unittest.main()
