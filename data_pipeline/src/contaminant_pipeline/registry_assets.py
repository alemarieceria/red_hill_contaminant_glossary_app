"""Tracked contaminant registry and reference-crosswalk assets."""

from collections.abc import Iterable
import csv
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from pathlib import Path
import shutil
import tempfile

from .bootstrap_report import BootstrapReportStatus
from .bootstrap_validation import ValidatedBootstrap
from .config import release_order_key, validate_release_id
from .crosswalk import ReferenceResolutionMethod
from .identifiers import contaminant_id_number
from .paths import REGISTRY_DIR


REGISTRY_FILENAME = "contaminant_registry.csv"
CROSSWALK_FILENAME = "reference_crosswalk.csv"
REGISTRY_HEADERS = (
    "id_contaminant",
    "id_legacy_cg",
    "id_name",
    "status",
    "successor_id",
    "issued_release_id",
    "retired_release_id",
)
CROSSWALK_HEADERS = (
    "refs_review_name",
    "id_contaminant",
    "resolution_method",
    "reviewed_release_id",
)


class RegistryStatus(StrEnum):
    """Lifecycle state of an issued contaminant ID."""

    ACTIVE = "active"
    RETIRED = "retired"


def _exact_nonblank_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be nonblank text")
    if value != value.strip():
        raise ValueError(f"{field_name} must not have surrounding whitespace")
    return value


@dataclass(frozen=True)
class RegistryEntry:
    """One permanently issued contaminant identifier."""

    id_contaminant: str
    id_legacy_cg: int | None
    id_name: str
    status: RegistryStatus
    successor_id: str | None
    issued_release_id: str
    retired_release_id: str | None

    def __post_init__(self) -> None:
        contaminant_id_number(self.id_contaminant)
        if self.id_legacy_cg is not None and (
            type(self.id_legacy_cg) is not int or self.id_legacy_cg <= 0
        ):
            raise ValueError("legacy CG ID must be a positive integer or blank")
        _exact_nonblank_text(self.id_name, "registry name")
        if not isinstance(self.status, RegistryStatus):
            raise ValueError("registry status must be active or retired")
        validate_release_id(self.issued_release_id)
        if self.successor_id is not None:
            contaminant_id_number(self.successor_id)
            if self.successor_id == self.id_contaminant:
                raise ValueError("a registry ID cannot succeed itself")

        if self.status is RegistryStatus.ACTIVE:
            if self.successor_id is not None or self.retired_release_id is not None:
                raise ValueError(
                    "active registry entries cannot have retirement fields"
                )
        else:
            if self.retired_release_id is None:
                raise ValueError(
                    "retired registry entries require a retirement release"
                )
            validate_release_id(self.retired_release_id)
            if release_order_key(self.retired_release_id) < release_order_key(
                self.issued_release_id
            ):
                raise ValueError("retirement release cannot precede issuance")


@dataclass(frozen=True)
class TrackedCrosswalkEntry:
    """One durable exact or reviewed reference-label resolution."""

    refs_review_name: str
    id_contaminant: str
    resolution_method: ReferenceResolutionMethod
    reviewed_release_id: str

    def __post_init__(self) -> None:
        _exact_nonblank_text(self.refs_review_name, "reference review label")
        contaminant_id_number(self.id_contaminant)
        if not isinstance(self.resolution_method, ReferenceResolutionMethod):
            raise ValueError("resolution method must be exact or override")
        validate_release_id(self.reviewed_release_id)


@dataclass(frozen=True)
class RegistryAssetProposal:
    """The validated rows for both tracked CSV assets."""

    registry_entries: tuple[RegistryEntry, ...]
    crosswalk_entries: tuple[TrackedCrosswalkEntry, ...]


def validate_registry_entries(
    entries: Iterable[RegistryEntry],
    *,
    require_initial_legacy_ids: bool = False,
) -> tuple[RegistryEntry, ...]:
    """Validate and deterministically order registry entries."""

    values = tuple(entries)
    if any(not isinstance(entry, RegistryEntry) for entry in values):
        raise ValueError("registry rows must be RegistryEntry records")

    ids: set[str] = set()
    legacy_ids: set[int] = set()
    for entry in values:
        if entry.id_contaminant in ids:
            raise ValueError(f"duplicate registry ID: {entry.id_contaminant}")
        ids.add(entry.id_contaminant)
        if entry.id_legacy_cg is not None:
            if entry.id_legacy_cg in legacy_ids:
                raise ValueError(f"duplicate legacy CG ID: {entry.id_legacy_cg}")
            legacy_ids.add(entry.id_legacy_cg)

    for entry in values:
        if entry.successor_id is not None and entry.successor_id not in ids:
            raise ValueError(
                f"registry successor is not present: {entry.successor_id}"
            )

    if require_initial_legacy_ids:
        expected = set(range(1, 153))
        if legacy_ids != expected or len(values) != 152:
            missing = sorted(expected - legacy_ids)
            unexpected = sorted(legacy_ids - expected)
            raise ValueError(
                "initial registry must contain legacy IDs 1 through 152; "
                f"missing={missing}; unexpected={unexpected}"
            )

    return tuple(
        sorted(values, key=lambda entry: contaminant_id_number(entry.id_contaminant))
    )


def validate_tracked_crosswalk(
    entries: Iterable[TrackedCrosswalkEntry],
    registry_entries: Iterable[RegistryEntry],
) -> tuple[TrackedCrosswalkEntry, ...]:
    """Validate targets, uniqueness, and deterministic crosswalk ordering."""

    registry = validate_registry_entries(registry_entries)
    registry_ids = {entry.id_contaminant for entry in registry}
    values = tuple(entries)
    if any(not isinstance(entry, TrackedCrosswalkEntry) for entry in values):
        raise ValueError("crosswalk rows must be TrackedCrosswalkEntry records")

    labels: set[str] = set()
    for entry in values:
        if entry.refs_review_name in labels:
            raise ValueError(
                f"duplicate crosswalk label: {entry.refs_review_name!r}"
            )
        labels.add(entry.refs_review_name)
        if entry.id_contaminant not in registry_ids:
            raise ValueError(
                f"crosswalk target is absent from registry: {entry.id_contaminant}"
            )
    return tuple(sorted(values, key=lambda entry: entry.refs_review_name))


def validate_registry_transition(
    previous: Iterable[RegistryEntry],
    proposed: Iterable[RegistryEntry],
) -> tuple[RegistryEntry, ...]:
    """Reject removal, reuse, reactivation, and noncontiguous new IDs."""

    old_entries = validate_registry_entries(previous)
    new_entries = validate_registry_entries(proposed)
    old_by_id = {entry.id_contaminant: entry for entry in old_entries}
    new_by_id = {entry.id_contaminant: entry for entry in new_entries}

    removed = sorted(set(old_by_id) - set(new_by_id))
    if removed:
        raise ValueError("issued registry IDs cannot be removed: " + ", ".join(removed))

    for contaminant_id, old_entry in old_by_id.items():
        new_entry = new_by_id[contaminant_id]
        if old_entry.id_legacy_cg != new_entry.id_legacy_cg:
            raise ValueError(f"legacy CG ID cannot change: {contaminant_id}")
        if old_entry.issued_release_id != new_entry.issued_release_id:
            raise ValueError(f"issuance release cannot change: {contaminant_id}")
        if old_entry.status is RegistryStatus.RETIRED:
            if new_entry.status is not RegistryStatus.RETIRED:
                raise ValueError(f"retired registry ID cannot reactivate: {contaminant_id}")
            if (
                old_entry.successor_id != new_entry.successor_id
                or old_entry.retired_release_id != new_entry.retired_release_id
            ):
                raise ValueError(
                    f"retired registry lifecycle cannot change: {contaminant_id}"
                )

    new_ids = sorted(
        contaminant_id_number(value)
        for value in set(new_by_id) - set(old_by_id)
    )
    highest_old = max(
        (contaminant_id_number(value) for value in old_by_id), default=0
    )
    if new_ids != list(range(highest_old + 1, highest_old + len(new_ids) + 1)):
        raise ValueError("new registry IDs must extend contiguously above the highest ID")
    return new_entries


def validate_crosswalk_transition(
    previous: Iterable[TrackedCrosswalkEntry],
    proposed: Iterable[TrackedCrosswalkEntry],
    registry_entries: Iterable[RegistryEntry],
) -> tuple[TrackedCrosswalkEntry, ...]:
    """Reject removal or retargeting of a reviewed reference label."""

    old_entries = validate_tracked_crosswalk(previous, registry_entries)
    new_entries = validate_tracked_crosswalk(proposed, registry_entries)
    new_by_label = {entry.refs_review_name: entry for entry in new_entries}
    for old_entry in old_entries:
        new_entry = new_by_label.get(old_entry.refs_review_name)
        if new_entry is None:
            raise ValueError(
                f"reviewed crosswalk label cannot be removed: "
                f"{old_entry.refs_review_name!r}"
            )
        if new_entry != old_entry:
            raise ValueError(
                f"reviewed crosswalk label cannot be retargeted or rewritten: "
                f"{old_entry.refs_review_name!r}"
            )
    return new_entries


def _csv_bytes(headers: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def serialize_registry(entries: Iterable[RegistryEntry]) -> bytes:
    """Serialize validated registry rows as deterministic UTF-8 CSV."""

    values = validate_registry_entries(entries)
    return _csv_bytes(
        REGISTRY_HEADERS,
        (
            (
                entry.id_contaminant,
                "" if entry.id_legacy_cg is None else entry.id_legacy_cg,
                entry.id_name,
                entry.status.value,
                entry.successor_id or "",
                entry.issued_release_id,
                entry.retired_release_id or "",
            )
            for entry in values
        ),
    )


def serialize_crosswalk(
    entries: Iterable[TrackedCrosswalkEntry],
    registry_entries: Iterable[RegistryEntry],
) -> bytes:
    """Serialize validated crosswalk rows as deterministic UTF-8 CSV."""

    values = validate_tracked_crosswalk(entries, registry_entries)
    return _csv_bytes(
        CROSSWALK_HEADERS,
        (
            (
                entry.refs_review_name,
                entry.id_contaminant,
                entry.resolution_method.value,
                entry.reviewed_release_id,
            )
            for entry in values
        ),
    )


def _read_csv_bytes(data: bytes, expected_headers: tuple[str, ...]) -> list[list[str]]:
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("tracked CSV must not contain a UTF-8 byte-order mark")
    if not data.endswith(b"\n") or b"\r" in data:
        raise ValueError("tracked CSV must use LF newlines and end with a newline")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("tracked CSV must be valid UTF-8") from error
    try:
        rows = list(csv.reader(StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        raise ValueError("tracked CSV is malformed") from error
    if not rows or tuple(rows[0]) != expected_headers:
        found = tuple(rows[0]) if rows else ()
        raise ValueError(
            f"tracked CSV headers must be exactly {expected_headers!r}; found {found!r}"
        )
    if len(set(rows[0])) != len(rows[0]):
        raise ValueError("tracked CSV contains duplicate headers")
    for row in rows[1:]:
        if len(row) != len(expected_headers):
            raise ValueError("tracked CSV row has the wrong number of columns")
    return rows[1:]


def _optional_text(value: str) -> str | None:
    return value if value else None


def load_registry_bytes(data: bytes) -> tuple[RegistryEntry, ...]:
    """Strictly load and validate registry CSV bytes."""

    rows = _read_csv_bytes(data, REGISTRY_HEADERS)
    entries = []
    for row in rows:
        legacy_text = row[1]
        legacy_id = None
        if legacy_text:
            if not legacy_text.isascii() or not legacy_text.isdecimal():
                raise ValueError("legacy CG ID must be a canonical integer")
            legacy_id = int(legacy_text)
            if str(legacy_id) != legacy_text:
                raise ValueError("legacy CG ID must be a canonical integer")
        try:
            status = RegistryStatus(row[3])
        except ValueError as error:
            raise ValueError(f"invalid registry status: {row[3]!r}") from error
        entries.append(
            RegistryEntry(
                id_contaminant=row[0],
                id_legacy_cg=legacy_id,
                id_name=row[2],
                status=status,
                successor_id=_optional_text(row[4]),
                issued_release_id=row[5],
                retired_release_id=_optional_text(row[6]),
            )
        )
    return validate_registry_entries(entries)


def load_crosswalk_bytes(
    data: bytes,
    registry_entries: Iterable[RegistryEntry],
) -> tuple[TrackedCrosswalkEntry, ...]:
    """Strictly load and validate crosswalk CSV bytes."""

    rows = _read_csv_bytes(data, CROSSWALK_HEADERS)
    entries = []
    for row in rows:
        try:
            method = ReferenceResolutionMethod(row[2])
        except ValueError as error:
            raise ValueError(f"invalid resolution method: {row[2]!r}") from error
        entries.append(TrackedCrosswalkEntry(row[0], row[1], method, row[3]))
    return validate_tracked_crosswalk(entries, registry_entries)


def load_registry(path: Path) -> tuple[RegistryEntry, ...]:
    """Read one registry CSV path and return strictly validated records."""

    return load_registry_bytes(path.read_bytes())


def load_crosswalk(
    path: Path,
    registry_entries: Iterable[RegistryEntry],
) -> tuple[TrackedCrosswalkEntry, ...]:
    """Read one crosswalk CSV path and validate it against the registry."""

    return load_crosswalk_bytes(path.read_bytes(), registry_entries)


def propose_registry_assets(validated: ValidatedBootstrap) -> RegistryAssetProposal:
    """Convert a passing bootstrap into initial tracked asset rows."""

    if not isinstance(validated, ValidatedBootstrap):
        raise ValueError("assets require a ValidatedBootstrap result")
    if validated.report.status is not BootstrapReportStatus.PASSED:
        raise ValueError("assets require a passing bootstrap report")
    release_id = validated.compatibility.data_release_id
    identities_by_id = {
        identity.id_contaminant: identity
        for identity in validated.glossary_identities
    }
    mapping_ids = {mapping.id_contaminant for mapping in validated.id_mappings}
    if mapping_ids != set(identities_by_id):
        raise ValueError("bootstrap ID mappings and glossary identities disagree")

    registry = validate_registry_entries(
        (
            RegistryEntry(
                id_contaminant=mapping.id_contaminant,
                id_legacy_cg=mapping.id_legacy_cg,
                id_name=identities_by_id[mapping.id_contaminant].id_name,
                status=RegistryStatus.ACTIVE,
                successor_id=None,
                issued_release_id=release_id,
                retired_release_id=None,
            )
            for mapping in validated.id_mappings
        ),
        require_initial_legacy_ids=True,
    )
    crosswalk = validate_tracked_crosswalk(
        (
            TrackedCrosswalkEntry(
                refs_review_name=entry.refs_review_name,
                id_contaminant=entry.id_contaminant,
                resolution_method=entry.resolution_method,
                reviewed_release_id=release_id,
            )
            for entry in validated.reference_crosswalk
        ),
        registry,
    )
    return RegistryAssetProposal(registry, crosswalk)


def freeze_registry_assets(
    validated: ValidatedBootstrap,
    registry_dir: Path = REGISTRY_DIR,
) -> tuple[Path, Path]:
    """Atomically create, or idempotently confirm, both tracked assets."""

    proposal = propose_registry_assets(validated)
    registry_bytes = serialize_registry(proposal.registry_entries)
    crosswalk_bytes = serialize_crosswalk(
        proposal.crosswalk_entries, proposal.registry_entries
    )
    target_dir = Path(registry_dir)
    registry_path = target_dir / REGISTRY_FILENAME
    crosswalk_path = target_dir / CROSSWALK_FILENAME

    if target_dir.exists():
        if not target_dir.is_dir():
            raise ValueError(f"registry path is not a directory: {target_dir}")
        existing_names = {path.name for path in target_dir.iterdir()}
        expected_names = {REGISTRY_FILENAME, CROSSWALK_FILENAME}
        if existing_names != expected_names:
            raise ValueError("tracked registry directory is partial or unexpected")
        if (
            registry_path.read_bytes() == registry_bytes
            and crosswalk_path.read_bytes() == crosswalk_bytes
        ):
            return registry_path, crosswalk_path
        raise ValueError("tracked registry assets differ; refusing to overwrite")

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{target_dir.name}-", dir=target_dir.parent)
    )
    try:
        (staging_dir / REGISTRY_FILENAME).write_bytes(registry_bytes)
        (staging_dir / CROSSWALK_FILENAME).write_bytes(crosswalk_bytes)
        staging_dir.replace(target_dir)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
    return registry_path, crosswalk_path
