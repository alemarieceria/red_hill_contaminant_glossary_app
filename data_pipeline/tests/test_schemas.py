from decimal import Decimal
import unittest

from pydantic import ValidationError

from contaminant_pipeline.schemas import (
    ActionLevel,
    ContaminantRecord,
    FieldOwner,
    FOOTNOTE_HEADER_MAP,
    FootnoteRecord,
    GLOSSARY_HEADER_MAP,
    IntegerRange,
    NotApplicable,
    NullPolicy,
    PesticideStatus,
    PrimaryClass,
    REFERENCE_HEADER_MAP,
    ReferenceRecord,
    RegulatoryRange,
    SafewatersReviewMarker,
    SecondaryClass,
    StockholmListing,
    TertiaryClass,
    WEBSITE_DISPLAY_FIELDS,
    public_field_names,
)


def valid_contaminant_values() -> dict[str, object]:
    return {
        "id_contaminant": "RHC-001",
        "id_name": "Example compound",
        "id_sort_name": "Example compound",
        "id_legacy_cg": 1,
        "id_chem_formula": "C2H6O",
        "class_primary": "Aliphatic",
        "class_pesticide": "not_pesticide",
        "chem_info_n_carbon": 2,
        "chem_info_n_nitrogen": 0,
        "chem_info_n_fluorine": 0,
        "chem_info_n_chlorine": 0,
        "chem_info_n_bromine": 0,
    }


class SchemaEnumTests(unittest.TestCase):
    def test_controlled_values_match_the_contract(self) -> None:
        self.assertEqual(
            {member.value for member in PrimaryClass},
            {
                "Aliphatic",
                "Aromatic",
                "Glycol ether",
                "Inorganic compound",
                "Mixture",
                "Non-compound measurement",
                "Pure element",
            },
        )
        self.assertEqual(len(SecondaryClass), 10)
        self.assertEqual(len(TertiaryClass), 23)
        self.assertEqual(
            {member.value for member in PesticideStatus},
            {
                "pesticide",
                "pesticide_product_contaminant",
                "not_pesticide",
                "unknown",
                "not_applicable",
            },
        )
        self.assertEqual(
            {member.value for member in StockholmListing},
            {
                "A",
                "A (as industrial chemical), C (as unintentional production)",
            },
        )

    def test_maps_source_headers_to_grouped_canonical_names(self) -> None:
        self.assertEqual(len(GLOSSARY_HEADER_MAP), 50)
        self.assertEqual(GLOSSARY_HEADER_MAP["Compound name given in datasets"], "id_name")
        self.assertEqual(GLOSSARY_HEADER_MAP["Cl"], "chem_info_n_chlorine")
        self.assertEqual(
            GLOSSARY_HEADER_MAP["NPDWR MCL (mg/L)"],
            "reg_status_npdwr_mcl_mg_l",
        )
        self.assertEqual(GLOSSARY_HEADER_MAP["Notes"], "source_notes_general")
        self.assertEqual(REFERENCE_HEADER_MAP["link"], "refs_url")
        self.assertEqual(
            FOOTNOTE_HEADER_MAP["text"], "source_notes_footnote_text"
        )
        self.assertEqual(
            set(GLOSSARY_HEADER_MAP.values()),
            set(ContaminantRecord.model_fields) - {"id_contaminant"},
        )
        self.assertEqual(
            set(REFERENCE_HEADER_MAP.values()),
            set(ReferenceRecord.model_fields) - {"id_contaminant"},
        )
        self.assertEqual(
            set(FOOTNOTE_HEADER_MAP.values()),
            set(FootnoteRecord.model_fields),
        )
        for name in GLOSSARY_HEADER_MAP.values():
            with self.subTest(name=name):
                self.assertTrue(
                    name.startswith(
                        ("id_", "class_", "chem_info_", "reg_status_", "source_notes_")
                    )
                )


class SupportingValueTests(unittest.TestCase):
    def test_accepts_ordered_ranges_and_action_levels(self) -> None:
        self.assertEqual(IntegerRange(lower=1, upper=3).upper, 3)
        self.assertEqual(
            RegulatoryRange(lower=Decimal("6.5"), upper=Decimal("8.5")).lower,
            Decimal("6.5"),
        )
        self.assertEqual(ActionLevel(value=Decimal("0.015")).value, Decimal("0.015"))

    def test_rejects_invalid_ranges_and_numbers(self) -> None:
        with self.assertRaises(ValidationError):
            IntegerRange(lower=3, upper=1)
        with self.assertRaises(ValidationError):
            RegulatoryRange(lower=Decimal("8.5"), upper=Decimal("6.5"))
        with self.assertRaises(ValidationError):
            ActionLevel(value=Decimal("NaN"))
        with self.assertRaises(ValidationError):
            ActionLevel(value=Decimal("-0.1"))


class ContaminantRecordTests(unittest.TestCase):
    def test_accepts_a_valid_record_and_preserves_null_states(self) -> None:
        values = valid_contaminant_values()
        values.update(
            {
                "chem_info_n_carbon": IntegerRange(lower=1, upper=3),
                "chem_info_n_nitrogen": NotApplicable.VALUE,
                "class_aromatic": False,
                "chem_info_halogenated": NotApplicable.VALUE,
                "source_notes_safewaters_review": SafewatersReviewMarker.UNRESOLVED,
            }
        )

        record = ContaminantRecord(**values)

        self.assertIsNone(record.id_aka)
        self.assertIs(record.class_aromatic, False)
        self.assertEqual(record.chem_info_n_nitrogen, NotApplicable.VALUE)
        self.assertEqual(
            record.chem_info_n_carbon,
            IntegerRange(lower=1, upper=3),
        )
        self.assertEqual(
            record.source_notes_safewaters_review,
            SafewatersReviewMarker.UNRESOLVED,
        )

    def test_accepts_explicit_not_applicable_scientific_identifiers(self) -> None:
        values = valid_contaminant_values()
        values.update(
            {
                "id_chem_formula": NotApplicable.VALUE,
                "id_casrn": NotApplicable.VALUE,
                "id_inchikey": NotApplicable.VALUE,
            }
        )

        record = ContaminantRecord(**values)

        self.assertEqual(record.id_chem_formula, NotApplicable.VALUE)
        self.assertEqual(record.id_casrn, NotApplicable.VALUE)
        self.assertEqual(record.id_inchikey, NotApplicable.VALUE)

    def test_rejects_missing_blank_and_unknown_values(self) -> None:
        missing = valid_contaminant_values()
        missing.pop("id_name")
        with self.assertRaises(ValidationError):
            ContaminantRecord(**missing)

        blank = valid_contaminant_values()
        blank["id_name"] = "  "
        with self.assertRaises(ValidationError):
            ContaminantRecord(**blank)

        unknown_enum = valid_contaminant_values()
        unknown_enum["class_primary"] = "Organic"
        with self.assertRaises(ValidationError):
            ContaminantRecord(**unknown_enum)

        null_required = valid_contaminant_values()
        null_required["chem_info_n_carbon"] = None
        with self.assertRaises(ValidationError):
            ContaminantRecord(**null_required)

        unknown_field = valid_contaminant_values()
        unknown_field["new_source_column"] = "unexpected"
        with self.assertRaises(ValidationError):
            ContaminantRecord(**unknown_field)

    def test_rejects_wrong_scalar_types_and_negative_values(self) -> None:
        boolean_number = valid_contaminant_values()
        boolean_number["class_aromatic"] = 0
        with self.assertRaises(ValidationError):
            ContaminantRecord(**boolean_number)

        negative_count = valid_contaminant_values()
        negative_count["chem_info_n_carbon"] = -1
        with self.assertRaises(ValidationError):
            ContaminantRecord(**negative_count)

        negative_regulatory_value = valid_contaminant_values()
        negative_regulatory_value["reg_status_npdwr_mcl_mg_l"] = Decimal("-0.1")
        with self.assertRaises(ValidationError):
            ContaminantRecord(**negative_regulatory_value)

    def test_records_field_ownership_nullability_and_publication(self) -> None:
        for field in ContaminantRecord.model_fields.values():
            metadata = field.json_schema_extra or {}
            self.assertIn(metadata.get("owner"), {owner.value for owner in FieldOwner})
            self.assertIn(
                metadata.get("null_policy"),
                {policy.value for policy in NullPolicy},
            )
            self.assertIsInstance(metadata.get("public"), bool)

        public_fields = public_field_names(ContaminantRecord)
        self.assertEqual(
            set(public_fields),
            set(WEBSITE_DISPLAY_FIELDS) | {"id_contaminant"},
        )
        self.assertIn("source_notes_general", public_fields)
        self.assertEqual(
            set(ContaminantRecord.model_fields) - set(public_fields),
            {
                "id_legacy_cg",
                "source_notes_npdwr_internal",
                "reg_status_hdoh_more_stringent",
                "source_notes_dataset_immediate",
                "source_notes_dataset_flushing",
                "source_notes_dataset_ltm",
                "source_notes_dataset_edwm",
                "source_notes_safewaters_legacy",
                "source_notes_safewaters_review",
            },
        )

        contaminant_id_metadata = (
            ContaminantRecord.model_fields["id_contaminant"].json_schema_extra or {}
        )
        aliases_metadata = (
            ContaminantRecord.model_fields["id_aka"].json_schema_extra or {}
        )
        self.assertEqual(contaminant_id_metadata["owner"], "registry")
        self.assertEqual(contaminant_id_metadata["null_policy"], "required")
        self.assertEqual(aliases_metadata["owner"], "glossary")
        self.assertEqual(aliases_metadata["null_policy"], "unknown_allowed")
        self.assertEqual(
            ContaminantRecord.model_fields[
                "reg_status_npdwr_mcl_mg_l"
            ].json_schema_extra["units"],
            "mg/L",
        )
        self.assertEqual(
            ContaminantRecord.model_fields["reg_status_smcl"].json_schema_extra[
                "units"
            ],
            "mg/L or pH",
        )


class RelationshipRecordTests(unittest.TestCase):
    def test_accepts_valid_reference_and_footnote_records(self) -> None:
        reference = ReferenceRecord(
            id_contaminant="RHC-001",
            refs_review_name="Example compound",
            refs_source="EPA",
            refs_url="https://example.gov/reference",
        )
        footnote = FootnoteRecord(
            source_notes_footnote_id="D",
            source_notes_footnote_text="Example footnote",
        )

        self.assertEqual(reference.id_contaminant, "RHC-001")
        self.assertEqual(footnote.source_notes_footnote_id, "D")
        self.assertEqual(
            ReferenceRecord.model_fields["refs_review_name"].json_schema_extra[
                "owner"
            ],
            "references",
        )
        self.assertFalse(
            ReferenceRecord.model_fields["refs_review_name"].json_schema_extra[
                "public"
            ]
        )
        self.assertEqual(
            FootnoteRecord.model_fields[
                "source_notes_footnote_text"
            ].json_schema_extra["owner"],
            "footnotes",
        )

    def test_rejects_invalid_reference_and_footnote_records(self) -> None:
        with self.assertRaises(ValidationError):
            ReferenceRecord(
                id_contaminant="RHC-000",
                refs_review_name="Example compound",
                refs_source="EPA",
                refs_url="https://example.gov/reference",
            )
        with self.assertRaises(ValidationError):
            ReferenceRecord(
                id_contaminant="RHC-001",
                refs_review_name="Example compound",
                refs_source="EPA",
                refs_url="spreadsheet.xlsx",
            )
        with self.assertRaises(ValidationError):
            FootnoteRecord(
                source_notes_footnote_id="bad id",
                source_notes_footnote_text="Example footnote",
            )


if __name__ == "__main__":
    unittest.main()
