#!/usr/bin/env python3
"""Build a static Kodi addon repository layout for GitHub Pages."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import textwrap
import xml.etree.ElementTree as ET
import zipfile


DEFAULT_BASE_URL = "https://TechXXX.github.io/kodirepo/"
DEFAULT_REPO_DATA_BASE_URL = "https://raw.githubusercontent.com/TechXXX/kodirepo/main/"
REPO_ADDON_ID = "repository.fenlight"
REPO_ADDON_NAME = "Fen Light Repository"
REPO_PROVIDER = "Fen Light"
REPO_SUMMARY = "Repository for Fen Light Kodi add-ons."
REPO_DESCRIPTION = (
    "Install this repository to receive Fen Light Kodi add-on updates "
    "from a GitHub Pages-hosted source."
)


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


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def get_addon_info(addon_xml: Path) -> tuple[str, str]:
    root = ET.parse(addon_xml).getroot()
    addon_id = root.attrib["id"]
    version = root.attrib["version"]
    return addon_id, version


def create_repo_addon_source(root_dir: Path, repo_data_base_url: str) -> Path:
    repo_dir = root_dir / REPO_ADDON_ID
    addon_xml = textwrap.dedent(
        f"""\
        <addon id="{REPO_ADDON_ID}" name="{REPO_ADDON_NAME}" provider-name="{REPO_PROVIDER}" version="1.0.0">
            <extension point="xbmc.addon.repository" name="{REPO_ADDON_NAME}">
                <dir>
                    <info compressed="false">{repo_data_base_url}addons.xml</info>
                    <checksum>{repo_data_base_url}addons.xml.md5</checksum>
                    <datadir zip="true">{repo_data_base_url}zips/</datadir>
                </dir>
            </extension>
            <extension point="xbmc.addon.metadata">
                <summary lang="en">{REPO_SUMMARY}</summary>
                <description lang="en">{REPO_DESCRIPTION}</description>
                <platform>all</platform>
            </extension>
        </addon>
        """
    )
    write_text(repo_dir / "addon.xml", addon_xml)
    return repo_dir


def find_addon_dirs(root_dir: Path) -> list[Path]:
    addon_dirs = []
    for path in root_dir.iterdir():
        if not path.is_dir():
            continue
        if path.name in {"zips", "scripts", ".git"}:
            continue
        if (path / "addon.xml").exists():
            addon_dirs.append(path)
    return sorted(addon_dirs, key=lambda item: item.name)


def package_addon(addon_dir: Path, output_dir: Path) -> Path:
    addon_id, version = get_addon_info(addon_dir / "addon.xml")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{addon_id}-{version}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(addon_dir.rglob("*")):
            if file_path.is_dir():
                continue
            arcname = str(Path(addon_dir.name) / file_path.relative_to(addon_dir))
            zf.write(file_path, arcname)
    return archive_path


def build_addons_xml(addon_dirs: list[Path], output_path: Path) -> None:
    addons = ET.Element("addons")
    for addon_dir in addon_dirs:
        root = ET.parse(addon_dir / "addon.xml").getroot()
        addons.append(root)
    indent_xml(addons)
    xml_payload = ET.tostring(addons, encoding="utf-8")
    output_path.write_bytes(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml_payload + b"\n")


def write_md5(file_path: Path) -> None:
    digest = hashlib.md5(file_path.read_bytes()).hexdigest()
    file_path.with_suffix(file_path.suffix + ".md5").write_text(digest, encoding="utf-8")


def main() -> None:
    args = parse_args()
    root_dir = args.root.resolve()
    base_url = normalize_base_url(args.base_url)
    repo_data_base_url = normalize_base_url(args.repo_data_base_url)

    plugin_addon_xml = root_dir / "plugin.video.fenlight" / "addon.xml"
    if not plugin_addon_xml.exists():
        raise SystemExit(f"Missing addon source: {plugin_addon_xml}")

    create_repo_addon_source(root_dir, repo_data_base_url)
    addon_dirs = find_addon_dirs(root_dir)

    for addon_dir in addon_dirs:
        addon_id, _version = get_addon_info(addon_dir / "addon.xml")
        package_dir = root_dir / "zips" / addon_id
        package_addon(addon_dir, package_dir)

    build_addons_xml(addon_dirs, root_dir / "addons.xml")
    write_md5(root_dir / "addons.xml")

    # Keep root copies for direct browser downloads on static hosts.
    plugin_id, plugin_version = get_addon_info(plugin_addon_xml)
    plugin_source_zip = root_dir / "zips" / plugin_id / f"{plugin_id}-{plugin_version}.zip"
    plugin_root_zip = root_dir / f"{plugin_id}-{plugin_version}.zip"
    if plugin_source_zip != plugin_root_zip:
        shutil.copy2(plugin_source_zip, plugin_root_zip)

    repo_source_zip = root_dir / "zips" / REPO_ADDON_ID / "repository.fenlight-1.0.0.zip"
    repo_root_zip = root_dir / "repository.fenlight-1.0.0.zip"
    if repo_source_zip != repo_root_zip:
        shutil.copy2(repo_source_zip, repo_root_zip)

    print(f"Built Kodi repo metadata for {len(addon_dirs)} addons")
    print(f"Site URL: {base_url}")
    print(f"Repo data URL: {repo_data_base_url}")


if __name__ == "__main__":
    main()
