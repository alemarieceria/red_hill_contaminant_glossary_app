"""Typed canonical records for normalized contaminant data."""

from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    StringConstraints,
    model_validator,
)

from .identifiers import contaminant_id_number


class FieldOwner(StrEnum):
    """Source whose meaning controls a canonical field."""

    REGISTRY = "registry"
    GLOSSARY = "glossary"
    REFERENCES = "references"
    FOOTNOTES = "footnotes"
    PIPELINE = "pipeline"


class NullPolicy(StrEnum):
    """Whether a blank source value may normalize to ``None``."""

    REQUIRED = "required"
    UNKNOWN_ALLOWED = "unknown_allowed"


class PrimaryClass(StrEnum):
    """Allowed top-level chemical or measurement classifications."""

    ALIPHATIC = "Aliphatic"
    AROMATIC = "Aromatic"
    GLYCOL_ETHER = "Glycol ether"
    INORGANIC_COMPOUND = "Inorganic compound"
    MIXTURE = "Mixture"
    NON_COMPOUND_MEASUREMENT = "Non-compound measurement"
    PURE_ELEMENT = "Pure element"


class SecondaryClass(StrEnum):
    """Allowed second-level chemical classifications."""

    ALKANE = "Alkane"
    ALKENE = "Alkene"
    BENZENE = "Benzene"
    METAL = "Metal"
    METALLOID = "Metalloid"
    METHOD_DEFINED_ANALYTICAL_MIXTURE = "Method-defined analytical mixture"
    MIXTURE_OF_PURE_COMPOUNDS = "Mixture of pure compounds"
    NONMETAL = "Nonmetal"
    PAH = "PAH"
    TRIAZINE = "Triazine"


class TertiaryClass(StrEnum):
    """Allowed detailed chemical-family classifications."""

    ALKALI_EARTH_METAL = "Alkali earth metal"
    ALKALINE_EARTH_METAL = "Alkaline earth metal"
    ALKENYLATED = "Alkenylated"
    ALKYLATED = "Alkylated"
    ANTHRACENE = "Anthracene"
    BRANCHED = "Branched"
    CHALCOGEN = "Chalcogen (oxygen group)"
    CYCLIC = "Cyclic"
    DERIVATIZED = "Derivatized"
    HALOGEN = "Halogen"
    HALOGENATED = "Halogenated"
    LINEAR = "Linear"
    NAPHTHALENE = "Naphthalene"
    NAPHTHALENE_ALKYLATED = "Naphthalene, alkylated"
    PNICTOGEN = "Pnictogen (nitrogen group)"
    POST_TRANSITION_METAL_GROUP_13 = "Post-transition metal, group 13"
    POST_TRANSITION_METAL_GROUP_14 = "Post-transition metal, group 14"
    TRANSITION_METAL_GROUP_6 = "Transition metal (group 6)"
    TRANSITION_METAL_GROUP_7 = "Transition metal (group 7)"
    TRANSITION_METAL_GROUP_8 = "Transition metal (group 8)"
    TRANSITION_METAL_GROUP_10 = "Transition metal (group 10)"
    TRANSITION_METAL_GROUP_11 = "Transition metal (group 11)"
    TRANSITION_METAL_GROUP_12 = "Transition metal (group 12)"


class PesticideStatus(StrEnum):
    """Normalized relationship between a contaminant and pesticide use."""

    PESTICIDE = "pesticide"
    PESTICIDE_PRODUCT_CONTAMINANT = "pesticide_product_contaminant"
    NOT_PESTICIDE = "not_pesticide"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class StockholmListing(StrEnum):
    """Allowed Stockholm Convention listing descriptions."""

    ANNEX_A = "A"
    ANNEX_A_AND_C = (
        "A (as industrial chemical), C (as unintentional production)"
    )


class NotApplicable(StrEnum):
    """Explicitly states that a field does not apply to the contaminant."""

    VALUE = "not_applicable"


class SafewatersReviewMarker(StrEnum):
    """Internal marker for a Safewaters value that still needs review."""

    UNRESOLVED = "!!!!"


def _validate_nonblank_text(value: str) -> str:
    if not value or value != value.strip():
        raise ValueError("text must be nonblank with no surrounding whitespace")
    return value


def _validate_contaminant_id(value: str) -> str:
    contaminant_id_number(value)
    return value


NonBlankText = Annotated[str, AfterValidator(_validate_nonblank_text)]
ContaminantId = Annotated[str, AfterValidator(_validate_contaminant_id)]
FootnoteId = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z][A-Z0-9_-]*$"),
]
NonnegativeInteger = Annotated[StrictInt, Field(ge=0)]
PositiveInteger = Annotated[StrictInt, Field(gt=0)]
NonnegativeDecimal = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class CanonicalModel(BaseModel):
    """Shared behavior for immutable canonical values and records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class IntegerRange(CanonicalModel):
    """Inclusive nonnegative integer range with ordered endpoints."""

    lower: NonnegativeInteger
    upper: NonnegativeInteger

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("range lower value must not exceed upper value")
        return self


class RegulatoryRange(CanonicalModel):
    """Inclusive nonnegative decimal range for a regulatory value."""

    lower: NonnegativeDecimal
    upper: NonnegativeDecimal

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("range lower value must not exceed upper value")
        return self


class ActionLevel(CanonicalModel):
    """Regulatory value explicitly represented as an action level."""

    value: NonnegativeDecimal


AtomCount = NonnegativeInteger | IntegerRange | NotApplicable
BooleanOrNotApplicable = StrictBool | NotApplicable
RegulatoryValue = NonnegativeDecimal | RegulatoryRange | ActionLevel

GLOSSARY_HEADER_MAP = MappingProxyType(
    {
        "Compound name given in datasets": "id_name",
        "Compound name for sorting": "id_sort_name",
        "CG ID #": "id_legacy_cg",
        "Chemical formula": "id_chem_formula",
        "a.k.a.s": "id_aka",
        "CASRN": "id_casrn",
        "InChIKey": "id_inchikey",
        "Primary": "class_primary",
        "Secondary": "class_secondary",
        "Tertiary": "class_tertiary",
        "Aromatic": "class_aromatic",
        "BTEXMN": "class_btexmn",
        "DBP": "class_dbp",
        "Known JP-5 component": "class_jp5_component",
        "PAH": "class_pah",
        "Pesticide": "class_pesticide",
        "C": "chem_info_n_carbon",
        "N": "chem_info_n_nitrogen",
        "F": "chem_info_n_fluorine",
        "Cl": "chem_info_n_chlorine",
        "Br": "chem_info_n_bromine",
        "1° alcohols": "chem_info_n_primary_alcohol",
        "2° alcohols": "chem_info_n_secondary_alcohol",
        "3° alcohols": "chem_info_n_tertiary_alcohol",
        "Ethers": "chem_info_n_ether",
        "Ketones": "chem_info_n_ketone",
        "Aldehydes": "chem_info_n_aldehyde",
        "Esters": "chem_info_n_ester",
        "Epoxides": "chem_info_n_epoxide",
        "Amines": "chem_info_n_amine",
        "Halogenated": "chem_info_halogenated",
        "Saturated": "chem_info_saturated",
        "NPDWR MCLG (mg/L)": "reg_status_npdwr_mclg_mg_l",
        "NPDWR MCL (mg/L)": "reg_status_npdwr_mcl_mg_l",
        "NPDWR notes": "source_notes_npdwr_internal",
        "SMCL (mg/L)": "reg_status_smcl",
        "CCL5": "reg_status_ccl5",
        "HDOH MCL (mg/L)": "reg_status_hdoh_mcl_mg_l",
        "HDOH more stringent": "reg_status_hdoh_more_stringent",
        "Montreal Protocol": "reg_status_montreal_protocol",
        "Stockholm Convention": "reg_status_stockholm_convention",
        "Sources": "source_notes_sources",
        "Notes": "source_notes_general",
        "Footnotes": "source_notes_footnote_ids",
        "Immediate": "source_notes_dataset_immediate",
        "Flushing reports": "source_notes_dataset_flushing",
        "LTM plan": "source_notes_dataset_ltm",
        "EDWM plan": "source_notes_dataset_edwm",
        "SafeWaters data (old scrape)": "source_notes_safewaters_legacy",
        "SafeWaters data (checking 2026-06-22)": (
            "source_notes_safewaters_review"
        ),
    }
)

REFERENCE_HEADER_MAP = MappingProxyType(
    {
        "compound_name": "refs_review_name",
        "source": "refs_source",
        "link": "refs_url",
    }
)

FOOTNOTE_HEADER_MAP = MappingProxyType(
    {
        "id": "source_notes_footnote_id",
        "text": "source_notes_footnote_text",
    }
)

WEBSITE_DISPLAY_FIELDS = frozenset(
    {
        "id_name",
        "id_sort_name",
        "id_chem_formula",
        "id_aka",
        "id_casrn",
        "id_inchikey",
        "class_primary",
        "class_secondary",
        "class_tertiary",
        "class_aromatic",
        "class_btexmn",
        "class_dbp",
        "class_jp5_component",
        "class_pah",
        "class_pesticide",
        "chem_info_n_carbon",
        "chem_info_n_nitrogen",
        "chem_info_n_fluorine",
        "chem_info_n_chlorine",
        "chem_info_n_bromine",
        "chem_info_n_primary_alcohol",
        "chem_info_n_secondary_alcohol",
        "chem_info_n_tertiary_alcohol",
        "chem_info_n_ether",
        "chem_info_n_ketone",
        "chem_info_n_aldehyde",
        "chem_info_n_ester",
        "chem_info_n_epoxide",
        "chem_info_n_amine",
        "chem_info_halogenated",
        "chem_info_saturated",
        "reg_status_npdwr_mclg_mg_l",
        "reg_status_npdwr_mcl_mg_l",
        "reg_status_smcl",
        "reg_status_ccl5",
        "reg_status_hdoh_mcl_mg_l",
        "reg_status_montreal_protocol",
        "reg_status_stockholm_convention",
        "source_notes_sources",
        "source_notes_general",
        "source_notes_footnote_ids",
    }
)


def _canonical_field(
    *,
    owner: FieldOwner,
    public: bool,
    null_policy: NullPolicy,
    units: str | None = None,
    default: Any = ...,
) -> Any:
    metadata: dict[str, object] = {
        "owner": owner.value,
        "public": public,
        "null_policy": null_policy.value,
    }
    if units is not None:
        metadata["units"] = units
    return Field(default=default, json_schema_extra=metadata)


class ContaminantRecord(CanonicalModel):
    """One normalized glossary contaminant."""

    id_contaminant: ContaminantId = _canonical_field(
        owner=FieldOwner.REGISTRY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    id_name: NonBlankText = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    id_sort_name: NonBlankText = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    id_legacy_cg: PositiveInteger = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.REQUIRED,
    )
    id_chem_formula: NonBlankText = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    id_aka: tuple[NonBlankText, ...] | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    id_casrn: tuple[NonBlankText, ...] | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    id_inchikey: tuple[NonBlankText, ...] | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_primary: PrimaryClass = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    class_secondary: SecondaryClass | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_tertiary: TertiaryClass | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_aromatic: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_btexmn: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_dbp: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_jp5_component: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_pah: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    class_pesticide: PesticideStatus = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    chem_info_n_carbon: AtomCount = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
        units="atoms",
    )
    chem_info_n_nitrogen: AtomCount = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
        units="atoms",
    )
    chem_info_n_fluorine: AtomCount = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
        units="atoms",
    )
    chem_info_n_chlorine: AtomCount = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
        units="atoms",
    )
    chem_info_n_bromine: AtomCount = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
        units="atoms",
    )
    chem_info_n_primary_alcohol: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_secondary_alcohol: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_tertiary_alcohol: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_ether: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_ketone: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_aldehyde: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_ester: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_epoxide: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_n_amine: NonnegativeInteger | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="groups",
        default=None,
    )
    chem_info_halogenated: BooleanOrNotApplicable | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    chem_info_saturated: BooleanOrNotApplicable | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    reg_status_npdwr_mclg_mg_l: NonnegativeDecimal | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="mg/L",
        default=None,
    )
    reg_status_npdwr_mcl_mg_l: NonnegativeDecimal | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="mg/L",
        default=None,
    )
    source_notes_npdwr_internal: NonBlankText | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    reg_status_smcl: RegulatoryValue | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="mg/L or pH",
        default=None,
    )
    reg_status_ccl5: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    reg_status_hdoh_mcl_mg_l: RegulatoryValue | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        units="mg/L",
        default=None,
    )
    reg_status_hdoh_more_stringent: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    reg_status_montreal_protocol: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    reg_status_stockholm_convention: StockholmListing | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_sources: NonBlankText | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_general: NonBlankText | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_footnote_ids: tuple[FootnoteId, ...] | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=True,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_dataset_immediate: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_dataset_flushing: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_dataset_ltm: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_dataset_edwm: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_safewaters_legacy: StrictBool | None = _canonical_field(
        owner=FieldOwner.GLOSSARY,
        public=False,
        null_policy=NullPolicy.UNKNOWN_ALLOWED,
        default=None,
    )
    source_notes_safewaters_review: StrictBool | SafewatersReviewMarker | None = (
        _canonical_field(
            owner=FieldOwner.GLOSSARY,
            public=False,
            null_policy=NullPolicy.UNKNOWN_ALLOWED,
            default=None,
        )
    )


class ReferenceRecord(CanonicalModel):
    """One normalized reference joined to a contaminant by stable ID."""

    id_contaminant: ContaminantId = _canonical_field(
        owner=FieldOwner.REGISTRY,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    refs_review_name: NonBlankText = _canonical_field(
        owner=FieldOwner.REFERENCES,
        public=False,
        null_policy=NullPolicy.REQUIRED,
    )
    refs_source: NonBlankText = _canonical_field(
        owner=FieldOwner.REFERENCES,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    refs_url: HttpUrl = _canonical_field(
        owner=FieldOwner.REFERENCES,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )


class FootnoteRecord(CanonicalModel):
    """One normalized footnote definition."""

    source_notes_footnote_id: FootnoteId = _canonical_field(
        owner=FieldOwner.FOOTNOTES,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )
    source_notes_footnote_text: NonBlankText = _canonical_field(
        owner=FieldOwner.FOOTNOTES,
        public=True,
        null_policy=NullPolicy.REQUIRED,
    )


def public_field_names(model_type: type[CanonicalModel]) -> tuple[str, ...]:
    """Return public fields in their declared order."""

    return tuple(
        name
        for name, field in model_type.model_fields.items()
        if (field.json_schema_extra or {}).get("public") is True
    )
