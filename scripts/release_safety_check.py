#!/usr/bin/env python3
"""Reject unsafe Kodi repository commits and pushes before they leave the machine."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DELETION_LIMIT = 40
CONFLICT_MARKERS = ("[conflicted", "(conflicted", " conflicted copy")


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def changed_paths(args: list[str]) -> list[tuple[str, str]]:
    output = git_output("diff", "--name-status", "-z", *args)
    fields = output.split("\0")
    changes: list[tuple[str, str]] = []
    index = 0
    while index < len(fields) - 1:
        status = fields[index]
        index += 1
        if not status:
            continue
        path = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            path = fields[index]
            index += 1
        changes.append((status, path))
    return changes


def fail(message: str) -> None:
    print(f"release safety check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def allow_large_deletion() -> bool:
    return os.environ.get("KODIREPO_ALLOW_LARGE_DELETION") == "1"


def check_conflict_artifacts() -> None:
    untracked = git_output("ls-files", "--others", "--exclude-standard").splitlines()
    conflict_files = [path for path in untracked if any(marker in path.lower() for marker in CONFLICT_MARKERS)]
    if conflict_files:
        fail("untracked sync-conflict files exist: " + ", ".join(conflict_files[:5]))

    refs_dir = ROOT / ".git" / "refs"
    if refs_dir.exists():
        bad_refs = [path for path in refs_dir.rglob("*") if path.is_file() and any(marker in path.name.lower() for marker in CONFLICT_MARKERS)]
        if bad_refs:
            fail("sync-conflict Git refs exist: " + ", ".join(str(path.relative_to(ROOT)) for path in bad_refs[:5]))


def check_deletions(changes: list[tuple[str, str]]) -> None:
    deleted = [path for status, path in changes if status == "D"]
    critical = [path for path in deleted if path in {"addons.xml", "addons.xml.md5"}]
    if (len(deleted) > DELETION_LIMIT or critical) and not allow_large_deletion():
        details = f"{len(deleted)} deleted paths"
        if critical:
            details += f" including {', '.join(critical)}"
        fail(details + ". Restore the files or deliberately override with KODIREPO_ALLOW_LARGE_DELETION=1.")


def check_repository_integrity() -> None:
    result = subprocess.run(["git", "fsck", "--full", "--no-reflogs"], cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        fail("Git object integrity check failed: " + (result.stderr or result.stdout).strip())


def check_package_feeds() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_repo_packages.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        fail("package feed validation failed: " + (result.stderr or result.stdout).strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="check the staged commit content")
    parser.add_argument("--range", nargs=2, metavar=("BASE", "HEAD"), help="check a proposed push range")
    args = parser.parse_args()
    if args.staged == bool(args.range):
        parser.error("provide exactly one of --staged or --range")

    diff_args = ["--cached"] if args.staged else [args.range[0], args.range[1]]
    check_conflict_artifacts()
    check_deletions(changed_paths(diff_args))
    check_repository_integrity()
    check_package_feeds()
    print("Release safety check passed")


if __name__ == "__main__":
    main()
