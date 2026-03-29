# Kodi Favourites Sync

Kodi service add-on that syncs `favourites.xml` with Google Drive through an OAuth bridge instead of embedding Google credentials in the add-on.

## What It Does

The add-on keeps a single remote copy of `favourites.xml` in Google Drive and syncs it on Kodi startup.

The default storage location is Google Drive `appDataFolder`, which is hidden from the normal Drive UI and scoped to the signed-in Google account.

## Security Model

The add-on does not contain a Google client secret.

Google sign-in happens in a browser through a separate auth bridge. Kodi shows a pairing code, the user completes Google sign-in in the browser, and the bridge returns tokens to the device through a short-lived pairing record.

The bridge keeps the OAuth client secret on the server side only. Kodi never receives that client secret.

The add-on stores OAuth tokens in Kodi settings after pairing:

- `oauth_refresh_token`
- `oauth_refresh_secret`
- `oauth_access_token`
- `oauth_scope`
- token expiry metadata

The refresh token is used so Kodi can continue syncing on later startups without asking the user to sign in every time.

The additional `oauth_refresh_secret` is required by the bridge before it will exchange a stored refresh token for a new access token. This prevents the bridge from acting as a public refresh endpoint if a refresh token is exposed.

Token-bearing bridge responses are marked `no-store`, and pairing records are short-lived and single-purpose.

## Pairing Flow

1. In Kodi, run `Pair Google Drive now`.
2. The add-on asks the bridge for a pairing session.
3. Kodi shows a code and activation URL.
4. The user signs into Google in a browser.
5. Google redirects back to the bridge.
6. The bridge marks the pairing as authorized.
7. Kodi claims the token payload and stores it locally.

After that, later startup syncs use the saved OAuth state and only contact the bridge when an access token needs to be refreshed.

## Data Access

The add-on requests these Google scopes:

- `openid`
- `email`
- `drive.appdata`
- `drive.file`

`drive.appdata` is the main storage mode. It keeps the sync file in the app's hidden Drive app-data area.

`drive.file` remains available for compatibility with Drive file operations and limited file-based access when needed.

## User-Facing Settings

The normal settings UI is intentionally small:

- `Pair Google Drive now`
- `Sync on Kodi startup`

Additional settings still exist internally for compatibility and recovery, but they are hidden from normal users.

## Sync Behavior

Sync currently runs on Kodi startup.

The model is last-write-wins. If one device has a newer local `favourites.xml` when startup sync runs, that version becomes the remote copy. If the remote copy is newer, Kodi downloads it and replaces the local file.

## Auth Bridge

The companion bridge for browser-based Google sign-in lives in [auth-bridge](/Users/kalter/Documents/CODEX/kodifavsyncOauth/auth-bridge).

Its job is to:

- hold the Google OAuth client secret server-side
- start the Google OAuth flow
- bind browser approval to a short-lived pairing session
- return token material only to the device that owns the pairing
- refresh access tokens only when both the refresh token and bridge-issued refresh secret are presented
