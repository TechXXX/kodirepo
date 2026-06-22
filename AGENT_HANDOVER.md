# Kodi Repo Agent Handover

Last updated: 2026-06-22.

This is the broad handover for future agents taking over Fen Light Patched,
TMDb Helper Patched, a4kSubtitles Patched, and nearby Kodi debugging work in
this repo. Read this with:

- `README.md`
- `plugin.video.fenlight.patched/README.md`
- `plugin.video.themoviedb.helper.patched/Readme.md`
- `service.subtitles.a4ksubtitles.patched/README.md`
- `plugin.video.fenlight.patched/resources/lib/fenlightsubs/README.md`

## Repo Shape

`/Users/kalter/Documents/CODEX/kodirepo` is the maintained Kodi repository.
Addon source trees live at repo root. Generated package mirrors and zips live
under `zips/`, with repo metadata in `addons.xml` and `addons.xml.md5`.

`DutchTechTestRepo` is retired from the normal workflow. Treat it as historical
context only unless the user explicitly revives it. Approved publish work should
go directly through this repo.

Do not hand-edit generated output unless the user explicitly asks for a package
mirror edit. Normal flow is source edit first, then regenerate package output
only when a release/package update is intended.

Useful scripts:

- `scripts/build_repo.py`
- `scripts/publish_addon_update.py`
- `scripts/README.md`

## Maintainer Role Boundary

The repo maintainer role is release hygiene first, not feature coding.

Allowed without asking first:

- inspect repo status and diffs
- summarize local changes
- update handover/release documentation
- bump addon versions for an approved release
- regenerate `zips/`, `addons.xml`, and checksum files
- commit and push the user-approved release scope

Ask the user before making coding changes, including Python, XML behavior,
skin behavior, provider logic, playback logic, scraper logic, settings logic,
or any feature implementation.

Important distinction:

- assume existing worktree changes were made by the user unless there is clear
  evidence otherwise
- when the user asks to publish/push changes, package and push those existing
  user-authored changes after normal inspection, version bumps, generated
  output refresh, and sanity checks
- do not block or reclassify an existing user-authored setting/code change as
  "agent coding"; the maintainer is committing the user's work
- if an existing change is risky, surprising, secret-bearing, or unrelated to
  the requested publish scope, report that clearly before pushing
- do not add new code or alter behavior beyond the existing worktree changes
  unless the user explicitly asks for that implementation
- maintainer-created edits should be limited to release mechanics and docs:
  version bumps, changelog/news text, handover notes, generated package output,
  repo metadata, and checksum refreshes

## Live Kodi Paths On This Mac

When debugging behavior, prefer live evidence over theory.

- Kodi logs:
  `/Users/kalter/Library/Logs/kodi.log`
  `/Users/kalter/Library/Logs/kodi.old.log`
- Installed addons:
  `/Users/kalter/Library/Application Support/Kodi/addons`
- Kodi profile userdata:
  `/Users/kalter/Library/Application Support/Kodi/userdata`
- Fen Light Patched userdata:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched`
- Fen Light Patched settings DB:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/settings.db`
- Fen Light Patched metadata cache:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/metacache.db`
- Fen Light Patched source cache:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/external.db`
- TMDb Helper Patched item cache:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.themoviedb.helper.patched/database_07/ItemDetails.db`
- TMDb Helper Patched user player overrides:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.themoviedb.helper.patched/players`

Use `PYTHONDONTWRITEBYTECODE=1` for Python smoke tests in addon trees to avoid
stray `__pycache__` files.

## Addon Boundaries

### Fen Light Patched

Source:

`plugin.video.fenlight.patched`

Current source version observed during this handover:

`2.0.89`

Fen owns:

- metadata lookup before playback
- source scraping
- source filtering and ordering
- resolver handoff to Kodi playback
- autoplay and source-select behavior
- next-episode/autoscrape timing
- local watched/progress/bookmark state
- playback window properties consumed by skins and companion addons
- pre-play subtitle-aware source promotion

Fen should not:

- invent sources when providers return none
- add one-off title hacks
- assume TMDb Helper Trakt auth applies to Fen
- own detailed subtitle scoring policy that belongs in `resources/lib/fenlightsubs`

### TMDb Helper Patched

Source:

`plugin.video.themoviedb.helper.patched`

Patched fork baseline in local docs:

`v6.15.2`

TMDb Helper is usually the launcher. Its Fen Light Patched player JSONs live at:

- `plugin.video.themoviedb.helper.patched/resources/players/fenlight.patched.auto.json`
- `plugin.video.themoviedb.helper.patched/resources/players/fenlight.patched.select.json`

They use `is_resolvable=false` and launch Fen with `mode=playback.media`,
`tmdb_id`, season/episode, title/year hints, and `autoplay=true/false`.
After that, Fen owns scraping, resolving, playback, resume, and source ordering.

TMDb Helper Trakt auth is real but scoped. It can support TMDb Helper lists,
indicators, progress metadata, player placeholders, and scrobbling when its
monitor sees enough Kodi playback metadata. It does not authorize Fen, POV,
Umbrella, Magneto, or any other launched player addon. A TMDb Helper resume
prompt can pass intent, but the launched player must preserve or apply the seek.

### a4kSubtitles Patched

Source:

`service.subtitles.a4ksubtitles.patched`

Fen talks to patched a4k in two phases:

- Before playback, Fen gathers subtitle candidates and uses
  `resources/lib/fenlightsubs` to promote subtitle-backed sources.
- During playback, Fen sets properties such as `subs.player_filename`,
  `subs.selector_source_key`, `subs.selector_payload`, and
  `subs.selector_playback_url`; the a4k service then attaches the chosen
  subtitle only when the current playback still matches the Fen handoff.

The subtitle selector policy belongs in:

`plugin.video.fenlight.patched/resources/lib/fenlightsubs`

## TMDb Identity And No-Source Cases

Do exact identity checks before changing code.

### The Terror: Devil In Silver

TMDb page investigated:

`https://www.themoviedb.org/tv/323903-the-terror-devil-in-silver/season/1`

Observed identity split:

- standalone TMDb show: `323903`
- standalone title: `The Terror: Devil in Silver`
- source ecosystems may index it as parent anthology `The Terror`
- parent TMDb: `75191`
- IMDb: `tt2708480`
- likely provider route: parent show season `3`

This is a real metadata/source-ecosystem mismatch. Do not add title-specific
translation code for it. It is safer to treat the standalone route as an honest
no-source result than to broaden Fen into making up aliases that might break
other shows.

TMDb alternative titles/aliases are not a magic list that should be blindly
fed into source searching. Many entries have alternative titles, but coverage,
language, and relevance vary. Treat them as metadata hints, not authoritative
scene/source aliases.

### Dutton Ranch Blank Metacache

Live testing found a separate generic failure class with TMDb `299167`
(`Dutton Ranch`): Fen had a cached `blank_entry` row even though direct TMDb
data existed.

Relevant files:

- `plugin.video.fenlight.patched/resources/lib/modules/metadata.py`
- `plugin.video.fenlight.patched/resources/lib/caches/meta_cache.py`
- `plugin.video.fenlight.patched/resources/lib/indexers/seasons.py`

Safe future direction: cache `blank_entry` only for explicit invalid TMDb
responses, not transient `None` or network/no-response conditions. Also guard
callers that assume season data exists. Keep this generic.

### Debug Checklist For "No Sources"

Before changing source logic, verify:

- requested TMDb/IMDb/TVDb identity
- show title, original title, parent anthology title, season, and episode
- Fen metacache row is not a stale `blank_entry`
- `external.db` is not serving a stale empty result
- provider/debrid settings are enabled in `settings.db`
- logs show providers actually ran
- failure is not a provider API exception such as non-JSON AIOStreams output

## POV Findings

Local installed POV observed:

`/Users/kalter/Library/Application Support/Kodi/addons/plugin.video.pov`

Version observed:

`6.06.09`

POV is a Fen fork, but compare it only to `plugin.video.fenlight.patched`, not
to upstream Fen, when deciding what to borrow.

Potentially worth borrowing:

- Pack downloader preselects all files in pack selection:
  `resources/lib/modules/downloader.py`
- Numeric resolve attempt limit:
  setting `limit_resolve`, used to cap how many sources are walked during
  resolve attempts.
- Trakt pagination helper using safer page sizes instead of oversized one-shot
  requests.
- TorBox `user_ip` passed to request-download calls. Treat this as an
  experiment, not an automatic copy.

Probably not worth copying directly:

- Magneto provider stack: too broad as a small patch.
- SubMaker subtitle path: not aligned with the current Fen/a4k selector flow.
- POV next-episode artwork/UI: the user does not like the graphics and does not
  want competing end-credit buttons.

### POV IntroDB Integration

POV directly queries IntroDB APIs from its player code. It does not coordinate
with the official TheIntroDB Kodi addon.

Observed behavior:

- It calls `https://api.introdb.app/segments`.
- It falls back to `https://api.theintrodb.org/v3/media`.
- It uses only `outro`/`credits` start timing.
- It converts the credits start into Fen-style next-episode window timing.
- It does not implement a skip-intro/skip-credits UI of its own.
- If the official TheIntroDB addon is installed and also displays a credits
  button, duplicate end-credit UI is possible.

The useful idea is data, not UI: use a credits/outro timestamp to time Fen's own
next-episode/autoscrape window more intelligently.

## TheIntroDB Official Addon

Official repo:

`https://github.com/TheIntroDB/kodi-addon`

Addon id:

`plugin.video.tidb`

It is a separate service addon. It reads the currently playing Kodi item through
Kodi APIs, identifies the media, queries TheIntroDB, and shows skip controls or
auto-skips configured segment types such as intro, recap, credits, and preview.

Current Fen Light Patched already sets useful playback metadata in
`player.py`, including media type, title/show title, season, episode, and unique
IDs. That means the official addon should be able to identify many Fen-launched
items, but it would bring its own UI.

UX stance from this investigation:

- Do not show two end-credit buttons.
- Do not rely on the official TheIntroDB overlay if Fen is also showing a next
  episode window.
- If this repo adopts IntroDB timing, Fen should own the end-credit experience
  and use IntroDB only as a timing source.
- Keep skip-intro separate from next-episode unless the user explicitly asks for
  a Fen-owned skip UI.

## Umbrella Findings

Umbrella was not installed locally under this Mac's Kodi addons and was not
found as a local `Documents/CODEX` checkout during the quick search. The current
official GitHub repo was checked instead.

Official source:

`https://github.com/umbrellaplug/umbrellaplug.github.io`

Version observed in official `omega/plugin.video.umbrella/addon.xml`:

`6.7.77`

Umbrella does not use IntroDB/TheIntroDB for next-episode timing.

Its PlayNext approach:

- add the next episode to Kodi's playlist
- optionally pre-scrape/pre-resolve the next episode
- trigger the PlayNext window by one of three methods:
  seconds remaining, watched percentage, or subtitle timing
- support still-watching checks and themed PlayNext XML windows

The subtitle timing mode downloads or reads an OpenSubs subtitle file, extracts
late subtitle timestamps, and uses that as a rough end-of-episode cue with
seconds/percentage fallback. Clever, but less deterministic than real credits
timing and less aligned with Fen Light Patched's current a4k selector flow.

Umbrella had no chapter-based timing beyond a debug callback for chapter seeks.

## FenLight AM Findings

Local source:

`/Users/kalter/Documents/CODEX/fenlightam/plugin.video.fenlight`

Version observed:

`2.2.04`

FenLight AM does not use IntroDB/TheIntroDB.

Its next-episode/autoscrape timing is close to Fen Light Patched:

- use Kodi `Player.Chapters` if enabled and a final chapter passes the threshold
- otherwise fall back to configured playback percentage
- show FenLight's own playback notification window

It also has a movie credits-stinger alert, but that is based on TMDb keyword
metadata such as `duringcreditsstinger` and `aftercreditsstinger`; it is not
actual credits timing.

Fen Light Patched already has a more defensive `final_chapter()` than FenLight
AM's simple "last chapter above threshold" logic.

## Next Episode, IntroDB, And Credits Timing

Current ranking of timing approaches for this repo:

1. Existing Fen Light Patched chapter timing: keep it.
2. Use generic IntroDB credits/outro/preview timing as an optional data source
   for Fen's existing next-episode/autoscrape timing.
3. Use percentage fallback when neither chapter nor IntroDB timing is available.
4. Avoid Umbrella-style subtitle timing unless there is a specific reason; it
   crosses into subtitle-provider concerns and is fuzzier.
5. Avoid official TheIntroDB addon UI for end credits if Fen's next-episode UI
   is active.

Current IntroDB implementation:

- no title-specific code
- no new competing end-credit button
- no dependency on the official addon overlay
- short network timeout
- no fatal playback failure if IntroDB is down
- query by stable IDs and season/episode
- use only credits/outro timing for next-episode timing
- intro/recap skip buttons are optional Fen-owned controls behind settings
- the repo intentionally ships the default TheIntroDB API key in Fen settings;
  users can still replace it in settings when needed

## TMDb Helper, Players, And Trakt

TMDb Helper player selection launches another addon. It does not turn TMDb
Helper into the playback owner after handoff.

Examples:

- Fen Light Patched player launches Fen Light Patched.
- POV player launches POV.
- Umbrella player launches Umbrella.
- Magneto player launches Magneto or its configured player/scraper path.

If the launched player lacks Trakt/resume/scrobble support, TMDb Helper auth
does not automatically fill that gap. The official Trakt addon may scrobble
Kodi playback globally, but resume points can still be player-specific because
each player stores and applies its own resume/bookmark behavior.

## Historical Fen 2.0.07 Source Audit

The user asked about political/conservative text in old Fen Light source.

Audited source:

`/Users/kalter/Documents/CODEX/temp/plugin.video.fenlight-2.0.07.zip`

Extracted audit path used at the time:

`/tmp/fenlight-2.0.07-audit/plugin.video.fenlight`

Confirmed messages:

- `resources/lib/modules/kodi_utils.py:2` contained `# TRUMP WON`
- `resources/text/changelog.txt` contained `GOD BLESS HIM AND KEEP HIM SAFE`
  / `God Bless him and keep him safe.`

The broader changelog sweep found those "God Bless..." lines as the only
political/religious-looking changelog hits noted in that audit. Do not assume
those messages are present in the current patched source without checking.

## Upstream And Fork Update Policy

When comparing/updating from upstream:

- verify the actual upstream source online when the user asks for latest
- preserve patched addon identity, addon id, provider name, and user-facing fork
  identity
- when the user says "code changes nothing else", do not bring metadata churn,
  branding changes, generated package changes, or unrelated docs
- inspect local diffs before editing; do not revert user changes
- use source-level changes first, then package/repo metadata only when asked or
  when shipping a release

For TMDb Helper Patched, previous upstream syncs were intentionally constrained
to Python/code logic that did not interfere with the patched identity.

## Guard Rails

- No one-off title fixes for `The Terror`, `Dutton Ranch`, or similar cases.
- No fake aliases or invented sources.
- No hidden behavior that changes source results without logging/debug evidence.
- No assumption that TMDb Helper Trakt auth authorizes player addons.
- No duplicate end-credit UI if Fen owns next episode.
- No broad provider-stack swaps from POV/Magneto without a separate plan.
- No generated-output edits unless packaging is part of the task.
- When in doubt, check `kodi.log`, the live addon copy, and live cache DBs first.

## High-Signal Commands

```sh
tail -n 250 "/Users/kalter/Library/Logs/kodi.log"

rg -n "playback.media|sort_subtitle_ready_autoplay|selector_payload|final_chapter|auto_nextep_settings" \
  /Users/kalter/Documents/CODEX/kodirepo/plugin.video.fenlight.patched

sqlite3 "/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/metacache.db" \
  "select db_type, tmdb_id, imdb_id, tvdb_id, meta, datetime(expires, 'unixepoch', 'localtime') from metadata where tmdb_id='299167';"

sqlite3 "/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/settings.db" \
  "select id, value from settings where id like '%tb%' or id like '%external%';"

rg -n -i "introdb|theintrodb|getCredits|Player.Chapters|playnext.method|downloadForPlayNext" \
  "/Users/kalter/Library/Application Support/Kodi/addons" \
  /Users/kalter/Documents/CODEX/fenlightam \
  /Users/kalter/Documents/CODEX/kodirepo/plugin.video.fenlight.patched
```
