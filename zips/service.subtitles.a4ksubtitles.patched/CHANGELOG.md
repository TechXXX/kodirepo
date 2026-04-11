> Maintainer note: Read `README.md` first for the current file map and shipped
> behavior. This file is release history only.

* [v3.23.24](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.24):
  * Promote selector-keyed runtime subtitle attachment to the main repo so autoplay tries the exact selector-matched subtitle for the active playback source before falling back to a fresh runtime search.
  * Keep built-in subtitle preference intact while making selector-forced external subtitle attempts follow the active retry source across autoplay retries.
  * Speed up selector-backed startup attachment by fast-polling during the first playback seconds before the IMDb-gated fallback runtime search path takes over.
  * Shift OpenSubtitles movie retrieval toward IMDb-first searches, then use lighter title and year variants plus filename-year correction fallback when metadata is wrong.
  * On OpenSubtitles download `401`, clear cached auth state, re-login once, and retry the same candidate automatically.

* Session note (2026-04-11):
  * Consume Fenlight's selector-provided subtitle payload at runtime, keyed to the active playback source, so autoplay now tries the exact source/subtitle pairing chosen by the centralized selector before falling back to a fresh runtime search.
  * Keep built-in subtitle stream preference intact while making selector-forced external subtitle attempts source-specific, so retrying from source 1 to source 2 carries the second source's matched subtitle instead of reusing stale runtime ranking.
  * Speed up selector-backed startup attachment by fast-polling during the first few playback seconds and trying the forced selector subtitle before waiting on the IMDb metadata gate used by the fallback runtime search path.
  * Session validation on `Avatar: Fire and Ash` confirmed the live runtime path now logs `Using selector-matched runtime subtitle` and attaches the exact selector-backed LAMA subtitle for the played LAMA source.
  * Shift OpenSubtitles movie retrieval toward IMDb-first API searches, then use lighter title and year variants only as fallback, after manual API checks proved the simpler query shape returned valid results for titles the older constrained path missed.
  * Add filename-year correction for movie OpenSubtitles searches so bad metadata years no longer suppress valid subtitle hits in cases like `Good Luck, Have Fun, Don't Die`.
  * Session validation confirmed the new movie search path recovers automatic Dutch subtitle downloads for titles like `The Bride!` after Kodi reloads the long-running a4k service.
  * On OpenSubtitles download `401`, clear the cached auth state, re-login once, and retry the same download candidate so stale token failures recover instead of forcing an unnecessary provider fallback.
  * Session validation on `Glengarry Glen Ross` confirmed the new recovery path: `401 -> login 200 -> retry download 200 -> subtitle attached`.

* [v3.23.23](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.23):
  * Consume Fenlight's selector-provided subtitle payload at runtime, keyed to the active playback source, so autoplay tries the exact source/subtitle pairing chosen by the selector before falling back to a fresh runtime search.
  * Keep built-in subtitle stream preference intact while making selector-forced external subtitle attempts source-specific across autoplay retries.
  * Speed up selector-backed startup attachment by fast-polling during the first playback seconds and trying the forced selector subtitle before the IMDb-gated fallback runtime search.
  * Shift OpenSubtitles movie retrieval toward IMDb-first searches, then use lighter title and year variants plus filename-year correction fallback when metadata is wrong.
  * On OpenSubtitles download `401`, clear cached auth state, re-login once, and retry the same candidate so stale token failures recover automatically.

* [v3.23.22](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.22):
  * Refresh stale cached OpenSubtitles rows when translation markers are missing so shadow snapshots and downstream selectors do not silently lose `ai_translated` and `machine_translated` state.
  * Make API-mode Fenlight probing survive live Kodi builds where `xbmc.Player().getPlayingFile` is read-only by falling back to mocked a4k video metadata helpers instead of hard-failing the search.
  * Add a backward-compatible `logger.info(...)` alias in the Kodi logger shim so shadow subtitle snapshot logging no longer throws `module 'a4kSubtitles.lib.logger' has no attribute 'info'`.
  * Record the follow-up `Hoppers` investigation result: direct OpenSubtitles API reproduction returns the Dutch `SyncUP` subtitle with `ai_translated=true`, while the active live Kodi a4k runtime path still serializes the same subtitle as `false/false`, so more runtime-path tracing is still required before treating the live issue as fixed.

* [v3.23.21](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.21):
  * Prevent autoplay subtitle preparation from crashing when uploader comments contain Unicode digit separators such as `²`.
  * Rewrite matching-stem runtime subtitle temp filenames before attach so Kodi shows a readable external subtitle name instead of collapsing to generic `(External)`.

* [v3.23.20](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.20):
  * Migrate the Kodi settings dialog to the current schema so provider toggles and account fields no longer reset while switching categories.
  * Restore selector shadow snapshots for multi-provider runs, including paired Fenlight source snapshots plus history-only runtime/manual subtitle snapshots so shared latest shadow aliases stay rebuildable.
  * Make manual subtitle picks bypass Kodi's TempSubtitle handoff and attach the real downloaded file directly so Kodi shows the chosen release name without the old false failed-download notice.

* [v3.23.19](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.19):
  * Refresh packaged branding and artwork so repo installs stop reusing the old selector-test presentation from stale Kodi package caches.

* [v3.23.18](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.18):
  * Add universal [AI]/[MT] badges to manual search subtitle rows so translated results are clearly marked across skins.

* [v3.23.17](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.17):
  * Prefer full OpenSubtitles release names over truncated file names so downstream selector ranking can use the real release stem.
  * Keep API-mode settings overrides compatible with Kodi's read-only Addon object during pre-play subtitle gathers.
  * Refresh cached OpenSubtitles rows when translation markers are missing before selector ranking so `ai_translated` and `machine_translated` state stays accurate.

* [v3.23.13](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.13):
  * Fix comment-fallback ranking crashes in final subtitle selection.

* [v3.23.12](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.12):
  * Use OpenSubtitles uploader comments as a fallback-only compatibility signal after direct filename matching.

* [v3.23.11](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.11):
  * Demote AI and machine-translated subtitle results during final ranking so they only win as fallback.

* [v3.23.10](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.10):
  * Move full release history into CHANGELOG.md so repository metadata stays compact.

* [v3.23.9](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.9):
  * Fix OpenSubtitles download retries and cleanup after failed downloads.
  * Improve subtitle ranking for prerelease and release-family mismatches.
  * Add resilient OpenSubtitles movie fallback search when year metadata is wrong.
  * Show a notification when an AI or machine translated subtitle is selected.

* [v3.23.7](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.7):
  * Relax OpenSubtitles TV episode IMDb filtering in API-mode pre-play searches so valid episode subtitle results survive to Fenlight matching.

* [v3.23.6](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.6):
  * Add targeted search pipeline logging for API-mode pre-play debugging, including raw service results and each prepare/filter stage.

* [v3.23.5](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.5):
  * Mock the full video metadata entrypoint in API mode so subtitle probing can run before playback without Kodi player state.

* [v3.23.4](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.4):
  * Skip immutable xbmcvfs.File method overrides in live Kodi so API-mode subtitle probing can continue without mocked size/hash methods.

* [v3.23.3](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.3):
  * Fix API-mode filename mocking fallback for live Kodi by avoiding Python name-mangling on the internal video helper.

* [v3.23.2](https://github.com/newt-sc/a4kSubtitles%20Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.2):
  * Make API-mode video metadata mocking compatible with live Kodi Player objects.

* [v3.23.1](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.1):
  * Fix overwriting existing subtitles during auto-download.

* [v3.23.0](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.23.0):
  * Fix Podnadpisi download handling.
  * Reduce logs verbosity without debug enabled.

* [v3.22.0](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.22.0):
  * Fix Podnadpisi service returning incorrect language codes.

* [v3.21.5](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.21.5):
  * SubSource: Fix language handling so all regional variants are detected instead of only one.

* [v3.21.4](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.21.4):
  * SubSource: Fix foreign language handling in the new API.
  * Metainfo: Fix IMDb release year to correctly pull the first release date for TV shows.

* [v3.21.3](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.21.3):
  * SubSource: Fix and update API (now requires API key)

* [v3.21.2](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.21.2):
  * SubSource: Fix and update API

* [v3.21.1](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.21.1):
  * Dynamic AI subtitles translation from English to the selected Preferred Language in KODI's settings
    * Requires API Key
    * Currently only OpenAI and NexosAI backends are supported
    * For NexosAI model should be specified by ID, not name
    * Turning AI translation on - disables usage of embedded subtitles
    * Currently only supported when using auto-search or auto-download feature

* [v3.20.0](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.20.0):
  * Auto download/selection improvements (by bbviking)

* [v3.19.1](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.19.1):
  * Parse subtitles version

* [v3.19.0](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.19.0):
  * Lower OpenSubtitles token cache from 7 days to 1 day
  * Fix auto download stopping after first failed subtitle download
  * Fix wrong language set for results when multiple languages are configured (Thanks to @peno64)

* [v3.18.3](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.18.3):
  * Auto Download: Fix selecting incorrect episode in archive file

* [v3.18.2](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.18.2):
  * SubSource: Fix foreign languages

* [v3.18.1](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.18.1):
  * Fix IMDB ID not found

* [v3.18.0](https://github.com/newt-sc/a4kSubtitles Patched/releases/tag/service.subtitles.a4ksubtitles.patched%2Fservice.subtitles.a4ksubtitles.patched-3.18.0):
  * Use the newer InfoTagVideo KODI API (contributed by @kiamvdd)
