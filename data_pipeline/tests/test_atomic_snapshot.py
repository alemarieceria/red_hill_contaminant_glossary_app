from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
from shutil import copyfile
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from contaminant_pipeline.config import (
    GLOSSARY_WORKBOOK_FILENAME,
    REFERENCES_WORKBOOK_FILENAME,
)
from contaminant_pipeline.intake import (
    IncomingContractError,
    inventory_incoming_pair,
    publish_raw_snapshot,
    read_incoming_pair,
)
from contaminant_pipeline.paths import (
    CONTAMINANT_REGISTRY_PATH,
    INCOMING_DIR,
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    MANIFEST_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    PUBLIC_DATA_DIR,
    RAW_SNAPSHOTS_DIR,
    REFERENCE_CROSSWALK_PATH,
    REPOSITORY_ROOT,
)
from fixture_paths import (
    SYNTHETIC_GLOSSARY_WORKBOOK,
    SYNTHETIC_REFERENCES_WORKBOOK,
)


GENERATED_ROOTS = (MANIFEST_DIR, PROCESSED_DIR, OUTPUT_DIR, PUBLIC_DATA_DIR)


def _copy_fixture_pair(directory: Path) -> None:
    copyfile(
        SYNTHETIC_GLOSSARY_WORKBOOK,
        directory / GLOSSARY_WORKBOOK_FILENAME,
    )
    copyfile(
        SYNTHETIC_REFERENCES_WORKBOOK,
        directory / REFERENCES_WORKBOOK_FILENAME,
    )


def _inventory(directory: Path):
    return inventory_incoming_pair(read_incoming_pair(directory))


def _file_state(paths):
    return {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in paths
    }


def _tree_state(roots):
    state = []
    for root in roots:
        state.append((root, root.exists()))
        if root.exists():
            for path in sorted(root.rglob("*")):
                state.append(
                    (path, path.is_dir(), path.read_bytes() if path.is_file() else None)
                )
    return tuple(state)


class AtomicSnapshotSuccessTests(unittest.TestCase):
    def test_publishes_exact_pair_and_returns_frozen_snapshot_paths(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            incoming = base / "incoming"
            raw_root = base / "raw"
            incoming.mkdir()
            _copy_fixture_pair(incoming)
            source_paths = (
                incoming / GLOSSARY_WORKBOOK_FILENAME,
                incoming / REFERENCES_WORKBOOK_FILENAME,
            )
            source_before = _file_state(source_paths)
            inventory = _inventory(incoming)

            result = publish_raw_snapshot(inventory, raw_root)

            self.assertIs(result.inventory, inventory)
            self.assertEqual(result.data_release_id, "20000115-r2")
            self.assertEqual(result.snapshot_dir, raw_root.resolve() / "20000115-r2")
            self.assertEqual(
                {path.name for path in result.snapshot_dir.iterdir()},
                {GLOSSARY_WORKBOOK_FILENAME, REFERENCES_WORKBOOK_FILENAME},
            )
            self.assertEqual(result.glossary_path.read_bytes(), source_before[source_paths[0]][0])
            self.assertEqual(result.references_path.read_bytes(), source_before[source_paths[1]][0])
            self.assertEqual(
                sha256(result.glossary_path.read_bytes()).hexdigest(),
                inventory.glossary_inventory.sha256,
            )
            self.assertEqual(
                sha256(result.references_path.read_bytes()).hexdigest(),
                inventory.references_inventory.sha256,
            )
            self.assertEqual(_file_state(source_paths), source_before)
            self.assertEqual(tuple(raw_root.glob(".20000115-r2-*")), ())
            with self.assertRaises(FrozenInstanceError):
                result.data_release_id = "changed"

    def test_target_appears_only_at_the_complete_directory_rename(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            incoming = base / "incoming"
            raw_root = base / "raw"
            incoming.mkdir()
            _copy_fixture_pair(incoming)
            inventory = _inventory(incoming)
            target = raw_root.resolve() / inventory.data_release_id
            original_replace = Path.replace
            observations = []

            def observing_replace(staging, destination):
                observations.append(
                    (
                        destination.exists(),
                        {path.name for path in staging.iterdir()},
                    )
                )
                return original_replace(staging, destination)

            with patch.object(
                Path,
                "replace",
                autospec=True,
                side_effect=observing_replace,
            ):
                result = publish_raw_snapshot(inventory, raw_root)

            self.assertEqual(
                observations,
                [
                    (
                        False,
                        {GLOSSARY_WORKBOOK_FILENAME, REFERENCES_WORKBOOK_FILENAME},
                    )
                ],
            )
            self.assertEqual(result.snapshot_dir, target)
            self.assertTrue(target.is_dir())

    def test_separate_roots_receive_byte_identical_snapshots(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            incoming = base / "incoming"
            incoming.mkdir()
            _copy_fixture_pair(incoming)
            inventory = _inventory(incoming)

            first = publish_raw_snapshot(inventory, base / "raw-one")
            second = publish_raw_snapshot(inventory, base / "raw-two")

            for filename in (
                GLOSSARY_WORKBOOK_FILENAME,
                REFERENCES_WORKBOOK_FILENAME,
            ):
                self.assertEqual(
                    (first.snapshot_dir / filename).read_bytes(),
                    (second.snapshot_dir / filename).read_bytes(),
                )


class AtomicSnapshotPreconditionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.incoming = self.base / "incoming"
        self.incoming.mkdir()
        _copy_fixture_pair(self.incoming)
        self.inventory = _inventory(self.incoming)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _assert_early_failure(self, inventory, message, root=None):
        raw_root = root or self.base / "raw"
        with patch("contaminant_pipeline.intake.tempfile.mkdtemp") as staging:
            with patch("contaminant_pipeline.intake.shutil.copyfile") as copier:
                with self.assertRaisesRegex(IncomingContractError, message):
                    publish_raw_snapshot(inventory, raw_root)
        staging.assert_not_called()
        copier.assert_not_called()

    def test_requires_a_consistent_inventory(self) -> None:
        self._assert_early_failure(object(), "IncomingPairInventory")
        self._assert_early_failure(
            replace(self.inventory, data_release_id="20000116"),
            "release ID does not match",
        )
        self._assert_early_failure(
            replace(
                self.inventory,
                glossary_inventory=replace(
                    self.inventory.glossary_inventory,
                    filename="wrong.xlsx",
                ),
            ),
            "filename",
        )
        self._assert_early_failure(
            replace(
                self.inventory,
                glossary_inventory=replace(
                    self.inventory.glossary_inventory,
                    size_bytes=self.inventory.glossary_inventory.size_bytes + 1,
                ),
            ),
            "byte size",
        )
        self._assert_early_failure(
            replace(
                self.inventory,
                glossary_inventory=replace(
                    self.inventory.glossary_inventory,
                    sha256="0" * 64,
                ),
            ),
            "SHA-256",
        )

    def test_rejects_missing_sources_and_invalid_raw_roots(self) -> None:
        self.inventory.incoming_pair.glossary_snapshot.path.unlink()
        self._assert_early_failure(self.inventory, "not an ordinary file")

        _copy_fixture_pair(self.incoming)
        inventory = _inventory(self.incoming)
        root_file = self.base / "raw-file"
        root_file.write_text("not a directory", encoding="utf-8")
        self._assert_early_failure(inventory, "not a directory", root_file)

    def test_refuses_every_preexisting_target_without_changing_it(self) -> None:
        for kind in ("file", "directory"):
            with self.subTest(kind=kind):
                raw_root = self.base / f"raw-{kind}"
                raw_root.mkdir()
                target = raw_root / self.inventory.data_release_id
                if kind == "file":
                    target.write_bytes(b"existing")
                else:
                    target.mkdir()
                    (target / "marker").write_bytes(b"existing")
                before = _tree_state((raw_root,))

                self._assert_early_failure(
                    self.inventory,
                    "already exists",
                    raw_root,
                )

                self.assertEqual(_tree_state((raw_root,)), before)


class AtomicSnapshotFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.incoming = self.base / "incoming"
        self.raw_root = self.base / "raw"
        self.incoming.mkdir()
        _copy_fixture_pair(self.incoming)
        self.inventory = _inventory(self.incoming)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _assert_no_publication(self):
        self.assertFalse((self.raw_root / self.inventory.data_release_id).exists())
        self.assertEqual(tuple(self.raw_root.glob(f".{self.inventory.data_release_id}-*")), ())

    def test_rejects_a_source_changed_after_inventory(self) -> None:
        references = self.incoming / REFERENCES_WORKBOOK_FILENAME
        glossary_before = (self.incoming / GLOSSARY_WORKBOOK_FILENAME).read_bytes()
        references.write_bytes(references.read_bytes() + b"changed")

        with self.assertRaisesRegex(IncomingContractError, "staged references bytes"):
            publish_raw_snapshot(self.inventory, self.raw_root)

        self._assert_no_publication()
        self.assertEqual(
            (self.incoming / GLOSSARY_WORKBOOK_FILENAME).read_bytes(),
            glossary_before,
        )

    def test_cleans_staging_after_each_copy_failure(self) -> None:
        original_copyfile = copyfile
        for failure_call in (1, 2):
            with self.subTest(failure_call=failure_call):
                calls = 0

                def failing_copy(source, destination):
                    nonlocal calls
                    calls += 1
                    if calls == failure_call:
                        raise OSError("injected copy failure")
                    return original_copyfile(source, destination)

                with patch(
                    "contaminant_pipeline.intake.shutil.copyfile",
                    side_effect=failing_copy,
                ):
                    with self.assertRaisesRegex(IncomingContractError, "copy or verify"):
                        publish_raw_snapshot(self.inventory, self.raw_root)
                self._assert_no_publication()

    def test_cleans_staging_after_verification_and_content_failures(self) -> None:
        with patch(
            "contaminant_pipeline.intake._file_fingerprint",
            return_value=(1, "0" * 64),
        ):
            with self.assertRaisesRegex(IncomingContractError, "staged glossary bytes"):
                publish_raw_snapshot(self.inventory, self.raw_root)
        self._assert_no_publication()

        original_copyfile = copyfile
        calls = 0

        def adding_extra(source, destination):
            nonlocal calls
            calls += 1
            result = original_copyfile(source, destination)
            if calls == 2:
                (Path(destination).parent / "extra.txt").write_text(
                    "unexpected",
                    encoding="utf-8",
                )
            return result

        with patch(
            "contaminant_pipeline.intake.shutil.copyfile",
            side_effect=adding_extra,
        ):
            with self.assertRaisesRegex(IncomingContractError, "exactly the two"):
                publish_raw_snapshot(self.inventory, self.raw_root)
        self._assert_no_publication()

    def test_cleans_staging_after_rename_failure(self) -> None:
        with patch.object(Path, "replace", side_effect=OSError("rename failure")):
            with self.assertRaisesRegex(IncomingContractError, "could not publish"):
                publish_raw_snapshot(self.inventory, self.raw_root)

        self._assert_no_publication()

    def test_target_race_preserves_competing_target(self) -> None:
        target = self.raw_root.resolve() / self.inventory.data_release_id

        def racing_replace(_staging, destination):
            destination.mkdir()
            (destination / "competitor").write_bytes(b"keep")
            raise OSError("target race")

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=racing_replace,
        ):
            with self.assertRaisesRegex(IncomingContractError, "could not publish"):
                publish_raw_snapshot(self.inventory, self.raw_root)

        self.assertEqual((target / "competitor").read_bytes(), b"keep")
        self.assertEqual(tuple(self.raw_root.glob(f".{self.inventory.data_release_id}-*")), ())

    def test_reports_a_staging_cleanup_failure_without_broad_deletion(self) -> None:
        with patch(
            "contaminant_pipeline.intake.shutil.copyfile",
            side_effect=OSError("copy failure"),
        ):
            with patch(
                "contaminant_pipeline.intake.shutil.rmtree",
                side_effect=OSError("cleanup failure"),
            ):
                with self.assertRaisesRegex(
                    IncomingContractError,
                    "cleanup also failed",
                ) as raised:
                    publish_raw_snapshot(self.inventory, self.raw_root)

        leftovers = tuple(self.raw_root.glob(f".{self.inventory.data_release_id}-*"))
        self.assertEqual(len(leftovers), 1)
        self.assertIn(str(leftovers[0]), str(raised.exception))
        self.assertFalse((self.raw_root / self.inventory.data_release_id).exists())


class AuthoritativeAtomicSnapshotTests(unittest.TestCase):
    def test_publishes_authoritative_pair_only_to_disposable_root(self) -> None:
        protected_paths = (
            INCOMING_GLOSSARY_WORKBOOK,
            INCOMING_REFERENCES_WORKBOOK,
            CONTAMINANT_REGISTRY_PATH,
            REFERENCE_CROSSWALK_PATH,
            RAW_SNAPSHOTS_DIR / "20260115" / GLOSSARY_WORKBOOK_FILENAME,
        )
        protected_before = _file_state(protected_paths)
        generated_before = _tree_state(GENERATED_ROOTS)

        with TemporaryDirectory() as temporary:
            inventory = inventory_incoming_pair(read_incoming_pair(INCOMING_DIR))
            result = publish_raw_snapshot(inventory, Path(temporary) / "raw")
            self.assertEqual(
                result.glossary_path.read_bytes(),
                INCOMING_GLOSSARY_WORKBOOK.read_bytes(),
            )
            self.assertEqual(
                result.references_path.read_bytes(),
                INCOMING_REFERENCES_WORKBOOK.read_bytes(),
            )

        self.assertEqual(_file_state(protected_paths), protected_before)
        self.assertEqual(_tree_state(GENERATED_ROOTS), generated_before)

    def test_generated_snapshot_paths_are_ignored_but_history_is_tracked(self) -> None:
        future = RAW_SNAPSHOTS_DIR / "20991231" / GLOSSARY_WORKBOOK_FILENAME
        staging = RAW_SNAPSHOTS_DIR / ".20991231-example"
        historical = RAW_SNAPSHOTS_DIR / "20260115" / GLOSSARY_WORKBOOK_FILENAME

        for path in (future, staging):
            result = subprocess.run(
                ["git", "check-ignore", "-q", "--", str(path)],
                cwd=REPOSITORY_ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
        historical_result = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(historical)],
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        self.assertEqual(historical_result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
