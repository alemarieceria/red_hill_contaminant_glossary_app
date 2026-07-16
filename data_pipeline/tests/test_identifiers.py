import unittest

from contaminant_pipeline.identifiers import (
    contaminant_id_number,
    next_contaminant_id,
    validate_contaminant_ids,
)


class ContaminantIdFormatTests(unittest.TestCase):
    def test_accepts_valid_identifiers(self) -> None:
        self.assertEqual(contaminant_id_number("RHC-001"), 1)
        self.assertEqual(contaminant_id_number("RHC-152"), 152)
        self.assertEqual(contaminant_id_number("RHC-999"), 999)

    def test_rejects_invalid_identifiers(self) -> None:
        invalid_values = (
            "RHC-000",
            "RHC-1",
            "RHC-0001",
            "rhc-001",
            " RHC-001",
            "RHC-001 ",
            1,
            None,
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    contaminant_id_number(value)

    def test_rejects_duplicate_identifiers(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate contaminant ID"):
            validate_contaminant_ids(["RHC-001", "RHC-001"])


class ContaminantIdAllocationTests(unittest.TestCase):
    def test_starts_at_one_when_none_have_been_issued(self) -> None:
        self.assertEqual(next_contaminant_id([]), "RHC-001")

    def test_uses_the_highest_issued_id_not_input_order_or_gaps(self) -> None:
        issued_ids = ["RHC-152", "RHC-001", "RHC-025"]

        self.assertEqual(next_contaminant_id(issued_ids), "RHC-153")

    def test_retired_ids_remain_reserved_when_in_the_registry(self) -> None:
        active_ids = ["RHC-001", "RHC-002"]
        retired_ids = ["RHC-003"]

        self.assertEqual(
            next_contaminant_id([*active_ids, *retired_ids]), "RHC-004"
        )

    def test_rejects_allocation_after_999(self) -> None:
        with self.assertRaisesRegex(ValueError, "range is exhausted"):
            next_contaminant_id(["RHC-999"])


if __name__ == "__main__":
    unittest.main()
