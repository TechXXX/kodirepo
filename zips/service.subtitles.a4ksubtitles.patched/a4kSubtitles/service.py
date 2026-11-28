# -*- coding: utf-8 -*-
"""The long-running Kodi service: poll playback and hand each video to the right module.

See docs/service-structure.md for the module map. This file only holds the
poll loop; per-playback state lives in `service_state.PlaybackState`.
"""

from a4kSubtitles import selector_handoff as selector
from a4kSubtitles.ai_translate import ai_settings, disable_ai_without_api_key, translate_next_chunk
from a4kSubtitles.service_state import ServiceContext
from a4kSubtitles.subtitle_attach import attach_runtime_subtitle

FAST_SELECTOR_POLL_INTERVAL = 0.2
FAST_SELECTOR_POLL_WINDOW = 3.0
SUBTITLE_STREAM_SETTLE_SECONDS = 5.0
DEFAULT_POLL_INTERVAL = 1.0


def start(api):
    core = api.core
    try:
        if core.kodi.migrate_auto_sync_subtitles_default_on():
            core.logger.debug('Enabled background subtitle timing sync for this profile')
    except Exception as exc:
        core.logger.debug('Background subtitle sync default-on migration skipped: %s' % exc)
    core.kodi.xbmcvfs.delete(core.utils.suspend_service_file)
    core.shutil.rmtree(core.utils.temp_dir, ignore_errors=True)
    monitor = core.kodi.xbmc.Monitor()

    ctx = ServiceContext(api, monitor)
    state = ctx.state

    poll_interval = DEFAULT_POLL_INTERVAL
    while not monitor.abortRequested():
        if monitor.waitForAbort(poll_interval):
            break
        poll_interval = DEFAULT_POLL_INTERVAL

        if disable_ai_without_api_key(core):
            state.reset()

        if not core.kodi.get_bool_setting('general', 'auto_search'):
            continue

        use_ai = core.kodi.get_bool_setting('general', 'use_ai')
        if core.kodi.xbmcvfs.exists(core.utils.suspend_service_file):
            if use_ai:
                state.reset()
            continue

        has_video = core.kodi.xbmc.Player().isPlayingVideo()

        if not has_video and (state.has_done_subs_check or state.prev_playing_filename):
            state.reset()

        has_video_duration = core.kodi.xbmc.getCondVisibility('Player.HasDuration')

        # In-case episode changed.
        if has_video:
            playing_filename = core.kodi.xbmc.getInfoLabel('Player.Filenameandpath')
            if state.prev_playing_filename != playing_filename:
                state.reset()
                state.prev_playing_filename = playing_filename
                state.subtitle_stream_settle_until = core.time.time() + SUBTITLE_STREAM_SETTLE_SECONDS
                if core.kodi.get_property(selector.selector_payload_prop):
                    state.fast_selector_poll_until = core.time.time() + FAST_SELECTOR_POLL_WINDOW

        if (
            not state.has_done_subs_check
            and core.kodi.get_property(selector.selector_payload_prop)
            and core.time.time() < state.fast_selector_poll_until
        ):
            poll_interval = FAST_SELECTOR_POLL_INTERVAL

        if not has_video or not has_video_duration or state.has_done_subs_check:
            if use_ai:
                keep_current_attached_subtitle = has_video and state.has_done_subs_check and state.attached_subtitle_active
                if not keep_current_attached_subtitle:
                    core.kodi.xbmcvfs.delete(core.utils.suspend_service_file)
                    core.shutil.rmtree(core.utils.temp_dir, ignore_errors=True)
            continue

        use_ai, ai_provider, ai_api_key, ai_model = ai_settings(core, use_ai)

        subfile = core.utils.get_subfile_from_temp_dir()

        if not subfile and core.kodi.xbmcvfs.exists(core.utils.suspend_service_file):
            core.logger.debug('Service suspended, skipping subtitle check')
            state.ai_last_timestamp = None
            state.ai_tries = 0
            continue

        if not subfile:
            subfile = core.utils.get_subfile_from_temp_dir()

        if state.last_subfile and subfile != state.last_subfile:
            state.ai_last_timestamp = None
            state.ai_tries = 0

        core.logger.debug('use_ai_translation: %s, ai_translation_active: %s, subfile: %s' % (use_ai, state.ai_translation_active, subfile))
        if use_ai and state.ai_translation_active and subfile:
            if not translate_next_chunk(ctx, subfile, ai_provider, ai_api_key, ai_model):
                core.logger.debug('AI translation failed, marking subtitles check as done')
                state.has_done_subs_check = True

            core.logger.debug('Skipping subtitle download due to AI translation')
            continue

        attach_runtime_subtitle(ctx, use_ai, ai_provider, ai_api_key, ai_model)
