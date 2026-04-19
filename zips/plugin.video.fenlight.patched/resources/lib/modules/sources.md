# `sources.py` Notes

This file is the orchestration hub for patched Fenlight autoplay.

It is high-risk because scraping, filtering, selector integration, fallback
promotion, resolution, and playback entry all touch this file.

## High-Level Flow

Relevant path for autoplay:

1. `playback_prep(...)`
2. `get_sources()`
3. source collection and filtering
4. `sort_subtitle_ready_autoplay(...)`
5. `play_source(...)` / `play_file(...)`

## Subtitle-Aware Autoplay Design

The current patched design is:

- collect sources first
- connect to patched a4k API mode once
- gather subtitle results once per title/run
- import the bundled selector integration once
- rank the full source list against the subtitle list
- promote the best subtitle-backed top-5 retry pool
- append the remaining raw source order behind that promoted pool

This is the important change from the older experiment:

- no per-source subtitle probing

## Key Selector Hooks

The selector-related methods worth knowing are:

- `sort_subtitle_ready_autoplay(...)`
- `_get_a4k_subtitles_api(...)`
- `_get_subtitle_selector_integration(...)`
- `_gather_a4k_subtitles_once(...)`
- `_a4k_search_video_meta(...)`
- `_subtitle_search_filename(...)`

## Responsibilities

This file should own:

- source collection
- source filtering
- selector integration wiring
- retry-pool promotion order
- final handoff to playback

This file should not own:

- the detailed subtitle scoring rules
- AI prompt interpretation or TMDb AI-search intent building
- the actual player lifecycle

## Current Behavioral Rules

- subtitle policy comes from the selector, not from ad hoc logic here
- only one subtitle gather should happen per autoplay run/title
- promoted subtitle-backed matches are limited to the best 5
- raw source order is still kept behind the promoted pool as fallback
- bundled selector normalization may preserve meaningful bracketed technical
  segments like quality, codec, and year tokens when they help release-name
  matching

## Future-Agent Guard Rails

- Do not reintroduce per-source subtitle probing.
- Do not move playback logic into the selector integration.
- Do not duplicate subtitle policy here if the selector can own it cleanly.
- Do not move AI-search prompt handling into this file. AI discovery belongs in
  `ai_search.py` before `sources.py` ever runs.
- If ranking looks wrong, inspect the selector package before adding more local
  heuristics in this file.

## Debug Checklist

If subtitle-backed autoplay looks wrong:

- confirm a4k API connection succeeded
- confirm the selector integration module loaded
- confirm only one subtitle gather happened
- inspect the promoted retry-pool log summary
- compare the promoted pool with a shadow trace
- only after that inspect playback resolution and player start behavior
