# -*- coding: utf-8 -*-
"""Timing-check the English subtitle before a full-file AI translation (added in 3.23.63).

Translated cues keep the source timing, so the Dutch result can only line up
with the video if the English source does. Before translating, the source is
compared with the embedded English cue timings of the playing video: an
aligned source is used as is, a confirmed fixed offset is applied to a
retimed copy, and a source that does not match is replaced by the best-timed
of up to three other subtitles in the source language. With too little
evidence, or no match, the subtitle is translated as downloaded. The timing
reads wait until `TIMING_READ_START_DELAY_SECONDS` after playback start; if
playback stops or changes meanwhile, nothing is translated. Embedded
subtitle text is never extracted. Log lines start with `AI source timing`.
"""

from a4kSubtitles import selector_handoff as selector
from a4kSubtitles.subtitle_sync import embedded_cue_candidates, retime_srt, subtitle_starts
from a4kSubtitles.timing_rules import (
    FALLBACK_MIN_EXTERNAL_CUES,
    autosync_path,
    best_embedded_match,
    eligible_reference_candidates,
    fallback_match_is_confirmed,
    fallback_match_rank,
    max_embedded_cues,
    offset_to_apply,
    wait_before_timing_reads,
)

# The probe must stay short; a file without a subtitle Cue index then simply
# reports too little evidence and translation goes ahead as before.
AI_SOURCE_TIMING_MAX_SECONDS = 12
AI_SOURCE_MAX_ALTERNATIVES = 3


def read_srt_starts(path):
    with open(path, 'rb') as handle:
        text = handle.read().decode('utf-8-sig')
    return text, subtitle_starts(text)


def timed_copy(path, text, result):
    """Return path, or a retimed copy when the match needs a real shift."""
    offset_ms = offset_to_apply(result)
    if not offset_ms:
        return path, 0
    output_file = autosync_path(path, offset_ms)
    with open(output_file, 'w', encoding='utf-8') as handle:
        handle.write(retime_srt(text, offset_ms))
    return output_file, offset_ms


def best_timed_alternative_source(ctx, reference_candidates, selected_result, language):
    """Download up to three other subtitles in the source language and keep the best confirmed timing match."""
    core, api = ctx.core, ctx.api
    try:
        alternatives = api.search({
            'action': 'search',
            'languages': language,
            'preferredlanguage': language,
        }) or []
    except Exception as exc:
        core.logger.debug('AI source timing: alternative search failed: %s' % exc)
        return None

    selected_identity = selector.result_identity(selected_result)
    confirmed, downloaded, attempted = [], [], 0
    for alternative in alternatives:
        if selector.result_identity(alternative) == selected_identity:
            continue
        attempted += 1
        if attempted > AI_SOURCE_MAX_ALTERNATIVES:
            break
        name = selector.matched_subtitle_name(alternative)
        try:
            alternative_file = api.download(alternative, preserve_existing=True)
            if not alternative_file:
                continue
            downloaded.append(alternative_file)
            text, starts = read_srt_starts(alternative_file)
            if len(starts) < FALLBACK_MIN_EXTERNAL_CUES:
                core.logger.debug('AI source timing: rejected alternative, too few cues | subtitle=%s | cues=%s' % (name, len(starts)))
                continue
            result = best_embedded_match(reference_candidates, starts)
            if not fallback_match_is_confirmed(result):
                core.logger.debug('AI source timing: rejected alternative, no strong timing match | subtitle=%s | result=%s' % (name, result))
                continue
            core.logger.debug('AI source timing: confirmed alternative | subtitle=%s | result=%s' % (name, result))
            confirmed.append((alternative_file, text, result, name))
        except Exception as exc:
            core.logger.debug('AI source timing: alternative comparison failed | subtitle=%s | error=%s' % (name, exc))

    best = max(confirmed, key=lambda item: fallback_match_rank(item[2])) if confirmed else None
    for path in downloaded:
        if best is None or path != best[0]:
            try:
                core.os.remove(path)
            except Exception:
                pass
    if best is None:
        core.logger.debug('AI source timing: no alternative matched the embedded timing | compared=%s' % min(attempted, AI_SOURCE_MAX_ALTERNATIVES))
        return None

    alternative_file, text, result, name = best
    output_file, offset_ms = timed_copy(alternative_file, text, result)
    core.logger.debug(
        'AI source timing: translating better-timed alternative | subtitle=%s | applied_offset_ms=%s | matched_cues=%s | file=%s' % (
            name, offset_ms, result.get('matched_cues'), output_file,
        )
    )
    return output_file


def timing_checked_ai_source(ctx, subfile, selected_result, language):
    """Return the file to translate.

    The original when it is aligned or there is too little evidence, a retimed
    copy for a confirmed fixed offset, or a better-timed alternative when the
    original does not match at all. None when playback stopped or changed while
    waiting for the timing reads, so nothing is translated for nobody.
    """
    core = ctx.core
    try:
        if not core.kodi.get_bool_setting('general', 'auto_sync_subtitles'):
            core.logger.debug('AI source timing check skipped: auto-sync setting is disabled')
            return subfile
    except Exception:
        return subfile

    playback_url = selector.direct_playback_url(core)
    if not playback_url:
        core.logger.debug('AI source timing check skipped: no direct playback URL')
        return subfile

    try:
        text, starts = read_srt_starts(subfile)
    except Exception as exc:
        core.logger.debug('AI source timing check skipped: subtitle unreadable | error=%s' % exc)
        return subfile

    playing_file = core.kodi.xbmc.getInfoLabel('Player.Filenameandpath') or ''
    if not wait_before_timing_reads(core, ctx.monitor, ctx.state.playback_started_at, 'AI source timing'):
        return None
    if (not core.kodi.xbmc.Player().isPlayingVideo()
            or (core.kodi.xbmc.getInfoLabel('Player.Filenameandpath') or '') != playing_file):
        core.logger.debug('AI source timing: playback stopped or changed during the start delay, not translating')
        return None

    reference_candidates = embedded_cue_candidates(playback_url, max_seconds=AI_SOURCE_TIMING_MAX_SECONDS)
    eligible = eligible_reference_candidates(reference_candidates)
    embedded_cues = max_embedded_cues(reference_candidates)
    core.logger.debug(
        'AI source timing probe | embedded_tracks=%s | embedded_cues=%s | subtitle_cues=%s' % (
            len(reference_candidates), embedded_cues, len(starts),
        )
    )
    if not eligible or len(starts) < FALLBACK_MIN_EXTERNAL_CUES:
        core.logger.debug('AI source timing: not enough embedded timing evidence, translating the subtitle as downloaded')
        return subfile

    result = best_embedded_match(eligible, starts)
    if fallback_match_is_confirmed(result):
        output_file, offset_ms = timed_copy(subfile, text, result)
        if offset_ms:
            core.logger.debug(
                'AI source timing: shifted source before translating | offset_ms=%s | matched_cues=%s | file=%s' % (
                    offset_ms, result.get('matched_cues'), output_file,
                )
            )
        else:
            core.logger.debug(
                'AI source timing: source matches embedded timing | detected_offset_ms=%s | matched_cues=%s' % (
                    result.get('offset_ms'), result.get('matched_cues'),
                )
            )
        return output_file

    core.logger.debug('AI source timing: source does not match embedded timing | result=%s' % result)
    alternative = best_timed_alternative_source(ctx, eligible, selected_result, language)
    if alternative:
        return alternative
    core.logger.info('AI source timing: no subtitle matched the embedded timing; translating the selected one anyway')
    return subfile
