# Kodi Favourites Sync

Kodi service add-on that syncs `favourites.xml` across devices using Google
Drive and a browser-based OAuth pairing flow.

This README is written for maintainers and future agents first, while still
keeping the user setup and security model in one place.

## What This Addon Does

This is the simpler single-target sync variant in the main repo.

Its job is intentionally narrow:

- pair once with Google Drive
- sync `favourites.xml` on Kodi startup
- optionally run `Sync now`
- store the backup in hidden Google Drive app data

## Maintainer File Map

- `addon.xml`
  Kodi metadata and entrypoints.
- `plugin.py`
  Settings-driven `RunPlugin(...)` routes for pairing and manual sync.
- `pair_google_drive.py`
  Direct entrypoint that launches the pairing flow.
- `sync_now.py`
  Direct entrypoint for a manual sync run.
- `service.py`
  Startup service entrypoint used on Kodi boot.
- `resources/settings.xml`
  Visible and internal addon settings.
- `resources/lib/pairing_flow.py`
  Pairing orchestration, dialogs, polling, and token claim.
- `resources/lib/pairing_dialog.py`
  Pairing code and QR dialog UI.
- `resources/lib/oauth_bridge.py`
  HTTP client for the external auth bridge.
- `resources/lib/drive_api.py`
  Google Drive HTTP and storage helpers.
- `resources/lib/sync_engine.py`
  Compares local vs remote state and performs upload or download.
- `resources/lib/state.py`
  Persists OAuth and sync state in Kodi settings.
- `resources/lib/kodi_compat.py`
  Kodi-version-safe wrappers for logging, settings, dialogs, and filesystem
  calls.

## Runtime Flow

There are three main ways this addon runs:

1. Kodi startup
   `service.py` calls `service_main()` in `sync_engine.py`.
2. Pairing
   `plugin.py?action=pair_google_drive` or `pair_google_drive.py` enters the
   browser pairing flow.
3. Manual sync
   `plugin.py?action=sync_now` or `sync_now.py` runs the sync engine on demand.

## User Setup

1. Install the add-on.
2. Open add-on settings.
3. Select `Pair Google Drive now`.
4. Complete the sign-in flow in your browser or on your phone.
5. Leave `Sync on Kodi startup` enabled.

After pairing, the add-on syncs `favourites.xml` each time Kodi starts.

## How Sync Decides What To Do

- Remote storage uses Google Drive app data by default.
- The backup is not intended to be visible in the normal Drive file list.
- Sync behavior is last-write-wins.

That means the newest `favourites.xml` seen during a sync run becomes the
winning version.

If a device downloads a newer favourites file during startup, Kodi may not
always reflect the change in the UI until favourites are reopened or Kodi is
restarted again.

## Visible Settings

- `Pair Google Drive now`
- `Sync on Kodi startup`

The add-on also keeps internal OAuth and storage settings for compatibility, so
not every stored value is meant for direct user editing.

## OAuth Bridge

Browser sign-in is handled through the Vercel auth bridge.

Current bridge URL:

- `https://auth-bridge-rho.vercel.app`

## Security Model

The add-on does not contain a Google client secret.

Google sign-in happens in a browser through the auth bridge. Kodi shows a
pairing code, the user completes Google sign-in in the browser, and the bridge
returns tokens through a short-lived pairing record.

Important security properties:

- no Google client secret inside Kodi
- no manual token copy-paste flow
- one-time token handoff from the bridge to Kodi
- short-lived pairing sessions with explicit expiry
- no public token refresh endpoint

Kodi stores OAuth state in settings after pairing:

- `oauth_refresh_token`
- `oauth_refresh_secret`
- `oauth_access_token`
- `oauth_scope`
- token expiry metadata

## Pairing Flow

1. In Kodi, run `Pair Google Drive now`.
2. The add-on asks the bridge for a pairing session.
3. Kodi shows a code and activation URL.
4. The user signs into Google in a browser.
5. Google redirects back to the bridge.
6. The bridge marks the pairing as authorized.
7. Kodi claims the token payload and stores it locally.

## Future-Agent Guard Rails

- Keep browser OAuth on the bridge side. Do not move the Google client secret
  into Kodi.
- Keep this addon focused on `favourites.xml`; if the work needs multiple
  categories or custom targets, that belongs in the newer sync-tool family.
- If startup sync breaks, inspect `sync_engine.py` and state handling before
  changing the pairing flow.
