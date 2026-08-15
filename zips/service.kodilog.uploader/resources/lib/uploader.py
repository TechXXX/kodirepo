from __future__ import absolute_import

import datetime
import hashlib
import io
import json
import os
import platform
import re
import socket
import sys
import time
import traceback
import uuid
import xml.etree.ElementTree as ET
import zipfile

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
    import xbmcvfs
except Exception:  # pragma: no cover - lets compile/tests run outside Kodi.
    xbmc = None
    xbmcaddon = None
    xbmcgui = None
    xbmcvfs = None

try:
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - Python 2 fallback.
    from urllib2 import HTTPError, Request, URLError, urlopen


ADDON_ID = "service.kodilog.uploader"
DEFAULT_TARGET_ADDON_ID = "plugin.video.fenlight.kodienglish"
DEFAULT_SERVER_URL = "https://logs.basaio.duckdns.org/upload"
DEFAULT_AUTH_TOKEN = "27c45ed5c5c31c47c1f22f230c350604ce0c6a77418ced1d158543d87bb82548"
DEFAULT_MAX_LOG_KB = 4096
DEVICE_NAME_PLACEHOLDERS = ("", "shield", "kodi")
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
DIAGNOSTIC_ADDONS = (
    ("plugin.video.fenlight.kodienglish", "Fen Light English"),
    ("plugin.video.fenlight.patched", "Fen Light Patched"),
    ("script.module.cocoscrapers", "CocoScrapers"),
    ("script.module.cocoscrapers.kodienglish", "CocoScrapers KodiEnglish"),
    ("script.module.magneto", "Magneto"),
    ("script.module.resolveurl", "ResolveURL"),
    ("plugin.video.themoviedb.helper.patched.kodienglish", "TMDb Helper Patched English"),
    ("plugin.video.themoviedb.helper.patched", "TMDb Helper Patched"),
    ("plugin.video.themoviedb.helper", "TMDb Helper"),
    ("service.subtitles.a4ksubtitles.patched", "a4kSubtitles Patched"),
    ("service.subtitles.a4ksubtitles", "a4kSubtitles"),
    ("repository.kodienglish", "KodiEnglish Repository"),
    ("repository.dutchtech", "DutchTech Repository"),
)
FENLIGHT_DIAGNOSTIC_SETTINGS = (
    "provider.external",
    "external_scraper.module",
    "external_scraper.name",
)
FENLIGHT_PATTERNS = (
    "fen light",
    "fenlight",
    "plugin.video.fenlight",
    "###fen",
)
ERROR_PATTERNS = ("error", "exception", "traceback", "failed", "failure")

SENSITIVE_SETTING_HINTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "apikey",
    "api_key",
    "auth",
    "authorization",
    "username",
    "user_name",
    "easynews",
    "debrid",
    "torbox",
    "trakt",
    "rd.",
    "pm.",
    "ad.",
)

REDACTION_PATTERNS = (
    (
        re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@"),
        r"\1[REDACTED]@",
    ),
    (
        re.compile(r"(?i)\b(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]+"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(access_token|refresh_token|token|api[_-]?key|apikey|key|"
            r"secret|client_secret|password|passwd|username|user)\s*=\s*([^&\s]+)"
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(
            r"""(?ix)
            (["']?(?:access_token|refresh_token|token|api[_-]?key|apikey|key|
            secret|client_secret|password|passwd|username|user)["']?\s*[:=]\s*["'])
            ([^"']+)
            (["'])
            """
        ),
        r"\1[REDACTED]\3",
    ),
)


class UploadResult(object):
    def __init__(self, success, message, status=None, response=None, upload_id=None):
        self.success = success
        self.message = message
        self.status = status
        self.response = response or {}
        self.upload_id = upload_id


def get_addon(addon_id=ADDON_ID):
    if xbmcaddon is None:
        return None
    try:
        return xbmcaddon.Addon(addon_id)
    except Exception:
        return None


def log(message, level="info"):
    prefix = "[Kodi Log Uploader] "
    if xbmc is None:
        print(prefix + str(message))
        return
    kodi_level = getattr(xbmc, "LOGINFO", 1)
    if level == "warning":
        kodi_level = getattr(xbmc, "LOGWARNING", 2)
    elif level == "error":
        kodi_level = getattr(xbmc, "LOGERROR", 4)
    try:
        xbmc.log(prefix + str(message), kodi_level)
    except Exception:
        pass


def notify(message, error=False):
    if xbmcgui is None:
        log(message, level="error" if error else "info")
        return
    try:
        xbmcgui.Dialog().notification(
            "Kodi Log Uploader",
            message,
            getattr(xbmcgui, "NOTIFICATION_ERROR", "") if error else "",
            5000,
        )
    except Exception:
        log(message, level="error" if error else "info")


def show_dialog(message, error=False):
    if xbmcgui is None:
        notify(message, error=error)
        return
    try:
        xbmcgui.Dialog().ok("Kodi Log Uploader", message)
    except Exception:
        notify(message, error=error)


def get_setting(addon, setting_id, default=""):
    if addon is None:
        return default
    try:
        value = addon.getSetting(setting_id)
        if value in (None, ""):
            return default
        return value
    except Exception:
        return default


def set_setting_string(addon, setting_id, value):
    if addon is None:
        return False
    try:
        if hasattr(addon, "setSettingString"):
            addon.setSettingString(setting_id, value)
        else:
            addon.setSetting(setting_id, value)
        return True
    except Exception as exc:
        log("Could not set %s: %s" % (setting_id, exc), level="warning")
        return False


def ensure_default_settings(addon):
    if get_setting(addon, "server_url", ""):
        pass
    elif set_setting_string(addon, "server_url", DEFAULT_SERVER_URL):
        log("Filled default log receiver URL.")
    if not get_setting(addon, "auth_token", "") and set_setting_string(addon, "auth_token", DEFAULT_AUTH_TOKEN):
        log("Filled default upload token.")
    if get_setting(addon, "defaults.tv_safe_v1", "") != "true":
        if set_setting_string(addon, "auto_error_upload", "false"):
            log("Applied TV-safe default: disabled error-triggered uploads.")
        set_setting_string(addon, "defaults.tv_safe_v1", "true")
    configured = get_setting(addon, "device_name", "").strip()
    if configured.lower() not in DEVICE_NAME_PLACEHOLDERS:
        return
    detected = detected_device_name()
    if detected and detected.lower() != configured.lower() and set_setting_string(addon, "device_name", detected):
        log("Filled local device name: %s" % detected)


def setting_bool(addon, setting_id, default=False):
    value = get_setting(addon, setting_id, "true" if default else "false")
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def setting_int(addon, setting_id, default, minimum=None, maximum=None):
    try:
        value = int(float(get_setting(addon, setting_id, str(default))))
    except Exception:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def translate_path(path):
    if xbmcvfs is not None and hasattr(xbmcvfs, "translatePath"):
        try:
            return xbmcvfs.translatePath(path)
        except Exception:
            pass
    if xbmc is not None and hasattr(xbmc, "translatePath"):
        try:
            return xbmc.translatePath(path)
        except Exception:
            pass
    return path


def kodi_info_label(label):
    if xbmc is None:
        return ""
    try:
        return xbmc.getInfoLabel(label)
    except Exception:
        return ""


def kodi_cond_visibility(condition):
    if xbmc is None:
        return False
    try:
        return bool(xbmc.getCondVisibility(condition))
    except Exception:
        return False


def now_utc():
    try:
        value = datetime.datetime.now(datetime.timezone.utc)
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:  # pragma: no cover - defensive fallback for odd Kodi builds.
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sanitize_device_name(name):
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "")).strip(".-")
    return name[:80] or ""


def kodi_setting_value(setting_id):
    for special_path in ("special://profile/guisettings.xml", "special://masterprofile/guisettings.xml"):
        path = translate_path(special_path)
        if not path or not os.path.exists(path):
            continue
        try:
            setting = ET.parse(path).find(".//setting[@id='%s']" % setting_id)
            if setting is not None and setting.text:
                return setting.text
        except Exception as exc:
            log("Could not read Kodi setting %s from %s: %s" % (setting_id, path, exc), level="warning")
    return ""


def kodi_services_device_name():
    return kodi_setting_value("services.devicename")


def detected_device_name():
    candidates = (
        kodi_services_device_name(),
        kodi_info_label("System.FriendlyName"),
        socket.gethostname(),
        platform.node(),
        kodi_info_label("System.ProfileName"),
    )
    ignored = ("", "kodi", "localhost", "localhost.localdomain", "unknown", "none")
    for candidate in candidates:
        name = sanitize_device_name(candidate)
        if name and name.lower() not in ignored:
            return name
    return "kodi"


def safe_device_name(addon):
    configured = sanitize_device_name(get_setting(addon, "device_name", ""))
    if configured and configured.lower() not in DEVICE_NAME_PLACEHOLDERS:
        return configured
    return detected_device_name()


def target_addon_id(addon):
    value = get_setting(addon, "target_addon_id", DEFAULT_TARGET_ADDON_ID)
    return value.strip() or DEFAULT_TARGET_ADDON_ID


def redact_text(text):
    if not text:
        return ""
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    redacted = _redact_sensitive_xml_settings(redacted)
    return redacted


def _redact_sensitive_xml_settings(text):
    setting_re = re.compile(
        r'(<setting\b[^>]*\bid=["\']([^"\']+)["\'][^>]*\bvalue=["\'])([^"\']*)(["\'][^>]*/?>)',
        re.IGNORECASE,
    )

    def replace(match):
        setting_id = match.group(2).lower()
        if any(hint in setting_id for hint in SENSITIVE_SETTING_HINTS):
            return match.group(1) + "[REDACTED]" + match.group(4)
        return match.group(0)

    return setting_re.sub(replace, text)


def read_tail(path, max_kb):
    max_bytes = max(1, int(max_kb)) * 1024
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes), os.SEEK_SET)
            data = handle.read(max_bytes)
    except Exception as exc:
        return None, "Could not read %s: %s" % (path, exc)
    text = data.decode("utf-8", "replace")
    if len(data) == max_bytes:
        text = "[truncated to last %s KB]\n%s" % (max_kb, text)
    return redact_text(text), None


def read_text_file(path, max_kb=512):
    text, error = read_tail(path, max_kb)
    if error:
        return None
    return text


def list_existing_log_files(log_dir):
    names = []
    preferred = ("kodi.log", "kodi.old.log")
    for name in preferred:
        path = os.path.join(log_dir, name)
        if os.path.exists(path):
            names.append(name)
    try:
        for name in os.listdir(log_dir):
            lower = name.lower()
            if name in names:
                continue
            if lower.startswith("kodi_crashlog") and lower.endswith(".log"):
                names.append(name)
            elif lower.startswith("kodi_stacktrace") and lower.endswith(".log"):
                names.append(name)
    except Exception as exc:
        log("Could not list log directory %s: %s" % (log_dir, exc), level="warning")
    return names[:8]


def target_addon_details(addon_id):
    details = {"id": addon_id, "installed": False}
    target = get_addon(addon_id)
    if target is None:
        return details
    details["installed"] = True
    for key in ("name", "version", "path", "profile"):
        try:
            details[key] = target.getAddonInfo(key)
        except Exception:
            details[key] = ""
    details["path_translated"] = translate_path(details.get("path", ""))
    details["profile_translated"] = translate_path(details.get("profile", ""))
    return details


def addon_snapshot(addon_id, label=None):
    addon = get_addon(addon_id)
    snapshot = {
        "id": addon_id,
        "label": label or addon_id,
        "installed": addon is not None,
        "enabled": kodi_cond_visibility("System.HasAddon(%s)" % addon_id),
    }
    if addon is None:
        return snapshot
    for key in ("name", "version", "path", "profile"):
        try:
            snapshot[key] = addon.getAddonInfo(key)
        except Exception:
            snapshot[key] = ""
    return snapshot


def read_addon_settings(addon_id, setting_ids):
    values = {}
    addon = get_addon(addon_id)
    if addon is None:
        return values
    for setting_id in setting_ids:
        values[setting_id] = get_setting(addon, setting_id, "")
    return values


def current_skin_snapshot():
    skin_id = (
        kodi_setting_value("lookandfeel.skin")
        or kodi_info_label("Skin.String(skin.id)")
        or kodi_info_label("System.CurrentSkin")
    )
    addon = get_addon(skin_id) if skin_id else None
    snapshot = {
        "id": skin_id,
        "name": kodi_info_label("System.CurrentSkin"),
        "theme": kodi_setting_value("lookandfeel.skintheme"),
        "colors": kodi_setting_value("lookandfeel.skincolors"),
    }
    if addon is not None:
        for key in ("name", "version"):
            try:
                snapshot[key] = addon.getAddonInfo(key)
            except Exception:
                pass
    return snapshot


def kodi_environment_snapshot(device_name):
    return {
        "device_name": device_name,
        "services_device_name": kodi_services_device_name(),
        "friendly_name": kodi_info_label("System.FriendlyName"),
        "profile_name": kodi_info_label("System.ProfileName"),
        "kodi_version": kodi_info_label("System.BuildVersion"),
        "kodi_build_date": kodi_info_label("System.BuildDate"),
        "skin": current_skin_snapshot(),
        "language": kodi_info_label("System.Language"),
        "region": kodi_info_label("System.Region"),
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "python_version": sys.version,
    }


def diagnostics_summary(addon, device_name, target_details):
    target_id = target_addon_id(addon)
    addons = [addon_snapshot(addon_id, label) for addon_id, label in DIAGNOSTIC_ADDONS]
    installed = {item["id"]: item for item in addons}
    fenlight_settings = read_addon_settings(target_id, FENLIGHT_DIAGNOSTIC_SETTINGS)

    def any_installed(*addon_ids):
        return any(installed.get(addon_id, {}).get("installed", False) for addon_id in addon_ids)

    def any_enabled(*addon_ids):
        return any(installed.get(addon_id, {}).get("enabled", False) for addon_id in addon_ids)

    return {
        "created_at_utc": now_utc(),
        "target_addon_id": target_id,
        "target_addon": target_details,
        "environment": kodi_environment_snapshot(device_name),
        "addons": addons,
        "dependency_check": {
            "fen_light_installed": bool(target_details.get("installed")),
            "fen_light_variant_installed": any_installed(
                "plugin.video.fenlight.kodienglish",
                "plugin.video.fenlight.patched",
            ),
            "cocoscrapers_installed": any_installed(
                "script.module.cocoscrapers",
                "script.module.cocoscrapers.kodienglish",
            ),
            "magneto_installed": installed.get("script.module.magneto", {}).get("installed", False),
            "resolveurl_installed": installed.get("script.module.resolveurl", {}).get("installed", False),
            "tmdb_helper_installed": any_installed(
                "plugin.video.themoviedb.helper.patched.kodienglish",
                "plugin.video.themoviedb.helper.patched",
                "plugin.video.themoviedb.helper",
            ),
            "a4k_installed": any_installed(
                "service.subtitles.a4ksubtitles.patched",
                "service.subtitles.a4ksubtitles",
            ),
            "repository_kodienglish_installed": installed.get("repository.kodienglish", {}).get("installed", False),
            "repository_kodienglish_enabled": installed.get("repository.kodienglish", {}).get("enabled", False),
            "repository_variant_enabled": any_enabled("repository.kodienglish", "repository.dutchtech"),
            "external_scraper_enabled": fenlight_settings.get("provider.external", ""),
            "external_scraper_module": fenlight_settings.get("external_scraper.module", ""),
            "external_scraper_name": fenlight_settings.get("external_scraper.name", ""),
        },
        "fenlight_settings": fenlight_settings,
    }


def diagnostic_value(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return "yes" if value.lower() == "true" else "no"
    if value in (None, ""):
        return ""
    return str(value)


def diagnostics_summary_text(summary):
    dependency = summary.get("dependency_check", {})
    environment = summary.get("environment", {})
    skin = environment.get("skin", {})
    lines = [
        "Kodi Log Uploader diagnostics summary",
        "Created UTC: %s" % summary.get("created_at_utc", ""),
        "",
        "Environment",
        "Device name: %s" % environment.get("device_name", ""),
        "Kodi Services device name: %s" % environment.get("services_device_name", ""),
        "Kodi version: %s" % environment.get("kodi_version", ""),
        "Kodi build date: %s" % environment.get("kodi_build_date", ""),
        "Skin: %s %s (%s)" % (skin.get("name", ""), skin.get("version", ""), skin.get("id", "")),
        "Language: %s" % environment.get("language", ""),
        "Region: %s" % environment.get("region", ""),
        "Platform: %s" % environment.get("platform", ""),
        "",
        "Dependency Check",
        "Fen Light installed: %s" % diagnostic_value(dependency.get("fen_light_installed")),
        "Fen Light variant installed: %s" % diagnostic_value(dependency.get("fen_light_variant_installed")),
        "CocoScrapers installed: %s" % diagnostic_value(dependency.get("cocoscrapers_installed")),
        "Magneto installed: %s" % diagnostic_value(dependency.get("magneto_installed")),
        "ResolveURL installed: %s" % diagnostic_value(dependency.get("resolveurl_installed")),
        "TMDb Helper installed: %s" % diagnostic_value(dependency.get("tmdb_helper_installed")),
        "a4k installed: %s" % diagnostic_value(dependency.get("a4k_installed")),
        "KodiEnglish repository installed: %s" % diagnostic_value(dependency.get("repository_kodienglish_installed")),
        "KodiEnglish repository enabled: %s" % diagnostic_value(dependency.get("repository_kodienglish_enabled")),
        "Repository variant enabled: %s" % diagnostic_value(dependency.get("repository_variant_enabled")),
        "External scraper enabled: %s" % diagnostic_value(dependency.get("external_scraper_enabled")),
        "External scraper module: %s" % diagnostic_value(dependency.get("external_scraper_module")),
        "External scraper name: %s" % diagnostic_value(dependency.get("external_scraper_name")),
        "",
        "Selected Add-ons",
    ]
    for item in summary.get("addons", []):
        lines.append(
            "- {label}: installed={installed}, enabled={enabled}, version={version}, id={id}".format(
                label=item.get("label", item.get("id", "")),
                installed=diagnostic_value(item.get("installed")),
                enabled=diagnostic_value(item.get("enabled")),
                version=item.get("version", ""),
                id=item.get("id", ""),
            )
        )
    return "\n".join(lines) + "\n"


def collect_log_entries(addon):
    log_dir = translate_path("special://logpath/")
    max_log_kb = setting_int(addon, "max_log_kb", DEFAULT_MAX_LOG_KB, minimum=64, maximum=16384)
    entries = []
    errors = []
    for name in list_existing_log_files(log_dir):
        path = os.path.join(log_dir, name)
        text, error = read_tail(path, max_log_kb)
        if error:
            errors.append(error)
            continue
        entries.append({"name": name, "path": path, "text": text or ""})
    return log_dir, entries, errors


def fenlight_excerpt(entries):
    selected = []
    for entry in entries:
        for line in entry["text"].splitlines():
            lower = line.lower()
            fen_hit = any(pattern in lower for pattern in FENLIGHT_PATTERNS)
            error_hit = any(pattern in lower for pattern in ERROR_PATTERNS)
            if fen_hit or error_hit:
                selected.append("[%s] %s" % (entry["name"], line))
    if not selected:
        return "No Fen Light or error lines found in collected logs.\n"
    return "\n".join(selected[-1000:]) + "\n"


def collect_extra_files(addon, target_details):
    extras = []
    addon_path = target_details.get("path_translated") or ""
    profile_path = target_details.get("profile_translated") or ""
    addon_xml = os.path.join(addon_path, "addon.xml") if addon_path else ""
    if addon_xml and os.path.exists(addon_xml):
        text = read_text_file(addon_xml, 256)
        if text:
            extras.append(("fenlight/addon.xml", text))
    if setting_bool(addon, "include_fenlight_settings", True):
        settings_xml = os.path.join(profile_path, "settings.xml") if profile_path else ""
        if settings_xml and os.path.exists(settings_xml):
            text = read_text_file(settings_xml, 512)
            if text:
                extras.append(("fenlight/settings.redacted.xml", redact_text(text)))
    return extras


def collect_archive(reason):
    addon = get_addon()
    upload_id = uuid.uuid4().hex
    target_id = target_addon_id(addon)
    target_details = target_addon_details(target_id)
    log_dir, logs, read_errors = collect_log_entries(addon)
    device_name = safe_device_name(addon)
    diagnostics = diagnostics_summary(addon, device_name, target_details)
    manifest = {
        "upload_id": upload_id,
        "created_at_utc": now_utc(),
        "reason": reason,
        "device_name": device_name,
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": sys.version,
        "kodi_version": kodi_info_label("System.BuildVersion"),
        "kodi_build_date": kodi_info_label("System.BuildDate"),
        "log_dir": log_dir,
        "target_addon": target_details,
        "read_errors": read_errors,
        "collected_logs": [{"name": item["name"], "path": item["path"]} for item in logs],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        archive.writestr("diagnostics/summary.json", json.dumps(diagnostics, indent=2, sort_keys=True))
        archive.writestr("diagnostics/summary.txt", diagnostics_summary_text(diagnostics))
        archive.writestr("logs/fenlight_excerpt.log", fenlight_excerpt(logs))
        for entry in logs:
            archive.writestr("logs/%s" % entry["name"], entry["text"])
        for archive_name, text in collect_extra_files(addon, target_details):
            archive.writestr(archive_name, text)
    data = buffer.getvalue()
    manifest["archive_sha256"] = hashlib.sha256(data).hexdigest()
    manifest["archive_bytes"] = len(data)
    return data, manifest


def normalize_upload_url(url):
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"(?i)^https?://", url):
        url = "https://" + url
    trimmed = url.rstrip("/")
    if not trimmed.lower().endswith("/upload"):
        trimmed += "/upload"
    return trimmed


def upload_archive(data, manifest):
    addon = get_addon()
    ensure_default_settings(addon)
    server_url = normalize_upload_url(get_setting(addon, "server_url", DEFAULT_SERVER_URL))
    token = get_setting(addon, "auth_token", "")
    if not server_url:
        return UploadResult(False, "Server URL is not configured.", upload_id=manifest.get("upload_id"))
    if not token:
        return UploadResult(False, "Upload token is not configured.", upload_id=manifest.get("upload_id"))
    if len(data) > MAX_ARCHIVE_BYTES:
        return UploadResult(
            False,
            "Archive is too large: %.1f MB" % (len(data) / 1024.0 / 1024.0),
            upload_id=manifest.get("upload_id"),
        )

    headers = {
        "Content-Type": "application/zip",
        "User-Agent": "KodiLogUploader/0.1",
        "X-Kodi-Log-Token": token,
        "X-Device-ID": manifest.get("device_name", "kodi"),
        "X-Upload-Reason": manifest.get("reason", "manual"),
        "X-Upload-ID": manifest.get("upload_id", ""),
    }
    request = Request(server_url, data=data, headers=headers)
    try:
        response = urlopen(request, timeout=30)
        status = getattr(response, "status", None) or response.getcode()
        body = response.read().decode("utf-8", "replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        return UploadResult(False, "Server rejected upload: HTTP %s %s" % (exc.code, body[:200]), status=exc.code)
    except URLError as exc:
        return UploadResult(False, "Upload failed: %s" % exc, upload_id=manifest.get("upload_id"))
    except Exception as exc:
        return UploadResult(False, "Upload failed: %s" % exc, upload_id=manifest.get("upload_id"))

    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {"raw": body}
    if status < 200 or status >= 300:
        return UploadResult(False, "Upload failed: HTTP %s" % status, status=status, response=payload)
    return UploadResult(
        True,
        "Uploaded %s KB" % max(1, int(len(data) / 1024)),
        status=status,
        response=payload,
        upload_id=manifest.get("upload_id"),
    )


def run_upload(reason="manual", interactive=False):
    ensure_default_settings(get_addon())
    try:
        data, manifest = collect_archive(reason)
        result = upload_archive(data, manifest)
    except Exception:
        log("Upload crashed: %s" % traceback.format_exc(), level="error")
        result = UploadResult(False, "Upload crashed. Check kodi.log for details.")

    if result.success:
        remote_id = result.response.get("remote_id") or result.upload_id or ""
        message = "Logs uploaded%s." % (": %s" % remote_id if remote_id else "")
        log(message)
        if interactive:
            show_dialog(message)
    else:
        log(result.message, level="error")
        if interactive:
            show_dialog(result.message, error=True)
    return result


def manual_upload_entrypoint():
    run_upload("manual", interactive=True)


def recent_error_signature(addon):
    log_dir = translate_path("special://logpath/")
    path = os.path.join(log_dir, "kodi.log")
    if not os.path.exists(path):
        return ""
    text, error = read_tail(path, 512)
    if error or not text:
        return ""
    matches = []
    for line in text.splitlines()[-500:]:
        lower = line.lower()
        fen_hit = any(pattern in lower for pattern in FENLIGHT_PATTERNS)
        error_hit = any(pattern in lower for pattern in ERROR_PATTERNS)
        if fen_hit and error_hit:
            matches.append(line)
    if not matches:
        return ""
    joined = "\n".join(matches[-40:])
    return hashlib.sha256(joined.encode("utf-8", "replace")).hexdigest()


def service_main():
    addon = get_addon()
    ensure_default_settings(addon)
    if xbmc is None:
        log("Kodi runtime is unavailable; service loop not started.", level="warning")
        return

    monitor = xbmc.Monitor()
    startup_delay = setting_int(addon, "startup_delay_seconds", 45, minimum=0, maximum=600)
    if startup_delay and monitor.waitForAbort(startup_delay):
        return

    last_auto_upload = 0
    baseline_signature = recent_error_signature(addon)

    if setting_bool(addon, "upload_on_startup", True):
        result = run_upload("startup", interactive=False)
        if result.success:
            last_auto_upload = time.time()
        baseline_signature = recent_error_signature(addon)

    interval_minutes = setting_int(addon, "error_scan_interval_minutes", 5, minimum=1, maximum=1440)
    min_gap_minutes = setting_int(addon, "min_auto_upload_gap_minutes", 60, minimum=5, maximum=1440)
    log(
        "Service started. Startup upload: %s. Error-triggered uploads: %s. Error scan interval: %s minutes"
        % (
            setting_bool(addon, "upload_on_startup", True),
            setting_bool(addon, "auto_error_upload", False),
            interval_minutes,
        )
    )

    while not monitor.abortRequested():
        if monitor.waitForAbort(interval_minutes * 60):
            break
        addon = get_addon()
        if not setting_bool(addon, "auto_error_upload", False):
            continue
        signature = recent_error_signature(addon)
        if not signature or signature == baseline_signature:
            continue
        now = time.time()
        if now - last_auto_upload < min_gap_minutes * 60:
            baseline_signature = signature
            log("Detected error signature but skipped upload due to throttle.")
            continue
        result = run_upload("auto-error", interactive=False)
        if result.success:
            last_auto_upload = now
        baseline_signature = signature

    log("Service stopped.")
