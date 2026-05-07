import datetime
import io
import json
import os
import sys
import traceback
import urllib.error
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


ADDON_ID = "plugin.program.famyt"
YOUTUBE_ADDON_ID = "plugin.video.youtube"
YOUTUBE_DATA_PATH = "special://profile/addon_data/plugin.video.youtube"
API_KEYS_FILENAME = "api_keys.json"
CLIENT_ID_SUFFIX = ".apps.googleusercontent.com"


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


def _end_plugin_directory():
    try:
        if len(sys.argv) > 1 and str(sys.argv[1]).isdigit():
            import xbmcplugin

            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True)
    except Exception:
        pass


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
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_keys(data):
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
    youtube = xbmcaddon.Addon(YOUTUBE_ADDON_ID)
    _set_setting(youtube, "youtube.api.key", keys["api_key"])
    _set_setting(youtube, "youtube.api.id", keys["client_id"])
    _set_setting(youtube, "youtube.api.secret", keys["client_secret"])


def run():
    try:
        addon = _addon()
        api_url = _get_setting(addon, "api_url").strip()

        if not api_url or "YOUR-VERCEL-PROJECT" in api_url:
            xbmcgui.Dialog().ok(
                "famYT",
                "Set the famYT bridge URL in the add-on settings first.",
            )
            return

        if not xbmcgui.Dialog().yesno(
            "famYT",
            "Install family YouTube API credentials for this Kodi profile?",
        ):
            return

        password = _prompt_password()
        if not password:
            return

        progress = xbmcgui.DialogProgress()
        progress.create("famYT", "Fetching YouTube API credentials...")

        try:
            bridge_data = _read_bridge_response(api_url, password)
            progress.update(50, "Installing credentials...")
            keys = _extract_keys(bridge_data)
            api_keys_path = _write_api_keys(keys)
            _update_youtube_settings(keys)
            _set_setting(addon, "last_install", datetime.datetime.utcnow().isoformat() + "Z")
            _log("Installed YouTube API credentials at %s" % api_keys_path)
            progress.close()
            xbmcgui.Dialog().ok(
                "famYT",
                "YouTube API credentials were installed. Open the YouTube add-on and sign in with your own Google account.",
            )
        except Exception as exc:
            progress.close()
            _log("Install failed: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
            _notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR, ms=8000)
    finally:
        _end_plugin_directory()
