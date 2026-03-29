#!/usr/bin/env python3
"""Publish addon updates without bumping the repository addon version."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess

from build_repo import (
    build_addons_xml,
    get_source_dirs,
    git_output,
    import_root_addon_zips,
    mirror_addon_source,
    package_addon,
    write_md5,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root directory.",
    )
    return parser.parse_args()


def update_addon_outputs(root_dir: Path, addon_ids: list[str], source_dirs: list[Path]) -> None:
    source_map = {addon_dir.name: addon_dir for addon_dir in source_dirs}
    for addon_id in addon_ids:
        addon_dir = source_map.get(addon_id)
        if addon_dir is None:
            raise SystemExit(f"Imported addon source missing after extraction: {addon_id}")
        output_dir = root_dir / "zips" / addon_id
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        mirror_addon_source(addon_dir, output_dir)
        package_addon(addon_dir, output_dir)


def ensure_publish_ready(root_dir: Path, addon_ids: list[str]) -> None:
    status = git_output(root_dir, "status", "--porcelain").splitlines()
    allowed_prefixes = tuple(
        [
            "addons.xml",
            "addons.xml.md5",
            "scripts/publish_addon_update.py",
            *addon_ids,
            *[f"zips/{addon_id}" for addon_id in addon_ids],
        ]
    )
    unexpected = []
    for line in status:
        path = line[3:]
        if " -> " in path:
            _old, path = path.split(" -> ", 1)
        if path.startswith(allowed_prefixes):
            continue
        unexpected.append(line)
    if unexpected:
        raise SystemExit(
            "Refusing to publish addon update with unrelated worktree changes:\n"
            + "\n".join(unexpected)
        )


def publish_changes(root_dir: Path, addon_ids: list[str]) -> None:
    ensure_publish_ready(root_dir, addon_ids)
    subprocess.run(["git", "add", "--all", "."], cwd=root_dir, check=True)
    if not git_output(root_dir, "diff", "--cached", "--name-only").strip():
        print("No addon update changes to commit")
        return
    summary = ", ".join(addon_ids)
    subprocess.run(
        ["git", "commit", "-m", f"Publish addon update: {summary}"],
        cwd=root_dir,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=root_dir, check=True)


def main() -> None:
    args = parse_args()
    root_dir = args.root.resolve()
    imported_ids = import_root_addon_zips(root_dir)
    if not imported_ids:
        raise SystemExit("No addon zip found in repo root")

    source_dirs = get_source_dirs(root_dir)
    update_addon_outputs(root_dir, imported_ids, source_dirs)
    build_addons_xml(source_dirs, root_dir / "addons.xml")
    write_md5(root_dir / "addons.xml")

    print(f"Updated addons: {', '.join(imported_ids)}")
    publish_changes(root_dir, imported_ids)


if __name__ == "__main__":
    main()
