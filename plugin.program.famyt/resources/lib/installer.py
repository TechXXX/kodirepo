import ast
import datetime
import io
import json
import os
import shutil
import sqlite3
import sys
import traceback
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlencode, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


ADDON_ID = "plugin.program.famyt"
WIDGET_IMPORTER_ADDON_ID = "script.kodiskin.widget.importer"
YOUTUBE_ADDON_ID = "plugin.video.youtube"
YOUTUBE_DATA_PATH = "special://profile/addon_data/plugin.video.youtube"
API_KEYS_FILENAME = "api_keys.json"
CLIENT_ID_SUFFIX = ".apps.googleusercontent.com"
ADVANCEDSETTINGS_PATH = "special://profile/advancedsettings.xml"
KEYMAPS_SOURCE_DIR = os.path.join("resources", "keymaps")
KEYMAPS_TARGET_PATH = "special://profile/keymaps"
THUMBNAILS_PATH = "special://profile/Thumbnails"
TEXTURES_DATABASE_DIR = "special://profile/Database"
PACKAGES_CACHE_PATH = "special://home/addons/packages"
GUISETTINGS_PATH = "special://profile/guisettings.xml"
GUISETTINGS_BACKUP_DIR = os.path.join("backups", "guisettings")
GUISETTINGS_BUILTIN_PATH = os.path.join("resources", "guisettings", "guisettings.xml")
GUISETTINGS_BUILTIN_PRESETS_DIR = os.path.join("resources", "guisettings", "presets")
GUISETTINGS_SAVED_PRESETS_DIR = os.path.join("presets", "guisettings")
GUISETTINGS_DOWNLOAD_MAX_BYTES = 2 * 1024 * 1024
SOURCES_PATH = "special://profile/sources.xml"
SOURCES_BACKUP_DIR = os.path.join("backups", "sources")
SOURCES_BUILTIN_PATH = os.path.join("resources", "sources", "sources.xml")
SOURCES_BUILTIN_PRESETS_DIR = os.path.join("resources", "sources", "presets")
SOURCES_SAVED_PRESETS_DIR = os.path.join("presets", "sources")
SOURCES_DOWNLOAD_MAX_BYTES = 2 * 1024 * 1024
INSTALL_ALL_PRESET_ID = "macbook"
PRESET_MANIFEST_FILENAME = "preset.json"
SKIN_SETTINGS_SOURCE_DIR = os.path.join("resources", "skinsettings")
SKIN_SETTINGS_BUILTIN_PRESETS_DIR = os.path.join("resources", "skinsettings", "presets")
SKIN_SETTINGS_SAVED_PRESETS_DIR = os.path.join("presets", "skinsettings")
SKIN_SETTINGS_BACKUP_DIR = os.path.join("backups", "skinsettings")
SKIN_SETTINGS_DOWNLOAD_MAX_BYTES = 5 * 1024 * 1024
SKIN_SETTINGS_ADDONS = (
    ("skin.dutchtech.fuse.3", "DutchTech Fuse 3", "skin.dutchtech.fuse.3"),
    (
        "skin.dutchtech.fuse.3.kodienglish",
        "Kodi English Fuse 3",
        "skin.dutchtech.fuse.3",
    ),
    (
        "skin.arctic.horizon.2.patched",
        "Arctic Horizon 2 Patched",
        "skin.arctic.horizon.2.patched",
    ),
    (
        "skin.arctic.horizon.2.patched.kodienglish",
        "Arctic Horizon 2 Patched English",
        "skin.arctic.horizon.2.patched",
    ),
    (
        "skin.arctic.horizon.2.1",
        "Arctic Horizon 2.1",
        "skin.arctic.horizon.2.patched",
    ),
)

FENLIGHT_ADDON_IDS = (
    "plugin.video.fenlight",
    "plugin.video.fenlight.patched",
    "plugin.video.fenlight.kodienglish",
    "plugin.video.fenlight.patched.kodienglish",
)
FENLIGHT_ADDON_LABELS = {
    "plugin.video.fenlight": "Fen Light",
    "plugin.video.fenlight.patched": "Fen Light Patched",
    "plugin.video.fenlight.kodienglish": "Fen Light KodiEnglish",
    "plugin.video.fenlight.patched.kodienglish": "Fen Light Patched KodiEnglish",
}
FENLIGHT_SETTINGS_DB = os.path.join("databases", "settings.db")
FENLIGHT_SETTINGS_XML = "settings.xml"
FENLIGHT_SETTINGS_BUILTIN_PRESETS_DIR = os.path.join("resources", "fenlightsettings", "presets")
FENLIGHT_SETTINGS_SAVED_PRESETS_DIR = os.path.join("presets", "fenlightsettings")
FENLIGHT_SETTINGS_BACKUP_DIR = os.path.join("backups", "fenlightsettings")
FENLIGHT_AIOSTREAMS_MANIFEST_SETTING = "tb.usenet_search.aiostreams_manifest"
A4KSUBTITLES_ADDON_IDS = (
    "service.subtitles.a4ksubtitles.patched",
)
A4KSUBTITLES_ADDON_LABELS = {
    "service.subtitles.a4ksubtitles.patched": "a4kSubtitles Patched",
}
A4KSUBTITLES_AI_MODEL = "gpt-4.1-mini-2025-04-14"
A4KSUBTITLES_SETTINGS_XML = "settings.xml"
A4KSUBTITLES_BUILTIN_PRESETS_DIR = os.path.join("resources", "a4ksubtitlessettings", "presets")
A4KSUBTITLES_SAVED_PRESETS_DIR = os.path.join("presets", "a4ksubtitlessettings")
A4KSUBTITLES_BACKUP_DIR = os.path.join("backups", "a4ksubtitlessettings")
COCOSCRAPERS_ADDON_IDS = (
    "script.module.cocoscrapers",
)
COCOSCRAPERS_USER_UNDESIRABLES = (
    ".hc.",
    ".hin.",
    ".hindi.",
    ".ita.",
    ".rus.",
    ".ukr.",
)
COCOSCRAPERS_DISABLED_DEFAULT_UNDESIRABLES = (
    "dutchreleaseteam",
)

MENU_ITEMS = (
    ("[ALL] Kodi sources", "install_sources"),
    ("[ALL] Fen Light settings preset", "install_fenlightsettings"),
    ("[ALL] a4kSubtitles settings preset", "install_a4ksubtitlessettings_preset"),
    ("[ALL] YouTube credentials", "install_youtube"),
    ("[ALL] TorBox API key and Manifest URL", "install_torbox"),
    ("[ALL] a4kSubtitles credentials", "install_a4ksubtitles"),
    ("[ALL] Cocoscrapers filters", "install_cocoscrapers"),
    ("[ALL] Kodi network settings", "install_advanced_network"),
    ("[ALL] Kodi keymaps", "install_keymaps"),
    ("Install everything", "install_all"),
    ("KodiSkin Widget Importer", "launch_widget_importer"),
    ("Utilities", "menu_utilities", True),
    ("Kodi GUI settings", "menu_guisettings", True),
    ("Kodi sources", "menu_sources", True),
    ("Fen Light settings", "menu_fenlightsettings", True),
    ("a4kSubtitles backup/restore", "menu_a4ksubtitlessettings", True),
    ("Skin settings", "menu_skinsettings", True),
)

GUISETTINGS_MENU_ITEMS = (
    ("Back up Kodi GUI settings", "backup_guisettings"),
    ("Save current GUI settings as preset", "save_guisettings_preset"),
    ("Rename GUI settings preset", "rename_guisettings_preset"),
    ("Delete GUI settings preset", "delete_guisettings_preset"),
    ("Restore GUI settings from URL", "restore_guisettings_url"),
    ("Restore GUI settings preset", "restore_guisettings_builtin"),
)

SOURCES_MENU_ITEMS = (
    ("Back up Kodi sources", "backup_sources"),
    ("Save current sources as preset", "save_sources_preset"),
    ("Rename sources preset", "rename_sources_preset"),
    ("Delete sources preset", "delete_sources_preset"),
    ("Restore sources from URL", "restore_sources_url"),
    ("Restore sources preset", "restore_sources_builtin"),
)

FENLIGHTSETTINGS_MENU_ITEMS = (
    ("Back up Fen Light settings", "backup_fenlightsettings"),
    ("Save current Fen Light settings as preset", "save_fenlightsettings_preset"),
    ("Rename Fen Light settings preset", "rename_fenlightsettings_preset"),
    ("Delete Fen Light settings preset", "delete_fenlightsettings_preset"),
    ("Restore Fen Light settings preset", "restore_fenlightsettings_builtin"),
)

A4KSUBTITLESSETTINGS_MENU_ITEMS = (
    ("Back up a4kSubtitles settings", "backup_a4ksubtitlessettings"),
    ("Save current a4kSubtitles settings as preset", "save_a4ksubtitlessettings_preset"),
    ("Rename a4kSubtitles settings preset", "rename_a4ksubtitlessettings_preset"),
    ("Delete a4kSubtitles settings preset", "delete_a4ksubtitlessettings_preset"),
    ("Restore a4kSubtitles settings preset", "restore_a4ksubtitlessettings_builtin"),
)

SKINSETTINGS_MENU_ITEMS = (
    ("Back up skin settings", "backup_skinsettings"),
    ("Save current skin settings as preset", "save_skinsettings_preset"),
    ("Rename skin settings preset", "rename_skinsettings_preset"),
    ("Delete skin settings preset", "delete_skinsettings_preset"),
    ("Restore skin settings from URL", "restore_skinsettings_url"),
    ("Restore skin settings preset", "restore_skinsettings_builtin"),
)

UTILITIES_MENU_ITEMS = (
    ("Show setup status", "show_setup_status"),
    ("Export debug bundle", "export_debug_bundle"),
    ("Clear thumbnail cache", "clear_thumbnail_cache"),
    ("Clear add-on package cache", "clear_package_cache"),
    ("Clean Setup Kit backups", "clean_setup_backups"),
    ("Reload skin", "reload_skin"),
    ("Restart Kodi", "restart_kodi"),
)

UTILITY_ACTIONS = tuple(item[1] for item in UTILITIES_MENU_ITEMS)


def _addon():
    return xbmcaddon.Addon(ADDON_ID)


def _log(message, level=xbmc.LOGINFO):
    xbmc.log("[Kodi Setup Kit] %s" % message, level)


def _translate_path(path):
    translated = xbmcvfs.translatePath(path)
    if isinstance(translated, bytes):
        translated = translated.decode("utf-8")
    return translated


def _get_setting(addon, key):
    getter = getattr(addon, "getSettingString", None)
    if callable(getter):
        return getter(key)
    return addon.getSetting(key)


def _set_setting(addon, key, value):
    setter = getattr(addon, "setSettingString", None)
    if callable(setter):
        setter(key, value)
        return
    addon.setSetting(key, value)


def _set_timestamp(addon, key, touch_last_install=False):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, key, now)
    if touch_last_install:
        _set_setting(addon, "last_install", now)
    return now


def _notify(message, heading="Kodi Setup Kit", icon=xbmcgui.NOTIFICATION_INFO, ms=5000):
    xbmcgui.Dialog().notification(heading, message, icon, ms)


def _show_text(heading, text):
    dialog = xbmcgui.Dialog()
    textviewer = getattr(dialog, "textviewer", None)
    if callable(textviewer):
        textviewer(heading, text)
        return
    dialog.ok(heading, text)


def _yesno(heading, message, yes_label="Yes", no_label="No"):
    dialog = xbmcgui.Dialog()
    try:
        return dialog.yesno(heading, message, nolabel=no_label, yeslabel=yes_label)
    except TypeError:
        try:
            return dialog.yesno(heading, message, no_label, yes_label)
        except TypeError:
            return dialog.yesno(heading, message)


def _plugin_handle():
    try:
        return int(sys.argv[1])
    except Exception:
        return -1


def _end_plugin_directory():
    handle = _plugin_handle()
    if handle < 0:
        return
    try:
        import xbmcplugin

        xbmcplugin.endOfDirectory(handle, succeeded=True)
    except Exception:
        pass


def _query_params():
    query = ""
    if len(sys.argv) > 2:
        query = (sys.argv[2] or "").lstrip("?")
    return dict(parse_qsl(query))


def _menu_url(action):
    return "%s?%s" % (sys.argv[0], urlencode({"action": action}))


def _show_menu(items=MENU_ITEMS):
    handle = _plugin_handle()
    if handle < 0:
        xbmcgui.Dialog().ok("Kodi Setup Kit", "Open Kodi Setup Kit from Kodi's program add-ons menu.")
        return

    import xbmcplugin

    for entry in items:
        label, action = entry[0], entry[1]
        is_folder = bool(entry[2]) if len(entry) > 2 else False
        item = xbmcgui.ListItem(label=label)
        try:
            item.setArt({"icon": "DefaultAddonProgram.png"})
        except Exception:
            pass
        xbmcplugin.addDirectoryItem(handle, _menu_url(action), item, is_folder)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def _prompt_password():
    dialog = xbmcgui.Dialog()
    hidden_option = getattr(xbmcgui, "ALPHANUM_HIDE_INPUT", 0)
    return dialog.input(
        "Kodi Setup Kit password",
        type=getattr(xbmcgui, "INPUT_ALPHANUM", 0),
        option=hidden_option,
    )


def _json_response(status, message):
    return RuntimeError("Bridge returned %s: %s" % (status, message))


def _read_bridge_response(api_url, password):
    payload = json.dumps({"password": password}).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Kodi Setup Kit Kodi add-on",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
            message = data.get("error") or data.get("message") or exc.reason
        except Exception:
            message = exc.reason
        raise _json_response(exc.code, message)
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach Kodi Setup Kit bridge: %s" % exc.reason)
    except ValueError:
        raise RuntimeError("Kodi Setup Kit bridge returned invalid JSON")


def _pick(data, *keys):
    if not isinstance(data, dict):
        return ""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_youtube_keys(data):
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else data
    api_key = _pick(keys, "api_key", "apiKey")
    client_id = _pick(keys, "client_id", "clientId")
    client_secret = _pick(keys, "client_secret", "clientSecret")

    missing = []
    if not api_key:
        missing.append("api_key")
    if not client_id:
        missing.append("client_id")
    if not client_secret:
        missing.append("client_secret")
    if missing:
        raise RuntimeError("Kodi Setup Kit bridge response is missing: %s" % ", ".join(missing))

    if client_id.endswith(CLIENT_ID_SUFFIX):
        client_id = client_id[: -len(CLIENT_ID_SUFFIX)]

    return {
        "api_key": api_key,
        "client_id": client_id,
        "client_secret": client_secret,
    }


def _extract_torbox_key(data):
    torbox = data.get("torbox") if isinstance(data.get("torbox"), dict) else {}
    api_key = _pick(torbox, "api_key", "apiKey", "token")
    if not api_key:
        api_key = _pick(data, "torbox_api_key", "torboxApiKey", "torbox_token", "torboxToken")
    if not api_key:
        raise RuntimeError(
            "Kodi Setup Kit bridge response is missing torbox.api_key. "
            "Add TORBOX_API_KEY to the Vercel environment and redeploy."
        )
    return api_key


def _extract_torbox_aiostreams_manifest(data):
    torbox = data.get("torbox") if isinstance(data.get("torbox"), dict) else {}
    return _pick(
        torbox,
        "aiostreams_manifest_url",
        "aiostreamsManifestUrl",
        "aiostreams_manifest",
        "aiostreamsManifest",
        "manifest_url",
        "manifestUrl",
    ) or _pick(
        data,
        "torbox_aiostreams_manifest_url",
        "torboxAiostreamsManifestUrl",
        "torbox_manifest_url",
        "torboxManifestUrl",
    )


def _extract_a4ksubtitles_settings(data):
    a4k = data.get("a4ksubtitles") if isinstance(data.get("a4ksubtitles"), dict) else {}
    if not a4k:
        a4k = data.get("a4ksubs") if isinstance(data.get("a4ksubs"), dict) else {}

    opensubtitles = (
        a4k.get("opensubtitles") if isinstance(a4k.get("opensubtitles"), dict) else {}
    )
    ai = a4k.get("ai") if isinstance(a4k.get("ai"), dict) else {}

    opensubtitles_username = _pick(
        opensubtitles,
        "username",
        "user",
    ) or _pick(
        a4k,
        "opensubtitles_username",
        "openSubtitlesUsername",
        "opensubtitlesUser",
    )
    opensubtitles_password = _pick(
        opensubtitles,
        "password",
        "pass",
    ) or _pick(
        a4k,
        "opensubtitles_password",
        "openSubtitlesPassword",
    )
    ai_api_key = _pick(
        ai,
        "api_key",
        "apiKey",
        "key",
    ) or _pick(
        a4k,
        "ai_api_key",
        "aiApiKey",
        "openai_api_key",
        "openAiApiKey",
    )

    missing = []
    if not opensubtitles_username:
        missing.append("a4ksubtitles.opensubtitles.username")
    if not opensubtitles_password:
        missing.append("a4ksubtitles.opensubtitles.password")
    if not ai_api_key:
        missing.append("a4ksubtitles.ai.api_key")
    if missing:
        raise RuntimeError(
            "Kodi Setup Kit bridge response is missing: %s. "
            "Add the A4KSUBS_* values to the Vercel environment and redeploy."
            % ", ".join(missing)
        )

    return {
        "opensubtitles.username": opensubtitles_username,
        "opensubtitles.password": opensubtitles_password,
        "opensubtitles.enabled": "true",
        "general.ai_api_key": ai_api_key,
        "general.use_ai": "true",
        "general.ai_provider": "0",
        "general.ai_model": A4KSUBTITLES_AI_MODEL,
    }


def _write_api_keys(keys):
    data_dir = _translate_path(YOUTUBE_DATA_PATH)
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)

    api_keys_path = os.path.join(data_dir, API_KEYS_FILENAME)
    tmp_path = api_keys_path + ".tmp"
    payload = {
        "keys": {
            "developer": {},
            "user": {
                "api_key": keys["api_key"],
                "client_id": keys["client_id"],
                "client_secret": keys["client_secret"],
            },
        },
    }

    with io.open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=4, sort_keys=True)
        handle.write("\n")
    if os.path.exists(api_keys_path):
        os.remove(api_keys_path)
    os.rename(tmp_path, api_keys_path)
    return api_keys_path


def _update_youtube_settings(keys):
    try:
        youtube = xbmcaddon.Addon(YOUTUBE_ADDON_ID)
    except Exception:
        _log("YouTube add-on was not found; wrote api_keys.json only", xbmc.LOGWARNING)
        return False

    _set_setting(youtube, "youtube.api.key", keys["api_key"])
    _set_setting(youtube, "youtube.api.id", keys["client_id"])
    _set_setting(youtube, "youtube.api.secret", keys["client_secret"])
    return True


def _addon_installed(addon_id):
    try:
        xbmcaddon.Addon(addon_id)
        return True
    except Exception:
        return False


def _addon_data_path(addon_id):
    return _translate_path("special://profile/addon_data/%s" % addon_id)


def _candidate_fenlight_addons():
    found = []
    for addon_id in FENLIGHT_ADDON_IDS:
        data_path = _addon_data_path(addon_id)
        if _addon_installed(addon_id) or os.path.isdir(data_path):
            found.append((addon_id, data_path))
    return found


def _candidate_a4ksubtitles_addons():
    found = []
    for addon_id in A4KSUBTITLES_ADDON_IDS:
        data_path = _addon_data_path(addon_id)
        if _addon_installed(addon_id) or os.path.isdir(data_path):
            found.append((addon_id, data_path))
    return found


def _candidate_cocoscrapers_addons():
    found = []
    for addon_id in COCOSCRAPERS_ADDON_IDS:
        data_path = _addon_data_path(addon_id)
        if _addon_installed(addon_id) or os.path.isdir(data_path):
            found.append((addon_id, data_path))
    return found


def _addon_install_path(addon_id):
    try:
        path = xbmcaddon.Addon(addon_id).getAddonInfo("path")
    except Exception:
        return ""
    return _translate_path(path)


def _write_fenlight_torbox_setting(addon_id, data_path, api_key, aiostreams_manifest_url=""):
    db_path = os.path.join(data_path, FENLIGHT_SETTINGS_DB)
    db_dir = os.path.dirname(db_path)
    if not os.path.isdir(db_dir):
        os.makedirs(db_dir)

    rows = [
        ("tb.token", "string", "empty_setting", api_key),
        ("tb.enabled", "boolean", "false", "true"),
    ]
    if aiostreams_manifest_url:
        rows.append(
            (
                FENLIGHT_AIOSTREAMS_MANIFEST_SETTING,
                "string",
                "empty_setting",
                aiostreams_manifest_url,
            )
        )

    connection = sqlite3.connect(db_path, timeout=10)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS settings "
            "(setting_id text not null unique, setting_type text, "
            "setting_default text, setting_value text)"
        )
        connection.executemany(
            "INSERT OR REPLACE INTO settings "
            "(setting_id, setting_type, setting_default, setting_value) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        connection.commit()
    finally:
        connection.close()

    _log("Installed TorBox API key for %s at %s" % (addon_id, db_path))
    return db_path


def _set_fenlight_window_cache(api_key, aiostreams_manifest_url=""):
    try:
        window = xbmcgui.Window(10000)
        window.setProperty("fenlight.tb.token", api_key)
        window.setProperty("fenlight.tb.enabled", "true")
        if aiostreams_manifest_url:
            window.setProperty(
                "fenlight.%s" % FENLIGHT_AIOSTREAMS_MANIFEST_SETTING,
                aiostreams_manifest_url,
            )
    except Exception:
        pass


def _indent_xml(element, level=0):
    children = list(element)
    if not children:
        return

    indentation = "\n" + "    " * (level + 1)
    if not element.text or not element.text.strip():
        element.text = indentation

    for child in children:
        _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indentation

    children[-1].tail = "\n" + "    " * level


def _parse_xml(path):
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        return ET.parse(path, parser=parser)
    except TypeError:
        return ET.parse(path)


def _utc_timestamp():
    return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def _backup_file(path):
    backup_path = "%s.famyt-backup-%s" % (path, _utc_timestamp())
    os.replace(path, backup_path)
    return backup_path


def _copy_binary_file(source_path, target_path):
    parent = os.path.dirname(target_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(source_path, "rb") as source:
        payload = source.read()
    with io.open(target_path, "wb") as target:
        target.write(payload)
    return target_path


def _same_file_bytes(path, payload):
    if not os.path.exists(path):
        return False
    try:
        with io.open(path, "rb") as handle:
            return handle.read() == payload
    except Exception:
        return False


def _direct_child(element, tag):
    for child in list(element):
        if child.tag == tag:
            return child
    return None


def _set_direct_child_text(element, tag, value):
    child = _direct_child(element, tag)
    if child is None:
        child = ET.SubElement(element, tag)
    child.text = value
    return child


def _write_advanced_network_settings():
    userdata_path = _translate_path("special://profile")
    if not os.path.isdir(userdata_path):
        os.makedirs(userdata_path)

    advancedsettings_path = _translate_path(ADVANCEDSETTINGS_PATH)
    backup_path = ""

    if os.path.exists(advancedsettings_path):
        try:
            tree = _parse_xml(advancedsettings_path)
            root = tree.getroot()
            if root.tag != "advancedsettings":
                backup_path = _backup_file(advancedsettings_path)
                root = ET.Element("advancedsettings", {"version": "1.0"})
                tree = ET.ElementTree(root)
        except Exception as exc:
            backup_path = _backup_file(advancedsettings_path)
            root = ET.Element("advancedsettings", {"version": "1.0"})
            tree = ET.ElementTree(root)
            _log("Backed up invalid advancedsettings.xml: %s" % exc, xbmc.LOGWARNING)
    else:
        root = ET.Element("advancedsettings", {"version": "1.0"})
        tree = ET.ElementTree(root)

    network = _direct_child(root, "network")
    if network is None:
        network = ET.SubElement(root, "network")

    _set_direct_child_text(network, "disablehttp2", "true")
    _set_direct_child_text(network, "disableipv6", "true")

    _indent_xml(root)
    tmp_path = advancedsettings_path + ".tmp"
    tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
    if os.path.exists(advancedsettings_path):
        os.remove(advancedsettings_path)
    os.rename(tmp_path, advancedsettings_path)

    _log("Installed Kodi network advanced settings at %s" % advancedsettings_path)
    return advancedsettings_path, backup_path


def _addon_resource_path(*parts):
    addon_path = xbmcaddon.Addon(ADDON_ID).getAddonInfo("path")
    return os.path.join(_translate_path(addon_path), *parts)


def _preset_id_from_name(name):
    cleaned = []
    previous_dash = False
    name = (name or "").strip().encode("ascii", "ignore").decode("ascii")
    for char in name.lower():
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
        elif char in (" ", "-", "_", "."):
            if not previous_dash:
                cleaned.append("-")
                previous_dash = True
    preset_id = "".join(cleaned).strip("-")
    if not preset_id:
        raise RuntimeError("Enter a preset name using letters or numbers.")
    return preset_id


def _preset_name_from_id(preset_id):
    return " ".join(part.capitalize() for part in preset_id.replace("_", "-").split("-") if part)


def _prompt_preset_name(kind):
    return xbmcgui.Dialog().input(
        "%s preset name" % kind,
        type=getattr(xbmcgui, "INPUT_ALPHANUM", 0),
    ).strip()


def _write_json_file(path, data):
    tmp_path = path + ".tmp"
    with io.open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4, sort_keys=True)
        handle.write("\n")
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp_path, path)


def _write_binary_payload(path, payload):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    tmp_path = path + ".tmp"
    with io.open(tmp_path, "wb") as handle:
        handle.write(payload)
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp_path, path)
    return path


def _read_preset_name(preset_dir, fallback_id):
    manifest_path = os.path.join(preset_dir, PRESET_MANIFEST_FILENAME)
    if os.path.exists(manifest_path):
        try:
            with io.open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            name = manifest.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except Exception as exc:
            _log("Could not read preset manifest %s: %s" % (manifest_path, exc), xbmc.LOGWARNING)
    return _preset_name_from_id(fallback_id)


def _write_preset_manifest(preset_dir, preset_id, preset_name, preset_type):
    if not os.path.isdir(preset_dir):
        os.makedirs(preset_dir)
    _write_json_file(
        os.path.join(preset_dir, PRESET_MANIFEST_FILENAME),
        {
            "id": preset_id,
            "name": preset_name,
            "type": preset_type,
            "saved_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
    )


def _preset_label(preset):
    origin = "Built-in" if preset["origin"] == "builtin" else "Saved"
    return "%s [%s]" % (preset["name"], origin)


def _prompt_preset(presets, heading):
    if not presets:
        raise RuntimeError("No presets were found.")
    labels = [_preset_label(preset) for preset in presets]
    index = xbmcgui.Dialog().select(heading, labels)
    if index < 0:
        return None
    return presets[index]


def _manageable_preset(preset):
    if preset.get("id") == "built-in":
        raise RuntimeError("The legacy built-in preset cannot be renamed or deleted.")
    return preset


def _rename_preset(preset, new_name, preset_type):
    _manageable_preset(preset)
    new_id = _preset_id_from_name(new_name)
    old_dir = preset["dir"]
    parent_dir = os.path.dirname(old_dir)
    new_dir = os.path.join(parent_dir, new_id)

    if os.path.normcase(os.path.abspath(old_dir)) == os.path.normcase(os.path.abspath(new_dir)):
        _write_preset_manifest(old_dir, new_id, new_name, preset_type)
        return old_dir

    if os.path.exists(new_dir):
        raise RuntimeError("A preset named %s already exists." % new_name)

    os.rename(old_dir, new_dir)
    _write_preset_manifest(new_dir, new_id, new_name, preset_type)
    _log("Renamed %s preset %s to %s" % (preset_type, preset["id"], new_id))
    return new_dir


def _delete_preset(preset, preset_type):
    _manageable_preset(preset)
    preset_dir = preset["dir"]
    if not os.path.isdir(preset_dir):
        raise RuntimeError("Preset folder was not found.")
    shutil.rmtree(preset_dir)
    _log("Deleted %s preset %s from %s" % (preset_type, preset["id"], preset_dir))
    return preset_dir


def _confirm_delete_preset(preset):
    return _yesno(
        "Kodi Setup Kit",
        (
            "Delete preset %s?\n\n"
            "This removes that preset from %s storage.\n\n"
            "It does not change current Kodi settings."
        )
        % (_preset_label(preset), preset["origin"]),
        yes_label="Delete",
        no_label="Cancel",
    )


def _preset_dirs(root_dir, payload_exists):
    presets = []
    if not os.path.isdir(root_dir):
        return presets
    for preset_id in sorted(os.listdir(root_dir)):
        if preset_id.startswith("."):
            continue
        preset_dir = os.path.join(root_dir, preset_id)
        if not os.path.isdir(preset_dir) or not payload_exists(preset_dir):
            continue
        presets.append((preset_id, preset_dir, _read_preset_name(preset_dir, preset_id)))
    return presets


def _default_builtin_preset(presets, kind):
    for preset in presets:
        if preset.get("id") == INSTALL_ALL_PRESET_ID:
            return preset
    for preset in presets:
        if preset.get("origin") == "builtin":
            return preset
    raise RuntimeError("No built-in %s preset was found." % kind)


def _matching_preset_payload(payloads, target_addon_id, kind):
    for payload in payloads:
        if payload[0] == target_addon_id:
            return payload
    if len(payloads) == 1:
        return payloads[0]
    raise RuntimeError("%s preset does not include settings for %s." % (kind, target_addon_id))


def _save_payload_to_roots(roots, preset_id, preset_name, preset_type, writer):
    saved = []
    errors = []
    for origin, preset_dir in roots:
        try:
            _write_preset_manifest(preset_dir, preset_id, preset_name, preset_type)
            writer(preset_dir)
            saved.append((origin, preset_dir))
        except Exception as exc:
            errors.append("%s: %s" % (origin, exc))
            _log("Could not save %s preset to %s: %s" % (preset_type, preset_dir, exc), xbmc.LOGWARNING)
    if not saved:
        raise RuntimeError("Could not save preset: %s" % "; ".join(errors))
    return saved, errors


def _keymap_source_files():
    source_dir = _addon_resource_path(KEYMAPS_SOURCE_DIR)
    if not os.path.isdir(source_dir):
        raise RuntimeError("Kodi Setup Kit keymap bundle was not found.")

    keymap_files = []
    for name in sorted(os.listdir(source_dir)):
        if name.startswith("._") or not name.lower().endswith(".xml"):
            continue
        path = os.path.join(source_dir, name)
        if os.path.isfile(path):
            keymap_files.append((name, path))
    if not keymap_files:
        raise RuntimeError("Kodi Setup Kit keymap bundle is empty.")
    return keymap_files


def _install_keymap_files():
    target_dir = _translate_path(KEYMAPS_TARGET_PATH)
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)

    installed = []
    backups = []
    for name, source_path in _keymap_source_files():
        with io.open(source_path, "rb") as handle:
            payload = handle.read()

        target_path = os.path.join(target_dir, name)
        if _same_file_bytes(target_path, payload):
            installed.append(name)
            continue

        if os.path.exists(target_path):
            backups.append(_backup_file(target_path))

        tmp_path = target_path + ".tmp"
        with io.open(tmp_path, "wb") as handle:
            handle.write(payload)
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(tmp_path, target_path)
        installed.append(name)

    _log("Installed Kodi keymaps at %s: %s" % (target_dir, ", ".join(installed)))
    return installed, backups


def _addon_data_dir(*parts):
    data_dir = _addon_data_path(*parts)
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    return data_dir


def _addon_data_path(*parts):
    data_dir = _translate_path("special://profile/addon_data/%s" % ADDON_ID)
    if parts:
        data_dir = os.path.join(data_dir, *parts)
    return data_dir


def _guisettings_path():
    return _translate_path(GUISETTINGS_PATH)


def _parse_guisettings_payload(payload):
    try:
        root = ET.fromstring(payload)
    except Exception as exc:
        raise RuntimeError("GUI settings XML is invalid: %s" % exc)
    if root.tag != "settings":
        raise RuntimeError("GUI settings XML must have a <settings> root.")
    if not root.findall("./setting"):
        raise RuntimeError("GUI settings XML does not contain any <setting> entries.")
    return root


def _guisettings_backup_path(prefix):
    backup_dir = _addon_data_dir(GUISETTINGS_BACKUP_DIR)
    return os.path.join(backup_dir, "%s-%s.xml" % (prefix, _utc_timestamp()))


def _backup_current_guisettings(prefix="guisettings"):
    source_path = _guisettings_path()
    if not os.path.exists(source_path):
        raise RuntimeError("guisettings.xml was not found in this Kodi profile.")
    target_path = _guisettings_backup_path(prefix)
    _copy_binary_file(source_path, target_path)
    _log("Backed up guisettings.xml to %s" % target_path)
    return target_path


def _jsonrpc_guisetting_value(text):
    if text is None:
        return ""
    value = text.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if value and value.lstrip("-").isdigit():
        try:
            return int(value)
        except Exception:
            return value
    if value and "." in value:
        try:
            return float(value)
        except Exception:
            return value
    return value


def _apply_guisettings_live(root):
    execute_jsonrpc = getattr(xbmc, "executeJSONRPC", None)
    if not callable(execute_jsonrpc):
        return 0, 0

    applied = 0
    failed = 0
    for node in root.findall("./setting"):
        setting_id = node.get("id")
        if not setting_id:
            continue
        payload = {
            "jsonrpc": "2.0",
            "method": "Settings.SetSettingValue",
            "params": {
                "setting": setting_id,
                "value": _jsonrpc_guisetting_value(node.text),
            },
            "id": 1,
        }
        try:
            response = json.loads(execute_jsonrpc(json.dumps(payload)))
            if response.get("result") == "OK":
                applied += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return applied, failed


def _write_guisettings_payload(payload, source_label):
    root = _parse_guisettings_payload(payload)
    userdata_path = _translate_path("special://profile")
    if not os.path.isdir(userdata_path):
        os.makedirs(userdata_path)

    guisettings_path = _guisettings_path()
    backup_path = ""
    if os.path.exists(guisettings_path):
        backup_path = _backup_current_guisettings("guisettings-before-restore")

    applied, failed = _apply_guisettings_live(root)

    tmp_path = guisettings_path + ".tmp"
    with io.open(tmp_path, "wb") as handle:
        handle.write(payload)
    if os.path.exists(guisettings_path):
        os.remove(guisettings_path)
    os.rename(tmp_path, guisettings_path)

    _log("Restored guisettings.xml from %s to %s" % (source_label, guisettings_path))
    return guisettings_path, backup_path, applied, failed


def _guisettings_payload_exists(preset_dir):
    return os.path.exists(os.path.join(preset_dir, "guisettings.xml"))


def _guisettings_builtin_presets():
    presets = []
    root_dir = _addon_resource_path(GUISETTINGS_BUILTIN_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _guisettings_payload_exists):
        presets.append(
            {
                "origin": "builtin",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
                "payload_path": os.path.join(preset_dir, "guisettings.xml"),
            }
        )

    legacy_path = _addon_resource_path(GUISETTINGS_BUILTIN_PATH)
    if not presets and os.path.exists(legacy_path):
        presets.append(
            {
                "origin": "builtin",
                "id": "built-in",
                "name": "Built-in",
                "dir": os.path.dirname(legacy_path),
                "payload_path": legacy_path,
            }
        )
    return presets


def _guisettings_saved_presets():
    presets = []
    root_dir = _addon_data_dir(GUISETTINGS_SAVED_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _guisettings_payload_exists):
        presets.append(
            {
                "origin": "saved",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
                "payload_path": os.path.join(preset_dir, "guisettings.xml"),
            }
        )
    return presets


def _guisettings_presets():
    return _guisettings_builtin_presets() + _guisettings_saved_presets()


def _prompt_guisettings_preset():
    return _prompt_preset(_guisettings_presets(), "GUI settings preset")


def _read_guisettings_preset_payload(preset):
    source_path = preset["payload_path"]
    if not os.path.exists(source_path):
        raise RuntimeError("GUI settings preset is missing guisettings.xml.")
    with io.open(source_path, "rb") as handle:
        payload = handle.read()
    _parse_guisettings_payload(payload)
    return payload


def _save_guisettings_preset(addon, preset_name):
    preset_id = _preset_id_from_name(preset_name)
    source_path = _guisettings_path()
    if not os.path.exists(source_path):
        raise RuntimeError("guisettings.xml was not found in this Kodi profile.")
    with io.open(source_path, "rb") as handle:
        payload = handle.read()
    _parse_guisettings_payload(payload)

    roots = (
        (
            "built-in",
            _addon_resource_path(GUISETTINGS_BUILTIN_PRESETS_DIR, preset_id),
        ),
        (
            "saved",
            _addon_data_dir(GUISETTINGS_SAVED_PRESETS_DIR, preset_id),
        ),
    )

    def writer(preset_dir):
        _write_binary_payload(os.path.join(preset_dir, "guisettings.xml"), payload)

    saved, errors = _save_payload_to_roots(roots, preset_id, preset_name, "guisettings", writer)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_guisettings_preset_save", now)
    _set_setting(addon, "last_install", now)

    message = "GUI settings preset saved as %s." % preset_name
    message += "\n\nSaved locations: %s" % ", ".join(origin for origin, _path in saved)
    if errors:
        message += "\n\nSome locations were skipped: %s" % "; ".join(errors)
    return message


def _rename_guisettings_preset(addon, preset, new_name):
    _rename_preset(preset, new_name, "guisettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_guisettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "GUI settings preset renamed to %s." % new_name


def _delete_guisettings_preset(addon, preset):
    _delete_preset(preset, "guisettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_guisettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "GUI settings preset deleted: %s." % preset["name"]


def _download_guisettings_payload(url):
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError("Enter a valid http or https URL.")

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/xml,text/xml,*/*",
            "User-Agent": "Kodi Setup Kit Kodi add-on",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read(GUISETTINGS_DOWNLOAD_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Could not download GUI settings: HTTP %s" % exc.code)
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not download GUI settings: %s" % exc.reason)

    if len(payload) > GUISETTINGS_DOWNLOAD_MAX_BYTES:
        raise RuntimeError("GUI settings download is too large.")
    _parse_guisettings_payload(payload)
    return payload


def _prompt_guisettings_url():
    return xbmcgui.Dialog().input(
        "GUI settings URL",
        type=getattr(xbmcgui, "INPUT_ALPHANUM", 0),
    )


def _confirm_guisettings_restore(source_label):
    return _yesno(
        "Kodi Setup Kit",
        (
            "Restore Kodi GUI settings from %s?\n\n"
            "The current guisettings.xml will be backed up first.\n\n"
            "Restart Kodi immediately after restore."
        )
        % source_label,
        yes_label="Restore",
        no_label="Cancel",
    )


def _restore_guisettings_message(source_label, guisettings_path, backup_path, applied, failed):
    message = (
        "GUI settings restored from %s. Restart Kodi immediately for the safest result."
        % source_label
    )
    if backup_path:
        message += "\n\nBackup saved to: %s" % backup_path
    message += "\n\nLive settings applied: %s" % applied
    if failed:
        message += " (%s could not be applied live)." % failed
    return message


def _sources_path():
    return _translate_path(SOURCES_PATH)


def _parse_sources_payload(payload):
    try:
        root = ET.fromstring(payload)
    except Exception as exc:
        raise RuntimeError("Sources XML is invalid: %s" % exc)
    if root.tag != "sources":
        raise RuntimeError("Sources XML must have a <sources> root.")
    if not root.findall(".//source"):
        raise RuntimeError("Sources XML does not contain any <source> entries.")
    return root


def _sources_backup_path(prefix):
    backup_dir = _addon_data_dir(SOURCES_BACKUP_DIR)
    return os.path.join(backup_dir, "%s-%s.xml" % (prefix, _utc_timestamp()))


def _backup_current_sources(prefix="sources"):
    source_path = _sources_path()
    if not os.path.exists(source_path):
        raise RuntimeError("sources.xml was not found in this Kodi profile.")
    target_path = _sources_backup_path(prefix)
    _copy_binary_file(source_path, target_path)
    _log("Backed up sources.xml to %s" % target_path)
    return target_path


def _write_sources_payload(payload, source_label):
    _parse_sources_payload(payload)
    userdata_path = _translate_path("special://profile")
    if not os.path.isdir(userdata_path):
        os.makedirs(userdata_path)

    sources_path = _sources_path()
    backup_path = ""
    if os.path.exists(sources_path):
        backup_path = _backup_current_sources("sources-before-restore")

    tmp_path = sources_path + ".tmp"
    with io.open(tmp_path, "wb") as handle:
        handle.write(payload)
    if os.path.exists(sources_path):
        os.remove(sources_path)
    os.rename(tmp_path, sources_path)

    _log("Restored sources.xml from %s to %s" % (source_label, sources_path))
    return sources_path, backup_path


def _sources_payload_exists(preset_dir):
    return os.path.exists(os.path.join(preset_dir, "sources.xml"))


def _sources_builtin_presets():
    presets = []
    root_dir = _addon_resource_path(SOURCES_BUILTIN_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _sources_payload_exists):
        presets.append(
            {
                "origin": "builtin",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
                "payload_path": os.path.join(preset_dir, "sources.xml"),
            }
        )

    legacy_path = _addon_resource_path(SOURCES_BUILTIN_PATH)
    if not presets and os.path.exists(legacy_path):
        presets.append(
            {
                "origin": "builtin",
                "id": "built-in",
                "name": "Built-in",
                "dir": os.path.dirname(legacy_path),
                "payload_path": legacy_path,
            }
        )
    return presets


def _sources_saved_presets():
    presets = []
    root_dir = _addon_data_dir(SOURCES_SAVED_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _sources_payload_exists):
        presets.append(
            {
                "origin": "saved",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
                "payload_path": os.path.join(preset_dir, "sources.xml"),
            }
        )
    return presets


def _sources_presets():
    return _sources_builtin_presets() + _sources_saved_presets()


def _prompt_sources_preset():
    return _prompt_preset(_sources_presets(), "Sources preset")


def _read_sources_preset_payload(preset):
    source_path = preset["payload_path"]
    if not os.path.exists(source_path):
        raise RuntimeError("Sources preset is missing sources.xml.")
    with io.open(source_path, "rb") as handle:
        payload = handle.read()
    _parse_sources_payload(payload)
    return payload


def _save_sources_preset(addon, preset_name):
    preset_id = _preset_id_from_name(preset_name)
    source_path = _sources_path()
    if not os.path.exists(source_path):
        raise RuntimeError("sources.xml was not found in this Kodi profile.")
    with io.open(source_path, "rb") as handle:
        payload = handle.read()
    _parse_sources_payload(payload)

    roots = (
        (
            "built-in",
            _addon_resource_path(SOURCES_BUILTIN_PRESETS_DIR, preset_id),
        ),
        (
            "saved",
            _addon_data_dir(SOURCES_SAVED_PRESETS_DIR, preset_id),
        ),
    )

    def writer(preset_dir):
        _write_binary_payload(os.path.join(preset_dir, "sources.xml"), payload)

    saved, errors = _save_payload_to_roots(roots, preset_id, preset_name, "sources", writer)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_sources_preset_save", now)
    _set_setting(addon, "last_install", now)

    message = "Sources preset saved as %s." % preset_name
    message += "\n\nSaved locations: %s" % ", ".join(origin for origin, _path in saved)
    if errors:
        message += "\n\nSome locations were skipped: %s" % "; ".join(errors)
    return message


def _rename_sources_preset(addon, preset, new_name):
    _rename_preset(preset, new_name, "sources")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_sources_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "Sources preset renamed to %s." % new_name


def _delete_sources_preset(addon, preset):
    _delete_preset(preset, "sources")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_sources_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "Sources preset deleted: %s." % preset["name"]


def _download_sources_payload(url):
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError("Enter a valid http or https URL.")

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/xml,text/xml,*/*",
            "User-Agent": "Kodi Setup Kit Kodi add-on",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read(SOURCES_DOWNLOAD_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Could not download sources: HTTP %s" % exc.code)
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not download sources: %s" % exc.reason)

    if len(payload) > SOURCES_DOWNLOAD_MAX_BYTES:
        raise RuntimeError("Sources download is too large.")
    _parse_sources_payload(payload)
    return payload


def _prompt_sources_url():
    return xbmcgui.Dialog().input(
        "Sources XML URL",
        type=getattr(xbmcgui, "INPUT_ALPHANUM", 0),
    )


def _confirm_sources_restore(source_label):
    return _yesno(
        "Kodi Setup Kit",
        (
            "Restore Kodi sources from %s?\n\n"
            "The current sources.xml will be backed up first.\n\n"
            "Restart Kodi after restore so File manager and source pickers refresh."
        )
        % source_label,
        yes_label="Restore",
        no_label="Cancel",
    )


def _restore_sources_message(source_label, sources_path, backup_path):
    message = (
        "Kodi sources restored from %s. Restart Kodi so File manager and source pickers refresh."
        % source_label
    )
    if backup_path:
        message += "\n\nBackup saved to: %s" % backup_path
    return message


def _fenlight_label(addon_id):
    return FENLIGHT_ADDON_LABELS.get(addon_id, addon_id)


def _fenlight_settings_db_path(data_path):
    return os.path.join(data_path, FENLIGHT_SETTINGS_DB)


def _fenlight_settings_xml_path(data_path):
    return os.path.join(data_path, FENLIGHT_SETTINGS_XML)


def _fenlight_settings_targets(include_missing=False):
    targets = []
    for addon_id in FENLIGHT_ADDON_IDS:
        data_path = _addon_data_path(addon_id)
        db_path = _fenlight_settings_db_path(data_path)
        if (
            include_missing
            or _addon_installed(addon_id)
            or os.path.exists(db_path)
            or os.path.isdir(data_path)
        ):
            targets.append((addon_id, _fenlight_label(addon_id), data_path))
    return targets


def _prompt_fenlight_settings_target():
    targets = _fenlight_settings_targets()
    if not targets:
        targets = _fenlight_settings_targets(include_missing=True)
    labels = ["%s (%s)" % (target[1], target[0]) for target in targets]
    index = xbmcgui.Dialog().select("Fen Light settings target", labels)
    if index < 0:
        return None
    return targets[index]


def _validate_fenlight_settings_db(db_path):
    if not os.path.exists(db_path):
        raise RuntimeError("Fen Light settings.db was not found.")
    try:
        dbcon = sqlite3.connect(db_path)
        columns = [row[1] for row in dbcon.execute("PRAGMA table_info(settings)").fetchall()]
        count = dbcon.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    except Exception as exc:
        raise RuntimeError("Fen Light settings.db is invalid: %s" % exc)
    finally:
        try:
            dbcon.close()
        except Exception:
            pass
    required = {"setting_id", "setting_type", "setting_default", "setting_value"}
    if not required.issubset(set(columns)):
        raise RuntimeError("Fen Light settings.db is missing required settings columns.")
    if count <= 0:
        raise RuntimeError("Fen Light settings.db does not contain any settings.")
    return count


def _fenlight_settings_backup_dir(addon_id, prefix):
    backup_root = _addon_data_dir(FENLIGHT_SETTINGS_BACKUP_DIR)
    safe_addon_id = addon_id.replace(".", "-")
    backup_dir = os.path.join(backup_root, "%s-%s-%s" % (safe_addon_id, prefix, _utc_timestamp()))
    if not os.path.isdir(backup_dir):
        os.makedirs(backup_dir)
    return backup_dir


def _backup_one_fenlight_settings(addon_id, data_path, prefix):
    db_path = _fenlight_settings_db_path(data_path)
    if not os.path.exists(db_path):
        raise RuntimeError("%s settings.db was not found." % _fenlight_label(addon_id))
    _validate_fenlight_settings_db(db_path)

    backup_dir = _fenlight_settings_backup_dir(addon_id, prefix)
    db_dest = os.path.join(backup_dir, FENLIGHT_SETTINGS_DB)
    xml_path = _fenlight_settings_xml_path(data_path)
    _copy_binary_file(db_path, db_dest)
    if os.path.exists(xml_path):
        _copy_binary_file(xml_path, os.path.join(backup_dir, FENLIGHT_SETTINGS_XML))
    _log("Backed up %s Fen Light settings to %s" % (addon_id, backup_dir))
    return backup_dir


def _backup_current_fenlight_settings():
    backups = []
    for addon_id, label, data_path in _fenlight_settings_targets():
        db_path = _fenlight_settings_db_path(data_path)
        if not os.path.exists(db_path):
            continue
        backups.append((addon_id, label, _backup_one_fenlight_settings(addon_id, data_path, "settings")))
    if not backups:
        raise RuntimeError("No Fen Light settings.db files were found in this Kodi profile.")
    return backups


def _fenlight_settings_preset_has_payload(preset_dir):
    for addon_id in FENLIGHT_ADDON_IDS:
        if os.path.exists(os.path.join(preset_dir, addon_id, FENLIGHT_SETTINGS_DB)):
            return True
    return os.path.exists(os.path.join(preset_dir, FENLIGHT_SETTINGS_DB))


def _fenlight_settings_builtin_presets():
    presets = []
    root_dir = _addon_resource_path(FENLIGHT_SETTINGS_BUILTIN_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _fenlight_settings_preset_has_payload):
        presets.append(
            {
                "origin": "builtin",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
            }
        )
    return presets


def _fenlight_settings_saved_presets():
    presets = []
    root_dir = _addon_data_dir(FENLIGHT_SETTINGS_SAVED_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _fenlight_settings_preset_has_payload):
        presets.append(
            {
                "origin": "saved",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
            }
        )
    return presets


def _fenlight_settings_presets():
    return _fenlight_settings_builtin_presets() + _fenlight_settings_saved_presets()


def _prompt_fenlight_settings_preset():
    return _prompt_preset(_fenlight_settings_presets(), "Fen Light settings preset")


def _fenlight_settings_preset_payloads(preset):
    payloads = []
    preset_dir = preset["dir"]
    for addon_id in FENLIGHT_ADDON_IDS:
        db_path = os.path.join(preset_dir, addon_id, FENLIGHT_SETTINGS_DB)
        if not os.path.exists(db_path):
            continue
        _validate_fenlight_settings_db(db_path)
        xml_path = os.path.join(preset_dir, addon_id, FENLIGHT_SETTINGS_XML)
        payloads.append((addon_id, db_path, xml_path if os.path.exists(xml_path) else ""))

    legacy_db_path = os.path.join(preset_dir, FENLIGHT_SETTINGS_DB)
    if not payloads and os.path.exists(legacy_db_path):
        _validate_fenlight_settings_db(legacy_db_path)
        legacy_xml_path = os.path.join(preset_dir, FENLIGHT_SETTINGS_XML)
        payloads.append(("", legacy_db_path, legacy_xml_path if os.path.exists(legacy_xml_path) else ""))

    if not payloads:
        raise RuntimeError("Fen Light settings preset is missing settings.db.")
    return payloads


def _choose_fenlight_settings_payload(preset, target):
    payloads = _fenlight_settings_preset_payloads(preset)
    target_addon_id = target[0]
    for payload in payloads:
        if payload[0] == target_addon_id:
            return payload
    if len(payloads) == 1:
        return payloads[0]

    labels = ["%s (%s)" % (_fenlight_label(addon_id), addon_id) for addon_id, _db, _xml in payloads]
    index = xbmcgui.Dialog().select("Fen Light preset source", labels)
    if index < 0:
        return None
    return payloads[index]


def _write_fenlight_settings_payload(target, source_db_path, source_xml_path, source_label):
    addon_id, label, data_path = target
    row_count = _validate_fenlight_settings_db(source_db_path)
    db_path = _fenlight_settings_db_path(data_path)
    db_dir = os.path.dirname(db_path)
    if not os.path.isdir(db_dir):
        os.makedirs(db_dir)
    if not os.path.isdir(data_path):
        os.makedirs(data_path)

    backup_path = ""
    if os.path.exists(db_path):
        backup_path = _backup_one_fenlight_settings(addon_id, data_path, "settings-before-restore")

    _copy_binary_file(source_db_path, db_path)
    if source_xml_path and os.path.exists(source_xml_path):
        _copy_binary_file(source_xml_path, _fenlight_settings_xml_path(data_path))

    _log("Restored %s Fen Light settings from %s to %s" % (addon_id, source_label, db_path))
    return {
        "addon_id": addon_id,
        "label": label,
        "db_path": db_path,
        "backup_path": backup_path,
        "row_count": row_count,
    }


def _save_fenlight_settings_preset(addon, preset_name):
    preset_id = _preset_id_from_name(preset_name)
    payloads = []
    for addon_id, label, data_path in _fenlight_settings_targets():
        db_path = _fenlight_settings_db_path(data_path)
        if not os.path.exists(db_path):
            continue
        _validate_fenlight_settings_db(db_path)
        xml_path = _fenlight_settings_xml_path(data_path)
        payloads.append((addon_id, label, db_path, xml_path if os.path.exists(xml_path) else ""))

    if not payloads:
        raise RuntimeError("No Fen Light settings.db files were found in this Kodi profile.")

    roots = (
        (
            "built-in",
            _addon_resource_path(FENLIGHT_SETTINGS_BUILTIN_PRESETS_DIR, preset_id),
        ),
        (
            "saved",
            _addon_data_dir(FENLIGHT_SETTINGS_SAVED_PRESETS_DIR, preset_id),
        ),
    )

    def writer(preset_dir):
        for addon_id, _label, db_path, xml_path in payloads:
            addon_dir = os.path.join(preset_dir, addon_id)
            _copy_binary_file(db_path, os.path.join(addon_dir, FENLIGHT_SETTINGS_DB))
            if xml_path:
                _copy_binary_file(xml_path, os.path.join(addon_dir, FENLIGHT_SETTINGS_XML))

    saved, errors = _save_payload_to_roots(roots, preset_id, preset_name, "fenlightsettings", writer)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_fenlightsettings_preset_save", now)
    _set_setting(addon, "last_install", now)

    message = "Fen Light settings preset saved as %s for: %s." % (
        preset_name,
        ", ".join(label for _addon_id, label, _db_path, _xml_path in payloads),
    )
    message += "\n\nSaved locations: %s" % ", ".join(origin for origin, _path in saved)
    if errors:
        message += "\n\nSome locations were skipped: %s" % "; ".join(errors)
    return message


def _rename_fenlight_settings_preset(addon, preset, new_name):
    _rename_preset(preset, new_name, "fenlightsettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_fenlightsettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "Fen Light settings preset renamed to %s." % new_name


def _delete_fenlight_settings_preset(addon, preset):
    _delete_preset(preset, "fenlightsettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_fenlightsettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "Fen Light settings preset deleted: %s." % preset["name"]


def _confirm_fenlight_settings_restore(source_label, target_label):
    return _yesno(
        "Kodi Setup Kit",
        (
            "Restore Fen Light settings from %s to %s?\n\n"
            "The current settings.db will be backed up first.\n\n"
            "Restart Kodi after restore so Fen Light reloads its settings cache."
        )
        % (source_label, target_label),
        yes_label="Restore",
        no_label="Cancel",
    )


def _restore_fenlight_settings_message(source_label, result):
    message = (
        "Fen Light settings restored from %s to %s. Restart Kodi so Fen Light reloads its settings cache."
        % (source_label, result["label"])
    )
    message += "\n\nSettings rows restored: %s" % result["row_count"]
    if result["backup_path"]:
        message += "\n\nBackup saved to: %s" % result["backup_path"]
    return message


def _a4ksubtitles_label(addon_id):
    return A4KSUBTITLES_ADDON_LABELS.get(addon_id, addon_id)


def _a4ksubtitles_settings_path(data_path):
    return os.path.join(data_path, A4KSUBTITLES_SETTINGS_XML)


def _a4ksubtitles_targets(include_missing=False):
    targets = []
    for addon_id in A4KSUBTITLES_ADDON_IDS:
        data_path = _addon_data_path(addon_id)
        settings_path = _a4ksubtitles_settings_path(data_path)
        if (
            include_missing
            or _addon_installed(addon_id)
            or os.path.exists(settings_path)
            or os.path.isdir(data_path)
        ):
            targets.append((addon_id, _a4ksubtitles_label(addon_id), data_path))
    return targets


def _prompt_a4ksubtitles_target():
    targets = _a4ksubtitles_targets()
    if not targets:
        targets = _a4ksubtitles_targets(include_missing=True)
    labels = ["%s (%s)" % (target[1], target[0]) for target in targets]
    index = xbmcgui.Dialog().select("a4kSubtitles settings target", labels)
    if index < 0:
        return None
    return targets[index]


def _parse_a4ksubtitles_payload(payload):
    try:
        root = ET.fromstring(payload)
    except Exception as exc:
        raise RuntimeError("a4kSubtitles settings XML is invalid: %s" % exc)
    if root.tag != "settings":
        raise RuntimeError("a4kSubtitles settings XML must have a <settings> root.")
    if not root.findall("./setting"):
        raise RuntimeError("a4kSubtitles settings XML does not contain any <setting> entries.")
    return root


def _a4ksubtitles_backup_path(addon_id, prefix):
    backup_dir = _addon_data_dir(A4KSUBTITLES_BACKUP_DIR)
    safe_addon_id = addon_id.replace(".", "-")
    filename = "%s-%s-%s.xml" % (safe_addon_id, prefix, _utc_timestamp())
    return os.path.join(backup_dir, filename)


def _backup_one_a4ksubtitles_settings(addon_id, source_path, prefix):
    if not os.path.exists(source_path):
        raise RuntimeError("%s settings.xml was not found." % _a4ksubtitles_label(addon_id))
    with io.open(source_path, "rb") as handle:
        _parse_a4ksubtitles_payload(handle.read())
    target_path = _a4ksubtitles_backup_path(addon_id, prefix)
    _copy_binary_file(source_path, target_path)
    _log("Backed up %s a4kSubtitles settings to %s" % (addon_id, target_path))
    return target_path


def _backup_current_a4ksubtitles_settings():
    backups = []
    for addon_id, label, data_path in _a4ksubtitles_targets():
        source_path = _a4ksubtitles_settings_path(data_path)
        if not os.path.exists(source_path):
            continue
        backups.append((addon_id, label, _backup_one_a4ksubtitles_settings(addon_id, source_path, "settings")))
    if not backups:
        raise RuntimeError("No a4kSubtitles settings.xml files were found in this Kodi profile.")
    return backups


def _a4ksubtitles_preset_has_payload(preset_dir):
    for addon_id in A4KSUBTITLES_ADDON_IDS:
        if os.path.exists(os.path.join(preset_dir, addon_id, A4KSUBTITLES_SETTINGS_XML)):
            return True
    return os.path.exists(os.path.join(preset_dir, A4KSUBTITLES_SETTINGS_XML))


def _a4ksubtitles_builtin_presets():
    presets = []
    root_dir = _addon_resource_path(A4KSUBTITLES_BUILTIN_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _a4ksubtitles_preset_has_payload):
        presets.append(
            {
                "origin": "builtin",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
            }
        )
    return presets


def _a4ksubtitles_saved_presets():
    presets = []
    root_dir = _addon_data_dir(A4KSUBTITLES_SAVED_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _a4ksubtitles_preset_has_payload):
        presets.append(
            {
                "origin": "saved",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
            }
        )
    return presets


def _a4ksubtitles_presets():
    return _a4ksubtitles_builtin_presets() + _a4ksubtitles_saved_presets()


def _prompt_a4ksubtitles_preset():
    return _prompt_preset(_a4ksubtitles_presets(), "a4kSubtitles settings preset")


def _a4ksubtitles_preset_payloads(preset):
    payloads = []
    preset_dir = preset["dir"]
    for addon_id in A4KSUBTITLES_ADDON_IDS:
        settings_path = os.path.join(preset_dir, addon_id, A4KSUBTITLES_SETTINGS_XML)
        if not os.path.exists(settings_path):
            continue
        with io.open(settings_path, "rb") as handle:
            _parse_a4ksubtitles_payload(handle.read())
        payloads.append((addon_id, settings_path))

    legacy_path = os.path.join(preset_dir, A4KSUBTITLES_SETTINGS_XML)
    if not payloads and os.path.exists(legacy_path):
        with io.open(legacy_path, "rb") as handle:
            _parse_a4ksubtitles_payload(handle.read())
        payloads.append(("", legacy_path))

    if not payloads:
        raise RuntimeError("a4kSubtitles settings preset is missing settings.xml.")
    return payloads


def _choose_a4ksubtitles_payload(preset, target):
    payloads = _a4ksubtitles_preset_payloads(preset)
    target_addon_id = target[0]
    for payload in payloads:
        if payload[0] == target_addon_id:
            return payload
    if len(payloads) == 1:
        return payloads[0]

    labels = ["%s (%s)" % (_a4ksubtitles_label(addon_id), addon_id) for addon_id, _path in payloads]
    index = xbmcgui.Dialog().select("a4kSubtitles preset source", labels)
    if index < 0:
        return None
    return payloads[index]


def _apply_a4ksubtitles_settings_live(addon_id, root):
    try:
        subtitle_addon = xbmcaddon.Addon(addon_id)
    except Exception:
        return 0, 0

    applied = 0
    failed = 0
    for node in root.findall("./setting"):
        setting_id = node.get("id")
        if not setting_id:
            continue
        value = node.text if node.text is not None else ""
        try:
            _set_setting(subtitle_addon, setting_id, value)
            applied += 1
        except Exception:
            failed += 1
    return applied, failed


def _write_a4ksubtitles_payload(target, source_path, source_label):
    addon_id, label, data_path = target
    with io.open(source_path, "rb") as handle:
        payload = handle.read()
    root = _parse_a4ksubtitles_payload(payload)
    if not os.path.isdir(data_path):
        os.makedirs(data_path)

    settings_path = _a4ksubtitles_settings_path(data_path)
    backup_path = ""
    if os.path.exists(settings_path):
        backup_path = _backup_one_a4ksubtitles_settings(addon_id, settings_path, "settings-before-restore")

    applied, failed = _apply_a4ksubtitles_settings_live(addon_id, root)
    _write_binary_payload(settings_path, payload)
    _clear_a4ksubtitles_tokens(data_path)

    _log("Restored %s a4kSubtitles settings from %s to %s" % (addon_id, source_label, settings_path))
    return {
        "addon_id": addon_id,
        "label": label,
        "settings_path": settings_path,
        "backup_path": backup_path,
        "applied": applied,
        "failed": failed,
        "row_count": len(root.findall("./setting")),
    }


def _save_a4ksubtitles_preset(addon, preset_name):
    preset_id = _preset_id_from_name(preset_name)
    payloads = []
    for addon_id, label, data_path in _a4ksubtitles_targets():
        settings_path = _a4ksubtitles_settings_path(data_path)
        if not os.path.exists(settings_path):
            continue
        with io.open(settings_path, "rb") as handle:
            _parse_a4ksubtitles_payload(handle.read())
        payloads.append((addon_id, label, settings_path))

    if not payloads:
        raise RuntimeError("No a4kSubtitles settings.xml files were found in this Kodi profile.")

    roots = (
        (
            "built-in",
            _addon_resource_path(A4KSUBTITLES_BUILTIN_PRESETS_DIR, preset_id),
        ),
        (
            "saved",
            _addon_data_dir(A4KSUBTITLES_SAVED_PRESETS_DIR, preset_id),
        ),
    )

    def writer(preset_dir):
        for addon_id, _label, settings_path in payloads:
            _copy_binary_file(
                settings_path,
                os.path.join(preset_dir, addon_id, A4KSUBTITLES_SETTINGS_XML),
            )

    saved, errors = _save_payload_to_roots(roots, preset_id, preset_name, "a4ksubtitlessettings", writer)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_a4ksubtitlessettings_preset_save", now)
    _set_setting(addon, "last_install", now)

    message = "a4kSubtitles settings preset saved as %s for: %s." % (
        preset_name,
        ", ".join(label for _addon_id, label, _settings_path in payloads),
    )
    message += "\n\nSaved locations: %s" % ", ".join(origin for origin, _path in saved)
    if errors:
        message += "\n\nSome locations were skipped: %s" % "; ".join(errors)
    return message


def _rename_a4ksubtitles_preset(addon, preset, new_name):
    _rename_preset(preset, new_name, "a4ksubtitlessettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_a4ksubtitlessettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "a4kSubtitles settings preset renamed to %s." % new_name


def _delete_a4ksubtitles_preset(addon, preset):
    _delete_preset(preset, "a4ksubtitlessettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_a4ksubtitlessettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "a4kSubtitles settings preset deleted: %s." % preset["name"]


def _confirm_a4ksubtitles_restore(source_label, target_label):
    return _yesno(
        "Kodi Setup Kit",
        (
            "Restore a4kSubtitles settings from %s to %s?\n\n"
            "The current settings.xml will be backed up first.\n\n"
            "Cached OpenSubtitles tokens will be cleared."
        )
        % (source_label, target_label),
        yes_label="Restore",
        no_label="Cancel",
    )


def _restore_a4ksubtitles_message(source_label, result):
    message = "a4kSubtitles settings restored from %s to %s." % (
        source_label,
        result["label"],
    )
    message += "\n\nSettings restored: %s" % result["row_count"]
    message += "\nLive settings applied: %s" % result["applied"]
    if result["failed"]:
        message += " (%s could not be applied live)." % result["failed"]
    if result["backup_path"]:
        message += "\n\nBackup saved to: %s" % result["backup_path"]
    return message


def _skin_settings_path(data_path):
    return os.path.join(data_path, "settings.xml")


def _skin_settings_targets(include_missing=False):
    targets = []
    for addon_id, label, builtin_id in SKIN_SETTINGS_ADDONS:
        data_path = _addon_data_path(addon_id)
        settings_path = _skin_settings_path(data_path)
        if (
            include_missing
            or _addon_installed(addon_id)
            or os.path.exists(settings_path)
            or os.path.isdir(data_path)
        ):
            targets.append((addon_id, label, builtin_id, data_path))
    return targets


def _skin_settings_target_by_addon_id(addon_id):
    for target in _skin_settings_targets(include_missing=True):
        if target[0] == addon_id:
            return target
    return None


def _parse_skin_settings_payload(payload):
    try:
        root = ET.fromstring(payload)
    except Exception as exc:
        raise RuntimeError("Skin settings XML is invalid: %s" % exc)
    if root.tag != "settings":
        raise RuntimeError("Skin settings XML must have a <settings> root.")
    if not root.findall("./setting"):
        raise RuntimeError("Skin settings XML does not contain any <setting> entries.")
    return root


def _skin_settings_backup_path(addon_id, prefix):
    backup_dir = _addon_data_dir(SKIN_SETTINGS_BACKUP_DIR)
    filename = "%s-%s-%s.xml" % (addon_id, prefix, _utc_timestamp())
    return os.path.join(backup_dir, filename)


def _backup_one_skin_settings(addon_id, source_path, prefix):
    target_path = _skin_settings_backup_path(addon_id, prefix)
    _copy_binary_file(source_path, target_path)
    _log("Backed up %s skin settings to %s" % (addon_id, target_path))
    return target_path


def _backup_current_skin_settings():
    backups = []
    for addon_id, label, _builtin_id, data_path in _skin_settings_targets():
        source_path = _skin_settings_path(data_path)
        if not os.path.exists(source_path):
            continue
        backup_path = _backup_one_skin_settings(addon_id, source_path, "settings")
        backups.append((addon_id, label, backup_path))
    if not backups:
        raise RuntimeError(
            "No supported skin settings were found. Install or open DutchTech Fuse 3 or Arctic Horizon 2 first."
        )
    return backups


def _read_skin_settings_payload(source_path, addon_id):
    if not os.path.exists(source_path):
        raise RuntimeError("Skin settings preset is missing settings.xml for %s." % addon_id)
    with io.open(source_path, "rb") as handle:
        payload = handle.read()
    _parse_skin_settings_payload(payload)
    return payload


def _apply_skin_settings_live(addon_id, root):
    try:
        skin = xbmcaddon.Addon(addon_id)
    except Exception:
        return 0, 0

    applied = 0
    failed = 0
    for node in root.findall("./setting"):
        setting_id = node.get("id")
        if not setting_id:
            continue
        value = node.text if node.text is not None else ""
        try:
            _set_setting(skin, setting_id, value)
            applied += 1
        except Exception:
            failed += 1
    return applied, failed


def _write_skin_settings_payload(target, payload, source_label):
    addon_id, label, _builtin_id, data_path = target
    root = _parse_skin_settings_payload(payload)
    if not os.path.isdir(data_path):
        os.makedirs(data_path)

    settings_path = _skin_settings_path(data_path)
    backup_path = ""
    if os.path.exists(settings_path):
        backup_path = _backup_one_skin_settings(
            addon_id, settings_path, "settings-before-restore"
        )

    applied, failed = _apply_skin_settings_live(addon_id, root)

    tmp_path = settings_path + ".tmp"
    with io.open(tmp_path, "wb") as handle:
        handle.write(payload)
    if os.path.exists(settings_path):
        os.remove(settings_path)
    os.rename(tmp_path, settings_path)

    _log("Restored %s skin settings from %s to %s" % (addon_id, source_label, settings_path))
    return {
        "addon_id": addon_id,
        "label": label,
        "settings_path": settings_path,
        "backup_path": backup_path,
        "applied": applied,
        "failed": failed,
    }


def _prompt_skin_settings_target():
    targets = _skin_settings_targets()
    if not targets:
        targets = _skin_settings_targets(include_missing=True)
    labels = ["%s (%s)" % (target[1], target[0]) for target in targets]
    index = xbmcgui.Dialog().select("Skin settings target", labels)
    if index < 0:
        return None
    return targets[index]


def _download_skin_settings_payload(url):
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError("Enter a valid http or https URL.")

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/zip,application/xml,text/xml,*/*",
            "User-Agent": "Kodi Setup Kit Kodi add-on",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read(SKIN_SETTINGS_DOWNLOAD_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Could not download skin settings: HTTP %s" % exc.code)
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not download skin settings: %s" % exc.reason)

    if len(payload) > SKIN_SETTINGS_DOWNLOAD_MAX_BYTES:
        raise RuntimeError("Skin settings download is too large.")
    return payload


def _skin_settings_payloads_from_zip(payload):
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        raise RuntimeError("Skin settings ZIP is invalid.")

    items = []
    seen = set()
    try:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            parts = [part for part in name.split("/") if part]
            if not parts or parts[-1] != "settings.xml":
                continue
            if any(part == "__MACOSX" or part.startswith("._") for part in parts):
                continue
            if info.file_size > SKIN_SETTINGS_DOWNLOAD_MAX_BYTES:
                raise RuntimeError("A skin settings XML inside the ZIP is too large.")

            matched_addon_id = ""
            for addon_id, _label, _builtin_id in SKIN_SETTINGS_ADDONS:
                if addon_id in parts:
                    matched_addon_id = addon_id
                    break
            if not matched_addon_id or matched_addon_id in seen:
                continue

            item_payload = archive.read(info)
            _parse_skin_settings_payload(item_payload)
            target = _skin_settings_target_by_addon_id(matched_addon_id)
            if target is None:
                continue
            items.append((target, item_payload, name))
            seen.add(matched_addon_id)
    finally:
        archive.close()

    if not items:
        raise RuntimeError(
            "No supported skin settings were found in the ZIP. Use paths like skin.dutchtech.fuse.3/settings.xml."
        )
    return items


def _skin_settings_payload_items_from_url(url):
    payload = _download_skin_settings_payload(url)
    if zipfile.is_zipfile(io.BytesIO(payload)):
        return _skin_settings_payloads_from_zip(payload), "ZIP URL"

    _parse_skin_settings_payload(payload)
    target = _prompt_skin_settings_target()
    if target is None:
        raise RuntimeError("Skin settings restore was canceled.")
    return [(target, payload, url)], "XML URL"


def _prompt_skin_settings_url():
    return xbmcgui.Dialog().input(
        "Skin settings URL",
        type=getattr(xbmcgui, "INPUT_ALPHANUM", 0),
    )


def _confirm_skin_settings_restore(source_label):
    return _yesno(
        "Kodi Setup Kit",
        (
            "Restore skin settings from %s?\n\n"
            "DutchTech Fuse 3 / Arctic Horizon 2 settings will be backed up first.\n\n"
            "Restart Kodi or reload the skin after restore."
        )
        % source_label,
        yes_label="Restore",
        no_label="Cancel",
    )


def _restore_skin_settings_message(source_label, results):
    labels = [result["label"] for result in results]
    applied = sum(result["applied"] for result in results)
    failed = sum(result["failed"] for result in results)
    backups = [result["backup_path"] for result in results if result["backup_path"]]

    message = (
        "Skin settings restored from %s for: %s. Restart Kodi or reload the skin."
        % (source_label, ", ".join(labels))
    )
    if backups:
        message += "\n\nBackups saved: %s" % len(backups)
    message += "\n\nLive settings applied: %s" % applied
    if failed:
        message += " (%s could not be applied live)." % failed
    return message


def _skin_settings_preset_has_payload(preset_dir):
    for addon_id, _label, _builtin_id in SKIN_SETTINGS_ADDONS:
        if os.path.exists(os.path.join(preset_dir, addon_id, "settings.xml")):
            return True
    return False


def _skin_settings_legacy_builtin_has_payload(preset_dir):
    return any(
        os.path.exists(os.path.join(preset_dir, builtin_id, "settings.xml"))
        for _addon_id, _label, builtin_id in SKIN_SETTINGS_ADDONS
    )


def _skin_settings_builtin_presets():
    presets = []
    root_dir = _addon_resource_path(SKIN_SETTINGS_BUILTIN_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _skin_settings_preset_has_payload):
        presets.append(
            {
                "origin": "builtin",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
            }
        )

    legacy_dir = _addon_resource_path(SKIN_SETTINGS_SOURCE_DIR)
    if not presets and os.path.isdir(legacy_dir) and _skin_settings_legacy_builtin_has_payload(legacy_dir):
        presets.append(
            {
                "origin": "builtin",
                "id": "built-in",
                "name": "Built-in",
                "dir": legacy_dir,
            }
        )
    return presets


def _skin_settings_saved_presets():
    presets = []
    root_dir = _addon_data_dir(SKIN_SETTINGS_SAVED_PRESETS_DIR)
    for preset_id, preset_dir, preset_name in _preset_dirs(root_dir, _skin_settings_preset_has_payload):
        presets.append(
            {
                "origin": "saved",
                "id": preset_id,
                "name": preset_name,
                "dir": preset_dir,
            }
        )
    return presets


def _skin_settings_presets():
    return _skin_settings_builtin_presets() + _skin_settings_saved_presets()


def _prompt_skin_settings_preset():
    return _prompt_preset(_skin_settings_presets(), "Skin settings preset")


def _skin_settings_preset_payload_path(preset, builtin_id):
    return os.path.join(preset["dir"], builtin_id, "settings.xml")


def _restore_skin_settings_preset(addon, preset):
    targets = _skin_settings_targets()
    if not targets:
        target = _prompt_skin_settings_target()
        if target is None:
            raise RuntimeError("Skin settings restore was canceled.")
        targets = [target]

    results = []
    for target in targets:
        builtin_id = target[2]
        source_path = _skin_settings_preset_payload_path(preset, builtin_id)
        if not os.path.exists(source_path):
            continue
        payload = _read_skin_settings_payload(source_path, builtin_id)
        results.append(_write_skin_settings_payload(target, payload, _preset_label(preset)))

    if not results:
        raise RuntimeError("The selected skin settings preset does not match any supported installed skin.")

    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_skinsettings_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_skin_settings_message(_preset_label(preset), results)


def _save_skin_settings_preset(addon, preset_name):
    preset_id = _preset_id_from_name(preset_name)
    payloads = []
    seen = set()
    for addon_id, label, builtin_id, data_path in _skin_settings_targets():
        if builtin_id in seen:
            continue
        source_path = _skin_settings_path(data_path)
        if not os.path.exists(source_path):
            continue
        with io.open(source_path, "rb") as handle:
            payload = handle.read()
        _parse_skin_settings_payload(payload)
        payloads.append((builtin_id, label, payload))
        seen.add(builtin_id)

    if not payloads:
        raise RuntimeError("No supported skin settings were found in this Kodi profile.")

    roots = (
        (
            "built-in",
            _addon_resource_path(SKIN_SETTINGS_BUILTIN_PRESETS_DIR, preset_id),
        ),
        (
            "saved",
            _addon_data_dir(SKIN_SETTINGS_SAVED_PRESETS_DIR, preset_id),
        ),
    )

    def writer(preset_dir):
        for builtin_id, _label, payload in payloads:
            _write_binary_payload(os.path.join(preset_dir, builtin_id, "settings.xml"), payload)

    saved, errors = _save_payload_to_roots(roots, preset_id, preset_name, "skinsettings", writer)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_skinsettings_preset_save", now)
    _set_setting(addon, "last_install", now)

    message = "Skin settings preset saved as %s for: %s." % (
        preset_name,
        ", ".join(label for _builtin_id, label, _payload in payloads),
    )
    message += "\n\nSaved locations: %s" % ", ".join(origin for origin, _path in saved)
    if errors:
        message += "\n\nSome locations were skipped: %s" % "; ".join(errors)
    return message


def _rename_skin_settings_preset(addon, preset, new_name):
    _rename_preset(preset, new_name, "skinsettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_skinsettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "Skin settings preset renamed to %s." % new_name


def _delete_skin_settings_preset(addon, preset):
    _delete_preset(preset, "skinsettings")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_skinsettings_preset_manage", now)
    _set_setting(addon, "last_install", now)
    return "Skin settings preset deleted: %s." % preset["name"]


def _restore_skin_settings_from_url(addon, url):
    items, source_label = _skin_settings_payload_items_from_url(url)
    results = []
    for target, payload, item_label in items:
        results.append(_write_skin_settings_payload(target, payload, item_label))

    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_skinsettings_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_skin_settings_message(source_label, results)


def _write_kodi_settings_xml(data_path, values):
    if not os.path.isdir(data_path):
        os.makedirs(data_path)

    settings_path = os.path.join(data_path, "settings.xml")
    if os.path.exists(settings_path):
        try:
            tree = ET.parse(settings_path)
            root = tree.getroot()
        except Exception:
            root = ET.Element("settings", {"version": "2"})
            tree = ET.ElementTree(root)
    else:
        root = ET.Element("settings", {"version": "2"})
        tree = ET.ElementTree(root)

    if root.tag != "settings":
        root = ET.Element("settings", {"version": "2"})
        tree = ET.ElementTree(root)
    if not root.get("version"):
        root.set("version", "2")

    for key, value in values.items():
        node = root.find("./setting[@id='%s']" % key)
        if node is None:
            node = ET.SubElement(root, "setting", {"id": key})
        node.text = str(value)

    _indent_xml(root)
    tmp_path = settings_path + ".tmp"
    tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
    if os.path.exists(settings_path):
        os.remove(settings_path)
    os.rename(tmp_path, settings_path)
    return settings_path


def _write_a4ksubtitles_settings(addon_id, data_path, values):
    try:
        subtitle_addon = xbmcaddon.Addon(addon_id)
        for key, value in values.items():
            _set_setting(subtitle_addon, key, str(value))
        _log("Installed a4kSubtitles settings for %s via Kodi settings API" % addon_id)
    except Exception:
        settings_path = _write_kodi_settings_xml(data_path, values)
        _log("Installed a4kSubtitles settings for %s at %s" % (addon_id, settings_path))


def _clear_a4ksubtitles_tokens(data_path):
    tokens_path = os.path.join(data_path, "tokens_cache.json")
    if not os.path.exists(tokens_path):
        return

    try:
        with io.open(tokens_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or "opensubtitles" not in data:
            return
        data.pop("opensubtitles", None)
        tmp_path = tokens_path + ".tmp"
        with io.open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=4, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, tokens_path)
        _log("Cleared cached OpenSubtitles token for a4kSubtitles")
    except Exception as exc:
        _log("Could not clear a4kSubtitles token cache: %s" % exc, xbmc.LOGWARNING)


def _clean_undesirable_keyword(keyword):
    return keyword.strip().replace(" ", "")


def _clean_undesirable_keywords(keywords):
    cleaned = []
    seen = set()
    for keyword in keywords:
        keyword = _clean_undesirable_keyword(keyword)
        if not keyword or keyword in seen:
            continue
        cleaned.append(keyword)
        seen.add(keyword)
    return cleaned


def _load_cocoscrapers_default_undesirables(addon_id):
    addon_path = _addon_install_path(addon_id)
    if not addon_path:
        return []

    source_path = os.path.join(
        addon_path,
        "lib",
        "cocoscrapers",
        "modules",
        "source_utils.py",
    )
    if not os.path.exists(source_path):
        return []

    try:
        with io.open(source_path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=source_path)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "UNDESIRABLES":
                    return _clean_undesirable_keywords(ast.literal_eval(node.value))
    except Exception as exc:
        _log("Could not read Cocoscrapers default undesirables: %s" % exc, xbmc.LOGWARNING)
    return []


def _write_cocoscrapers_settings(addon_id, data_path):
    values = {"filter.undesirables": "true"}
    try:
        cocoscrapers = xbmcaddon.Addon(addon_id)
        for key, value in values.items():
            _set_setting(cocoscrapers, key, value)
        _log("Enabled Cocoscrapers undesirable filter for %s via Kodi settings API" % addon_id)
    except Exception:
        settings_path = _write_kodi_settings_xml(data_path, values)
        _log("Enabled Cocoscrapers undesirable filter for %s at %s" % (addon_id, settings_path))


def _write_cocoscrapers_undesirables(addon_id, data_path):
    if not os.path.isdir(data_path):
        os.makedirs(data_path)

    default_keywords = _load_cocoscrapers_default_undesirables(addon_id)
    disabled_defaults = set(_clean_undesirable_keywords(COCOSCRAPERS_DISABLED_DEFAULT_UNDESIRABLES))
    user_keywords = _clean_undesirable_keywords(COCOSCRAPERS_USER_UNDESIRABLES)
    db_path = os.path.join(data_path, "undesirables.db")

    rows = []
    for keyword in default_keywords:
        rows.append((keyword, False, keyword not in disabled_defaults))
    for keyword in user_keywords:
        rows.append((keyword, True, True))
    desired_user_keywords = set(user_keywords)

    connection = sqlite3.connect(db_path, timeout=10)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS undesirables "
            "(keyword TEXT NOT NULL, user_defined BOOL NOT NULL, "
            "enabled BOOL NOT NULL, UNIQUE(keyword))"
        )
        connection.executemany(
            "INSERT OR REPLACE INTO undesirables "
            "(keyword, user_defined, enabled) VALUES (?, ?, ?)",
            rows,
        )
        dirty_rows = []
        for (keyword,) in connection.execute("SELECT keyword FROM undesirables"):
            cleaned = _clean_undesirable_keyword(keyword)
            if not cleaned:
                dirty_rows.append((keyword,))
            elif cleaned in desired_user_keywords and cleaned != keyword:
                dirty_rows.append((keyword,))
        if dirty_rows:
            connection.executemany("DELETE FROM undesirables WHERE keyword = ?", dirty_rows)
        connection.commit()
    finally:
        connection.close()

    _log(
        "Installed %s default and %s user Cocoscrapers undesirables for %s at %s"
        % (len(default_keywords), len(user_keywords), addon_id, db_path)
    )
    return db_path


def _install_youtube(addon, bridge_data):
    keys = _extract_youtube_keys(bridge_data)
    api_keys_path = _write_api_keys(keys)
    updated_settings = _update_youtube_settings(keys)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_youtube_install", now)
    _set_setting(addon, "last_install", now)
    _log("Installed YouTube API credentials at %s" % api_keys_path)

    if updated_settings:
        return "YouTube credentials installed."
    return "YouTube credentials saved. Install YouTube later to use them."


def _install_torbox(addon, bridge_data):
    api_key = _extract_torbox_key(bridge_data)
    aiostreams_manifest_url = _extract_torbox_aiostreams_manifest(bridge_data)
    candidates = _candidate_fenlight_addons()
    if not candidates:
        raise RuntimeError("Fen Light was not found in this Kodi profile.")

    updated = []
    for addon_id, data_path in candidates:
        _write_fenlight_torbox_setting(addon_id, data_path, api_key, aiostreams_manifest_url)
        updated.append(addon_id)

    _set_fenlight_window_cache(api_key, aiostreams_manifest_url)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_torbox_install", now)
    _set_setting(addon, "last_install", now)
    if aiostreams_manifest_url:
        return "TorBox API key and AIOStreams manifest installed for: %s." % ", ".join(updated)
    return "TorBox API key installed for: %s." % ", ".join(updated)


def _install_a4ksubtitles(addon, bridge_data):
    values = _extract_a4ksubtitles_settings(bridge_data)
    candidates = _candidate_a4ksubtitles_addons()
    if not candidates:
        raise RuntimeError("a4kSubtitles Patched was not found in this Kodi profile.")

    updated = []
    for addon_id, data_path in candidates:
        _write_a4ksubtitles_settings(addon_id, data_path, values)
        _clear_a4ksubtitles_tokens(data_path)
        updated.append(addon_id)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_a4ksubtitles_install", now)
    _set_setting(addon, "last_install", now)
    return "a4kSubtitles settings installed for: %s." % ", ".join(updated)


def _install_cocoscrapers(addon):
    candidates = _candidate_cocoscrapers_addons()
    if not candidates:
        raise RuntimeError("Cocoscrapers was not found in this Kodi profile.")

    updated = []
    for addon_id, data_path in candidates:
        _write_cocoscrapers_settings(addon_id, data_path)
        _write_cocoscrapers_undesirables(addon_id, data_path)
        updated.append(addon_id)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_cocoscrapers_install", now)
    _set_setting(addon, "last_install", now)
    return "Cocoscrapers filters installed for: %s." % ", ".join(updated)


def _install_advanced_network_settings(addon):
    advancedsettings_path, backup_path = _write_advanced_network_settings()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_advanced_network_install", now)
    _set_setting(addon, "last_install", now)

    message = (
        "Kodi network advanced settings installed. "
        "Restart Kodi for disablehttp2 and disableipv6 to take effect."
    )
    if backup_path:
        message += " Existing invalid advancedsettings.xml was backed up."
    return message


def _install_keymaps(addon):
    installed, backups = _install_keymap_files()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_keymaps_install", now)
    _set_setting(addon, "last_install", now)

    message = (
        "Kodi keymaps installed: %s. Restart Kodi for the keymaps to take effect."
        % ", ".join(installed)
    )
    if backups:
        message += " Existing matching keymap files were backed up."
    return message


def _empty_cleanup_result():
    return {"files": 0, "dirs": 0, "bytes": 0, "errors": []}


def _merge_cleanup_result(target, source):
    target["files"] += source.get("files", 0)
    target["dirs"] += source.get("dirs", 0)
    target["bytes"] += source.get("bytes", 0)
    target["errors"].extend(source.get("errors", []))
    return target


def _path_stats(path):
    stats = _empty_cleanup_result()
    if not os.path.lexists(path):
        return stats

    if os.path.isfile(path) or os.path.islink(path):
        stats["files"] = 1
        try:
            stats["bytes"] = os.path.getsize(path)
        except Exception:
            stats["bytes"] = 0
        return stats

    if os.path.isdir(path):
        stats["dirs"] = 1
        for root, dirs, files in os.walk(path):
            stats["dirs"] += len(dirs)
            for filename in files:
                file_path = os.path.join(root, filename)
                stats["files"] += 1
                try:
                    stats["bytes"] += os.path.getsize(file_path)
                except Exception:
                    pass
    return stats


def _delete_path(path, result):
    stats = _path_stats(path)
    if not stats["files"] and not stats["dirs"]:
        return result
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        _merge_cleanup_result(result, stats)
    except Exception as exc:
        result["errors"].append("%s: %s" % (path, exc))
    return result


def _delete_directory_contents(path):
    result = _empty_cleanup_result()
    if not os.path.isdir(path):
        return result
    for name in sorted(os.listdir(path)):
        _delete_path(os.path.join(path, name), result)
    return result


def _delete_matching_children(path, predicate):
    result = _empty_cleanup_result()
    if not os.path.isdir(path):
        return result
    for name in sorted(os.listdir(path)):
        if predicate(name):
            _delete_path(os.path.join(path, name), result)
    return result


def _directory_contents_stats(path):
    result = _empty_cleanup_result()
    if not os.path.isdir(path):
        return result
    for name in sorted(os.listdir(path)):
        _merge_cleanup_result(result, _path_stats(os.path.join(path, name)))
    return result


def _matching_children_stats(path, predicate):
    result = _empty_cleanup_result()
    if not os.path.isdir(path):
        return result
    for name in sorted(os.listdir(path)):
        if predicate(name):
            _merge_cleanup_result(result, _path_stats(os.path.join(path, name)))
    return result


def _format_bytes(size):
    size = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            if unit == "B":
                return "%d %s" % (int(size), unit)
            return "%.1f %s" % (size, unit)
        size /= 1024.0
    return "%.1f GB" % size


def _format_cleanup_result(result):
    message = "Deleted %s file(s), %s folder(s), %s." % (
        result["files"],
        result["dirs"],
        _format_bytes(result["bytes"]),
    )
    if result["errors"]:
        message += "\n\nCould not delete:\n%s" % "\n".join(result["errors"][:8])
        if len(result["errors"]) > 8:
            message += "\n...and %s more." % (len(result["errors"]) - 8)
    return message


def _is_textures_database_name(name):
    return name.startswith("Textures") and ".db" in name


def _is_setup_backup_name(name):
    return ".famyt-backup-" in name


def _confirm_clear_thumbnail_cache():
    return _yesno(
        "Kodi Setup Kit",
        (
            "Clear Kodi thumbnail cache?\n\n"
            "This deletes cached artwork in Thumbnails and Textures*.db.\n\n"
            "Kodi will rebuild artwork afterward. Restart Kodi when this finishes."
        ),
        yes_label="Clear",
        no_label="Cancel",
    )


def _confirm_clear_package_cache():
    return _yesno(
        "Kodi Setup Kit",
        (
            "Clear Kodi add-on package cache?\n\n"
            "This deletes cached add-on ZIP downloads from addons/packages.\n\n"
            "Installed add-ons are not removed."
        ),
        yes_label="Clear",
        no_label="Cancel",
    )


def _confirm_clean_setup_backups():
    return _yesno(
        "Kodi Setup Kit",
        (
            "Clean Setup Kit backups?\n\n"
            "This deletes backups created by Kodi Setup Kit.\n\n"
            "Current Kodi settings and saved presets are not removed."
        ),
        yes_label="Clean",
        no_label="Cancel",
    )


def _clear_thumbnail_cache(addon):
    result = _delete_directory_contents(_translate_path(THUMBNAILS_PATH))
    textures_result = _delete_matching_children(
        _translate_path(TEXTURES_DATABASE_DIR),
        _is_textures_database_name,
    )
    _merge_cleanup_result(result, textures_result)
    _set_timestamp(addon, "last_thumbnail_clear", True)
    return "Thumbnail cache cleared.\n%s\n\nRestart Kodi so the texture database is rebuilt cleanly." % (
        _format_cleanup_result(result)
    )


def _clear_package_cache(addon):
    result = _delete_directory_contents(_translate_path(PACKAGES_CACHE_PATH))
    _set_timestamp(addon, "last_package_cache_clear", True)
    return "Add-on package cache cleared.\n%s" % _format_cleanup_result(result)


def _clean_setup_backups(addon):
    result = _empty_cleanup_result()
    backup_dir = _addon_data_path("backups")
    _delete_path(backup_dir, result)
    _merge_cleanup_result(
        result,
        _delete_matching_children(_translate_path("special://profile"), _is_setup_backup_name),
    )
    _merge_cleanup_result(
        result,
        _delete_matching_children(_translate_path(KEYMAPS_TARGET_PATH), _is_setup_backup_name),
    )
    _set_timestamp(addon, "last_backup_cleanup", True)
    return "Setup Kit backups cleaned.\n%s" % _format_cleanup_result(result)


def _reload_skin(addon):
    xbmc.executebuiltin("ReloadSkin()")
    _set_timestamp(addon, "last_skin_reload", True)
    return "Skin reload requested."


def _restart_kodi(addon):
    _set_timestamp(addon, "last_restart_request", True)
    xbmc.executebuiltin("RestartApp")
    return "Kodi restart requested."


def _advanced_network_status():
    path = _translate_path(ADVANCEDSETTINGS_PATH)
    if not os.path.exists(path):
        return "missing"
    try:
        root = _parse_xml(path).getroot()
        network = _direct_child(root, "network")
        if network is None:
            return "present, network settings missing"
        disablehttp2_node = _direct_child(network, "disablehttp2")
        disableipv6_node = _direct_child(network, "disableipv6")
        disablehttp2 = (
            (disablehttp2_node.text if disablehttp2_node is not None else "") or ""
        ).strip().lower()
        disableipv6 = (
            (disableipv6_node.text if disableipv6_node is not None else "") or ""
        ).strip().lower()
        if disablehttp2 == "true" and disableipv6 == "true":
            return "installed"
        return "present, values differ"
    except Exception as exc:
        return "invalid: %s" % exc


def _bundled_keymaps_status():
    try:
        source_files = _keymap_source_files()
    except Exception as exc:
        return "bundle unavailable: %s" % exc
    target_dir = _translate_path(KEYMAPS_TARGET_PATH)
    installed = 0
    stale = []
    for name, source_path in source_files:
        with io.open(source_path, "rb") as handle:
            payload = handle.read()
        target_path = os.path.join(target_dir, name)
        if _same_file_bytes(target_path, payload):
            installed += 1
        else:
            stale.append(name)
    status = "%s/%s bundled keymap(s) installed" % (installed, len(source_files))
    if stale:
        status += "; missing or outdated: %s" % ", ".join(stale)
    return status


def _sources_status():
    path = _sources_path()
    if not os.path.exists(path):
        return "missing"
    try:
        with io.open(path, "rb") as handle:
            payload = handle.read()
        root = _parse_sources_payload(payload)
        return "present, %s source(s)" % len(root.findall(".//source"))
    except Exception as exc:
        return "invalid: %s" % exc


def _fenlight_settings_status():
    statuses = []
    for addon_id, label, data_path in _fenlight_settings_targets():
        db_path = _fenlight_settings_db_path(data_path)
        if not os.path.exists(db_path):
            statuses.append("%s: missing" % label)
            continue
        try:
            row_count = _validate_fenlight_settings_db(db_path)
            statuses.append("%s: %s row(s)" % (label, row_count))
        except Exception as exc:
            statuses.append("%s: invalid: %s" % (label, exc))
    if not statuses:
        return "no Fen Light variants found"
    return "; ".join(statuses)


def _a4ksubtitles_settings_status():
    statuses = []
    for addon_id, label, data_path in _a4ksubtitles_targets():
        settings_path = _a4ksubtitles_settings_path(data_path)
        if not os.path.exists(settings_path):
            statuses.append("%s: missing" % label)
            continue
        try:
            with io.open(settings_path, "rb") as handle:
                root = _parse_a4ksubtitles_payload(handle.read())
            statuses.append("%s: %s setting(s)" % (label, len(root.findall("./setting"))))
        except Exception as exc:
            statuses.append("%s: invalid: %s" % (label, exc))
    if not statuses:
        return "not found"
    return "; ".join(statuses)


def _cache_status(path, label):
    stats = _directory_contents_stats(_translate_path(path))
    return "%s: %s file(s), %s folder(s), %s" % (
        label,
        stats["files"],
        stats["dirs"],
        _format_bytes(stats["bytes"]),
    )


def _thumbnail_status():
    thumbs = _directory_contents_stats(_translate_path(THUMBNAILS_PATH))
    textures = _matching_children_stats(
        _translate_path(TEXTURES_DATABASE_DIR),
        _is_textures_database_name,
    )
    return "Thumbnail cache: %s file(s), %s folder(s), %s; texture DB: %s file(s), %s" % (
        thumbs["files"],
        thumbs["dirs"],
        _format_bytes(thumbs["bytes"]),
        textures["files"],
        _format_bytes(textures["bytes"]),
    )


def _setup_status_text(addon):
    timestamp_keys = (
        ("YouTube", "last_youtube_install"),
        ("TorBox", "last_torbox_install"),
        ("a4kSubtitles", "last_a4ksubtitles_install"),
        ("Cocoscrapers", "last_cocoscrapers_install"),
        ("Advanced network", "last_advanced_network_install"),
        ("Keymaps", "last_keymaps_install"),
        ("Sources backup", "last_sources_backup"),
        ("Sources restore", "last_sources_restore"),
        ("Fen Light settings backup", "last_fenlightsettings_backup"),
        ("Fen Light settings restore", "last_fenlightsettings_restore"),
        ("a4kSubtitles settings backup", "last_a4ksubtitlessettings_backup"),
        ("a4kSubtitles settings restore", "last_a4ksubtitlessettings_restore"),
        ("Thumbnails cleared", "last_thumbnail_clear"),
        ("Package cache cleared", "last_package_cache_clear"),
        ("Backups cleaned", "last_backup_cleanup"),
    )
    lines = [
        "Profile: %s" % _translate_path("special://profile"),
        "Skin: %s" % xbmc.getSkinDir(),
        "Advanced network: %s" % _advanced_network_status(),
        "Keymaps: %s" % _bundled_keymaps_status(),
        "Sources: %s" % _sources_status(),
        "Fen Light settings: %s" % _fenlight_settings_status(),
        "a4kSubtitles settings: %s" % _a4ksubtitles_settings_status(),
        _thumbnail_status(),
        _cache_status(PACKAGES_CACHE_PATH, "Package cache"),
        "",
        "Last runs:",
    ]
    for label, key in timestamp_keys:
        lines.append("- %s: %s" % (label, _get_setting(addon, key) or "never"))
    return "\n".join(lines)


def _zip_file_if_exists(zip_handle, path, arcname):
    if os.path.isfile(path):
        zip_handle.write(path, arcname)
        return True
    return False


def _zip_keymap_files(zip_handle):
    keymaps_dir = _translate_path(KEYMAPS_TARGET_PATH)
    if not os.path.isdir(keymaps_dir):
        return
    for name in sorted(os.listdir(keymaps_dir)):
        if name.startswith("._") or not name.lower().endswith(".xml"):
            continue
        _zip_file_if_exists(
            zip_handle,
            os.path.join(keymaps_dir, name),
            "profile/keymaps/%s" % name,
        )


def _export_debug_bundle(addon):
    debug_dir = _addon_data_dir("debug")
    bundle_path = os.path.join(debug_dir, "kodi-setup-kit-debug-%s.zip" % _utc_timestamp())
    log_dir = _translate_path("special://logpath")

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_handle:
        zip_handle.writestr("diagnostics/status.txt", _setup_status_text(addon))
        _zip_file_if_exists(zip_handle, os.path.join(log_dir, "kodi.log"), "logs/kodi.log")
        _zip_file_if_exists(zip_handle, os.path.join(log_dir, "kodi.old.log"), "logs/kodi.old.log")
        _zip_file_if_exists(
            zip_handle,
            _translate_path(ADVANCEDSETTINGS_PATH),
            "profile/advancedsettings.xml",
        )
        _zip_file_if_exists(
            zip_handle,
            _sources_path(),
            "profile/sources.xml",
        )
        _zip_file_if_exists(
            zip_handle,
            _translate_path("special://profile/addon_data/%s/settings.xml" % ADDON_ID),
            "profile/addon_data/%s/settings.xml" % ADDON_ID,
        )
        _zip_keymap_files(zip_handle)

    _set_timestamp(addon, "last_debug_bundle", True)
    return "Debug bundle exported to:\n%s" % bundle_path


def _launch_widget_importer(addon):
    if not _addon_installed(WIDGET_IMPORTER_ADDON_ID):
        if not _yesno(
            "Kodi Setup Kit",
            "KodiSkin Widget Importer is not installed.\n\nOpen Kodi's installer for it now?",
            yes_label="Open",
            no_label="Cancel",
        ):
            return "KodiSkin Widget Importer was not opened."
        xbmc.executebuiltin("InstallAddon(%s)" % WIDGET_IMPORTER_ADDON_ID)
        return "Kodi opened the installer for KodiSkin Widget Importer."

    xbmc.executebuiltin("RunScript(%s)" % WIDGET_IMPORTER_ADDON_ID)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_widget_importer_launch", now)
    _set_setting(addon, "last_install", now)
    return "KodiSkin Widget Importer opened."


def _backup_guisettings(addon):
    backup_path = _backup_current_guisettings()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_guisettings_backup", now)
    _set_setting(addon, "last_install", now)
    return "GUI settings backed up to: %s" % backup_path


def _restore_guisettings_preset(addon, preset):
    payload = _read_guisettings_preset_payload(preset)
    guisettings_path, backup_path, applied, failed = _write_guisettings_payload(
        payload, _preset_label(preset)
    )
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_guisettings_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_guisettings_message(
        _preset_label(preset), guisettings_path, backup_path, applied, failed
    )


def _restore_guisettings_from_url(addon, url):
    payload = _download_guisettings_payload(url)
    guisettings_path, backup_path, applied, failed = _write_guisettings_payload(
        payload, "URL"
    )
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_guisettings_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_guisettings_message(
        "URL", guisettings_path, backup_path, applied, failed
    )


def _backup_sources(addon):
    backup_path = _backup_current_sources()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_sources_backup", now)
    _set_setting(addon, "last_install", now)
    return "Kodi sources backed up to: %s" % backup_path


def _restore_sources_preset(addon, preset):
    payload = _read_sources_preset_payload(preset)
    sources_path, backup_path = _write_sources_payload(payload, _preset_label(preset))
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_sources_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_sources_message(_preset_label(preset), sources_path, backup_path)


def _restore_sources_from_url(addon, url):
    payload = _download_sources_payload(url)
    sources_path, backup_path = _write_sources_payload(payload, "URL")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_sources_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_sources_message("URL", sources_path, backup_path)


def _backup_fenlight_settings(addon):
    backups = _backup_current_fenlight_settings()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_fenlightsettings_backup", now)
    _set_setting(addon, "last_install", now)
    labels = [backup[1] for backup in backups]
    return "Fen Light settings backed up for: %s." % ", ".join(labels)


def _restore_fenlight_settings_preset(addon, preset, target):
    payload = _choose_fenlight_settings_payload(preset, target)
    if payload is None:
        raise RuntimeError("Fen Light settings restore was canceled.")
    _source_addon_id, source_db_path, source_xml_path = payload
    result = _write_fenlight_settings_payload(
        target,
        source_db_path,
        source_xml_path,
        _preset_label(preset),
    )
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_fenlightsettings_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_fenlight_settings_message(_preset_label(preset), result)


def _backup_a4ksubtitles_settings(addon):
    backups = _backup_current_a4ksubtitles_settings()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_a4ksubtitlessettings_backup", now)
    _set_setting(addon, "last_install", now)
    labels = [backup[1] for backup in backups]
    return "a4kSubtitles settings backed up for: %s." % ", ".join(labels)


def _restore_a4ksubtitles_preset(addon, preset, target):
    payload = _choose_a4ksubtitles_payload(preset, target)
    if payload is None:
        raise RuntimeError("a4kSubtitles settings restore was canceled.")
    _source_addon_id, source_path = payload
    result = _write_a4ksubtitles_payload(target, source_path, _preset_label(preset))
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_a4ksubtitlessettings_restore", now)
    _set_setting(addon, "last_install", now)
    return _restore_a4ksubtitles_message(_preset_label(preset), result)


def _install_sources(addon):
    preset = _default_builtin_preset(_sources_builtin_presets(), "sources")
    return _restore_sources_preset(addon, preset)


def _install_fenlight_settings_preset(addon):
    preset = _default_builtin_preset(_fenlight_settings_builtin_presets(), "Fen Light settings")
    targets = _fenlight_settings_targets()
    if not targets:
        raise RuntimeError("Fen Light was not found in this Kodi profile.")

    payloads = _fenlight_settings_preset_payloads(preset)
    results = []
    for target in targets:
        _source_addon_id, source_db_path, source_xml_path = _matching_preset_payload(
            payloads,
            target[0],
            "Fen Light settings",
        )
        results.append(
            _write_fenlight_settings_payload(
                target,
                source_db_path,
                source_xml_path,
                _preset_label(preset),
            )
        )

    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_fenlightsettings_restore", now)
    _set_setting(addon, "last_install", now)
    return (
        "Fen Light settings preset restored for: %s. Restart Kodi so Fen Light reloads its settings cache."
        % ", ".join(result["label"] for result in results)
    )


def _install_a4ksubtitles_settings_preset(addon):
    preset = _default_builtin_preset(_a4ksubtitles_builtin_presets(), "a4kSubtitles settings")
    targets = _a4ksubtitles_targets()
    if not targets:
        raise RuntimeError("a4kSubtitles Patched was not found in this Kodi profile.")

    payloads = _a4ksubtitles_preset_payloads(preset)
    results = []
    for target in targets:
        _source_addon_id, source_path = _matching_preset_payload(
            payloads,
            target[0],
            "a4kSubtitles settings",
        )
        results.append(_write_a4ksubtitles_payload(target, source_path, _preset_label(preset)))

    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_a4ksubtitlessettings_restore", now)
    _set_setting(addon, "last_install", now)
    return "a4kSubtitles settings preset restored for: %s." % ", ".join(
        result["label"] for result in results
    )


def _backup_skin_settings(addon):
    backups = _backup_current_skin_settings()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_skinsettings_backup", now)
    _set_setting(addon, "last_install", now)
    labels = [backup[1] for backup in backups]
    return "Skin settings backed up for: %s." % ", ".join(labels)


def _run_install_all_step(messages, label, install_func):
    try:
        messages.append(install_func())
        return True
    except Exception as exc:
        message = "%s skipped: %s" % (label, exc)
        messages.append(message)
        _log("Install everything step skipped: %s\n%s" % (message, traceback.format_exc()), xbmc.LOGWARNING)
        return False


def _run_progress_action(progress_title, progress_message, action_func):
    progress = xbmcgui.DialogProgress()
    progress.create("Kodi Setup Kit", progress_message)
    try:
        message = action_func()
        progress.update(100, "Done")
        progress.close()
        xbmcgui.Dialog().ok(progress_title, message)
    except Exception as exc:
        progress.close()
        _log("Action failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
        _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)


def _run_utility_action(action, addon):
    if action == "show_setup_status":
        _set_timestamp(addon, "last_status_check")
        _show_text("Kodi Setup Kit status", _setup_status_text(addon))
        return

    if action == "export_debug_bundle":
        _run_progress_action(
            "Kodi Setup Kit",
            "Exporting debug bundle...",
            lambda: _export_debug_bundle(addon),
        )
        return

    if action == "clear_thumbnail_cache":
        if not _confirm_clear_thumbnail_cache():
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Clearing thumbnail cache...",
            lambda: _clear_thumbnail_cache(addon),
        )
        return

    if action == "clear_package_cache":
        if not _confirm_clear_package_cache():
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Clearing add-on package cache...",
            lambda: _clear_package_cache(addon),
        )
        return

    if action == "clean_setup_backups":
        if not _confirm_clean_setup_backups():
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Cleaning Setup Kit backups...",
            lambda: _clean_setup_backups(addon),
        )
        return

    if action == "reload_skin":
        if not _yesno(
            "Kodi Setup Kit",
            "Reload the active Kodi skin now?",
            yes_label="Reload",
            no_label="Cancel",
        ):
            return
        _notify(_reload_skin(addon))
        return

    if action == "restart_kodi":
        if not _yesno(
            "Kodi Setup Kit",
            "Restart Kodi now?",
            yes_label="Restart",
            no_label="Cancel",
        ):
            return
        _notify(_restart_kodi(addon))
        return

    _show_menu(UTILITIES_MENU_ITEMS)


def _run_action(action):
    if action == "menu_guisettings":
        _show_menu(GUISETTINGS_MENU_ITEMS)
        return

    if action == "menu_sources":
        _show_menu(SOURCES_MENU_ITEMS)
        return

    if action == "menu_fenlightsettings":
        _show_menu(FENLIGHTSETTINGS_MENU_ITEMS)
        return

    if action == "menu_a4ksubtitlessettings":
        _show_menu(A4KSUBTITLESSETTINGS_MENU_ITEMS)
        return

    if action == "menu_skinsettings":
        _show_menu(SKINSETTINGS_MENU_ITEMS)
        return

    if action == "menu_utilities":
        _show_menu(UTILITIES_MENU_ITEMS)
        return

    if action not in (
        "install_sources",
        "install_fenlightsettings",
        "install_a4ksubtitlessettings_preset",
        "install_youtube",
        "install_torbox",
        "install_a4ksubtitles",
        "install_cocoscrapers",
        "install_advanced_network",
        "install_keymaps",
        "launch_widget_importer",
        "backup_guisettings",
        "save_guisettings_preset",
        "rename_guisettings_preset",
        "delete_guisettings_preset",
        "restore_guisettings_url",
        "restore_guisettings_builtin",
        "backup_sources",
        "save_sources_preset",
        "rename_sources_preset",
        "delete_sources_preset",
        "restore_sources_url",
        "restore_sources_builtin",
        "backup_fenlightsettings",
        "save_fenlightsettings_preset",
        "rename_fenlightsettings_preset",
        "delete_fenlightsettings_preset",
        "restore_fenlightsettings_builtin",
        "backup_a4ksubtitlessettings",
        "save_a4ksubtitlessettings_preset",
        "rename_a4ksubtitlessettings_preset",
        "delete_a4ksubtitlessettings_preset",
        "restore_a4ksubtitlessettings_builtin",
        "backup_skinsettings",
        "save_skinsettings_preset",
        "rename_skinsettings_preset",
        "delete_skinsettings_preset",
        "restore_skinsettings_url",
        "restore_skinsettings_builtin",
        "install_all",
    ) + UTILITY_ACTIONS:
        _show_menu()
        return

    addon = _addon()

    if action in UTILITY_ACTIONS:
        _run_utility_action(action, addon)
        return

    if action == "install_sources":
        _run_progress_action(
            "Kodi Setup Kit",
            "Restoring Kodi sources...",
            lambda: _install_sources(addon),
        )
        return

    if action == "install_fenlightsettings":
        _run_progress_action(
            "Kodi Setup Kit",
            "Restoring Fen Light settings preset...",
            lambda: _install_fenlight_settings_preset(addon),
        )
        return

    if action == "install_a4ksubtitlessettings_preset":
        _run_progress_action(
            "Kodi Setup Kit",
            "Restoring a4kSubtitles settings preset...",
            lambda: _install_a4ksubtitles_settings_preset(addon),
        )
        return

    if action == "install_cocoscrapers":
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Installing Cocoscrapers filters...")
        try:
            message = _install_cocoscrapers(addon)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "install_advanced_network":
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Installing Kodi network advanced settings...")
        try:
            message = _install_advanced_network_settings(addon)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "install_keymaps":
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Installing Kodi keymaps...")
        try:
            message = _install_keymaps(addon)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "launch_widget_importer":
        try:
            message = _launch_widget_importer(addon)
            _notify(message)
        except Exception as exc:
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "backup_guisettings":
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Backing up Kodi GUI settings...")
        try:
            message = _backup_guisettings(addon)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "save_guisettings_preset":
        preset_name = _prompt_preset_name("GUI settings")
        if not preset_name:
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Saving GUI settings preset...")
        try:
            message = _save_guisettings_preset(addon, preset_name)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "rename_guisettings_preset":
        preset = _prompt_guisettings_preset()
        if preset is None:
            return
        new_name = _prompt_preset_name("New GUI settings")
        if not new_name:
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Renaming GUI settings preset...")
        try:
            message = _rename_guisettings_preset(addon, preset, new_name)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "delete_guisettings_preset":
        preset = _prompt_guisettings_preset()
        if preset is None or not _confirm_delete_preset(preset):
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Deleting GUI settings preset...")
        try:
            message = _delete_guisettings_preset(addon, preset)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "restore_guisettings_builtin":
        preset = _prompt_guisettings_preset()
        if preset is None:
            return
        preset_label = _preset_label(preset)
        if not _confirm_guisettings_restore(preset_label):
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Restoring GUI settings preset...")
        try:
            message = _restore_guisettings_preset(addon, preset)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "restore_guisettings_url":
        url = _prompt_guisettings_url()
        if not url:
            return
        if not _confirm_guisettings_restore("the URL"):
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Restoring GUI settings from URL...")
        try:
            message = _restore_guisettings_from_url(addon, url)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "backup_sources":
        _run_progress_action(
            "Kodi Setup Kit",
            "Backing up Kodi sources...",
            lambda: _backup_sources(addon),
        )
        return

    if action == "save_sources_preset":
        preset_name = _prompt_preset_name("Sources")
        if not preset_name:
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Saving sources preset...",
            lambda: _save_sources_preset(addon, preset_name),
        )
        return

    if action == "rename_sources_preset":
        preset = _prompt_sources_preset()
        if preset is None:
            return
        new_name = _prompt_preset_name("New sources")
        if not new_name:
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Renaming sources preset...",
            lambda: _rename_sources_preset(addon, preset, new_name),
        )
        return

    if action == "delete_sources_preset":
        preset = _prompt_sources_preset()
        if preset is None or not _confirm_delete_preset(preset):
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Deleting sources preset...",
            lambda: _delete_sources_preset(addon, preset),
        )
        return

    if action == "restore_sources_builtin":
        preset = _prompt_sources_preset()
        if preset is None:
            return
        preset_label = _preset_label(preset)
        if not _confirm_sources_restore(preset_label):
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Restoring sources preset...",
            lambda: _restore_sources_preset(addon, preset),
        )
        return

    if action == "restore_sources_url":
        url = _prompt_sources_url()
        if not url:
            return
        if not _confirm_sources_restore("the URL"):
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Restoring sources from URL...",
            lambda: _restore_sources_from_url(addon, url),
        )
        return

    if action == "backup_fenlightsettings":
        _run_progress_action(
            "Kodi Setup Kit",
            "Backing up Fen Light settings...",
            lambda: _backup_fenlight_settings(addon),
        )
        return

    if action == "save_fenlightsettings_preset":
        preset_name = _prompt_preset_name("Fen Light settings")
        if not preset_name:
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Saving Fen Light settings preset...",
            lambda: _save_fenlight_settings_preset(addon, preset_name),
        )
        return

    if action == "rename_fenlightsettings_preset":
        preset = _prompt_fenlight_settings_preset()
        if preset is None:
            return
        new_name = _prompt_preset_name("New Fen Light settings")
        if not new_name:
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Renaming Fen Light settings preset...",
            lambda: _rename_fenlight_settings_preset(addon, preset, new_name),
        )
        return

    if action == "delete_fenlightsettings_preset":
        preset = _prompt_fenlight_settings_preset()
        if preset is None or not _confirm_delete_preset(preset):
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Deleting Fen Light settings preset...",
            lambda: _delete_fenlight_settings_preset(addon, preset),
        )
        return

    if action == "restore_fenlightsettings_builtin":
        preset = _prompt_fenlight_settings_preset()
        if preset is None:
            return
        target = _prompt_fenlight_settings_target()
        if target is None:
            return
        preset_label = _preset_label(preset)
        if not _confirm_fenlight_settings_restore(preset_label, target[1]):
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Restoring Fen Light settings preset...",
            lambda: _restore_fenlight_settings_preset(addon, preset, target),
        )
        return

    if action == "backup_a4ksubtitlessettings":
        _run_progress_action(
            "Kodi Setup Kit",
            "Backing up a4kSubtitles settings...",
            lambda: _backup_a4ksubtitles_settings(addon),
        )
        return

    if action == "save_a4ksubtitlessettings_preset":
        preset_name = _prompt_preset_name("a4kSubtitles settings")
        if not preset_name:
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Saving a4kSubtitles settings preset...",
            lambda: _save_a4ksubtitles_preset(addon, preset_name),
        )
        return

    if action == "rename_a4ksubtitlessettings_preset":
        preset = _prompt_a4ksubtitles_preset()
        if preset is None:
            return
        new_name = _prompt_preset_name("New a4kSubtitles settings")
        if not new_name:
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Renaming a4kSubtitles settings preset...",
            lambda: _rename_a4ksubtitles_preset(addon, preset, new_name),
        )
        return

    if action == "delete_a4ksubtitlessettings_preset":
        preset = _prompt_a4ksubtitles_preset()
        if preset is None or not _confirm_delete_preset(preset):
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Deleting a4kSubtitles settings preset...",
            lambda: _delete_a4ksubtitles_preset(addon, preset),
        )
        return

    if action == "restore_a4ksubtitlessettings_builtin":
        preset = _prompt_a4ksubtitles_preset()
        if preset is None:
            return
        target = _prompt_a4ksubtitles_target()
        if target is None:
            return
        preset_label = _preset_label(preset)
        if not _confirm_a4ksubtitles_restore(preset_label, target[1]):
            return
        _run_progress_action(
            "Kodi Setup Kit",
            "Restoring a4kSubtitles settings preset...",
            lambda: _restore_a4ksubtitles_preset(addon, preset, target),
        )
        return

    if action == "backup_skinsettings":
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Backing up skin settings...")
        try:
            message = _backup_skin_settings(addon)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "save_skinsettings_preset":
        preset_name = _prompt_preset_name("Skin settings")
        if not preset_name:
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Saving skin settings preset...")
        try:
            message = _save_skin_settings_preset(addon, preset_name)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "rename_skinsettings_preset":
        preset = _prompt_skin_settings_preset()
        if preset is None:
            return
        new_name = _prompt_preset_name("New skin settings")
        if not new_name:
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Renaming skin settings preset...")
        try:
            message = _rename_skin_settings_preset(addon, preset, new_name)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "delete_skinsettings_preset":
        preset = _prompt_skin_settings_preset()
        if preset is None or not _confirm_delete_preset(preset):
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Deleting skin settings preset...")
        try:
            message = _delete_skin_settings_preset(addon, preset)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "restore_skinsettings_builtin":
        preset = _prompt_skin_settings_preset()
        if preset is None:
            return
        preset_label = _preset_label(preset)
        if not _confirm_skin_settings_restore(preset_label):
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Restoring skin settings preset...")
        try:
            message = _restore_skin_settings_preset(addon, preset)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    if action == "restore_skinsettings_url":
        url = _prompt_skin_settings_url()
        if not url:
            return
        if not _confirm_skin_settings_restore("the URL"):
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Setup Kit", "Restoring skin settings from URL...")
        try:
            message = _restore_skin_settings_from_url(addon, url)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("Kodi Setup Kit", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    api_url = _get_setting(addon, "api_url").strip()
    if not api_url or "YOUR-VERCEL-PROJECT" in api_url:
        xbmcgui.Dialog().ok("Kodi Setup Kit", "Set the Kodi Setup Kit bridge URL in the add-on settings first.")
        return

    password = _prompt_password()
    if not password:
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Kodi Setup Kit", "Contacting Kodi Setup Kit bridge...")

    try:
        bridge_data = _read_bridge_response(api_url, password)
        messages = []

        if action == "install_all":
            install_all_steps = (
                (
                    8,
                    "Restoring Kodi sources...",
                    "Kodi sources",
                    lambda: _install_sources(addon),
                ),
                (
                    18,
                    "Restoring Fen Light settings preset...",
                    "Fen Light settings preset",
                    lambda: _install_fenlight_settings_preset(addon),
                ),
                (
                    28,
                    "Restoring a4kSubtitles settings preset...",
                    "a4kSubtitles settings preset",
                    lambda: _install_a4ksubtitles_settings_preset(addon),
                ),
                (
                    40,
                    "Installing YouTube credentials...",
                    "YouTube credentials",
                    lambda: _install_youtube(addon, bridge_data),
                ),
                (
                    52,
                    "Installing TorBox API key...",
                    "TorBox API key",
                    lambda: _install_torbox(addon, bridge_data),
                ),
                (
                    64,
                    "Installing a4kSubtitles credentials...",
                    "a4kSubtitles credentials",
                    lambda: _install_a4ksubtitles(addon, bridge_data),
                ),
                (
                    76,
                    "Installing Cocoscrapers filters...",
                    "Cocoscrapers filters",
                    lambda: _install_cocoscrapers(addon),
                ),
                (
                    88,
                    "Installing Kodi network advanced settings...",
                    "Kodi network advanced settings",
                    lambda: _install_advanced_network_settings(addon),
                ),
                (
                    96,
                    "Installing Kodi keymaps...",
                    "Kodi keymaps",
                    lambda: _install_keymaps(addon),
                ),
            )
            for percent, message, label, install_func in install_all_steps:
                progress.update(percent, message)
                _run_install_all_step(messages, label, install_func)
        elif action == "install_youtube":
            progress.update(25, "Installing YouTube credentials...")
            messages.append(_install_youtube(addon, bridge_data))
        elif action == "install_torbox":
            progress.update(50, "Installing TorBox API key...")
            messages.append(_install_torbox(addon, bridge_data))
        elif action == "install_a4ksubtitles":
            progress.update(75, "Installing a4kSubtitles settings...")
            messages.append(_install_a4ksubtitles(addon, bridge_data))

        progress.update(100, "Done")
        progress.close()
        summary = "\n".join(messages)
        if action in ("install_youtube", "install_all"):
            summary += "\n\nFamily members can still sign in to YouTube with their own Google account."
        xbmcgui.Dialog().ok(
            "Kodi Setup Kit",
            summary,
        )
    except Exception as exc:
        progress.close()
        _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
        _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)


def run():
    params = _query_params()
    action = params.get("action")
    if not action:
        _show_menu()
        return

    try:
        _run_action(action)
    finally:
        _end_plugin_directory()
