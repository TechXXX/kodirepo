# Fen Light Subtitle Selector Notes

This package is Fen Light Patched's bundled source/subtitle matching layer.
Read this before changing autoplay subtitle ranking.

## Files

- `subtitle_selector.py`
  Deterministic scoring policy for matching source release names to subtitle
  filenames/comments.
- `integration.py`
  Adapter between Fen source dictionaries, a4k subtitle result dictionaries,
  and the standalone selector API.

## Responsibilities

The selector owns:

- release-name normalization
- subtitle filename versus comment scoring
- translated-subtitle demotion
- generic title-only fallback demotion
- returning ranked source/subtitle pairs

The selector does not own:

- Fen source scraping
- a4k provider searches
- Kodi playback
- runtime subtitle download or attachment
- TMDb title alias policy

## Fen/a4k Contract

`integration.rank_kodi_sources_by_subtitles(...)` receives Fen source rows and
a4k subtitle rows. It returns ranked items while preserving the original source
and subtitle objects.

`integration.build_kodi_selector_playback_metadata(...)` attaches runtime
metadata back to a Fen source:

- `selector_source_key`
- `selector_match_score`
- `selector_match_reason`
- `selector_matched_subtitle`
- `selector_requires_ai_translation`
- `selector_subtitle_payload`

`player.py` later publishes `selector_source_key` and
`selector_subtitle_payload` as Kodi window properties for patched a4k's service
loop.

## Change Policy

If a subtitle-backed source is promoted incorrectly, start here. Prefer a
small selector scoring change with a clear fixture or debug trace over an ad
hoc sort rule in `sources.py`.

Do not solve media-title edge cases by hardcoding individual titles. If the
problem is that providers use a different show identity than TMDb, document the
case and keep source results honest.
