# Kodi Favourites Sync

Kodi service add-on that syncs `favourites.xml` with Google Drive using OAuth refresh tokens instead of a service account.

This repository now also includes a secure browser-side auth bridge for Vercel in [auth-bridge](/Users/kalter/Documents/CODEX/kodifavsyncOauth/auth-bridge).

## What changed from the service-account version

- Keeps the working Kodi packaging and startup service behavior.
- Keeps the old-style `resources/settings.xml` schema that showed up correctly in Kodi.
- Keeps `xbmcvfs.translatePath` and plain `addon.getSetting(...)` compatibility choices.
- Switches Google auth to OAuth refresh tokens.
- Defaults remote storage to Google Drive `appDataFolder`, which avoids the service-account upload quota problem and fits a TV-hostile login flow better.

## Recommended OAuth model

The add-on itself stays non-interactive during startup sync. Initial sign-in happens through the browser auth bridge, and Kodi receives the token automatically after the user finishes the browser flow.

## Remote modes

- `appdata`
  Stores the backup in the app's hidden Google Drive app-data space. Best first choice for reliable backup/sync.
- `drive_file`
  Looks up a visible Drive file by name, optionally within `drive_folder_id`.
- `file_id`
  Uses `drive_file_id` directly.

For a first working OAuth version, `appdata` is the safest mode.

## Kodi settings

Set these in the add-on settings:

- `oauth_bridge_url`
- `remote_mode`
- `drive_file_id` if using `file_id`
- `drive_folder_id` if using `drive_file`
- `remote_filename`

Then run the add-on script `pair_google_drive.py` from Kodi to start browser pairing.

## Build the add-on zip

```sh
chmod +x build_addon.sh
./build_addon.sh
```

That produces a zip with the required Kodi structure:

```text
service.kodi.favourites.sync-0.2.0.zip
  service.kodi.favourites.sync/
    addon.xml
    service.py
    sync_now.py
    pair_google_drive.py
    README.md
    resources/
      settings.xml
      icon.png
      fanart.jpg
      lib/
```

## Test loop

After each install/update in Kodi:

1. Bump the add-on version in `addon.xml`.
2. Rebuild the zip so Kodi sees it as a new version.
3. Install the zip in Kodi.
4. Inspect the Kodi log:

```sh
rg -n "service.kodi.favourites.sync|Kodi Favourites Sync|Starting sync|Sync failed|Downloaded newer|Uploaded newer|already in sync" ~/Library/Logs/kodi.log
```

Kodi log path on macOS:

```text
/Users/kalter/Library/Logs/kodi.log
```

## Browser auth bridge

If you want automatic browser sign-in without copy-paste, use the Vercel bridge in `[auth-bridge](/Users/kalter/Documents/CODEX/kodifavsyncOauth/auth-bridge)`. The bridge design and hardening notes are summarized in `[SECURITY_MODEL.md](/Users/kalter/Documents/CODEX/kodifavsyncOauth/SECURITY_MODEL.md)`.

The intended flow is:

1. Deploy the bridge on Vercel and set `oauth_bridge_url` in Kodi.
2. In Kodi, run `pair_google_drive.py`.
3. Kodi requests a pairing code, opens the browser when possible, and polls the bridge.
4. After browser approval, Kodi stores the refresh token automatically.
