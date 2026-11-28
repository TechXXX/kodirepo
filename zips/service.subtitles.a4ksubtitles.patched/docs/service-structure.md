# Playback service structure

The long-running Kodi service (`main_service.py` → `a4kSubtitles.service.start`)
watches playback, picks and attaches subtitles, checks their timing and runs AI
translation. Until 3.23.63 almost all of it lived in one 1,550-line `start()`
function with 42 nested functions sharing state through `nonlocal`. The
refactor below split it into modules with one explicit state object. The
behavior and every log line stayed the same.

Read this before changing any of the modules below, and update it when you
move, add or remove a function.

## Modules

| Module | Job | Main entry points |
| --- | --- | --- |
| `service.py` | The poll loop only: settings checks, playback-change detection, fast polling while a selector payload waits, then hands off. | `start(api)` |
| `service_state.py` | All per-playback state and the context passed everywhere. | `PlaybackState`, `ServiceContext` |
| `subtitle_attach.py` | One pass per video: existing stream, Fen selector pick, runtime search. Direct attach starts background sync; the English AI fallback is timing-checked, then translated. | `attach_runtime_subtitle`, `download_and_attach_result`, `update_sub_stream`, `prepare_runtime_attach_subfile` |
| `selector_handoff.py` | Fen Light Patched selector window properties, and checks that a payload belongs to the video playing now. | `forced_subtitle_result`, `payload_requires_ai_translation`, `direct_playback_url`, `current_playing_url`, `result_identity`, `matched_subtitle_name` |
| `ai_translate.py` | AI settings, the `gpt-6-luna` pin, full-file translation with live partial attach and stop on playback end, and the older chunked mode. | `ai_settings`, `pinned_ai_model`, `disable_ai_without_api_key`, `translate_and_attach_subfile`, `translate_next_chunk` |
| `ai_source_timing.py` | 3.23.63 check of the English source against the embedded timing before a full-file translation; can retime it or swap in a better-timed alternative. Logs start with `AI source timing`. | `timing_checked_ai_source` |
| `background_sync.py` | Daemon thread that checks a directly attached subtitle against the embedded timing, retimes it or replaces it. Logs start with `Background subtitle`. | `start_background_subtitle_sync` |
| `timing_rules.py` | Thresholds and decisions shared by both timing checks. | `best_embedded_match`, `fallback_match_is_confirmed`, `fallback_match_rank`, `offset_to_apply`, `autosync_path` |
| `runtime_languages.py` | Language-code helpers. | `language_code`, `normalize_language_list`, `subtitle_result_matches_languages`, `remove_english_search_languages_for_ai` |
| `subtitle_sync.py` (unchanged) | Reads embedded cue start times from the Matroska Cue index over bounded HTTP range reads, and matches cue timelines. | `embedded_cue_candidates`, `find_best_offset`, `subtitle_starts`, `retime_srt` |

Imports only go down this table: `service` → `subtitle_attach` → (`ai_translate`,
`ai_source_timing`, `background_sync`) → (`selector_handoff`, `timing_rules`,
`runtime_languages`) → `subtitle_sync`. Nothing imports `service.py`, and no
module imports Kodi directly: everything goes through `ctx.core`, which is what
lets the tests run without Kodi.

## State

`ServiceContext` holds `api`, `core`, `monitor` and `state`. Functions that need
more than `core` take `ctx` as their first argument. `PlaybackState` fields
(documented in `service_state.py`):

- `has_done_subs_check`: this video has been handled.
- `prev_playing_filename`: the video being handled.
- `fast_selector_poll_until`, `subtitle_stream_settle_until`: poll timing.
- `ai_last_timestamp`, `ai_tries`, `ai_translation_active`, `ai_translation_source`:
  AI translation progress.
- `attached_subtitle_active`: keep the temp folder while a4k's subtitle is in use.
- `sync_started_subfiles`: background sync workers already started.
- `last_subfile`: kept across `reset()` on purpose.

`state.reset()` runs when playback stops or the video changes.

## One video, start to finish

1. `service.start` notices a new video, resets state and opens a 5-second
   window (`subtitle_stream_settle_until`) for an embedded Dutch track to appear.
2. `subtitle_attach.attach_runtime_subtitle`:
   - `update_sub_stream` picks a preferred-language stream the player already
     has. An embedded track always wins; a sidecar only after the 5 seconds.
   - Otherwise `selector_handoff.forced_subtitle_result` gives Fen's pick. A
     Dutch pick is attached directly and `background_sync` checks its timing.
     An English pick with `requires_ai_translation` goes through
     `ai_source_timing.timing_checked_ai_source`, then
     `ai_translate.translate_and_attach_subfile(..., full_file=True)`.
   - Otherwise a runtime search in the preferred languages
     (`keep_translated=True`, it never AI-translates).
3. The full-file translation stops before the next batch when playback stops or
   another video plays, and the loop resets.

## Decisions that must survive later changes

- An embedded subtitle track in the preferred language is always preferred.
- a4k never extracts embedded subtitle text. Timing comes from the Matroska Cue
  index (`subtitle_sync.py`), which works on every device. An ffmpeg/ffprobe
  extraction path existed but was never called and was removed in the first
  refactor step; Android TV devices such as the Shield have no ffmpeg. Do not
  bring it back. If the embedded English text is ever needed, it has to come
  from a pure-Python reader, not a binary.
- Automatic (API mode) searches drop other sites' AI/machine translations when
  a4k can translate itself (`search.__drop_translated_results`); the runtime
  search passes `keep_translated=True` because it never AI-translates.
- The OpenAI model stays pinned to `gpt-6-luna` (see README for all three pins).
- Timing replacement stays conservative: a weak or ambiguous probe leaves the
  subtitle as it is (`timing_rules.py`, `docs/subtitle-timing-validation.md`).
- Every log line keeps its wording; the owner and earlier reports search the
  Kodi log for them.

## Tests

`tests/service_fakes.py` has a fake `core` (Kodi, player, settings, window
properties), a fake API that serves SRT text per result name, and timeline
helpers. `tests/test_service_modules.py` covers state, selector hand-off,
languages and AI settings; `tests/test_service_flow.py` covers the timing check
outcomes, full-file and chunked translation, attach paths and one run of the
real poll loop. Run `python3 -m unittest discover -s tests` from the addon folder.

## Refactor history

Done in one release after 3.23.63, tested live by the owner before publishing:

1. Deleted the unused ffmpeg/ffprobe embedded-extraction code (11 functions)
   and a branch for an `'embedded_english'` source no caller sent. service.py
   went from 1,904 to 1,614 lines.
2. Moved AI translation to `ai_translate.py`, with `PlaybackState` replacing
   the shared `nonlocal` variables.
3. Moved the selector hand-off to `selector_handoff.py` and the source timing
   check to `ai_source_timing.py`; the shared thresholds went to
   `timing_rules.py`, background sync to `background_sync.py`.
4. Left `service.start()` as the poll loop (about 90 lines); attaching moved to
   `subtitle_attach.py`.
5. Added `tests/service_fakes.py`, `test_service_modules.py` and
   `test_service_flow.py` (28 tests).

Module-level names lost their leading underscore when they moved (for example
`_offset_to_apply` is now `timing_rules.offset_to_apply`).
