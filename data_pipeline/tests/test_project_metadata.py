import sys
import tomllib
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]


class ProjectMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pyproject_path = PIPELINE_ROOT / "pyproject.toml"
        with pyproject_path.open("rb") as pyproject_file:
            cls.pyproject = tomllib.load(pyproject_file)
        cls.project = cls.pyproject["project"]

    def test_declares_supported_python_range_and_local_version(self) -> None:
        self.assertEqual(self.project["requires-python"], ">=3.11,<3.14")
        self.assertEqual(
            (PIPELINE_ROOT / ".python-version").read_text(encoding="utf-8").strip(),
            "3.13",
        )
        self.assertGreaterEqual(sys.version_info[:2], (3, 11))
        self.assertLess(sys.version_info[:2], (3, 14))

    def test_keeps_release_dependencies_minimal(self) -> None:
        dependencies = "\n".join(self.project["dependencies"]).lower()

        for package in ("pandas", "openpyxl", "pydantic"):
            self.assertIn(package, dependencies)
        for package in ("pytest", "httpx", "rdkit", "argparse"):
            self.assertNotIn(package, dependencies)

    def test_separates_development_and_optional_features(self) -> None:
        extras = self.project["optional-dependencies"]

        self.assertEqual(set(extras), {"dev", "enrichment", "chemistry"})
        self.assertTrue(any(item.startswith("pytest") for item in extras["dev"]))
        self.assertTrue(
            any(item.startswith("httpx") for item in extras["enrichment"])
        )
        self.assertTrue(
            any(item.startswith("rdkit") for item in extras["chemistry"])
        )

    def test_configures_src_package_build(self) -> None:
        self.assertEqual(
            self.pyproject["build-system"]["build-backend"],
            "hatchling.build",
        )
        self.assertEqual(
            self.pyproject["tool"]["hatch"]["build"]["targets"]["wheel"][
                "packages"
            ],
            ["src/contaminant_pipeline"],
        )

    def test_configures_test_and_lint_tools(self) -> None:
        tools = self.pyproject["tool"]

        self.assertEqual(tools["pytest"]["ini_options"]["testpaths"], ["tests"])
        self.assertEqual(tools["ruff"]["target-version"], "py311")
        self.assertIn("F", tools["ruff"]["lint"]["select"])
        self.assertTrue(
            any(
                item.startswith("ruff")
                for item in self.project["optional-dependencies"]["dev"]
            )
        )


if __name__ == "__main__":
    unittest.main()
