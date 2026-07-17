from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from shutil import copyfile
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from contaminant_pipeline.config import (
    GLOSSARY_WORKBOOK_FILENAME,
    INTAKE_MANIFEST_SCHEMA_VERSION,
    REFERENCES_WORKBOOK_FILENAME,
)
from contaminant_pipeline.intake import (
    GitSourceState,
    IncomingContractError,
    build_intake_manifest,
    inspect_git_source_state,
    inventory_incoming_pair,
    publish_intake_manifest,
    publish_raw_snapshot,
    read_incoming_pair,
    serialize_intake_manifest,
    validate_git_source_state,
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


COMMIT = "a" * 40
FIXED_GIT = GitSourceState("commit", COMMIT)
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


def _raw_publication(base: Path, incoming: Path | None = None):
    source = incoming or base / "incoming"
    if incoming is None:
        source.mkdir()
        _copy_fixture_pair(source)
    inventory = inventory_incoming_pair(read_incoming_pair(source))
    return publish_raw_snapshot(inventory, base / "raw")


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


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


class GitSourceStateTests(unittest.TestCase):
    def test_classifies_clean_dirty_and_untracked_repositories(self) -> None:
        cases = (
            ("", "commit"),
            (" M data.xlsx\n", "local"),
            ("?? new.xlsx\n", "local"),
        )
        for status, expected in cases:
            with self.subTest(expected=expected):
                runner = Mock(
                    side_effect=(
                        _completed(stdout=COMMIT + "\n"),
                        _completed(stdout=status),
                    )
                )

                result = inspect_git_source_state(".", runner=runner)

                self.assertEqual(result, GitSourceState(expected, COMMIT))
                commands = [call.args[0] for call in runner.call_args_list]
                self.assertEqual(commands[0], ["git", "rev-parse", "--verify", "HEAD"])
                self.assertEqual(
                    commands[1],
                    [
                        "git",
                        "status",
                        "--porcelain=v1",
                        "--untracked-files=all",
                    ],
                )
                if status.strip():
                    self.assertNotIn(status.strip(), repr(result))

    def test_uses_unknown_for_unavailable_or_untrustworthy_git(self) -> None:
        cases = (
            Mock(side_effect=OSError("missing git")),
            Mock(side_effect=subprocess.TimeoutExpired("git", 10)),
            Mock(return_value=_completed(returncode=1)),
            Mock(return_value=_completed(stdout="not-a-commit\n")),
            Mock(
                side_effect=(
                    _completed(stdout=COMMIT + "\n"),
                    _completed(returncode=1),
                )
            ),
        )
        for runner in cases:
            with self.subTest(runner=runner):
                self.assertEqual(
                    inspect_git_source_state(".", runner=runner),
                    GitSourceState("unknown", None),
                )

    def test_rejects_contradictory_git_records(self) -> None:
        valid = (
            GitSourceState("commit", COMMIT),
            GitSourceState("local", COMMIT),
            GitSourceState("unknown", None),
        )
        for state in valid:
            self.assertIs(validate_git_source_state(state), state)

        invalid = (
            GitSourceState("other", None),
            GitSourceState("commit", None),
            GitSourceState("local", "ABC"),
            GitSourceState("unknown", COMMIT),
        )
        for state in invalid:
            with self.subTest(state=state):
                with self.assertRaises(IncomingContractError):
                    validate_git_source_state(state)


class IntakeManifestSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.raw = _raw_publication(self.base)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_builds_complete_portable_synthetic_manifest(self) -> None:
        manifest = build_intake_manifest(self.raw, FIXED_GIT)
        serialized = serialize_intake_manifest(manifest)
        data = json.loads(serialized)

        self.assertEqual(
            set(data),
            {
                "data_release_id",
                "manifest_schema_version",
                "source_git",
                "workbooks",
            },
        )
        self.assertEqual(data["manifest_schema_version"], INTAKE_MANIFEST_SCHEMA_VERSION)
        self.assertEqual(data["data_release_id"], "20000115-r2")
        self.assertEqual(
            data["source_git"],
            {"state": "commit", "head_commit": COMMIT},
        )
        self.assertEqual(
            [workbook["workbook_type"] for workbook in data["workbooks"]],
            ["contaminant_glossary", "references"],
        )
        self.assertEqual(
            [workbook["workbook_revision"] for workbook in data["workbooks"]],
            ["20000115", "20000115-r2"],
        )
        self.assertEqual(
            [workbook["snapshot_path"] for workbook in data["workbooks"]],
            [
                "20000115-r2/contaminant_glossary.xlsx",
                "20000115-r2/references.xlsx",
            ],
        )
        for record, inventory in zip(
            data["workbooks"],
            (
                self.raw.inventory.glossary_inventory,
                self.raw.inventory.references_inventory,
            ),
            strict=True,
        ):
            self.assertEqual(record["size_bytes"], inventory.size_bytes)
            self.assertEqual(record["sha256"], inventory.sha256)
            self.assertEqual(record["worksheet_count"], inventory.worksheet_count)
            self.assertEqual(len(record["worksheets"]), inventory.worksheet_count)
            self.assertIn("headers", record["worksheets"][0])
            self.assertIn("tables", record["worksheets"][0])
            self.assertIn("formulas", record["worksheets"][0])
        text = serialized.decode("utf-8")
        self.assertNotIn(str(self.base), text)
        self.assertNotIn("data/00_incoming", text)
        self.assertNotIn("Synthetic Alpha", text)
        self.assertNotIn("\\r", repr(text))
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_serialization_is_deterministic_utf8_and_escaped(self) -> None:
        manifest = build_intake_manifest(self.raw, FIXED_GIT)
        workbook = manifest.workbooks[0]
        inventory = workbook.inventory
        worksheet = inventory.worksheets[1]
        header = worksheet.headers[0]
        special = 'Hawaiʻi "quoted" \\ path\nline'
        changed_worksheet = replace(
            worksheet,
            headers=(replace(header, value=special), *worksheet.headers[1:]),
        )
        changed_inventory = replace(
            inventory,
            worksheets=(
                inventory.worksheets[0],
                changed_worksheet,
                *inventory.worksheets[2:],
            ),
        )
        changed = replace(
            manifest,
            workbooks=(replace(workbook, inventory=changed_inventory), manifest.workbooks[1]),
        )

        first = serialize_intake_manifest(changed)
        second = serialize_intake_manifest(changed)

        self.assertEqual(first, second)
        self.assertIn("Hawaiʻi".encode(), first)
        self.assertNotIn(b"\\u02bb", first)
        parsed = json.loads(first)
        self.assertEqual(
            parsed["workbooks"][0]["worksheets"][1]["headers"][0]["value"],
            special,
        )
        self.assertNotIn(b"\r", first)

    def test_manifest_records_are_immutable_and_validate_schema(self) -> None:
        manifest = build_intake_manifest(self.raw, FIXED_GIT)
        with self.assertRaises(FrozenInstanceError):
            manifest.data_release_id = "changed"
        with self.assertRaisesRegex(IncomingContractError, "schema"):
            serialize_intake_manifest(
                replace(manifest, manifest_schema_version="2.0.0")
            )


class IntakeManifestPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.raw = _raw_publication(self.base)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_atomically_publishes_equal_bytes_to_separate_roots(self) -> None:
        first = publish_intake_manifest(
            self.raw,
            self.base / "manifests-one",
            source_git=FIXED_GIT,
        )
        second = publish_intake_manifest(
            self.raw,
            self.base / "manifests-two",
            source_git=FIXED_GIT,
        )

        self.assertEqual(first.serialized_bytes, second.serialized_bytes)
        self.assertEqual(first.path.read_bytes(), first.serialized_bytes)
        self.assertEqual(first.path.name, "20000115-r2.json")
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(tuple(first.path.parent.glob(".20000115-r2-*.json")), ())
        with self.assertRaises(FrozenInstanceError):
            first.path = Path("changed")

    def test_target_appears_only_at_the_atomic_rename(self) -> None:
        manifest_root = self.base / "manifests"
        target = manifest_root.resolve() / "20000115-r2.json"
        original_replace = Path.replace
        observations = []

        def observing_replace(temporary, destination):
            observations.append(
                (destination.exists(), temporary.read_bytes().startswith(b"{"))
            )
            return original_replace(temporary, destination)

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=observing_replace,
        ):
            result = publish_intake_manifest(
                self.raw,
                manifest_root,
                source_git=FIXED_GIT,
            )

        self.assertEqual(observations, [(False, True)])
        self.assertEqual(result.path, target)

    def test_unknown_git_state_still_publishes(self) -> None:
        result = publish_intake_manifest(
            self.raw,
            self.base / "manifests",
            source_git=GitSourceState("unknown", None),
        )
        self.assertEqual(
            json.loads(result.serialized_bytes)["source_git"],
            {"state": "unknown", "head_commit": None},
        )

    def test_rejects_invalid_raw_snapshot_before_git_or_staging(self) -> None:
        self.raw.references_path.write_bytes(b"changed")
        runner = Mock()
        with patch("contaminant_pipeline.intake.tempfile.mkstemp") as staging:
            with self.assertRaisesRegex(IncomingContractError, "references snapshot bytes"):
                publish_intake_manifest(
                    self.raw,
                    self.base / "manifests",
                    git_runner=runner,
                )
        runner.assert_not_called()
        staging.assert_not_called()

    def test_rejects_missing_extra_and_inconsistent_raw_publications(self) -> None:
        cases = []
        wrong_release = replace(self.raw, data_release_id="20000116")
        cases.append((wrong_release, "release relationships"))
        wrong_path = replace(
            self.raw,
            glossary_path=self.raw.snapshot_dir / "wrong.xlsx",
        )
        cases.append((wrong_path, "snapshot path"))
        for publication, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(IncomingContractError, message):
                    build_intake_manifest(publication, FIXED_GIT)

        extra = self.raw.snapshot_dir / "extra.txt"
        extra.write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(IncomingContractError, "exactly the two"):
            publish_intake_manifest(
                self.raw,
                self.base / "manifests-extra",
                source_git=FIXED_GIT,
            )

    def test_refuses_invalid_roots_and_existing_targets(self) -> None:
        root_file = self.base / "manifest-file"
        root_file.write_text("not a directory", encoding="utf-8")
        with self.assertRaisesRegex(IncomingContractError, "not a directory"):
            publish_intake_manifest(self.raw, root_file, source_git=FIXED_GIT)

        root = self.base / "existing"
        root.mkdir()
        target = root / "20000115-r2.json"
        target.write_bytes(b"existing")
        with self.assertRaisesRegex(IncomingContractError, "already exists"):
            publish_intake_manifest(self.raw, root, source_git=FIXED_GIT)
        self.assertEqual(target.read_bytes(), b"existing")


class IntakeManifestFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.raw = _raw_publication(self.base)
        self.manifest_root = self.base / "manifests"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _assert_no_manifest(self):
        self.assertFalse((self.manifest_root / "20000115-r2.json").exists())
        self.assertEqual(tuple(self.manifest_root.glob(".20000115-r2-*.json")), ())

    def test_cleans_temporary_file_after_write_and_readback_failures(self) -> None:
        with patch.object(Path, "write_bytes", side_effect=OSError("write failure")):
            with self.assertRaisesRegex(IncomingContractError, "could not publish"):
                publish_intake_manifest(
                    self.raw,
                    self.manifest_root,
                    source_git=FIXED_GIT,
                )
        self._assert_no_manifest()

        original_read_bytes = Path.read_bytes

        def mismatching_read(path):
            if path.name.startswith(".20000115-r2-"):
                return b"different"
            return original_read_bytes(path)

        with patch.object(
            Path,
            "read_bytes",
            autospec=True,
            side_effect=mismatching_read,
        ):
            with self.assertRaisesRegex(IncomingContractError, "verification failed"):
                publish_intake_manifest(
                    self.raw,
                    self.manifest_root,
                    source_git=FIXED_GIT,
                )
        self._assert_no_manifest()

    def test_cleans_temporary_file_after_rename_failure(self) -> None:
        with patch.object(Path, "replace", side_effect=OSError("rename failure")):
            with self.assertRaisesRegex(IncomingContractError, "could not publish"):
                publish_intake_manifest(
                    self.raw,
                    self.manifest_root,
                    source_git=FIXED_GIT,
                )
        self._assert_no_manifest()

    def test_manifest_target_race_preserves_competing_file(self) -> None:
        target = self.manifest_root.resolve() / "20000115-r2.json"

        def racing_replace(_temporary, destination):
            destination.write_bytes(b"competitor")
            raise OSError("race")

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=racing_replace,
        ):
            with self.assertRaisesRegex(IncomingContractError, "could not publish"):
                publish_intake_manifest(
                    self.raw,
                    self.manifest_root,
                    source_git=FIXED_GIT,
                )

        self.assertEqual(target.read_bytes(), b"competitor")
        self.assertEqual(tuple(self.manifest_root.glob(".20000115-r2-*.json")), ())

    def test_reports_cleanup_failure_without_removing_raw_snapshot(self) -> None:
        with patch.object(Path, "replace", side_effect=OSError("rename failure")):
            with patch.object(Path, "unlink", side_effect=OSError("cleanup failure")):
                with self.assertRaisesRegex(
                    IncomingContractError,
                    "cleanup also failed",
                ) as raised:
                    publish_intake_manifest(
                        self.raw,
                        self.manifest_root,
                        source_git=FIXED_GIT,
                    )

        leftovers = tuple(self.manifest_root.glob(".20000115-r2-*.json"))
        self.assertEqual(len(leftovers), 1)
        self.assertIn(str(leftovers[0]), str(raised.exception))
        self.assertTrue(self.raw.glossary_path.is_file())
        self.assertTrue(self.raw.references_path.is_file())


class AuthoritativeIntakeManifestTests(unittest.TestCase):
    def test_builds_authoritative_manifest_only_in_disposable_roots(self) -> None:
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
            base = Path(temporary)
            inventory = inventory_incoming_pair(read_incoming_pair(INCOMING_DIR))
            raw = publish_raw_snapshot(inventory, base / "raw")
            result = publish_intake_manifest(raw, base / "manifests")
            data = json.loads(result.serialized_bytes)
            self.assertIn(data["source_git"]["state"], {"commit", "local", "unknown"})
            for record, path in zip(
                data["workbooks"],
                (raw.glossary_path, raw.references_path),
                strict=True,
            ):
                content = path.read_bytes()
                self.assertEqual(record["size_bytes"], len(content))
                self.assertEqual(record["sha256"], __import__("hashlib").sha256(content).hexdigest())

        self.assertEqual(_file_state(protected_paths), protected_before)
        self.assertEqual(_tree_state(GENERATED_ROOTS), generated_before)

    def test_generated_manifest_paths_are_ignored(self) -> None:
        paths = (
            MANIFEST_DIR / "20991231.json",
            MANIFEST_DIR / ".20991231-example.json",
        )
        for path in paths:
            result = subprocess.run(
                ["git", "check-ignore", "-q", "--", str(path)],
                cwd=REPOSITORY_ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
