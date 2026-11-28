# -*- coding: utf-8 -*-
"""Background subtitle sync: line an attached subtitle up with the embedded English timing.

After a4k attaches a downloaded subtitle directly (not AI-translated), a
daemon thread reads the embedded subtitle cue starts from the playing file's
Matroska Cue index (`subtitle_sync.embedded_cue_candidates`, bounded HTTP
range reads) and compares them with the subtitle's cue starts. A confirmed
fixed offset is applied to a retimed `.autosync.` copy; a subtitle with no
strong match is replaced by the best confirmed of up to three alternatives in
the same language. The timing reads wait until
`TIMING_READ_START_DELAY_SECONDS` after playback start, so they do not compete
with Kodi buffering the start of the video. Log lines start with `Background subtitle`.
"""

import threading

from a4kSubtitles import selector_handoff as selector
from a4kSubtitles.subtitle_sync import embedded_cue_candidates, retime_srt, subtitle_starts
from a4kSubtitles.timing_rules import (
    FALLBACK_MIN_EMBEDDED_CUES,
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


def start_background_subtitle_sync(ctx, subfile, selected_result=None):
    """Align a newly attached external SRT without delaying playback."""
    core, api, monitor = ctx.core, ctx.api, ctx.monitor
    if not subfile:
        core.logger.debug('Background subtitle sync skipped: no subtitle file was attached')
        return
    if '.autosync.' in core.os.path.basename(subfile):
        core.logger.debug('Background subtitle sync skipped: subtitle was already timing-adjusted | subtitle=%s' % subfile)
        return
    try:
        if not core.kodi.get_bool_setting('general', 'auto_sync_subtitles'):
            core.logger.debug('Background subtitle sync skipped: auto-sync setting is disabled | subtitle=%s' % subfile)
            return
    except Exception as exc:
        core.logger.debug('Background subtitle sync skipped: unable to read auto-sync setting | error=%s' % exc)
        return

    playback_url = selector.current_playing_url(core)
    if playback_url.startswith('plugin://'):
        playback_url = core.kodi.get_property(selector.selector_playback_url_prop) or ''
    if not playback_url or playback_url.startswith('plugin://'):
        core.logger.debug(
            'Background subtitle sync skipped: no direct playback URL | player=%s | selector_url=%s' % (
                selector.current_playing_url(core), core.kodi.get_property(selector.selector_playback_url_prop) or '',
            )
        )
        return

    sync_key = '%s|%s' % (playback_url, subfile)
    if sync_key in ctx.state.sync_started_subfiles:
        core.logger.debug('Background subtitle sync skipped: worker already queued for subtitle | subtitle=%s' % subfile)
        return
    ctx.state.sync_started_subfiles.add(sync_key)
    playback_started_at = ctx.state.playback_started_at
    selector_source_key = core.kodi.get_property(selector.selector_source_key_prop)
    core.logger.debug(
        'Background subtitle sync queued | subtitle=%s | playback=%s | selector_source=%s' % (
            subfile, selector.short_text(playback_url), selector.short_text(selector_source_key),
        )
    )

    def playback_is_current():
        """Avoid work and UI changes after Kodi has moved to another item."""
        if monitor.abortRequested():
            core.logger.debug('Background subtitle sync playback guard failed: service is stopping')
            return False
        if not core.kodi.xbmc.Player().isPlayingVideo():
            core.logger.debug('Background subtitle sync playback guard failed: video is no longer playing')
            return False
        current_url = selector.current_playing_url(core)
        normalized_current_url = current_url
        # Kodi continues to report the Fen plugin URL for a short period
        # after attaching the subtitle, while the selector already holds
        # the direct stream URL used to start this worker.  Treat those
        # two representations as the same playback until Kodi catches up.
        if current_url.startswith('plugin://'):
            normalized_current_url = core.kodi.get_property(selector.selector_playback_url_prop) or current_url
        if normalized_current_url != playback_url:
            core.logger.debug(
                'Background subtitle sync playback guard failed: playback URL changed | expected=%s | current=%s | normalized=%s' % (
                    selector.short_text(playback_url),
                    selector.short_text(current_url),
                    selector.short_text(normalized_current_url),
                )
            )
            return False
        current_source_key = core.kodi.get_property(selector.selector_source_key_prop)
        if selector_source_key and current_source_key and current_source_key != selector_source_key:
            core.logger.debug(
                'Background subtitle sync playback guard failed: selector source changed | expected=%s | current=%s' % (
                    selector.short_text(selector_source_key), selector.short_text(current_source_key),
                )
            )
            return False
        return True

    def try_timing_validated_fallback(reference_candidates, external_starts):
        """Only replace a rejected subtitle with a proven timing match."""
        embedded_cues = max_embedded_cues(reference_candidates)
        # A missing Cue index is not evidence that the selected subtitle is
        # bad.  Require a useful amount of broad embedded evidence before
        # spending network requests on fallback candidates.  The threshold
        # applies to one track: timings across separate English tracks must
        # never be combined as if they were one reference timeline.
        if embedded_cues < FALLBACK_MIN_EMBEDDED_CUES or len(external_starts) < FALLBACK_MIN_EXTERNAL_CUES:
            core.logger.debug(
                'Background subtitle fallback skipped: insufficient timing evidence | embedded_cues=%s | embedded_tracks=%s | subtitle_cues=%s' % (
                    embedded_cues, len(reference_candidates), len(external_starts),
                )
            )
            return False

        if not playback_is_current():
            core.logger.debug('Background subtitle fallback cancelled: playback changed before candidate search')
            return False

        selected_identity = selector.result_identity(selected_result)
        selected_language = ((selected_result or {}).get('lang') or
                             ((selected_result or {}).get('action_args') or {}).get('lang') or '')
        if not selected_language:
            return False

        try:
            alternatives = api.search({
                'action': 'search',
                'languages': selected_language,
                'preferredlanguage': selected_language,
            }) or []
        except Exception as exc:
            core.logger.debug('Background subtitle fallback search failed: %s' % exc)
            return False

        attempted = 0
        confirmed = []
        for alternative in alternatives:
            if selector.result_identity(alternative) == selected_identity:
                continue
            attempted += 1
            if attempted > 3:
                break
            candidate_name = selector.matched_subtitle_name(alternative)
            if not playback_is_current():
                core.logger.debug(
                    'Background subtitle fallback cancelled: playback changed before candidate | subtitle=%s' % candidate_name
                )
                return False
            try:
                core.logger.debug(
                    'Background subtitle fallback comparing candidate | index=%s | subtitle=%s' % (
                        attempted, candidate_name,
                    )
                )
                alternative_file = api.download(alternative, preserve_existing=True)
                if not alternative_file:
                    core.logger.debug(
                        'Background subtitle fallback rejected candidate: download produced no subtitle file | subtitle=%s' % candidate_name
                    )
                    continue
                with open(alternative_file, 'rb') as handle:
                    alternative_bytes = handle.read()
                alternative_text = alternative_bytes.decode('utf-8-sig')
                alternative_starts = subtitle_starts(alternative_text)
                if len(alternative_starts) < FALLBACK_MIN_EXTERNAL_CUES:
                    core.logger.debug(
                        'Background subtitle fallback rejected candidate: insufficient external cues | subtitle=%s | subtitle_cues=%s' % (
                            candidate_name, len(alternative_starts),
                        )
                    )
                    continue
                alternative_result = best_embedded_match(
                    reference_candidates, alternative_starts
                )
                if not fallback_match_is_confirmed(alternative_result):
                    core.logger.debug(
                        'Background subtitle fallback rejected candidate: no strong timing match | subtitle=%s | subtitle_cues=%s | result=%s' % (
                            candidate_name, len(alternative_starts), alternative_result,
                        )
                    )
                    continue
                core.logger.debug(
                    'Background subtitle fallback confirmed candidate | subtitle=%s | result=%s' % (
                        candidate_name, alternative_result,
                    )
                )
                confirmed.append((alternative_file, alternative_text, alternative_result, candidate_name))
            except Exception as exc:
                core.logger.debug(
                    'Background subtitle fallback rejected candidate: comparison failed | subtitle=%s | error=%s' % (
                        candidate_name, exc,
                    )
                )
        if not confirmed:
            core.logger.debug('Background subtitle fallback completed: all compared candidates rejected | attempted=%s' % attempted)
            return False

        best = max(confirmed, key=lambda item: fallback_match_rank(item[2]))
        for candidate in confirmed:
            if candidate is not best:
                core.logger.debug(
                    'Background subtitle fallback rejected candidate: weaker confirmed timing fit | subtitle=%s | result=%s | selected=%s' % (
                        candidate[3], candidate[2], best[3],
                    )
                )

        # Do not attach a completed worker result to a later episode.
        if not playback_is_current():
            core.logger.debug('Background subtitle fallback cancelled: playback changed before attach')
            return False
        alternative_file, alternative_text, alternative_result, candidate_name = best
        detected_offset_ms = alternative_result['offset_ms']
        offset_ms = offset_to_apply(alternative_result)
        output_file = alternative_file
        if offset_ms:
            output_file = autosync_path(alternative_file, offset_ms)
            with open(output_file, 'w', encoding='utf-8') as handle:
                handle.write(retime_srt(alternative_text, offset_ms))
        if not playback_is_current():
            core.logger.debug('Background subtitle fallback cancelled: playback changed before attach')
            return False
        core.kodi.xbmc.Player().setSubtitles(output_file)
        try:
            core.kodi.xbmc.Player().showSubtitles(True)
        except:
            pass
        core.kodi.notification('Subtitle fallback matched timing: %s' % candidate_name, time=5000)
        core.logger.debug(
            'Background subtitle fallback applied | detected_offset_ms=%s | applied_offset_ms=%s | method=%s | matched_cues=%s | from=%s | to=%s' % (
                detected_offset_ms, offset_ms,
                alternative_result.get('method', 'unknown'), alternative_result['matched_cues'], subfile, output_file,
            )
        )
        return True

    def worker():
        try:
            if not playback_is_current():
                core.logger.debug('Background subtitle sync cancelled before probe: playback is no longer current | subtitle=%s' % subfile)
                return
            core.logger.debug('Background subtitle sync worker started | subtitle=%s' % subfile)
            if not wait_before_timing_reads(core, monitor, playback_started_at, 'Background subtitle sync'):
                return
            if not playback_is_current():
                core.logger.debug('Background subtitle sync cancelled after the start delay: playback is no longer current | subtitle=%s' % subfile)
                return
            with open(subfile, 'rb') as handle:
                original_bytes = handle.read()
            try:
                original_text = original_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                core.logger.debug('Background subtitle sync skipped: external SRT is not UTF-8')
                return

            original_starts = subtitle_starts(original_text)
            core.logger.debug(
                'Background subtitle sync probing embedded cues | subtitle_cues=%s | playback=%s' % (
                    len(original_starts), selector.short_text(playback_url),
                )
            )
            reference_candidates = embedded_cue_candidates(playback_url)
            embedded_cues = max_embedded_cues(reference_candidates)
            core.logger.debug(
                'Background subtitle sync probe complete | embedded_tracks=%s | embedded_cues=%s | subtitle_cues=%s' % (
                    len(reference_candidates), embedded_cues, len(original_starts),
                )
            )
            for candidate in reference_candidates:
                if candidate.get('sample_stats'):
                    core.logger.debug(
                        'Background subtitle sync sampling | track=%s | stats=%s' % (
                            candidate.get('track_number'), candidate['sample_stats'],
                        )
                    )
            eligible_candidates = eligible_reference_candidates(reference_candidates)
            if not eligible_candidates or len(original_starts) < FALLBACK_MIN_EXTERNAL_CUES:
                core.logger.debug(
                    'Background subtitle sync retained original: insufficient timing evidence | embedded_cues=%s | subtitle_cues=%s' % (
                        embedded_cues, len(original_starts),
                    )
                )
                return
            result = best_embedded_match(eligible_candidates, original_starts)
            if not fallback_match_is_confirmed(result):
                core.logger.debug(
                    'Background subtitle sync found no strong embedded-English timing match | embedded_tracks=%s | embedded_cues=%s | result=%s | subtitle=%s' % (
                        len(eligible_candidates), embedded_cues, result, subfile,
                    )
                )
                try_timing_validated_fallback(eligible_candidates, original_starts)
                return

            detected_offset_ms = result['offset_ms']
            offset_ms = offset_to_apply(result)
            if not offset_ms:
                core.logger.debug(
                    'Background subtitle sync: subtitle already aligned | detected_offset_ms=%s | zero_offset_matches=%s | subtitle=%s' % (
                        detected_offset_ms, result.get('zero_offset_matches'), subfile,
                    )
                )
                return

            # Do not attach a completed worker result to a later episode.
            if not playback_is_current():
                return

            output_file = autosync_path(subfile, offset_ms)
            with open(output_file, 'w', encoding='utf-8') as handle:
                handle.write(retime_srt(original_text, offset_ms))

            # Recheck after writing, because range probing is asynchronous.
            if not playback_is_current():
                return
            core.kodi.xbmc.Player().setSubtitles(output_file)
            try:
                core.kodi.xbmc.Player().showSubtitles(True)
            except:
                pass
            core.kodi.notification('Subtitle timing corrected: %+d ms' % offset_ms, time=5000)
            core.logger.debug(
                'Background subtitle sync applied | offset_ms=%s | method=%s | votes=%s | matched_cues=%s | track=%s | track_name=%s | sdh=%s | subtitle=%s' % (
                    offset_ms, result.get('method', 'unknown'), result['votes'], result['matched_cues'], result['track_number'], result['track_name'], result['is_sdh'], output_file,
                )
            )
        except Exception as exc:
            core.logger.debug('Background subtitle sync failed: %s' % exc)

    thread = threading.Thread(target=worker, name='a4k-subtitle-sync')
    thread.daemon = True
    thread.start()
