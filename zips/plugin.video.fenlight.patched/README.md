# Fen Light Patched Agent Notes

Last reviewed: 2026-06-21 against `plugin.video.fenlight.patched` `2.0.86`.

This is the production-facing patched Fen Light addon in `kodirepo`. Future
agents should read this before changing scraping, playback, subtitle pairing,
TMDb Helper player handoff, or Trakt/resume behavior.

For cross-addon handover notes covering POV, Umbrella, FenLight AM, IntroDB,
TheIntroDB, TMDb Helper, Trakt boundaries, and known no-source edge cases, read
`../AGENT_HANDOVER.md`.

## What Fen Owns

Fen Light Patched is the owner of:

- source scraping and cached source result handling
- metadata lookup through Fen's TMDb/metacache layer
- autoplay/source-select ordering
- pre-play subtitle-aware retry-pool promotion
- resolver handoff to Kodi playback
- Fen's own watched/progress/bookmark updates
- playback window properties consumed by skins, a4k, and other addons

Fen does not own:

- detailed subtitle scoring policy, which lives in `resources/lib/fenlightsubs`
- runtime subtitle download/attachment, which lives in
  `service.subtitles.a4ksubtitles.patched`
- TMDb Helper widget/list construction or Trakt list UI
- external player addon authorization

## Main Playback Flow

The foreground playback path is:

1. `resources/lib/fenlight.py`
2. `resources/lib/modules/router.py`
3. `Sources().playback_prep(params)` for `mode=playback.media`
4. `Sources.get_meta()`
5. `Sources.determine_scrapers_status()`
6. `Sources.get_sources()`
7. source collection from internal, folder, and external providers
8. `Sources.process_results(results)`
9. optional `Sources.sort_subtitle_ready_autoplay(results)`
10. `Sources.play_source(...)` / `Sources.play_file(...)`
11. `FenLightPlayer().run(url, sources_obj)`
12. Kodi playback and Fen watched/bookmark monitoring

Important files:

- `resources/lib/modules/sources.py`
  Scrape orchestration, filters, subtitle-aware autoplay promotion, source
  selection, resolve retry ordering.
- `resources/lib/modules/player.py`
  Kodi listitem creation, resume setup, playback properties, watch/bookmark
  updates, next-episode state.
- `resources/lib/modules/metadata.py`
  TMDb metadata fetches and `blank_entry` metacache behavior.
- `resources/lib/caches/meta_cache.py`
  Persistent and window-property metadata cache.
- `resources/lib/scrapers/external.py`
  Wrapper for external torrent provider modules such as CocoScrapers-style
  providers.
- `resources/lib/fenlightsubs/`
  Bundled source/subtitle selector policy and Fen/a4k adapter.

## Source Systems

Internal scrapers are enabled through Fen settings and include:

- `easynews`
- `rd_cloud`
- `pm_cloud`
- `ad_cloud`
- `oc_cloud`
- `tb_cloud`
- local `folders`

External scraper support is generic. `settings.external_scraper_info()` reads
`fenlight.external_scraper.module`; `sources.py` then appends
`special://home/addons/<module>/lib` to `sys.path` and imports
`<module-name>.sources_<module-name>`. Current-style providers come from
`total_providers['torrents']`; older modules can still fall back through
`legacy_external_sources()`.

Do not invent sources in Fen. If there are no provider results, keep the empty
result honest and debug metadata, provider settings, debrid auth, cache state,
or external module behavior.

## a4k Subtitle Contract

Fen uses patched a4k in two separate ways.

Pre-play autoplay ranking:

- `sources.py` imports `A4kSubtitlesApi` from
  `special://home/addons/service.subtitles.a4ksubtitles.patched`.
- Fen gathers configured-language subtitles once per title/run.
- `resources/lib/fenlightsubs/integration.py` ranks the full source list
  against the full subtitle result list.
- The best subtitle-backed sources, up to
  `subtitle_fallback_candidate_limit = 10`, are promoted ahead of the raw
  source order.
- If no preferred-language subtitle matches and a4k AI translation is
  configured, Fen performs one final English OpenSubtitles-only fallback and
  marks those matched subtitles as requiring AI translation.

Runtime handoff:

- `player.py` sets `subs.player_filename`.
- `player.py` sets `subs.selector_source_key`.
- `player.py` sets `subs.selector_payload` when the selected source has a
  selector-matched subtitle.
- a4k's service loop reads those properties and may attach the exact matched
  subtitle, after first preferring an embedded preferred-language subtitle
  stream already present in Kodi.

Selector policy belongs in `resources/lib/fenlightsubs/subtitle_selector.py`.
Fen should wire data into the selector; it should not grow ad hoc title or
subtitle scoring patches in `sources.py` unless the change is strictly about
Fen-specific orchestration.

## TMDb Helper Contract

TMDb Helper's bundled Fen player JSONs are launchers:

- `plugin.video.themoviedb.helper.patched/resources/players/fenlight.patched.auto.json`
- `plugin.video.themoviedb.helper.patched/resources/players/fenlight.patched.select.json`

Both use `is_resolvable=false` and call:

- `plugin://plugin.video.fenlight.patched/?mode=playback.media...&autoplay=true`
- `plugin://plugin.video.fenlight.patched/?mode=playback.media...&autoplay=false`

That means TMDb Helper passes `tmdb_id`, season/episode, title/year hints, and
the autoplay flag into Fen. Fen then owns scraping, resolving, playback,
watched/progress updates, and subtitle-aware retry ordering.

Do not assume TMDb Helper Trakt auth authorizes Fen, POV, Umbrella, Magneto, or
any other player addon. TMDb Helper's Trakt auth is useful for TMDb Helper
lists, indicators, progress metadata, player placeholders, and scrobbling when
its playback monitor has enough Kodi metadata, but each launched player still
owns its own source resolution and local resume behavior.

If a TMDb Helper player JSON changes in the repo, also check the installed
userdata copies. Kodi may use the user profile copy instead of the bundled
repo copy.

## Live Kodi Paths On This Mac

Useful local paths for debugging this machine:

- Kodi log:
  `/Users/kalter/Library/Logs/kodi.log`
- Installed Fen addon:
  `/Users/kalter/Library/Application Support/Kodi/addons/plugin.video.fenlight.patched`
- Fen userdata:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched`
- Fen metadata cache:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/metacache.db`
- Fen external/source cache:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/external.db`
- Fen settings DB:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/settings.db`
- Installed TMDb Helper players:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.themoviedb.helper.patched/players`

Selector shadow snapshots are intentionally odd:

- enable marker:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/enable_selector_shadow`
- snapshot directory:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight/subtitle_selector_shadow`

The snapshot directory still uses the unpatched `plugin.video.fenlight` profile
name. Do not "fix" that path casually; existing debug tooling may depend on it.

## Known Edge Cases

### The Terror: Devil In Silver

TMDb has a standalone 2026 entry:

- TMDb `323903`
- title `The Terror: Devil in Silver`

Scene/source ecosystems may name this as the parent anthology instead:

- parent title `The Terror`
- parent TMDb `75191`
- IMDb `tt2708480`
- season `3`

For the standalone TMDb `323903` route, Fen may honestly find zero sources
because providers index the parent-anthology route. This is an unfortunate
metadata/source-ecosystem edge case, not a reason to add title-specific code.
Do not add special handling for this title.

### Dutton Ranch Blank Metacache

Live debugging found a generic transient metadata problem for TMDb `299167`
(`Dutton Ranch`). Fen had cached a `blank_entry` row with placeholder IDs even
though a direct TMDb API fetch returned valid data.

Relevant code:

- `modules/metadata.py` creates 24-hour `blank_entry` rows.
- `caches/meta_cache.py` stores and clears those rows in both SQLite and Kodi
  window properties.
- `indexers/seasons.py` and source prep can fail before providers are reached
  when show metadata is blank or incomplete.

Safe future fix direction: cache `blank_entry` only for explicit invalid TMDb
responses such as status codes in `invalid_error_codes`, not for transient
`None`/network/no-response conditions. Also guard callers that assume
`season_data` exists. This should be generic; do not add Dutton-specific code.

### No Sources Versus Bad Metadata

A real "no sources" case should remain a real no-sources result. Before trying
to change provider behavior, verify:

- Fen metadata is not a `blank_entry`.
- The requested TMDb/show/season/episode identity matches how providers name
  the media.
- External provider settings and debrid auth are enabled.
- `external.db` is not serving a stale empty result.
- Logs show providers actually ran.

## Useful Commands

From the repo root:

```sh
rg -n "playback.media|sort_subtitle_ready_autoplay|selector_payload" plugin.video.fenlight.patched
python3 -m py_compile plugin.video.fenlight.patched/resources/lib/modules/sources.py plugin.video.fenlight.patched/resources/lib/modules/player.py
tail -n 200 "/Users/kalter/Library/Logs/kodi.log"
sqlite3 "/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.fenlight.patched/databases/metacache.db" "select db_type, tmdb_id, imdb_id, tvdb_id, meta, datetime(expires, 'unixepoch', 'localtime') from metadata where tmdb_id='299167';"
```

For source cache checks, inspect `external.db` rows by `db_type`, `tmdb_id`,
`title`, `season`, and `episode`. Empty cached result rows are evidence of what
Fen/provider search returned at that time; they are not permission to fabricate
sources.

## Guard Rails

- Do not add one-off title fixes for shows like `The Terror: Devil in Silver`.
- Do not fabricate sources or aliases to hide a real no-result provider state.
- Do not move subtitle ranking into `player.py`.
- Do not reintroduce per-source subtitle probing for autoplay.
- Do not assume TMDb Helper's Trakt auth applies to launched player addons.
- Do not edit generated `zips/` mirrors by hand.
- When debugging live Kodi behavior, confirm whether Kodi is running the repo
  copy or the installed addon copy.
