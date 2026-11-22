#!/usr/bin/env python3
"""Build and validate Kodi 22-only packages alongside the shared repository feed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from build_repo import should_skip_file


PIERS_MIN_KODI = "21.90.901"  # Includes Piers prereleases such as 22.0-RC2.
PIERS_DEPENDENCIES = {"xbmc.gui": "5.18.0", "xbmc.python": "3.1.2"}
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def release_spec(root_dir: Path) -> dict:
    spec = json.loads((root_dir / "piers" / "releases.json").read_text(encoding="utf-8"))
    if spec["min_kodi_version"] != PIERS_MIN_KODI or not spec["addons"]:
        raise ValueError("Piers releases must declare the Kodi 22 minimum and at least one addon")
    return spec


def piers_addon(root_dir: Path, addon_id: str, release: dict) -> ET.Element:
    source_xml = root_dir / addon_id / "addon.xml"
    addon = ET.parse(source_xml).getroot()
    if addon.get("id") != addon_id:
        raise ValueError(f"Source addon ID mismatch: {addon_id}")
    if version_tuple(release["version"]) <= version_tuple(addon.attrib["version"]):
        raise ValueError(f"Piers {addon_id} must be newer than the shared release")

    dependency_id = release["kodi_dependency"]
    minimum = release["minimum_dependency_version"]
    if dependency_id not in PIERS_DEPENDENCIES or version_tuple(minimum) < version_tuple(PIERS_DEPENDENCIES[dependency_id]):
        raise ValueError(f"Piers {addon_id} has no Kodi 22-only dependency")
    dependency = next(
        (item for item in addon.findall("./requires/import") if item.get("addon") == dependency_id),
        None,
    )
    if dependency is None:
        requires = addon.find("requires")
        if requires is None:
            requires = ET.Element("requires")
            addon.insert(0, requires)
        dependency = ET.SubElement(requires, "import", {"addon": dependency_id})
    dependency.set("version", minimum)
    dependency.attrib.pop("optional", None)
    addon.set("version", release["version"])
    return addon


def addon_xml_bytes(addon: ET.Element) -> bytes:
    ET.indent(addon, space="    ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(addon, encoding="utf-8") + b"\n"


def package_piers_addon(source_dir: Path, addon_xml: bytes, output_path: Path) -> None:
    addon_id = source_dir.name
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source_file in sorted(source_dir.rglob("*")):
            if not source_file.is_file() or should_skip_file(addon_id, source_file):
                continue
            name = f"{addon_id}/{source_file.relative_to(source_dir).as_posix()}"
            member = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            if source_file.name == "addon.xml" and source_file.parent == source_dir:
                archive.writestr(member, addon_xml)
            else:
                with source_file.open("rb") as source, archive.open(member, "w") as target:
                    shutil.copyfileobj(source, target)


def build_piers_release(root_dir: Path) -> None:
    spec = release_spec(root_dir)
    piers_zips = root_dir / "piers" / "zips"
    piers_zips.mkdir(parents=True, exist_ok=True)
    catalog = ET.Element("addons")
    for addon_id, release in sorted(spec["addons"].items()):
        source_dir = root_dir / addon_id
        addon = piers_addon(root_dir, addon_id, release)
        catalog.append(addon)
        output_dir = piers_zips / addon_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{addon_id}-{release['version']}.zip"
        with tempfile.TemporaryDirectory() as temp_name:
            candidate = Path(temp_name) / output_path.name
            package_piers_addon(source_dir, addon_xml_bytes(ET.fromstring(ET.tostring(addon))), candidate)
            if output_path.exists() and output_path.read_bytes() != candidate.read_bytes():
                raise ValueError(f"{output_path} changed without a Piers version bump")
            if not output_path.exists():
                shutil.move(candidate, output_path)
        for previous in output_dir.glob(f"{addon_id}-*.zip"):
            if previous != output_path:
                previous.unlink()
        for asset in ("icon.png", "fanart.jpg"):
            if (source_dir / asset).exists():
                shutil.copy2(source_dir / asset, output_dir / asset)

    ET.indent(catalog, space="    ")
    catalog_path = piers_zips / "addons.xml"
    catalog_path.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(catalog, encoding="utf-8") + b"\n")
    (piers_zips / "addons.xml.md5").write_text(hashlib.md5(catalog_path.read_bytes()).hexdigest(), encoding="utf-8")
    validate_piers_release(root_dir)


def validate_piers_release(root_dir: Path) -> None:
    spec = release_spec(root_dir)
    repo_addon = ET.parse(root_dir / "repository.dutchtech" / "addon.xml").getroot()
    piers_dirs = [directory for directory in repo_addon.findall("./extension[@point='xbmc.addon.repository']/dir")
                  if directory.get("minversion") == PIERS_MIN_KODI]
    if len(piers_dirs) != 1 or not all("piers/zips/" in (piers_dirs[0].findtext(tag) or "") for tag in ("info", "checksum", "datadir")):
        raise ValueError("Repository addon does not advertise the Kodi 22-only Piers feed")

    piers_zips = root_dir / "piers" / "zips"
    catalog_path = piers_zips / "addons.xml"
    checksum = (piers_zips / "addons.xml.md5").read_text(encoding="utf-8").strip()
    if hashlib.md5(catalog_path.read_bytes()).hexdigest() != checksum:
        raise ValueError("Piers catalog checksum mismatch")
    addons = ET.parse(catalog_path).getroot().findall("addon")
    if {addon.get("id") for addon in addons} != set(spec["addons"]):
        raise ValueError("Piers catalog does not match releases.json")
    shared_versions = {
        addon.attrib["id"]: addon.attrib["version"]
        for addon in ET.parse(root_dir / "addons.xml").getroot().findall("addon")
    }
    for addon in addons:
        addon_id = addon.attrib["id"]
        release = spec["addons"][addon_id]
        if addon_id in shared_versions and version_tuple(addon.attrib["version"]) <= version_tuple(shared_versions[addon_id]):
            raise ValueError(f"Piers {addon_id} must be newer than shared catalog version {shared_versions[addon_id]}")
        expected = piers_addon(root_dir, addon_id, release)
        if ET.canonicalize(ET.tostring(addon, encoding="unicode"), strip_text=True) != ET.canonicalize(ET.tostring(expected, encoding="unicode"), strip_text=True):
            raise ValueError(f"Piers catalog metadata mismatch: {addon_id}")
        zip_path = piers_zips / addon_id / f"{addon_id}-{release['version']}.zip"
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Corrupt Piers package: {zip_path}")
            packaged = ET.fromstring(archive.read(f"{addon_id}/addon.xml"))
        if ET.canonicalize(ET.tostring(packaged, encoding="unicode"), strip_text=True) != ET.canonicalize(ET.tostring(expected, encoding="unicode"), strip_text=True):
            raise ValueError(f"Piers package metadata mismatch: {addon_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    build_piers_release(args.root.resolve())
    print("Built and validated Kodi 22 Piers release")


if __name__ == "__main__":
    main()
