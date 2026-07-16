"""Rules for immutable Red Hill contaminant identifiers."""

from collections.abc import Iterable
import re


CONTAMINANT_ID_PATTERN = re.compile(r"^RHC-([0-9]{3})$")
MAX_CONTAMINANT_ID = 999


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


# Used only when issuing a new ID for a new contaminant, a split, or a corrected compound identity. Retired IDs must remain in issued_ids so they are never reused. This function is not needed when a release issues no IDs.
def next_contaminant_id(issued_ids: Iterable[object]) -> str:
    """Return the ID after the highest ID ever issued.

    ``issued_ids`` must include retired IDs so that they cannot be reused.
    """

    # Validate the issued IDs
    validated = validate_contaminant_ids(issued_ids)
    # Determine the next number to use by finding the maximum numeric portion of the validated IDs and adding 1. If there are no validated IDs, default to 0 and add 1.
    next_number = max(
        (contaminant_id_number(value) for value in validated), default=0
    ) + 1

    # Check if the next number exceeds the maximum allowed contaminant ID
    if next_number > MAX_CONTAMINANT_ID:
        raise ValueError("the RHC-NNN contaminant ID range is exhausted")

    # Return the next contaminant ID in the format "RHC-NNN", where NNN is a zero-padded three-digit number
    return f"RHC-{next_number:03d}"
