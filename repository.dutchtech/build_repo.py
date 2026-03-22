#!/usr/bin/env python3

import os
import hashlib
import zipfile
import xml.etree.ElementTree as ET
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# If script is inside repository.dutchtech, move root up one level
if os.path.basename(CURRENT_DIR) == "repository.dutchtech":
    ROOT_DIR = os.path.dirname(CURRENT_DIR)
else:
    ROOT_DIR = CURRENT_DIR

ZIPS_DIR = os.path.join(ROOT_DIR, "zips")
REPO_FOLDER = os.path.join(ROOT_DIR, "repository.dutchtech")
REPO_ZIP_PREFIX = "repository.dutchtech-"


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

    zip_name = f"{REPO_ZIP_PREFIX}{new_version}.zip"

    repo_zip_dir = os.path.join(ZIPS_DIR, "repository.dutchtech")
    if not os.path.exists(repo_zip_dir):
        os.makedirs(repo_zip_dir)

    zip_path = os.path.join(repo_zip_dir, zip_name)

    print(f"Building repo zip: {zip_name}")

    zip_folder(REPO_FOLDER, zip_path)

    # copy to root (only keep latest in root)
    for f in os.listdir(ROOT_DIR):
        if f.startswith(REPO_ZIP_PREFIX) and f.endswith(".zip"):
            os.remove(os.path.join(ROOT_DIR, f))

    root_copy_path = os.path.join(ROOT_DIR, zip_name)
    with open(zip_path, "rb") as src:
        with open(root_copy_path, "wb") as dst:
            dst.write(src.read())

    print("Copied latest repo zip to root (old ones removed)")

    return zip_name


def generate_addons_xml():
    addons = ET.Element("addons")

    if not os.path.exists(ZIPS_DIR):
        os.makedirs(ZIPS_DIR)

    for root_dir, _, files in os.walk(ZIPS_DIR):
        for file in sorted(files):
            if not file.endswith(".zip"):
                continue

            zip_path = os.path.join(root_dir, file)

            with zipfile.ZipFile(zip_path, "r") as z:
                for name in z.namelist():
                    if name.endswith("addon.xml"):
                        data = z.read(name)
                        try:
                            addon_element = ET.fromstring(data)
                            addons.append(addon_element)
                        except Exception as e:
                            print(f"Skipping broken addon in {file}: {e}")

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


def update_index_html(repo_zip_name):
    index_path = os.path.join(ROOT_DIR, "index.html")

    if not os.path.exists(index_path):
        print("index.html not found, skipping update")
        return

    with open(index_path, "r") as f:
        content = f.read()

    content_new = re.sub(r"repository\.dutchtech-\d+\.\d+\.\d+\.zip", repo_zip_name, content)

    with open(index_path, "w") as f:
        f.write(content_new)

    print("index.html version updated")


def main():
    print("=== Building Kodi Repo ===")

    repo_zip_name = build_repo_zip()
    generate_addons_xml()
    generate_md5()
    update_index_html(repo_zip_name)

    print("=== Done ===")


if __name__ == "__main__":
    main()