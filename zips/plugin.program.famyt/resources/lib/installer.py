import ast
import datetime
import io
import json
import os
import sqlite3
import sys
import traceback
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


ADDON_ID = "plugin.program.famyt"
YOUTUBE_ADDON_ID = "plugin.video.youtube"
YOUTUBE_DATA_PATH = "special://profile/addon_data/plugin.video.youtube"
API_KEYS_FILENAME = "api_keys.json"
CLIENT_ID_SUFFIX = ".apps.googleusercontent.com"

FENLIGHT_ADDON_IDS = (
    "plugin.video.fenlight",
    "plugin.video.fenlight.patched",
    "plugin.video.fenlight.kodienglish",
    "plugin.video.fenlight.patched.kodienglish",
)
FENLIGHT_SETTINGS_DB = os.path.join("databases", "settings.db")
A4KSUBTITLES_ADDON_IDS = (
    "service.subtitles.a4ksubtitles.patched",
)
A4KSUBTITLES_AI_MODEL = "gpt-4.1-mini-2025-04-14"
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
    ("Install YouTube credentials", "install_youtube"),
    ("Install TorBox API key", "install_torbox"),
    ("Install a4kSubtitles settings", "install_a4ksubtitles"),
    ("Install Cocoscrapers filters", "install_cocoscrapers"),
    ("Install everything", "install_all"),
)


def _addon():
    return xbmcaddon.Addon(ADDON_ID)


def _log(message, level=xbmc.LOGINFO):
    xbmc.log("[famYT] %s" % message, level)


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


def _notify(message, heading="famYT", icon=xbmcgui.NOTIFICATION_INFO, ms=5000):
    xbmcgui.Dialog().notification(heading, message, icon, ms)


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


def _show_menu():
    handle = _plugin_handle()
    if handle < 0:
        xbmcgui.Dialog().ok("famYT", "Open famYT from Kodi's program add-ons menu.")
        return

    import xbmcplugin

    for label, action in MENU_ITEMS:
        item = xbmcgui.ListItem(label=label)
        try:
            item.setArt({"icon": "DefaultAddonProgram.png"})
        except Exception:
            pass
        xbmcplugin.addDirectoryItem(handle, _menu_url(action), item, False)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def _prompt_password():
    dialog = xbmcgui.Dialog()
    hidden_option = getattr(xbmcgui, "ALPHANUM_HIDE_INPUT", 0)
    return dialog.input(
        "famYT password",
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
            "User-Agent": "famYT Kodi add-on",
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
        raise RuntimeError("Could not reach famYT bridge: %s" % exc.reason)
    except ValueError:
        raise RuntimeError("famYT bridge returned invalid JSON")


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
        raise RuntimeError("famYT bridge response is missing: %s" % ", ".join(missing))

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
            "famYT bridge response is missing torbox.api_key. "
            "Add TORBOX_API_KEY to the Vercel environment and redeploy."
        )
    return api_key


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
            "famYT bridge response is missing: %s. "
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


def _write_fenlight_torbox_setting(addon_id, data_path, api_key):
    db_path = os.path.join(data_path, FENLIGHT_SETTINGS_DB)
    db_dir = os.path.dirname(db_path)
    if not os.path.isdir(db_dir):
        os.makedirs(db_dir)

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
            (
                ("tb.token", "string", "empty_setting", api_key),
                ("tb.enabled", "boolean", "false", "true"),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    _log("Installed TorBox API key for %s at %s" % (addon_id, db_path))
    return db_path


def _set_fenlight_window_cache(api_key):
    try:
        window = xbmcgui.Window(10000)
        window.setProperty("fenlight.tb.token", api_key)
        window.setProperty("fenlight.tb.enabled", "true")
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
    candidates = _candidate_fenlight_addons()
    if not candidates:
        raise RuntimeError("Fen Light was not found in this Kodi profile.")

    updated = []
    for addon_id, data_path in candidates:
        _write_fenlight_torbox_setting(addon_id, data_path, api_key)
        updated.append(addon_id)

    _set_fenlight_window_cache(api_key)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    _set_setting(addon, "last_torbox_install", now)
    _set_setting(addon, "last_install", now)
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


def _run_install_all_step(messages, label, install_func):
    try:
        messages.append(install_func())
        return True
    except Exception as exc:
        message = "%s skipped: %s" % (label, exc)
        messages.append(message)
        _log("Install everything step skipped: %s\n%s" % (message, traceback.format_exc()), xbmc.LOGWARNING)
        return False


def _run_action(action):
    if action not in (
        "install_youtube",
        "install_torbox",
        "install_a4ksubtitles",
        "install_cocoscrapers",
        "install_all",
    ):
        _show_menu()
        return

    addon = _addon()

    if action == "install_cocoscrapers":
        progress = xbmcgui.DialogProgress()
        progress.create("famYT", "Installing Cocoscrapers filters...")
        try:
            message = _install_cocoscrapers(addon)
            progress.update(100, "Done")
            progress.close()
            xbmcgui.Dialog().ok("famYT", message)
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
        return

    api_url = _get_setting(addon, "api_url").strip()
    if not api_url or "YOUR-VERCEL-PROJECT" in api_url:
        xbmcgui.Dialog().ok("famYT", "Set the famYT bridge URL in the add-on settings first.")
        return

    password = _prompt_password()
    if not password:
        return

    progress = xbmcgui.DialogProgress()
    progress.create("famYT", "Contacting famYT bridge...")

    try:
        bridge_data = _read_bridge_response(api_url, password)
        messages = []

        if action == "install_all":
            progress.update(25, "Installing YouTube credentials...")
            _run_install_all_step(
                messages,
                "YouTube credentials",
                lambda: _install_youtube(addon, bridge_data),
            )
            progress.update(50, "Installing TorBox API key...")
            _run_install_all_step(
                messages,
                "TorBox API key",
                lambda: _install_torbox(addon, bridge_data),
            )
            progress.update(75, "Installing a4kSubtitles settings...")
            _run_install_all_step(
                messages,
                "a4kSubtitles settings",
                lambda: _install_a4ksubtitles(addon, bridge_data),
            )
            progress.update(90, "Installing Cocoscrapers filters...")
            _run_install_all_step(
                messages,
                "Cocoscrapers filters",
                lambda: _install_cocoscrapers(addon),
            )
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
            "famYT",
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
