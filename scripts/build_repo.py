#!/usr/bin/env python3
"""Build a static Kodi addon repository layout for GitHub Pages."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import xml.etree.ElementTree as ET
import zipfile


DEFAULT_BASE_URL = "https://TechXXX.github.io/kodirepo/"
DEFAULT_REPO_DATA_BASE_URL = "https://raw.githubusercontent.com/TechXXX/kodirepo/main/"
REPO_ADDON_ID = "repository.dutchtech"
REPO_ADDON_NAME = "DutchTech Repository"
REPO_PROVIDER = "DutchTech"
REPO_SUMMARY = "Repository for DutchTech Kodi add-ons."
REPO_DESCRIPTION = (
    "Install this repository to receive DutchTech Kodi add-on updates "
    "from a GitHub Pages-hosted source."
)
REPO_ALLOWED_FILES = {"addon.xml", "icon.png", "fanart.jpg"}
STATIC_PUBLISH_PATHS = [
    "addons.xml",
    "addons.xml.md5",
    "index.html",
    "scripts/build_repo.py",
]
EXCLUDED_SOURCE_DIRS = {"scripts", "zips", "__pycache__"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("KODI_REPO_BASE_URL", DEFAULT_BASE_URL),
        help="Public GitHub Pages base URL for this repo.",
    )
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root directory.",
    )
    parser.add_argument(
        "--repo-data-base-url",
        default=os.environ.get("KODI_REPO_DATA_BASE_URL", DEFAULT_REPO_DATA_BASE_URL),
        help="Base URL Kodi should use for addons.xml, addons.xml.md5, and zips.",
    )
    return parser.parse_args()


def normalize_base_url(value: str) -> str:
    return value.rstrip("/") + "/"


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def indent_xml(elem: ET.Element, level: int = 0) -> None:
    indent = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "    "
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = indent


def get_addon_info(addon_xml: Path) -> tuple[str, str]:
    root = ET.parse(addon_xml).getroot()
    return root.attrib["id"], root.attrib["version"]


def bump_version(version: str) -> str:
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def ensure_repo_addon_source(root_dir: Path, repo_data_base_url: str) -> tuple[Path, str]:
    repo_dir = root_dir / REPO_ADDON_ID
    repo_dir.mkdir(parents=True, exist_ok=True)
    addon_xml_path = repo_dir / "addon.xml"

    current_version = "1.0.0"
    if addon_xml_path.exists():
        current_root = ET.parse(addon_xml_path).getroot()
        current_version = current_root.attrib.get("version", current_version)
    repo_version = bump_version(current_version)

    addon_xml = textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <addon id="{REPO_ADDON_ID}" name="{REPO_ADDON_NAME}" provider-name="{REPO_PROVIDER}" version="{repo_version}">
            <extension point="xbmc.addon.repository" name="{REPO_ADDON_NAME}">
                <dir>
                    <info compressed="false">{repo_data_base_url}addons.xml</info>
                    <checksum>{repo_data_base_url}addons.xml.md5</checksum>
                    <datadir zip="true">{repo_data_base_url}zips/</datadir>
                </dir>
            </extension>
            <extension point="xbmc.addon.metadata">
                <summary>{REPO_SUMMARY}</summary>
                <description>{REPO_DESCRIPTION}</description>
                <disclaimer></disclaimer>
                <platform>all</platform>
                <assets>
                    <icon>icon.png</icon>
                    <fanart>fanart.jpg</fanart>
                </assets>
            </extension>
        </addon>
        """
    )
    write_text(addon_xml_path, addon_xml)

    icon_path = repo_dir / "icon.png"
    fanart_path = repo_dir / "fanart.jpg"
    if not icon_path.exists():
        shutil.copy2(
            root_dir / "plugin.video.fenlight" / "resources" / "media" / "fenlight_icon.png",
            icon_path,
        )
    if not fanart_path.exists():
        shutil.copy2(
            root_dir / "plugin.video.fenlight" / "resources" / "media" / "fenlight_fanart2.jpg",
            fanart_path,
        )
    return repo_dir, repo_version


def import_root_addon_zips(root_dir: Path) -> list[str]:
    imported_ids: list[str] = []
    for zip_path in sorted(root_dir.glob("*.zip")):
        if zip_path.name.startswith(f"{REPO_ADDON_ID}-"):
            continue
        with zipfile.ZipFile(zip_path) as zf:
            addon_xml_members = [name for name in zf.namelist() if name.endswith("addon.xml")]
            if len(addon_xml_members) != 1:
                raise SystemExit(f"Expected one addon.xml in {zip_path.name}, found {len(addon_xml_members)}")
            addon_xml_member = addon_xml_members[0]
            addon_root = ET.fromstring(zf.read(addon_xml_member))
            addon_id = addon_root.attrib["id"]
            member_parts = Path(addon_xml_member).parts
            top_level_dir = member_parts[0] if len(member_parts) > 1 else ""
            with tempfile.TemporaryDirectory() as temp_dir_name:
                temp_dir = Path(temp_dir_name)
                zf.extractall(temp_dir)
                extracted_dir = temp_dir / top_level_dir if top_level_dir else temp_dir
                target_dir = root_dir / addon_id
                remove_path(target_dir)
                shutil.copytree(extracted_dir, target_dir)
        zip_path.unlink()
        imported_ids.append(addon_id)
    return imported_ids


def get_source_dirs(root_dir: Path) -> list[Path]:
    source_dirs = []
    for path in sorted(root_dir.iterdir()):
        if not path.is_dir():
            continue
        if path.name.startswith(".") or path.name in EXCLUDED_SOURCE_DIRS:
            continue
        addon_xml = path / "addon.xml"
        if addon_xml.exists():
            source_dirs.append(path)
    source_dirs.sort(key=lambda path: (path.name == REPO_ADDON_ID, path.name))
    if not any(path.name == REPO_ADDON_ID for path in source_dirs):
        raise SystemExit(f"Missing addon source: {root_dir / REPO_ADDON_ID / 'addon.xml'}")
    return source_dirs


def reset_generated_outputs(root_dir: Path, repo_version: str) -> None:
    for path in root_dir.glob("repository.dutchtech-*.zip"):
        if path.name != f"{REPO_ADDON_ID}-{repo_version}.zip":
            remove_path(path)
    remove_path(root_dir / "addons.xml")
    remove_path(root_dir / "addons.xml.md5")
    remove_path(root_dir / "zips")


def update_index_html(root_dir: Path, repo_version: str) -> None:
    index_path = root_dir / "index.html"
    if not index_path.exists():
        return
    lines = [
        "<!DOCTYPE html>",
        f'<a href="{REPO_ADDON_ID}-{repo_version}.zip">{REPO_ADDON_ID}-{repo_version}.zip</a>',
    ]
    write_text(index_path, "\n".join(lines) + "\n")


def should_skip_file(addon_id: str, file_path: Path) -> bool:
    parts = file_path.parts
    if any(part.startswith(".") for part in parts):
        return True
    if "__pycache__" in parts:
        return True
    if file_path.suffix == ".pyc":
        return True
    if "__MACOSX" in parts:
        return True
    if addon_id == REPO_ADDON_ID and file_path.name not in REPO_ALLOWED_FILES:
        return True
    return False


def mirror_addon_source(addon_dir: Path, output_dir: Path) -> None:
    addon_id = addon_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_path in sorted(addon_dir.rglob("*")):
        if file_path.is_dir() or should_skip_file(addon_id, file_path):
            continue
        destination = output_dir / file_path.relative_to(addon_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, destination)


def package_addon(addon_dir: Path, output_dir: Path) -> Path:
    addon_id, version = get_addon_info(addon_dir / "addon.xml")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{addon_id}-{version}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(addon_dir.rglob("*")):
            if file_path.is_dir() or should_skip_file(addon_id, file_path):
                continue
            arcname = str(Path(addon_dir.name) / file_path.relative_to(addon_dir))
            zf.write(file_path, arcname)
    return archive_path


def build_addons_xml(addon_dirs: list[Path], output_path: Path) -> None:
    addons = ET.Element("addons")
    for addon_dir in addon_dirs:
        addons.append(ET.parse(addon_dir / "addon.xml").getroot())
    indent_xml(addons)
    xml_payload = ET.tostring(addons, encoding="utf-8")
    output_path.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + xml_payload
        + b"\n"
    )


def write_md5(file_path: Path) -> None:
    digest = hashlib.md5(file_path.read_bytes()).hexdigest()
    file_path.with_suffix(file_path.suffix + ".md5").write_text(digest, encoding="utf-8")


def git_output(root_dir: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def publish_prefixes(source_dirs: list[Path]) -> tuple[str, ...]:
    prefixes = list(STATIC_PUBLISH_PATHS)
    prefixes.extend(addon_dir.name for addon_dir in source_dirs)
    prefixes.extend(f"zips/{addon_dir.name}" for addon_dir in source_dirs)
    return tuple(prefixes)


def ensure_publish_ready(root_dir: Path, source_dirs: list[Path]) -> None:
    status = git_output(root_dir, "status", "--porcelain").splitlines()
    allowed_prefixes = publish_prefixes(source_dirs)
    allowed_patterns = (f"{REPO_ADDON_ID}-",)
    unexpected = []
    for line in status:
        path = line[3:]
        if " -> " in path:
            _old, path = path.split(" -> ", 1)
        if path.startswith(allowed_prefixes) or path.startswith(allowed_patterns):
            continue
        unexpected.append(line)
    if unexpected:
        raise SystemExit(
            "Refusing to publish with unrelated worktree changes:\n" + "\n".join(unexpected)
        )


def publish_changes(root_dir: Path, repo_version: str, source_dirs: list[Path]) -> None:
    ensure_publish_ready(root_dir, source_dirs)
    subprocess.run(
        ["git", "add", "--all", "."],
        cwd=root_dir,
        check=True,
    )
    if not git_output(root_dir, "diff", "--cached", "--name-only").strip():
        print("No publishable changes to commit")
        return
    subprocess.run(
        ["git", "commit", "-m", f"Publish Kodi repo {repo_version}"],
        cwd=root_dir,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=root_dir, check=True)


def main() -> None:
    args = parse_args()
    root_dir = args.root.resolve()
    base_url = normalize_base_url(args.base_url)
    repo_data_base_url = normalize_base_url(args.repo_data_base_url)

    imported_ids = import_root_addon_zips(root_dir)
    _repo_dir, repo_version = ensure_repo_addon_source(root_dir, repo_data_base_url)
    source_dirs = get_source_dirs(root_dir)

    reset_generated_outputs(root_dir, repo_version)
    (root_dir / "zips").mkdir(parents=True, exist_ok=True)

    package_paths: dict[str, Path] = {}
    for addon_dir in source_dirs:
        addon_id, _version = get_addon_info(addon_dir / "addon.xml")
        output_dir = root_dir / "zips" / addon_id
        mirror_addon_source(addon_dir, output_dir)
        package_paths[addon_id] = package_addon(addon_dir, output_dir)

    build_addons_xml(source_dirs, root_dir / "addons.xml")
    write_md5(root_dir / "addons.xml")
    update_index_html(root_dir, repo_version)

    repo_zip = package_paths[REPO_ADDON_ID]
    shutil.copy2(repo_zip, root_dir / repo_zip.name)

    print(f"Built Kodi repo metadata for {len(source_dirs)} addons")
    print(f"Repository version: {repo_version}")
    print(f"Site URL: {base_url}")
    print(f"Repo data URL: {repo_data_base_url}")
    if imported_ids:
        print(f"Imported root zips: {', '.join(imported_ids)}")
    publish_changes(root_dir, repo_version, source_dirs)


if __name__ == "__main__":
    main()
