"""Stable paths to non-authoritative workbook fixtures."""

from pathlib import Path


FIXTURE_WORKBOOK_DIR = Path(__file__).resolve().parent / "fixtures" / "workbooks"
SYNTHETIC_GLOSSARY_WORKBOOK = (
    FIXTURE_WORKBOOK_DIR / "contaminant_glossary.xlsx"
)
SYNTHETIC_REFERENCES_WORKBOOK = FIXTURE_WORKBOOK_DIR / "references.xlsx"

