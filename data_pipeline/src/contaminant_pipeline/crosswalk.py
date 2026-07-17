"""Resolve reference review labels to immutable contaminant identifiers."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .identifiers import contaminant_id_number, validate_contaminant_ids


class ReferenceResolutionMethod(StrEnum):
    """How a reference review label was resolved."""

    EXACT = "exact"
    OVERRIDE = "override"


@dataclass(frozen=True)
class GlossaryIdentity:
    """The exact glossary name and stable ID for one contaminant."""

    id_name: str
    id_contaminant: str


@dataclass(frozen=True)
class ReferenceCrosswalkEntry:
    """One distinct reference review label resolved to a stable ID."""

    refs_review_name: str
    id_contaminant: str
    resolution_method: ReferenceResolutionMethod


# These are deliberate resolutions for the current workbook's labels that do
# not exactly equal their glossary names. Runtime code never guesses variants.
REFERENCE_NAME_OVERRIDES: Mapping[str, str] = MappingProxyType(
    {
        "1,1,1,2-tetrachloroethane": "RHC-123",
        "1,1,1-trichloroethane": "RHC-142",
        "1,1,2,2-tetrachloroethane": "RHC-124",
        "1,2,4-trimethylbenzene": "RHC-147",
        "1,2-Dibromo-3-chloropropane (DBCP)": "RHC-051",
        "1,3,5-trimethylbenzene": "RHC-148",
        "2-Butanone (Methyl Ethyl Ketone)": "RHC-027",
        "Benzo(a)anthracene": "RHC-011",
        "Benzo(a)pyrene": "RHC-012",
        "Benzo(b)fluoranthene": "RHC-013",
        "Benzo(g,h,i)perylene": "RHC-014",
        "Benzo(k)fluoranthene": "RHC-015",
        "Diisopropyl ether": "RHC-074",
        "acenaphthene": "RHC-002",
        "acenaphthylene": "RHC-003",
        "benzo[k]tetraphene": "RHC-016",
        "cis-nonachlor": "RHC-106",
        "n-propylbenzene": "RHC-114",
        "tert-Bultylbenzene": "RHC-030",
        "trans-nonachlor": "RHC-107",
        "xylenes": "RHC-152",
    }
)


def _require_nonblank_text(value: object, field_name: str) -> str:
    """Return nonblank text without changing any source characters."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be nonblank text")
    return value


def build_reference_crosswalk(
    glossary_identities: Iterable[GlossaryIdentity],
    reference_labels: Iterable[object],
    overrides: Mapping[str, str],
) -> tuple[ReferenceCrosswalkEntry, ...]:
    """Resolve each distinct reference label by exact match or override."""

    identities = tuple(glossary_identities)
    names_to_ids: dict[str, str] = {}
    ambiguous_names: set[str] = set()
    glossary_ids: list[str] = []

    for identity in identities:
        if not isinstance(identity, GlossaryIdentity):
            raise ValueError("glossary identities must be GlossaryIdentity records")

        name = _require_nonblank_text(identity.id_name, "glossary name")
        contaminant_id_number(identity.id_contaminant)
        glossary_ids.append(identity.id_contaminant)

        if name in names_to_ids:
            ambiguous_names.add(name)
        else:
            names_to_ids[name] = identity.id_contaminant

    validate_contaminant_ids(glossary_ids)
    if ambiguous_names:
        names = ", ".join(repr(name) for name in sorted(ambiguous_names))
        raise ValueError(f"ambiguous glossary names: {names}")

    labels = tuple(
        _require_nonblank_text(value, "reference label")
        for value in reference_labels
    )
    distinct_labels = set(labels)

    validated_overrides: dict[str, str] = {}
    for raw_label, target_id in overrides.items():
        label = _require_nonblank_text(raw_label, "override label")
        contaminant_id_number(target_id)
        if target_id not in glossary_ids:
            raise ValueError(
                f"override target is absent from glossary identities: {target_id}"
            )
        if label in names_to_ids:
            raise ValueError(f"override replaces an exact match: {label!r}")
        if label not in distinct_labels:
            raise ValueError(f"unused override label: {label!r}")
        validated_overrides[label] = target_id

    entries: list[ReferenceCrosswalkEntry] = []
    unresolved: list[str] = []
    for label in sorted(distinct_labels):
        if label in names_to_ids:
            target_id = names_to_ids[label]
            method = ReferenceResolutionMethod.EXACT
        elif label in validated_overrides:
            target_id = validated_overrides[label]
            method = ReferenceResolutionMethod.OVERRIDE
        else:
            unresolved.append(label)
            continue

        entries.append(
            ReferenceCrosswalkEntry(
                refs_review_name=label,
                id_contaminant=target_id,
                resolution_method=method,
            )
        )

    if unresolved:
        labels_text = ", ".join(repr(label) for label in unresolved)
        raise ValueError(f"unresolved reference labels: {labels_text}")

    return tuple(entries)
