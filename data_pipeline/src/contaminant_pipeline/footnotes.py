"""Validate footnote definitions and glossary footnote relationships."""

from collections.abc import Iterable
from dataclasses import dataclass
import re

from openpyxl.utils.cell import coordinate_to_tuple

from .config import FOOTNOTES_SHEET_NAME, GLOSSARY_SHEET_NAME
from .identifiers import contaminant_id_number
from .io_excel import WorkbookSnapshot
from .schemas import FOOTNOTE_HEADER_MAP


FOOTNOTE_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]*$")


@dataclass(frozen=True)
class FootnoteDefinition:
    """One reusable footnote definition."""

    footnote_id: str
    text: str


@dataclass(frozen=True)
class GlossaryFootnoteSource:
    """One glossary row's raw footnote cell and assigned stable ID."""

    id_contaminant: str
    source_row: int
    value: object
    formula: str | None = None


@dataclass(frozen=True)
class FootnoteUsage:
    """The ordered footnotes used by one glossary contaminant."""

    id_contaminant: str
    footnote_ids: tuple[str, ...]


@dataclass(frozen=True)
class FootnoteValidationIssue:
    """One definition or usage problem with optional source context."""

    message: str
    sheet_name: str
    source_row: int | None = None
    source_value: str | None = None


class FootnoteValidationError(ValueError):
    """Raised with every safely collectible footnote problem."""

    def __init__(self, issues: Iterable[FootnoteValidationIssue]) -> None:
        self.issues = tuple(issues)
        message = "; ".join(issue.message for issue in self.issues)
        super().__init__(message)


def _literal_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be nonblank text")
    if value != value.strip():
        raise ValueError(f"{field_name} must not have surrounding whitespace")
    return value


def validate_footnote_relationships(
    glossary_snapshot: WorkbookSnapshot,
    glossary_sources: Iterable[GlossaryFootnoteSource],
) -> tuple[tuple[FootnoteDefinition, ...], tuple[FootnoteUsage, ...]]:
    """Validate definitions and usages without reading or writing files."""

    sheets = tuple(
        sheet
        for sheet in glossary_snapshot.sheets
        if sheet.name == FOOTNOTES_SHEET_NAME
    )
    if len(sheets) != 1:
        raise FootnoteValidationError(
            (
                FootnoteValidationIssue(
                    f"expected exactly one {FOOTNOTES_SHEET_NAME!r} sheet; "
                    f"found {len(sheets)}",
                    FOOTNOTES_SHEET_NAME,
                ),
            )
        )
    sheet = sheets[0]
    cells = {
        coordinate_to_tuple(cell.coordinate): cell for cell in sheet.cells
    }
    expected_headers = tuple(FOOTNOTE_HEADER_MAP)
    headers = tuple(
        cells.get((1, column)).value if cells.get((1, column)) else None
        for column in (1, 2)
    )
    extra_headers = tuple(
        cell.value
        for (row, column), cell in cells.items()
        if row == 1 and column > 2
    )
    header_formulas = any(
        cell is not None and cell.formula is not None
        for cell in (cells.get((1, 1)), cells.get((1, 2)))
    )
    if headers != expected_headers or extra_headers or header_formulas:
        raise FootnoteValidationError(
            (
                FootnoteValidationIssue(
                    f"Footnotes headers must be exactly {expected_headers!r}",
                    FOOTNOTES_SHEET_NAME,
                ),
            )
        )

    issues: list[FootnoteValidationIssue] = []
    definitions: list[FootnoteDefinition] = []
    seen_definition_ids: set[str] = set()
    for row in range(2, sheet.max_row + 1):
        id_cell = cells.get((row, 1))
        text_cell = cells.get((row, 2))
        if id_cell is None and text_cell is None:
            continue
        raw_id = id_cell.value if id_cell else None
        raw_text = text_cell.value if text_cell else None
        try:
            if (id_cell and id_cell.formula) or (text_cell and text_cell.formula):
                raise ValueError("footnote definitions must be literal text")
            footnote_id = _literal_text(raw_id, "footnote ID")
            text = _literal_text(raw_text, "footnote text")
            if FOOTNOTE_ID_PATTERN.fullmatch(footnote_id) is None:
                raise ValueError(f"invalid footnote ID: {footnote_id!r}")
            if footnote_id in seen_definition_ids:
                raise ValueError(f"duplicate footnote ID: {footnote_id}")
        except ValueError as error:
            issues.append(
                FootnoteValidationIssue(
                    message=str(error),
                    sheet_name=FOOTNOTES_SHEET_NAME,
                    source_row=row,
                    source_value=repr(raw_id),
                )
            )
            continue

        seen_definition_ids.add(footnote_id)
        definitions.append(FootnoteDefinition(footnote_id, text))

    definition_ids = {definition.footnote_id for definition in definitions}
    definitions_are_valid = not issues
    usages: list[FootnoteUsage] = []
    seen_contaminant_ids: set[str] = set()
    for source in glossary_sources:
        if not isinstance(source, GlossaryFootnoteSource):
            raise ValueError(
                "glossary footnote sources must be GlossaryFootnoteSource records"
            )
        try:
            contaminant_id_number(source.id_contaminant)
            if source.id_contaminant in seen_contaminant_ids:
                raise ValueError(
                    f"duplicate glossary footnote source: {source.id_contaminant}"
                )
            if type(source.source_row) is not int or source.source_row <= 0:
                raise ValueError("footnote source row must be a positive integer")
            if source.formula is not None:
                raise ValueError("glossary footnote usage must be literal text")

            if source.value is None:
                footnote_ids: tuple[str, ...] = ()
            else:
                if not isinstance(source.value, str) or not source.value.strip():
                    raise ValueError(
                        "glossary footnote usage must be nonblank text or blank"
                    )
                raw_tokens = source.value.split(",")
                tokens = tuple(token.strip() for token in raw_tokens)
                if any(not token for token in tokens):
                    raise ValueError("glossary footnote usage has an empty token")
                if len(set(tokens)) != len(tokens):
                    raise ValueError(
                        "glossary footnote usage contains a duplicate ID"
                    )
                invalid_ids = tuple(
                    token
                    for token in tokens
                    if FOOTNOTE_ID_PATTERN.fullmatch(token) is None
                )
                if invalid_ids:
                    raise ValueError(
                        "invalid glossary footnote ID: "
                        + ", ".join(repr(value) for value in invalid_ids)
                    )
                unknown_ids = tuple(
                    token for token in tokens if token not in definition_ids
                )
                if definitions_are_valid and unknown_ids:
                    raise ValueError(
                        "unknown glossary footnote ID: "
                        + ", ".join(repr(value) for value in unknown_ids)
                    )
                footnote_ids = tokens
        except ValueError as error:
            issues.append(
                FootnoteValidationIssue(
                    message=str(error),
                    sheet_name=GLOSSARY_SHEET_NAME,
                    source_row=source.source_row
                    if type(source.source_row) is int and source.source_row > 0
                    else None,
                    source_value=repr(source.value),
                )
            )
            continue

        seen_contaminant_ids.add(source.id_contaminant)
        usages.append(FootnoteUsage(source.id_contaminant, footnote_ids))

    if issues:
        raise FootnoteValidationError(issues)

    return (
        tuple(sorted(definitions, key=lambda value: value.footnote_id)),
        tuple(sorted(usages, key=lambda value: value.id_contaminant)),
    )
