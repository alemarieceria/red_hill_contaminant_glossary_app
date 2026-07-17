from dataclasses import FrozenInstanceError, fields
import unittest

from contaminant_pipeline.bootstrap_report import (
    BootstrapFinding,
    BootstrapFindingCategory,
    BootstrapFindingSeverity,
    BootstrapReportCounts,
    BootstrapReportStatus,
    BootstrapValidationReport,
    build_bootstrap_report,
    format_bootstrap_report,
)
from contaminant_pipeline.config import (
    GLOSSARY_WORKBOOK_TYPE,
    REFERENCES_WORKBOOK_TYPE,
    WORKBOOK_SCHEMA_VERSION,
)
from contaminant_pipeline.metadata import (
    WorkbookMetadata,
    validate_workbook_compatibility,
)


def report_counts(**changes) -> BootstrapReportCounts:
    values = {
        "glossary_rows": 152,
        "assigned_contaminant_ids": 152,
        "distinct_glossary_names": 152,
        "reference_rows": 406,
        "distinct_reference_labels": 133,
        "exact_match_reference_rows": 343,
        "override_reference_rows": 63,
        "footnote_definitions": 4,
        "glossary_footnote_usages": 19,
    }
    values.update(changes)
    return BootstrapReportCounts(**values)


def compatible_workbooks():
    return validate_workbook_compatibility(
        WorkbookMetadata(
            GLOSSARY_WORKBOOK_TYPE,
            WORKBOOK_SCHEMA_VERSION,
            "20260716",
        ),
        WorkbookMetadata(
            REFERENCES_WORKBOOK_TYPE,
            WORKBOOK_SCHEMA_VERSION,
            "20260716",
        ),
    )


def finding(
    category=BootstrapFindingCategory.REFERENCES,
    severity=BootstrapFindingSeverity.WARNING,
    code="review_label_differs",
    message="Reference review label differs from the glossary name.",
    **context,
) -> BootstrapFinding:
    return BootstrapFinding(
        category=category,
        severity=severity,
        code=code,
        message=message,
        **context,
    )


class BootstrapReportSuccessTests(unittest.TestCase):
    def test_builds_and_formats_a_passing_report(self) -> None:
        counts = report_counts()
        compatibility = compatible_workbooks()

        report = build_bootstrap_report(counts, compatibility, [])
        formatted = format_bootstrap_report(report)

        self.assertEqual(report.status, BootstrapReportStatus.PASSED)
        self.assertEqual(report.findings, ())
        self.assertIn("status: passed", formatted)
        self.assertIn("data_release_id: 20260716", formatted)
        self.assertIn("workbook_compatibility:", formatted)
        self.assertIn("findings:\n  none", formatted)
        for count_field in fields(counts):
            self.assertIn(
                f"{count_field.name}: {getattr(counts, count_field.name)}",
                formatted,
            )

    def test_records_and_report_collections_are_immutable(self) -> None:
        counts = report_counts()
        observation = finding()
        report = build_bootstrap_report(
            counts, compatible_workbooks(), [observation]
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(counts, "glossary_rows", 1)
        with self.assertRaises(FrozenInstanceError):
            setattr(observation, "message", "Changed")
        with self.assertRaises(FrozenInstanceError):
            setattr(report, "status", BootstrapReportStatus.FAILED)
        self.assertIsInstance(report.findings, tuple)

    def test_does_not_mutate_caller_findings(self) -> None:
        findings = [
            finding(code="z_code", message="Later finding."),
            finding(code="a_code", message="Earlier finding."),
        ]
        original = findings.copy()

        build_bootstrap_report(report_counts(), compatible_workbooks(), findings)

        self.assertEqual(findings, original)


class BootstrapReportFindingTests(unittest.TestCase):
    def test_info_and_warnings_keep_a_passing_status(self) -> None:
        findings = (
            finding(
                category=BootstrapFindingCategory.NAMES,
                severity=BootstrapFindingSeverity.INFO,
                code="name_count",
                message="Glossary names were counted.",
            ),
            finding(
                category=BootstrapFindingCategory.WORKBOOKS,
                severity=BootstrapFindingSeverity.WARNING,
                code="older_reference_revision",
                message="The references workbook is unchanged.",
            ),
        )

        report = build_bootstrap_report(
            report_counts(), compatible_workbooks(), findings
        )

        self.assertEqual(report.status, BootstrapReportStatus.PASSED)

    def test_any_nonworkbook_error_makes_a_compatible_report_fail(self) -> None:
        report = build_bootstrap_report(
            report_counts(),
            compatible_workbooks(),
            [
                finding(
                    severity=BootstrapFindingSeverity.ERROR,
                    code="unresolved_label",
                    message="A reference label is unresolved.",
                )
            ],
        )

        self.assertEqual(report.status, BootstrapReportStatus.FAILED)

    def test_finding_order_is_deterministic_and_duplicates_are_retained(
        self,
    ) -> None:
        repeated = finding(
            severity=BootstrapFindingSeverity.ERROR,
            code="unresolved_label",
            message="A label is unresolved.",
            source_row=8,
            source_value="Variant",
        )
        findings = [
            finding(
                severity=BootstrapFindingSeverity.INFO,
                code="summary",
                message="Summary information.",
            ),
            repeated,
            finding(
                severity=BootstrapFindingSeverity.ERROR,
                code="unresolved_label",
                message="A label is unresolved.",
                source_row=3,
                source_value="Other variant",
            ),
            repeated,
        ]

        forward = build_bootstrap_report(
            report_counts(), compatible_workbooks(), findings
        )
        reverse = build_bootstrap_report(
            report_counts(), compatible_workbooks(), reversed(findings)
        )

        self.assertEqual(forward, reverse)
        self.assertEqual(
            format_bootstrap_report(forward),
            format_bootstrap_report(reverse),
        )
        self.assertEqual(forward.findings.count(repeated), 2)
        self.assertEqual(forward.findings[0].source_row, 3)

    def test_formats_every_category_and_optional_context(self) -> None:
        findings = (
            finding(
                category=BootstrapFindingCategory.NAMES,
                severity=BootstrapFindingSeverity.ERROR,
                code="ambiguous_name",
                message="A glossary name is ambiguous.",
                workbook="contaminant_glossary",
                sheet="Glossary",
                source_row=4,
                source_value="Example",
            ),
            finding(
                category=BootstrapFindingCategory.IDS,
                severity=BootstrapFindingSeverity.ERROR,
                code="duplicate_id",
                message="A contaminant ID is duplicated.",
            ),
            finding(
                category=BootstrapFindingCategory.REFERENCES,
                severity=BootstrapFindingSeverity.ERROR,
                code="unresolved_reference",
                message="A reference label is unresolved.",
            ),
            finding(
                category=BootstrapFindingCategory.FOOTNOTES,
                severity=BootstrapFindingSeverity.ERROR,
                code="unknown_footnote",
                message="A footnote ID is unknown.",
            ),
            finding(
                category=BootstrapFindingCategory.WORKBOOKS,
                severity=BootstrapFindingSeverity.ERROR,
                code="incompatible_metadata",
                message="Workbook Metadata is incompatible.",
            ),
        )

        report = build_bootstrap_report(report_counts(), None, findings)
        formatted = format_bootstrap_report(report)

        self.assertEqual(report.status, BootstrapReportStatus.FAILED)
        self.assertIn("data_release_id: unavailable", formatted)
        self.assertIn("workbook_compatibility: unavailable", formatted)
        for category in BootstrapFindingCategory:
            self.assertIn(f"] {category.value}.", formatted)
        self.assertIn(
            "context: workbook=contaminant_glossary; sheet=Glossary; "
            "row=4; value=Example",
            formatted,
        )


class BootstrapReportValidationTests(unittest.TestCase):
    def test_rejects_invalid_counts(self) -> None:
        invalid_values = (-1, True, 1.5, "1", None)

        for count_field in fields(report_counts()):
            for value in invalid_values:
                with self.subTest(field=count_field.name, value=value):
                    with self.assertRaisesRegex(
                        ValueError, "nonnegative integer"
                    ):
                        report_counts(**{count_field.name: value})

    def test_rejects_invalid_finding_enums(self) -> None:
        cases = (
            ("references", BootstrapFindingSeverity.ERROR, "category"),
            (BootstrapFindingCategory.REFERENCES, "error", "severity"),
        )

        for category, severity, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    finding(category=category, severity=severity)

    def test_rejects_invalid_finding_code_or_message(self) -> None:
        cases = (
            ({"code": ""}, "finding code"),
            ({"code": " bad"}, "finding code"),
            ({"message": " "}, "finding message"),
            ({"message": 1}, "finding message"),
        )

        for changes, expected_message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, expected_message):
                    finding(**changes)

    def test_rejects_invalid_optional_finding_context(self) -> None:
        cases = (
            ({"workbook": ""}, "finding workbook"),
            ({"sheet": " "}, "finding sheet"),
            ({"source_value": 1}, "finding source value"),
            ({"source_row": 0}, "positive integer"),
            ({"source_row": -1}, "positive integer"),
            ({"source_row": True}, "positive integer"),
            ({"source_row": "1"}, "positive integer"),
        )

        for changes, expected_message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, expected_message):
                    finding(**changes)

    def test_rejects_invalid_report_input_records(self) -> None:
        valid_counts = report_counts()
        valid_compatibility = compatible_workbooks()
        cases = (
            (object(), valid_compatibility, [], "report counts"),
            (valid_counts, object(), [], "report compatibility"),
            (valid_counts, valid_compatibility, [object()], "report findings"),
        )

        for counts, compatibility, findings, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    build_bootstrap_report(counts, compatibility, findings)

    def test_rejects_missing_compatibility_without_a_workbook_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "requires a workbook-category error"
        ):
            build_bootstrap_report(report_counts(), None, [])

    def test_rejects_successful_compatibility_with_a_workbook_error(self) -> None:
        workbook_error = finding(
            category=BootstrapFindingCategory.WORKBOOKS,
            severity=BootstrapFindingSeverity.ERROR,
            code="incompatible_metadata",
            message="Workbook Metadata is incompatible.",
        )

        with self.assertRaisesRegex(ValueError, "conflicts"):
            build_bootstrap_report(
                report_counts(), compatible_workbooks(), [workbook_error]
            )

    def test_direct_report_construction_still_sorts_findings(self) -> None:
        later = finding(code="z_code", message="Later finding.")
        earlier = finding(code="a_code", message="Earlier finding.")

        report = BootstrapValidationReport(
            report_counts(), compatible_workbooks(), (later, earlier)
        )

        self.assertEqual(report.findings, (earlier, later))

    def test_formatter_rejects_an_invalid_record(self) -> None:
        with self.assertRaisesRegex(ValueError, "BootstrapValidationReport"):
            format_bootstrap_report(object())


if __name__ == "__main__":
    unittest.main()
