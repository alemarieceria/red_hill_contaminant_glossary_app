"""Smoke tests for the installed package and module command line."""

from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from contaminant_pipeline.paths import (
    INCOMING_GLOSSARY_WORKBOOK,
    INCOMING_REFERENCES_WORKBOOK,
)


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PACKAGE_FILE = (
    PIPELINE_ROOT / "src" / "contaminant_pipeline" / "__init__.py"
).resolve()
INSTALLED_DISTRIBUTION_NAME = "red-hill-contaminant-pipeline"
INSTALLED_DISTRIBUTION_VERSION = "0.1.0"


def run_isolated_python(
    *arguments: str,
    working_directory: Path,
) -> subprocess.CompletedProcess[str]:
    """Run this environment's Python without repository import shortcuts."""

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-I", *arguments],
        cwd=working_directory,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def process_failure_message(result: subprocess.CompletedProcess[str]) -> str:
    """Return captured child-process details for a useful test failure."""

    return (
        f"exit code: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def authoritative_workbook_digests() -> dict[Path, str]:
    """Fingerprint protected inputs without opening them as Excel files."""

    return {
        path: sha256(path.read_bytes()).hexdigest()
        for path in (
            INCOMING_GLOSSARY_WORKBOOK,
            INCOMING_REFERENCES_WORKBOOK,
        )
    }


class FoundationSmokeTests(unittest.TestCase):
    def test_installed_package_imports_from_src_layout(self) -> None:
        import_script = (
            "from importlib.metadata import version\n"
            "from pathlib import Path\n"
            "import contaminant_pipeline\n"
            f'print(version("{INSTALLED_DISTRIBUTION_NAME}"))\n'
            "print(Path(contaminant_pipeline.__file__).resolve())\n"
        )
        original_digests = authoritative_workbook_digests()

        with TemporaryDirectory(
            prefix=".foundation-smoke-",
            dir=PIPELINE_ROOT / "tests",
        ) as temporary_directory:
            working_directory = Path(temporary_directory)
            result = run_isolated_python(
                "-c",
                import_script,
                working_directory=working_directory,
            )

            self.assertEqual(
                result.returncode,
                0,
                process_failure_message(result),
            )
            output_lines = result.stdout.splitlines()
            self.assertEqual(
                output_lines,
                [
                    INSTALLED_DISTRIBUTION_VERSION,
                    str(EXPECTED_PACKAGE_FILE),
                ],
            )
            self.assertEqual(tuple(working_directory.iterdir()), ())

        self.assertEqual(authoritative_workbook_digests(), original_digests)

    def test_module_cli_help_runs_outside_the_project(self) -> None:
        original_digests = authoritative_workbook_digests()

        with TemporaryDirectory(
            prefix=".foundation-smoke-",
            dir=PIPELINE_ROOT / "tests",
        ) as temporary_directory:
            working_directory = Path(temporary_directory)
            result = run_isolated_python(
                "-m",
                "contaminant_pipeline",
                "--help",
                working_directory=working_directory,
            )

            self.assertEqual(
                result.returncode,
                0,
                process_failure_message(result),
            )
            self.assertIn("usage: contaminant-pipeline", result.stdout)
            self.assertIn("Red Hill contaminant glossary", result.stdout)
            self.assertEqual(result.stderr, "")
            self.assertEqual(tuple(working_directory.iterdir()), ())

        self.assertEqual(authoritative_workbook_digests(), original_digests)


if __name__ == "__main__":
    unittest.main()
