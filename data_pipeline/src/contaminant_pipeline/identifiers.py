"""Rules for immutable Red Hill contaminant identifiers."""

from collections.abc import Iterable
from dataclasses import dataclass
import re


CONTAMINANT_ID_PATTERN = re.compile(r"^RHC-([0-9]{3})$")
MAX_CONTAMINANT_ID = 999
INITIAL_LEGACY_ID_MIN = 1
INITIAL_LEGACY_ID_MAX = 152
INITIAL_LEGACY_IDS = frozenset(
    range(INITIAL_LEGACY_ID_MIN, INITIAL_LEGACY_ID_MAX + 1)
)


@dataclass(frozen=True)
class BootstrapIdMapping:
    """One deterministic legacy-to-stable identifier mapping."""

    id_legacy_cg: int
    id_contaminant: str


# Validation function, used during every release
def contaminant_id_number(value: object) -> int:
    """Return an identifier's numeric portion or raise ``ValueError``."""

    # Is this value text?
    if not isinstance(value, str):
        raise ValueError("contaminant ID must be text")

    # Does it have the right form?
    match = CONTAMINANT_ID_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("contaminant ID must have the form RHC-NNN")

    # If so, what is its numeric portion?
    number = int(match.group(1))

    # Reject if value is zero, since RHC-000 is not a valid contaminant ID
    if number == 0:
        raise ValueError("RHC-000 is not a valid contaminant ID")

    return number


# Validation function, used during every release
def validate_contaminant_ids(values: Iterable[object]) -> tuple[str, ...]:
    """Validate a collection of unique IDs while preserving its order."""

    # Preserve original order of values
    validated: list[str] = []
    # Store unique values to detect duplicates
    seen: set[str] = set()

    # Check each value for validity and uniqueness
    for value in values:
        # Is it a valid contaminant ID?
        contaminant_id_number(value)
        assert isinstance(value, str)  # Narrowed by contaminant_id_number.
        # Has it already been seen?
        if value in seen:
            raise ValueError(f"duplicate contaminant ID: {value}")
        # If not, add it to the seen set and validated list
        seen.add(value)
        validated.append(value)

    return tuple(validated)


def bootstrap_contaminant_ids(
    legacy_ids: Iterable[object],
) -> tuple[BootstrapIdMapping, ...]:
    """Map the complete initial legacy ID set to stable contaminant IDs."""

    validated_legacy_ids: list[int] = []
    seen: set[int] = set()

    for value in legacy_ids:
        if type(value) is not int:
            raise ValueError("legacy CG ID must be an integer")
        if value not in INITIAL_LEGACY_IDS:
            raise ValueError(
                "legacy CG ID must be between "
                f"{INITIAL_LEGACY_ID_MIN} and {INITIAL_LEGACY_ID_MAX}: {value}"
            )
        if value in seen:
            raise ValueError(f"duplicate legacy CG ID: {value}")

        seen.add(value)
        validated_legacy_ids.append(value)

    missing_ids = sorted(INITIAL_LEGACY_IDS - seen)
    if missing_ids:
        missing_text = ", ".join(str(value) for value in missing_ids)
        raise ValueError(f"incomplete legacy CG ID set; missing: {missing_text}")

    mappings = tuple(
        BootstrapIdMapping(
            id_legacy_cg=legacy_id,
            id_contaminant=f"RHC-{legacy_id:03d}",
        )
        for legacy_id in sorted(validated_legacy_ids)
    )
    validate_contaminant_ids(
        mapping.id_contaminant for mapping in mappings
    )
    return mappings


# Used only when issuing a new ID for a new contaminant, a split, or a corrected
# compound identity. Retired IDs must remain in issued_ids so they are never
# reused. This function is not needed when a release issues no IDs.
def next_contaminant_id(issued_ids: Iterable[object]) -> str:
    """Return the ID after the highest ID ever issued.

    ``issued_ids`` must include retired IDs so that they cannot be reused.
    """

    # Validate the issued IDs
    validated = validate_contaminant_ids(issued_ids)
    # Use the highest issued number, not input order or gaps. Start at one when
    # the registry is empty.
    next_number = max(
        (contaminant_id_number(value) for value in validated), default=0
    ) + 1

    # Check if the next number exceeds the maximum allowed contaminant ID
    if next_number > MAX_CONTAMINANT_ID:
        raise ValueError("the RHC-NNN contaminant ID range is exhausted")

    # Return the next zero-padded RHC-NNN identifier.
    return f"RHC-{next_number:03d}"
