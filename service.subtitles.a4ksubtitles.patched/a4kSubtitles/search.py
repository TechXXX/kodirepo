# -*- coding: utf-8 -*-
import os

shadow_snapshot_dir = 'special://profile/addon_data/plugin.video.fenlight/subtitle_selector_shadow'

def __replace_non_ascii_digits(text):
    if not text:
        return text
    return ''.join(' ' if char.isdigit() and char not in '0123456789' else char for char in text)

def __is_ascii_digit_token(token):
    return bool(token) and all(char in '0123456789' for char in token)

def __shadow_translate_path(core, path):
    try:
        return core.kodi.xbmcvfs.translatePath(path)
    except:
        return core.kodi.xbmc.translatePath(path)

def __shadow_match_key(meta):
    media_type = 'episode' if getattr(meta, 'is_tvshow', False) else 'movie'
    title = getattr(meta, 'tvshow', None) or getattr(meta, 'title', None) or ''
    season = getattr(meta, 'season', '') or ''
    episode = getattr(meta, 'episode', '') or ''
    if season == '-1':
        season = ''
    if episode == '-1':
        episode = ''
    return '%s|%s|%s|%s|%s' % (
        media_type,
        getattr(meta, 'imdb_id', '') or '',
        season,
        episode,
        title,
    )

def __shadow_serialized_meta(meta):
    return {
        'media_type': 'episode' if getattr(meta, 'is_tvshow', False) else 'movie',
        'title': getattr(meta, 'title', None),
        'tvshow': getattr(meta, 'tvshow', None),
        'year': getattr(meta, 'year', None),
        'imdb_id': getattr(meta, 'imdb_id', None),
        'season': getattr(meta, 'season', None),
        'episode': getattr(meta, 'episode', None),
        'filename_without_ext': getattr(meta, 'filename_without_ext', None),
        'languages': getattr(meta, 'languages', None),
        'preferredlanguage': getattr(meta, 'preferredlanguage', None),
    }

def __shadow_serialized_action_args(core, action_args):
    if not isinstance(action_args, dict):
        return {}

    serialized = {}
    for key, value in action_args.items():
        try:
            core.json.dumps(value)
            serialized[key] = value
        except Exception:
            serialized[key] = str(value)
    return serialized

def __shadow_serialized_result(core, result):
    action_args = result.get('action_args', {})
    return {
        'service_name': result.get('service_name'),
        'service': result.get('service'),
        'lang': result.get('lang'),
        'lang_code': result.get('lang_code'),
        'name': result.get('name'),
        'rating': result.get('rating'),
        'sync': result.get('sync'),
        'impaired': result.get('impaired'),
        'color': result.get('color'),
        'comment': result.get('comment'),
        'comments': result.get('comments'),
        'ai_translated': bool(result.get('ai_translated') or action_args.get('ai_translated')),
        'machine_translated': bool(result.get('machine_translated') or action_args.get('machine_translated')),
        'action_args': __shadow_serialized_action_args(core, action_args),
    }

def __shadow_safe_name(value):
    return ''.join(i if i.isalnum() else '_' for i in value).strip('_') or 'latest'

def __write_stage_debug(core, filename, results):
    try:
        directory = __shadow_translate_path(core, shadow_snapshot_dir)
        os.makedirs(directory, exist_ok=True)
        serialized_results = [__shadow_serialized_result(core, item) for item in results]
        with open(os.path.join(directory, filename), 'w') as file_handle:
            file_handle.write(core.json.dumps(serialized_results, indent=2))
    except Exception as exc:
        core.logger.error('stage debug write failed for %s: %s' % (filename, exc))

def __write_shadow_subtitle_snapshot(core, meta, results):
    try:
        directory = __shadow_translate_path(core, shadow_snapshot_dir)
        os.makedirs(directory, exist_ok=True)
        timestamp = int(core.time.time() * 1000)
        match_key = __shadow_match_key(meta)
        alias_mode = getattr(core, 'shadow_snapshot_alias_mode', None)
        if alias_mode is None:
            alias_mode = 'pairable' if core.api_mode_enabled else 'history_only'
        serialized_results = [__shadow_serialized_result(core, item) for item in results]
        payload = {
            'snapshot_type': 'a4k_subtitles',
            'timestamp': timestamp,
            'match_key': match_key,
            'alias_mode': alias_mode,
            'meta': __shadow_serialized_meta(meta),
            'results': serialized_results,
        }
        json_data = core.json.dumps(payload, indent=2)
        history_path = os.path.join(directory, 'subtitles_%s.json' % timestamp)
        latest_path = os.path.join(directory, 'latest_subtitles.json')
        match_latest_path = os.path.join(directory, 'latest_subtitles_%s.json' % __shadow_safe_name(match_key))
        targets = [history_path]
        if alias_mode != 'history_only':
            targets.extend((latest_path, match_latest_path))
        for target in targets:
            with open(target, 'w') as file_handle:
                file_handle.write(json_data)
        with open(os.path.join(directory, 'shadow_serialized_debug.json'), 'w') as file_handle:
            file_handle.write(core.json.dumps(serialized_results, indent=2))
        core.logger.info('shadow serialized subtitle results: %s' % core.json.dumps(serialized_results, indent=2))
        if alias_mode == 'history_only':
            core.logger.debug(lambda: 'shadow snapshot saved (history only): %s' % history_path)
        else:
            core.logger.debug(lambda: 'shadow snapshot saved: %s' % history_path)
    except Exception as exc:
        core.logger.error('shadow snapshot write failed: %s' % exc)

def __comment_candidate_names(core, comments):
    if not comments:
        return []

    comments = __replace_non_ascii_digits(core.utils.unquote(comments))
    names = []
    lines = [line.strip() for line in core.re.split(r'[\r\n]+', comments) if line and line.strip()]
    for line in lines:
        line = core.re.sub(r'^[^:]+:\s*', '', line).strip()
        line = core.re.sub(r'\s*\([^)]*\)\s*$', '', line).strip()
        line = line.strip(' -|,;')
        if not line:
            continue
        if len(core.re.findall(r'[A-Za-z0-9]', line)) < 6:
            continue
        if not any(sep in line for sep in ('.', '-', ' ')):
            continue
        if line not in names:
            names.append(line)
    return names

def __release_group_candidates(core, text, regexsplitwords, ignored_tokens):
    if not text:
        return []

    normalized_text = __replace_non_ascii_digits(core.utils.unquote(text))
    raw_tokens = [token.strip().lower() for token in core.re.split(regexsplitwords, normalized_text) if token and token.strip()]
    tokens = [token for token in raw_tokens if not __is_ascii_digit_token(token) and token not in ignored_tokens]
    if not tokens:
        return []

    tail = tokens[-3:]
    candidates = []
    if len(tail[-1]) >= 4:
        candidates.append(tail[-1])
    for size in (2, 3):
        if len(tail) >= size:
            candidate = ' '.join(tail[-size:])
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates

def __comments_reference_release_group(core, comments, candidates, regexsplitwords):
    if not comments or not candidates:
        return False

    normalized_comments = core.re.sub(regexsplitwords, ' ', __replace_non_ascii_digits(core.utils.unquote(comments)).lower())
    normalized_comments = ' ' + core.re.sub(r'\s+', ' ', normalized_comments).strip() + ' '
    for candidate in candidates:
        normalized_candidate = ' ' + candidate.strip().lower() + ' '
        if normalized_candidate in normalized_comments:
            return True
    return False

def __sample_result_names(results, limit=3):
    sample_names = []
    for result in results:
        if not isinstance(result, dict):
            continue
        name = result.get('name', '')
        if not name:
            action_args = result.get('action_args', {})
            name = action_args.get('filename', '')
        if not name or name in sample_names:
            continue
        sample_names.append(name)
        if len(sample_names) >= limit:
            break
    return sample_names

def __log_results_summary(core, stage, results):
    try:
        if results is None:
            summary = 'type=None count=0'
        elif not isinstance(results, list):
            summary = 'type=%s' % type(results).__name__
        else:
            first_keys = 'None'
            if results and isinstance(results[0], dict):
                first_keys = ','.join(sorted(results[0].keys())[:8]) or 'None'
            sample_names = ' | '.join(__sample_result_names(results)) or 'None'
            summary = 'type=list count=%s keys=%s sample_names=%s' % (len(results), first_keys, sample_names)
        core.logger.debug('search.%s - %s' % (stage, summary))
    except Exception as exc:
        core.logger.error('search.%s - summary_failed: %s' % (stage, exc))

def __auth_service(core, service_name, request):
    service = core.services[service_name]
    response = core.request.execute(core, request)
    service.parse_auth_response(core, service_name, response)

def __query_service(core, service_name, meta, request, results):
    try:
        service = core.services[service_name]
        response = core.request.execute(core, request)

        if response and response.status_code == 200 and response.text:
            service_results = service.parse_search_response(core, service_name, meta, response)
        else:
            service_results = []

        __log_results_summary(core, '%s.raw' % service_name, service_results)
        __write_stage_debug(core, 'stage_parse_%s.json' % service_name, service_results)
        results.extend(service_results)
        __write_stage_debug(core, 'stage_query_results_%s.json' % service_name, results)

        core.logger.debug(lambda: core.json.dumps({
            'url': request['url'],
            'count': len(service_results),
            'status_code': response.status_code if response else 'N/A'
        }, indent=2))
    finally:
        core.progress_text = core.progress_text.replace(service.display_name, '')
        core.kodi.update_progress(core)

def __add_results(core, results, meta):  # pragma: no cover
    for item in results:
        listitem = core.kodi.create_listitem(item)

        action_args = core.utils.quote_plus(core.json.dumps(item['action_args']))

        core.kodi.xbmcplugin.addDirectoryItem(
            handle=core.handle,
            listitem=listitem,
            isFolder=False,
            url='plugin://%s/?action=download&service_name=%s&action_args=%s'
                % (core.kodi.addon_id, item['service_name'], action_args)
        )

def __has_results(service_name, results):
    return any(map(lambda r: r['service_name'] == service_name, results))

def __opensubtitles_results_missing_translation_flags(results):
    for result in results:
        if result.get('service_name') != 'opensubtitles':
            continue

        action_args = result.get('action_args') or {}
        if 'ai_translated' not in action_args or 'machine_translated' not in action_args:
            return True

    return False

def __save_results(core, meta, results):
    try:
        if len(results) == 0:
            return
        meta_hash = core.cache.get_meta_hash(meta)
        json_data = core.json.dumps({
            'hash': meta_hash,
            'timestamp': core.time.time(),
            'results': results
        }, indent=2)
        with open(core.cache.results_filepath, 'w') as f:
            f.write(json_data)
    except:
        import traceback
        traceback.print_exc()

def __get_last_results(core, meta):
    force_search = []

    if core.api_mode_enabled:
        core.logger.debug('api_mode search bypassing persisted subtitle cache')
        return ([], force_search)

    try:
        with open(core.cache.results_filepath, 'r') as f:
            last_results = core.json.loads(f.read())

        meta_hash = core.cache.get_meta_hash(meta)
        if last_results['hash'] != meta_hash:
            return ([], [])

        has_bsplayer_results = __has_results('bsplayer', last_results['results'])
        has_bsplayer_results_expired = core.time.time() - last_results['timestamp'] > 3 * 60
        if has_bsplayer_results and has_bsplayer_results_expired:
            last_results['results'] = list(filter(lambda r: r['service_name'] != 'bsplayer', last_results['results']))
            force_search.append('bsplayer')

        has_stale_opensubtitles_translation_cache = __opensubtitles_results_missing_translation_flags(last_results['results'])
        if has_stale_opensubtitles_translation_cache:
            last_results['results'] = list(filter(lambda r: r['service_name'] != 'opensubtitles', last_results['results']))
            force_search.append('opensubtitles')
            core.logger.debug('opensubtitles cache missing translation flags, forcing refresh')

        return (last_results['results'], force_search)
    except: pass

    return ([], [])

def __sanitize_results(core, meta, results):
    __write_stage_debug(core, 'stage_before_sanitize.json', results)
    temp_dict = {}

    for result in results:
        temp_dict[result['action_args']['url']] = result
        result['name'] = core.utils.unquote(result['name'])

    sanitized = list(temp_dict.values())
    __write_stage_debug(core, 'stage_after_sanitize.json', sanitized)
    return sanitized

def __apply_language_filter(meta, results):
    return list(filter(lambda x: x and x['lang'] in meta.languages, results))

def __apply_limit(core, all_results, meta):
    limit = core.kodi.get_int_setting('general.results_limit')
    lang_limit = int(limit / len(meta.languages))
    if lang_limit * len(meta.languages) < limit:
        lang_limit += 1

    results = []
    for lang in meta.languages:
        lang_results = list(filter(lambda x: x['lang'] == lang, all_results))
        if len(lang_results) < lang_limit:
            lang_limit += lang_limit - len(lang_results)
        results.extend(lang_results[:lang_limit])

    return results[:limit]

def __prepare_results(core, meta, results):
    __log_results_summary(core, 'prepare.input', results)
    results = __apply_language_filter(meta, results)
    __log_results_summary(core, 'prepare.language_filter', results)
    results = __sanitize_results(core, meta, results)
    __log_results_summary(core, 'prepare.sanitized', results)
    __write_stage_debug(core, 'stage_pre_sort.json', results)

    release_groups = [
        ['bluray', 'bd', 'bdrip', 'brrip', 'bdmv', 'bdscr', 'remux', 'bdremux', 'uhdremux', 'uhdbdremux', 'uhdbluray'],
        ['web', 'webdl', 'webrip', 'webr', 'webdlrip', 'webcap'],
        ['dvd', 'dvd5', 'dvd9', 'dvdr', 'dvdrip', 'dvdscr'],
        ['scr', 'screener', 'r5', 'r6', 'cam', 'camrip', 'hdcam', 'tele', 'telesync', 'ts']
    ]
    release = []
    for group in release_groups:
        release.extend(group)
    media_exts = ['avi', 'mp4', 'mkv', 'ts', 'm2ts', 'mts', 'mpeg', 'mpg', 'mov', 'wmv', 'flv', 'vob']
    release.extend(media_exts)

    quality_groups = [
        ['4k', '2160p', '2160', '4kuhd', '4kultrahd', 'ultrahd', 'uhd'],
        ['1080p', '1080'],
        ['720p', '720'],
        ['480p'],
        ['360p', '240p', '144p'],
    ]
    quality = []
    for group in quality_groups:
        quality.extend(group)

    service_groups = [
        ['netflix', 'nflx', 'nf'],
        ['amazon', 'amzn', 'primevideo'],
        ['hulu', 'hlu'],
        ['crunchyroll', 'cr'],
        ['disney', 'disneyplus'],
        ['hbo', 'hbonow', 'hbogo', 'hbomax', 'hmax'],
        ['bbc'],
        ['sky', 'skyq'],
        ['syfy'],
        ['atvp', 'atvplus'],
        ['pcok', 'peacock'],
    ]
    service = []
    for group in service_groups:
        service.extend(group)

    codec_groups = [
        ['x264', 'h264', '264', 'avc'],
        ['x265', 'h265', '265', 'hevc'],
        ['av1', 'vp9', 'vp8', 'divx', 'xvid'],
    ]
    codec = []
    for group in codec_groups:
        codec.extend(group)

    audio_groups = [
        ['dts', 'dtshd', 'atmos', 'truehd'],
        ['aac', 'ac'],
        ['dd', 'ddp', 'ddp5', 'dd5', 'dd2', 'dd1', 'dd7', 'ddp7'],
    ]
    audio = []
    for group in audio_groups:
        audio.extend(group)

    color_groups = [
        ['hdr', '10bit', '12bit', 'hdr10', 'hdr10plus', 'dolbyvision', 'dolby', 'vision'],
        ['sdr', '8bit'],
    ]
    color = []
    for group in color_groups:
        color.extend(group)

    extra = ['extended', 'cut', 'remastered', 'proper']
    ignored_release_group_tokens = set(release + quality + service + codec + audio + color + extra + ['multi', 'multiple', 'sub', 'subs', 'subtitle'])

    source_filename = core.utils.unquote(getattr(meta, 'filename', '') or '').lower()
    filename = core.utils.unquote(meta.filename_without_ext).lower()
    source_match_text = source_filename or filename
    regexsplitwords = r'[\s\.\:\;\(\)\[\]\{\}\\\/\&\€\'\`\#\@\=\$\?\!\%\+\-\_\*\^]'
    meta_nameparts = core.re.split(regexsplitwords, source_match_text)
    source_release_candidates = __release_group_candidates(core, source_match_text, regexsplitwords, ignored_release_group_tokens)

    release_list = [i for i in meta_nameparts if i in release]
    quality_list = [i for i in meta_nameparts if i in quality]
    service_list = [i for i in meta_nameparts if i in service]
    codec_list = [i for i in meta_nameparts if i in codec]
    audio_list = [i for i in meta_nameparts if i in audio]
    color_list = [i for i in meta_nameparts if i in color]
    extra_list = [i for i in meta_nameparts if i in extra]

    for item in release_list:
        for group in release_groups:
            if item in group:
                release_list = group
                break

    for item in quality_list:
        for group in quality_groups:
            if item in group:
                quality_list = group
                break

    for item in service_list:
        for group in service_groups:
            if item in group:
                service_list = group
                break

    for item in codec_list:
        for group in codec_groups:
            if item in group:
                codec_list = group
                break

    for item in audio_list:
        for group in audio_groups:
            if item in group:
                audio_list = group
                break

    for item in color_list:
        for group in color_groups:
            if item in group:
                color_list = group
                break

    def _filter_name(x):
        name_diff_ignore = media_exts + quality + codec + audio + color
        name_diff_ignore += ["multi", 'multiple', 'sub', 'subs', 'subtitle']

        x = __replace_non_ascii_digits(x).strip()
        if __is_ascii_digit_token(x):
            x = str(int(x)).zfill(3)
        elif x.isdigit():
            x = ''
        elif x.lower() in name_diff_ignore:
            x = ''
        return x.lower()

    def _match_numbers(a, b):
        offset = 0
        for s in b:
            s = __replace_non_ascii_digits(core.re.sub(r'v[1-4]', "", s)).strip()
            if not __is_ascii_digit_token(s):
                continue
            elif meta.episode and s.zfill(3) == meta.episode.zfill(3):
                offset += 0.4
            elif s in a:
                offset += 0.2

        return offset

    def _name_match_score(candidate_name, cleaned_source_nameparts, source_release_group):
        candidate_parts = core.re.split(regexsplitwords, candidate_name.lower())
        cleaned_candidate_parts = list(filter(len, map(_filter_name, candidate_parts)))
        candidate_matching_offset = 0
        candidate_release_mismatch_penalty = 0

        candidate_release_group = None
        for group in release_groups:
            if any(token in cleaned_candidate_parts for token in group):
                candidate_release_group = group
                break

        if source_release_group and candidate_release_group and source_release_group is not candidate_release_group:
            candidate_release_mismatch_penalty += 1.2

        if meta.is_tvshow:
            sub_info = core.utils.extract_season_episode(candidate_name)

            is_season = sub_info.season and sub_info.season == meta.season.zfill(3)
            is_episode = sub_info.episode and sub_info.episode == meta.episode.zfill(3)

            if is_season and not sub_info.episode:
                candidate_matching_offset += 0.6
            if is_season and is_episode:
                candidate_matching_offset += 0.4
            elif meta.episode and int(meta.episode) in sub_info.episodes_range:
                candidate_matching_offset += 0.3
            elif sub_info.season and sub_info.episode:
                candidate_matching_offset -= 0.5

            if candidate_matching_offset == 0:
                candidate_matching_offset = _match_numbers(cleaned_source_nameparts, cleaned_candidate_parts)

        return core.difflib.SequenceMatcher(None, cleaned_source_nameparts, cleaned_candidate_parts).ratio() + candidate_matching_offset - candidate_release_mismatch_penalty

    def sorter(x):
        name = x['name'].lower()
        nameparts = core.re.split(regexsplitwords, name)
        action_args = x.get('action_args', {})

        # Add episode number to action_args to detect the desired episode later during sub extraction.
        action_args.setdefault("episodeid", meta.episode.zfill(3) if meta.episode else "")

        cleaned_nameparts = list(filter(len, map(_filter_name, nameparts)))
        cleaned_file_nameparts = list(filter(len, map(_filter_name, meta_nameparts)))
        translated_fallback_rank = int(bool(action_args.get('ai_translated', False) or action_args.get('machine_translated', False)))

        source_release_group = None
        subtitle_release_group = None
        for group in release_groups:
            if any(token in cleaned_file_nameparts for token in group):
                source_release_group = group
                break
        for group in release_groups:
            if any(token in cleaned_nameparts for token in group):
                subtitle_release_group = group
                break

        prerelease_group = release_groups[-1]
        source_is_prerelease = source_release_group is prerelease_group
        subtitle_is_prerelease = subtitle_release_group is prerelease_group or any(token in cleaned_nameparts for token in prerelease_group)
        prerelease_rank = 0 if source_is_prerelease else int(subtitle_is_prerelease)
        direct_name_score = _name_match_score(name, cleaned_file_nameparts, source_release_group)
        direct_release_candidates = __release_group_candidates(core, name, regexsplitwords, ignored_release_group_tokens)
        direct_release_group_hit = bool(set(source_release_candidates).intersection(direct_release_candidates))
        if direct_release_group_hit:
            direct_name_score = max(direct_name_score, 1.08)
        comment_name_score = 0
        comment_release_group_hit = False
        comment_only_rank = 0
        comments = x.get('comments', '')
        if comments and not direct_release_group_hit and direct_name_score < 0.9:
            comment_name_score = max((_name_match_score(candidate, cleaned_file_nameparts, source_release_group) for candidate in __comment_candidate_names(core, comments)), default=0)
            comment_release_group_hit = __comments_reference_release_group(core, comments, source_release_candidates, regexsplitwords)
            if comment_release_group_hit:
                comment_name_score = max(comment_name_score, direct_name_score + 0.25, 1.15)
                comment_only_rank = 0
            elif comment_name_score > direct_name_score:
                comment_only_rank = 1
        effective_name_score = direct_name_score if direct_release_group_hit or (comment_only_rank == 0 and not comment_release_group_hit) else comment_name_score - (0.0 if comment_release_group_hit else 0.02)

        return (
            prerelease_rank,
            translated_fallback_rank,
            not direct_release_group_hit,
            not comment_release_group_hit,
            comment_only_rank,
            not x['lang'] == meta.preferredlanguage,
            meta.languages.index(x['lang']),
            not x['sync'] == 'true',
            -effective_name_score,
            -sum(i in nameparts for i in release_list) * 10,
            -sum(i in nameparts for i in quality_list) * 10,
            -sum(i in nameparts for i in codec_list) * 10,
            -sum(i in nameparts for i in service_list) * 10,
            -sum(i in nameparts for i in audio_list),
            -sum(i in nameparts for i in color_list),
            -sum(i in nameparts for i in extra_list),
            -core.difflib.SequenceMatcher(None, filename, name).ratio(),
            -x['rating'],
            not x['impaired'] == 'true',
            x['service'],
        )

    results = sorted(results, key=sorter)
    __log_results_summary(core, 'prepare.sorted_initial', results)
    results = __apply_limit(core, results, meta)
    __log_results_summary(core, 'prepare.limited', results)
    results = sorted(results, key=sorter)
    __log_results_summary(core, 'prepare.sorted_final', results)

    return results

def __parse_languages(core, languages):
    return list({language for language in (core.kodi.parse_language(x) for x in languages) if language is not None})

def __chain_auth_and_search_threads(core, auth_thread, search_thread):
    auth_thread.start()
    auth_thread.join()
    search_thread.start()
    search_thread.join()

def __wait_threads(core, request_threads):
    threads = []

    for (auth_thread, search_thread) in request_threads:
        if not auth_thread:
            threads.append(search_thread)
        else:
            thread = core.threading.Thread(target=__chain_auth_and_search_threads, args=(core, auth_thread, search_thread))
            threads.append(thread)

    core.utils.wait_threads(threads)

def __complete_search(core, results, meta):
    __log_results_summary(core, 'complete', results)
    __write_shadow_subtitle_snapshot(core, meta, results)
    if core.api_mode_enabled:
        return results

    __add_results(core, results, meta)  # pragma: no cover

def __search(core, service_name, meta, results):
    service = core.services[service_name]
    requests = service.build_search_requests(core, service_name, meta)
    core.logger.debug(lambda: '%s - %s' % (service_name, core.json.dumps(requests, default=lambda o: '', indent=2)))

    threads = []
    for request in requests:
        thread = core.threading.Thread(target=__query_service, args=(core, service_name, meta, request, results))
        threads.append(thread)

    core.utils.wait_threads(threads)

def search(core, params):
    meta = core.video.get_meta(core)
    core.last_meta = meta

    meta.languages = __parse_languages(core, core.utils.unquote(params['languages']).split(','))
    meta.preferredlanguage = core.kodi.parse_language(params['preferredlanguage'])
    core.logger.debug(lambda: core.json.dumps(meta, default=lambda o: '', indent=2))
    core.logger.debug('search.meta_languages - languages=%s preferred=%s api_mode=%s filename=%s' % (
        meta.languages, meta.preferredlanguage, core.api_mode_enabled, getattr(meta, 'filename', '')
    ))

    if meta.imdb_id == '':
        core.logger.error('missing imdb id!')
        core.kodi.notification('IMDB ID is not provided')
        return

    threads = []
    (results, force_search) = __get_last_results(core, meta)
    __log_results_summary(core, 'cached', results)
    for service_name in core.services:
        if len(results) > 0 and (__has_results(service_name, results) or service_name not in force_search):
            continue

        if not core.kodi.get_bool_setting(service_name, 'enabled'):
            continue

        service = core.services[service_name]
        core.progress_text += service.display_name + '|'

        auth_thread = None
        auth_request = service.build_auth_request(core, service_name)
        if auth_request:
            auth_thread = core.threading.Thread(target=__auth_service, args=(core, service_name, auth_request))

        search_thread = core.threading.Thread(target=__search, args=(core, service_name, meta, results))

        threads.append((auth_thread, search_thread))

    if len(threads) == 0:
        return __complete_search(core, results, meta)

    core.progress_text = core.progress_text[:-1]
    core.kodi.update_progress(core)

    ready_queue = core.utils.queue.Queue()
    cancellation_token = lambda: None
    cancellation_token.iscanceled = False

    def check_cancellation():  # pragma: no cover
        dialog = core.progress_dialog
        while (core.progress_dialog is not None and not cancellation_token.iscanceled):
            if not dialog.iscanceled():
                core.time.sleep(1)
                continue

            cancellation_token.iscanceled = True
            final_results = __prepare_results(core, meta, results)
            ready_queue.put(__complete_search(core, final_results, meta))
            break

    def wait_all_results():
        __wait_threads(core, threads)
        if cancellation_token.iscanceled:
            return
        final_results = __prepare_results(core, meta, results)
        __save_results(core, meta, final_results)
        ready_queue.put(__complete_search(core, final_results, meta))

    core.threading.Thread(target=check_cancellation).start()
    core.threading.Thread(target=wait_all_results).start()

    return ready_queue.get()
