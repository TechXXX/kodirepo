# Kodi Setup Kit Handover

Last updated: 2026-06-27.

This document preserves the operational context for `plugin.program.famyt`,
now named **Kodi Setup Kit**. The add-on started as a private YouTube API-key
installer and has become the family Kodi bootstrap tool for a configured Shield
/ MacBook-style profile.

The add-on id is still `plugin.program.famyt` for compatibility. Treat
"famYT" as the old implementation name and "Kodi Setup Kit" as the user-facing
name.

## High-Level Shape

There are three moving parts:

- `kodirepo`: main DutchTech Kodi repository and the production package feed.
- `KodiEnglish`: English-family repository that carries a matching Setup Kit
  package for that feed.
- `youtubeapikey/famyt-vercel`: private Vercel bridge that stores secrets in
  Vercel environment variables and returns them to Kodi after the shared family
  password is provided.

The Kodi repositories must not contain private API keys, OAuth secrets, TorBox
tokens, OpenSubtitles credentials, AI keys, or Kodi webserver passwords.

The Vercel bridge is the private secret source. The public add-on zip contains
only installer logic, sanitized presets, artwork, keymaps, and profile defaults.

Current Setup Kit version at this handover: `0.9.15`.

## Security Model

Keep this boundary intact:

- Public repo: installer code, preset XML/DB files, keymaps, docs.
- Vercel env vars: YouTube credentials, TorBox key, AIOStreams manifest URL,
  a4kSubtitles credentials, AI key, Kodi webserver credentials.
- Local `.env`: ignored working copy for pushing those Vercel env vars.
- Kodi userdata: final installed state on each device.

Never commit:

- `.env`
- `.env.*` except `.env.example`
- API keys or OAuth secrets
- TorBox API keys
- OpenSubtitles passwords
- AI translation keys
- Kodi webserver username/password if they are intended to be private
- screenshots that visibly contain credentials

The bundled GUI preset deliberately enables Kodi's HTTP webserver and
authentication, but leaves the username/password blank. `Install everything`
fills those from Vercel if the optional `KODI_WEBSERVER_*` env vars are set.

## Vercel Bridge Contract

Local project:

`/Users/kalter/Documents/CODEX/youtubeapikey/famyt-vercel`

Production alias:

`https://famyt-vercel.vercel.app`

Kodi calls:

`POST /api/youtube-keys`

Request:

```json
{ "password": "shared-family-password" }
```

Response shape:

```json
{
  "keys": {
    "api_key": "...",
    "client_id": "...apps.googleusercontent.com",
    "client_secret": "..."
  },
  "torbox": {
    "api_key": "...",
    "aiostreams_manifest_url": "..."
  },
  "a4ksubtitles": {
    "opensubtitles": {
      "username": "...",
      "password": "..."
    },
    "ai": {
      "api_key": "..."
    }
  },
  "kodi": {
    "webserver": {
      "username": "...",
      "password": "...",
      "port": "8080"
    }
  }
}
```

Only `keys` is required. The other objects are optional and appear only when
their env vars are configured.

Required Vercel env vars:

- `FAMYT_PASSWORD` or `FAMYT_PASSWORD_SHA256`
- `YOUTUBE_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`

Optional Vercel env vars:

- `TORBOX_API_KEY`
- `TORBOX_AIOSTREAMS_MANIFEST_URL`
- `A4KSUBS_OPENSUBTITLES_USERNAME`
- `A4KSUBS_OPENSUBTITLES_PASSWORD`
- `A4KSUBS_AI_API_KEY`
- `KODI_WEBSERVER_USERNAME`
- `KODI_WEBSERVER_PASSWORD`
- `KODI_WEBSERVER_PORT`

After env changes:

```bash
cd /Users/kalter/Documents/CODEX/youtubeapikey/famyt-vercel
./push-env.sh .env production
vercel deploy --prod -y
```

Vercel env changes apply to new deployments, so redeploy after pushing env
vars. Do a redacted smoke test only; do not print secret values.

## Main Menu Shape

Top-level menu items marked `[ALL]` are included in `Install everything`.
As of `0.9.15`, the first nine menu items are:

1. `[ALL] Kodi sources`
2. `[ALL] Fen Light settings preset`
3. `[ALL] a4kSubtitles settings preset`
4. `[ALL] YouTube credentials`
5. `[ALL] TorBox API key and Manifest URL`
6. `[ALL] a4kSubtitles credentials`
7. `[ALL] Cocoscrapers filters`
8. `[ALL] Kodi network/webserver settings`
9. `[ALL] Kodi keymaps`

`Install everything` runs exactly those steps in that order.

The order is deliberate:

- Fen Light settings must be restored before TorBox credentials.
- a4kSubtitles preset must be restored before a4k credentials.
- GUI preset restore is separate; webserver credentials are applied in the
  network/webserver step from Vercel.

## Install Everything Details

### 1. Kodi Sources

Restores bundled `sources.xml` from the MacBook preset.

Source:

`plugin.program.famyt/resources/sources/presets/macbook/sources.xml`

Backups go under:

`special://profile/addon_data/plugin.program.famyt/backups/sources`

Restart Kodi if file manager/source pickers do not refresh immediately.

### 2. Fen Light Settings Preset

Restores bundled Fen Light `settings.db` and optional `settings.xml` payloads.

Source:

`plugin.program.famyt/resources/fenlightsettings/presets/macbook/`

The current bundled Fen Light preset contains non-secret profile preferences.
It also contains TorBox rows with empty placeholders:

- `tb.token=empty_setting`
- `tb.usenet_search.aiostreams_manifest=empty_setting`
- `tb.enabled=true`

This means:

- Running TorBox after Fen Light settings is safe.
- Running Fen Light settings after TorBox can wipe the TorBox token and
  manifest URL.

`Install everything` uses the safe order: Fen Light settings first, TorBox
second.

Targets detected by the add-on:

- `plugin.video.fenlight`
- `plugin.video.fenlight.patched`
- `plugin.video.fenlight.kodienglish`
- `plugin.video.fenlight.patched.kodienglish`

The restore copies the whole preset DB over the live one, but it is no longer a
blind overwrite: before the copy it captures the live Trakt and debrid rows, and
after the copy it writes them back. So existing logins survive a restore on an
already-configured box, while every other setting is reset to the family
baseline. Restart Kodi afterward so Fen Light reloads its settings cache.

Preserved across restore (see `FENLIGHT_PRESERVE_SETTING_PREFIXES` and
`FENLIGHT_PRESERVE_SETTING_IDS` in `installer.py`): every row whose id starts
with `trakt.`, `rd.`, `pm.`, `ad.`, `ed.`, or `tb.`, plus the exact id
`omdb_api`. That keeps Trakt auth (`trakt.token`, `trakt.refresh`, `trakt.user`,
`trakt.client`, `trakt.secret`, `trakt.auth_state*`), the debrid logins Fen
stores in its own DB — Real-Debrid (`rd.`), Premiumize (`pm.`), AllDebrid
(`ad.`), EasyDebrid (`ed.`), TorBox (`tb.`) — and a personal OMDb API key. The
user does not have to re-auth Trakt, re-enter debrid keys, or re-enter their own
OMDb key. On a fresh box there is no live DB, so nothing is preserved and the
preset (plus Fen's own reseed) applies as-is. In `Install everything`, the TorBox
step still runs after this and overrides `tb.token` from Vercel, so the family
TorBox key wins there.

The preserve step only carries over rows that hold a real value; blank
placeholders (`''`, `empty_setting`, `NULL`) are skipped so the device falls
through to the preset or Fen's reseeded default instead of pinning a blank.

`omdb_api` is both deleted from the preset and preserved: deleting it lets a box
with no real key reseed Fen's shared default OMDb key, while preserving it keeps
a device's own registered OMDb key (which avoids sharing OMDb's daily free-tier
quota) across a restore. Because blanks are skipped, a box that never had (or had
emptied) its OMDb key still gets Fen's default `987d3ba9` filled in on the next
restart; only a device with a real custom key keeps that custom key.

Public default keys are handled the opposite way: they must NOT be carried in the
preset as blanked `empty_setting` rows, or the copy wipes them. They are deleted
from the bundled preset DB so Fen re-seeds its shipped defaults on the next
restart (its `SyncSettings` service re-inserts any missing row from
`settings_cache.py` defaults):

- `tmdb_api` (Fen's shared default TMDb API key)
- `introdb.api_key` (Fen's shipped default IntroDB key)
- `trakt.client` / `trakt.secret` / `trakt.auth_state*` are also deleted from the
  preset, but on an existing box the preserve step keeps the live values instead;
  only a fresh box falls through to Fen's reseeded defaults.

These are Fen Light Patched's own public defaults (see
`plugin.video.fenlight.patched/resources/lib/modules/kodi_utils.py` and
`.../caches/settings_cache.py`), not private family secrets, so they belong to
the add-on, not to the Setup Kit. When re-capturing this preset, delete these
rows again rather than shipping them blanked.

### 3. a4kSubtitles Settings Preset

Restores the sanitized MacBook a4kSubtitles Patched `settings.xml`.

Source:

`plugin.program.famyt/resources/a4ksubtitlessettings/presets/macbook/`

Bundled secret fields are intentionally blank:

- `general.ai_api_key`
- `opensubtitles.username`
- `opensubtitles.password`
- `subdl.apikey`
- `subsource.apikey`

The installer clears cached a4k/OpenSubtitles tokens after restore. Credentials
are installed later from Vercel by the a4k credentials step.

### 4. YouTube Credentials

Installs the shared YouTube API key, OAuth client ID, and OAuth client secret.

Writes:

`special://profile/addon_data/plugin.video.youtube/api_keys.json`

If the YouTube add-on is already installed, it also updates YouTube's Kodi
settings:

- `youtube.api.key`
- `youtube.api.id`
- `youtube.api.secret`

Family members can still sign into YouTube with their own Google account. The
API credentials are developer credentials; the watch history/subscriptions
come from the individual YouTube login.

### 5. TorBox API Key And Manifest URL

Installs:

- `tb.token`
- `tb.enabled=true`
- `tb.usenet_search.aiostreams_manifest` when provided by Vercel

It writes those rows into each detected Fen Light settings DB using
`INSERT OR REPLACE`. It does not replace the full Fen Light settings DB and
does not wipe unrelated Fen settings.

Important interaction:

- TorBox install after Fen Light settings is safe.
- Fen Light settings restore after TorBox can wipe TorBox because it copies a
  whole preset DB over the live DB.

### 6. a4kSubtitles Credentials

Installs from Vercel:

- OpenSubtitles username
- OpenSubtitles password
- AI translation API key
- AI model pinned to `gpt-4.1-mini-2025-04-14`
- OpenSubtitles enabled
- AI enabled

This should run after the a4kSubtitles settings preset, because the bundled
preset is sanitized and would blank those fields.

### 7. Cocoscrapers Filters

Writes Cocoscrapers undesirable filters and disables the unwanted default entry
identified during setup.

Current bundled user undesirable keywords:

- `.hc.`
- `.hin.`
- `.hindi.`
- `.ita.`
- `.rus.`
- `.ukr.`

Current disabled default undesirable:

- `dutchreleaseteam`

### 8. Kodi Network / Webserver Settings

Writes `advancedsettings.xml`:

```xml
<advancedsettings>
  <network>
    <disablehttp2>true</disablehttp2>
    <disableipv6>true</disableipv6>
  </network>
</advancedsettings>
```

`disablehttp2` and `disableipv6` are separate. HTTP/2 is not IPv6.

If Vercel returns `kodi.webserver`, this same step also updates
`guisettings.xml` and tries live JSON-RPC application for:

- `services.webserver=true`
- `services.webserverauthentication=true`
- `services.webserverusername`
- `services.webserverpassword`
- `services.webserverport`

Restart Kodi if the webserver settings do not appear immediately.

### 9. Kodi Keymaps

Installs bundled keymaps from:

`plugin.program.famyt/resources/keymaps`

Current keymaps:

- `gen.xml`
- `zz_fenlight_quickrescrape.xml`
- `zz_fullscreen_back_stop.xml`

Notable behavior:

- Backspace in fullscreen video stops playback.
- Fen Light quick-rescrape shortcut is available from supported windows.
- Some Shield/remote key events are mapped for subtitle/quick-rescrape habits.

Restart Kodi after keymap install.

## GUI Settings

GUI settings are tricky because Kodi keeps many of them in memory and writes
`guisettings.xml` during shutdown.

The Setup Kit GUI restore does two things:

1. Attempts to apply settings live through JSON-RPC.
2. Writes the preset `guisettings.xml` file to the profile.

Some settings may stick immediately. Others, especially regional and services
settings, require restart. Some settings can be overwritten by Kodi on shutdown
if Kodi still has old in-memory values.

Known behaviors from live testing:

- Many GUI values did stick after restore.
- Regional settings did not reliably take until the preset was refreshed from
  the current MacBook profile.
- Kodi webserver username/password should come from Vercel, not the bundled
  GUI preset.
- JSON-RPC `Settings.SetSettingValue` can return boolean `true`; the installer
  now counts that as success. Older code only counted `"OK"` and over-reported
  live failures.
- The GUI restore does NOT live-apply the webserver settings
  (`services.webserver`, `services.webserverauthentication`,
  `services.webserverusername`, `services.webserverpassword`; see
  `GUISETTINGS_LIVE_APPLY_SKIP_IDS`). The preset enables auth with a blank
  password, and applying `services.webserverauthentication=true` live makes Kodi
  raise a modal error ("If web server authentication is enabled, a password must
  be entered as well"). Those settings are still written to `guisettings.xml` and
  are applied for real by the Vercel-backed webserver step, which has a password.
- The live-apply loop now logs each failed setting id, value, coerced type, and
  JSON-RPC reason (`GUI live-apply failed: ...`) plus a summary line, at info
  level, so the settings that do not stick can be diagnosed without Kodi debug
  logging.

Bundled GUI preset is now refreshed from the MacBook profile and has:

- `locale.country=NL`
- webserver enabled
- webserver authentication enabled
- webserver username/password blank

Use GUI settings restore for profile shape. Use `Install everything` to apply
private webserver credentials from Vercel.

## Skin Settings

Skin setting tools can back up, save, rename, delete, and restore presets for
the supported skins.

Supported targets are declared in `SKIN_SETTINGS_ADDONS` in:

`plugin.program.famyt/resources/lib/installer.py`

Current bundled skin settings include DutchTech Fuse 3 and Arctic Horizon 2
patched targets. Presets can be named by the user, so Dutch and English
variants can coexist.

Saved presets are written both to add-on resources when writable and to Kodi
profile add-on data. On Android, bundled resources may be read-only, so the
profile add-on data path is the durable location.

## KodiSkin Widget Importer

The separate KodiSkin Widget Importer was integrated as a menu launch target,
but the original add-on still exists separately. Setup Kit launches it rather
than duplicating all widget logic inline.

Preset context from this conversation:

- AF3 DutchTech/MacBook widgets are the Dutch preset.
- Existing English widgets were preserved as English presets.
- The removed `Recent bekeken` widget should not return to either AF3 preset.

## Utilities

Utilities currently include status/debug and cleanup helpers. Important ones:

- Show setup status.
- Export debug bundle.
- Clear thumbnail cache.
- Clear add-on package cache.
- Clean Setup Kit backups.
- Reload skin.
- Restart Kodi.

Clear thumbnail cache deletes both:

- `special://profile/Thumbnails`
- `Textures*.db` in the profile database folder

Kodi rebuilds artwork afterward. Restart is recommended after this cleanup.

## Backup And Preset Storage

Setup Kit stores its own backups and saved presets under:

`special://profile/addon_data/plugin.program.famyt/`

Important subfolders:

- `backups/guisettings`
- `backups/sources`
- `backups/fenlightsettings`
- `backups/a4ksubtitlessettings`
- `backups/skinsettings`
- `presets/guisettings`
- `presets/sources`
- `presets/fenlightsettings`
- `presets/a4ksubtitlessettings`
- `presets/skinsettings`

Bundled presets live under:

`plugin.program.famyt/resources/`

Do not assume built-in resources are writable on Android devices. Saved user
presets in profile add-on data are the safer persistence point.

## Live Testing Paths

MacBook Kodi profile:

`/Users/kalter/Library/Application Support/Kodi/userdata`

MacBook Kodi logs:

`/Users/kalter/Library/Logs/kodi.log`

Android/Kodinerds Maven profile used in this work:

`/Volumes/internal/Android/data/net.kodinerds.maven.kodi21/files/.kodi`

Older Windows portable profile path seen in the thread:

`/Volumes/[C] Windows 11/Kodi 21.3/portable_data`

When the user reports live behavior, check the real profile and logs before
theorizing.

## Publishing Workflow

For Setup Kit source changes in `kodirepo` and `KodiEnglish`:

1. Edit source in `plugin.program.famyt/`.
2. Keep shared files synced between repos when behavior should match.
3. Preserve repo-specific `addon.xml` dependency differences.
4. Bump `plugin.program.famyt/addon.xml` version for Kodi-visible releases.
5. Update `<news>` with the user-facing change.
6. Rebuild `zips/plugin.program.famyt/` and the zip archive.
7. Regenerate `addons.xml` and checksum files.
8. Validate.
9. Commit and push both repos.

Useful rebuild snippet:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
import shutil
from scripts.build_repo import build_addons_xml, get_source_dirs, mirror_addon_source, package_addon, write_md5

root = Path('/Users/kalter/Documents/CODEX/kodirepo')
addon_id = 'plugin.program.famyt'
source_dirs = get_source_dirs(root)
addon_dir = {path.name: path for path in source_dirs}[addon_id]
output_dir = root / 'zips' / addon_id
if output_dir.exists():
    shutil.rmtree(output_dir)
output_dir.mkdir(parents=True, exist_ok=True)
mirror_addon_source(addon_dir, output_dir)
archive = package_addon(addon_dir, output_dir)
print(archive.relative_to(root))
build_addons_xml(source_dirs, root / 'addons.xml')
write_md5(root / 'addons.xml')
PY
```

For `KodiEnglish`, change `root` to:

`/Users/kalter/Documents/CODEX/KodiEnglish`

and stage `addons.xml.md5.txt` too.

## Validation Checklist

Run before pushing a Setup Kit release:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  plugin.program.famyt/plugin.py \
  plugin.program.famyt/resources/lib/installer.py

git diff --check
```

Also verify:

- `addons.xml` advertises the new `plugin.program.famyt` version.
- The new zip exists under `zips/plugin.program.famyt/`.
- No `__pycache__`, `.pyc`, `.DS_Store`, `__MACOSX`, or `._*` files are inside
  the zip.
- Source and generated mirror files match.
- Sanitized presets have no private secrets.
- First nine menu labels still start with `[ALL]` if `Install everything`
  behavior is changed.

Vercel validation:

```bash
cd /Users/kalter/Documents/CODEX/youtubeapikey/famyt-vercel
node --check api/youtube-keys.js
bash -n push-env.sh
```

Use a redacted smoke test for production. Confirm booleans like
`has_kodi_webserver=true`; do not print secret values.

## Common Footguns

### Fen Light settings can wipe TorBox

The Fen Light preset restore copies a full `settings.db`. If run after TorBox,
it can overwrite `tb.token` and the AIOStreams manifest with `empty_setting`.

Safe order:

1. Fen Light settings preset
2. TorBox API key and Manifest URL

`Install everything` already follows this order.

### a4kSubtitles preset can wipe a4k credentials

The bundled a4k preset is sanitized. Run credentials after preset restore.

Safe order:

1. a4kSubtitles settings preset
2. a4kSubtitles credentials

`Install everything` already follows this order.

### Fen Light preset can wipe Fen's own default keys

The Fen Light preset restore copies the whole preset DB. If the preset carries
Fen's public default keys as blanked `empty_setting` rows (`tmdb_api`,
`introdb.api_key`, and the `trakt.*` app creds), the copy overwrites the live
defaults and breaks TMDb metadata on the family box. Keep those rows deleted
from the preset so Fen re-seeds its own shipped defaults on restart.

Per-user Trakt and debrid logins are the other side of this: the restore
captures live `trakt.`/`rd.`/`pm.`/`ad.`/`ed.`/`tb.` rows and writes them back
after the copy, so restoring on an already-configured box does not sign the user
out of Trakt or wipe debrid keys. Do not remove that preserve step when touching
the restore path. See `Install Everything Details -> 2. Fen Light Settings
Preset`.

### GUI restore is not a magic live migration

GUI restore writes the file and tries JSON-RPC live apply. Restart is still the
safest result, especially for regional/services settings.

### Missing components should not abort everything

`Install everything` uses a per-step wrapper so missing optional components
are reported as skipped instead of breaking the whole run. This was added
after an install at a family member's device failed when a4kSubtitles Patched
was missing.

### Same-version packages are not real updates

Kodi update detection is version based. For a Kodi-visible Setup Kit change,
bump `plugin.program.famyt` and rebuild package metadata.

### Vercel env changes require redeploy

After adding or changing Vercel env vars:

```bash
./push-env.sh .env production
vercel deploy --prod -y
```

### Kodi private GitHub auth is awkward

The chosen distribution model avoids private GitHub login inside Kodi. Family
installs the public/private repo zip, and secrets come from the password-gated
Vercel bridge.

## When Adding A New Setup Task

Prefer this pattern:

1. Add a narrow installer function.
2. Keep secrets in Vercel, not the add-on repo.
3. Add an individual top-level menu item if it is family-useful.
4. Add `[ALL]` only if it should run in `Install everything`.
5. Think carefully about ordering if one step restores full profile files and
   another step installs credentials.
6. Make missing optional add-ons skip cleanly.
7. Update this document, `plugin.program.famyt/README.md`, and the Vercel
   README if the bridge contract changes.

## Current Intended Family Setup Flow

On a fresh family Kodi device:

1. Install the repository zip.
2. Install Kodi Setup Kit.
3. Open Setup Kit settings and set the bridge URL.
4. Run `Install everything`.
5. Enter the shared family password.
6. Restart Kodi.
7. If YouTube prompts for a normal account login, family members can sign in
   with their own Google account.

Run manual restore tools only when needed. For normal setup, the `[ALL]` flow
is the curated path.
