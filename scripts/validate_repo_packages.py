#!/usr/bin/env python3
"""Validate that every source addon version has a matching installable ZIP."""

from __future__ import annotations

import argparse
from pathlib import Path

from build_repo import get_source_dirs, validate_addon_packages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root directory.",
    )
    return parser.parse_args()


def main() -> None:
    root_dir = parse_args().root.resolve()
    addon_dirs = get_source_dirs(root_dir)
    validate_addon_packages(root_dir, addon_dirs)
    print(f"Validated {len(addon_dirs)} addon packages")


if __name__ == "__main__":
    main()
