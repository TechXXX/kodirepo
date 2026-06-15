# -*- coding: utf-8 -*-
"""TorBox CDN and real requestdl throughput tester for Kodi."""

import os
import re
import sqlite3
import sys
import time
import traceback
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse

import requests
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs


ADDON_ID = "plugin.video.torbox.cdn.test"
ADDON_NAME = "TorBox CDN Test"
BASE_API = "https://api.torbox.app/v1/api/"
USER_AGENT = "Kodi TorBox CDN Test/0.1.0"
LAST_REPORT_FILE = "last_report.txt"
TOKEN_SETTING_KEYS = ("tb.token", "fenlight.tb.token")
FENLIGHT_ADDON_IDS = (
    "plugin.video.fenlight.patched",
    "plugin.video.fenlight",
    "plugin.video.fenlight.patched.kodienglish",
    "plugin.video.fenlight.kodienglish",
)
VIDEO_EXTENSIONS = (
    ".mkv", ".mp4", ".m4v", ".avi", ".mov", ".ts", ".m2ts", ".webm", ".wmv",
)
DEFAULT_CHUNK_SIZE = 256 * 1024

MEDIA_ENDPOINTS = {
    "torrent": {
        "history": "torrents/mylist",
        "explore": "torrents/mylist?id=%s",
        "requestdl": "torrents/requestdl",
        "id_param": "torrent_id",
    },
    "usenet": {
        "history": "usenet/mylist",
        "explore": "usenet/mylist?id=%s",
        "requestdl": "usenet/requestdl",
        "id_param": "usenet_id",
    },
    "webdl": {
        "history": "webdl/mylist",
        "explore": "webdl/mylist?id=%s",
        "requestdl": "webdl/requestdl",
        "id_param": "web_id",
    },
}

REGION_LABELS = {
    "auto": "Auto",
    "erth": "Cloudflare (ERTH)",
    "hare": "BunnyCDN (HARE)",
    "wnam": "US West (WNAM)",
    "enam": "US East (ENAM)",
    "cnam": "US Central (CNAM)",
    "snam": "US South (SNAM)",
    "latm": "Latin America (LATM)",
    "apac": "Asia Pacific (APAC)",
    "soce": "South Oceania (SOCE)",
    "indi": "India (INDI)",
    "japn": "Japan (JAPN)",
    "weur": "West Europe (WEUR)",
    "neur": "North Europe (NEUR)",
    "ceur": "Central Europe (CEUR)",
    "seur": "South Europe (SEUR)",
    "nord": "Norway (NORD)",
    "slav": "Ukraine (SLAV)",
    "safr": "South Africa (SAFR)",
    "meas": "Middle East (MEAS)",
}


class UserCancelled(Exception):
    pass


def _addon():
    return xbmcaddon.Addon(ADDON_ID)


def _translate_path(path):
    translate = getattr(xbmcvfs, "translatePath", None) or getattr(xbmc, "translatePath")
    translated = translate(path)
    if isinstance(translated, bytes):
        translated = translated.decode("utf-8")
    return translated


def _addon_profile():
    profile = _translate_path(_addon().getAddonInfo("profile"))
    if not xbmcvfs.exists(profile):
        xbmcvfs.mkdirs(profile)
    return profile


def _setting(key, default=""):
    value = _addon().getSetting(key)
    return value if value not in ("", None) else default


def _setting_int(key, default):
    try:
        value = int(float(_setting(key, str(default))))
        return value if value > 0 else default
    except Exception:
        return default


def _setting_float(key, default):
    try:
        value = float(_setting(key, str(default)))
        return value if value > 0 else default
    except Exception:
        return default


def _log(message, level=xbmc.LOGINFO):
    xbmc.log("[%s] %s" % (ADDON_NAME, message), level)


def _notify(message, icon=xbmcgui.NOTIFICATION_INFO, ms=5000):
    xbmcgui.Dialog().notification(ADDON_NAME, message, icon, ms)


def _query_params():
    query = sys.argv[2].lstrip("?") if len(sys.argv) > 2 else ""
    return dict(parse_qsl(query, keep_blank_values=True))


def _plugin_handle():
    try:
        return int(sys.argv[1])
    except Exception:
        return -1


def _plugin_url(params):
    return "%s?%s" % (sys.argv[0], urlencode(params))


def _finish_directory(succeeded=True):
    handle = _plugin_handle()
    if handle >= 0:
        xbmcplugin.endOfDirectory(handle, succeeded=succeeded)


def _make_item(label, action=None, is_folder=False, params=None):
    params = params or {}
    if action:
        params = dict(params)
        params["action"] = action
        url = _plugin_url(params)
    else:
        url = sys.argv[0]
    item = xbmcgui.ListItem(label=label)
    item.setArt({"icon": "DefaultAddonVideo.png", "thumb": "DefaultAddonVideo.png"})
    return url, item, is_folder


def show_menu():
    handle = _plugin_handle()
    if handle < 0:
        xbmcgui.Dialog().ok(ADDON_NAME, "Open this add-on from Kodi's video add-ons menu.")
        return

    items = [
        _make_item("Run real 5 GB TorBox file test", "auto_real_file_test"),
        _make_item("Choose TorBox cloud file to test", "browse_cloud", True),
        _make_item("Run TorBox CDN speedtest files", "cdn_speedtest"),
        _make_item("Test latest resolved TorBox URL from Kodi log", "log_url_test"),
        _make_item("View last report", "view_last_report"),
        _make_item("Open settings", "settings"),
    ]
    for url, item, is_folder in items:
        xbmcplugin.addDirectoryItem(handle, url, item, is_folder)
    xbmcplugin.setContent(handle, "files")
    xbmcplugin.endOfDirectory(handle, succeeded=True)


def _headers(token=""):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer %s" % token
    return headers


def _api_get(endpoint, token="", params=None):
    url = BASE_API + endpoint
    response = requests.get(url, params=params or {}, headers=_headers(token), timeout=25)
    try:
        payload = response.json()
    except Exception:
        response.raise_for_status()
        raise RuntimeError("TorBox returned a non-JSON response from %s" % endpoint)
    if response.status_code >= 400 or payload.get("success") is False:
        detail = payload.get("detail") or payload.get("error") or response.reason
        raise RuntimeError("TorBox API %s failed: %s" % (endpoint, detail))
    return payload


def _addon_setting_from(addon_id, key):
    try:
        addon = xbmcaddon.Addon(addon_id)
    except Exception:
        return ""
    try:
        getter = getattr(addon, "getSettingString", None)
        return (getter(key) if callable(getter) else addon.getSetting(key)).strip()
    except Exception:
        return ""


def _fenlight_profile(addon_id):
    try:
        addon = xbmcaddon.Addon(addon_id)
    except Exception:
        return ""
    try:
        return _translate_path(addon.getAddonInfo("profile"))
    except Exception:
        return ""


def _token_from_fenlight_db(addon_id):
    profile = _fenlight_profile(addon_id)
    if not profile:
        return ""
    db_path = os.path.join(profile, "databases", "settings.db")
    if not os.path.exists(db_path):
        return ""
    try:
        dbcon = sqlite3.connect(db_path)
        try:
            for key in TOKEN_SETTING_KEYS:
                stripped_key = key.replace("fenlight.", "")
                row = dbcon.execute(
                    "SELECT setting_value FROM settings WHERE setting_id = ?",
                    (stripped_key,),
                ).fetchone()
                if row and row[0] and row[0] != "empty_setting":
                    return str(row[0]).strip()
        finally:
            dbcon.close()
    except Exception as exc:
        _log("Could not read Fen Light settings DB for %s: %s" % (addon_id, exc), xbmc.LOGWARNING)
    return ""


def get_torbox_token():
    override = _setting("torbox_token", "").strip()
    if override:
        return override, "own add-on settings"

    configured_id = _setting("fenlight_addon_id", FENLIGHT_ADDON_IDS[0]).strip()
    addon_ids = []
    for addon_id in (configured_id,) + FENLIGHT_ADDON_IDS:
        if addon_id and addon_id not in addon_ids:
            addon_ids.append(addon_id)

    for addon_id in addon_ids:
        for key in TOKEN_SETTING_KEYS:
            token = _addon_setting_from(addon_id, key)
            if token and token != "empty_setting":
                return token, "%s settings" % addon_id
        token = _token_from_fenlight_db(addon_id)
        if token:
            return token, "%s settings.db" % addon_id
    raise RuntimeError("No TorBox token found. Set one here or configure TorBox in Fen Light first.")


def _progress(title, line):
    dialog = xbmcgui.DialogProgress()
    dialog.create(title, line)
    return dialog


def _progress_update(progress, percent, line1="", line2="", line3=""):
    if not progress:
        return
    if progress and progress.iscanceled():
        raise UserCancelled()
    try:
        progress.update(percent, line1, line2, line3)
    except TypeError:
        progress.update(percent, "\n".join(part for part in (line1, line2, line3) if part))


def _safe_close(progress):
    try:
        if progress:
            progress.close()
    except Exception:
        pass


def _gb(size_bytes):
    try:
        return float(size_bytes) / 1073741824.0
    except Exception:
        return 0.0


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _shorten(text, length=120):
    text = text or ""
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def _host(url):
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def cdn_label_from_url(url):
    host = _host(url).lower()
    if not host:
        return "Unknown"
    for code, label in REGION_LABELS.items():
        if ".%s." % code in host or host.startswith("%s." % code):
            return label
    if "tb-cdn.earth" in host or ".erth." in host:
        return REGION_LABELS["erth"]
    if ".hare." in host:
        return REGION_LABELS["hare"]
    if "tb-cdn" in host:
        return "TorBox CDN"
    return host


def _redact_url(url):
    if not url:
        return ""
    parsed = urlparse(url)
    query = parsed.query
    if query:
        query = re.sub(r"(?i)(token=)[^&]+", r"\1<redacted>", query)
        query = re.sub(r"(?i)(apikey=|api_key=|auth=|authorization=)[^&]+", r"\1<redacted>", query)
        return "%s://%s%s?%s" % (parsed.scheme, parsed.netloc, parsed.path, query)
    return "%s://%s%s" % (parsed.scheme, parsed.netloc, parsed.path)


def _format_bytes(size_bytes):
    if size_bytes >= 1073741824:
        return "%.2f GB" % _gb(size_bytes)
    if size_bytes >= 1048576:
        return "%.1f MB" % (float(size_bytes) / 1048576.0)
    return "%d bytes" % size_bytes


def scan_cloud_files(token, target_gb=None, limit=None, progress=None):
    target_gb = target_gb if target_gb is not None else _setting_float("target_file_gb", 5.0)
    limit = limit or _setting_int("cloud_scan_limit", 50)
    candidates = []
    total_types = len(MEDIA_ENDPOINTS)

    for type_index, media_type in enumerate(("torrent", "usenet", "webdl"), 1):
        info = MEDIA_ENDPOINTS[media_type]
        percent_base = int(((type_index - 1) / float(total_types)) * 85)
        _progress_update(progress, percent_base, "Loading %s cloud..." % media_type)
        history = _api_get(info["history"], token).get("data") or []
        folders = [item for item in history if item.get("download_finished")]
        folders = folders[:limit]
        folder_count = len(folders) or 1

        for index, folder in enumerate(folders, 1):
            folder_id = folder.get("id")
            if not folder_id:
                continue
            percent = percent_base + int((index / float(folder_count)) * (85 / float(total_types)))
            _progress_update(progress, min(percent, 90), "Scanning %s cloud..." % media_type, _shorten(folder.get("name", ""), 70))
            try:
                details = _api_get(info["explore"] % folder_id, token).get("data") or {}
            except Exception as exc:
                _log("Skipping %s folder %s: %s" % (media_type, folder_id, exc), xbmc.LOGWARNING)
                continue
            for file_item in details.get("files") or []:
                name = file_item.get("short_name") or file_item.get("name") or ""
                if not name.lower().endswith(VIDEO_EXTENSIONS):
                    continue
                size_bytes = _safe_int(file_item.get("size"))
                if size_bytes <= 0:
                    continue
                candidates.append(
                    {
                        "media_type": media_type,
                        "folder_id": str(folder_id),
                        "file_id": str(file_item.get("id")),
                        "name": name,
                        "folder_name": folder.get("name") or "",
                        "size_bytes": size_bytes,
                        "size_gb": _gb(size_bytes),
                        "distance": abs(_gb(size_bytes) - target_gb),
                    }
                )

    candidates.sort(key=lambda item: (item["distance"], -item["size_bytes"], item["name"].lower()))
    return candidates


def resolve_cloud_file(token, media_type, folder_id, file_id):
    info = MEDIA_ENDPOINTS[media_type]
    params = {"token": token, info["id_param"]: folder_id, "file_id": file_id}
    if media_type in ("usenet", "webdl"):
        params["user_ip"] = "true"
    result = _api_get(info["requestdl"], token, params=params).get("data")
    if isinstance(result, dict):
        result = result.get("url") or result.get("link") or result.get("download_url")
    if not result:
        raise RuntimeError("TorBox did not return a download URL for %s file %s,%s" % (media_type, folder_id, file_id))
    return result


def measure_url(url, max_bytes=None, max_seconds=None, progress=None, label="Download"):
    max_bytes = max_bytes or (_setting_int("test_limit_mb", 256) * 1048576)
    max_seconds = max_seconds or _setting_int("test_duration_seconds", 30)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Range": "bytes=0-%d" % (max_bytes - 1)}
    started = time.time()
    first_byte_at = None
    total = 0
    status_code = None
    response_headers = {}
    final_url = url
    error = ""

    try:
        with requests.get(url, headers=headers, stream=True, timeout=(10, 35), allow_redirects=True) as response:
            status_code = response.status_code
            response_headers = dict(response.headers)
            final_url = response.url
            response.raise_for_status()
            for chunk in response.iter_content(DEFAULT_CHUNK_SIZE):
                if not chunk:
                    continue
                if first_byte_at is None:
                    first_byte_at = time.time()
                total += len(chunk)
                elapsed = max(time.time() - started, 0.001)
                percent = min(99, int((total / float(max_bytes)) * 100))
                mbps = (total * 8.0) / elapsed / 1000000.0
                _progress_update(
                    progress,
                    percent,
                    label,
                    "%s read at %.2f Mbps" % (_format_bytes(total), mbps),
                    _shorten(_host(final_url), 80),
                )
                if total >= max_bytes or elapsed >= max_seconds:
                    break
    except UserCancelled:
        raise
    except Exception as exc:
        error = str(exc)

    finished = time.time()
    elapsed = max(finished - started, 0.001)
    mbps = (total * 8.0) / elapsed / 1000000.0
    mibs = (total / 1048576.0) / elapsed
    ttfb_ms = None if first_byte_at is None else (first_byte_at - started) * 1000.0
    return {
        "url": url,
        "final_url": final_url,
        "host": _host(final_url or url),
        "cdn": cdn_label_from_url(final_url or url),
        "status": status_code,
        "bytes": total,
        "elapsed": elapsed,
        "mbps": mbps,
        "mibs": mibs,
        "ttfb_ms": ttfb_ms,
        "headers": response_headers,
        "error": error,
    }


def _result_line(result, index=None):
    prefix = "%02d. " % index if index is not None else ""
    ttfb = "n/a" if result.get("ttfb_ms") is None else "%.0f ms" % result["ttfb_ms"]
    error = " | ERROR: %s" % result["error"] if result.get("error") else ""
    return (
        "%s[B]%s[/B] | %s | %.2f Mbps | %.2f MiB/s | %s in %.1fs | TTFB %s | HTTP %s%s"
        % (
            prefix,
            result.get("cdn") or "Unknown",
            result.get("host") or "unknown host",
            result.get("mbps") or 0.0,
            result.get("mibs") or 0.0,
            _format_bytes(result.get("bytes") or 0),
            result.get("elapsed") or 0.0,
            ttfb,
            result.get("status"),
            error,
        )
    )


def _headers_summary(headers):
    wanted = ("server", "cf-ray", "cf-cache-status", "x-cache", "content-length", "content-range", "accept-ranges")
    rows = []
    lower = {str(k).lower(): v for k, v in (headers or {}).items()}
    for key in wanted:
        value = lower.get(key)
        if value:
            rows.append("%s: %s" % (key, value))
    return rows


def _save_report(text):
    path = os.path.join(_addon_profile(), LAST_REPORT_FILE)
    with open(path, "w", encoding="utf-8") as file_obj:
        file_obj.write(text)
    return path


def _show_report(title, text):
    _save_report(text)
    dialog = xbmcgui.Dialog()
    try:
        dialog.textviewer(title, text)
    except Exception:
        dialog.ok(title, text[:1200])


def _report_header(kind, token_source=""):
    lines = [
        "[B]%s[/B]" % kind,
        "Time: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Max sample: %d MB or %d seconds" % (_setting_int("test_limit_mb", 256), _setting_int("test_duration_seconds", 30)),
    ]
    if token_source:
        lines.append("TorBox token source: %s" % token_source)
    return lines


def run_auto_real_file_test():
    progress = None
    try:
        token, token_source = get_torbox_token()
        target_gb = _setting_float("target_file_gb", 5.0)
        progress = _progress(ADDON_NAME, "Finding a %.1f GB TorBox cloud video..." % target_gb)
        candidates = scan_cloud_files(token, target_gb=target_gb, progress=progress)
        if not candidates:
            raise RuntimeError("No TorBox cloud video files were found.")
        candidate = candidates[0]
        _progress_update(progress, 90, "Resolving TorBox requestdl URL...", _shorten(candidate["name"], 80))
        resolved_url = resolve_cloud_file(token, candidate["media_type"], candidate["folder_id"], candidate["file_id"])
        _progress_update(progress, 92, "Testing resolved URL...", _shorten(_host(resolved_url), 80))
        result = measure_url(resolved_url, progress=progress, label="Real TorBox file test")
        _progress_update(progress, 100, "Done")
        _safe_close(progress)

        lines = _report_header("Real TorBox Cloud File Test", token_source)
        lines.extend(
            [
                "",
                "Selected file: %s" % candidate["name"],
                "Folder: %s" % candidate["folder_name"],
                "Type: %s" % candidate["media_type"],
                "Size: %.2f GB" % candidate["size_gb"],
                "Resolved URL: %s" % _redact_url(resolved_url),
                "",
                _result_line(result),
            ]
        )
        headers = _headers_summary(result.get("headers"))
        if headers:
            lines.extend(["", "[B]Response headers[/B]"])
            lines.extend(headers)
        lines.extend(["", "Nearby candidates scanned: %d" % len(candidates)])
        for item in candidates[:8]:
            lines.append("- %.2f GB | %s | %s" % (item["size_gb"], item["media_type"], _shorten(item["name"], 100)))
        _show_report("Real TorBox File Test", "\n".join(lines))
    except UserCancelled:
        _safe_close(progress)
        _notify("Cancelled")
    except Exception as exc:
        _safe_close(progress)
        _log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(ADDON_NAME, str(exc))
    finally:
        _finish_directory()


def browse_cloud():
    progress = None
    try:
        token, _token_source = get_torbox_token()
        target_gb = _setting_float("target_file_gb", 5.0)
        progress = _progress(ADDON_NAME, "Scanning TorBox cloud files...")
        candidates = scan_cloud_files(token, target_gb=target_gb, progress=progress)
        _safe_close(progress)
        if not candidates:
            xbmcgui.Dialog().ok(ADDON_NAME, "No TorBox cloud video files were found.")
            return _finish_directory()

        handle = _plugin_handle()
        for item in candidates[:200]:
            label = "%.2f GB | %s | %s" % (item["size_gb"], item["media_type"], item["name"])
            params = {
                "media_type": item["media_type"],
                "folder_id": item["folder_id"],
                "file_id": item["file_id"],
                "name": item["name"],
                "size_bytes": str(item["size_bytes"]),
            }
            url, list_item, is_folder = _make_item(label, "test_selected_file", False, params)
            list_item.setInfo("video", {"title": item["name"]})
            xbmcplugin.addDirectoryItem(handle, url, list_item, is_folder)
        xbmcplugin.setContent(handle, "files")
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    except UserCancelled:
        _safe_close(progress)
        _notify("Cancelled")
        _finish_directory(False)
    except Exception as exc:
        _safe_close(progress)
        _log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(ADDON_NAME, str(exc))
        _finish_directory(False)


def test_selected_file(params):
    progress = None
    try:
        token, token_source = get_torbox_token()
        media_type = params["media_type"]
        folder_id = params["folder_id"]
        file_id = params["file_id"]
        name = params.get("name") or "%s,%s" % (folder_id, file_id)
        size_bytes = _safe_int(params.get("size_bytes"))
        progress = _progress(ADDON_NAME, "Resolving selected TorBox file...")
        resolved_url = resolve_cloud_file(token, media_type, folder_id, file_id)
        result = measure_url(resolved_url, progress=progress, label="Selected TorBox file test")
        _safe_close(progress)

        lines = _report_header("Selected TorBox Cloud File Test", token_source)
        lines.extend(
            [
                "",
                "Selected file: %s" % name,
                "Type: %s" % media_type,
                "Size: %s" % (_format_bytes(size_bytes) if size_bytes else "unknown"),
                "Resolved URL: %s" % _redact_url(resolved_url),
                "",
                _result_line(result),
            ]
        )
        headers = _headers_summary(result.get("headers"))
        if headers:
            lines.extend(["", "[B]Response headers[/B]"])
            lines.extend(headers)
        _show_report("Selected TorBox File Test", "\n".join(lines))
    except UserCancelled:
        _safe_close(progress)
        _notify("Cancelled")
    except Exception as exc:
        _safe_close(progress)
        _log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(ADDON_NAME, str(exc))
    finally:
        _finish_directory()


def run_cdn_speedtest():
    progress = None
    try:
        test_length = _setting("speedtest_length", "short").strip() or "short"
        test_length = {"0": "short", "1": "long"}.get(test_length, test_length)
        region_filter = _setting("cdn_region_filter", "").strip().lower()
        params = {"test_length": test_length}
        if region_filter:
            params["region"] = region_filter
        progress = _progress(ADDON_NAME, "Loading TorBox CDN speedtest files...")
        payload = _api_get("speedtest", params=params)
        items = payload.get("data") or []
        if not items:
            raise RuntimeError("TorBox returned no CDN speedtest files.")

        results = []
        total = len(items)
        for index, item in enumerate(items, 1):
            url = item.get("url") or ""
            if not url:
                continue
            label = "%s %s" % (item.get("region") or "", item.get("name") or "")
            _progress_update(progress, int(((index - 1) / float(total)) * 100), "Testing CDN %d of %d" % (index, total), label)
            result = measure_url(url, progress=progress, label="CDN %d/%d" % (index, total))
            result["region"] = item.get("region") or ""
            result["name"] = item.get("name") or ""
            result["closest"] = bool(item.get("closest"))
            result["raw_url"] = url
            results.append(result)
        _progress_update(progress, 100, "Done")
        _safe_close(progress)

        results.sort(key=lambda item: item.get("mbps") or 0.0, reverse=True)
        lines = _report_header("TorBox CDN Speedtest Files")
        lines.extend(
            [
                "TorBox test length: %s" % test_length,
                "Region filter: %s" % (region_filter or "none"),
                "CDNs tested: %d" % len(results),
                "",
                "[B]Ranked Results[/B]",
            ]
        )
        for index, result in enumerate(results, 1):
            closest = " | closest" if result.get("closest") else ""
            region = result.get("region") or "unknown"
            name = result.get("name") or result.get("host")
            lines.append("%s | region %s | %s%s" % (_result_line(result, index), region, name, closest))
        _show_report("TorBox CDN Speedtest", "\n".join(lines))
    except UserCancelled:
        _safe_close(progress)
        _notify("Cancelled")
    except Exception as exc:
        _safe_close(progress)
        _log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(ADDON_NAME, str(exc))
    finally:
        _finish_directory()


def _read_log_file(path):
    try:
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as file_obj:
            return file_obj.read()
    except Exception:
        return ""


def latest_log_url():
    log_dir = _translate_path("special://logpath")
    paths = [
        os.path.join(log_dir, "kodi.log"),
        os.path.join(log_dir, "kodi.old.log"),
    ]
    pattern = re.compile(r"https?://[^\s<>'\"]*tb-cdn[^\s<>'\"]+", re.IGNORECASE)
    for path in paths:
        text = _read_log_file(path)
        matches = [match.rstrip(").,]") for match in pattern.findall(text)]
        playable = []
        for url in matches:
            parsed = urlparse(url)
            if parsed.path and parsed.path != "/":
                playable.append(url)
        download_urls = [url for url in playable if "/dld/" in urlparse(url).path]
        candidates = download_urls or playable
        if candidates:
            return candidates[-1], path
    return "", ""


def run_log_url_test():
    progress = None
    try:
        url, source_path = latest_log_url()
        if not url:
            raise RuntimeError("No resolved TorBox tb-cdn URL found in kodi.log or kodi.old.log.")
        progress = _progress(ADDON_NAME, "Testing latest Kodi log TorBox URL...")
        result = measure_url(url, progress=progress, label="Kodi log URL test")
        _safe_close(progress)
        lines = _report_header("Latest Kodi Log TorBox URL Test")
        lines.extend(
            [
                "Log file: %s" % source_path,
                "Resolved URL: %s" % _redact_url(url),
                "",
                _result_line(result),
            ]
        )
        headers = _headers_summary(result.get("headers"))
        if headers:
            lines.extend(["", "[B]Response headers[/B]"])
            lines.extend(headers)
        _show_report("Kodi Log URL Test", "\n".join(lines))
    except UserCancelled:
        _safe_close(progress)
        _notify("Cancelled")
    except Exception as exc:
        _safe_close(progress)
        _log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(ADDON_NAME, str(exc))
    finally:
        _finish_directory()


def view_last_report():
    try:
        path = os.path.join(_addon_profile(), LAST_REPORT_FILE)
        if not os.path.exists(path):
            xbmcgui.Dialog().ok(ADDON_NAME, "No report has been saved yet.")
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as file_obj:
            text = file_obj.read()
        _show_report("Last TorBox CDN Test Report", text)
    finally:
        _finish_directory()


def open_settings():
    _addon().openSettings()
    _finish_directory()


def run():
    params = _query_params()
    action = params.get("action", "")
    if not action:
        return show_menu()
    if action == "auto_real_file_test":
        return run_auto_real_file_test()
    if action == "browse_cloud":
        return browse_cloud()
    if action == "test_selected_file":
        return test_selected_file(params)
    if action == "cdn_speedtest":
        return run_cdn_speedtest()
    if action == "log_url_test":
        return run_log_url_test()
    if action == "view_last_report":
        return view_last_report()
    if action == "settings":
        return open_settings()
    xbmcgui.Dialog().ok(ADDON_NAME, "Unknown action: %s" % action)
    _finish_directory(False)


if __name__ == "__main__":
    run()
