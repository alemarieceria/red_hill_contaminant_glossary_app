"""Central filesystem locations for the contaminant pipeline."""

from pathlib import Path

from .config import (
    GLOSSARY_WORKBOOK_FILENAME,
    REFERENCES_WORKBOOK_FILENAME,
    validate_release_id,
)


PIPELINE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PIPELINE_ROOT.parent

DATA_DIR = PIPELINE_ROOT / "data"
INCOMING_DIR = DATA_DIR / "00_incoming"
MANIFEST_DIR = DATA_DIR / "01_manifest"
RAW_SNAPSHOTS_DIR = DATA_DIR / "02_raw_snapshots"
PROCESSED_DIR = DATA_DIR / "03_processed"
OUTPUT_DIR = DATA_DIR / "04_output"
PUBLIC_DATA_DIR = REPOSITORY_ROOT / "public" / "data"

INCOMING_GLOSSARY_WORKBOOK = INCOMING_DIR / GLOSSARY_WORKBOOK_FILENAME
INCOMING_REFERENCES_WORKBOOK = INCOMING_DIR / REFERENCES_WORKBOOK_FILENAME


def raw_snapshot_dir(release_id: object) -> Path:
    """Return the raw-snapshot directory for a validated release ID."""

    return RAW_SNAPSHOTS_DIR / validate_release_id(release_id)


def processed_release_dir(release_id: object) -> Path:
    """Return the processed-data directory for a validated release ID."""

    return PROCESSED_DIR / validate_release_id(release_id)


def output_release_dir(release_id: object) -> Path:
    """Return the output directory for a validated release ID."""

    return OUTPUT_DIR / validate_release_id(release_id)


def manifest_path(release_id: object) -> Path:
    """Return the manifest JSON path for a validated release ID."""

    validated_release_id = validate_release_id(release_id)
    return MANIFEST_DIR / f"{validated_release_id}.json"
