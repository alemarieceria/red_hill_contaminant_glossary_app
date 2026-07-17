from dataclasses import replace
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from contaminant_pipeline.bootstrap_validation import validate_bootstrap_snapshots
from contaminant_pipeline.crosswalk import (
    REFERENCE_NAME_OVERRIDES,
    ReferenceResolutionMethod,
)
from contaminant_pipeline.io_excel import read_workbook
from contaminant_pipeline.paths import (
    CONTAMINANT_REGISTRY_PATH,
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    REFERENCE_CROSSWALK_PATH,
    REGISTRY_DIR,
)
from contaminant_pipeline.registry_assets import (
    CROSSWALK_FILENAME,
    REGISTRY_FILENAME,
    RegistryEntry,
    RegistryStatus,
    TrackedCrosswalkEntry,
    freeze_registry_assets,
    load_crosswalk,
    load_crosswalk_bytes,
    load_registry,
    load_registry_bytes,
    propose_registry_assets,
    serialize_crosswalk,
    serialize_registry,
    validate_crosswalk_transition,
    validate_registry_entries,
    validate_registry_transition,
    validate_tracked_crosswalk,
)


def active_entry(
    contaminant_id="RHC-001",
    legacy_id=1,
    name="Alpha",
    issued="20260716",
) -> RegistryEntry:
    return RegistryEntry(
        contaminant_id,
        legacy_id,
        name,
        RegistryStatus.ACTIVE,
        None,
        issued,
        None,
    )


def retired_entry(
    contaminant_id="RHC-001",
    legacy_id=1,
    name="Alpha",
    successor_id="RHC-002",
    issued="20260716",
    retired="20260716-r2",
) -> RegistryEntry:
    return RegistryEntry(
        contaminant_id,
        legacy_id,
        name,
        RegistryStatus.RETIRED,
        successor_id,
        issued,
        retired,
    )


def crosswalk_entry(
    label="Alpha",
    contaminant_id="RHC-001",
    method=ReferenceResolutionMethod.EXACT,
    release="20260716",
) -> TrackedCrosswalkEntry:
    return TrackedCrosswalkEntry(label, contaminant_id, method, release)


@cache
def authoritative_bootstrap():
    return validate_bootstrap_snapshots(
        read_workbook(INCOMING_GLOSSARY_WORKBOOK),
        read_workbook(INCOMING_REFERENCES_WORKBOOK),
        REFERENCE_NAME_OVERRIDES,
    )


class RegistryRecordValidationTests(unittest.TestCase):
    def test_accepts_active_retired_and_future_entries(self) -> None:
        survivor = active_entry("RHC-002", 2, "Beta")
        retired = retired_entry()
        future = active_entry("RHC-003", None, "Gāmma", "20260717")

        result = validate_registry_entries((future, survivor, retired))

        self.assertEqual(
            tuple(entry.id_contaminant for entry in result),
            ("RHC-001", "RHC-002", "RHC-003"),
        )

    def test_rejects_invalid_registry_record_values(self) -> None:
        cases = (
            ({"id_contaminant": "rhc-001"}, "RHC-NNN"),
            ({"id_legacy_cg": True}, "positive integer"),
            ({"id_legacy_cg": 0}, "positive integer"),
            ({"id_name": " "}, "nonblank text"),
            ({"id_name": " Alpha"}, "surrounding whitespace"),
            ({"status": "active"}, "status"),
            ({"successor_id": "RHC-001"}, "succeed itself"),
            ({"issued_release_id": "20260716-r1"}, "release ID"),
            (
                {"successor_id": "RHC-002"},
                "active registry entries",
            ),
            (
                {
                    "status": RegistryStatus.RETIRED,
                    "retired_release_id": None,
                },
                "require a retirement release",
            ),
            (
                {
                    "status": RegistryStatus.RETIRED,
                    "successor_id": "RHC-002",
                    "issued_release_id": "20260717",
                    "retired_release_id": "20260716",
                },
                "cannot precede",
            ),
        )

        base = {
            "id_contaminant": "RHC-001",
            "id_legacy_cg": 1,
            "id_name": "Alpha",
            "status": RegistryStatus.ACTIVE,
            "successor_id": None,
            "issued_release_id": "20260716",
            "retired_release_id": None,
        }
        for changes, message in cases:
            with self.subTest(changes=changes):
                values = {**base, **changes}
                with self.assertRaisesRegex(ValueError, message):
                    RegistryEntry(**values)

    def test_rejects_duplicate_ids_legacy_ids_and_missing_successors(self) -> None:
        cases = (
            ([active_entry(), active_entry()], "duplicate registry ID"),
            (
                [active_entry(), active_entry("RHC-002", 1, "Beta")],
                "duplicate legacy CG ID",
            ),
            ([retired_entry()], "successor is not present"),
        )

        for entries, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_registry_entries(entries)

    def test_rejects_invalid_crosswalk_rows_and_targets(self) -> None:
        registry = (active_entry(),)
        with self.assertRaisesRegex(ValueError, "nonblank text"):
            crosswalk_entry(label=" ")
        with self.assertRaisesRegex(ValueError, "resolution method"):
            TrackedCrosswalkEntry("Alpha", "RHC-001", "exact", "20260716")

        cases = (
            ([crosswalk_entry(contaminant_id="RHC-002")], "absent"),
            (
                [crosswalk_entry(), crosswalk_entry()],
                "duplicate crosswalk label",
            ),
        )

        for entries, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_tracked_crosswalk(entries, registry)


class RegistryTransitionTests(unittest.TestCase):
    def test_allows_rename_retirement_and_contiguous_new_ids(self) -> None:
        previous = (
            active_entry("RHC-001", 1, "Old Alpha"),
            active_entry("RHC-002", 2, "Beta"),
        )
        proposed = (
            retired_entry("RHC-001", 1, "Renamed Alpha", "RHC-002"),
            previous[1],
            active_entry("RHC-003", None, "Gamma", "20260716-r2"),
        )

        result = validate_registry_transition(previous, proposed)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].status, RegistryStatus.RETIRED)
        self.assertEqual(result[0].id_name, "Renamed Alpha")

    def test_rejects_removal_reactivation_and_immutable_field_changes(self) -> None:
        active_two = active_entry("RHC-002", 2, "Beta")
        old_retired = retired_entry()
        cases = (
            ((active_entry(), active_two), (active_entry(),), "cannot be removed"),
            (
                (old_retired, active_two),
                (active_entry(), active_two),
                "cannot reactivate",
            ),
            (
                (active_entry(),),
                (active_entry(legacy_id=2),),
                "legacy CG ID cannot change",
            ),
            (
                (active_entry(),),
                (active_entry(issued="20260717"),),
                "issuance release cannot change",
            ),
        )

        for previous, proposed, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_registry_transition(previous, proposed)

    def test_rejects_gap_filling_and_skipped_new_ids(self) -> None:
        previous = (active_entry("RHC-001", 1), active_entry("RHC-003", 3))
        cases = (
            (*previous, active_entry("RHC-002", 2)),
            (*previous, active_entry("RHC-005", None)),
        )

        for proposed in cases:
            with self.subTest(proposed=proposed[-1].id_contaminant):
                with self.assertRaisesRegex(ValueError, "extend contiguously"):
                    validate_registry_transition(previous, proposed)

    def test_crosswalk_transition_retains_existing_labels(self) -> None:
        registry = (active_entry(), active_entry("RHC-002", 2, "Beta"))
        previous = (crosswalk_entry(),)
        proposed = (
            *previous,
            crosswalk_entry("Beta", "RHC-002", ReferenceResolutionMethod.OVERRIDE),
        )

        self.assertEqual(
            validate_crosswalk_transition(previous, proposed, registry),
            proposed,
        )

    def test_crosswalk_transition_rejects_removal_or_retargeting(self) -> None:
        registry = (active_entry(), active_entry("RHC-002", 2, "Beta"))
        previous = (crosswalk_entry(),)
        cases = (
            ((), "cannot be removed"),
            ((crosswalk_entry(contaminant_id="RHC-002"),), "cannot be retargeted"),
        )

        for proposed, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_crosswalk_transition(previous, proposed, registry)


class RegistrySerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = (
            active_entry("RHC-002", None, 'Béta, "quoted"', "20260717"),
            active_entry("RHC-001", 1, "Alpha"),
        )
        self.crosswalk = (
            crosswalk_entry(
                'Béta, "review"',
                "RHC-002",
                ReferenceResolutionMethod.OVERRIDE,
                "20260717",
            ),
            crosswalk_entry(),
        )

    def test_serialization_is_sorted_utf8_lf_and_round_trips(self) -> None:
        registry_bytes = serialize_registry(reversed(self.registry))
        crosswalk_bytes = serialize_crosswalk(
            reversed(self.crosswalk), reversed(self.registry)
        )

        self.assertEqual(registry_bytes, serialize_registry(self.registry))
        self.assertEqual(
            crosswalk_bytes, serialize_crosswalk(self.crosswalk, self.registry)
        )
        self.assertTrue(registry_bytes.endswith(b"\n"))
        self.assertNotIn(b"\r", registry_bytes)
        self.assertIn("Béta".encode(), registry_bytes)
        loaded_registry = load_registry_bytes(registry_bytes)
        self.assertEqual(loaded_registry, tuple(reversed(self.registry)))
        self.assertEqual(
            load_crosswalk_bytes(crosswalk_bytes, loaded_registry),
            tuple(reversed(self.crosswalk)),
        )

    def test_loaders_reject_malformed_or_noncanonical_bytes(self) -> None:
        valid = serialize_registry((active_entry(),))
        cases = (
            (b"\xef\xbb\xbf" + valid, "byte-order mark"),
            (b"\xff\n", "valid UTF-8"),
            (valid.replace(b"\n", b"\r\n"), "LF newlines"),
            (valid.rstrip(b"\n"), "end with a newline"),
            (b"wrong,headers\n", "headers must be exactly"),
            (
                b"id_contaminant,id_legacy_cg,id_name,status,successor_id,"
                b"issued_release_id,retired_release_id\nRHC-001,1\n",
                "wrong number of columns",
            ),
            (valid.replace(b",1,Alpha,", b",01,Alpha,"), "canonical integer"),
        )

        for data, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    load_registry_bytes(data)


class RegistryFilesystemTests(unittest.TestCase):
    def test_freezes_reloads_and_idempotently_retries(self) -> None:
        proposal = propose_registry_assets(authoritative_bootstrap())
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            target = Path(temporary) / "registry"

            registry_path, crosswalk_path = freeze_registry_assets(
                authoritative_bootstrap(), target
            )
            registry_mtime = registry_path.stat().st_mtime_ns
            crosswalk_mtime = crosswalk_path.stat().st_mtime_ns
            second_paths = freeze_registry_assets(authoritative_bootstrap(), target)

            loaded_registry = load_registry(registry_path)
            loaded_crosswalk = load_crosswalk(crosswalk_path, loaded_registry)
            self.assertEqual(loaded_registry, proposal.registry_entries)
            self.assertEqual(loaded_crosswalk, proposal.crosswalk_entries)
            self.assertEqual(second_paths, (registry_path, crosswalk_path))
            self.assertEqual(registry_path.stat().st_mtime_ns, registry_mtime)
            self.assertEqual(crosswalk_path.stat().st_mtime_ns, crosswalk_mtime)

    def test_rejects_partial_and_differing_existing_content(self) -> None:
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            partial = Path(temporary) / "partial"
            partial.mkdir()
            (partial / REGISTRY_FILENAME).write_bytes(b"partial")
            with self.assertRaisesRegex(ValueError, "partial or unexpected"):
                freeze_registry_assets(authoritative_bootstrap(), partial)

            collision = Path(temporary) / "collision"
            _, crosswalk_path = freeze_registry_assets(
                authoritative_bootstrap(), collision
            )
            crosswalk_path.write_bytes(crosswalk_path.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                freeze_registry_assets(authoritative_bootstrap(), collision)

    def test_cleans_staging_after_atomic_publication_failure(self) -> None:
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            target = Path(temporary) / "registry"
            with patch.object(Path, "replace", side_effect=OSError("failure")):
                with self.assertRaisesRegex(OSError, "failure"):
                    freeze_registry_assets(authoritative_bootstrap(), target)

            self.assertFalse(target.exists())
            self.assertEqual(tuple(Path(temporary).glob(".registry-*")), ())


class AuthoritativeRegistryAssetTests(unittest.TestCase):
    def test_tracked_paths_and_current_assets_match_the_bootstrap(self) -> None:
        self.assertEqual(REGISTRY_DIR.name, "registry")
        self.assertEqual(CONTAMINANT_REGISTRY_PATH.name, REGISTRY_FILENAME)
        self.assertEqual(REFERENCE_CROSSWALK_PATH.name, CROSSWALK_FILENAME)
        proposal = propose_registry_assets(authoritative_bootstrap())

        registry = load_registry(CONTAMINANT_REGISTRY_PATH)
        crosswalk = load_crosswalk(REFERENCE_CROSSWALK_PATH, registry)

        self.assertEqual(registry, proposal.registry_entries)
        self.assertEqual(crosswalk, proposal.crosswalk_entries)
        self.assertEqual(len(registry), 152)
        self.assertEqual(len(crosswalk), 133)
        self.assertEqual(registry[0].id_contaminant, "RHC-001")
        self.assertEqual(registry[-1].id_contaminant, "RHC-152")
        self.assertEqual(
            sum(
                entry.resolution_method is ReferenceResolutionMethod.EXACT
                for entry in crosswalk
            ),
            112,
        )
        self.assertEqual(
            sum(
                entry.resolution_method is ReferenceResolutionMethod.OVERRIDE
                for entry in crosswalk
            ),
            21,
        )

    def test_reordered_bootstrap_values_produce_identical_bytes(self) -> None:
        validated = authoritative_bootstrap()
        reordered = replace(
            validated,
            glossary_identities=tuple(reversed(validated.glossary_identities)),
            id_mappings=tuple(reversed(validated.id_mappings)),
            reference_crosswalk=tuple(reversed(validated.reference_crosswalk)),
        )

        original = propose_registry_assets(validated)
        shuffled = propose_registry_assets(reordered)

        self.assertEqual(
            serialize_registry(original.registry_entries),
            serialize_registry(shuffled.registry_entries),
        )
        self.assertEqual(
            serialize_crosswalk(
                original.crosswalk_entries, original.registry_entries
            ),
            serialize_crosswalk(
                shuffled.crosswalk_entries, shuffled.registry_entries
            ),
        )

    def test_generation_does_not_modify_authoritative_workbooks(self) -> None:
        glossary_bytes = INCOMING_GLOSSARY_WORKBOOK.read_bytes()
        reference_bytes = INCOMING_REFERENCES_WORKBOOK.read_bytes()

        propose_registry_assets(authoritative_bootstrap())

        self.assertEqual(INCOMING_GLOSSARY_WORKBOOK.read_bytes(), glossary_bytes)
        self.assertEqual(INCOMING_REFERENCES_WORKBOOK.read_bytes(), reference_bytes)


if __name__ == "__main__":
    unittest.main()
