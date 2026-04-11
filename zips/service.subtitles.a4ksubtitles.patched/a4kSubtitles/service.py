# -*- coding: utf-8 -*-

selector_source_key_prop = 'subs.selector_source_key'
selector_payload_prop = 'subs.selector_payload'

def _selector_matched_subtitle_name(result):
    if not isinstance(result, dict):
        return ''

    action_args = result.get('action_args') or {}
    return result.get('name') or action_args.get('filename') or result.get('filename') or ''

def _selector_forced_subtitle_result(core):
    payload_text = core.kodi.get_property(selector_payload_prop)
    if not payload_text:
        return (None, None)

    current_source_key = core.kodi.get_property(selector_source_key_prop)
    if not current_source_key:
        return (None, None)

    try:
        payload = core.json.loads(payload_text)
    except Exception as exc:
        core.logger.debug('selector subtitle payload parse failed: %s' % exc)
        return (None, None)

    payload_source_key = payload.get('source_key', '')
    if payload_source_key and payload_source_key != current_source_key:
        core.logger.debug(
            'selector subtitle payload ignored for stale source key | payload=%s | current=%s' % (
                payload_source_key,
                current_source_key,
            )
        )
        return (None, payload)

    matched_subtitle = payload.get('matched_subtitle')
    if not isinstance(matched_subtitle, dict):
        return (None, payload)

    if not matched_subtitle.get('service_name') or not isinstance(matched_subtitle.get('action_args'), dict):
        core.logger.debug('selector subtitle payload missing service/action_args')
        return (None, payload)

    return (matched_subtitle, payload)

def start(api):
    core = api.core
    core.kodi.xbmcvfs.delete(core.utils.suspend_service_file)
    core.shutil.rmtree(core.utils.temp_dir, ignore_errors=True)
    monitor = core.kodi.xbmc.Monitor()

    has_done_subs_check = False
    prev_playing_filename = ''
    fast_selector_poll_until = 0.0

    ai_max_range = 60
    ai_step = ai_max_range / 2
    fast_selector_poll_interval = 0.2
    fast_selector_poll_window = 3.0
    default_poll_interval = 1.0

    last_subfile = None
    subfile_translated = None
    ai_last_timestamp = None
    ai_tries = 0

    def reset():
        nonlocal has_done_subs_check, prev_playing_filename, ai_last_timestamp, ai_tries
        nonlocal fast_selector_poll_until

        has_done_subs_check = False
        prev_playing_filename = ''
        ai_last_timestamp = None
        ai_tries = 0
        fast_selector_poll_until = 0.0

    def prepare_runtime_attach_subfile(subfile):
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

    def download_and_attach_result(result, preferredlang, preferredlang_preai, use_ai, ai_provider, ai_api_key, ai_model):
        nonlocal last_subfile, ai_last_timestamp, ai_tries, has_done_subs_check

        subfile = api.download(result)
        last_subfile = subfile

        if not subfile:
            core.logger.debug('No subtitle file found for %s' % result)
            return False

        if not use_ai or preferredlang == preferredlang_preai:
            subfile = prepare_runtime_attach_subfile(subfile)
            last_subfile = subfile
            core.logger.debug('Setting subtitles: %s' % subfile)
            core.kodi.xbmc.Player().setSubtitles(subfile)
            return True

        core.logger.debug('Using AI to translate subtitles: %s' % subfile)
        subfile_translated = subfile + '.translated'

        moviename = '%s (%s)' % (core.last_meta.title, core.last_meta.year) if core.last_meta else ''
        target_language = core.utils.get_lang_id(preferredlang_preai, core.kodi.xbmc.ISO_639_2)

        core.logger.debug('Translating subtitles with AI provider: %s, model: %s' % (ai_provider, ai_model))
        core.logger.debug('Moviename: %s, target_language: %s' % (moviename, target_language))

        ai_last_timestamp = core.kodi.xbmc.Player().getTime()

        core.utils.gptsubtrans.translate(
            input_file=subfile,
            target_language=target_language,
            output_file=subfile_translated,
            moviename=moviename,
            provider=ai_provider,
            api_key=ai_api_key,
            model=ai_model,
            begin_seconds=ai_last_timestamp,
            end_seconds=ai_last_timestamp + ai_max_range,
            log=core.logger.debug
        )

        core.kodi.xbmc.Player().setSubtitles(subfile_translated)
        ai_tries = 0
        has_done_subs_check = False
        return True

    poll_interval = default_poll_interval
    while not monitor.abortRequested():
        if monitor.waitForAbort(poll_interval):
            break
        poll_interval = default_poll_interval

        if not core.kodi.get_bool_setting('general', 'auto_search'):
            continue

        use_ai = core.kodi.get_bool_setting('general', 'use_ai')
        if core.kodi.xbmcvfs.exists(core.utils.suspend_service_file):
            if use_ai:
                reset()
            continue

        has_video = core.kodi.xbmc.Player().isPlayingVideo()

        if not has_video and has_done_subs_check:
            reset()

        has_video_duration = core.kodi.xbmc.getCondVisibility('Player.HasDuration')

        # In-case episode changed.
        if has_video:
            playing_filename = core.kodi.xbmc.getInfoLabel('Player.Filenameandpath')
            if prev_playing_filename != playing_filename:
                reset()
                prev_playing_filename = playing_filename
                if core.kodi.get_property(selector_payload_prop):
                    fast_selector_poll_until = core.time.time() + fast_selector_poll_window

        if (
            not has_done_subs_check
            and core.kodi.get_property(selector_payload_prop)
            and core.time.time() < fast_selector_poll_until
        ):
            poll_interval = fast_selector_poll_interval

        if not has_video or not has_video_duration or has_done_subs_check:
            if use_ai:
                core.kodi.xbmcvfs.delete(core.utils.suspend_service_file)
                core.shutil.rmtree(core.utils.temp_dir, ignore_errors=True)
            continue

        if use_ai:
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

            ai_api_key = core.kodi.get_setting('general', 'ai_api_key')
            ai_model = core.kodi.get_setting('general', 'ai_model')
            if ai_api_key is None or ai_api_key == '' or ai_model is None or ai_model == '':
                use_ai = False

        subfile = core.utils.get_subfile_from_temp_dir()

        if not subfile and core.kodi.xbmcvfs.exists(core.utils.suspend_service_file):
            core.logger.debug('Service suspended, skipping subtitle check')
            ai_last_timestamp = None
            ai_tries = 0
            continue

        if not subfile:
            subfile = core.utils.get_subfile_from_temp_dir()

        if last_subfile and subfile != last_subfile:
            ai_last_timestamp = None
            ai_tries = 0

        core.logger.debug('use_ai: %s, subfile: %s' % (use_ai, subfile))
        if use_ai and subfile:
            def translate_subtitles():
                nonlocal ai_last_timestamp, ai_tries, last_subfile

                timestamp = core.kodi.xbmc.Player().getTime()
                subfile_translated = subfile + '.translated'

                if ai_last_timestamp is not None and ai_last_timestamp + ai_step > timestamp and timestamp > ai_last_timestamp and core.kodi.xbmcvfs.exists(subfile_translated):
                    core.logger.debug('Skipping AI translation, already translated')
                    return True

                try:
                    ai_last_timestamp = timestamp
                    moviename = '%s (%s)' % (core.last_meta.title, core.last_meta.year) if core.last_meta else ''
                    target_language = core.utils.get_lang_id(core.kodi.get_kodi_setting('locale.subtitlelanguage'), core.kodi.xbmc.ISO_639_2)

                    core.logger.debug('Subtitles file: %s' % subfile)
                    core.logger.debug('Using AI to translate portion of subtitles between %s and %s seconds in %s' % (ai_last_timestamp, ai_last_timestamp + ai_max_range, target_language))

                    core.utils.gptsubtrans.translate(
                        input_file=subfile,
                        target_language=target_language,
                        output_file=subfile_translated,
                        moviename=moviename,
                        provider=ai_provider,
                        api_key=ai_api_key,
                        model=ai_model,
                        begin_seconds=ai_last_timestamp,
                        end_seconds=ai_last_timestamp + ai_max_range,
                        log=core.logger.debug
                    )

                    last_subfile = subfile
                    core.logger.debug('Translated subtitles file: %s' % subfile_translated)
                    core.kodi.xbmc.Player().setSubtitles(subfile_translated)
                    ai_tries = 0
                    return True
                except:
                    import traceback
                    if 'No scenes to translate' in traceback.format_exc():
                        return True

                    ai_tries += 1
                    core.logger.error('Error translating subtitles with AI')
                    return ai_tries < 3

            if not translate_subtitles():
                core.logger.debug('AI translation failed, marking subtitles check as done')
                has_done_subs_check = True

            core.logger.debug('Skipping subtitle download due to AI translation')
            continue

        core.logger.debug('Continuing with subtitle download process')
        has_done_subs_check = True
        has_subtitles = False

        preferredlang = core.kodi.get_kodi_setting('locale.subtitlelanguage')
        prefer_sdh = core.kodi.get_bool_setting('general', 'prefer_sdh')
        prefer_forced = not prefer_sdh and (core.kodi.get_bool_setting('general', 'prefer_forced') or preferredlang == 'forced_only')
        preferredlang = core.kodi.parse_language(preferredlang)

        try:
            def update_sub_stream():
                if not core.kodi.get_bool_setting('general', 'auto_select'):
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

                if len(preferedlang_sub_indexes) == 0:
                    core.logger.debug('no subtitles found for %s' % preferredlang)
                    return

                def find_sub_index():
                    if 'subtitles' not in player_props:
                        return None

                    sub_index = None
                    for sub in player_props['subtitles']:
                        subname = sub['name'].lower()
                        if sub['language'] != preferredlang_code:
                            continue
                        if prefer_sdh and (sub['isimpaired'] or 'sdh' in subname or 'captions' in subname or 'honorific' in subname):
                            core.logger.debug('found SDH subtitles: %s' % subname)
                            sub_index = sub['index']
                            break
                        if prefer_forced and (sub['isforced'] or 'forced' in subname):
                            core.logger.debug('found forced subtitles: %s' % subname)
                            sub_index = sub['index']
                            break

                    if sub_index is None:
                        for sub in player_props['subtitles']:
                            subname = sub['name'].lower()
                            if sub['language'] != preferredlang_code:
                                continue
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
                return True

            if not use_ai:
                has_subtitles = update_sub_stream()
        except Exception as e:
            core.logger.debug('Error on update_sub_stream: %s' % e)

        if has_subtitles:
            continue

        if not core.kodi.get_bool_setting('general', 'auto_download'):
            core.kodi.xbmc.executebuiltin('ActivateWindow(SubtitleSearch)')
            continue

        languages = core.kodi.get_kodi_setting('subtitles.languages')
        preferredlang_preai = preferredlang

        if use_ai:
            languages = ['English']
            preferredlang = 'English'

        forced_result, forced_payload = _selector_forced_subtitle_result(core)
        if forced_result:
            try:
                core.logger.debug(
                    'Using selector-matched runtime subtitle | source_key=%s | score=%s | reason=%s | subtitle=%s' % (
                        forced_payload.get('source_key', ''),
                        forced_payload.get('match_score'),
                        forced_payload.get('match_reason'),
                        _selector_matched_subtitle_name(forced_result),
                    )
                )
                if download_and_attach_result(
                    forced_result,
                    preferredlang,
                    preferredlang_preai,
                    use_ai,
                    ai_provider if use_ai else '',
                    ai_api_key if use_ai else '',
                    ai_model if use_ai else '',
                ):
                    continue
            except:
                import traceback
                core.logger.error('Error applying selector-matched subtitle: %s' % traceback.format_exc())

        has_imdb = core.kodi.xbmc.getInfoLabel('VideoPlayer.IMDBNumber')
        if not has_imdb:
            continue

        params = {
            'action': 'search',
            'languages': ','.join(languages),
            'preferredlanguage': preferredlang
        }

        results = api.search(params)
        for result in results:
            try:
                if not download_and_attach_result(
                    result,
                    preferredlang,
                    preferredlang_preai,
                    use_ai,
                    ai_provider if use_ai else '',
                    ai_api_key if use_ai else '',
                    ai_model if use_ai else '',
                ):
                    continue
                break
            except:
                import traceback
                core.logger.error('Error downloading or setting subtitles: %s' % traceback.format_exc())
                continue
