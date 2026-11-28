# -*- coding: utf-8 -*-
"""AI subtitle translation for the playback service.

Two modes, both through the bundled `gptsubtrans` translator:

- Full file (`translate_and_attach_subfile(..., full_file=True)`): used for the
  English subtitle Fen Light's selector hands over when no Dutch subtitle
  exists. Translates the whole file in batches, starting near the playhead,
  attaches a live partial file while it runs, and stops before the next batch
  once playback stops or another video plays (`translation_stop_reason`).
- Chunked (`translate_next_chunk`): the older mode that translates 60 seconds
  around the playhead each poll while `state.ai_translation_active` is true.

The OpenAI model is pinned to `OPENAI_TRANSLATION_MODEL`; see README for the
other two places that must agree.
"""

from a4kSubtitles.runtime_languages import language_code

OPENAI_TRANSLATION_MODEL = 'gpt-6-luna'

# Chunked mode: seconds translated per chunk, and how far playback must move
# past the previous chunk start before the next chunk is translated.
AI_CHUNK_SECONDS = 60
AI_CHUNK_STEP_SECONDS = AI_CHUNK_SECONDS / 2


def pinned_ai_model(core, ai_provider, configured_model):
    if ai_provider != 'OpenAI':
        return configured_model

    configured_model = (configured_model or '').strip()
    if configured_model != OPENAI_TRANSLATION_MODEL:
        core.logger.debug(
            'Forcing OpenAI subtitle translation model to %s (configured=%s)' % (
                OPENAI_TRANSLATION_MODEL,
                configured_model or '<empty>',
            )
        )
        try:
            core.kodi.set_setting('general', 'ai_model', OPENAI_TRANSLATION_MODEL)
        except Exception as exc:
            core.logger.debug('Unable to persist pinned OpenAI subtitle translation model: %s' % exc)

    return OPENAI_TRANSLATION_MODEL


def ai_api_key_configured(core):
    api_key = (core.kodi.get_setting('general', 'ai_api_key') or '').strip()
    return bool(api_key and api_key != 'empty_setting')


def disable_ai_without_api_key(core):
    if not core.kodi.get_bool_setting('general', 'use_ai'):
        return False

    if ai_api_key_configured(core):
        return False

    core.logger.debug('Disabling AI subtitle translation because no API key is configured')
    try:
        core.kodi.set_setting('general', 'use_ai', 'false')
    except Exception as exc:
        core.logger.debug('Unable to persist disabled AI subtitle translation setting: %s' % exc)
    return True


def ai_settings(core, use_ai):
    """Return (use_ai, provider, api_key, model); use_ai turns False when the settings cannot translate."""
    if not use_ai:
        return False, '', '', ''

    ai_provider = core.kodi.get_setting('general', 'ai_provider')
    if ai_provider is None or ai_provider == '':
        ai_provider = '0'

    if ai_provider == '0':
        ai_provider = 'OpenAI'
    else:
        ai_provider = 'NexosAI'

    if ai_provider not in ['OpenAI', 'NexosAI']:
        core.logger.error('Invalid AI provider: %s' % ai_provider)
        use_ai = False

    ai_api_key = (core.kodi.get_setting('general', 'ai_api_key') or '').strip()
    ai_model = pinned_ai_model(core, ai_provider, core.kodi.get_setting('general', 'ai_model'))
    if ai_api_key == 'empty_setting' or not ai_api_key or (ai_provider != 'OpenAI' and (ai_model is None or ai_model == '')):
        use_ai = False
    return use_ai, ai_provider, ai_api_key, ai_model


def ai_translated_subfile_path(core, subfile, target_language, live=False):
    folder = core.os.path.dirname(subfile)
    basename = core.os.path.basename(subfile)
    root, ext = core.os.path.splitext(basename)
    root_parts = root.rsplit('.', 1)
    if len(root_parts) == 2 and root_parts[1].isalpha() and len(root_parts[1]) <= 3:
        root = root_parts[0]
    suffix = 'translated.live.%s.srt' if live else 'translated.%s.srt'
    return core.os.path.join(folder, '%s.%s' % (root, suffix % target_language))


def subtitle_file_looks_usable(core, path):
    try:
        if not path or not core.os.path.exists(path) or core.os.path.getsize(path) <= 0:
            return False
        with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
            return '-->' in handle.read(4096)
    except:
        return False


def translate_and_attach_subfile(ctx, subfile, target_preferredlang, ai_provider, ai_api_key, ai_model, reason, source='', full_file=False):
    core, monitor, state = ctx.core, ctx.monitor, ctx.state

    translator = getattr(core.utils, 'gptsubtrans', None)
    if not translator:
        core.logger.error('AI translation fallback unavailable: bundled gptsubtrans could not be imported')
        return False

    ai_model = pinned_ai_model(core, ai_provider, ai_model)
    target_language = language_code(core, target_preferredlang)
    if not target_language:
        core.logger.debug('AI translation fallback skipped: no target subtitle language')
        return False

    core.logger.debug('Using AI to translate %s: %s' % (reason, subfile))
    subfile_translated = ai_translated_subfile_path(core, subfile, target_language)

    moviename = '%s (%s)' % (core.last_meta.title, core.last_meta.year) if core.last_meta else ''

    core.logger.debug('Translating subtitles with AI provider: %s, model: %s' % (ai_provider, ai_model))
    core.logger.debug('Moviename: %s, target_language: %s' % (moviename, target_language))

    state.ai_last_timestamp = core.kodi.xbmc.Player().getTime()
    begin_seconds = None if full_file else state.ai_last_timestamp
    end_seconds = None if full_file else state.ai_last_timestamp + AI_CHUNK_SECONDS
    if full_file:
        core.logger.debug('Translating complete subtitle file with AI')

    partial_attach_window_seconds = 120.0
    live_partial_file = ai_translated_subfile_path(core, subfile, target_language, True)
    live_partial_state = {'attached_batch': 0, 'attached_coverage_seconds': 0.0, 'attached_playhead_seconds': None, 'attached_file': ''}

    def current_playback_position():
        try:
            player = core.kodi.xbmc.Player()
            return player.getTime() if player.isPlaying() else None
        except Exception:
            return None

    try:
        translation_started_file = core.kodi.xbmc.getInfoLabel('Player.Filenameandpath') or ''
    except Exception:
        translation_started_file = ''
    stop_state = {'seen_playing': bool(translation_started_file)}

    def translation_stop_reason():
        """Checked before each AI batch: a reason to stop, or None to keep translating."""
        if monitor.abortRequested():
            return 'Kodi is shutting down'
        try:
            player = core.kodi.xbmc.Player()
            if player.isPlayingVideo():
                stop_state['seen_playing'] = True
                playing_file = core.kodi.xbmc.getInfoLabel('Player.Filenameandpath') or ''
                if translation_started_file and playing_file and playing_file != translation_started_file:
                    return 'a different video is playing'
                return None
            if not stop_state['seen_playing']:
                return None
            # Give Kodi a few seconds in case the stream is only reopening.
            for _ in range(5):
                if monitor.waitForAbort(1):
                    return 'Kodi is shutting down'
                if player.isPlayingVideo():
                    return None
            return 'playback stopped'
        except Exception:
            return None
    notification_state = {'shown': False}

    def notify_ai_translated_subtitle_selected():
        if notification_state['shown']:
            return
        notification_state['shown'] = True
        core.kodi.notification(core.kodi.gpt_translated_notification_text(ai_model), time=4000)

    def cleanup_live_partial_files(keep_file=''):
        try:
            temp_dir = core.os.path.dirname(subfile_translated)
            translated_basename = core.os.path.basename(subfile_translated)
            live_basename = core.os.path.basename(live_partial_file)
            legacy_basename = core.os.path.basename(subfile + '.translated')
            for filename in core.os.listdir(temp_dir):
                if filename == live_basename or (
                    filename.startswith(legacy_basename + '.live')
                    and filename.endswith('.srt')
                ) or (
                    filename.startswith(translated_basename + '.live.')
                    and filename.endswith('.srt')
                ):
                    path = core.os.path.join(temp_dir, filename)
                    if keep_file and path == keep_file:
                        continue
                    try:
                        core.os.remove(path)
                    except:
                        pass
        except Exception as exc:
            core.logger.debug('Partial AI subtitle cleanup skipped: %s' % exc)

    if full_file:
        cleanup_live_partial_files()

    def attach_partial_translation(output_file, batch_number, total_batches, coverage_seconds=None):
        if not full_file:
            return
        try:
            coverage_seconds = float(coverage_seconds or 0.0)
        except:
            coverage_seconds = 0.0
        playhead = current_playback_position()
        if batch_number < total_batches and live_partial_state['attached_batch'] > 0:
            near_playhead = (
                playhead is not None
                and playhead - 30.0 <= coverage_seconds <= playhead + 300.0
            )
            moved_to_new_area = (
                playhead is not None
                and live_partial_state['attached_playhead_seconds'] is not None
                and abs(playhead - live_partial_state['attached_playhead_seconds']) >= 60.0
            )
            coverage_changed = (
                abs(coverage_seconds - live_partial_state['attached_coverage_seconds'])
                >= partial_attach_window_seconds
            )
            if not (moved_to_new_area or (near_playhead and coverage_changed)):
                return
        if not subtitle_file_looks_usable(core, output_file):
            return

        try:
            try:
                core.os.remove(live_partial_file)
            except:
                pass
            core.shutil.copyfile(output_file, live_partial_file)
            core.kodi.xbmc.Player().setSubtitles(live_partial_file)
            try:
                core.kodi.xbmc.Player().showSubtitles(True)
            except:
                pass
            notify_ai_translated_subtitle_selected()
            live_partial_state['attached_batch'] = batch_number
            live_partial_state['attached_coverage_seconds'] = coverage_seconds
            live_partial_state['attached_playhead_seconds'] = playhead
            live_partial_state['attached_file'] = live_partial_file
            core.logger.debug(
                'Refreshed live AI subtitle translation: batch=%s/%s coverage=%.1fs file=%s' % (
                    batch_number,
                    total_batches,
                    coverage_seconds,
                    live_partial_file,
                )
            )
        except Exception as exc:
            core.logger.debug('Partial AI subtitle attach skipped: %s' % exc)

    stop_reason = translator.translate(
        input_file=subfile,
        target_language=target_language,
        output_file=subfile_translated,
        moviename=moviename,
        provider=ai_provider,
        api_key=ai_api_key,
        model=ai_model,
        begin_seconds=begin_seconds,
        end_seconds=end_seconds,
        priority_seconds=state.ai_last_timestamp if full_file else None,
        log=core.logger.debug,
        partial_callback=attach_partial_translation if full_file else None,
        playback_position=current_playback_position if full_file else None,
        should_stop=translation_stop_reason,
    )

    if stop_reason:
        # Nobody is watching this video any more: do not attach, and hand the
        # service loop back so it can reset or handle the next video.
        core.logger.debug('AI subtitle translation stopped early: %s' % stop_reason)
        if full_file:
            cleanup_live_partial_files()
        return True

    state.last_subfile = subfile
    subtitle_to_attach = subfile_translated
    if full_file and live_partial_state['attached_file']:
        try:
            core.shutil.copyfile(subfile_translated, live_partial_state['attached_file'])
            subtitle_to_attach = live_partial_state['attached_file']
            core.logger.debug(
                'Refreshed partial AI subtitle stream with final translation: file=%s' % subtitle_to_attach
            )
        except Exception as exc:
            core.logger.debug('Final AI subtitle live-file refresh skipped: %s' % exc)

    core.kodi.xbmc.Player().setSubtitles(subtitle_to_attach)
    try:
        core.kodi.xbmc.Player().showSubtitles(True)
    except:
        pass
    notify_ai_translated_subtitle_selected()
    if full_file:
        cleanup_live_partial_files(keep_file=subtitle_to_attach)
    state.ai_tries = 0
    state.has_done_subs_check = bool(full_file)
    state.ai_translation_active = not full_file
    state.ai_translation_source = source
    state.attached_subtitle_active = True
    return True


def translate_next_chunk(ctx, subfile, ai_provider, ai_api_key, ai_model):
    """Chunked mode: translate the next 60 seconds around the playhead. False means give up on this video."""
    core, state = ctx.core, ctx.state

    timestamp = core.kodi.xbmc.Player().getTime()
    previous_ai_last_timestamp = state.ai_last_timestamp

    try:
        active_subfile = subfile
        translation_range = AI_CHUNK_SECONDS

        moviename = '%s (%s)' % (core.last_meta.title, core.last_meta.year) if core.last_meta else ''
        target_language = language_code(core, core.kodi.parse_language(core.kodi.get_kodi_setting('locale.subtitlelanguage')))
        if not target_language:
            core.logger.debug('AI translation skipped: no target subtitle language')
            return False

        subfile_translated = ai_translated_subfile_path(core, active_subfile, target_language)

        if previous_ai_last_timestamp is not None and previous_ai_last_timestamp + AI_CHUNK_STEP_SECONDS > timestamp and timestamp > previous_ai_last_timestamp and core.kodi.xbmcvfs.exists(subfile_translated):
            core.logger.debug('Skipping AI translation, already translated')
            return True

        state.ai_last_timestamp = timestamp
        core.logger.debug('Subtitles file: %s' % active_subfile)
        core.logger.debug('Using AI to translate portion of subtitles between %s and %s seconds in %s' % (state.ai_last_timestamp, state.ai_last_timestamp + translation_range, target_language))

        translator = getattr(core.utils, 'gptsubtrans', None)
        if not translator:
            core.logger.error('AI translation unavailable: bundled gptsubtrans could not be imported')
            return False

        translator.translate(
            input_file=active_subfile,
            target_language=target_language,
            output_file=subfile_translated,
            moviename=moviename,
            provider=ai_provider,
            api_key=ai_api_key,
            model=ai_model,
            begin_seconds=state.ai_last_timestamp,
            end_seconds=state.ai_last_timestamp + translation_range,
            log=core.logger.debug
        )

        state.last_subfile = active_subfile
        core.logger.debug('Translated subtitles file: %s' % subfile_translated)
        core.kodi.xbmc.Player().setSubtitles(subfile_translated)
        state.ai_tries = 0
        return True
    except:
        import traceback
        if 'No scenes to translate' in traceback.format_exc():
            return True

        state.ai_tries += 1
        core.logger.error('Error translating subtitles with AI')
        return state.ai_tries < 3
