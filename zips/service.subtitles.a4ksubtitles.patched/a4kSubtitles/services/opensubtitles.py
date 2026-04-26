# -*- coding: utf-8 -*-

__api_host = 'api.opensubtitles.com'
__api_url = 'https://%s/api/v1'
__api_key = '7IQ4FYAepMynq20VYYHyj5mVHtx3qvKa'
__user_agent = 'a4kSubtitles v3'
__content_type = 'application/json'
__date_format = '%Y-%m-%d %H:%M:%S'

def __set_api_headers(core, service_name, request, token_cache=None):
    if core.os.getenv('A4KSUBTITLES_TESTRUN') != 'true' and token_cache is None:
        cache = core.cache.get_tokens_cache()
        token_cache = cache.get(service_name, None)

    base_url = token_cache['base_url'] if token_cache else __api_host

    request['url'] = request['url'] % base_url
    request['headers'] = request.get('headers', {})
    request['headers'].update({
        'User-Agent': __user_agent,
        'Api-Key': __api_key,
        'Accept': __content_type,
        'Content-Type': __content_type,
    })

    if core.os.getenv('A4KSUBTITLES_TESTRUN') == 'true':
        return

    if token_cache and 'token' in token_cache:
        request['headers']['Authorization'] = 'Bearer %s' % token_cache['token']

def build_auth_request(core, service_name):
    if core.os.getenv('A4KSUBTITLES_TESTRUN') == 'true':
        return

    cache = core.cache.get_tokens_cache()
    token_cache = cache.get(service_name, None)
    if token_cache is not None and 'ttl' in token_cache:
        token_ttl = core.datetime.fromtimestamp(core.time.mktime(core.time.strptime(token_cache['ttl'], __date_format)))
        if token_ttl > core.datetime.now():
            return

    cache.pop(service_name, None)
    core.cache.save_tokens_cache(cache)

    username = core.kodi.get_setting(service_name, 'username')
    password = core.kodi.get_setting(service_name, 'password')

    if username == '' or password == '':
        core.kodi.notification('OpenSubtitles now requires authentication! Enter username/password in the addon Settings->Accounts or disable the service.')
        return

    request = {
        'method': 'POST',
        'url': __api_url + '/login',
        'data': core.json.dumps({
            'username': username,
            'password': password,
        }),
    }

    __set_api_headers(core, service_name, request, token_cache=False)

    return request

def parse_auth_response(core, service_name, response):
    if response.status_code == 400:
        core.kodi.notification('OpenSubtitles authentication failed! Bad username. Make sure you have entered your username and not your email in the username field.')
        return
    elif response.status_code != 200 or not response.text:
        core.kodi.notification('OpenSubtitles authentication failed! Check your OpenSubtitles.com username and password.')
        return

    response = core.json.loads(response.text)
    token = response.get('token', None)
    base_url = response.get('base_url', __api_host)
    allowed_downloads = response.get('user', {}).get('allowed_downloads', 0)

    if token is None:
        core.kodi.notification('OpenSubtitles authentication failed!')
        return

    if allowed_downloads == 0:
        core.kodi.notification('OpenSubtitles failed! No downloads left for today.')
        return

    token_cache = {
        'token': token,
        'base_url': base_url,
        'ttl': (core.datetime.now() + core.timedelta(days=1)).strftime(__date_format),
    }

    cache = core.cache.get_tokens_cache()
    cache[service_name] = token_cache
    core.cache.save_tokens_cache(cache)

def __clear_auth_cache(core, service_name):
    cache = core.cache.get_tokens_cache()
    cache.pop(service_name, None)
    core.cache.save_tokens_cache(cache)

def __refresh_auth(core, service_name):
    __clear_auth_cache(core, service_name)

    auth_request = build_auth_request(core, service_name)
    if not auth_request:
        return False

    response = core.request.execute(core, auth_request, progress=False)
    if response is None:
        return False

    parse_auth_response(core, service_name, response)

    token_cache = core.cache.get_tokens_cache().get(service_name, None)
    return bool(token_cache and token_cache.get('token'))

def build_search_requests(core, service_name, meta):
    cache = core.cache.get_tokens_cache()
    token_cache = cache.get(service_name, None)
    if token_cache is None and core.os.getenv('A4KSUBTITLES_TESTRUN') != 'true':
        return []

    lang_ids = core.utils.get_lang_ids(meta.languages, core.kodi.xbmc.ISO_639_1)

    def build_request(params, next_request=None):
        request = {
            'method': 'GET',
            'url': __api_url + '/subtitles',
            'params': params,
        }

        __set_api_headers(core, service_name, request, token_cache)
        if next_request is not None:
            def fallback_if_empty(response):
                try:
                    payload = core.json.loads(response.text)
                    if payload.get('data'):
                        return None
                except Exception:
                    return None
                return next_request

            request['validate'] = fallback_if_empty
        return request

    if meta.is_tvshow:
        episode_query = '%s S%.2dE%.2d' % (meta.tvshow, int(meta.season), int(meta.episode))
        base_params = {
            'languages': ','.join(lang_ids),
            'type': 'episode',
            'season_number': meta.season,
            'episode_number': meta.episode,
        }

        def normalize_imdb_id(imdb_id):
            if not imdb_id:
                return None
            return imdb_id[2:] if imdb_id.startswith('tt') else imdb_id

        # OpenSubtitles episode pages are keyed by the parent TV-show IMDb id plus
        # season/episode. Adding query text to that request can hide valid rows.
        parent_imdb_id = normalize_imdb_id(
            getattr(meta, 'tv_show_imdb_id', '') or getattr(meta, 'imdb_id', '')
        )

        fallback_title = build_request(dict(base_params, query=meta.title)) if meta.title else None
        fallback_episode_title = build_request(
            dict(base_params, query='%s %s' % (episode_query, meta.title)),
            next_request=fallback_title
        ) if meta.title else None
        fallback_episode_query = build_request(
            dict(base_params, query=episode_query),
            next_request=fallback_episode_title
        )

        if not parent_imdb_id:
            return [fallback_episode_query]

        primary_params = dict(base_params, parent_imdb_id=parent_imdb_id)
        return [build_request(primary_params, next_request=fallback_episode_query)]

    base_params = {
        'languages': ','.join(lang_ids),
        'type': 'movie',
    }

    if meta.filehash:
        base_params['moviehash'] = meta.filehash

    imdb_id = meta.imdb_id[2:] if meta.imdb_id.startswith('tt') else meta.imdb_id
    title = meta.title
    title_with_year = '%s %s' % (title, meta.year) if meta.year else title

    fallback_title_only = build_request(dict(base_params, query=title))
    fallback_title_imdb = build_request(
        dict(base_params, query=title, imdb_id=imdb_id),
        next_request=fallback_title_only
    )
    strict_request = build_request(
        dict(base_params, query=title_with_year, imdb_id=imdb_id, year=meta.year),
        next_request=fallback_title_imdb
    )

    return [strict_request]

def parse_search_response(core, service_name, meta, response):
    try:
        results = core.json.loads(response.text)
    except Exception as exc:
        core.logger.error('%s - %s' % (service_name, exc))
        return []

    service = core.services[service_name]

    def map_result(result):
        result = result['attributes']
        imdb_id = result.get('feature_details', {}).get('imdb_id', None)
        if len(result['files']) == 0:
            return None

        tv_show_imdb_id_as_int = getattr(meta, 'tv_show_imdb_id_as_int', 0)
        imdb_matches = imdb_id is None or imdb_id in (meta.imdb_id_as_int, tv_show_imdb_id_as_int)
        # OpenSubtitles episode searches can return valid episode subtitles keyed to a
        # different IMDb entity than the pre-play mocked metadata. Keep TV episode
        # candidates and let the later filename-based ranking decide.
        if not meta.is_tvshow and not imdb_matches:
            return None
        if meta.is_tvshow and imdb_id is not None and not imdb_matches and not (meta.season and meta.episode):
            return None

        filename = result.get('release') or result['files'][0]['file_name']
        language = core.utils.get_lang_id(result['language'], core.kodi.xbmc.ENGLISH_NAME)

        return {
            'service_name': service_name,
            'service': service.display_name,
            'lang': language,
            'name': filename,
            'comments': result.get('comments', ''),
            'rating': int(round(float(result['ratings']) / 2)),
            'lang_code': core.utils.get_lang_id(language, core.kodi.xbmc.ISO_639_1),
            'sync': 'true' if result.get('moviehash_match', False) else 'false',
            'impaired': 'true' if result['hearing_impaired'] else 'false',
            'color': 'springgreen',
            'action_args': {
                'url': result['files'][0]['file_id'],
                'lang': language,
                'filename': filename,
                'release_name': result.get('release'),
                'gzip': True,
                'ai_translated': result.get('ai_translated', False),
                'machine_translated': result.get('machine_translated', False),
            }
        }

    return [item for item in map(map_result, results['data']) if item]

def build_download_request(core, service_name, args, retry=0, reauthed=False):
    def download_request(response):
        result = core.json.loads(response.text)

        if not result.get('link', None) and result['remaining'] == 0:
            core.kodi.notification('OpenSubtitles failed! No downloads left for today.')
            return

        return {
            'method': 'GET',
            'url': result['link'],
            'stream': True
        }

    def validate_download_response(response):
        if response.status_code == 401 and not reauthed:
            core.logger.info('%s - download returned 401, clearing token cache and retrying once' % service_name)
            if __refresh_auth(core, service_name):
                return build_download_request(core, service_name, args, retry=retry, reauthed=True)

            core.logger.error('%s - download returned 401 and auth refresh failed' % service_name)
            return None

        if retry > 5:
            return None

        if response.status_code in [502, 503, 429, 409, 403]:
            next_retry = retry + 1
            if response.status_code in [503, 403]:
                next_retry = 6
            else:
                core.time.sleep(3)

            return build_download_request(core, service_name, args, retry=next_retry, reauthed=reauthed)

        return None

    file_id = args['url']
    request = {
        'method': 'POST',
        'url': __api_url + '/download',
        'data': core.json.dumps({
            'file_id': file_id,
        }),
        'next': lambda r: download_request(r),
        'validate': validate_download_response,
    }

    __set_api_headers(core, service_name, request)

    return request
