# Kodi Favourites Sync

Kodi service add-on that syncs `favourites.xml` across devices using Google Drive and an OAuth browser pairing flow.

This add-on is designed to stay simple in Kodi:
- Pair once with Google Drive
- Sync automatically on Kodi startup
- Store the remote backup in hidden Google Drive app data

## User Setup

1. Install the add-on.
2. Open add-on settings.
3. Select `Pair Google Drive now`.
4. Complete the sign-in flow in your browser or on your phone.
5. Leave `Sync on Kodi startup` enabled.

After pairing, the add-on will sync `favourites.xml` each time Kodi starts.

## How It Works

- The add-on syncs on Kodi startup only.
- Remote storage uses Google Drive app data by default.
- The backup is not intended to be visible in the normal Drive file list.
- Sync behavior is last-write-wins.

This means the newest `favourites.xml` seen during sync becomes the remote version.

If a device downloads a newer favourites file during startup, Kodi may not always reflect the change in the UI until favourites are reopened or Kodi is restarted again.

## Settings

Visible settings are intentionally minimal:
- `Pair Google Drive now`
- `Sync on Kodi startup`

The add-on also keeps internal OAuth and storage settings for compatibility, but normal users do not need to manage them directly.

## OAuth Bridge

Browser sign-in is handled through the Vercel auth bridge in [auth-bridge](/Users/kalter/Documents/CODEX/kodifavsyncOauth/auth-bridge).

Current bridge URL:
- `https://auth-bridge-rho.vercel.app`

Security notes for the bridge are documented in [SECURITY_MODEL.md](/Users/kalter/Documents/CODEX/kodifavsyncOauth/SECURITY_MODEL.md).

## Build

```sh
chmod +x build_addon.sh
./build_addon.sh
```

The build output is a Kodi-ready zip with a single top-level folder:

```text
service.kodi.favourites.sync-<version>.zip
  service.kodi.favourites.sync/
    addon.xml
    service.py
    plugin.py
    sync_now.py
    pair_google_drive.py
    README.md
    resources/
      settings.xml
      icon.png
      fanart.jpg
      lib/
```

## Publish

Build the zip in:
- `/Users/kalter/Documents/CODEX/kodifavsyncOauth`

Then copy the zip into:
- `/Users/kalter/Documents/CODEX/kodirepo/`

Then run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /Users/kalter/Documents/CODEX/kodirepo/scripts/publish_addon_update.py
```

Do not use the full repo builder unless explicitly needed.

## Logs

macOS Kodi log:

```text
/Users/kalter/Library/Logs/kodi.log
```

Android / Fire TV style Kodi log:

```text
/Volumes/internal/Android/data/net.kodinerds.maven.kodi21/files/.kodi/temp/kodi.log
```

Useful log filter:

```sh
rg -n "service.kodi.favourites.sync|Kodi Favourites Sync|Starting sync|Sync failed|download|upload|pair|oauth|bridge" ~/Library/Logs/kodi.log
```

## Notes For Development

- Add-on type remains `xbmc.service`
- Startup entry point is `service.py`
- Settings schema uses old-style `resources/settings.xml`
- Kodi paths should use `xbmcvfs.translatePath`
- Settings access should go through the compat layer
- Bump the add-on version on every rebuild you want Kodi to install
