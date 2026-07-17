from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from contaminant_pipeline.config import (
    GLOSSARY_WORKBOOK_FILENAME,
    INTAKE_MANIFEST_SCHEMA_VERSION,
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
from contaminant_pipeline.paths import (
    CONTAMINANT_REGISTRY_PATH,
    INCOMING_DIR,
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    MANIFEST_DIR,
    OUTPUT_DIR,
    PIPELINE_ROOT,
    PROCESSED_DIR,
    PUBLIC_DATA_DIR,
    RAW_SNAPSHOTS_DIR,
    REFERENCE_CROSSWALK_PATH,
)
from fixture_paths import (
    SYNTHETIC_GLOSSARY_WORKBOOK,
    SYNTHETIC_REFERENCES_WORKBOOK,
)


FIXED_GIT = GitSourceState("commit", "a" * 40)
PROTECTED_PATHS = (
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
    RAW_SNAPSHOTS_DIR / "20260115" / GLOSSARY_WORKBOOK_FILENAME,
    CONTAMINANT_REGISTRY_PATH,
    REFERENCE_CROSSWALK_PATH,
    PIPELINE_ROOT / "pyproject.toml",
    PIPELINE_ROOT / "uv.lock",
)
GENERATED_ROOTS = (
    MANIFEST_DIR,
    RAW_SNAPSHOTS_DIR,
    PROCESSED_DIR,
    OUTPUT_DIR,
    PUBLIC_DATA_DIR,
)


def _copy_fixture_pair(directory: Path) -> None:
    directory.mkdir(parents=True)
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
        path: (path.read_bytes(), path.stat().st_size, path.stat().st_mtime_ns)
        for path in paths
    }


def _tree_state(roots):
    state = []
    for root in roots:
        state.append((root, root.exists(), root.is_symlink()))
        if not root.exists() or root.is_symlink():
            continue
        for path in sorted(root.rglob("*")):
            is_link = path.is_symlink()
            is_file = path.is_file() and not is_link
            state.append(
                (
                    path,
                    is_link,
                    path.is_dir() and not is_link,
                    path.read_bytes() if is_file else None,
                )
            )
    return tuple(state)


def _artifact_state(result):
    paths = (
        result.raw_snapshot.glossary_path,
        result.raw_snapshot.references_path,
        result.manifest.path,
    )
    return _file_state(paths), tuple(
        sorted(path.name for path in result.raw_snapshot.snapshot_dir.iterdir())
    )


class Phase2EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protected_before = _file_state(PROTECTED_PATHS)
        self.generated_before = _tree_state(GENERATED_ROOTS)
        self.temporary = TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self) -> None:
        try:
            self.assertEqual(_file_state(PROTECTED_PATHS), self.protected_before)
            self.assertEqual(_tree_state(GENERATED_ROOTS), self.generated_before)
        finally:
            self.temporary.cleanup()

    def test_authoritative_creation_and_retry_are_complete_and_read_only(self) -> None:
        inventory = inventory_incoming_pair(read_incoming_pair(INCOMING_DIR))
        raw_root = self.base / "raw"
        manifest_root = self.base / "manifests"
        created = publish_or_reuse_intake(inventory, raw_root, manifest_root)

        self.assertEqual(created.disposition, "created")
        self.assertTrue(created.raw_created)
        self.assertTrue(created.manifest_created)
        self.assertEqual(created.inventory.data_release_id, created.raw_snapshot.data_release_id)
        self.assertEqual(created.inventory.data_release_id, created.manifest.manifest.data_release_id)
        with self.assertRaises(FrozenInstanceError):
            created.disposition = "changed"

        expected_sources = (
            INCOMING_GLOSSARY_WORKBOOK,
            INCOMING_REFERENCES_WORKBOOK,
        )
        raw_paths = (
            created.raw_snapshot.glossary_path,
            created.raw_snapshot.references_path,
        )
        self.assertEqual(
            tuple(sorted(path.name for path in created.raw_snapshot.snapshot_dir.iterdir())),
            (GLOSSARY_WORKBOOK_FILENAME, REFERENCES_WORKBOOK_FILENAME),
        )
        for source, raw_path in zip(expected_sources, raw_paths, strict=True):
            self.assertEqual(raw_path.read_bytes(), source.read_bytes())

        manifest_bytes = created.manifest.path.read_bytes()
        self.assertEqual(manifest_bytes, created.manifest.serialized_bytes)
        self.assertTrue(manifest_bytes.endswith(b"\n"))
        self.assertFalse(manifest_bytes.endswith(b"\n\n"))
        self.assertNotIn(b"\r", manifest_bytes)
        document = json.loads(manifest_bytes)
        self.assertEqual(document["manifest_schema_version"], INTAKE_MANIFEST_SCHEMA_VERSION)
        self.assertIn(document["source_git"]["state"], {"commit", "local", "unknown"})
        for record, raw_path in zip(document["workbooks"], raw_paths, strict=True):
            content = raw_path.read_bytes()
            self.assertEqual(record["size_bytes"], len(content))
            self.assertEqual(record["sha256"], sha256(content).hexdigest())
            self.assertEqual(
                record["snapshot_path"],
                f"{created.inventory.data_release_id}/{raw_path.name}",
            )
            self.assertFalse(Path(record["snapshot_path"]).is_absolute())
            self.assertNotIn("00_incoming", record["snapshot_path"])

        before_retry = _artifact_state(created)
        with patch("contaminant_pipeline.intake.shutil.copyfile") as copying:
            with patch("contaminant_pipeline.intake.tempfile.mkdtemp") as raw_temp:
                with patch("contaminant_pipeline.intake.tempfile.mkstemp") as manifest_temp:
                    with patch("contaminant_pipeline.intake.subprocess.run") as git:
                        existing = publish_or_reuse_intake(
                            inventory,
                            raw_root,
                            manifest_root,
                        )
        self.assertEqual(existing.disposition, "existing")
        self.assertFalse(existing.raw_created)
        self.assertFalse(existing.manifest_created)
        self.assertEqual(_artifact_state(existing), before_retry)
        self.assertEqual(existing.manifest.serialized_bytes, manifest_bytes)
        copying.assert_not_called()
        raw_temp.assert_not_called()
        manifest_temp.assert_not_called()
        git.assert_not_called()

    def test_publication_is_deterministic_and_survives_disposable_source_removal(self) -> None:
        incoming = self.base / "incoming"
        _copy_fixture_pair(incoming)
        inventory = _inventory(incoming)
        first = publish_or_reuse_intake(
            inventory,
            self.base / "raw-one",
            self.base / "manifest-one",
            source_git=FIXED_GIT,
        )
        second = publish_or_reuse_intake(
            inventory,
            self.base / "raw-two",
            self.base / "manifest-two",
            source_git=FIXED_GIT,
        )
        self.assertEqual(first.manifest.serialized_bytes, second.manifest.serialized_bytes)
        self.assertEqual(
            first.raw_snapshot.glossary_path.read_bytes(),
            second.raw_snapshot.glossary_path.read_bytes(),
        )
        self.assertEqual(
            first.raw_snapshot.references_path.read_bytes(),
            second.raw_snapshot.references_path.read_bytes(),
        )

        for source in incoming.iterdir():
            source.unlink()
        incoming.rmdir()
        document = json.loads(first.manifest.path.read_bytes())
        for record in document["workbooks"]:
            snapshot = (self.base / "raw-one") / Path(record["snapshot_path"])
            content = snapshot.read_bytes()
            self.assertEqual(len(content), record["size_bytes"])
            self.assertEqual(sha256(content).hexdigest(), record["sha256"])

    def test_manifest_failures_leave_raw_recoverable(self) -> None:
        incoming = self.base / "incoming"
        _copy_fixture_pair(incoming)
        inventory = _inventory(incoming)
        original_read = Path.read_bytes
        cases = ("create", "write", "verify", "rename")
        for case in cases:
            with self.subTest(case=case):
                raw_root = self.base / f"raw-{case}"
                manifest_root = self.base / f"manifest-{case}"
                raw = publish_raw_snapshot(inventory, raw_root)
                raw_before = _file_state((raw.glossary_path, raw.references_path))

                if case == "create":
                    context = patch(
                        "contaminant_pipeline.intake.tempfile.mkstemp",
                        side_effect=OSError("create failure"),
                    )
                elif case == "write":
                    context = patch.object(
                        Path,
                        "write_bytes",
                        side_effect=OSError("write failure"),
                    )
                elif case == "verify":
                    def mismatching_read(path):
                        if path.name.startswith(f".{inventory.data_release_id}-"):
                            return b"different"
                        return original_read(path)

                    context = patch.object(
                        Path,
                        "read_bytes",
                        autospec=True,
                        side_effect=mismatching_read,
                    )
                else:
                    context = patch.object(
                        Path,
                        "replace",
                        side_effect=OSError("rename failure"),
                    )

                with context:
                    with self.assertRaises(IncomingContractError):
                        publish_or_reuse_intake(
                            inventory,
                            raw_root,
                            manifest_root,
                            source_git=FIXED_GIT,
                        )

                self.assertEqual(
                    _file_state((raw.glossary_path, raw.references_path)),
                    raw_before,
                )
                self.assertFalse(
                    (manifest_root / f"{inventory.data_release_id}.json").exists()
                )
                self.assertEqual(tuple(manifest_root.glob(".*.json")), ())
                recovered = publish_or_reuse_intake(
                    inventory,
                    raw_root,
                    manifest_root,
                    source_git=FIXED_GIT,
                )
                self.assertEqual(recovered.disposition, "recovered")
                self.assertFalse(recovered.raw_created)
                self.assertTrue(recovered.manifest_created)

    def test_raw_failures_publish_neither_artifact(self) -> None:
        incoming = self.base / "incoming"
        _copy_fixture_pair(incoming)
        inventory = _inventory(incoming)
        original_copy = copyfile
        cases = ("temporary", "first-copy", "second-copy", "rename")
        for case in cases:
            with self.subTest(case=case):
                raw_root = self.base / f"raw-{case}"
                manifest_root = self.base / f"manifest-{case}"
                calls = 0

                def failing_copy(source, destination):
                    nonlocal calls
                    calls += 1
                    if case == "first-copy" and calls == 1:
                        raise OSError("first copy failure")
                    if case == "second-copy" and calls == 2:
                        raise OSError("second copy failure")
                    return original_copy(source, destination)

                if case == "temporary":
                    context = patch(
                        "contaminant_pipeline.intake.tempfile.mkdtemp",
                        side_effect=OSError("temporary failure"),
                    )
                elif case == "rename":
                    context = patch.object(
                        Path,
                        "replace",
                        side_effect=OSError("rename failure"),
                    )
                else:
                    context = patch(
                        "contaminant_pipeline.intake.shutil.copyfile",
                        side_effect=failing_copy,
                    )

                with context:
                    with self.assertRaises(IncomingContractError):
                        publish_or_reuse_intake(
                            inventory,
                            raw_root,
                            manifest_root,
                            source_git=FIXED_GIT,
                        )
                self.assertFalse((raw_root / inventory.data_release_id).exists())
                self.assertFalse(manifest_root.exists())
                if raw_root.exists():
                    self.assertEqual(tuple(raw_root.iterdir()), ())

    def test_sources_changed_after_inventory_fail_without_being_repaired(self) -> None:
        for filename in (GLOSSARY_WORKBOOK_FILENAME, REFERENCES_WORKBOOK_FILENAME):
            with self.subTest(filename=filename):
                incoming = self.base / f"incoming-{filename}"
                _copy_fixture_pair(incoming)
                inventory = _inventory(incoming)
                changed = incoming / filename
                changed.write_bytes(changed.read_bytes() + b"changed")
                changed_bytes = changed.read_bytes()
                raw_root = self.base / f"raw-{filename}"
                manifest_root = self.base / f"manifest-{filename}"

                with self.assertRaisesRegex(IncomingContractError, "staged.*bytes"):
                    publish_or_reuse_intake(
                        inventory,
                        raw_root,
                        manifest_root,
                        source_git=FIXED_GIT,
                    )
                self.assertEqual(changed.read_bytes(), changed_bytes)
                self.assertFalse((raw_root / inventory.data_release_id).exists())
                self.assertFalse(manifest_root.exists())

    def test_same_release_collisions_preserve_the_completed_winner(self) -> None:
        for filename in (GLOSSARY_WORKBOOK_FILENAME, REFERENCES_WORKBOOK_FILENAME):
            with self.subTest(filename=filename):
                original = self.base / f"original-{filename}"
                changed = self.base / f"changed-{filename}"
                _copy_fixture_pair(original)
                _copy_fixture_pair(changed)
                raw_root = self.base / f"raw-collision-{filename}"
                manifest_root = self.base / f"manifest-collision-{filename}"
                winner = publish_or_reuse_intake(
                    _inventory(original),
                    raw_root,
                    manifest_root,
                    source_git=FIXED_GIT,
                )
                winner_before = _artifact_state(winner)
                source = changed / filename
                source.write_bytes(source.read_bytes() + b"changed")
                contender = _inventory(changed)
                self.assertEqual(contender.data_release_id, winner.inventory.data_release_id)

                with self.assertRaisesRegex(
                    IncomingContractError,
                    "revision collision.*different (size|SHA-256)",
                ):
                    publish_or_reuse_intake(
                        contender,
                        raw_root,
                        manifest_root,
                        source_git=FIXED_GIT,
                    )
                self.assertEqual(_artifact_state(winner), winner_before)

    def test_existing_state_and_malformed_history_fail_closed(self) -> None:
        incoming = self.base / "incoming"
        _copy_fixture_pair(incoming)
        inventory = _inventory(incoming)
        raw_root = self.base / "raw"
        manifest_root = self.base / "manifests"
        other_raw = publish_raw_snapshot(inventory, self.base / "other-raw")
        manifest = publish_intake_manifest(
            other_raw,
            manifest_root,
            source_git=FIXED_GIT,
        )

        with self.assertRaisesRegex(IncomingContractError, "without its raw"):
            publish_or_reuse_intake(
                inventory,
                raw_root,
                manifest_root,
                source_git=FIXED_GIT,
            )
        self.assertFalse((raw_root / inventory.data_release_id).exists())

        manifest.path.unlink()
        malformed_cases = {
            "unexpected.txt": b"unexpected",
            "bad-name.json": b"{}\n",
            f"{inventory.data_release_id}.json": b'{"duplicate":1,"duplicate":2}\n',
        }
        for name, content in malformed_cases.items():
            with self.subTest(name=name):
                for child in manifest_root.iterdir():
                    child.unlink()
                (manifest_root / name).write_bytes(content)
                with self.assertRaises(IncomingContractError):
                    publish_or_reuse_intake(
                        inventory,
                        raw_root,
                        manifest_root,
                        source_git=FIXED_GIT,
                    )
                self.assertEqual((manifest_root / name).read_bytes(), content)
                self.assertFalse((raw_root / inventory.data_release_id).exists())

    def test_hidden_staging_is_ignored_but_arbitrary_hidden_history_is_not(self) -> None:
        incoming = self.base / "incoming"
        _copy_fixture_pair(incoming)
        inventory = _inventory(incoming)
        manifest_root = self.base / "manifests"
        manifest_root.mkdir()
        owned = manifest_root / f".{inventory.data_release_id}-leftover.json"
        owned.write_bytes(b"controlled leftover")
        result = publish_or_reuse_intake(
            inventory,
            self.base / "raw",
            manifest_root,
            source_git=FIXED_GIT,
        )
        self.assertEqual(result.disposition, "created")
        self.assertEqual(owned.read_bytes(), b"controlled leftover")

        second_manifest = self.base / "manifests-two"
        second_manifest.mkdir()
        arbitrary = second_manifest / ".unrelated"
        arbitrary.write_bytes(b"keep")
        with self.assertRaisesRegex(IncomingContractError, "unexpected.*history"):
            publish_or_reuse_intake(
                inventory,
                self.base / "raw-two",
                second_manifest,
                source_git=FIXED_GIT,
            )
        self.assertEqual(arbitrary.read_bytes(), b"keep")

    def test_final_revalidation_rejects_post_publication_mutation(self) -> None:
        incoming = self.base / "incoming"
        _copy_fixture_pair(incoming)
        inventory = _inventory(incoming)
        original_manifest_publisher = publish_intake_manifest

        raw_root = self.base / "raw-mutated"
        manifest_root = self.base / "manifest-mutated"

        def mutate_raw_after_manifest(*args, **kwargs):
            result = original_manifest_publisher(*args, **kwargs)
            result.raw_snapshot.glossary_path.write_bytes(b"changed after manifest")
            return result

        with patch(
            "contaminant_pipeline.intake.publish_intake_manifest",
            side_effect=mutate_raw_after_manifest,
        ):
            with self.assertRaisesRegex(IncomingContractError, "different size"):
                publish_or_reuse_intake(
                    inventory,
                    raw_root,
                    manifest_root,
                    source_git=FIXED_GIT,
                )

        raw_root_two = self.base / "raw-manifest-mutated"
        manifest_root_two = self.base / "manifest-manifest-mutated"

        def mutate_manifest_after_publish(*args, **kwargs):
            result = original_manifest_publisher(*args, **kwargs)
            result.path.write_bytes(b"changed after publication")
            return result

        with patch(
            "contaminant_pipeline.intake.publish_intake_manifest",
            side_effect=mutate_manifest_after_publish,
        ):
            with self.assertRaises(IncomingContractError):
                publish_or_reuse_intake(
                    inventory,
                    raw_root_two,
                    manifest_root_two,
                    source_git=FIXED_GIT,
                )

    def test_representative_early_contract_failures_create_no_outputs(self) -> None:
        cases = ("missing", "swapped", "corrupt")
        for case in cases:
            with self.subTest(case=case):
                incoming = self.base / f"incoming-{case}"
                _copy_fixture_pair(incoming)
                if case == "missing":
                    (incoming / REFERENCES_WORKBOOK_FILENAME).unlink()
                elif case == "swapped":
                    glossary = incoming / GLOSSARY_WORKBOOK_FILENAME
                    references = incoming / REFERENCES_WORKBOOK_FILENAME
                    glossary_bytes = glossary.read_bytes()
                    glossary.write_bytes(references.read_bytes())
                    references.write_bytes(glossary_bytes)
                else:
                    (incoming / GLOSSARY_WORKBOOK_FILENAME).write_bytes(b"not xlsx")
                raw_root = self.base / f"raw-{case}"
                manifest_root = self.base / f"manifest-{case}"

                with self.assertRaises(IncomingContractError):
                    pair = read_incoming_pair(incoming)
                    inventory = inventory_incoming_pair(pair)
                    publish_or_reuse_intake(
                        inventory,
                        raw_root,
                        manifest_root,
                        source_git=FIXED_GIT,
                    )
                self.assertFalse(raw_root.exists())
                self.assertFalse(manifest_root.exists())


if __name__ == "__main__":
    unittest.main()
