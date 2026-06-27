# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import posixpath
import re
import ssl
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import xbmc  # type: ignore
    import xbmcaddon  # type: ignore
    import xbmcgui  # type: ignore
    import xbmcvfs  # type: ignore
except ImportError:  # Allows local syntax/unit checks outside Kodi.
    xbmc = None
    xbmcaddon = None
    xbmcgui = None
    xbmcvfs = None


ADDON_ID = "script.kodiskin.widget.importer"
ADDON_NAME = "KodiSkin Widget Importer"
ADDON_ROOT = Path(__file__).resolve().parents[2]
SHORTCUTS_DATA = "special://profile/addon_data/script.skinshortcuts/"
SKINVARIABLES_NODES_DATA = "special://profile/addon_data/script.skinvariables/nodes/"
SKIN_ADDON_DATA = "special://profile/addon_data/{}/"
ADDON_DATA = "special://profile/addon_data/{}/".format(ADDON_ID)
ADDON_RESOURCE_PREFIX = "addon-resource://"
INCLUDE_NAME = "script-skinshortcuts-includes.xml"
SKIN_SETTINGS_NAME = "settings.xml"
SKINVARIABLES_GENERATOR_NAME = "skinvariables-generator.json"
SKINVARIABLES_SHORTCUT_PREFIX = "skinvariables-shortcut-"
SKINVARIABLES_SHORTCUT_SUFFIX = ".json"
PRELOADED_AH2_SETUP_LABEL = "Preloaded AH2 setup"
PRELOADED_AF3_DUTCH_SETUP_LABEL = "Preloaded AF3 DutchTech setup"
PRELOADED_AF3_ENGLISH_SETUP_LABEL = "Preloaded AF3 English widgets"
PRELOADED_AH2_WIDGET_LABEL = "Preloaded AH2 widgets"
PRELOADED_AF3_WIDGET_LABEL = "MacBook AF3 DutchTech widgets"
PRELOADED_AF3_ENGLISH_WIDGET_LABEL = "English AF3 widgets"
PRELOADED_AH2_SETTINGS_LABEL = "MacBook Arctic Horizon 2 settings"
PRELOADED_AF3_SETTINGS_LABEL = "MacBook Arctic Fuse 3 settings"
SKINVARIABLES_SKIP_FILES = {
    "skinvariables-shortcut-config.json",
    "skinvariables-shortcut-context.json",
}
PRELOADED_WIDGET_SOURCES = [
    (
        PRELOADED_AH2_WIDGET_LABEL,
        "https://e.pcloud.link/publink/show?code=8Vdy6alK",
    ),
    (
        PRELOADED_AF3_WIDGET_LABEL,
        "{}resources/preloaded/widgets/skin.dutchtech.fuse.3".format(ADDON_RESOURCE_PREFIX),
    ),
    (
        PRELOADED_AF3_ENGLISH_WIDGET_LABEL,
        "{}resources/preloaded/widgets/skin.arctic.fuse.3".format(ADDON_RESOURCE_PREFIX),
    ),
]
PRELOADED_SKIN_SETTINGS = [
    (
        "MacBook Arctic Horizon 2 settings",
        "skin.arctic.horizon.2.patched",
        "ah2",
        "resources/preloaded/skin-settings/skin.arctic.horizon.2.patched/settings.xml",
    ),
    (
        "MacBook Arctic Fuse 3 settings",
        "skin.arctic.fuse.3",
        "af3",
        "resources/preloaded/skin-settings/skin.arctic.fuse.3/settings.xml",
    ),
]
USER_AGENT = "{}/0.1.19 Kodi".format(ADDON_ID)
IMPORT_MODE_OVERWRITE = "overwrite"
IMPORT_MODE_APPEND = "append"
PCLOUD_API_DEFAULT = "https://api.pcloud.com"
PCLOUD_API_EU = "https://eapi.pcloud.com"
PLUGIN_VIDEO_RE = re.compile(r"plugin://(plugin\.video\.[A-Za-z0-9_.-]+)")
HELPER_VIDEO_ADDON_IDS = {
    "plugin.video.themoviedb.helper",
    "plugin.video.themoviedb.helper.patched",
    "plugin.video.themoviedb.helper.patched.kodienglish",
}
KNOWN_VIDEO_TARGETS = [
    ("plugin.video.fenlight.patched", "Fen Light Patched"),
    ("plugin.video.fenlight.aisearch", "Fen Light AI Search"),
    ("plugin.video.fenlight", "Fen Light"),
    ("plugin.video.fenlight.kodienglish", "Fen Light English"),
    ("plugin.video.fenlight.patched.kodienglish", "Fen Light Patched English"),
    ("plugin.video.fen", "Fen"),
]


class ImportCancelled(Exception):
    pass


class ImportErrorWithMessage(Exception):
    pass


@dataclass(frozen=True)
class ImportFile:
    source_path: Path
    source_skin: str
    target_name: str
    kind: str


@dataclass(frozen=True)
class ShortcutPackage:
    source_skin: str
    files: List[ImportFile]
    include_path: Optional[Path]
    skipped_hashes: List[Path]


@dataclass(frozen=True)
class SkinVariablesFile:
    source_path: Path
    source_skin: str
    target_name: str
    menu_name: str


@dataclass(frozen=True)
class SkinVariablesPackage:
    source_skin: str
    files: List[SkinVariablesFile]


@dataclass(frozen=True)
class VideoAddonRewrite:
    source_ids: Tuple[str, ...]
    target_id: str


@dataclass(frozen=True)
class SkinSettingsPreset:
    label: str
    source_skin: str
    family: str
    relative_path: str


class KodiUI:
    def __init__(self) -> None:
        self.dialog = xbmcgui.Dialog() if xbmcgui else None

    def log(self, message: str, level: Optional[int] = None) -> None:
        line = "[{}] {}".format(ADDON_ID, message)
        if xbmc:
            xbmc.log(line, level if level is not None else xbmc.LOGINFO)
        else:
            print(line)

    def ok(self, heading: str, *lines: str) -> None:
        message = "\n".join([line for line in lines if line])
        if self.dialog:
            try:
                self.dialog.ok(heading, message)
            except TypeError:
                self.dialog.ok(heading, *lines[:3])
        else:
            print("{}\n{}".format(heading, message))

    def error(self, *lines: str) -> None:
        self.ok(ADDON_NAME, *lines)

    def yesno(self, heading: str, *lines: str) -> bool:
        message = "\n".join([line for line in lines if line])
        if self.dialog:
            try:
                return bool(self.dialog.yesno(heading, message))
            except TypeError:
                return bool(self.dialog.yesno(heading, *lines[:3]))
        print("{}\n{}".format(heading, message))
        return True

    def select(self, heading: str, options: Sequence[str]) -> int:
        if self.dialog:
            return int(self.dialog.select(heading, list(options)))
        return 0

    def input(self, heading: str, default: str = "") -> str:
        if self.dialog:
            input_type = getattr(xbmcgui, "INPUT_ALPHANUM", 0)
            return self.dialog.input(heading, defaultt=default, type=input_type)
        return default

    def browse_zip(self) -> str:
        if not self.dialog:
            return ""
        try:
            return self.dialog.browseSingle(
                1,
                "Choose widget backup ZIP",
                "files",
                ".zip",
                False,
                False,
                "",
            )
        except TypeError:
            return self.dialog.browse(1, "Choose widget backup ZIP", "files", ".zip")

    def progress(self, heading: str, message: str):
        if not xbmcgui:
            return None
        progress = xbmcgui.DialogProgress()
        progress.create(heading, message)
        return progress


def main() -> None:
    ui = KodiUI()
    work_dir: Optional[Path] = None
    try:
        action = choose_action(ui)
        ui.log("Selected action: {}".format(action))
        if action == "skin_settings":
            import_preloaded_skin_settings(ui)
            return
        complete_af3_setup = action == "preloaded_af3_dutchtech_setup"
        preloaded_af3_english = action == "preloaded_af3_english_widgets"
        complete_ah2_setup = action == "preloaded_ah2_setup"
        if complete_af3_setup:
            source = preloaded_widget_source(PRELOADED_AF3_WIDGET_LABEL)
            ui.log("Using preloaded AF3 DutchTech setup source")
        elif preloaded_af3_english:
            source = preloaded_widget_source(PRELOADED_AF3_ENGLISH_WIDGET_LABEL)
            ui.log("Using preloaded AF3 English widget source")
        elif complete_ah2_setup:
            source = preloaded_widget_source(PRELOADED_AH2_WIDGET_LABEL)
            ui.log("Using preloaded AH2 setup source")
        else:
            source = choose_source(ui)

        if not source:
            return

        target_skin = get_current_skin()
        if not target_skin:
            raise ImportErrorWithMessage("Could not detect the active Kodi skin.")

        work_dir = make_work_dir()
        package_root = prepare_source(source, work_dir, ui)
        skinvariables_package = discover_skinvariables_package(package_root, target_skin, ui)
        if skinvariables_package.files and skin_supports_skinvariables(target_skin):
            video_rewrite = choose_video_addon_rewrite(skinvariables_package, ui)
            import_mode = (
                IMPORT_MODE_OVERWRITE
                if complete_af3_setup or preloaded_af3_english
                else choose_import_mode(ui)
            )

            if not confirm_skinvariables_import(
                skinvariables_package,
                target_skin,
                video_rewrite,
                import_mode,
                complete_af3_setup,
                ui,
            ):
                return

            backup_dir = import_skinvariables_shortcuts(
                skinvariables_package.files, target_skin, video_rewrite, import_mode, ui
            )
            settings_backup_dir = ""
            if complete_af3_setup:
                preset = skin_settings_preset_by_label(PRELOADED_AF3_SETTINGS_LABEL)
                settings_payload = read_skin_settings_payload(skin_settings_preset_path(preset))
                if video_rewrite:
                    settings_payload = rewrite_video_addons_in_bytes(settings_payload, video_rewrite)
                settings_backup_dir = import_skin_settings_payload(settings_payload, target_skin, ui)
            save_last_source(source)
            rebuild_skinvariables_shortcuts(ui)

            rewrite_note = ""
            if video_rewrite:
                rewrite_note = "Retargeted Fen-style paths to {}. ".format(video_rewrite.target_id)
            settings_note = ""
            if settings_backup_dir:
                settings_note = "Settings backup: {}".format(settings_backup_dir)
            if preloaded_af3_english:
                imported_note = "Imported {} English Arctic Fuse 3 shortcut node file(s).".format(
                    len(skinvariables_package.files)
                )
            elif complete_af3_setup:
                imported_note = "Imported {} DutchTech Arctic Fuse 3 shortcut node file(s).".format(
                    len(skinvariables_package.files)
                )
            else:
                imported_note = "Imported {} Arctic Fuse 3 shortcut node file(s).".format(
                    len(skinvariables_package.files)
                )
            if complete_af3_setup:
                imported_note = "{} Imported MacBook AF3 skin settings.".format(imported_note)

            ui.ok(
                ADDON_NAME,
                imported_note,
                "Node backup: {}".format(backup_dir),
                settings_note,
                "{}Skin Variables rebuild was triggered.".format(rewrite_note),
            )
            return

        package = discover_package(package_root, target_skin, ui)
        if not package.files:
            if skinvariables_package.files:
                raise ImportErrorWithMessage(
                    "That looks like an Arctic Fuse 3 / Skin Variables widget backup, "
                    "but the active skin does not look like an AF3 Skin Variables skin."
                )
            raise ImportErrorWithMessage(
                "No Skin Shortcuts DATA/properties or Arctic Fuse 3 shortcut JSON files were found in that ZIP."
            )
        if skin_supports_skinvariables(target_skin):
            raise ImportErrorWithMessage(
                "The active skin uses Arctic Fuse 3 / Skin Variables widgets, but that ZIP only "
                "contains Skin Shortcuts XML. Import an AF3 Skin Variables widget backup instead."
            )

        video_rewrite = choose_video_addon_rewrite(package, ui)
        import_mode = IMPORT_MODE_OVERWRITE if complete_ah2_setup else choose_import_mode(ui)

        if not confirm_import(
            package, target_skin, video_rewrite, import_mode, complete_ah2_setup, ui
        ):
            return

        backup_dir = import_shortcuts(package.files, target_skin, video_rewrite, import_mode, ui)
        settings_backup_dir = ""
        if complete_ah2_setup:
            preset = skin_settings_preset_by_label(PRELOADED_AH2_SETTINGS_LABEL)
            settings_payload = read_skin_settings_payload(skin_settings_preset_path(preset))
            if video_rewrite:
                settings_payload = rewrite_video_addons_in_bytes(settings_payload, video_rewrite)
            settings_backup_dir = import_skin_settings_payload(settings_payload, target_skin, ui)
        save_last_source(source)

        include_note = ""
        if package.include_path and import_mode == IMPORT_MODE_APPEND:
            include_note = "Generated include skipped in add-on mode; Skin Shortcuts will rebuild it."
        elif package.include_path and ui.yesno(
            ADDON_NAME,
            "The ZIP also contains a generated include.",
            "Copy it to the active skin too?",
            "Choose No if you want Skin Shortcuts to rebuild it.",
        ):
            include_backup = import_generated_include(package.include_path, video_rewrite, ui)
            include_note = "Generated include backup: {}".format(include_backup)

        rewrite_note = ""
        if video_rewrite:
            rewrite_note = "Retargeted widgets to {}.".format(video_rewrite.target_id)
        final_note = "Reload the skin or restart Kodi so widgets rebuild."
        if rewrite_note and include_note:
            final_note = "{} {}".format(rewrite_note, include_note)
        elif rewrite_note or include_note:
            final_note = rewrite_note or include_note
        settings_note = ""
        if settings_backup_dir:
            settings_note = "Settings backup: {}".format(settings_backup_dir)
            if final_note:
                final_note = "{} {}".format(final_note, settings_note)
            else:
                final_note = settings_note
        imported_note = "Imported {} Skin Shortcuts files.".format(len(package.files))
        if complete_ah2_setup:
            imported_note = "{} Imported MacBook AH2 skin settings.".format(imported_note)

        ui.ok(
            ADDON_NAME,
            imported_note,
            "Backup: {}".format(backup_dir),
            final_note,
        )
    except ImportCancelled:
        ui.log("Import cancelled")
    except Exception as exc:
        ui.log("Import failed: {}".format(exc), getattr(xbmc, "LOGERROR", None) if xbmc else None)
        ui.error("Import failed.", str(exc))
    finally:
        if work_dir is not None:
            shutil.rmtree(str(work_dir), ignore_errors=True)


def choose_action(ui: KodiUI) -> str:
    options = [
        PRELOADED_AF3_DUTCH_SETUP_LABEL,
        PRELOADED_AF3_ENGLISH_SETUP_LABEL,
        "Import widgets from source",
        PRELOADED_AH2_SETUP_LABEL,
    ]
    choice = ui.select(ADDON_NAME, options)
    if choice < 0:
        raise ImportCancelled()
    if choice == 0:
        return "preloaded_af3_dutchtech_setup"
    if choice == 1:
        return "preloaded_af3_english_widgets"
    if choice == 3:
        return "preloaded_ah2_setup"
    return "widgets"


def choose_source(ui: KodiUI) -> str:
    last_source = load_last_source()
    options: List[str] = ["Preloaded widgets"]
    if last_source:
        options.append("Use last widget source")
    options.extend(["Paste URL or path", "Browse for ZIP"])

    choice = ui.select(ADDON_NAME, options)
    if choice < 0:
        raise ImportCancelled()

    label = options[choice]
    if label == "Use last widget source":
        return last_source
    if label == "Preloaded widgets":
        return choose_preloaded_source(ui)
    if label == "Browse for ZIP":
        return strip_quotes(ui.browse_zip())
    return strip_quotes(ui.input("Paste widget ZIP, pCloud link, or path", last_source))


def choose_preloaded_source(ui: KodiUI) -> str:
    if len(PRELOADED_WIDGET_SOURCES) == 1:
        return PRELOADED_WIDGET_SOURCES[0][1]

    labels = [label for label, _source in PRELOADED_WIDGET_SOURCES]
    choice = ui.select("Preloaded widgets", labels)
    if choice < 0:
        raise ImportCancelled()
    return PRELOADED_WIDGET_SOURCES[choice][1]


def preloaded_widget_source(label: str) -> str:
    for source_label, source in PRELOADED_WIDGET_SOURCES:
        if source_label == label:
            return source
    raise ImportErrorWithMessage("Preloaded widget source is missing: {}".format(label))


def skin_settings_preset_by_label(label: str) -> SkinSettingsPreset:
    for item in PRELOADED_SKIN_SETTINGS:
        preset = SkinSettingsPreset(*item)
        if preset.label == label:
            return preset
    raise ImportErrorWithMessage("Preloaded skin settings preset is missing: {}".format(label))


def import_preloaded_skin_settings(ui: KodiUI) -> None:
    target_skin = get_current_skin()
    if not target_skin:
        raise ImportErrorWithMessage("Could not detect the active Kodi skin.")

    preset = choose_skin_settings_preset(target_skin, ui)
    source_path = skin_settings_preset_path(preset)
    payload = read_skin_settings_payload(source_path)

    if not confirm_skin_settings_import(preset, target_skin, ui):
        return

    backup_dir = import_skin_settings_payload(payload, target_skin, ui)
    ui.ok(
        ADDON_NAME,
        "Imported skin settings.",
        "Preset: {}".format(preset.label),
        "Backup: {}".format(backup_dir),
        "Reload the skin or restart Kodi so settings are applied.",
    )


def choose_skin_settings_preset(target_skin: str, ui: KodiUI) -> SkinSettingsPreset:
    presets = [SkinSettingsPreset(*item) for item in PRELOADED_SKIN_SETTINGS]
    target_family = skin_settings_family(target_skin)
    labels = []
    for preset in presets:
        label = preset.label
        if target_family and preset.family == target_family:
            label = "{} [matches active skin]".format(label)
        labels.append(label)

    choice = ui.select("Preloaded skin settings", labels)
    if choice < 0:
        raise ImportCancelled()
    return presets[choice]


def confirm_skin_settings_import(
    preset: SkinSettingsPreset, target_skin: str, ui: KodiUI
) -> bool:
    compatibility_note = "Preset matches the active skin family."
    target_family = skin_settings_family(target_skin)
    if not target_family:
        compatibility_note = "Warning: the active skin is not recognised as AH2 or AF3."
    elif target_family != preset.family:
        compatibility_note = "Warning: preset family does not match the active skin."

    return ui.yesno(
        ADDON_NAME,
        "Preset skin: {}".format(preset.source_skin),
        "Target skin: {}".format(target_skin),
        "{} Replace the target skin settings.xml after making a backup?".format(
            compatibility_note
        ),
    )


def skin_settings_preset_path(preset: SkinSettingsPreset) -> Path:
    path = ADDON_ROOT / preset.relative_path
    if not path.exists():
        raise ImportErrorWithMessage("Bundled skin settings preset is missing: {}".format(path))
    return path


def read_skin_settings_payload(source_path: Path) -> bytes:
    payload = source_path.read_bytes()
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ImportErrorWithMessage("Bundled skin settings XML is invalid: {}".format(exc))
    if root.tag != "settings":
        raise ImportErrorWithMessage("Bundled skin settings XML must have a settings root.")
    return payload


def import_skin_settings_payload(payload: bytes, target_skin: str, ui: KodiUI) -> str:
    target_dir = vfs_join(SKIN_ADDON_DATA.format(target_skin))
    target = vfs_join(target_dir, SKIN_SETTINGS_NAME)
    ensure_vfs_dir(target_dir)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = vfs_join(ADDON_DATA, "backups", stamp, "skin-settings", target_skin)
    ensure_vfs_dir(backup_dir)

    if vfs_exists(target):
        copy_vfs(target, vfs_join(backup_dir, SKIN_SETTINGS_NAME))
    write_bytes_vfs(target, payload)
    apply_active_skin_settings(payload, target_skin, ui)
    ui.log("Imported skin settings for {}".format(target_skin))
    return backup_dir


def apply_active_skin_settings(payload: bytes, target_skin: str, ui: KodiUI) -> None:
    if not xbmc or target_skin != get_current_skin():
        return

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ImportErrorWithMessage("Could not apply skin settings XML: {}".format(exc))

    applied = 0
    for setting in root.findall("setting"):
        setting_id = setting.attrib.get("id")
        if not setting_id:
            continue
        setting_type = setting.attrib.get("type", "string")
        value = setting.text or ""
        if setting_type == "bool":
            if value.lower() == "true":
                xbmc.executebuiltin("Skin.SetBool({})".format(setting_id))
            else:
                xbmc.executebuiltin("Skin.Reset({})".format(setting_id))
        else:
            if value:
                xbmc.executebuiltin(
                    "Skin.SetString({},{})".format(setting_id, escape_builtin_arg(value))
                )
            else:
                xbmc.executebuiltin("Skin.Reset({})".format(setting_id))
        applied += 1

    ui.log("Applied {} skin setting(s) to the active skin".format(applied))


def skin_settings_family(skin_id: str) -> str:
    if is_arctic_fuse_3_skin(skin_id):
        return "af3"
    if re.search(r"\.horizon\.2(?:\.|$)", skin_id or ""):
        return "ah2"
    return ""


def confirm_import(
    package: ShortcutPackage,
    target_skin: str,
    video_rewrite: Optional[VideoAddonRewrite],
    import_mode: str,
    include_skin_settings: bool,
    ui: KodiUI,
) -> bool:
    data_count = len([item for item in package.files if item.kind == "data"])
    prop_count = len([item for item in package.files if item.kind == "properties"])
    rewrite_note = "Video add-ons: unchanged"
    if video_rewrite:
        rewrite_note = "Video add-ons: {} -> {}".format(
            ", ".join(video_rewrite.source_ids), video_rewrite.target_id
        )
    mode_note = "Mode: overwrite matching local files"
    if import_mode == IMPORT_MODE_APPEND:
        mode_note = "Mode: add onto existing local files"
    settings_note = ""
    if include_skin_settings:
        settings_note = " MacBook AH2 skin settings.xml will also replace the active skin settings."
    return ui.yesno(
        ADDON_NAME,
        "Source skin: {}".format(package.source_skin),
        "Target skin: {}".format(target_skin),
        "{}. {}. Import {} DATA and {} properties file(s)?{}".format(
            mode_note, rewrite_note, data_count, prop_count, settings_note
        ),
    )


def confirm_skinvariables_import(
    package: SkinVariablesPackage,
    target_skin: str,
    video_rewrite: Optional[VideoAddonRewrite],
    import_mode: str,
    include_skin_settings: bool,
    ui: KodiUI,
) -> bool:
    rewrite_note = "Video add-ons: unchanged"
    if video_rewrite:
        rewrite_note = "Video add-ons: {} -> {}".format(
            ", ".join(video_rewrite.source_ids), video_rewrite.target_id
        )
    mode_note = "Mode: overwrite matching local files"
    if import_mode == IMPORT_MODE_APPEND:
        mode_note = "Mode: add onto existing local files"
    menu_note = ", ".join(item.menu_name for item in package.files)
    settings_note = ""
    if include_skin_settings:
        settings_note = " MacBook AF3 skin settings.xml will also replace the active skin settings."
    return ui.yesno(
        ADDON_NAME,
        "Source skin: {}".format(package.source_skin),
        "Target AF3 skin: {}".format(target_skin),
        "{}. {}. Import {} shortcut node file(s): {}.{}".format(
            mode_note, rewrite_note, len(package.files), menu_note, settings_note
        ),
    )


def get_current_skin() -> str:
    if xbmc:
        return xbmc.getSkinDir()
    return "skin.arctic.horizon.2.patched"


def make_work_dir() -> Path:
    root = translate_path(vfs_join(ADDON_DATA, "work"))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = root / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_source(source: str, work_dir: Path, ui: KodiUI) -> Path:
    if not source:
        raise ImportCancelled()

    if is_addon_resource_source(source):
        return addon_resource_path(source)

    if is_pcloud_public_link(source):
        ui.log("Resolving pCloud public link")
        source = resolve_pcloud_download_url(source)

    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        zip_path = work_dir / "source.zip"
        download_url(source, zip_path, ui)
        return extract_or_fail(zip_path, work_dir / "extracted")

    if is_directory_source(source):
        return Path(translate_path(source))

    zip_path = work_dir / "source.zip"
    copy_source_to_local(source, zip_path)
    return extract_or_fail(zip_path, work_dir / "extracted")


def extract_or_fail(zip_path: Path, extract_dir: Path) -> Path:
    if not zipfile.is_zipfile(str(zip_path)):
        raise ImportErrorWithMessage(describe_non_zip(zip_path))
    safe_extract_zip(zip_path, extract_dir)
    return extract_dir


def discover_package(root: Path, target_skin: str, ui: KodiUI) -> ShortcutPackage:
    package = discover_package_once(root, target_skin, ui)
    if package.files:
        return package

    nested_zips = [path for path in root.rglob("*.zip") if path.is_file()]
    if len(nested_zips) == 1:
        nested_root = root.parent / "nested-zip"
        ui.log("No shortcuts found; extracting nested ZIP {}".format(nested_zips[0].name))
        safe_extract_zip(nested_zips[0], nested_root)
        return discover_package_once(nested_root, target_skin, ui)

    return package


def discover_skinvariables_package(
    root: Path, target_skin: str, ui: KodiUI
) -> SkinVariablesPackage:
    package = discover_skinvariables_package_once(root, target_skin, ui)
    if package.files:
        return package

    nested_zips = [path for path in root.rglob("*.zip") if path.is_file()]
    if len(nested_zips) == 1:
        nested_root = root.parent / "nested-skinvariables-zip"
        ui.log("No Skin Variables widgets found; extracting nested ZIP {}".format(nested_zips[0].name))
        safe_extract_zip(nested_zips[0], nested_root)
        return discover_skinvariables_package_once(nested_root, target_skin, ui)

    return package


def discover_skinvariables_package_once(
    root: Path, target_skin: str, ui: KodiUI
) -> SkinVariablesPackage:
    candidates: List[SkinVariablesFile] = []

    for path in sorted(root.rglob("{}*{}".format(SKINVARIABLES_SHORTCUT_PREFIX, SKINVARIABLES_SHORTCUT_SUFFIX))):
        if not path.is_file() or any(part == "__MACOSX" for part in path.parts):
            continue

        menu_name = parse_skinvariables_shortcut_filename(path.name)
        if not menu_name:
            continue
        if not is_skinvariables_shortcut_node_file(path):
            continue

        candidates.append(
            SkinVariablesFile(
                path,
                infer_skinvariables_source_skin(path, root),
                path.name,
                menu_name,
            )
        )

    if not candidates:
        return SkinVariablesPackage("", [])

    source_skin = choose_source_skin(candidates, ui)
    chosen = [item for item in candidates if item.source_skin == source_skin]
    deduped = dedupe_by_target_name(chosen, root)

    return SkinVariablesPackage(source_skin, deduped)


def discover_package_once(root: Path, target_skin: str, ui: KodiUI) -> ShortcutPackage:
    candidates: List[ImportFile] = []
    include_paths: List[Path] = []
    skipped_hashes: List[Path] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part == "__MACOSX" for part in path.parts):
            continue

        name = path.name
        if name == INCLUDE_NAME:
            include_paths.append(path)
            continue

        if name.endswith(".hash"):
            source_skin = name[:-5]
            if source_skin:
                skipped_hashes.append(path)
            continue

        if name.endswith(".properties"):
            source_skin = name[: -len(".properties")]
            if looks_like_skin_id(source_skin):
                candidates.append(
                    ImportFile(path, source_skin, "{}.properties".format(target_skin), "properties")
                )
            continue

        data_name = parse_data_filename(name)
        if data_name:
            source_skin, menu_name = data_name
            candidates.append(
                ImportFile(
                    path,
                    source_skin,
                    "{}-{}.DATA.xml".format(target_skin, menu_name),
                    "data",
                )
            )

    if not candidates:
        return ShortcutPackage("", [], first_path(include_paths), skipped_hashes)

    source_skin = choose_source_skin(candidates, ui)
    chosen = [item for item in candidates if item.source_skin == source_skin]
    deduped = dedupe_by_target_name(chosen, root)

    return ShortcutPackage(source_skin, deduped, first_path(include_paths), skipped_hashes)


def choose_source_skin(candidates: Sequence[ImportFile], ui: KodiUI) -> str:
    skins = sorted(set(item.source_skin for item in candidates if item.source_skin))
    if not skins:
        raise ImportErrorWithMessage("Could not detect the source skin id in the backup.")
    if len(skins) == 1:
        return skins[0]

    labels = [
        "{} ({} files)".format(skin, len([item for item in candidates if item.source_skin == skin]))
        for skin in skins
    ]
    choice = ui.select("Choose source skin", labels)
    if choice < 0:
        raise ImportCancelled()
    return skins[choice]


def dedupe_by_target_name(candidates: Sequence[ImportFile], root: Path) -> List[ImportFile]:
    by_name: Dict[str, ImportFile] = {}
    for item in candidates:
        current = by_name.get(item.target_name)
        if current is None or candidate_score(item.source_path, root) > candidate_score(
            current.source_path, root
        ):
            by_name[item.target_name] = item
    return [by_name[name] for name in sorted(by_name)]


def candidate_score(path: Path, root: Path) -> Tuple[int, int]:
    rel = relative_parts(path, root)
    normalized = "/".join(part.lower() for part in rel)
    in_addon_data = "addon_data/script.skinshortcuts" in normalized
    shallow = -len(rel)
    return (2 if in_addon_data else 1, shallow)


def choose_video_addon_rewrite(
    package: object, ui: KodiUI
) -> Optional[VideoAddonRewrite]:
    scanned = scan_video_addons(package)
    source_ids = tuple(
        addon_id
        for addon_id, _count in sorted(scanned.items(), key=lambda item: (-item[1], item[0]))
        if is_switchable_video_addon(addon_id)
    )
    if not source_ids:
        return None

    scan_label = ", ".join(
        "{} ({})".format(video_addon_name(addon_id), scanned[addon_id])
        for addon_id in source_ids
    )
    target_ids = build_video_target_choices(source_ids)
    labels = ["Keep original add-ons"]
    labels.extend(video_target_label(addon_id) for addon_id in target_ids)
    labels.append("Custom Fen/Fen Light add-on id")

    choice = ui.select("Widget video add-on: {}".format(scan_label), labels)
    if choice < 0:
        raise ImportCancelled()
    if choice == 0:
        return None
    if choice == len(labels) - 1:
        target_id = strip_quotes(ui.input("Target Fen/Fen Light add-on id", source_ids[0]))
        if not target_id:
            raise ImportCancelled()
    else:
        target_id = target_ids[choice - 1]

    if not looks_like_fen_video_addon_id(target_id):
        raise ImportErrorWithMessage(
            "Invalid Fen/Fen Light add-on id: {}".format(target_id)
        )
    if len(source_ids) == 1 and source_ids[0] == target_id:
        return None
    return VideoAddonRewrite(source_ids, target_id)


def scan_video_addons(package: object) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    paths = [item.source_path for item in getattr(package, "files", [])]
    include_path = getattr(package, "include_path", None)
    if include_path:
        paths.append(include_path)

    for path in paths:
        try:
            text = path.read_text("utf-8", "replace")
        except Exception:
            continue
        for addon_id in PLUGIN_VIDEO_RE.findall(text):
            counts[addon_id] = counts.get(addon_id, 0) + 1
    return counts


def build_video_target_choices(source_ids: Sequence[str]) -> List[str]:
    target_ids: List[str] = []
    for addon_id, _name in KNOWN_VIDEO_TARGETS:
        append_unique(target_ids, addon_id)
    return target_ids


def addon_is_installed(addon_id: str) -> bool:
    if xbmcaddon:
        try:
            xbmcaddon.Addon(addon_id).getAddonInfo("id")
            return True
        except Exception:
            return False
    return False


def is_switchable_video_addon(addon_id: str) -> bool:
    if addon_id in HELPER_VIDEO_ADDON_IDS:
        return False
    if addon_id in {target_id for target_id, _name in KNOWN_VIDEO_TARGETS}:
        return True
    return looks_like_fen_video_addon_id(addon_id)


def looks_like_fen_video_addon_id(value: str) -> bool:
    return bool(re.match(r"^plugin\.video\.fen(?:light)?(?:[._-][A-Za-z0-9_.-]+)?$", value))


def video_target_label(addon_id: str) -> str:
    installed_note = "installed" if addon_is_installed(addon_id) else "known"
    return "{} [{}]".format(video_addon_name(addon_id), installed_note)


def video_addon_name(addon_id: str) -> str:
    for known_id, known_name in KNOWN_VIDEO_TARGETS:
        if addon_id == known_id:
            return "{} ({})".format(known_name, addon_id)
    return addon_id


def append_unique(values: List[str], value: str) -> None:
    if value not in values:
        values.append(value)


def choose_import_mode(ui: KodiUI) -> str:
    options = [
        "Overwrite matching local widget files",
        "Add onto existing local widget files",
    ]
    choice = ui.select("Import mode", options)
    if choice < 0:
        raise ImportCancelled()
    return IMPORT_MODE_APPEND if choice == 1 else IMPORT_MODE_OVERWRITE


def import_shortcuts(
    files: Sequence[ImportFile],
    target_skin: str,
    video_rewrite: Optional[VideoAddonRewrite],
    import_mode: str,
    ui: KodiUI,
) -> str:
    ensure_vfs_dir(SHORTCUTS_DATA)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = vfs_join(ADDON_DATA, "backups", stamp, "script.skinshortcuts")
    ensure_vfs_dir(backup_dir)

    target_hash_name = "{}.hash".format(target_skin)
    targets = [item.target_name for item in files] + [target_hash_name]
    for target_name in targets:
        dest = vfs_join(SHORTCUTS_DATA, target_name)
        if vfs_exists(dest):
            backup_dest = vfs_join(backup_dir, target_name)
            copy_vfs(dest, backup_dest)

    for item in files:
        dest = vfs_join(SHORTCUTS_DATA, item.target_name)
        if vfs_exists(dest) and import_mode == IMPORT_MODE_OVERWRITE:
            delete_vfs(dest)
        if import_mode == IMPORT_MODE_APPEND and vfs_exists(dest):
            merge_import_file(item, dest, video_rewrite, ui)
        else:
            copy_import_file(item.source_path, dest, video_rewrite)
            ui.log("Imported {}".format(item.target_name))

    hash_path = vfs_join(SHORTCUTS_DATA, target_hash_name)
    if vfs_exists(hash_path):
        delete_vfs(hash_path)
        ui.log("Removed {} to force Skin Shortcuts rebuild".format(target_hash_name))

    return backup_dir


def import_skinvariables_shortcuts(
    files: Sequence[SkinVariablesFile],
    target_skin: str,
    video_rewrite: Optional[VideoAddonRewrite],
    import_mode: str,
    ui: KodiUI,
) -> str:
    target_dir = vfs_join(SKINVARIABLES_NODES_DATA, target_skin)
    ensure_vfs_dir(target_dir)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = vfs_join(
        ADDON_DATA, "backups", stamp, "script.skinvariables", "nodes", target_skin
    )
    ensure_vfs_dir(backup_dir)

    for item in files:
        dest = vfs_join(target_dir, item.target_name)
        if vfs_exists(dest):
            copy_vfs(dest, vfs_join(backup_dir, item.target_name))

    for item in files:
        dest = vfs_join(target_dir, item.target_name)
        source_data = read_import_bytes(item.source_path, video_rewrite)
        if import_mode == IMPORT_MODE_APPEND and vfs_exists(dest):
            added = merge_skinvariables_data(dest, source_data)
            ui.log("Merged {} shortcut row(s) into {}".format(added, item.target_name))
        else:
            write_skinvariables_data(dest, source_data)
            ui.log("Imported {}".format(item.target_name))

    return backup_dir


def rebuild_skinvariables_shortcuts(ui: KodiUI) -> None:
    if not xbmc:
        ui.log("Skin Variables rebuild skipped outside Kodi")
        return
    xbmc.executebuiltin(
        "SetProperty(SkinVariables.ShortcutsNode.Reload,{},Home)".format(time.time())
    )
    xbmc.executebuiltin("RunScript(script.skinvariables,action=buildtemplate,force)")
    ui.log("Triggered Skin Variables shortcut rebuild")


def import_generated_include(
    include_path: Path, video_rewrite: Optional[VideoAddonRewrite], ui: KodiUI
) -> str:
    skin_include_dir = "special://skin/1080i/"
    target = vfs_join(skin_include_dir, INCLUDE_NAME)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = vfs_join(ADDON_DATA, "backups", stamp, "generated-include")
    ensure_vfs_dir(backup_dir)

    if vfs_exists(target):
        copy_vfs(target, vfs_join(backup_dir, INCLUDE_NAME))
        delete_vfs(target)
    copy_import_file(include_path, target, video_rewrite)
    ui.log("Copied generated include to active skin")
    return backup_dir


def copy_import_file(
    source_path: Path, dest: str, video_rewrite: Optional[VideoAddonRewrite]
) -> None:
    data = read_import_bytes(source_path, video_rewrite)
    write_bytes_vfs(dest, data)


def read_import_bytes(
    source_path: Path, video_rewrite: Optional[VideoAddonRewrite]
) -> bytes:
    data = source_path.read_bytes()
    if not video_rewrite:
        return data
    return rewrite_video_addons_in_bytes(data, video_rewrite)


def merge_import_file(
    item: ImportFile,
    dest: str,
    video_rewrite: Optional[VideoAddonRewrite],
    ui: KodiUI,
) -> None:
    source_data = read_import_bytes(item.source_path, video_rewrite)
    if item.kind == "data":
        added = merge_shortcuts_data(dest, source_data)
        ui.log("Merged {} shortcut(s) into {}".format(added, item.target_name))
        return
    if item.kind == "properties":
        added = merge_properties_data(dest, source_data)
        ui.log("Merged {} property row(s) into {}".format(added, item.target_name))
        return
    raise ImportErrorWithMessage("Cannot merge file type: {}".format(item.kind))


def merge_shortcuts_data(dest: str, source_data: bytes) -> int:
    try:
        target_root = ET.fromstring(read_bytes_vfs(dest))
        source_root = ET.fromstring(source_data)
    except ET.ParseError as exc:
        raise ImportErrorWithMessage("Could not merge shortcut XML: {}".format(exc))
    if target_root.tag != "shortcuts" or source_root.tag != "shortcuts":
        raise ImportErrorWithMessage("Expected Skin Shortcuts XML with a shortcuts root.")

    signatures = {
        shortcut_signature(shortcut) for shortcut in target_root.findall("shortcut")
    }
    added = 0
    for shortcut in list(source_root.findall("shortcut")):
        signature = shortcut_signature(shortcut)
        if signature in signatures:
            continue
        target_root.append(shortcut)
        signatures.add(signature)
        added += 1

    indent_element(target_root)
    write_bytes_vfs(dest, ET.tostring(target_root, encoding="utf-8") + b"\n")
    return added


def shortcut_signature(shortcut: ET.Element) -> Tuple[str, str, str, str]:
    return (
        child_text(shortcut, "defaultID"),
        child_text(shortcut, "label"),
        child_text(shortcut, "label2"),
        child_text(shortcut, "action"),
    )


def child_text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def merge_properties_data(dest: str, source_data: bytes) -> int:
    try:
        target_rows = json.loads(read_bytes_vfs(dest).decode("utf-8-sig", "replace"))
        source_rows = json.loads(source_data.decode("utf-8-sig", "replace"))
    except Exception as exc:
        raise ImportErrorWithMessage("Could not merge properties JSON: {}".format(exc))
    if not isinstance(target_rows, list) or not isinstance(source_rows, list):
        raise ImportErrorWithMessage("Expected Skin Shortcuts properties to be a list.")

    existing_keys = {property_row_key(row) for row in target_rows}
    added = 0
    for row in source_rows:
        key = property_row_key(row)
        if key in existing_keys:
            continue
        target_rows.append(row)
        existing_keys.add(key)
        added += 1

    payload = json.dumps(target_rows, ensure_ascii=False, indent=4).encode("utf-8")
    write_bytes_vfs(dest, payload + b"\n")
    return added


def property_row_key(row: object) -> Tuple[object, ...]:
    if isinstance(row, list) and len(row) >= 3:
        return tuple(row[:3])
    return (json.dumps(row, sort_keys=True, ensure_ascii=False),)


def write_skinvariables_data(dest: str, source_data: bytes) -> None:
    rows = load_skinvariables_rows(source_data)
    ensure_unique_skinvariables_guids(rows)
    write_json_vfs(dest, rows)


def merge_skinvariables_data(dest: str, source_data: bytes) -> int:
    target_rows = load_skinvariables_rows(read_bytes_vfs(dest))
    source_rows = load_skinvariables_rows(source_data)
    added = merge_skinvariables_rows(target_rows, source_rows)
    ensure_unique_skinvariables_guids(target_rows)
    write_json_vfs(dest, target_rows)
    return added


def load_skinvariables_rows(data: bytes) -> List[object]:
    try:
        rows = json.loads(data.decode("utf-8-sig", "replace"))
    except Exception as exc:
        raise ImportErrorWithMessage("Could not read Skin Variables shortcut JSON: {}".format(exc))
    if not isinstance(rows, list):
        raise ImportErrorWithMessage("Expected Skin Variables shortcut JSON to be a list.")
    return rows


def merge_skinvariables_rows(target_rows: List[object], source_rows: Sequence[object]) -> int:
    by_signature = {
        skinvariables_item_signature(row): row
        for row in target_rows
        if isinstance(row, dict)
    }
    added = 0
    for row in source_rows:
        if not isinstance(row, dict):
            key = skinvariables_item_signature(row)
            if key in by_signature:
                continue
            target_rows.append(row)
            added += 1
            continue

        key = skinvariables_item_signature(row)
        target_row = by_signature.get(key)
        if isinstance(target_row, dict):
            added += merge_skinvariables_child_rows(target_row, row)
            continue

        target_rows.append(row)
        by_signature[key] = row
        added += 1
    return added


def merge_skinvariables_child_rows(target_row: Dict[str, object], source_row: Dict[str, object]) -> int:
    added = 0
    for child_key in ("submenu", "widgets"):
        source_children = source_row.get(child_key)
        if not isinstance(source_children, list):
            continue
        target_children = target_row.get(child_key)
        if not isinstance(target_children, list):
            target_children = []
            target_row[child_key] = target_children
        added += merge_skinvariables_rows(target_children, source_children)
    return added


def skinvariables_item_signature(row: object) -> Tuple[object, ...]:
    if not isinstance(row, dict):
        return ("raw", json.dumps(row, sort_keys=True, ensure_ascii=False))
    return (
        row.get("label", ""),
        row.get("path", ""),
        row.get("target", ""),
        row.get("widget_style", ""),
    )


def ensure_unique_skinvariables_guids(rows: Sequence[object]) -> None:
    used = set()

    def make_guid() -> str:
        while True:
            guid = "guid-{}".format(os.urandom(4).hex())
            if guid not in used:
                return guid

    def walk(items: Sequence[object]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            guid = str(item.get("guid") or "")
            if not guid or guid in used:
                guid = make_guid()
                item["guid"] = guid
            used.add(guid)
            for child_key in ("submenu", "widgets"):
                children = item.get(child_key)
                if isinstance(children, list):
                    walk(children)

    walk(rows)


def write_json_vfs(dest: str, rows: object) -> None:
    payload = json.dumps(rows, ensure_ascii=False, indent=4).encode("utf-8")
    write_bytes_vfs(dest, payload + b"\n")


def indent_element(element: ET.Element, level: int = 0) -> None:
    indent = "\n" + "\t" * level
    child_indent = "\n" + "\t" * (level + 1)
    children = list(element)
    if children:
        if not element.text or not element.text.strip():
            element.text = child_indent
        for child in children:
            indent_element(child, level + 1)
        if not children[-1].tail or not children[-1].tail.strip():
            children[-1].tail = indent
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indent


def rewrite_video_addons_in_bytes(data: bytes, video_rewrite: VideoAddonRewrite) -> bytes:
    text = data.decode("utf-8-sig", "replace")
    rewritten = rewrite_video_addons_in_text(text, video_rewrite)
    return rewritten.encode("utf-8")


def rewrite_video_addons_in_text(text: str, video_rewrite: VideoAddonRewrite) -> str:
    source_ids = set(video_rewrite.source_ids)

    def replace(match: re.Match[str]) -> str:
        addon_id = match.group(1)
        if addon_id in source_ids:
            return "plugin://{}".format(video_rewrite.target_id)
        return match.group(0)

    return PLUGIN_VIDEO_RE.sub(replace, text)


def resolve_pcloud_download_url(public_link: str) -> str:
    code = extract_pcloud_code(public_link)
    if not code:
        raise ImportErrorWithMessage("That pCloud link does not contain a public code.")

    errors: List[str] = []
    for api_base in pcloud_api_bases(public_link):
        try:
            metadata_response = fetch_pcloud_json(api_base, "showpublink", {"code": code})
        except Exception as exc:
            errors.append("{}: {}".format(api_base, exc))
            continue

        if metadata_response.get("result") != 0:
            errors.append(pcloud_error(metadata_response))
            continue

        metadata = metadata_response.get("metadata") or {}
        name = str(metadata.get("name") or "")
        is_folder = bool(metadata.get("isfolder"))
        if is_folder:
            return build_pcloud_api_url(api_base, "getpubzip", {"code": code, "filename": "skinshortcuts.zip"})

        if name.lower().endswith(".zip"):
            download_response = fetch_pcloud_json(
                api_base, "getpublinkdownload", {"code": code, "forcedownload": "1"}
            )
            if download_response.get("result") == 0:
                hosts = download_response.get("hosts") or []
                path = download_response.get("path")
                if hosts and path:
                    return "https://{}{}".format(str(hosts[0]), str(path))
            errors.append(pcloud_error(download_response))

        return build_pcloud_api_url(api_base, "getpubzip", {"code": code, "filename": "skinshortcuts.zip"})

    raise ImportErrorWithMessage("Could not resolve pCloud link: {}".format("; ".join(errors)))


def fetch_pcloud_json(api_base: str, method: str, params: Dict[str, str]) -> Dict[str, object]:
    url = build_pcloud_api_url(api_base, method, params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with open_url(request, timeout=30) as response:
        payload = response.read().decode("utf-8", "replace")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ImportErrorWithMessage("Unexpected response from pCloud.")
    return data


def build_pcloud_api_url(api_base: str, method: str, params: Dict[str, str]) -> str:
    return "{}/{}?{}".format(api_base.rstrip("/"), method, urllib.parse.urlencode(params))


def pcloud_api_bases(public_link: str) -> List[str]:
    host = urllib.parse.urlparse(public_link).netloc.lower()
    if host.startswith("e.") or host.startswith("e1.") or host.startswith("e2."):
        return [PCLOUD_API_EU, PCLOUD_API_DEFAULT]
    return [PCLOUD_API_DEFAULT, PCLOUD_API_EU]


def pcloud_error(response: Dict[str, object]) -> str:
    error = response.get("error") or "unknown pCloud error"
    result = response.get("result")
    return "{} ({})".format(error, result) if result is not None else str(error)


def download_url(url: str, dest: Path, ui: KodiUI) -> None:
    progress = ui.progress(ADDON_NAME, "Downloading widget backup...")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_url(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(str(dest), "wb") as handle:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress:
                        if progress.iscanceled():
                            raise ImportCancelled()
                        percent = int(downloaded * 100 / total) if total else 0
                        progress.update(min(percent, 100), "Downloading widget backup...")
    finally:
        if progress:
            progress.close()


def safe_extract_zip(zip_path: Path, extract_dir: Path) -> None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    root = extract_dir.resolve()
    with zipfile.ZipFile(str(zip_path)) as archive:
        for member in archive.infolist():
            target = (extract_dir / member.filename).resolve()
            if not is_inside(target, root):
                raise ImportErrorWithMessage("Unsafe path in ZIP: {}".format(member.filename))
            archive.extract(member, str(extract_dir))


def parse_data_filename(name: str) -> Optional[Tuple[str, str]]:
    suffix = ".DATA.xml"
    if not name.endswith(suffix) or "-" not in name:
        return None
    base = name[: -len(suffix)]
    source_skin, menu_name = base.split("-", 1)
    if not looks_like_skin_id(source_skin) or not menu_name:
        return None
    return source_skin, menu_name


def parse_skinvariables_shortcut_filename(name: str) -> str:
    if name in SKINVARIABLES_SKIP_FILES:
        return ""
    if not name.startswith(SKINVARIABLES_SHORTCUT_PREFIX):
        return ""
    if not name.endswith(SKINVARIABLES_SHORTCUT_SUFFIX):
        return ""
    menu_name = name[len(SKINVARIABLES_SHORTCUT_PREFIX) : -len(SKINVARIABLES_SHORTCUT_SUFFIX)]
    if not re.match(r"^[A-Za-z0-9_.-]+$", menu_name):
        return ""
    return menu_name


def is_skinvariables_shortcut_node_file(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text("utf-8-sig"))
    except Exception:
        return False
    return isinstance(payload, list)


def infer_skinvariables_source_skin(path: Path, root: Path) -> str:
    rel_parts = relative_parts(path, root)
    lowered = [part.lower() for part in rel_parts]

    for index, part in enumerate(lowered[:-1]):
        if part == "nodes" and index + 1 < len(rel_parts) - 1:
            candidate = rel_parts[index + 1]
            if looks_like_skin_id(candidate):
                return candidate

    for part in reversed(rel_parts[:-1]):
        if looks_like_skin_id(part):
            return part

    addon_skin = find_nearest_skin_addon_id(path, root)
    if addon_skin:
        return addon_skin

    return "Skin Variables"


def find_nearest_skin_addon_id(path: Path, root: Path) -> str:
    current = path.parent
    while is_inside(current, root):
        addon_xml = current / "addon.xml"
        if addon_xml.exists():
            try:
                addon_id = ET.parse(str(addon_xml)).getroot().attrib.get("id", "")
            except Exception:
                addon_id = ""
            if looks_like_skin_id(addon_id):
                return addon_id
        if current == root:
            break
        current = current.parent
    return ""


def looks_like_skin_id(value: str) -> bool:
    return bool(re.match(r"^skin\.[A-Za-z0-9_.-]+$", value))


def skin_supports_skinvariables(target_skin: str) -> bool:
    if vfs_exists(vfs_join("special://skin/shortcuts", SKINVARIABLES_GENERATOR_NAME)):
        return True
    return is_arctic_fuse_3_skin(target_skin)


def is_arctic_fuse_3_skin(skin_id: str) -> bool:
    return bool(re.search(r"\.fuse\.3(?:\.|$)", skin_id or ""))


def is_pcloud_public_link(source: str) -> bool:
    parsed = urllib.parse.urlparse(source)
    host = parsed.netloc.lower()
    is_pcloud_host = (
        "pcloud.link" in host
        or "pcloud.com" in host
        or host == "pc.cd"
        or host.endswith(".pc.cd")
    )
    return is_pcloud_host and bool(extract_pcloud_code(source))


def extract_pcloud_code(public_link: str) -> str:
    parsed = urllib.parse.urlparse(public_link)
    query = urllib.parse.parse_qs(parsed.query)
    if query.get("code"):
        return query["code"][0]

    host = parsed.netloc.lower()
    if host == "pc.cd" or host.endswith(".pc.cd"):
        path_code = parsed.path.strip("/").split("/", 1)[0]
        if re.match(r"^[A-Za-z0-9_-]+$", path_code or ""):
            return path_code

    fragment = parsed.fragment
    if fragment:
        fragment_query = urllib.parse.parse_qs(fragment.lstrip("#"))
        if fragment_query.get("code"):
            return fragment_query["code"][0]

    match = re.search(r"(?:^|[?&#])code=([^&#]+)", public_link)
    return urllib.parse.unquote(match.group(1)) if match else ""


def open_url(request: urllib.request.Request, timeout: int):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as exc:
        if is_ssl_verification_error(exc):
            context = ssl._create_unverified_context()
            return urllib.request.urlopen(request, timeout=timeout, context=context)
        raise


def is_ssl_verification_error(exc: urllib.error.URLError) -> bool:
    reason = getattr(exc, "reason", None)
    return isinstance(reason, ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(reason)


def is_directory_source(source: str) -> bool:
    if xbmcvfs and source.startswith(("special://", "smb://", "nfs://")):
        try:
            return bool(xbmcvfs.isdir(source))
        except Exception:
            return False
    path = Path(translate_path(source))
    return path.is_dir()


def is_addon_resource_source(source: str) -> bool:
    return source.startswith(ADDON_RESOURCE_PREFIX)


def addon_resource_path(source: str) -> Path:
    relative = source[len(ADDON_RESOURCE_PREFIX) :].strip("/")
    path = ADDON_ROOT / relative
    if not path.exists():
        raise ImportErrorWithMessage("Bundled preloaded source is missing: {}".format(path))
    return path


def copy_source_to_local(source: str, dest: Path) -> None:
    if xbmcvfs and source.startswith(("special://", "smb://", "nfs://", "ftp://")):
        if not xbmcvfs.copy(source, str(dest)):
            raise ImportErrorWithMessage("Could not copy source ZIP from {}".format(source))
        return

    local = Path(translate_path(source))
    if not local.exists():
        raise ImportErrorWithMessage("Source path does not exist: {}".format(source))
    shutil.copy2(str(local), str(dest))


def describe_non_zip(path: Path) -> str:
    try:
        text = path.read_bytes()[:2048].decode("utf-8", "replace").strip()
        data = json.loads(text)
        if isinstance(data, dict) and data.get("error"):
            return "Downloaded pCloud response was not a ZIP: {}".format(pcloud_error(data))
        if text:
            return "Downloaded file is not a ZIP. First response text: {}".format(text[:300])
    except Exception:
        pass
    return "Downloaded file is not a ZIP archive."


def strip_quotes(value: str) -> str:
    value = (value or "").strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def escape_builtin_arg(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ")


def translate_path(path: str) -> Path:
    if xbmcvfs:
        translated = xbmcvfs.translatePath(path)
        if isinstance(translated, bytes):
            translated = translated.decode("utf-8")
        return Path(translated)
    if path.startswith("special://profile/"):
        return Path.cwd() / "_kodi_profile" / path[len("special://profile/") :]
    if path.startswith("special://skin/"):
        return Path.cwd() / "_kodi_skin" / path[len("special://skin/") :]
    return Path(path)


def vfs_join(base: str, *parts: str) -> str:
    base = base.rstrip("/")
    clean_parts = [str(part).strip("/") for part in parts if str(part).strip("/")]
    return "/".join([base] + clean_parts)


def ensure_vfs_dir(path: str) -> None:
    if xbmcvfs:
        xbmcvfs.mkdirs(path)
    else:
        translate_path(path).mkdir(parents=True, exist_ok=True)


def vfs_exists(path: str) -> bool:
    if xbmcvfs:
        return bool(xbmcvfs.exists(path))
    return translate_path(path).exists()


def copy_vfs(source: str, dest: str) -> None:
    parent = posixpath.dirname(dest)
    if parent:
        ensure_vfs_dir(parent)

    if xbmcvfs:
        if not xbmcvfs.copy(source, dest):
            raise ImportErrorWithMessage("Could not copy {} to {}".format(source, dest))
        return

    source_path = translate_path(source)
    dest_path = translate_path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_path), str(dest_path))


def read_bytes_vfs(path: str) -> bytes:
    return translate_path(path).read_bytes()


def write_bytes_vfs(dest: str, data: bytes) -> None:
    parent = posixpath.dirname(dest)
    if parent:
        ensure_vfs_dir(parent)
    dest_path = translate_path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(data)


def delete_vfs(path: str) -> None:
    if xbmcvfs:
        xbmcvfs.delete(path)
    else:
        target = translate_path(path)
        if target.exists():
            target.unlink()


def load_last_source() -> str:
    path = translate_path(vfs_join(ADDON_DATA, "last-source.txt"))
    try:
        return path.read_text("utf-8").strip()
    except Exception:
        return ""


def save_last_source(source: str) -> None:
    path = translate_path(vfs_join(ADDON_DATA, "last-source.txt"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, "utf-8")


def first_path(paths: Sequence[Path]) -> Optional[Path]:
    return paths[0] if paths else None


def relative_parts(path: Path, root: Path) -> Tuple[str, ...]:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return path.parts


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
