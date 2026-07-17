"""Orchestrate the read-only Phase 0B bootstrap validation."""

from collections.abc import Mapping
from dataclasses import dataclass

from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

from .bootstrap_report import (
    BootstrapFinding,
    BootstrapFindingCategory,
    BootstrapFindingSeverity,
    BootstrapReportCounts,
    BootstrapReportStatus,
    BootstrapValidationReport,
    build_bootstrap_report,
    format_bootstrap_report,
)
from .config import (
    GLOSSARY_SHEET_NAME,
    GLOSSARY_TABLE_NAME,
    REFERENCES_SHEET_NAME,
)
from .crosswalk import (
    GlossaryIdentity,
    ReferenceCrosswalkEntry,
    ReferenceResolutionMethod,
    build_reference_crosswalk,
)
from .footnotes import (
    FootnoteDefinition,
    FootnoteUsage,
    FootnoteValidationError,
    GlossaryFootnoteSource,
    validate_footnote_relationships,
)
from .identifiers import BootstrapIdMapping, bootstrap_contaminant_ids
from .io_excel import WorkbookSnapshot
from .metadata import (
    WorkbookCompatibility,
    extract_workbook_metadata,
    validate_workbook_compatibility,
)
from .schemas import GLOSSARY_HEADER_MAP, REFERENCE_HEADER_MAP


@dataclass(frozen=True)
class _GlossarySourceRow:
    source_row: int
    id_name: object
    id_legacy_cg: object
    footnote_value: object
    footnote_formula: str | None


@dataclass(frozen=True)
class _ReferenceSourceRow:
    source_row: int
    review_label: object
    review_label_formula: str | None


@dataclass(frozen=True)
class ValidatedBootstrap:
    """Complete in-memory relationships from a passing bootstrap run."""

    report: BootstrapValidationReport
    compatibility: WorkbookCompatibility
    glossary_identities: tuple[GlossaryIdentity, ...]
    id_mappings: tuple[BootstrapIdMapping, ...]
    reference_crosswalk: tuple[ReferenceCrosswalkEntry, ...]
    footnote_definitions: tuple[FootnoteDefinition, ...]
    footnote_usages: tuple[FootnoteUsage, ...]


class BootstrapValidationError(ValueError):
    """Raised when bootstrap validation produces a failed report."""

    def __init__(self, report: BootstrapValidationReport) -> None:
        self.report = report
        super().__init__(format_bootstrap_report(report).rstrip())


def _source_header(header_map: Mapping[str, str], canonical_name: str) -> str:
    return next(
        header
        for header, mapped_name in header_map.items()
        if mapped_name == canonical_name
    )


def _extract_glossary_rows(
    snapshot: WorkbookSnapshot,
) -> tuple[_GlossarySourceRow, ...]:
    sheets = tuple(
        sheet for sheet in snapshot.sheets if sheet.name == GLOSSARY_SHEET_NAME
    )
    if len(sheets) != 1:
        raise ValueError(
            f"expected exactly one {GLOSSARY_SHEET_NAME!r} sheet; "
            f"found {len(sheets)}"
        )
    sheet = sheets[0]
    tables = tuple(
        table for table in sheet.tables if table.name == GLOSSARY_TABLE_NAME
    )
    if len(tables) != 1:
        raise ValueError(
            f"expected exactly one {GLOSSARY_TABLE_NAME!r} table; "
            f"found {len(tables)}"
        )
    try:
        min_column, header_row, max_column, max_row = range_boundaries(
            tables[0].reference
        )
    except ValueError as error:
        raise ValueError("malformed glossary table range") from error

    cells = {
        coordinate_to_tuple(cell.coordinate): cell for cell in sheet.cells
    }
    header_columns: dict[object, int] = {}
    duplicate_headers: set[object] = set()
    for column in range(min_column, max_column + 1):
        cell = cells.get((header_row, column))
        header = cell.value if cell else None
        if header in header_columns:
            duplicate_headers.add(header)
        else:
            header_columns[header] = column
    if duplicate_headers:
        raise ValueError("duplicate glossary source headers")

    name_header = _source_header(GLOSSARY_HEADER_MAP, "id_name")
    legacy_header = _source_header(GLOSSARY_HEADER_MAP, "id_legacy_cg")
    footnote_header = _source_header(
        GLOSSARY_HEADER_MAP, "source_notes_footnote_ids"
    )
    required_headers = (name_header, legacy_header, footnote_header)
    missing = tuple(header for header in required_headers if header not in header_columns)
    if missing:
        raise ValueError(
            "missing glossary source headers: "
            + ", ".join(repr(header) for header in missing)
        )

    rows = []
    for row in range(header_row + 1, max_row + 1):
        name_cell = cells.get((row, header_columns[name_header]))
        legacy_cell = cells.get((row, header_columns[legacy_header]))
        footnote_cell = cells.get((row, header_columns[footnote_header]))
        rows.append(
            _GlossarySourceRow(
                source_row=row,
                id_name=name_cell.value if name_cell else None,
                id_legacy_cg=legacy_cell.value if legacy_cell else None,
                footnote_value=footnote_cell.value if footnote_cell else None,
                footnote_formula=footnote_cell.formula if footnote_cell else None,
            )
        )
    return tuple(rows)


def _extract_reference_rows(
    snapshot: WorkbookSnapshot,
) -> tuple[_ReferenceSourceRow, ...]:
    sheets = tuple(
        sheet for sheet in snapshot.sheets if sheet.name == REFERENCES_SHEET_NAME
    )
    if len(sheets) != 1:
        raise ValueError(
            f"expected exactly one {REFERENCES_SHEET_NAME!r} sheet; "
            f"found {len(sheets)}"
        )
    sheet = sheets[0]
    cells = {
        coordinate_to_tuple(cell.coordinate): cell for cell in sheet.cells
    }
    header_columns: dict[object, int] = {}
    for (row, column), cell in cells.items():
        if row != 1 or cell.value not in REFERENCE_HEADER_MAP:
            continue
        if cell.value in header_columns:
            raise ValueError(f"duplicate reference header: {cell.value!r}")
        header_columns[cell.value] = column
    missing = tuple(
        header for header in REFERENCE_HEADER_MAP if header not in header_columns
    )
    if missing:
        raise ValueError(
            "missing reference source headers: "
            + ", ".join(repr(header) for header in missing)
        )

    review_header = _source_header(REFERENCE_HEADER_MAP, "refs_review_name")
    mapped_columns = tuple(header_columns.values())
    rows = []
    for row in range(2, sheet.max_row + 1):
        if not any((row, column) in cells for column in mapped_columns):
            continue
        review_cell = cells.get((row, header_columns[review_header]))
        rows.append(
            _ReferenceSourceRow(
                source_row=row,
                review_label=review_cell.value if review_cell else None,
                review_label_formula=review_cell.formula if review_cell else None,
            )
        )
    return tuple(rows)


def _warning_findings(snapshot: WorkbookSnapshot) -> tuple[BootstrapFinding, ...]:
    findings = []
    for warning in snapshot.warnings:
        source_row = None
        if warning.coordinate:
            try:
                source_row = coordinate_to_tuple(warning.coordinate)[0]
            except (TypeError, ValueError):
                source_row = None
        findings.append(
            BootstrapFinding(
                category=BootstrapFindingCategory.WORKBOOKS,
                severity=BootstrapFindingSeverity.WARNING,
                code="excel_read_warning",
                message=warning.message.strip() or "Excel reader warning.",
                workbook=snapshot.path.name,
                sheet=warning.sheet_name,
                source_row=source_row,
                source_value=warning.coordinate,
            )
        )
    return tuple(findings)


def validate_bootstrap_snapshots(
    glossary_snapshot: WorkbookSnapshot,
    references_snapshot: WorkbookSnapshot,
    overrides: Mapping[str, str],
) -> ValidatedBootstrap:
    """Validate all Phase 0B relationships from two read-only snapshots."""

    findings = [
        *_warning_findings(glossary_snapshot),
        *_warning_findings(references_snapshot),
    ]
    compatibility = None
    try:
        glossary_metadata = extract_workbook_metadata(glossary_snapshot)
        references_metadata = extract_workbook_metadata(references_snapshot)
        compatibility = validate_workbook_compatibility(
            glossary_metadata, references_metadata
        )
    except ValueError as error:
        findings.append(
            BootstrapFinding(
                category=BootstrapFindingCategory.WORKBOOKS,
                severity=BootstrapFindingSeverity.ERROR,
                code="incompatible_metadata",
                message=str(error),
            )
        )

    glossary_rows: tuple[_GlossarySourceRow, ...] = ()
    glossary_structure_valid = False
    try:
        glossary_rows = _extract_glossary_rows(glossary_snapshot)
        glossary_structure_valid = True
    except ValueError as error:
        findings.append(
            BootstrapFinding(
                category=BootstrapFindingCategory.NAMES,
                severity=BootstrapFindingSeverity.ERROR,
                code="invalid_glossary_structure",
                message=str(error),
                workbook=glossary_snapshot.path.name,
                sheet=GLOSSARY_SHEET_NAME,
            )
        )

    reference_rows: tuple[_ReferenceSourceRow, ...] = ()
    try:
        reference_rows = _extract_reference_rows(references_snapshot)
    except ValueError as error:
        findings.append(
            BootstrapFinding(
                category=BootstrapFindingCategory.REFERENCES,
                severity=BootstrapFindingSeverity.ERROR,
                code="invalid_reference_structure",
                message=str(error),
                workbook=references_snapshot.path.name,
                sheet=REFERENCES_SHEET_NAME,
            )
        )

    id_mappings: tuple[BootstrapIdMapping, ...] = ()
    identities: tuple[GlossaryIdentity, ...] = ()
    if glossary_rows:
        try:
            id_mappings = bootstrap_contaminant_ids(
                row.id_legacy_cg for row in glossary_rows
            )
            id_by_legacy = {
                mapping.id_legacy_cg: mapping.id_contaminant
                for mapping in id_mappings
            }
            identities = tuple(
                sorted(
                    (
                        GlossaryIdentity(
                            id_name=row.id_name,
                            id_contaminant=id_by_legacy[row.id_legacy_cg],
                        )
                        for row in glossary_rows
                    ),
                    key=lambda value: value.id_contaminant,
                )
            )
            names: dict[object, int] = {}
            ambiguous_names: set[str] = set()
            for identity in identities:
                if (
                    not isinstance(identity.id_name, str)
                    or not identity.id_name.strip()
                ):
                    raise ValueError("glossary names must be nonblank text")
                if identity.id_name in names:
                    ambiguous_names.add(identity.id_name)
                names[identity.id_name] = names.get(identity.id_name, 0) + 1
            if ambiguous_names:
                raise ValueError(
                    "ambiguous glossary names: "
                    + ", ".join(repr(name) for name in sorted(ambiguous_names))
                )
        except ValueError as error:
            category = (
                BootstrapFindingCategory.NAMES
                if "name" in str(error)
                else BootstrapFindingCategory.IDS
            )
            findings.append(
                BootstrapFinding(
                    category=category,
                    severity=BootstrapFindingSeverity.ERROR,
                    code="invalid_glossary_identity",
                    message=str(error),
                    workbook=glossary_snapshot.path.name,
                    sheet=GLOSSARY_SHEET_NAME,
                )
            )
            if category is BootstrapFindingCategory.IDS:
                id_mappings = ()
            identities = ()
    elif glossary_structure_valid:
        findings.append(
            BootstrapFinding(
                category=BootstrapFindingCategory.IDS,
                severity=BootstrapFindingSeverity.ERROR,
                code="invalid_glossary_identity",
                message="Glossary table contains no contaminant rows.",
                workbook=glossary_snapshot.path.name,
                sheet=GLOSSARY_SHEET_NAME,
            )
        )

    crosswalk: tuple[ReferenceCrosswalkEntry, ...] = ()
    exact_reference_rows = 0
    override_reference_rows = 0
    valid_reference_labels = tuple(
        row.review_label
        for row in reference_rows
        if isinstance(row.review_label, str) and row.review_label.strip()
    )
    invalid_reference_rows = tuple(
        row
        for row in reference_rows
        if row.review_label_formula is not None
        or not isinstance(row.review_label, str)
        or not row.review_label.strip()
    )
    for row in invalid_reference_rows:
        findings.append(
            BootstrapFinding(
                category=BootstrapFindingCategory.REFERENCES,
                severity=BootstrapFindingSeverity.ERROR,
                code="invalid_reference_label",
                message="Reference review label must be literal nonblank text.",
                workbook=references_snapshot.path.name,
                sheet=REFERENCES_SHEET_NAME,
                source_row=row.source_row,
                source_value=repr(row.review_label),
            )
        )

    if identities and not invalid_reference_rows and reference_rows:
        try:
            crosswalk = build_reference_crosswalk(
                identities, valid_reference_labels, overrides
            )
            entries_by_label = {
                entry.refs_review_name: entry for entry in crosswalk
            }
            exact_reference_rows = sum(
                entries_by_label[label].resolution_method
                is ReferenceResolutionMethod.EXACT
                for label in valid_reference_labels
            )
            override_reference_rows = sum(
                entries_by_label[label].resolution_method
                is ReferenceResolutionMethod.OVERRIDE
                for label in valid_reference_labels
            )
            for entry in crosswalk:
                if entry.resolution_method is ReferenceResolutionMethod.OVERRIDE:
                    findings.append(
                        BootstrapFinding(
                            category=BootstrapFindingCategory.REFERENCES,
                            severity=BootstrapFindingSeverity.INFO,
                            code="reference_label_override",
                            message=(
                                f"Resolved to {entry.id_contaminant} through "
                                "a reviewed override."
                            ),
                            workbook=references_snapshot.path.name,
                            sheet=REFERENCES_SHEET_NAME,
                            source_value=entry.refs_review_name,
                        )
                    )
        except ValueError as error:
            findings.append(
                BootstrapFinding(
                    category=BootstrapFindingCategory.REFERENCES,
                    severity=BootstrapFindingSeverity.ERROR,
                    code="unresolved_reference_relationship",
                    message=str(error),
                    workbook=references_snapshot.path.name,
                    sheet=REFERENCES_SHEET_NAME,
                )
            )
    elif reference_rows and not identities:
        findings.append(
            BootstrapFinding(
                category=BootstrapFindingCategory.REFERENCES,
                severity=BootstrapFindingSeverity.INFO,
                code="reference_validation_unavailable",
                message="Reference validation requires valid glossary identities.",
            )
        )

    definitions: tuple[FootnoteDefinition, ...] = ()
    usages: tuple[FootnoteUsage, ...] = ()
    if identities:
        identity_by_legacy = {
            mapping.id_legacy_cg: mapping.id_contaminant
            for mapping in id_mappings
        }
        sources = tuple(
            GlossaryFootnoteSource(
                id_contaminant=identity_by_legacy[row.id_legacy_cg],
                source_row=row.source_row,
                value=row.footnote_value,
                formula=row.footnote_formula,
            )
            for row in glossary_rows
        )
        try:
            definitions, usages = validate_footnote_relationships(
                glossary_snapshot, sources
            )
        except FootnoteValidationError as error:
            for issue in error.issues:
                findings.append(
                    BootstrapFinding(
                        category=BootstrapFindingCategory.FOOTNOTES,
                        severity=BootstrapFindingSeverity.ERROR,
                        code="invalid_footnote_relationship",
                        message=issue.message,
                        workbook=glossary_snapshot.path.name,
                        sheet=issue.sheet_name,
                        source_row=issue.source_row,
                        source_value=issue.source_value,
                    )
                )

    counts = BootstrapReportCounts(
        glossary_rows=len(glossary_rows),
        assigned_contaminant_ids=len(id_mappings),
        distinct_glossary_names=len(
            {
                row.id_name
                for row in glossary_rows
                if isinstance(row.id_name, str) and row.id_name.strip()
            }
        ),
        reference_rows=len(reference_rows),
        distinct_reference_labels=len(set(valid_reference_labels)),
        exact_match_reference_rows=exact_reference_rows,
        override_reference_rows=override_reference_rows,
        footnote_definitions=len(definitions),
        glossary_footnote_usages=sum(
            len(usage.footnote_ids) for usage in usages
        ),
    )
    report = build_bootstrap_report(counts, compatibility, findings)
    if report.status is BootstrapReportStatus.FAILED:
        raise BootstrapValidationError(report)

    assert compatibility is not None
    return ValidatedBootstrap(
        report=report,
        compatibility=compatibility,
        glossary_identities=identities,
        id_mappings=id_mappings,
        reference_crosswalk=crosswalk,
        footnote_definitions=definitions,
        footnote_usages=usages,
    )
