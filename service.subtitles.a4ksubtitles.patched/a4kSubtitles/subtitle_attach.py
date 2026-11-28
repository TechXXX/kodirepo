# -*- coding: utf-8 -*-
"""Pick or attach a subtitle for a video that has none in the preferred language yet.

`attach_runtime_subtitle` runs once per video (the service loop sets
`state.has_done_subs_check`). In order:

1. `update_sub_stream`: switch to a subtitle stream already in the video or
   player in the preferred language. An embedded track always wins. While
   `embedded_track_wait_active` is true (at most 5 seconds after the video
   starts), a sidecar is not accepted and nothing is downloaded, so a late
   embedded track can still win. The wait ends early once Kodi lists the
   video's own tracks, except for TS/M2TS files, which can list tracks late.
2. The Fen Light selector payload (`selector_handoff.forced_subtitle_result`):
   attach its matched Dutch subtitle, or AI-translate its English one
   (full-file) when the payload says `requires_ai_translation`.
3. A runtime search in the preferred languages (`keep_translated=True`, it
   never AI-translates), attaching the first result that downloads.
"""

from a4kSubtitles import selector_handoff as selector
from a4kSubtitles.ai_source_timing import timing_checked_ai_source
from a4kSubtitles.ai_translate import translate_and_attach_subfile
from a4kSubtitles.background_sync import start_background_subtitle_sync
from a4kSubtitles.runtime_languages import (
    language_code,
    normalize_language_list,
    remove_english_search_languages_for_ai,
    subtitle_result_matches_languages,
)


# MPEG-TS style containers have no track header: Kodi finds their tracks while
# reading the stream, so a subtitle track can be listed after the audio.
LATE_TRACK_EXTENSIONS = ('.ts', '.m2ts', '.mts', '.m2t')


def is_external_subtitle(subtitle):
    name = (subtitle.get('name') or '').lower()
    return subtitle.get('isexternal') is True or name.endswith((' (extern)', ' (external)'))


def tracks_can_appear_late(core):
    names = (
        core.kodi.xbmc.getInfoLabel('Player.Filename') or '',
        selector.current_playing_url(core),
        core.kodi.get_property(selector.selector_playback_url_prop) or '',
    )
    for name in names:
        leaf = selector.path_leaf(name).lower()
        if leaf.endswith(LATE_TRACK_EXTENSIONS):
            return leaf
    return ''


def embedded_track_wait_active(ctx, player_props=None):
    """True while waiting longer could still reveal an embedded preferred-language track.

    Kodi reads all tracks of an MKV or MP4 from its header at once, so as soon
    as it lists one of the video's own tracks (an embedded subtitle, or audio
    for a video without subtitles) the list is complete. Before that, and for
    TS/M2TS files, wait until `state.subtitle_stream_settle_until`.
    """
    core, state = ctx.core, ctx.state
    if state.embedded_wait_over or core.time.time() >= state.subtitle_stream_settle_until:
        return False

    late_file = tracks_can_appear_late(core)
    if late_file:
        if state.embedded_wait_logged != 'late':
            state.embedded_wait_logged = 'late'
            core.logger.debug('Embedded-track wait kept: TS/M2TS videos can list their tracks late | file=%s' % late_file)
        return True

    if player_props is None:
        player_props = core.kodi.get_kodi_player_subtitles() or {}
    own_subtitles = [sub for sub in (player_props.get('subtitles') or []) if not is_external_subtitle(sub)]
    try:
        audio_streams = core.kodi.xbmc.Player().getAvailableAudioStreams() or []
    except Exception:
        audio_streams = []
    if not own_subtitles and not audio_streams:
        return True

    state.embedded_wait_over = True
    core.logger.debug(
        "Embedded-track wait ended early: Kodi listed the video's own tracks | waited=%.1fs | embedded_subtitles=%s | audio_tracks=%s" % (
            core.time.time() - state.playback_started_at, len(own_subtitles), len(audio_streams),
        )
    )
    return False


def prepare_runtime_attach_subfile(core, subfile):
    try:
        video_filename = core.kodi.xbmc.getInfoLabel('Player.Filename')
        if not video_filename:
            return subfile

        video_stem = core.os.path.splitext(core.os.path.basename(video_filename))[0]
        sub_basename = core.os.path.basename(subfile)
        sub_root, sub_ext = core.os.path.splitext(sub_basename)

        lang_code = ''
        subtitle_stem = sub_root
        stem_parts = sub_root.rsplit(".", 1)
        if len(stem_parts) == 2 and stem_parts[1].isalpha() and len(stem_parts[1]) <= 3:
            subtitle_stem = stem_parts[0]
            lang_code = stem_parts[1]

        if subtitle_stem.lower() != video_stem.lower():
            return subfile

        humanized_stem = subtitle_stem.replace('.', ' ').replace('_', ' ').replace('-', ' ')
        humanized_stem = ' '.join(humanized_stem.split())
        rewritten_root = 'subtitle %s' % humanized_stem
        if lang_code:
            rewritten_root = '%s.%s' % (rewritten_root, lang_code)

        rewritten_path = core.os.path.join(core.utils.temp_dir, rewritten_root + sub_ext)

        if rewritten_path == subfile:
            return subfile

        try:
            core.os.remove(rewritten_path)
        except:
            pass

        core.os.rename(subfile, rewritten_path)
        core.logger.debug(
            'Rewrote matching-stem runtime subtitle basename | '
            'video=%s | original=%s | rewritten=%s' % (
                video_filename,
                subfile,
                rewritten_path
            )
        )
        return rewritten_path
    except Exception as e:
        core.logger.debug('Runtime subtitle basename rewrite skipped: %s' % e)
        return subfile


def download_and_attach_result(ctx, result, preferredlang, preferredlang_preai, use_ai, ai_provider, ai_api_key, ai_model, full_file_ai=False):
    core, state = ctx.core, ctx.state

    subfile = ctx.api.download(result)
    state.last_subfile = subfile

    if not subfile:
        core.logger.debug('No subtitle file found for %s' % result)
        return False

    if not use_ai or preferredlang == preferredlang_preai:
        subfile = prepare_runtime_attach_subfile(core, subfile)
        state.last_subfile = subfile
        core.logger.debug('Setting subtitles: %s' % subfile)
        core.kodi.xbmc.Player().setSubtitles(subfile)
        state.attached_subtitle_active = True
        start_background_subtitle_sync(ctx, subfile, result)
        return True

    if full_file_ai:
        # Only the full-file path: the chunked path re-reads whichever
        # subtitle file is in temp, so it must not see extra candidates.
        subfile = timing_checked_ai_source(ctx, subfile, result, preferredlang)
        if not subfile:
            # Playback stopped or changed before the timing check: handled, nothing to translate.
            return True
        state.last_subfile = subfile

    return translate_and_attach_subfile(
        ctx,
        subfile,
        preferredlang_preai,
        ai_provider,
        ai_api_key,
        ai_model,
        'downloaded subtitle fallback',
        'downloaded_english_full' if full_file_ai else '',
        full_file_ai,
    )


def update_sub_stream(ctx, preferredlang, prefer_sdh, prefer_forced, force=False, reason=''):
    """Switch to a preferred-language subtitle stream the player already has. True when one is selected."""
    core = ctx.core
    if not force and not core.kodi.get_bool_setting('general', 'auto_select'):
        return
    if preferredlang is None:
        core.logger.debug('no subtitle language found')
        return

    player_props = core.kodi.get_kodi_player_subtitles()
    preferredlang_code = core.utils.get_lang_id(preferredlang, core.kodi.xbmc.ISO_639_2)
    sub_langs = [core.utils.get_lang_id(s, core.kodi.xbmc.ISO_639_2) for s in core.kodi.xbmc.Player().getAvailableSubtitleStreams()]

    preferedlang_sub_indexes = [i for i, s in enumerate(sub_langs) if preferredlang_code == s]
    core.logger.debug('player_props: %s' % player_props)
    core.logger.debug('prefer_sdh: %s' % prefer_sdh)
    core.logger.debug('prefer_forced: %s' % prefer_forced)
    core.logger.debug('preferredlang_code: %s' % preferredlang_code)
    core.logger.debug('sub_langs: %s' % sub_langs)
    core.logger.debug('preferedlang_sub_indexes: %s' % preferedlang_sub_indexes)
    if force:
        core.logger.debug('forced preferred subtitle stream check: %s' % (reason or 'unspecified'))

    if len(preferedlang_sub_indexes) == 0:
        core.logger.debug('no subtitles found for %s' % preferredlang)
        return

    is_external = is_external_subtitle

    preferred_subtitles = [
        sub for sub in player_props.get('subtitles', [])
        if language_code(core, sub.get('language')) == preferredlang_code
    ]
    if (not force and core.kodi.get_bool_setting('general', 'auto_download')
            and preferred_subtitles and all(is_external(sub) for sub in preferred_subtitles)
            and embedded_track_wait_active(ctx, player_props)):
        core.logger.debug('Waiting for an embedded %s subtitle before accepting a sidecar' % preferredlang)
        return

    def find_sub_index():
        if 'subtitles' not in player_props:
            return None

        matching_subtitles = [
            sub for sub in player_props['subtitles']
            if language_code(core, sub.get('language')) == preferredlang_code
        ]
        embedded = [sub for sub in matching_subtitles if not is_external(sub)]
        candidates = embedded or matching_subtitles
        sub_index = None
        for sub in candidates:
            subname = sub['name'].lower()
            if prefer_sdh and (sub['isimpaired'] or 'sdh' in subname or 'captions' in subname or 'honorific' in subname):
                core.logger.debug('found SDH subtitles: %s' % subname)
                sub_index = sub['index']
                break
            if prefer_forced and (sub['isforced'] or 'forced' in subname):
                core.logger.debug('found forced subtitles: %s' % subname)
                sub_index = sub['index']
                break

        if sub_index is None:
            for sub in candidates:
                subname = sub['name'].lower()
                if not sub['isforced'] and all(s not in subname for s in ['forced', 'songs', 'commentary']):
                    core.logger.debug('found default subtitles: %s' % subname)
                    sub_index = sub['index']
                    break

        return sub_index

    sub_index = find_sub_index()
    if sub_index is None and preferredlang_code == 'pob':
        core.logger.debug('no subtitles found for %s, trying por' % preferredlang)
        preferredlang_code = 'por'
        sub_index = find_sub_index()

    if sub_index is None:
        if prefer_sdh:
            core.logger.debug('no SDH subtitles found for %s, fallback to last index from matched langs' % preferredlang)
            sub_index = preferedlang_sub_indexes[-1]
        elif not prefer_forced and len(preferedlang_sub_indexes) > 1:
            core.logger.debug('no subtitles found for %s, fallback to second index from matched langs' % preferredlang)
            sub_index = preferedlang_sub_indexes[1]
        else:
            core.logger.debug('no subtitles found for %s, fallback to first index from matched langs' % preferredlang)
            sub_index = preferedlang_sub_indexes[0]

    if not player_props['currentsubtitle'] or sub_index != player_props['currentsubtitle']['index']:
        core.kodi.xbmc.Player().setSubtitleStream(sub_index)
    if force:
        core.logger.debug(
            'Selected existing preferred subtitle stream before fallback | reason=%s | index=%s | language=%s' % (
                reason or 'unspecified',
                sub_index,
                preferredlang,
            )
        )
    return True


def attach_runtime_subtitle(ctx, use_ai, ai_provider, ai_api_key, ai_model):
    """One pass for the current video: existing stream, selector payload, then runtime search."""
    core, state = ctx.core, ctx.state
    core.logger.debug('Continuing with subtitle download process')
    state.has_done_subs_check = True
    has_subtitles = False

    preferredlang = core.kodi.get_kodi_setting('locale.subtitlelanguage')
    prefer_sdh = core.kodi.get_bool_setting('general', 'prefer_sdh')
    prefer_forced = not prefer_sdh and (core.kodi.get_bool_setting('general', 'prefer_forced') or preferredlang == 'forced_only')
    preferredlang = core.kodi.parse_language(preferredlang)

    try:
        has_subtitles = update_sub_stream(ctx, preferredlang, prefer_sdh, prefer_forced)
    except Exception as e:
        core.logger.debug('Error on update_sub_stream: %s' % e)

    if has_subtitles:
        return

    # Kodi can initially expose a sidecar subtitle before the embedded tracks
    # of a remote video. Give the preferred embedded stream time to appear.
    if (preferredlang and core.kodi.get_bool_setting('general', 'auto_select')
            and core.kodi.get_bool_setting('general', 'auto_download')
            and embedded_track_wait_active(ctx)):
        state.has_done_subs_check = False
        return

    if not core.kodi.get_bool_setting('general', 'auto_download'):
        core.kodi.xbmc.executebuiltin('ActivateWindow(SubtitleSearch)')
        return

    languages = normalize_language_list(core.kodi.get_kodi_setting('subtitles.languages'))
    if preferredlang and preferredlang not in languages:
        languages.append(preferredlang)
    languages = remove_english_search_languages_for_ai(core, languages, preferredlang, use_ai)
    preferredlang_preai = preferredlang

    forced_result, forced_payload = selector.forced_subtitle_result(core)
    if forced_result:
        try:
            forced_requires_ai_translation = selector.payload_requires_ai_translation(forced_payload)
            if forced_requires_ai_translation and not use_ai:
                core.logger.debug(
                    'Skipping selector-matched English subtitle fallback because AI translation is not configured | subtitle=%s' % (
                        selector.matched_subtitle_name(forced_result),
                    )
                )
            elif not forced_requires_ai_translation and not subtitle_result_matches_languages(core, forced_result, languages):
                core.logger.debug(
                    'Skipping selector-matched runtime subtitle outside configured languages | subtitle=%s | languages=%s' % (
                        selector.matched_subtitle_name(forced_result),
                        languages,
                    )
                )
            else:
                if forced_requires_ai_translation:
                    if update_sub_stream(
                        ctx, preferredlang, prefer_sdh, prefer_forced,
                        force=True,
                        reason='selector English AI fallback guard',
                    ):
                        core.logger.debug(
                            'Skipping selector-matched English AI fallback because an existing preferred-language subtitle stream is available'
                        )
                        return
                    forced_download_language = forced_payload.get('ai_translation_source_language') or 'English'
                else:
                    forced_download_language = preferredlang
                core.logger.debug(
                    'Using selector-matched runtime subtitle | source_key=%s | score=%s | reason=%s | subtitle=%s | ai_translate=%s' % (
                        forced_payload.get('source_key', ''),
                        forced_payload.get('match_score'),
                        forced_payload.get('match_reason'),
                        selector.matched_subtitle_name(forced_result),
                        forced_requires_ai_translation,
                    )
                )
                if download_and_attach_result(
                    ctx,
                    forced_result,
                    forced_download_language,
                    preferredlang_preai,
                    forced_requires_ai_translation,
                    ai_provider if forced_requires_ai_translation else '',
                    ai_api_key if forced_requires_ai_translation else '',
                    ai_model if forced_requires_ai_translation else '',
                    forced_requires_ai_translation,
                ):
                    return
        except:
            import traceback
            core.logger.error('Error applying selector-matched subtitle: %s' % traceback.format_exc())

    has_imdb = core.kodi.xbmc.getInfoLabel('VideoPlayer.IMDBNumber')
    attached_subtitle = False

    if has_imdb:
        params = {
            'action': 'search',
            'languages': ','.join(languages),
            'preferredlanguage': preferredlang,
            # This runtime search never AI-translates, so other sites' AI
            # subtitles are still better than leaving the viewer with none;
            # they stay ranked below human-made subtitles.
            'keep_translated': True,
        }

        results = ctx.api.search(params)
        for result in results:
            try:
                if not download_and_attach_result(
                    ctx,
                    result,
                    preferredlang,
                    preferredlang_preai,
                    False,
                    '',
                    '',
                    '',
                ):
                    continue
                attached_subtitle = True
                break
            except:
                import traceback
                core.logger.error('Error downloading or setting subtitles: %s' % traceback.format_exc())
                continue
    else:
        core.logger.debug('No IMDb metadata, skipping runtime subtitle search')

    if attached_subtitle:
        return

    if use_ai:
        core.logger.debug('AI fallback skipped after runtime search: external English subtitle fallback is selected before playback')
