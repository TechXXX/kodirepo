## sources.py notes

- This module does much more than scraping. It also filters, ranks, promotes, resolves, and starts playback.
- It is one of the highest-risk files for regressions because source ranking, subtitle matching, and playback handoff all meet here.

## Current playback rule

- For resolved playback attempts, use `player.run(url, self)`.
- Do not route foreground resolved playback through `player.run_resolved()` unless the target environment has been verified.
- This direct playback path fixed a real macOS Kodi playback issue where resolved Real-Debrid links were valid but Kodi failed when Fenlight used the resolver handoff path.

## Subtitle-aware ranking

- Subtitle probing and source promotion logic lives here.
- The intent is to prefer the source whose release name best matches the top-ranked a4k subtitle result.
- Release-name normalization, release-group extraction, and feature-alignment scoring are all part of that behavior.
- Changes in this area can improve subtitle matching, but can also reshuffle autoplay order or preferred source selection.

## Debugging guidance

- If subtitles look correct but the wrong source is promoted, inspect the subtitle match score helpers first.
- If Real-Debrid resolves successfully but playback fails, inspect the playback call site before assuming resolution is broken.
- When debugging Kodi logs, separate:
  - subtitle search/probe success
  - source resolution success
  - actual player start success

## Caution

- Future cleanup work may be tempted to remove the direct playback call because `run_resolved()` looks more explicit. Do not change that casually.
- Small edits here can affect autoplay, manual source choice, resolver retries, subtitle promotion, and debrid playback behavior at the same time.
