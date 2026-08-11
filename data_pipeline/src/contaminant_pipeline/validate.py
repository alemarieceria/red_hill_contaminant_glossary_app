"""Validate immutable raw workbooks before canonical processing."""

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType

from .config import (
    FOOTNOTES_SHEET_NAME,
    GLOSSARY_SHEET_NAME,
    GLOSSARY_TABLE_NAME,
    GLOSSARY_WORKBOOK_FILENAME,
    METADATA_SHEET_NAME,
    METADATA_TABLE_NAME,
    REFERENCES_SHEET_NAME,
    REFERENCES_WORKBOOK_FILENAME,
    SUPPORTED_WORKBOOK_SCHEMA_VERSIONS,
    WORKBOOK_SCHEMA_VERSION,
    validate_release_id,
)
from .intake import (
    IncomingContractError,
    IncomingPairInventory,
    IncomingWorkbookPair,
    IntakePublication,
    WorkbookInventory,
    inventory_incoming_pair,
    read_incoming_pair,
)
from .metadata import METADATA_HEADERS
from .schemas import (
    FOOTNOTE_HEADER_MAP,
    GLOSSARY_HEADER_MAP,
    REFERENCE_HEADER_MAP,
)


class WorkbookContractError(ValueError):
    """Raised when an immutable raw workbook violates its schema contract."""


@dataclass(frozen=True)
class ValidatedWorkbookContract:
    """A completed intake whose raw workbook structure is schema compliant."""

    intake_publication: IntakePublication
    raw_pair: IncomingWorkbookPair
    raw_inventory: IncomingPairInventory
    data_release_id: str
    schema_version: str


@dataclass(frozen=True)
class _HeaderContract:
    workbook_role: str
    sheet_name: str
    table_name: str | None
    expected_headers: tuple[str, ...]


_SCHEMA_HEADER_CONTRACTS = MappingProxyType(
    {
        WORKBOOK_SCHEMA_VERSION: (
            _HeaderContract(
                "glossary",
                GLOSSARY_SHEET_NAME,
                GLOSSARY_TABLE_NAME,
                tuple(GLOSSARY_HEADER_MAP),
            ),
            _HeaderContract(
                "glossary",
                FOOTNOTES_SHEET_NAME,
                None,
                tuple(FOOTNOTE_HEADER_MAP),
            ),
            _HeaderContract(
                "glossary",
                METADATA_SHEET_NAME,
                METADATA_TABLE_NAME,
                METADATA_HEADERS,
            ),
            _HeaderContract(
                "references",
                REFERENCES_SHEET_NAME,
                None,
                tuple(REFERENCE_HEADER_MAP),
            ),
            _HeaderContract(
                "references",
                METADATA_SHEET_NAME,
                METADATA_TABLE_NAME,
                METADATA_HEADERS,
            ),
        )
    }
)


def _validated_publication(value: object) -> IntakePublication:
    if not isinstance(value, IntakePublication):
        raise WorkbookContractError(
            "workbook contract validation requires a completed IntakePublication"
        )

    try:
        release_id = validate_release_id(value.inventory.data_release_id)
    except (AttributeError, ValueError) as error:
        raise WorkbookContractError(
            "completed intake has an invalid data release ID"
        ) from error

    raw = value.raw_snapshot
    manifest = value.manifest
    if raw.inventory != value.inventory:
        raise WorkbookContractError(
            f"release {release_id} raw snapshot does not retain its accepted inventory"
        )
    if manifest.raw_snapshot != raw:
        raise WorkbookContractError(
            f"release {release_id} manifest does not retain its raw snapshot"
        )
    if (
        raw.data_release_id != release_id
        or manifest.manifest.data_release_id != release_id
        or raw.snapshot_dir.name != release_id
    ):
        raise WorkbookContractError(
            f"release {release_id} completed intake identities do not agree"
        )
    if (
        raw.glossary_path.parent != raw.snapshot_dir
        or raw.glossary_path.name != GLOSSARY_WORKBOOK_FILENAME
        or raw.references_path.parent != raw.snapshot_dir
        or raw.references_path.name != REFERENCES_WORKBOOK_FILENAME
    ):
        raise WorkbookContractError(
            f"release {release_id} raw workbook paths do not follow the stable contract"
        )
    return value


def _workbook_for_role(
    inventory: IncomingPairInventory,
    role: str,
) -> WorkbookInventory:
    if role == "glossary":
        return inventory.glossary_inventory
    if role == "references":
        return inventory.references_inventory
    raise WorkbookContractError(f"unsupported workbook contract role: {role!r}")


def _headers_for_contract(
    workbook: WorkbookInventory,
    contract: _HeaderContract,
) -> tuple[str, ...]:
    sheets = tuple(
        sheet for sheet in workbook.worksheets if sheet.name == contract.sheet_name
    )
    if len(sheets) != 1:
        raise WorkbookContractError(
            f"{contract.workbook_role} workbook expected exactly one sheet "
            f"{contract.sheet_name!r}; found {len(sheets)}"
        )
    sheet = sheets[0]
    if contract.table_name is None:
        headers = sheet.headers
    else:
        tables = tuple(
            table for table in sheet.tables if table.name == contract.table_name
        )
        if len(tables) != 1:
            raise WorkbookContractError(
                f"{contract.workbook_role} workbook sheet {contract.sheet_name!r} "
                f"expected exactly one table {contract.table_name!r}; "
                f"found {len(tables)}"
            )
        headers = tables[0].headers
    return tuple(header.value for header in headers)


def _validate_headers(
    *,
    release_id: str,
    inventory: IncomingPairInventory,
    contracts: tuple[_HeaderContract, ...],
) -> None:
    for contract in contracts:
        workbook = _workbook_for_role(inventory, contract.workbook_role)
        actual = _headers_for_contract(workbook, contract)
        expected = contract.expected_headers
        actual_counts = Counter(actual)
        expected_counts = Counter(expected)
        if actual_counts == expected_counts:
            continue

        missing = tuple(
            header
            for header in expected
            if actual_counts[header] < expected_counts[header]
        )
        unexpected = tuple(
            header
            for header in actual
            if actual_counts[header] > expected_counts[header]
        )
        location = (
            f"release {release_id} {contract.workbook_role} workbook "
            f"sheet {contract.sheet_name!r}"
        )
        if contract.table_name is not None:
            location += f" table {contract.table_name!r}"
        raise WorkbookContractError(
            f"{location} headers do not match schema: "
            f"missing {missing!r}; unexpected {unexpected!r}"
        )


def _require_matching_inventory(
    *,
    release_id: str,
    role: str,
    accepted: WorkbookInventory,
    observed: WorkbookInventory,
) -> None:
    if observed.size_bytes != accepted.size_bytes:
        raise WorkbookContractError(
            f"release {release_id} {role} raw snapshot byte size does not match "
            "the completed intake"
        )
    if observed.sha256 != accepted.sha256:
        raise WorkbookContractError(
            f"release {release_id} {role} raw snapshot SHA-256 does not match "
            "the completed intake"
        )
    if observed != accepted:
        raise WorkbookContractError(
            f"release {release_id} {role} raw snapshot structural inventory "
            "does not match the completed intake"
        )


def validate_workbook_contract(
    intake_publication: IntakePublication,
) -> ValidatedWorkbookContract:
    """Validate schema structure from a completed intake's raw snapshots."""

    completed = _validated_publication(intake_publication)
    release_id = completed.inventory.data_release_id
    raw_dir = completed.raw_snapshot.snapshot_dir
    try:
        raw_pair = read_incoming_pair(raw_dir)
        raw_inventory = inventory_incoming_pair(raw_pair)
    except IncomingContractError as error:
        raise WorkbookContractError(
            f"release {release_id} raw workbook contract failed: {error}"
        ) from error

    if raw_inventory.data_release_id != release_id:
        raise WorkbookContractError(
            f"release {release_id} raw workbook Metadata derives release "
            f"{raw_inventory.data_release_id!r}"
        )
    _require_matching_inventory(
        release_id=release_id,
        role="glossary",
        accepted=completed.inventory.glossary_inventory,
        observed=raw_inventory.glossary_inventory,
    )
    _require_matching_inventory(
        release_id=release_id,
        role="references",
        accepted=completed.inventory.references_inventory,
        observed=raw_inventory.references_inventory,
    )

    schema_version = raw_pair.compatibility.glossary_metadata.schema_version
    if schema_version not in SUPPORTED_WORKBOOK_SCHEMA_VERSIONS:
        raise WorkbookContractError(
            f"release {release_id} uses unsupported workbook schema "
            f"{schema_version!r}"
        )
    contracts = _SCHEMA_HEADER_CONTRACTS.get(schema_version)
    if contracts is None:
        raise WorkbookContractError(
            f"release {release_id} has no workbook header contract for supported "
            f"schema {schema_version!r}"
        )
    _validate_headers(
        release_id=release_id,
        inventory=raw_inventory,
        contracts=contracts,
    )

    return ValidatedWorkbookContract(
        intake_publication=completed,
        raw_pair=raw_pair,
        raw_inventory=raw_inventory,
        data_release_id=release_id,
        schema_version=schema_version,
    )
