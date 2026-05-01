# DutchTech Kodi Repository

This repository is the main GitHub Pages distribution channel for DutchTech
Kodi packages.

For subtitle-selector and AI-search promotion work, this repo matters because
it is the production-facing package source for the patched Fenlight, the
standalone Fen Light AIsearch fork, and the patched a4k addon.

## Addons In This Repo

Current source-tree versions when this document was updated:

- `plugin.video.fenlight` `2.0.15`
  Baseline Fenlight package.
- `plugin.video.fenlight.aisearch` `1.0.7`
  Standalone AI-search fork with its own addon id, profile, artwork, and repo
  package. The production build keeps its built-in updater pointed at
  `kodirepo`, and it now supports up to three Gemini API keys with automatic
  fallback on rate-limit or quota-exhaustion responses.
- `plugin.video.fenlight.patched` `2.0.53`
  Main patched Fenlight build that bundles the selector locally and uses the
  centralized subtitle-aware retry-pool architecture. It now also includes the
  Gemini-backed AI Search entrypoint from the tested repo channel, multi-key
  Gemini fallback, a top-10 subtitle-backed retry pool, and selector comment
  alias promotion for stronger same-item release matches. The current
  production build also adds TMDb metadata language and fallback-language
  controls for movie, TV, collection, season, episode, and people details, now
  shows an explicit Trakt authorization status row in settings, strips tracker
  suffix noise like `.rartv.` and `.eztv` before subtitle release-group
  matching, and only skips blocked pirate-language sources when every detected
  audio stream is Russian, Ukrainian, or Chinese. It now also fixes local
  resume bookmark cleanup on newer Kodi video databases.
- `plugin.video.themoviedb.helper.patched` `6.15.2.8`
  Patched TMDb Helper production build used by the patched Arctic Horizon 2
  flow. The current production build includes the recommendations-window fixes
  and debug logging previously validated in the test repo. It now also switches
  OMDb lookups to the JSON endpoint while backfilling missing cached IMDb and
  OMDb ratings more reliably. It now also ships a bundled default OMDb API key
  for repo installs.
- `service.subtitles.a4ksubtitles.patched` `3.23.30`
  Main patched a4k build used with selector-aware Fenlight. The current
  production build searches OpenSubtitles TV episodes by parent show IMDb id
  plus season/episode before text fallbacks, so numeric show titles like
  `1923` return the full episode subtitle set for selector ranking.
- `service.kodi.favourites.sync` `0.2.36`
  Separate Google Drive favourites sync addon.
- `skin.arctic.horizon.2.patched` `0.8.30.5`
  Patched Arctic Horizon 2 production build intended to target
  `plugin.video.themoviedb.helper.patched` from this repo.
- `skin.arctic.horizon.2.1` `0.0.1`
  Forked skin package shipped by this repo.
- `repository.dutchtech` `1.0.42`
  The repository addon Kodi installs first.

## Layout

- `plugin.video.fenlight.aisearch/`
  Standalone Fen Light AIsearch source.
- `plugin.video.fenlight.patched/`
  Unpacked patched Fenlight source.
- `plugin.video.themoviedb.helper.patched/`
  Unpacked patched TMDb Helper source.
- `service.subtitles.a4ksubtitles.patched/`
  Unpacked patched a4k source.
- `plugin.video.fenlight/`
  Baseline Fenlight source kept for comparison or non-patched shipping.
- `service.kodi.favourites.sync/`
  Favourites sync service source.
- `skin.arctic.horizon.2.patched/`
  Patched Arctic Horizon 2 source that targets the patched TMDb Helper addon
  id from this repo.
- `skin.arctic.horizon.2.1/`
  Forked skin source.
- `scripts/`
  Repo build and publish helpers.
- `zips/`
  Generated installable addon packages. Do not hand-edit these.
- `addons.xml`
  Kodi metadata for every addon in the repo.
- `addons.xml.md5`
  Checksum for `addons.xml`.

## Docs To Read First

For selector, AI-search, or packaging work in this repo, read:

1. `README.md`
2. `scripts/README.md`
3. `plugin.video.fenlight.patched/resources/lib/modules/ai_search.md`
4. `plugin.video.fenlight.patched/resources/lib/modules/sources.md`
5. `plugin.video.fenlight.patched/resources/lib/modules/player.md`
6. `service.subtitles.a4ksubtitles.patched/README.md`
7. `plugin.video.themoviedb.helper.patched/Readme.md`
8. `skin.arctic.horizon.2.patched/Readme.md`
9. `skin.arctic.horizon.2.1/Readme.md`

## Selector-Relevant Addon Responsibilities

### `plugin.video.fenlight.patched`

This addon now owns:

- source scraping and filtering
- one-shot subtitle gather orchestration
- selector-backed retry-pool promotion
- TMDb-backed AI Search result building from Gemini prompt interpretation
- playback resolution and player handoff

It should not own the detailed subtitle policy rules. Those belong in the
selector package and its vendored copy. AI prompt interpretation and result
building also belong in `modules/ai_search.py`, not in `sources.py` or
`player.py`.

The current production Fen Light Patched build also skips autoplay sources
whose detected audio streams are Russian-only, Ukrainian-only, or Chinese-only
unless the selected title metadata already expects that spoken language.

It now also uses the show's original or English title plus the actual episode
name when building TV subtitle-search metadata and filenames.

### `plugin.video.fenlight.aisearch`

This addon now owns:

- standalone Gemini-backed AI Search flows
- TMDb-backed result rendering from structured intent
- its own updater path and settings surface

It should stay aligned with the tested search behavior in the test repo, while
keeping production updater defaults pointed at `kodirepo`.

That production-specific updater default matters because the shipped main build
should not pull users back onto the test channel.

### `service.subtitles.a4ksubtitles.patched`

This addon now owns:

- subtitle provider queries
- OpenSubtitles translation-flag capture
- addon-side subtitle ordering and download handling
- manual-search UI badges like `[AI]` and `[MT]`
- built-in subtitle preference before external download

It should not own Fenlight playback logic.

### `plugin.video.themoviedb.helper.patched`

This addon owns the patched recommendations-window flow used by the patched
skin.

That distinction matters because:

- recommendation list item normalization lives here
- keyword/info navigation fixes belong here
- helper-side debug logging for recommendation routing belongs here

### `skin.arctic.horizon.2.patched`

This skin owns the patched Kodi-side rendering that targets
`plugin.video.themoviedb.helper.patched`.

That distinction matters because:

- helper integration ids must match the patched helper addon
- stale recommendation-window properties must be cleared from the skin side

The current production patched skin also ships the Inter font family with
matching info-panel, rating, and hub-layout refinements. It now also gives
Next Page placeholder items dedicated fallback artwork/background handling so
they stop reusing stray media and plot text.
- visual recommendation-dialog behavior depends on skin XML, not helper Python

### `skin.arctic.horizon.2.1`

This addon owns Kodi-side rendering, not subtitle policy.

That distinction matters because:

- addon-only text changes show everywhere
- extra badge or icon slots in dialogs require skin layout support

## Script Workflows

The scripts are documented in `scripts/README.md`.

Short version:

- use `scripts/build_repo.py` when the repository addon itself or the repo-wide
  metadata needs a full rebuild
- use `scripts/publish_addon_update.py` when publishing an addon update without
  bumping the repository addon version

Important future-agent nuance:

- the `publish_addon_update.py` command-line flow is built around the "drop a
  new addon zip in the repo root" workflow
- if you already edited the unpacked source tree in place, you may need to call
  that script's helper functions or regenerate `zips/<addon-id>/` manually
  instead of relying on the CLI import step

## Generated Output Rules

- treat `zips/` as generated output
- if addon-local docs change, regenerate the matching package mirror under
  `zips/`
- keep addon `addon.xml` files focused on Kodi metadata, not release-history
  storage
- do not turn addon `addon.xml` `<news>` blocks into multi-version changelogs;
  use dedicated changelog files such as `CHANGELOG.md` or addon-owned changelog
  text files instead
- if `addon.xml` changes, also regenerate `addons.xml`
- do not edit `addons.xml.md5` by hand

## Scope Guard Rails

- subtitle-selector migration work belongs primarily in:
  - `plugin.video.fenlight.patched`
  - `service.subtitles.a4ksubtitles.patched`
- standalone AI-search promotion work belongs primarily in:
  - `plugin.video.fenlight.aisearch`
  - `plugin.video.fenlight.patched/resources/lib/modules/ai_search.py`
- baseline Fenlight is a reference point, not the main landing zone for new
  selector behavior
- unrelated addons and the skin should only be touched when the user-facing
  behavior truly depends on them
