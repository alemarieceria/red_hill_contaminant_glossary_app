from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from contaminant_pipeline.config import (
    GLOSSARY_WORKBOOK_FILENAME,
    REFERENCES_WORKBOOK_FILENAME,
)
from contaminant_pipeline.intake import (
    GitSourceState,
    IncomingContractError,
    inventory_incoming_pair,
    publish_intake_manifest,
    publish_or_reuse_intake,
    publish_raw_snapshot,
    read_incoming_pair,
)
from fixture_paths import (
    SYNTHETIC_GLOSSARY_WORKBOOK,
    SYNTHETIC_REFERENCES_WORKBOOK,
)


FIXED_GIT = GitSourceState("commit", "a" * 40)


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


def _state(paths):
    return {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in paths
    }


def _canonical_json(data) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class IntakeCollisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.incoming = self.base / "incoming"
        self.raw_root = self.base / "raw"
        self.manifest_root = self.base / "manifests"
        self.incoming.mkdir()
        _copy_fixture_pair(self.incoming)
        self.inventory = _inventory(self.incoming)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _publish(self):
        return publish_or_reuse_intake(
            self.inventory,
            self.raw_root,
            self.manifest_root,
            source_git=FIXED_GIT,
        )

    def test_first_publication_then_retry_is_an_untouched_no_op(self) -> None:
        created = self._publish()
        paths = (
            created.raw_snapshot.glossary_path,
            created.raw_snapshot.references_path,
            created.manifest.path,
        )
        before = _state(paths)

        with patch("contaminant_pipeline.intake.shutil.copyfile") as copying:
            with patch.object(Path, "write_bytes") as writing:
                existing = self._publish()

        self.assertEqual(created.disposition, "created")
        self.assertTrue(created.raw_created)
        self.assertTrue(created.manifest_created)
        self.assertEqual(existing.disposition, "existing")
        self.assertFalse(existing.raw_created)
        self.assertFalse(existing.manifest_created)
        self.assertEqual(_state(paths), before)
        self.assertEqual(existing.manifest.serialized_bytes, created.manifest.serialized_bytes)
        copying.assert_not_called()
        writing.assert_not_called()
        with self.assertRaises(FrozenInstanceError):
            existing.disposition = "changed"

    def test_raw_only_retry_publishes_only_the_missing_manifest(self) -> None:
        raw = publish_raw_snapshot(self.inventory, self.raw_root)
        raw_before = _state((raw.glossary_path, raw.references_path))

        with patch("contaminant_pipeline.intake.shutil.copyfile") as copying:
            recovered = self._publish()

        self.assertEqual(recovered.disposition, "recovered")
        self.assertFalse(recovered.raw_created)
        self.assertTrue(recovered.manifest_created)
        self.assertEqual(_state((raw.glossary_path, raw.references_path)), raw_before)
        copying.assert_not_called()

    def test_manifest_failure_leaves_recoverable_raw_then_retry_succeeds(self) -> None:
        with patch.object(Path, "write_bytes", side_effect=OSError("write failure")):
            with self.assertRaisesRegex(IncomingContractError, "could not publish"):
                self._publish()

        raw_target = self.raw_root / self.inventory.data_release_id
        manifest_target = self.manifest_root / f"{self.inventory.data_release_id}.json"
        self.assertTrue(raw_target.is_dir())
        self.assertFalse(manifest_target.exists())
        self.assertEqual(tuple(self.manifest_root.glob(".*.json")), ())

        recovered = self._publish()
        self.assertEqual(recovered.disposition, "recovered")
        self.assertFalse(recovered.raw_created)
        self.assertTrue(recovered.manifest_created)

    def test_different_source_pair_with_same_release_is_a_collision(self) -> None:
        first = self._publish()
        protected = _state(
            (
                first.raw_snapshot.glossary_path,
                first.raw_snapshot.references_path,
                first.manifest.path,
            )
        )
        changed = self.base / "changed"
        changed.mkdir()
        _copy_fixture_pair(changed)
        glossary = changed / GLOSSARY_WORKBOOK_FILENAME
        glossary.write_bytes(glossary.read_bytes() + b"changed")
        changed_inventory = _inventory(changed)
        self.assertEqual(changed_inventory.data_release_id, self.inventory.data_release_id)

        with self.assertRaisesRegex(IncomingContractError, "revision collision"):
            publish_or_reuse_intake(
                changed_inventory,
                self.raw_root,
                self.manifest_root,
                source_git=FIXED_GIT,
            )

        self.assertEqual(
            _state(tuple(protected)),
            protected,
        )

    def test_changed_raw_or_manifest_is_rejected_without_repair(self) -> None:
        first = self._publish()
        first.raw_snapshot.glossary_path.write_bytes(b"different")
        damaged_raw = first.raw_snapshot.glossary_path.read_bytes()
        with self.assertRaisesRegex(IncomingContractError, "different size"):
            self._publish()
        self.assertEqual(first.raw_snapshot.glossary_path.read_bytes(), damaged_raw)

        first.raw_snapshot.glossary_path.write_bytes(
            self.inventory.incoming_pair.glossary_snapshot.path.read_bytes()
        )
        document = json.loads(first.manifest.path.read_bytes())
        document["workbooks"][0]["warning_count"] += 1
        changed_manifest = _canonical_json(document)
        first.manifest.path.write_bytes(changed_manifest)
        with self.assertRaisesRegex(IncomingContractError, "existing inventory"):
            self._publish()
        self.assertEqual(first.manifest.path.read_bytes(), changed_manifest)

    def test_manifest_git_provenance_does_not_change_retry_identity(self) -> None:
        first = self._publish()
        different_git = GitSourceState("local", "b" * 40)
        retry = publish_or_reuse_intake(
            self.inventory,
            self.raw_root,
            self.manifest_root,
            source_git=different_git,
        )
        self.assertEqual(retry.disposition, "existing")
        self.assertEqual(retry.manifest.manifest.source_git, FIXED_GIT)
        self.assertEqual(retry.manifest.serialized_bytes, first.manifest.serialized_bytes)

    def test_prior_revision_with_different_hash_is_rejected(self) -> None:
        raw = publish_raw_snapshot(self.inventory, self.base / "history-raw")
        prior = publish_intake_manifest(
            raw,
            self.base / "history-source",
            source_git=FIXED_GIT,
        )
        document = json.loads(prior.serialized_bytes)
        document["data_release_id"] = "19990101"
        for workbook in document["workbooks"]:
            workbook["snapshot_path"] = (
                f"19990101/{workbook['filename']}"
            )
        document["workbooks"][0]["sha256"] = "0" * 64
        self.manifest_root.mkdir()
        (self.manifest_root / "19990101.json").write_bytes(
            _canonical_json(document)
        )

        with self.assertRaisesRegex(IncomingContractError, "revision collision"):
            self._publish()
        self.assertFalse((self.raw_root / self.inventory.data_release_id).exists())

    def test_unchanged_revision_may_be_reused_when_other_revision_advanced(self) -> None:
        raw = publish_raw_snapshot(self.inventory, self.base / "history-raw")
        prior = publish_intake_manifest(
            raw,
            self.base / "history-source",
            source_git=FIXED_GIT,
        )
        document = json.loads(prior.serialized_bytes)
        document["data_release_id"] = "19990101"
        for workbook in document["workbooks"]:
            workbook["snapshot_path"] = f"19990101/{workbook['filename']}"
        references = document["workbooks"][1]
        references["workbook_revision"] = "19990101"
        references["sha256"] = "0" * 64
        self.manifest_root.mkdir()
        (self.manifest_root / "19990101.json").write_bytes(
            _canonical_json(document)
        )

        result = self._publish()
        self.assertEqual(result.disposition, "created")

    def test_manifest_without_raw_and_malformed_history_fail_closed(self) -> None:
        other_raw = publish_raw_snapshot(self.inventory, self.base / "other-raw")
        publish_intake_manifest(
            other_raw,
            self.manifest_root,
            source_git=FIXED_GIT,
        )
        with self.assertRaisesRegex(IncomingContractError, "without its raw"):
            self._publish()
        self.assertFalse((self.raw_root / self.inventory.data_release_id).exists())

        (self.manifest_root / f"{self.inventory.data_release_id}.json").unlink()
        (self.manifest_root / "unexpected.txt").write_text("bad", encoding="utf-8")
        with self.assertRaisesRegex(IncomingContractError, "unexpected.*history"):
            self._publish()

    def test_noncanonical_duplicate_and_wrong_schema_manifests_are_rejected(self) -> None:
        raw = publish_raw_snapshot(self.inventory, self.raw_root)
        self.manifest_root.mkdir()
        target = self.manifest_root / f"{self.inventory.data_release_id}.json"
        cases = (
            b'{"data_release_id":"20000115-r2"}',
            b'{"data_release_id":"20000115-r2","data_release_id":"20000115-r2"}',
        )
        for content in cases:
            with self.subTest(content=content):
                target.write_bytes(content)
                with self.assertRaises(IncomingContractError):
                    self._publish()
        target.unlink()

        published = publish_intake_manifest(raw, self.manifest_root, source_git=FIXED_GIT)
        document = json.loads(published.serialized_bytes)
        document["manifest_schema_version"] = "2.0.0"
        target.write_bytes(_canonical_json(document))
        with self.assertRaisesRegex(IncomingContractError, "unsupported"):
            self._publish()

    def test_identical_raw_race_is_reconciled(self) -> None:
        original = publish_raw_snapshot

        def winning_then_failing(inventory, root):
            original(inventory, root)
            raise IncomingContractError("simulated target race")

        with patch(
            "contaminant_pipeline.intake.publish_raw_snapshot",
            side_effect=winning_then_failing,
        ):
            result = self._publish()

        self.assertEqual(result.disposition, "recovered")
        self.assertFalse(result.raw_created)
        self.assertTrue(result.manifest_created)

    def test_conflicting_raw_race_preserves_the_winner(self) -> None:
        target = self.raw_root / self.inventory.data_release_id

        def conflicting_winner(_inventory, _root):
            target.mkdir(parents=True)
            (target / GLOSSARY_WORKBOOK_FILENAME).write_bytes(b"competitor")
            (target / REFERENCES_WORKBOOK_FILENAME).write_bytes(b"competitor")
            raise IncomingContractError("simulated target race")

        with patch(
            "contaminant_pipeline.intake.publish_raw_snapshot",
            side_effect=conflicting_winner,
        ):
            with self.assertRaisesRegex(IncomingContractError, "different size"):
                self._publish()

        self.assertEqual(
            (target / GLOSSARY_WORKBOOK_FILENAME).read_bytes(),
            b"competitor",
        )

    def test_identical_and_conflicting_manifest_races_are_classified(self) -> None:
        original = publish_intake_manifest

        def exact_winner(*args, **kwargs):
            original(*args, **kwargs)
            raise IncomingContractError("simulated manifest race")

        with patch(
            "contaminant_pipeline.intake.publish_intake_manifest",
            side_effect=exact_winner,
        ):
            exact = self._publish()
        self.assertEqual(exact.disposition, "created")
        self.assertTrue(exact.raw_created)
        self.assertFalse(exact.manifest_created)

        second = self.base / "second"
        second.mkdir()
        _copy_fixture_pair(second)
        second_inventory = _inventory(second)
        raw_root = self.base / "raw-two"
        manifest_root = self.base / "manifests-two"
        target = manifest_root / f"{second_inventory.data_release_id}.json"

        def conflicting_winner(*_args, **_kwargs):
            manifest_root.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"competitor")
            raise IncomingContractError("simulated manifest race")

        with patch(
            "contaminant_pipeline.intake.publish_intake_manifest",
            side_effect=conflicting_winner,
        ):
            with self.assertRaises(IncomingContractError):
                publish_or_reuse_intake(
                    second_inventory,
                    raw_root,
                    manifest_root,
                    source_git=FIXED_GIT,
                )
        self.assertEqual(target.read_bytes(), b"competitor")


if __name__ == "__main__":
    unittest.main()
