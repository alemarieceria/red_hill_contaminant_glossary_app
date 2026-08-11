"""Stable workbook names and release rules for the contaminant pipeline."""

from datetime import datetime
import re


GLOSSARY_WORKBOOK_FILENAME = "contaminant_glossary.xlsx"
REFERENCES_WORKBOOK_FILENAME = "references.xlsx"

GLOSSARY_WORKBOOK_TYPE = "contaminant_glossary"
REFERENCES_WORKBOOK_TYPE = "references"

WORKBOOK_SCHEMA_VERSION = "1.0.0"
SUPPORTED_WORKBOOK_SCHEMA_VERSIONS = frozenset({WORKBOOK_SCHEMA_VERSION})
INTAKE_MANIFEST_SCHEMA_VERSION = "1.0.0"

INTRODUCTION_SHEET_NAME = "Introduction"
GLOSSARY_SHEET_NAME = "Glossary"
FOOTNOTES_SHEET_NAME = "Footnotes"
METADATA_SHEET_NAME = "Metadata"
REFERENCES_SHEET_NAME = "Sheet1"

GLOSSARY_WORKSHEET_NAMES = (
    INTRODUCTION_SHEET_NAME,
    GLOSSARY_SHEET_NAME,
    FOOTNOTES_SHEET_NAME,
    METADATA_SHEET_NAME,
)
REFERENCES_WORKSHEET_NAMES = (
    REFERENCES_SHEET_NAME,
    METADATA_SHEET_NAME,
)

FOOTNOTES_HEADER_ROW = 1
REFERENCES_HEADER_ROW = 1

GLOSSARY_TABLE_NAME = "Table_1"
METADATA_TABLE_NAME = "MetadataTable"

_RELEASE_ID_PATTERN = re.compile(
    r"^(?P<date>[0-9]{8})(?:-r(?:[2-9]|[1-9][0-9]+))?$"
)


def validate_release_id(value: object) -> str:
    """Return a valid release ID or raise ``ValueError``.

    A release ID is a real calendar date in ``YYYYMMDD`` form, optionally
    followed by ``-rN`` where ``N`` is at least 2.
    """

    if not isinstance(value, str):
        raise ValueError("release ID must be text")

    match = _RELEASE_ID_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(
            "release ID must have the form YYYYMMDD or YYYYMMDD-rN (N >= 2)"
        )

    try:
        datetime.strptime(match.group("date"), "%Y%m%d")
    except ValueError as error:
        raise ValueError("release ID contains an invalid calendar date") from error

    return value


def release_order_key(value: object) -> tuple[datetime, int]:
    """Return chronological and same-day ordering for a release ID."""

    release_id = validate_release_id(value)
    date_text, separator, suffix = release_id.partition("-r")
    revision_number = int(suffix) if separator else 1
    return datetime.strptime(date_text, "%Y%m%d"), revision_number
