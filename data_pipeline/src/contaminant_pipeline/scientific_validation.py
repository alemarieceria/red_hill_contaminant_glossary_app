"""Validate scientific values after identities and relationships resolve."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from types import MappingProxyType

from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries
from pydantic import HttpUrl, TypeAdapter, ValidationError

from .config import (
    GLOSSARY_SHEET_NAME,
    GLOSSARY_TABLE_NAME,
    REFERENCES_SHEET_NAME,
    WORKBOOK_SCHEMA_VERSION,
)
from .schemas import (
    ActionLevel,
    GLOSSARY_HEADER_MAP,
    IntegerRange,
    NotApplicable,
    PrimaryClass,
    REFERENCE_HEADER_MAP,
    RegulatoryRange,
    SecondaryClass,
    StockholmListing,
    TertiaryClass,
)
from .validate import (
    ValidatedIdentityRelationships,
    ValidationCategory,
    ValidationFinding,
    ValidationSeverity,
    sort_validation_findings,
)


@dataclass(frozen=True)
class ValidatedScientificContaminant:
    """One glossary row whose literal scientific values satisfy schema 1.0.0."""

    source_row: int
    id_contaminant: str
    raw_values: Mapping[str, object]
    formulas: Mapping[str, str | None]
    parsed_values: Mapping[str, object]


@dataclass(frozen=True)
class ValidatedScientificReference:
    """One reference row whose source text and URL satisfy schema 1.0.0."""

    source_row: int
    id_contaminant: str
    refs_review_name: str
    raw_values: Mapping[str, object]
    formulas: Mapping[str, str | None]
    parsed_values: Mapping[str, object]


@dataclass(frozen=True)
class ValidatedScientificFields:
    """Immutable scientific-value gate output for later Phase 3 stages."""

    identity_relationships: ValidatedIdentityRelationships
    data_release_id: str
    schema_version: str
    contaminants: tuple[ValidatedScientificContaminant, ...]
    references: tuple[ValidatedScientificReference, ...]
    findings: tuple[ValidationFinding, ...]


@dataclass(frozen=True)
class ScientificFieldInspection:
    """Read-only parsed records and findings, including blocking errors."""

    identity_relationships: ValidatedIdentityRelationships
    data_release_id: str
    schema_version: str
    contaminants: tuple[ValidatedScientificContaminant, ...]
    references: tuple[ValidatedScientificReference, ...]
    findings: tuple[ValidationFinding, ...]


class ScientificFieldValidationError(ValueError):
    """Raised when scientific/source fields contain error findings."""

    def __init__(self, findings) -> None:
        self.findings = sort_validation_findings(findings)
        message = "; ".join(
            f"{finding.code}: {finding.message}" for finding in self.findings
        )
        super().__init__(message)


_HTTP_URL = TypeAdapter(HttpUrl)
_MULTI_VALUE_DELIMITER = " | "
_NOT_APPLICABLE_TOKENS = frozenset({"NA", "N/A"})
_NOT_APPLICABLE_PRIMARY_CLASSES = frozenset(
    {PrimaryClass.MIXTURE.value, PrimaryClass.NON_COMPOUND_MEASUREMENT.value}
)
_IDENTIFIER_NOT_APPLICABLE_EXCEPTIONS = MappingProxyType(
    {"id_inchikey": frozenset({"RHC-071"})}
)
_INCHIKEY_PATTERN = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
_CASRN_PATTERN = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
_ATOM_RANGE_PATTERN = re.compile(r"^(\d+) - (\d+)$")
_FORMULA_PATTERN = re.compile(
    r"^(?P<body>(?:[A-Z][a-z]?(?:[1-9]\d*)?)+)"
    r"(?: (?P<charge>(?:[1-9]\d*)?[+\-−]))?$"
)
_FORMULA_ATOM_PATTERN = re.compile(r"([A-Z][a-z]?)([1-9]\d*)?")
_ELEMENT_SYMBOLS = frozenset(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co "
    "Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb "
    "Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re "
    "Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es "
    "Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split()
)

_REQUIRED_TEXT_FIELDS = frozenset({"id_sort_name"})
_OPTIONAL_TEXT_FIELDS = frozenset(
    {
        "source_notes_npdwr_internal",
        "source_notes_sources",
        "source_notes_general",
    }
)
_ENUM_FIELDS = MappingProxyType(
    {
        "class_primary": PrimaryClass,
        "class_secondary": SecondaryClass,
        "class_tertiary": TertiaryClass,
        "reg_status_stockholm_convention": StockholmListing,
    }
)
_REQUIRED_ENUM_FIELDS = frozenset({"class_primary"})
_BOOLEAN_FIELDS = frozenset(
    {
        "class_aromatic",
        "class_btexmn",
        "class_dbp",
        "class_jp5_component",
        "class_pah",
        "reg_status_ccl5",
        "reg_status_hdoh_more_stringent",
        "reg_status_montreal_protocol",
        "source_notes_dataset_immediate",
        "source_notes_dataset_flushing",
        "source_notes_dataset_ltm",
        "source_notes_dataset_edwm",
        "source_notes_safewaters_legacy",
    }
)
_ATOM_COUNT_FIELDS = frozenset(
    {
        "chem_info_n_carbon",
        "chem_info_n_nitrogen",
        "chem_info_n_fluorine",
        "chem_info_n_chlorine",
        "chem_info_n_bromine",
    }
)
_GROUP_COUNT_FIELDS = frozenset(
    {
        "chem_info_n_primary_alcohol",
        "chem_info_n_secondary_alcohol",
        "chem_info_n_tertiary_alcohol",
        "chem_info_n_ether",
        "chem_info_n_ketone",
        "chem_info_n_aldehyde",
        "chem_info_n_ester",
        "chem_info_n_epoxide",
        "chem_info_n_amine",
    }
)
_BOOLEAN_OR_NOT_APPLICABLE_FIELDS = frozenset(
    {"chem_info_halogenated", "chem_info_saturated"}
)
_ORDINARY_REGULATORY_FIELDS = frozenset(
    {"reg_status_npdwr_mclg_mg_l", "reg_status_npdwr_mcl_mg_l"}
)


def _sheet_cells(snapshot, sheet_name: str):
    sheet = next(sheet for sheet in snapshot.sheets if sheet.name == sheet_name)
    return sheet, {
        coordinate_to_tuple(cell.coordinate): cell for cell in sheet.cells
    }


def _extract_glossary_rows(validated: ValidatedIdentityRelationships):
    snapshot = validated.workbook_contract.raw_pair.glossary_snapshot
    sheet, cells = _sheet_cells(snapshot, GLOSSARY_SHEET_NAME)
    table = next(table for table in sheet.tables if table.name == GLOSSARY_TABLE_NAME)
    min_column, header_row, max_column, _ = range_boundaries(table.reference)
    columns_by_header = {
        cells[(header_row, column)].value: column
        for column in range(min_column, max_column + 1)
    }
    columns = {
        canonical: columns_by_header[header]
        for header, canonical in GLOSSARY_HEADER_MAP.items()
    }
    extracted = []
    for identity in validated.glossary_identities:
        raw_values = {}
        formulas = {}
        for canonical, column in columns.items():
            cell = cells.get((identity.source_row, column))
            raw_values[canonical] = cell.value if cell is not None else None
            formulas[canonical] = cell.formula if cell is not None else None
        extracted.append(
            (
                identity.source_row,
                identity.id_contaminant,
                MappingProxyType(raw_values),
                MappingProxyType(formulas),
            )
        )
    return tuple(extracted)


def _extract_reference_rows(validated: ValidatedIdentityRelationships):
    snapshot = validated.workbook_contract.raw_pair.references_snapshot
    sheet, cells = _sheet_cells(snapshot, REFERENCES_SHEET_NAME)
    columns_by_header = {
        cell.value: column
        for (row, column), cell in cells.items()
        if row == 1 and cell.value in REFERENCE_HEADER_MAP
    }
    columns = {
        canonical: columns_by_header[header]
        for header, canonical in REFERENCE_HEADER_MAP.items()
    }
    extracted = []
    for relationship in validated.reference_relationships:
        raw_values = {}
        formulas = {}
        for canonical, column in columns.items():
            cell = cells.get((relationship.source_row, column))
            raw_values[canonical] = cell.value if cell is not None else None
            formulas[canonical] = cell.formula if cell is not None else None
        extracted.append(
            (
                relationship.source_row,
                relationship.id_contaminant,
                relationship.refs_review_name,
                MappingProxyType(raw_values),
                MappingProxyType(formulas),
            )
        )
    return tuple(extracted)


def _finding(
    code: str,
    message: str,
    *,
    workbook: str | None = None,
    sheet: str | None = None,
    source_row: int | None = None,
    canonical_field: str | None = None,
    id_contaminant: str | None = None,
    source_value: object = None,
    category: ValidationCategory = ValidationCategory.SCIENTIFIC,
    severity: ValidationSeverity = ValidationSeverity.ERROR,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        category=category,
        severity=severity,
        message=message,
        workbook=workbook,
        sheet=sheet,
        source_row=source_row,
        canonical_field=canonical_field,
        id_contaminant=id_contaminant,
        source_value=repr(source_value),
    )


def _strict_text(value: object, *, required: bool) -> str | None:
    if value is None or value == "":
        if not required:
            return None
        raise ValueError("must be literal nonblank text without surrounding whitespace")
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("must be literal nonblank text without surrounding whitespace")
    return value


def _split_literal_values(value: object) -> tuple[str, ...]:
    text = _strict_text(value, required=True)
    assert text is not None
    if "|" in text and _MULTI_VALUE_DELIMITER not in text:
        raise ValueError("must use the literal ' | ' multi-value delimiter")
    tokens = tuple(text.split(_MULTI_VALUE_DELIMITER))
    if any(not token or token != token.strip() for token in tokens):
        raise ValueError("contains a blank token or token whitespace")
    if len(set(tokens)) != len(tokens):
        raise ValueError("contains a duplicate token")
    return tokens


def _not_applicable_allowed(
    canonical_field: str, id_contaminant: str, primary_value: object
) -> bool:
    return (
        primary_value in _NOT_APPLICABLE_PRIMARY_CLASSES
        or id_contaminant
        in _IDENTIFIER_NOT_APPLICABLE_EXCEPTIONS.get(
            canonical_field, frozenset()
        )
    )


def _parse_identifier_tokens(
    value: object,
    *,
    canonical_field: str,
    id_contaminant: str,
    primary_value: object,
    validator,
    required: bool,
):
    if value is None:
        if required:
            raise ValueError("is required and may not be blank")
        return None
    if value in _NOT_APPLICABLE_TOKENS:
        if not _not_applicable_allowed(
            canonical_field, id_contaminant, primary_value
        ):
            raise ValueError(
                "not-applicable is allowed only for a mixture, a non-compound "
                "measurement, or a documented stable-ID exception"
            )
        return NotApplicable.VALUE
    tokens = _split_literal_values(value)
    if any(token in _NOT_APPLICABLE_TOKENS for token in tokens):
        raise ValueError("may not mix a not-applicable token with real values")
    for token in tokens:
        validator(token)
    return tokens


def _validate_casrn(token: str) -> None:
    match = _CASRN_PATTERN.fullmatch(token)
    if match is None:
        raise ValueError("must use canonical CASRN syntax")
    digits = match.group(1) + match.group(2)
    expected = sum(
        multiplier * int(digit)
        for multiplier, digit in enumerate(reversed(digits), start=1)
    ) % 10
    if expected != int(match.group(3)):
        raise ValueError("has an invalid CASRN check digit")


def _validate_inchikey(token: str) -> None:
    if _INCHIKEY_PATTERN.fullmatch(token) is None:
        raise ValueError("must use the uppercase 14-10-1 InChIKey structure")


def _validate_formula_token(token: str) -> None:
    match = _FORMULA_PATTERN.fullmatch(token)
    if match is None:
        raise ValueError("has unsupported chemical-formula syntax")
    body = match.group("body")
    atoms = tuple(_FORMULA_ATOM_PATTERN.finditer(body))
    if "".join(atom.group(0) for atom in atoms) != body:
        raise ValueError("has unsupported chemical-formula syntax")
    unknown = tuple(atom.group(1) for atom in atoms if atom.group(1) not in _ELEMENT_SYMBOLS)
    if unknown:
        raise ValueError(f"contains unknown element symbol {unknown[0]!r}")


def _parse_enum(value: object, enum_type, *, required: bool):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError("must use one exact allowed text value")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError("must use one exact allowed text value") from error


def _parse_optional_boolean(value: object):
    if value is None:
        return None
    if type(value) is not bool:
        raise ValueError("must be a literal Boolean or blank")
    return value


def _parse_pesticide_source(value: object):
    if value is None or type(value) is bool:
        return value
    if isinstance(value, str) and value in {"Contaminant", "N/A"}:
        return value
    raise ValueError(
        "must be Boolean, blank, 'Contaminant', or 'N/A'; relationship "
        "semantics are checked in 3.4"
    )


def _parse_atom_count(value: object):
    if type(value) is int and value >= 0:
        return value
    if value == "NA":
        return NotApplicable.VALUE
    if isinstance(value, str):
        match = _ATOM_RANGE_PATTERN.fullmatch(value)
        if match is not None:
            lower, upper = (int(match.group(1)), int(match.group(2)))
            if lower <= upper:
                return IntegerRange(lower=lower, upper=upper)
    raise ValueError(
        "must be a nonnegative integer, an ordered 'N - N' range, or 'NA'"
    )


def _parse_group_count(value: object):
    if value is None:
        return None
    if type(value) is int and value >= 0:
        return value
    raise ValueError("must be a literal nonnegative integer or blank")


def _parse_boolean_or_not_applicable(value: object):
    if value is None or type(value) is bool:
        return value
    if value == "N/A":
        return NotApplicable.VALUE
    raise ValueError("must be a literal Boolean, blank, or 'N/A'")


def _parse_nonnegative_decimal(value: object):
    if value is None:
        return None
    if type(value) not in {int, float, Decimal}:
        raise ValueError("must be a finite nonnegative number or blank")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("must be a finite nonnegative number or blank") from error
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("must be a finite nonnegative number or blank")
    return parsed


def _parse_smcl(value: object):
    if value == "6.5-8.5":
        return RegulatoryRange(lower=Decimal("6.5"), upper=Decimal("8.5"))
    return _parse_nonnegative_decimal(value)


def _parse_hdoh(value: object):
    action_levels = {"AL = 0.015": "0.015", "AL = 1.3": "1.3"}
    if value in action_levels:
        return ActionLevel(value=Decimal(action_levels[value]))
    return _parse_nonnegative_decimal(value)


def _parse_safewaters_review(value: object):
    if value is None or type(value) is bool or value == "!!!!":
        return value
    raise ValueError("must be a literal Boolean, blank, or the '!!!!' marker")


def _parse_glossary_value(
    canonical_field: str,
    value: object,
    *,
    id_contaminant: str,
    primary_value: object,
):
    if canonical_field in _REQUIRED_TEXT_FIELDS:
        return _strict_text(value, required=True)
    if canonical_field in _OPTIONAL_TEXT_FIELDS:
        return _strict_text(value, required=False)
    if canonical_field == "id_aka":
        return None if value is None else _split_literal_values(value)
    if canonical_field == "id_chem_formula":
        parsed = _parse_identifier_tokens(
            value,
            canonical_field=canonical_field,
            id_contaminant=id_contaminant,
            primary_value=primary_value,
            validator=_validate_formula_token,
            required=True,
        )
        return value if isinstance(parsed, tuple) else parsed
    if canonical_field == "id_casrn":
        return _parse_identifier_tokens(
            value,
            canonical_field=canonical_field,
            id_contaminant=id_contaminant,
            primary_value=primary_value,
            validator=_validate_casrn,
            required=False,
        )
    if canonical_field == "id_inchikey":
        return _parse_identifier_tokens(
            value,
            canonical_field=canonical_field,
            id_contaminant=id_contaminant,
            primary_value=primary_value,
            validator=_validate_inchikey,
            required=False,
        )
    if canonical_field in _ENUM_FIELDS:
        return _parse_enum(
            value,
            _ENUM_FIELDS[canonical_field],
            required=canonical_field in _REQUIRED_ENUM_FIELDS,
        )
    if canonical_field in _BOOLEAN_FIELDS:
        return _parse_optional_boolean(value)
    if canonical_field == "class_pesticide":
        return _parse_pesticide_source(value)
    if canonical_field in _ATOM_COUNT_FIELDS:
        return _parse_atom_count(value)
    if canonical_field in _GROUP_COUNT_FIELDS:
        return _parse_group_count(value)
    if canonical_field in _BOOLEAN_OR_NOT_APPLICABLE_FIELDS:
        return _parse_boolean_or_not_applicable(value)
    if canonical_field in _ORDINARY_REGULATORY_FIELDS:
        return _parse_nonnegative_decimal(value)
    if canonical_field == "reg_status_smcl":
        return _parse_smcl(value)
    if canonical_field == "reg_status_hdoh_mcl_mg_l":
        return _parse_hdoh(value)
    if canonical_field == "source_notes_safewaters_review":
        return _parse_safewaters_review(value)
    raise KeyError(canonical_field)


_VALIDATED_GLOSSARY_FIELDS = tuple(
    field
    for field in GLOSSARY_HEADER_MAP.values()
    if field
    not in {"id_name", "id_legacy_cg", "source_notes_footnote_ids"}
)


def _validate_glossary_rows(validated: ValidatedIdentityRelationships):
    findings = []
    records = []
    workbook_name = validated.workbook_contract.raw_pair.glossary_snapshot.path.name
    for source_row, id_contaminant, raw_values, formulas in _extract_glossary_rows(
        validated
    ):
        parsed = {}
        primary_value = raw_values["class_primary"]
        for canonical_field in _VALIDATED_GLOSSARY_FIELDS:
            value = raw_values[canonical_field]
            try:
                parsed_value = _parse_glossary_value(
                    canonical_field,
                    value,
                    id_contaminant=id_contaminant,
                    primary_value=primary_value,
                )
                parsed[canonical_field] = parsed_value
                if canonical_field == "source_notes_sources" and value in {None, ""}:
                    findings.append(
                        _finding(
                            "pending_source_notes_sources",
                            "source_notes_sources is intentionally blank or pending; "
                            "canonical value remains null",
                            workbook=workbook_name,
                            sheet=GLOSSARY_SHEET_NAME,
                            source_row=source_row,
                            canonical_field=canonical_field,
                            id_contaminant=id_contaminant,
                            source_value=value,
                            severity=ValidationSeverity.WARNING,
                        )
                    )
                if canonical_field in {"id_casrn", "id_inchikey"}:
                    if value is None:
                        findings.append(
                            _finding(
                                f"pending_{canonical_field}",
                                f"{canonical_field} is blank/unknown and needs "
                                "completeness review",
                                workbook=workbook_name,
                                sheet=GLOSSARY_SHEET_NAME,
                                source_row=source_row,
                                canonical_field=canonical_field,
                                id_contaminant=id_contaminant,
                                source_value=value,
                                severity=ValidationSeverity.WARNING,
                            )
                        )
                    elif parsed_value is NotApplicable.VALUE:
                        findings.append(
                            _finding(
                                f"unverified_{canonical_field}_not_applicable",
                                f"{canonical_field} not-applicable is permitted but "
                                "still needs a reviewed per-ID rationale",
                                workbook=workbook_name,
                                sheet=GLOSSARY_SHEET_NAME,
                                source_row=source_row,
                                canonical_field=canonical_field,
                                id_contaminant=id_contaminant,
                                source_value=value,
                                severity=ValidationSeverity.WARNING,
                            )
                        )
            except (KeyError, TypeError, ValueError) as error:
                findings.append(
                    _finding(
                        f"invalid_{canonical_field}",
                        f"{canonical_field} {error}",
                        workbook=workbook_name,
                        sheet=GLOSSARY_SHEET_NAME,
                        source_row=source_row,
                        canonical_field=canonical_field,
                        id_contaminant=id_contaminant,
                        source_value=value,
                    )
                )
        records.append(
            ValidatedScientificContaminant(
                source_row=source_row,
                id_contaminant=id_contaminant,
                raw_values=raw_values,
                formulas=formulas,
                parsed_values=MappingProxyType(parsed),
            )
        )
    records.sort(key=lambda record: record.id_contaminant)
    return tuple(records), tuple(findings)


def _validate_reference_rows(validated: ValidatedIdentityRelationships):
    findings = []
    records = []
    workbook_name = validated.workbook_contract.raw_pair.references_snapshot.path.name
    for source_row, id_contaminant, review_name, raw_values, formulas in (
        _extract_reference_rows(validated)
    ):
        parsed = {}
        for canonical_field in ("refs_source", "refs_url"):
            value = raw_values[canonical_field]
            try:
                text = _strict_text(value, required=True)
                assert text is not None
                if canonical_field == "refs_url":
                    try:
                        parsed[canonical_field] = str(_HTTP_URL.validate_python(text))
                    except ValidationError as error:
                        raise ValueError(
                            "must be an absolute http or https URL with a host"
                        ) from error
                else:
                    parsed[canonical_field] = text
            except (TypeError, ValueError) as error:
                findings.append(
                    _finding(
                        f"invalid_{canonical_field}",
                        f"{canonical_field} {error}",
                        workbook=workbook_name,
                        sheet=REFERENCES_SHEET_NAME,
                        source_row=source_row,
                        canonical_field=canonical_field,
                        id_contaminant=id_contaminant,
                        source_value=value,
                        category=ValidationCategory.REFERENCES,
                    )
                )
        records.append(
            ValidatedScientificReference(
                source_row=source_row,
                id_contaminant=id_contaminant,
                refs_review_name=review_name,
                raw_values=raw_values,
                formulas=formulas,
                parsed_values=MappingProxyType(parsed),
            )
        )
    records.sort(key=lambda record: record.source_row)
    return tuple(records), tuple(findings)


def inspect_scientific_fields(
    identity_relationships: ValidatedIdentityRelationships,
) -> ScientificFieldInspection:
    """Inspect schema-1.0.0 values without hiding safely collected errors."""

    if not isinstance(identity_relationships, ValidatedIdentityRelationships):
        raise ScientificFieldValidationError(
            (
                _finding(
                    "invalid_identity_relationships",
                    "scientific validation requires ValidatedIdentityRelationships",
                ),
            )
        )
    if identity_relationships.schema_version != WORKBOOK_SCHEMA_VERSION:
        raise ScientificFieldValidationError(
            (
                _finding(
                    "unsupported_scientific_schema",
                    "scientific validation has no rules for schema "
                    f"{identity_relationships.schema_version!r}",
                ),
            )
        )

    try:
        contaminants, contaminant_findings = _validate_glossary_rows(
            identity_relationships
        )
        references, reference_findings = _validate_reference_rows(
            identity_relationships
        )
    except (KeyError, StopIteration, ValueError) as error:
        raise ScientificFieldValidationError(
            (
                _finding(
                    "invalid_scientific_source_structure",
                    f"validated source structure cannot be read: {error}",
                ),
            )
        ) from error

    findings = sort_validation_findings(
        (*contaminant_findings, *reference_findings)
    )
    return ScientificFieldInspection(
        identity_relationships=identity_relationships,
        data_release_id=identity_relationships.data_release_id,
        schema_version=identity_relationships.schema_version,
        contaminants=contaminants,
        references=references,
        findings=findings,
    )


def validate_scientific_fields(
    identity_relationships: ValidatedIdentityRelationships,
) -> ValidatedScientificFields:
    """Validate schema-1.0.0 values without changing authoritative sources."""

    inspection = inspect_scientific_fields(identity_relationships)
    if any(
        finding.severity is ValidationSeverity.ERROR
        for finding in inspection.findings
    ):
        raise ScientificFieldValidationError(inspection.findings)

    return ValidatedScientificFields(
        identity_relationships=inspection.identity_relationships,
        data_release_id=inspection.data_release_id,
        schema_version=inspection.schema_version,
        contaminants=inspection.contaminants,
        references=inspection.references,
        findings=inspection.findings,
    )
