from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import runpy
import unittest
from unittest.mock import patch

from contaminant_pipeline.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_builds_a_stable_parser(self) -> None:
        parser = build_parser()

        self.assertEqual(parser.prog, "contaminant-pipeline")
        self.assertIn("Red Hill contaminant glossary", parser.description)
        self.assertIn("--help", parser.format_help())

    def test_no_arguments_prints_help_without_reading_workbooks(self) -> None:
        stdout = StringIO()

        with patch("contaminant_pipeline.io_excel.read_workbook") as read_workbook:
            with redirect_stdout(stdout):
                exit_code = main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("usage: contaminant-pipeline", stdout.getvalue())
        read_workbook.assert_not_called()

    def test_explicit_help_exits_successfully(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("usage: contaminant-pipeline", stdout.getvalue())

    def test_unknown_arguments_exit_with_an_error(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                main(["--not-a-command"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("unrecognized arguments", stderr.getvalue())

    def test_module_entry_point_returns_main_exit_code(self) -> None:
        with patch("contaminant_pipeline.cli.main", return_value=7) as mocked_main:
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module(
                    "contaminant_pipeline.__main__",
                    run_name="__main__",
                )

        self.assertEqual(raised.exception.code, 7)
        mocked_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
