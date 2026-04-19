# `player.py` Notes

This file owns playback handoff and player-state monitoring for patched
Fenlight.

For subtitle-selector work, the most important rule is simple:

- ranking belongs in the selector and `sources.py`
- playback handoff belongs here

## Main Flow

The normal foreground path is:

1. `FenLightPlayer.run(...)`
2. `play_video(...)`
3. `make_listing(...)`
4. `_hybrid_resolve_handoff(...)`
5. fallback to `self.play(...)` if playback is not already active
6. `check_playback_start(...)`
7. `monitor(...)`

`run_resolved(...)` still exists, but it is not the preferred path for the
validated local setup.

## Why The Hybrid Handoff Exists

This file keeps the current hybrid handoff because the older stop-time popup
was linked to missing resolved-URL bookkeeping.

Current behavior:

- call `setResolvedUrl(...)` through `kodi_utils.set_resolved_url(...)`
- wait briefly to see if Kodi starts playback immediately
- if playback did not start, call direct `self.play(...)`

That gives the local machine both:

- the bookkeeping Kodi seems to want
- the direct playback fallback that kept playback reliable

## Responsibilities

This file should own:

- playback listitem construction
- resume-point setup
- playback-start detection
- watch-state and bookmark updates
- next-episode preparation
- dialog cleanup around successful playback

This file should not own:

- AI-search prompt interpretation
- TMDb result building for AI-search flows
- subtitle ranking policy
- subtitle/source compatibility heuristics
- subtitle search orchestration

## Future-Agent Guard Rails

- Do not move selector logic into this file.
- Do not move AI-search discovery logic into this file.
- Do not casually switch everything back to `run_resolved()`.
- Do not remove `_hybrid_resolve_handoff(...)` without re-testing the old stop
  regression on the target Kodi machine.
- If playback fails, inspect the source caller and resolve path before blaming
  the selector.

## Debug Checklist

If playback behavior looks wrong:

- check whether `setResolvedUrl(...)` succeeded
- check whether direct `self.play(...)` fallback ran
- check whether `check_playback_start(...)` saw `isPlayingVideo()`
- check whether the player ever entered `monitor(...)`
- separate source-ranking success from playback-start success
