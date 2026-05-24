# -*- coding: utf-8 -*-
"""Installer and runtime helper for Fen Light widget quick rescrape."""

import os
import re
import sys
import traceback
from urllib.parse import parse_qsl, urlencode, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


ADDON_ID = "script.fenlight.quickrescrape"
FEN_ADDON_ID = "plugin.video.fenlight.patched"
HOME_WINDOW_ID = 10000
MY_VIDEO_NAV_WINDOW_ID = 10025
ALLOWED_WINDOW_IDS = (HOME_WINDOW_ID, MY_VIDEO_NAV_WINDOW_ID)
FEN_PLUGIN_PREFIX = "plugin://{}/".format(FEN_ADDON_ID)
KEYMAP_FILE = "special://profile/keymaps/zz_fenlight_quickrescrape.xml"
KEYMAP_ACTION = "RunScript(special://home/addons/{}/default.py,rescrape)".format(ADDON_ID)
KEYMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<keymap>
  <Home>
    <keyboard>
      <i>{action}</i>
      <fastforward mod="longpress">{action}</fastforward>
    </keyboard>
    <appcommand>
      <fastforward mod="longpress">{action}</fastforward>
    </appcommand>
  </Home>
  <Videos>
    <keyboard>
      <i>{action}</i>
      <fastforward mod="longpress">{action}</fastforward>
    </keyboard>
    <appcommand>
      <fastforward mod="longpress">{action}</fastforward>
    </appcommand>
  </Videos>
</keymap>
""".format(action=KEYMAP_ACTION)

STATIC_FOCUS_SOURCES = (
    ("listitem", "ListItem"),
    ("container_focus", "Container.ListItem"),
    ("container_nowrap_0", "Container.ListItemNoWrap(0)"),
    ("container_nowrap_1", "Container.ListItemNoWrap(1)"),
    ("container_nowrap_-1", "Container.ListItemNoWrap(-1)"),
)
AH2_MEDIA_CONTAINER_IDS = (
    50, 500, 501, 502, 503, 504, 507, 508,
    510, 511, 512, 513, 514, 517,
    520, 521, 522, 523, 524, 527,
    540, 550, 551, 552, 553, 554, 557, 558,
    560, 570, 572, 574, 580, 581, 590, 591,
    99950, 99999,
)


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[{}] {}".format(ADDON_ID, message), level)


def notify(message, heading="Fen Quick Rescrape"):
    xbmcgui.Dialog().notification(heading, message, time=3000)


def write_text(path, text):
    directory = path.rsplit("/", 1)[0]
    if not xbmcvfs.exists(directory):
        xbmcvfs.mkdirs(directory)
    file_obj = xbmcvfs.File(path, "w")
    try:
        file_obj.write(text)
    finally:
        file_obj.close()


def install_keymap():
    write_text(KEYMAP_FILE, KEYMAP_XML)
    xbmc.executebuiltin("Action(ReloadKeymaps)")
    notify("Installed. Restart Kodi if the shortcut does not work immediately.")
    log("Installed keymap at {}".format(KEYMAP_FILE))


def remove_keymap():
    if xbmcvfs.exists(KEYMAP_FILE):
        xbmcvfs.delete(KEYMAP_FILE)
    xbmc.executebuiltin("Action(ReloadKeymaps)")
    notify("Removed keymap.")
    log("Removed keymap at {}".format(KEYMAP_FILE))


def addon_launch_menu():
    choice = xbmcgui.Dialog().select(
        "Fen Light Quick Rescrape",
        ["Install / update Shield FF shortcut", "Remove shortcut", "Test on focused item"],
    )
    if choice == 0:
        install_keymap()
    elif choice == 1:
        remove_keymap()
    elif choice == 2:
        run_rescrape()


def fen_lib_path():
    addon_path = xbmcaddon.Addon(FEN_ADDON_ID).getAddonInfo("path")
    return os.path.join(addon_path, "resources", "lib")


def labels_for_source(name, prefix):
    labels = {
        "source": name,
        "filename": xbmc.getInfoLabel("{}.FileNameAndPath".format(prefix)),
        "folder": xbmc.getInfoLabel("{}.FolderPath".format(prefix)),
        "path": xbmc.getInfoLabel("{}.Path".format(prefix)),
        "dbtype": xbmc.getInfoLabel("{}.DBTYPE".format(prefix)),
        "tmdb": xbmc.getInfoLabel("{}.UniqueId(tmdb)".format(prefix)) or xbmc.getInfoLabel("{}.UniqueID(tmdb)".format(prefix)),
        "season": xbmc.getInfoLabel("{}.Season".format(prefix)),
        "episode": xbmc.getInfoLabel("{}.Episode".format(prefix)),
        "title": xbmc.getInfoLabel("{}.Title".format(prefix)) or xbmc.getInfoLabel("{}.Label".format(prefix)),
        "label": xbmc.getInfoLabel("{}.Label".format(prefix)),
        "fen_options": xbmc.getInfoLabel("{}.Property(fenlight.options_params)".format(prefix)),
        "fen_extras": xbmc.getInfoLabel("{}.Property(fenlight.extras_params)".format(prefix)),
    }
    return labels


def labels_have_content(labels):
    return any(labels.get(key) for key in ("filename", "folder", "path", "dbtype", "tmdb", "season", "episode", "title", "fen_options", "fen_extras"))


def current_widget_container_sources():
    sources = []
    seen = set()
    for prop in ("Window.Property(TMDbHelper.WidgetContainer)", "Window(Home).Property(TMDbHelper.WidgetContainer)"):
        value = xbmc.getInfoLabel(prop)
        if not value or not value.isdigit() or value in seen:
            continue
        seen.add(value)
        sources.append(("window_prop_{}_focus".format(value), "Container({}).ListItem".format(value)))
        sources.append(("window_prop_{}_nowrap_0".format(value), "Container({}).ListItemNoWrap(0)".format(value)))
    return sources


def focus_sources():
    sources = current_widget_container_sources()
    sources.extend(STATIC_FOCUS_SOURCES)
    for container_id in AH2_MEDIA_CONTAINER_IDS:
        sources.append(("container_{}_focus".format(container_id), "Container({}).ListItem".format(container_id)))
        sources.append(("container_{}_nowrap_0".format(container_id), "Container({}).ListItemNoWrap(0)".format(container_id)))
    return sources


def extract_fen_url(value):
    if not value:
        return ""
    if value.startswith(FEN_PLUGIN_PREFIX):
        return value
    match = re.search(r"(plugin://%s/\?[^'\" ]+)" % re.escape(FEN_ADDON_ID), value)
    return match.group(1) if match else ""


def fen_url_mode(labels):
    for key in ("filename", "folder", "path", "fen_options", "fen_extras"):
        fen_url = extract_fen_url(labels.get(key, ""))
        if fen_url:
            return dict(parse_qsl(urlparse(fen_url).query, keep_blank_values=True)).get("mode", "")
    return ""


def candidate_summary(labels):
    return {
        "source": labels.get("source", ""),
        "dbtype": labels.get("dbtype", ""),
        "tmdb": labels.get("tmdb", ""),
        "season": labels.get("season", ""),
        "episode": labels.get("episode", ""),
        "title": labels.get("title", ""),
        "mode": fen_url_mode(labels),
    }


def focused_label_candidates():
    candidates = []
    for name, prefix in focus_sources():
        labels = labels_for_source(name, prefix)
        if labels_have_content(labels):
            candidates.append(labels)
    log("Focused label candidates: {}".format([candidate_summary(item) for item in candidates]))
    return candidates


def focused_fen_params():
    candidates = focused_label_candidates()
    for labels in candidates:
        source = labels.get("source", "unknown")
        for key in ("filename", "folder", "path", "fen_options", "fen_extras"):
            fen_url = extract_fen_url(labels.get(key, ""))
            if not fen_url:
                continue
            params = dict(parse_qsl(urlparse(fen_url).query, keep_blank_values=True))
            if params.get("mode") == "playback.media":
                log("Using focused Fen URL from {} {}: {}".format(source, key, fen_url))
                return params
            if params.get("mode") == "options_menu_choice" and params.get("content") == "movie":
                log("Using movie fallback from {} {}: {}".format(source, key, fen_url))
                return {
                    "mode": "playback.media",
                    "media_type": "movie",
                    "tmdb_id": params.get("tmdb_id", ""),
                }
            log("Ignored non-playback Fen URL from {} {}: {}".format(source, key, fen_url), xbmc.LOGDEBUG)

    for labels in candidates:
        params = fallback_params_from_labels(labels)
        if params:
            log("Using fallback params from {} info labels: {}".format(labels.get("source", "unknown"), params))
            return params
    return {}


def fallback_params_from_labels(labels):
    media_type = labels.get("dbtype", "").lower()
    tmdb_id = labels.get("tmdb", "")
    if media_type not in ("movie", "episode") or not tmdb_id:
        return {}

    params = {"mode": "playback.media", "media_type": media_type, "tmdb_id": tmdb_id}
    if media_type == "episode":
        season, episode = labels.get("season", ""), labels.get("episode", "")
        if not season or not episode:
            return {}
        params.update({"season": season, "episode": episode})
    return params


def clear_fen_source_cache(media_type, tmdb_id):
    lib_path = fen_lib_path()
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)

    from caches.base_cache import clear_cache
    from caches.external_cache import ExternalCache

    clear_cache("internal_scrapers", silent=True)
    ExternalCache().delete_cache_single(media_type, str(tmdb_id))
    log("Cleared Fen source cache for {} {}".format(media_type, tmdb_id))


def launch_source_select(params):
    play_params = {
        "mode": "playback.media",
        "media_type": params.get("media_type"),
        "tmdb_id": params.get("tmdb_id"),
        "autoplay": "false",
    }
    if play_params["media_type"] == "episode":
        play_params["season"] = params.get("season", "")
        play_params["episode"] = params.get("episode", "")
        if not play_params["season"] or not play_params["episode"]:
            notify("Missing season/episode")
            return

    url = "{}?{}".format(FEN_PLUGIN_PREFIX, urlencode(play_params))
    xbmc.executebuiltin("RunPlugin({})".format(url))
    log("Executed {}".format(url))


def run_rescrape():
    window_id = xbmcgui.getCurrentWindowId()
    dialog_id = xbmcgui.getCurrentWindowDialogId()
    log("Invoked for rescrape with argv={!r}, window_id={}, dialog_id={}".format(sys.argv, window_id, dialog_id))

    if window_id not in ALLOWED_WINDOW_IDS:
        log("Ignored outside supported windows")
        return

    try:
        xbmcaddon.Addon(FEN_ADDON_ID)
    except Exception:
        notify("Fen Light Patched is not installed")
        return

    params = focused_fen_params()
    media_type, tmdb_id = params.get("media_type"), params.get("tmdb_id")
    if media_type not in ("movie", "episode") or not tmdb_id:
        notify("No playable Fen movie/episode focused")
        return

    clear_fen_source_cache(media_type, tmdb_id)
    launch_source_select(params)


def main():
    args = [arg.lower() for arg in sys.argv[1:]]
    if "rescrape" in args:
        run_rescrape()
    else:
        addon_launch_menu()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)
        notify("Something went wrong")
