# -*- coding: utf-8 -*-

import requests
import urllib3
import re
import time
import ssl
import traceback
from .kodi import get_int_setting
from . import logger
from requests import adapters
from .third_party.cloudscraper import cloudscraper

__search_label_prop = 'a4k.search_label'

def __search_param(params, *names):
    for name in names:
        value = params.get(name, '')
        if value not in (None, ''):
            return str(value).strip()
    return ''

def __format_season_episode(params):
    season = __search_param(params, 'season_number', 'season')
    episode = __search_param(params, 'episode_number', 'episode')
    if not season or not episode:
        return ''

    try:
        return 'S%.2dE%.2d' % (int(season), int(episode))
    except:
        return 'S%sE%s' % (season, episode)

def __format_search_label(request):
    params = request.get('params', {})
    if not isinstance(params, dict):
        return ''

    label = __search_param(params, 'query', 'q', 'keywords', 'film_name', 'file_name')
    details = []

    season_episode = __format_season_episode(params)
    if season_episode and season_episode not in label:
        details.append(season_episode)

    detail_keys = (
        ('parent_tmdb_id', 'parent_tmdb_id'),
        ('parent_imdb_id', 'parent_imdb_id'),
        ('tmdb_id', 'tmdb_id'),
        ('imdb_id', 'imdb_id'),
        ('movieId', 'movieId'),
        ('moviehash', 'moviehash'),
        ('year', 'year'),
    )

    for key, display_key in detail_keys:
        value = __search_param(params, key)
        if not value:
            continue
        if label and key == 'year' and value in label:
            continue
        details.append('%s=%s' % (display_key, value))

    if not label:
        return ', '.join(details)
    if not details:
        return label
    return '%s (%s)' % (label, ', '.join(details))

def __publish_search_label(core, request):
    search_label = __format_search_label(request)
    if search_label:
        try:
            core.kodi.set_property(__search_label_prop, search_label)
        except:
            pass

class TLSAdapter(adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        self.poolmanager = urllib3.poolmanager.PoolManager(num_pools=connections,
                                                           maxsize=maxsize,
                                                           block=block,
                                                           ssl_version=ssl.PROTOCOL_TLSv1_2,
                                                           ssl_context=ctx)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def __retry(core, request, response, next, cfscrape, retry=0):
    if retry > 5:
        return None

    if response.status_code in [502, 503, 429, 409, 403]:
        if response.status_code in [503, 403]:
            retry = 5
        else:
            core.time.sleep(3)

        retry += 1
        request['validate'] = lambda response: __retry(core, request, response, next, cfscrape, retry)
        request['next'] = next
        request['cfscrape'] = cfscrape
        return request

def execute(core, request, progress=True, session=None):
    try: default_timeout = get_int_setting('general.timeout')
    except: default_timeout = 10
    request.setdefault('timeout', default_timeout)

    if progress and core.progress_dialog and not core.progress_dialog.dialog:
        core.progress_dialog.open()

    next = request.pop('next', None)
    error = request.pop('error', None)

    cfscrape = 'cfscrape' in request
    request.pop('cfscrape', None)

    validate = request.pop('validate', None)
    if not validate:
        validate = lambda response: __retry(core, request, response, next, cfscrape)

    if next:
        request.pop('stream', None)

    __publish_search_label(core, request)
    logger.debug('%s ^ - %s, %s' % (request['method'], request['url'], core.json.dumps(request.get('params', {}))))
    try:
        if cfscrape:
            request.pop('cfscrape', None)
            if not session:
                session = cloudscraper.create_scraper(interpreter='native')
            response = session.request(**request)
        else:
            session = requests.session()
            session.mount('https://', TLSAdapter())
            response = session.request(**request)
        exc = ''
    except:  # pragma: no cover
        if cfscrape:
            try:
                if not session:
                    session = cloudscraper.create_scraper(interpreter='native')
                response = session.request(verify=False, **request)
                exc = ''
            except:  # pragma: no cover
                exc = traceback.format_exc()
                response = lambda: None
                response.text = ''
                response.content = ''
                response.status_code = 500
        else:
            exc = traceback.format_exc()
            response = lambda: None
            response.text = ''
            response.content = ''
            response.status_code = 500
    logger.debug('%s $ - %s - %s, %s' % (request['method'], request['url'], response.status_code, exc))

    alt_request = validate(response)
    if alt_request:
        return execute(core, alt_request, progress)

    if next and response.status_code == 200:
        next_request = next(response)
        if next_request:
            return execute(core, next_request, progress, session)
        else:
            return None

    if error and response.status_code >= 400:
        next_request = error(response)
        if next_request:
            return execute(core, next_request, progress, session)
        else:
            return None

    return response
