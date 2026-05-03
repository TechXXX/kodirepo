# a4kSubtitles Patched

This directory is the unpacked main-repo source for the patched a4k subtitle
addon shipped to users alongside `plugin.video.fenlight.patched`.

Future agents should read this file before changing subtitle gathering, manual
subtitle UI, or OpenSubtitles translation handling.

## Why This Addon Exists

This patched build keeps subtitle retrieval inside a4k while making it usable
from Fenlight before playback starts.

Current important behavior:

- supports normal Kodi subtitle search and download flows, including repeated
  in-play manual subtitle searches after a manual pick
- exposes API mode so patched Fenlight can gather subtitles once per title/run
- preserves OpenSubtitles translation flags for ranking and notifications
- prefers built-in subtitle streams before downloading an external file
- shows universal `[AI]`, `[MT]`, and OpenSubtitles-backed `[HD]` badges in
  manual subtitle search rows

## Execution Model

There are three main entry patterns:

1. `main.py`
   Standard Kodi subtitle-addon entrypoint. Clears API mode and calls
   `a4kSubtitles.core.main(...)`.
2. `main_service.py`
   Starts the long-running subtitle service loop through
   `a4kSubtitles.service.start(...)`.
3. `a4kSubtitles/api.py`
   Lets other code, especially patched Fenlight, instantiate
   `A4kSubtitlesApi()` and call `search(...)`, `download(...)`, or
   `auto_load_enabled(...)` without driving the normal Kodi UI flow.

## File Map

- `addon.xml`
  Kodi metadata and addon version.
- `main.py`
  Regular plugin entrypoint for search/download actions.
- `main_service.py`
  Service entrypoint for auto-search/auto-download behavior.
- `a4kSubtitles/api.py`
  API-mode bridge used by patched Fenlight. It mocks Kodi/video metadata for
  pre-play subtitle gathering.
- `a4kSubtitles/core.py`
  Central router for plugin actions like `search` and `download`.
- `a4kSubtitles/search.py`
  Provider orchestration, result normalization, caching, filtering, and addon
  side ordering.
- `a4kSubtitles/download.py`
  Subtitle download, archive extraction, and final subtitle-file placement.
- `a4kSubtitles/service.py`
  Background loop that reacts to playback, prefers built-in subtitles when
  available, and only falls back to external download when needed.
- `a4kSubtitles/services/opensubtitles.py`
  OpenSubtitles auth/search/download request builder and parser. This is where
  translation flags are preserved in result payloads.
- `a4kSubtitles/lib/kodi.py`
  Kodi wrappers, settings access, listitem creation, notifications, and the
  manual-search `[AI]` / `[MT]` / `[HD]` badges.
- `resources/settings.xml`
  User-facing addon settings.
- `CHANGELOG.md`
  Release history only. Read this README first for architecture.

## Current Patched Behaviors That Matter

### API Mode For Fenlight

`A4kSubtitlesApi` is the reason this addon can support the current autoplay
architecture:

- Fenlight connects once
- subtitle search happens once per title/run
- results are returned as data instead of immediate UI output
- the selector ranks the full source list against the full subtitle list

This is the replacement for the older per-source probing experiment.

### Translation-Aware Results

OpenSubtitles rows can carry:

- `ai_translated`
- `machine_translated`

Those flags matter in three places:

- selector policy demotion
- translated-subtitle notifications on actual use
- manual-search row badges

### Manual Search UI

Manual search rows are created in `a4kSubtitles/lib/kodi.py`.

Important current behavior:

- translated rows prepend colored `[AI]` or `[MT]`
- OpenSubtitles `hd` rows also prepend `[HD]`
- the badges live in `label2`, so they work on any Kodi skin
- a4k also sets row properties, but skins only render extra visuals if they
  already have slots for them

### Manual Download Return Path

Manual download still attaches the persisted subtitle file directly so Kodi
shows the chosen release name, but it now also returns the selected file
through Kodi's normal subtitle-service result path.

That extra handoff matters for repeated in-play manual subtitle searches:

- the first manual pick should not poison the next subtitle-search open
- later subtitle-search opens should still reach `action=search` and rebuild
  the subtitle list instead of silently refusing to show it

### Built-In Subtitle Preference

`a4kSubtitles/service.py` first tries to switch to an already available
preferred-language subtitle stream in the player.

Only if no suitable built-in subtitle stream is found does the service continue
into external subtitle download or subtitle search UI.

That behavior must stay aligned with patched Fenlight's goal:

- built-in subtitles should beat external download when the stream already has
  the preferred language

## Future-Agent Guard Rails

- Do not move playback logic into this addon.
- Do not reintroduce per-source subtitle probing for Fenlight autoplay.
- Keep translation flags intact all the way from provider parsing to UI and
  selector consumers.
- Prefer skin-agnostic text markers for universal subtitle-row UI changes.
- If ranking behavior changes, fix selector policy in the selector package
  first, not by adding ad hoc sort rules here unless addon-side ordering truly
  needs it.
