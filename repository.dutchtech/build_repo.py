#!/usr/bin/env python3

import os
import hashlib
import zipfile
import xml.etree.ElementTree as ET

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# If script is inside repository.dutchtech, move root up one level
if os.path.basename(CURRENT_DIR) == "repository.dutchtech":
    ROOT_DIR = os.path.dirname(CURRENT_DIR)
else:
    ROOT_DIR = CURRENT_DIR
ZIPS_DIR = os.path.join(ROOT_DIR, "zips")

REPO_FOLDER = os.path.join(ROOT_DIR, "repository.dutchtech")
REPO_ZIP_PREFIX = "repository.dutchtech-"


def get_version_from_addon_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    return root.attrib.get("version")


# Bump last version component by 1
def bump_version(version):
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def zip_folder(folder_path, output_zip):
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ROOT_DIR)
                z.write(full_path, rel_path)


def build_repo_zip():
    addon_xml_path = os.path.join(REPO_FOLDER, "addon.xml")

    tree = ET.parse(addon_xml_path)
    root = tree.getroot()

    old_version = root.attrib.get("version")
    new_version = bump_version(old_version)

    print(f"Bumping version: {old_version} -> {new_version}")

    root.attrib["version"] = new_version
    tree.write(addon_xml_path, encoding="utf-8", xml_declaration=True)

    # clean old repo zips
    for f in os.listdir(ROOT_DIR):
        if f.startswith(REPO_ZIP_PREFIX) and f.endswith(".zip"):
            os.remove(os.path.join(ROOT_DIR, f))

    zip_name = f"{REPO_ZIP_PREFIX}{new_version}.zip"
    zip_path = os.path.join(ROOT_DIR, zip_name)

    print(f"Building repo zip: {zip_name}")

    zip_folder(REPO_FOLDER, zip_path)

    return zip_name


def generate_addons_xml():
    addons = ET.Element("addons")

    # scan zips directory
    for file in sorted(os.listdir(ZIPS_DIR)):
        if not file.endswith(".zip"):
            continue

        zip_path = os.path.join(ZIPS_DIR, file)

        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if name.endswith("addon.xml"):
                    data = z.read(name)
                    addon_element = ET.fromstring(data)
                    addons.append(addon_element)

    # add repository addon
    repo_addon_xml = os.path.join(REPO_FOLDER, "addon.xml")
    repo_tree = ET.parse(repo_addon_xml)
    addons.append(repo_tree.getroot())

    tree = ET.ElementTree(addons)

    output_path = os.path.join(ROOT_DIR, "addons.xml")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    print("addons.xml generated")


def generate_md5():
    path = os.path.join(ROOT_DIR, "addons.xml")

    with open(path, "rb") as f:
        data = f.read()

    md5 = hashlib.md5(data).hexdigest()

    with open(os.path.join(ROOT_DIR, "addons.xml.md5"), "w") as f:
        f.write(md5)

    print("addons.xml.md5 generated")


def main():
    print("=== Building Kodi Repo ===")

    build_repo_zip()
    generate_addons_xml()
    generate_md5()

    print("=== Done ===")


if __name__ == "__main__":
    main()