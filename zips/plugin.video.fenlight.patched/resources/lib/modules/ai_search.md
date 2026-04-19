# `ai_search.py` Notes

This file owns natural-language discovery for patched Fenlight.

It is intentionally separate from `sources.py` and `player.py` because AI
search is a discovery concern, not a source-ranking or playback concern.

## High-Level Flow

Relevant paths:

1. `ai_search.run(...)`
2. `_get_prompt(...)`
3. `GeminiAPI().interpret_prompt(...)`
4. `_build_result_payload(...)`
5. `_render_results(...)`

Widget/history path:

1. `ai_search.widget(...)`
2. `_cached_results(...)` or `_get_result_payload(...)`
3. `_render_results(...)`

## Current Design

The current patched design is:

- capture a free-form user prompt
- store that prompt in local Fenlight search history
- ask Gemini only for structured intent
- keep named-person intent separate from generic theme keywords
- keep TMDb as the source of truth for the displayed results
- prefer TMDb discover when genre/keyword/cast intent is strong enough
- fall back to TMDb title and keyword seeding when discover is too thin
- cache both interpreted intent and built result payloads for reuse

This is the important rule:

- Gemini suggests intent, but TMDb still provides the actual media list

## Responsibilities

This file should own:

- prompt capture and prompt reuse
- AI-search history integration
- Gemini intent-to-structure translation handoff
- TMDb discover/search payload construction
- person-to-cast resolution for movie discovery
- result-payload caching for repeat prompts

This file should not own:

- source scraping
- subtitle ranking
- autoplay retry-pool logic
- playback handoff

## Key Hooks

The main methods worth knowing are:

- `run(...)`
- `widget(...)`
- `results(...)`
- `_get_result_payload(...)`
- `_build_result_payload(...)`
- `_build_discover_url(...)`
- `_resolve_cast_ids(...)`
- `_intent_keyword_terms(...)`
- `_title_seed_results(...)`
- `_keyword_fallback_results(...)`

## Future-Agent Guard Rails

- Keep TMDb as the final source of truth for rendered results.
- Do not let the LLM directly choose final playable sources.
- Do not move subtitle or playback policy into this module.
- If result quality looks wrong, inspect genre, keyword, and people/cast
  resolution before changing downstream source logic.
- If you add new AI providers later, keep the structured-intent contract stable
  so the TMDb rendering path does not fork unnecessarily.

## Debug Checklist

If AI Search looks wrong:

- confirm `fenlight.gemini_api` is populated
- confirm `GeminiAPI().interpret_prompt(...)` returned structured data
- inspect whether discover mode or fallback mode was chosen
- compare the resolved genres, keywords, and people/cast matches with TMDb
  responses
- only after that inspect source scraping or playback behavior
