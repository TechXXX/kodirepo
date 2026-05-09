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

def _selector_payload_requires_ai_translation(payload):
    if not isinstance(payload, dict):
        return False
    return bool(payload.get('requires_ai_translation'))

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
    ai_translation_active = False
    ai_translation_source = ''
    attached_subtitle_active = False

    def reset():
        nonlocal has_done_subs_check, prev_playing_filename, ai_last_timestamp, ai_tries
        nonlocal fast_selector_poll_until, ai_translation_active, ai_translation_source
        nonlocal attached_subtitle_active

        has_done_subs_check = False
        prev_playing_filename = ''
        ai_last_timestamp = None
        ai_tries = 0
        fast_selector_poll_until = 0.0
        ai_translation_active = False
        ai_translation_source = ''
        attached_subtitle_active = False

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

    def normalize_language_list(value):
        if isinstance(value, str):
            values = value.split(',') if ',' in value else [value]
        else:
            values = list(value or [])
        return [str(item).strip() for item in values if item not in (None, '', 'none')]

    def language_code(value):
        if value in (None, '', 'none'):
            return ''
        value = str(value).strip()
        if not value:
            return ''
        return core.utils.get_lang_id(value, core.kodi.xbmc.ISO_639_2) or value.lower()

    def subtitle_result_matches_languages(result, languages):
        action_args = result.get('action_args') or {}
        allowed_codes = {language_code(value) for value in languages}
        result_codes = {
            language_code(value)
            for value in (
                result.get('lang'),
                result.get('lang_code'),
                action_args.get('lang'),
                action_args.get('language'),
            )
        }
        allowed_codes.discard('')
        result_codes.discard('')
        return not allowed_codes or not result_codes or bool(allowed_codes & result_codes)

    def remove_english_search_languages_for_ai(languages, preferredlang):
        if not use_ai or language_code(preferredlang) == 'eng':
            return languages
        filtered = [language for language in languages if language_code(language) != 'eng']
        if len(filtered) != len(languages):
            core.logger.debug('Removed English search language while AI translation is enabled')
        return filtered or ([preferredlang] if preferredlang else filtered)

    def player_subtitle_for_language(language):
        player_props = core.kodi.get_kodi_player_subtitles() or {}
        subtitles = player_props.get('subtitles') or []
        target_code = language_code(language)
        candidates = [sub for sub in subtitles if language_code(sub.get('language')) == target_code]
        if not candidates:
            return None

        for sub in candidates:
            subname = str(sub.get('name') or '').lower()
            if not sub.get('isforced') and all(token not in subname for token in ['forced', 'songs', 'commentary']):
                return sub
        return candidates[0]

    def find_binary(name):
        try:
            found = core.shutil.which(name)
            if found:
                return found
        except:
            pass

        for folder in ('/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin'):
            candidate = core.os.path.join(folder, name)
            try:
                if core.os.path.exists(candidate) and core.os.access(candidate, core.os.X_OK):
                    return candidate
            except:
                pass
        return None

    def run_subprocess(args, timeout):
        import subprocess
        return subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )

    def subtitle_file_looks_usable(path):
        try:
            if not path or not core.os.path.exists(path) or core.os.path.getsize(path) <= 0:
                return False
            with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
                return '-->' in handle.read(4096)
        except:
            return False

    def ai_translated_subfile_path(subfile, target_language, live=False):
        folder = core.os.path.dirname(subfile)
        basename = core.os.path.basename(subfile)
        root, ext = core.os.path.splitext(basename)
        root_parts = root.rsplit('.', 1)
        if len(root_parts) == 2 and root_parts[1].isalpha() and len(root_parts[1]) <= 3:
            root = root_parts[0]
        suffix = 'translated.live.%s.srt' if live else 'translated.%s.srt'
        return core.os.path.join(folder, '%s.%s' % (root, suffix % target_language))

    def current_playing_url():
        return (
            core.kodi.xbmc.getInfoLabel('Player.FilenameAndPath')
            or core.kodi.xbmc.getInfoLabel('Player.Filenameandpath')
            or core.kodi.xbmc.Player().getPlayingFile()
            or ''
        )

    def stream_language_code(stream):
        tags = stream.get('tags') or {}
        return language_code(tags.get('language') or tags.get('LANGUAGE') or tags.get('title') or tags.get('TITLE'))

    def format_srt_timestamp(seconds):
        try:
            milliseconds = int(round(float(seconds) * 1000))
        except:
            milliseconds = 0
        milliseconds = max(milliseconds, 0)
        hours = milliseconds // 3600000
        milliseconds = milliseconds % 3600000
        minutes = milliseconds // 60000
        milliseconds = milliseconds % 60000
        seconds = milliseconds // 1000
        milliseconds = milliseconds % 1000
        return '%02d:%02d:%02d,%03d' % (hours, minutes, seconds, milliseconds)

    def decode_ffprobe_packet_data(data):
        byte_values = []
        hex_digits = set('0123456789abcdefABCDEF')
        for line in str(data or '').splitlines():
            if ':' not in line:
                continue
            hex_column = line.split(':', 1)[1].split('  ', 1)[0]
            for group in hex_column.split():
                if len(group) % 2 != 0:
                    continue
                if not all(char in hex_digits for char in group):
                    continue
                for index in range(0, len(group), 2):
                    try:
                        byte_values.append(int(group[index:index + 2], 16))
                    except:
                        pass
        if not byte_values:
            return ''
        return bytes(byte_values).decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n').strip()

    def write_srt_from_ffprobe_packets(packets, output_file):
        cue_number = 0
        with open(output_file, 'w', encoding='utf-8') as handle:
            for packet in packets:
                text = decode_ffprobe_packet_data(packet.get('data'))
                if not text:
                    continue
                try:
                    start_seconds = float(packet.get('pts_time'))
                except:
                    continue
                try:
                    duration_seconds = float(packet.get('duration_time'))
                except:
                    duration_seconds = 2.0
                end_seconds = start_seconds + max(duration_seconds, 0.1)
                cue_number += 1
                handle.write('%s\n%s --> %s\n%s\n\n' % (
                    cue_number,
                    format_srt_timestamp(start_seconds),
                    format_srt_timestamp(end_seconds),
                    text,
                ))
        return cue_number

    def extract_embedded_subfile_with_ffprobe_packets(ffprobe, input_url, stream_index, output_file):
        try:
            core.logger.debug(
                'Extracting complete embedded English subtitle with ffprobe packets: stream=%s output=%s' % (
                    stream_index,
                    output_file,
                )
            )
            probe_packets = run_subprocess(
                [
                    ffprobe,
                    '-v', 'error',
                    '-select_streams', str(stream_index),
                    '-show_packets',
                    '-show_data',
                    '-show_entries', 'packet=pts_time,duration_time,data',
                    '-of', 'json',
                    input_url,
                ],
                600,
            )
            if probe_packets.returncode != 0:
                core.logger.debug('AI translation fallback ffprobe packet extraction failed: %s' % (probe_packets.stderr or '').strip())
                return False
            packets = (core.json.loads(probe_packets.stdout or '{}').get('packets') or [])
            cue_count = write_srt_from_ffprobe_packets(packets, output_file)
            if cue_count <= 0 or not subtitle_file_looks_usable(output_file):
                core.logger.debug('AI translation fallback ffprobe packet extraction produced no usable subtitle file')
                return False
            core.logger.debug('Extracted complete embedded English subtitle with ffprobe packets: %s cues=%s' % (output_file, cue_count))
            return True
        except Exception as exc:
            try:
                core.os.remove(output_file)
            except:
                pass
            core.logger.debug('AI translation fallback ffprobe packet extraction exception: %s' % exc)
            return False

    def extract_embedded_subfile_with_ffmpeg(ffmpeg, input_url, stream_index, output_file):
        try:
            core.logger.debug('Extracting complete embedded English subtitle with ffmpeg: stream=%s output=%s' % (stream_index, output_file))
            extract = run_subprocess(
                [
                    ffmpeg,
                    '-y',
                    '-nostdin',
                    '-loglevel', 'error',
                    '-i', input_url,
                    '-map', '0:%s' % stream_index,
                    '-map_chapters', '-1',
                    '-map_metadata', '-1',
                    '-c:s', 'srt',
                    '-flush_packets', '1',
                    output_file,
                ],
                600,
            )
            if extract.returncode != 0:
                core.logger.debug('AI translation fallback ffmpeg extraction failed: %s' % (extract.stderr or '').strip())
                return False
            if not subtitle_file_looks_usable(output_file):
                core.logger.debug('AI translation fallback ffmpeg extraction produced no usable subtitle file')
                return False
            core.logger.debug('Extracted complete embedded English subtitle with ffmpeg: %s' % output_file)
            return True
        except Exception as exc:
            try:
                core.os.remove(output_file)
            except:
                pass
            core.logger.debug('AI translation fallback ffmpeg extraction exception: %s' % exc)
            return False

    def extract_embedded_english_subfile(english_subtitle):
        ffprobe = find_binary('ffprobe')
        ffmpeg = find_binary('ffmpeg')
        if not ffprobe:
            core.logger.debug('AI translation fallback skipped: ffprobe unavailable for embedded subtitle extraction')
            return None

        input_url = current_playing_url()
        if not input_url:
            core.logger.debug('AI translation fallback skipped: no playing URL for embedded subtitle extraction')
            return None

        if input_url.startswith('plugin://'):
            core.logger.debug('AI translation fallback skipped: playing URL is not directly readable by ffmpeg')
            return None

        try:
            probe = run_subprocess(
                [
                    ffprobe,
                    '-v', 'error',
                    '-select_streams', 's',
                    '-show_entries', 'stream=index,codec_name:stream_tags=language,title',
                    '-of', 'json',
                    input_url,
                ],
                25,
            )
            if probe.returncode != 0:
                core.logger.debug('AI translation fallback ffprobe failed: %s' % (probe.stderr or '').strip())
                return None
            subtitle_streams = (core.json.loads(probe.stdout or '{}').get('streams') or [])
        except Exception as exc:
            core.logger.debug('AI translation fallback ffprobe exception: %s' % exc)
            return None

        text_codecs = {'subrip', 'ass', 'ssa', 'webvtt', 'mov_text', 'text'}
        selected_index = english_subtitle.get('index')
        english_streams = []
        for ordinal, stream in enumerate(subtitle_streams):
            if stream_language_code(stream) != 'eng':
                continue
            if stream.get('codec_name') not in text_codecs:
                continue
            if selected_index == ordinal:
                english_streams.insert(0, stream)
            else:
                english_streams.append(stream)

        if not english_streams:
            core.logger.debug('AI translation fallback skipped: no text-based embedded English subtitle stream found')
            return None

        stream = english_streams[0]
        stream_index = stream.get('index')
        if stream_index in (None, ''):
            core.logger.debug('AI translation fallback skipped: ffprobe did not expose an embedded subtitle stream index')
            return None

        try:
            core.kodi.xbmcvfs.mkdirs(core.utils.temp_dir)
        except:
            pass

        output_file = core.os.path.join(core.utils.temp_dir, 'embedded.english.%s.full.eng.srt' % stream_index)
        try:
            try:
                core.os.remove(output_file)
            except:
                pass
            core.logger.debug(
                'Extracting complete embedded English subtitle for AI translation: stream=%s codec=%s output=%s' % (
                    stream_index,
                    stream.get('codec_name'),
                    output_file,
                )
            )
            if extract_embedded_subfile_with_ffprobe_packets(ffprobe, input_url, stream_index, output_file):
                return output_file
            if ffmpeg and extract_embedded_subfile_with_ffmpeg(ffmpeg, input_url, stream_index, output_file):
                return output_file
            return None
        except Exception as exc:
            try:
                core.os.remove(output_file)
            except:
                pass
            core.logger.debug('AI translation fallback ffmpeg extraction exception: %s' % exc)
            return None

    def translate_and_attach_subfile(subfile, target_preferredlang, ai_provider, ai_api_key, ai_model, reason, source='', full_file=False):
        nonlocal last_subfile, ai_last_timestamp, ai_tries, has_done_subs_check
        nonlocal ai_translation_active, ai_translation_source, attached_subtitle_active

        target_language = language_code(target_preferredlang)
        if not target_language:
            core.logger.debug('AI translation fallback skipped: no target subtitle language')
            return False

        core.logger.debug('Using AI to translate %s: %s' % (reason, subfile))
        subfile_translated = ai_translated_subfile_path(subfile, target_language)

        moviename = '%s (%s)' % (core.last_meta.title, core.last_meta.year) if core.last_meta else ''

        core.logger.debug('Translating subtitles with AI provider: %s, model: %s' % (ai_provider, ai_model))
        core.logger.debug('Moviename: %s, target_language: %s' % (moviename, target_language))

        ai_last_timestamp = core.kodi.xbmc.Player().getTime()
        translation_range = ai_max_range + ai_step if source == 'embedded_english' else ai_max_range
        begin_seconds = None if full_file else ai_last_timestamp
        end_seconds = None if full_file else ai_last_timestamp + translation_range
        if full_file:
            core.logger.debug('Translating complete subtitle file with AI')

        partial_attach_window_seconds = 300.0
        live_partial_file = ai_translated_subfile_path(subfile, target_language, True)
        live_partial_state = {'attached_batch': 0, 'attached_coverage_seconds': 0.0, 'attached_file': ''}
        notification_state = {'shown': False}

        def notify_ai_translated_subtitle_selected():
            if notification_state['shown']:
                return
            notification_state['shown'] = True
            core.kodi.notification('GPT4 Translated', time=4000)

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
            if coverage_seconds < partial_attach_window_seconds and batch_number < total_batches:
                return
            if (
                batch_number < total_batches
                and live_partial_state['attached_batch'] > 0
                and coverage_seconds - live_partial_state['attached_coverage_seconds'] < partial_attach_window_seconds
            ):
                return
            if not subtitle_file_looks_usable(output_file):
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

        core.utils.gptsubtrans.translate(
            input_file=subfile,
            target_language=target_language,
            output_file=subfile_translated,
            moviename=moviename,
            provider=ai_provider,
            api_key=ai_api_key,
            model=ai_model,
            begin_seconds=begin_seconds,
            end_seconds=end_seconds,
            priority_seconds=ai_last_timestamp if full_file else None,
            log=core.logger.debug,
            partial_callback=attach_partial_translation if full_file else None
        )

        last_subfile = subfile
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
        ai_tries = 0
        has_done_subs_check = bool(full_file)
        ai_translation_active = not full_file
        ai_translation_source = source
        attached_subtitle_active = True
        return True

    def try_embedded_english_ai_translation(target_preferredlang, ai_provider, ai_api_key, ai_model):
        english_subtitle = player_subtitle_for_language('English')
        if not english_subtitle:
            core.logger.debug('AI translation fallback skipped: no embedded English subtitle stream')
            return False

        subfile = extract_embedded_english_subfile(english_subtitle)
        if not subfile:
            return False

        return translate_and_attach_subfile(
            subfile,
            target_preferredlang,
            ai_provider,
            ai_api_key,
            ai_model,
            'embedded English subtitle stream',
            'embedded_english_full',
            True,
        )

    def download_and_attach_result(result, preferredlang, preferredlang_preai, use_ai, ai_provider, ai_api_key, ai_model, full_file_ai=False):
        nonlocal last_subfile, ai_last_timestamp, ai_tries, has_done_subs_check, attached_subtitle_active

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
            attached_subtitle_active = True
            return True

        return translate_and_attach_subfile(
            subfile,
            preferredlang_preai,
            ai_provider,
            ai_api_key,
            ai_model,
            'downloaded subtitle fallback',
            'downloaded_english_full' if full_file_ai else '',
            full_file_ai,
        )

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
                keep_current_attached_subtitle = has_video and has_done_subs_check and attached_subtitle_active
                if not keep_current_attached_subtitle:
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

        core.logger.debug('use_ai_translation: %s, ai_translation_active: %s, subfile: %s' % (use_ai, ai_translation_active, subfile))
        if use_ai and ai_translation_active and subfile:
            def translate_subtitles():
                nonlocal ai_last_timestamp, ai_tries, last_subfile

                timestamp = core.kodi.xbmc.Player().getTime()
                previous_ai_last_timestamp = ai_last_timestamp

                try:
                    active_subfile = subfile
                    translation_range = ai_max_range

                    moviename = '%s (%s)' % (core.last_meta.title, core.last_meta.year) if core.last_meta else ''
                    target_language = language_code(core.kodi.parse_language(core.kodi.get_kodi_setting('locale.subtitlelanguage')))
                    if not target_language:
                        core.logger.debug('AI translation skipped: no target subtitle language')
                        return False

                    subfile_translated = ai_translated_subfile_path(active_subfile, target_language)

                    if previous_ai_last_timestamp is not None and previous_ai_last_timestamp + ai_step > timestamp and timestamp > previous_ai_last_timestamp and core.kodi.xbmcvfs.exists(subfile_translated):
                        core.logger.debug('Skipping AI translation, already translated')
                        return True

                    ai_last_timestamp = timestamp
                    core.logger.debug('Subtitles file: %s' % active_subfile)
                    core.logger.debug('Using AI to translate portion of subtitles between %s and %s seconds in %s' % (ai_last_timestamp, ai_last_timestamp + translation_range, target_language))

                    core.utils.gptsubtrans.translate(
                        input_file=active_subfile,
                        target_language=target_language,
                        output_file=subfile_translated,
                        moviename=moviename,
                        provider=ai_provider,
                        api_key=ai_api_key,
                        model=ai_model,
                        begin_seconds=ai_last_timestamp,
                        end_seconds=ai_last_timestamp + translation_range,
                        log=core.logger.debug
                    )

                    last_subfile = active_subfile
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
            def update_sub_stream(force=False, reason=''):
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
                if force:
                    core.logger.debug(
                        'Selected existing preferred subtitle stream before fallback | reason=%s | index=%s | language=%s' % (
                            reason or 'unspecified',
                            sub_index,
                            preferredlang,
                        )
                    )
                return True

            has_subtitles = update_sub_stream()
        except Exception as e:
            core.logger.debug('Error on update_sub_stream: %s' % e)

        if has_subtitles:
            continue

        if not core.kodi.get_bool_setting('general', 'auto_download'):
            core.kodi.xbmc.executebuiltin('ActivateWindow(SubtitleSearch)')
            continue

        languages = normalize_language_list(core.kodi.get_kodi_setting('subtitles.languages'))
        if preferredlang and preferredlang not in languages:
            languages.append(preferredlang)
        languages = remove_english_search_languages_for_ai(languages, preferredlang)
        preferredlang_preai = preferredlang

        forced_result, forced_payload = _selector_forced_subtitle_result(core)
        if forced_result:
            try:
                forced_requires_ai_translation = _selector_payload_requires_ai_translation(forced_payload)
                if forced_requires_ai_translation and not use_ai:
                    core.logger.debug(
                        'Skipping selector-matched English subtitle fallback because AI translation is not configured | subtitle=%s' % (
                            _selector_matched_subtitle_name(forced_result),
                        )
                    )
                elif not forced_requires_ai_translation and not subtitle_result_matches_languages(forced_result, languages):
                    core.logger.debug(
                        'Skipping selector-matched runtime subtitle outside configured languages | subtitle=%s | languages=%s' % (
                            _selector_matched_subtitle_name(forced_result),
                            languages,
                        )
                    )
                else:
                    if forced_requires_ai_translation:
                        if update_sub_stream(
                            force=True,
                            reason='selector English AI fallback guard',
                        ):
                            core.logger.debug(
                                'Skipping selector-matched English AI fallback because an existing preferred-language subtitle stream is available'
                            )
                            continue
                        forced_download_language = forced_payload.get('ai_translation_source_language') or 'English'
                    else:
                        forced_download_language = preferredlang
                    core.logger.debug(
                        'Using selector-matched runtime subtitle | source_key=%s | score=%s | reason=%s | subtitle=%s | ai_translate=%s' % (
                            forced_payload.get('source_key', ''),
                            forced_payload.get('match_score'),
                            forced_payload.get('match_reason'),
                            _selector_matched_subtitle_name(forced_result),
                            forced_requires_ai_translation,
                        )
                    )
                    if download_and_attach_result(
                        forced_result,
                        forced_download_language,
                        preferredlang_preai,
                        forced_requires_ai_translation,
                        ai_provider if forced_requires_ai_translation else '',
                        ai_api_key if forced_requires_ai_translation else '',
                        ai_model if forced_requires_ai_translation else '',
                        forced_requires_ai_translation,
                    ):
                        continue
            except:
                import traceback
                core.logger.error('Error applying selector-matched subtitle: %s' % traceback.format_exc())

        has_imdb = core.kodi.xbmc.getInfoLabel('VideoPlayer.IMDBNumber')
        attached_subtitle = False

        if has_imdb:
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
            continue

        if use_ai:
            core.logger.debug('AI fallback skipped after runtime search: external English subtitle fallback is selected before playback')
