from resources.lib.drive_api import DriveError
from resources.lib.kodi_compat import (
    get_addon,
    get_monitor,
    get_setting_string,
    log,
    notify,
    open_browser,
    progress_dialog,
    show_ok_dialog,
)
from resources.lib.oauth_bridge import OAuthBridgeClient
from resources.lib.sync_engine import persist_oauth_tokens


def pair_google_drive(addon=None):
    addon = addon or get_addon()
    bridge_url = get_setting_string(addon, "oauth_bridge_url", "")
    client = OAuthBridgeClient(bridge_url)
    monitor = get_monitor()

    try:
        pairing = client.create_pairing()
    except Exception as exc:  # pylint: disable=broad-except
        message = "Could not start browser pairing: %s" % exc
        log(message, level="error", addon=addon)
        show_ok_dialog("Kodi Favourites Sync", message)
        return False

    verification_uri = pairing.get("verification_uri_complete") or pairing.get("verification_url") or bridge_url
    user_code = pairing.get("user_code", "")
    pairing_id = pairing.get("pairing_id", "")
    poll_token = pairing.get("poll_token", "")
    interval = max(2, int(pairing.get("interval", 5)))
    expires_in = max(interval, int(pairing.get("expires_in", 600)))

    opened = open_browser(verification_uri)
    dialog = progress_dialog("Kodi Favourites Sync", "Open the browser and approve Google Drive access.")
    try:
        for elapsed in range(0, expires_in + interval, interval):
            percent = min(100, int((elapsed * 100) / max(1, expires_in)))
            dialog.update(
                percent,
                "Code: %s" % user_code,
                "URL: %s" % verification_uri,
                "Browser opened automatically." if opened else "Open the URL on another device if needed.",
            )
            if dialog.iscanceled():
                notify(addon, "Kodi Favourites Sync", "Google Drive pairing cancelled")
                return False

            status = client.pairing_status(pairing_id, poll_token)
            state = status.get("status")
            if state == "authorized":
                tokens = client.claim_pairing(pairing_id, poll_token)
                persist_oauth_tokens(addon, tokens)
                notify(addon, "Kodi Favourites Sync", "Google Drive connected successfully")
                return True
            if state == "failed":
                raise DriveError(status.get("last_error") or "Browser pairing failed")
            if monitor.waitForAbort(interval):
                return False
    except Exception as exc:  # pylint: disable=broad-except
        message = "Google Drive pairing failed: %s" % exc
        log(message, level="error", addon=addon)
        show_ok_dialog("Kodi Favourites Sync", message)
        return False
    finally:
        dialog.close()

    show_ok_dialog(
        "Kodi Favourites Sync",
        "The Google sign-in code expired before authorization finished. Start pairing again.",
    )
    return False


def pairing_entrypoint():
    pair_google_drive(get_addon())
