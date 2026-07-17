"""Deterministic in-memory reporting for bootstrap validation."""

from collections.abc import Iterable
from dataclasses import dataclass, field, fields
from enum import StrEnum

from .metadata import WorkbookCompatibility


class BootstrapReportStatus(StrEnum):
    """Overall result derived from report findings."""

    PASSED = "passed"
    FAILED = "failed"


class BootstrapFindingSeverity(StrEnum):
    """Effect of one finding on the report result."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class BootstrapFindingCategory(StrEnum):
    """Bootstrap subject described by one finding."""

    NAMES = "names"
    IDS = "ids"
    REFERENCES = "references"
    FOOTNOTES = "footnotes"
    WORKBOOKS = "workbooks"


def _exact_nonblank_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be nonblank text")
    if value != value.strip():
        raise ValueError(f"{field_name} must not have surrounding whitespace")
    return value


def _optional_nonblank_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be nonblank text when supplied")
    return value


@dataclass(frozen=True)
class BootstrapFinding:
    """One reportable bootstrap observation with optional source context."""

    category: BootstrapFindingCategory
    severity: BootstrapFindingSeverity
    code: str
    message: str
    workbook: str | None = None
    sheet: str | None = None
    source_row: int | None = None
    source_value: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.category, BootstrapFindingCategory):
            raise ValueError("finding category must be a BootstrapFindingCategory")
        if not isinstance(self.severity, BootstrapFindingSeverity):
            raise ValueError("finding severity must be a BootstrapFindingSeverity")
        _exact_nonblank_text(self.code, "finding code")
        _exact_nonblank_text(self.message, "finding message")
        _optional_nonblank_text(self.workbook, "finding workbook")
        _optional_nonblank_text(self.sheet, "finding sheet")
        _optional_nonblank_text(self.source_value, "finding source value")
        if self.source_row is not None and (
            type(self.source_row) is not int or self.source_row <= 0
        ):
            raise ValueError("finding source row must be a positive integer")


@dataclass(frozen=True)
class BootstrapReportCounts:
    """Counts that summarize the bootstrap inputs and relationships."""

    glossary_rows: int
    assigned_contaminant_ids: int
    distinct_glossary_names: int
    reference_rows: int
    distinct_reference_labels: int
    exact_match_reference_rows: int
    override_reference_rows: int
    footnote_definitions: int
    glossary_footnote_usages: int

    def __post_init__(self) -> None:
        for count_field in fields(self):
            value = getattr(self, count_field.name)
            if type(value) is not int or value < 0:
                raise ValueError(
                    f"{count_field.name} must be a nonnegative integer"
                )


@dataclass(frozen=True)
class BootstrapValidationReport:
    """A consistent, immutable bootstrap report."""

    counts: BootstrapReportCounts
    compatibility: WorkbookCompatibility | None
    findings: tuple[BootstrapFinding, ...]
    status: BootstrapReportStatus = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.counts, BootstrapReportCounts):
            raise ValueError("report counts must be a BootstrapReportCounts record")
        if self.compatibility is not None and not isinstance(
            self.compatibility, WorkbookCompatibility
        ):
            raise ValueError(
                "report compatibility must be a WorkbookCompatibility record"
            )
        if not isinstance(self.findings, tuple) or any(
            not isinstance(finding, BootstrapFinding)
            for finding in self.findings
        ):
            raise ValueError("report findings must be BootstrapFinding records")

        sorted_findings = tuple(sorted(self.findings, key=_finding_sort_key))
        object.__setattr__(self, "findings", sorted_findings)

        workbook_error = any(
            finding.category is BootstrapFindingCategory.WORKBOOKS
            and finding.severity is BootstrapFindingSeverity.ERROR
            for finding in sorted_findings
        )
        if self.compatibility is None and not workbook_error:
            raise ValueError(
                "missing compatibility requires a workbook-category error"
            )
        if self.compatibility is not None and workbook_error:
            raise ValueError(
                "successful compatibility conflicts with a workbook-category error"
            )

        status = (
            BootstrapReportStatus.FAILED
            if any(
                finding.severity is BootstrapFindingSeverity.ERROR
                for finding in sorted_findings
            )
            else BootstrapReportStatus.PASSED
        )
        object.__setattr__(self, "status", status)


_SEVERITY_ORDER = {
    BootstrapFindingSeverity.ERROR: 0,
    BootstrapFindingSeverity.WARNING: 1,
    BootstrapFindingSeverity.INFO: 2,
}


def _finding_sort_key(finding: BootstrapFinding) -> tuple[object, ...]:
    return (
        _SEVERITY_ORDER[finding.severity],
        finding.category.value,
        finding.code,
        finding.workbook or "",
        finding.sheet or "",
        finding.source_row or 0,
        finding.source_value or "",
        finding.message,
    )


def build_bootstrap_report(
    counts: BootstrapReportCounts,
    compatibility: WorkbookCompatibility | None,
    findings: Iterable[BootstrapFinding],
) -> BootstrapValidationReport:
    """Build a validated report without reading files or mutating inputs."""

    if not isinstance(counts, BootstrapReportCounts):
        raise ValueError("report counts must be a BootstrapReportCounts record")
    if compatibility is not None and not isinstance(
        compatibility, WorkbookCompatibility
    ):
        raise ValueError(
            "report compatibility must be a WorkbookCompatibility record"
        )

    finding_values = tuple(findings)
    if any(
        not isinstance(finding, BootstrapFinding)
        for finding in finding_values
    ):
        raise ValueError("report findings must be BootstrapFinding records")

    return BootstrapValidationReport(
        counts=counts,
        compatibility=compatibility,
        findings=tuple(sorted(finding_values, key=_finding_sort_key)),
    )


def format_bootstrap_report(report: BootstrapValidationReport) -> str:
    """Return stable plain text for a validated bootstrap report."""

    if not isinstance(report, BootstrapValidationReport):
        raise ValueError("report must be a BootstrapValidationReport record")

    lines = [
        "Bootstrap validation report",
        f"status: {report.status.value}",
    ]
    if report.compatibility is None:
        lines.extend(
            (
                "data_release_id: unavailable",
                "workbook_compatibility: unavailable",
            )
        )
    else:
        compatibility = report.compatibility
        glossary = compatibility.glossary_metadata
        references = compatibility.references_metadata
        lines.extend(
            (
                f"data_release_id: {compatibility.data_release_id}",
                "workbook_compatibility:",
                "  glossary: "
                f"{glossary.workbook_type} | schema {glossary.schema_version} "
                f"| revision {glossary.workbook_revision}",
                "  references: "
                f"{references.workbook_type} | schema "
                f"{references.schema_version} | revision "
                f"{references.workbook_revision}",
            )
        )

    lines.append("counts:")
    for count_field in fields(report.counts):
        lines.append(
            f"  {count_field.name}: {getattr(report.counts, count_field.name)}"
        )

    lines.append("findings:")
    if not report.findings:
        lines.append("  none")
    else:
        for finding in report.findings:
            lines.append(
                f"  - [{finding.severity.value}] {finding.category.value}."
                f"{finding.code}: {finding.message}"
            )
            context_parts = []
            if finding.workbook is not None:
                context_parts.append(f"workbook={finding.workbook}")
            if finding.sheet is not None:
                context_parts.append(f"sheet={finding.sheet}")
            if finding.source_row is not None:
                context_parts.append(f"row={finding.source_row}")
            if finding.source_value is not None:
                context_parts.append(f"value={finding.source_value}")
            if context_parts:
                lines.append("    context: " + "; ".join(context_parts))

    return "\n".join(lines) + "\n"
