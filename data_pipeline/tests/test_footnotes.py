from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from contaminant_pipeline.config import FOOTNOTES_SHEET_NAME
from contaminant_pipeline.footnotes import (
    FootnoteDefinition,
    FootnoteUsage,
    FootnoteValidationError,
    GlossaryFootnoteSource,
    validate_footnote_relationships,
)
from contaminant_pipeline.io_excel import (
    CellSnapshot,
    WorkbookSnapshot,
    WorksheetSnapshot,
)


def footnote_snapshot(
    rows=(("A", "Alpha note"), ("D", "Pesticide note")),
    headers=("id", "text"),
    formula_coordinate=None,
    sheet_name=FOOTNOTES_SHEET_NAME,
    extra_header=None,
) -> WorkbookSnapshot:
    cells = []
    for row_number, values in enumerate((headers, *rows), start=1):
        for column_number, value in enumerate(values, start=1):
            if value is None:
                continue
            coordinate = f"{'AB'[column_number - 1]}{row_number}"
            cells.append(
                CellSnapshot(
                    coordinate,
                    value,
                    "=\"computed\"" if coordinate == formula_coordinate else None,
                )
            )
    if extra_header is not None:
        cells.append(CellSnapshot("C1", extra_header, None))
    sheet = WorksheetSnapshot(
        name=sheet_name,
        max_row=len(rows) + 1,
        max_column=3 if extra_header is not None else 2,
        tables=(),
        cells=tuple(cells),
    )
    return WorkbookSnapshot(Path("glossary.xlsx"), (sheet,), ())


def source(
    contaminant_id="RHC-001",
    row=2,
    value=None,
    formula=None,
) -> GlossaryFootnoteSource:
    return GlossaryFootnoteSource(contaminant_id, row, value, formula)


class FootnoteRelationshipSuccessTests(unittest.TestCase):
    def test_validates_blank_single_and_multiple_ordered_usages(self) -> None:
        sources = [
            source("RHC-003", 4, "A, D"),
            source("RHC-001", 2, None),
            source("RHC-002", 3, "D"),
        ]
        original_sources = sources.copy()

        definitions, usages = validate_footnote_relationships(
            footnote_snapshot(), sources
        )

        self.assertEqual(
            definitions,
            (
                FootnoteDefinition("A", "Alpha note"),
                FootnoteDefinition("D", "Pesticide note"),
            ),
        )
        self.assertEqual(
            usages,
            (
                FootnoteUsage("RHC-001", ()),
                FootnoteUsage("RHC-002", ("D",)),
                FootnoteUsage("RHC-003", ("A", "D")),
            ),
        )
        self.assertEqual(sources, original_sources)
        with self.assertRaises(FrozenInstanceError):
            setattr(definitions[0], "text", "Changed")

    def test_allows_multiple_contaminants_to_share_a_definition(self) -> None:
        _, usages = validate_footnote_relationships(
            footnote_snapshot(),
            [source("RHC-001", 2, "A"), source("RHC-002", 3, "A")],
        )

        self.assertEqual(
            tuple(usage.footnote_ids for usage in usages), (("A",), ("A",))
        )


class FootnoteRelationshipFailureTests(unittest.TestCase):
    def assert_footnote_error(self, snapshot, sources, message) -> None:
        with self.assertRaises(FootnoteValidationError) as context:
            validate_footnote_relationships(snapshot, sources)
        self.assertIn(message, str(context.exception))
        self.assertGreaterEqual(len(context.exception.issues), 1)

    def test_rejects_missing_wrong_or_malformed_headers(self) -> None:
        cases = (
            (
                WorkbookSnapshot(Path("x.xlsx"), (), ()),
                "exactly one 'Footnotes'",
            ),
            (footnote_snapshot(sheet_name="Other"), "exactly one 'Footnotes'"),
            (footnote_snapshot(headers=("text", "id")), "headers must be exactly"),
            (footnote_snapshot(extra_header="other"), "headers must be exactly"),
            (
                footnote_snapshot(formula_coordinate="A1"),
                "headers must be exactly",
            ),
        )

        for snapshot, message in cases:
            with self.subTest(message=message):
                self.assert_footnote_error(snapshot, [], message)

    def test_rejects_invalid_definitions(self) -> None:
        cases = (
            (((None, "text"),), None, "footnote ID must be nonblank"),
            (((1, "text"),), None, "footnote ID must be nonblank"),
            ((("a", "text"),), None, "invalid footnote ID"),
            ((("A", None),), None, "footnote text must be nonblank"),
            ((("A", 1),), None, "footnote text must be nonblank"),
            ((("A", " text"),), None, "surrounding whitespace"),
            ((("A", "one"), ("A", "two")), None, "duplicate footnote ID"),
            ((("A", "text"),), "B2", "literal text"),
        )

        for rows, formula, message in cases:
            with self.subTest(message=message):
                self.assert_footnote_error(
                    footnote_snapshot(rows=rows, formula_coordinate=formula),
                    [],
                    message,
                )

    def test_rejects_invalid_usages_with_source_context(self) -> None:
        cases = (
            (1, None, "nonblank text or blank"),
            ("", None, "nonblank text or blank"),
            ("A", "=A1", "literal text"),
            ("A,,D", None, "empty token"),
            ("A,A", None, "duplicate ID"),
            ("a", None, "invalid glossary footnote ID"),
            ("A;D", None, "invalid glossary footnote ID"),
            ("Z", None, "unknown glossary footnote ID"),
        )

        for value, formula, message in cases:
            with self.subTest(value=value, formula=formula):
                with self.assertRaises(FootnoteValidationError) as context:
                    validate_footnote_relationships(
                        footnote_snapshot(),
                        [source(row=19, value=value, formula=formula)],
                    )
                issue = context.exception.issues[-1]
                self.assertIn(message, issue.message)
                self.assertEqual(issue.sheet_name, "Glossary")
                self.assertEqual(issue.source_row, 19)

    def test_collects_multiple_usage_errors(self) -> None:
        with self.assertRaises(FootnoteValidationError) as context:
            validate_footnote_relationships(
                footnote_snapshot(),
                [source("RHC-001", 2, "Z"), source("RHC-002", 3, "A,A")],
            )

        self.assertEqual(len(context.exception.issues), 2)


if __name__ == "__main__":
    unittest.main()
