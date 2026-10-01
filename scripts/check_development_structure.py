#!/usr/bin/env python3
"""Check that the repository's required development structure exists."""

import argparse
from pathlib import Path


REQUIRED_FILES = (
    Path("AGENTS.md"),
    Path(".agent/PLANS.md"),
    Path("docs/development/orchestration.md"),
)
REQUIRED_DIRECTORIES = (
    Path("docs/exec-plans/active"),
    Path("docs/exec-plans/completed"),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check required development policy files and plan directories."
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="repository root to check (defaults to this script's repository)",
    )
    args = parser.parse_args()

    root = (
        args.root.resolve()
        if args.root is not None
        else Path(__file__).resolve().parent.parent
    )
    failures: list[tuple[Path, str]] = []

    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).is_file():
            failures.append((relative_path, "regular file"))

    for relative_path in REQUIRED_DIRECTORIES:
        if not (root / relative_path).is_dir():
            failures.append((relative_path, "directory"))

    if failures:
        print(f"Development structure check failed: {len(failures)} required path(s) invalid.")
        for relative_path, expected_type in failures:
            print(f"- {relative_path.as_posix()}: expected {expected_type}")
        return 1

    print("Development structure check passed (5 required paths).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
