"""Command-line entry point for the contaminant pipeline."""

import argparse
from collections.abc import Sequence
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without reading data or changing files."""

    return argparse.ArgumentParser(
        prog="contaminant-pipeline",
        description=(
            "Validate and publish Red Hill contaminant glossary data. "
            "Pipeline commands will be added as their phases are implemented."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line arguments and return a process exit code."""

    parser = build_parser()
    arguments = list(argv) if argv is not None else sys.argv[1:]

    if not arguments:
        parser.print_help()
        return 0

    parser.parse_args(arguments)
    return 0
