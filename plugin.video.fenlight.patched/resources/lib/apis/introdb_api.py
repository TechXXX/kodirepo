# -*- coding: utf-8 -*-
import json
import time
import traceback

try:
	from urllib.parse import urlencode
	from urllib.request import Request, urlopen
	from urllib.error import HTTPError, URLError
except ImportError:
	from urllib import urlencode
	from urllib2 import Request, urlopen, HTTPError, URLError

from caches.settings_cache import get_setting
from modules import kodi_utils

logger = kodi_utils.logger

app_api_base = 'https://api.introdb.app'
org_api_base = 'https://api.theintrodb.org/v3'
empty_settings = ('', None, 'empty_setting')
request_timeout = 5
min_request_gap = 0.4
_last_request_time = 0.0
_episode_cache = {}


def _enabled(setting_id, default='false'):
	return get_setting('fenlight.%s' % setting_id, default) == 'true'


def introdb_enabled():
	return _enabled('introdb.enabled')


def introdb_debug():
	return _enabled('introdb.debug')


def _api_key():
	value = get_setting('fenlight.introdb.api_key', 'empty_setting')
	return '' if value in empty_settings else value.strip()


def _log(message, level='info', force=False):
	if force or introdb_debug():
		logger('Fen Light IntroDB', message)


def _to_number(value):
	try: return float(value)
	except: return None


def _clock_to_seconds(value):
	try:
		parts = [float(i) for i in str(value).strip().split(':')]
		if len(parts) == 2: return parts[0] * 60 + parts[1]
		if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
	except: pass
	return None


def _seconds_from_value(value, value_name=''):
	if value in empty_settings: return None
	if isinstance(value, str) and ':' in value:
		return _clock_to_seconds(value)
	number = _to_number(value)
	if number is None: return None
	if value_name.endswith('_ms'): return number / 1000.0
	if value_name in ('start', 'end') and number > 10000: return number / 1000.0
	return number


def _segment_time(segment, base_name):
	for key in ('%s_ms' % base_name, '%s_sec' % base_name, base_name):
		if key in segment:
			return _seconds_from_value(segment.get(key), key)
	return None


def _segment_score(segment):
	confidence = _to_number(segment.get('confidence'))
	if confidence is None: confidence = 0.5
	count = _to_number(segment.get('submission_count'))
	if count is None: count = 1.0
	return confidence + (count * 0.001)


def _normalize_imdb(imdb_id):
	if imdb_id in empty_settings: return None
	imdb_id = str(imdb_id).strip()
	return imdb_id if imdb_id.startswith('tt') else None


def _valid_tmdb(tmdb_id):
	try: return int(str(tmdb_id).strip()) > 0
	except: return False


def _episode_numbers(season, episode):
	try:
		season, episode = int(season), int(episode)
		if season <= 0 or episode <= 0: return None, None
		return season, episode
	except: return None, None


def _cache_key(tmdb_id, imdb_id, season, episode):
	return '%s:%s:%s:%s' % (tmdb_id or '', imdb_id or '', season or '', episode or '')


class IntroDBAPI:
	def __init__(self):
		self.api_key = _api_key()

	def query_episode_segments(self, meta):
		if not introdb_enabled(): return {}
		tmdb_id = meta.get('tmdb_id')
		imdb_id = _normalize_imdb(meta.get('imdb_id'))
		season, episode = _episode_numbers(meta.get('season'), meta.get('episode'))
		if not season or not episode:
			_log('missing season/episode; skipping lookup')
			return {}
		if not _valid_tmdb(tmdb_id) and not imdb_id:
			_log('missing TMDb/IMDb id; skipping lookup')
			return {}
		key = _cache_key(tmdb_id if _valid_tmdb(tmdb_id) else '', imdb_id, season, episode)
		if key in _episode_cache:
			return _episode_cache[key]
		requests = self._build_requests(tmdb_id, imdb_id, season, episode)
		if not requests: return {}
		result = {}
		source = ''
		for source, url, use_api_key in requests:
			data = self._request(url, source, use_api_key)
			result = self._parse_response(data)
			if result: break
		_episode_cache[key] = result
		if result:
			_log('segments found | source=%s | tmdb=%s | imdb=%s | season=%s | episode=%s | keys=%s' % (
				source, tmdb_id, imdb_id or '', season, episode, ','.join(sorted(result.keys()))), force=True)
		else:
			_log('no usable segments | tmdb=%s | imdb=%s | season=%s | episode=%s' % (
				tmdb_id, imdb_id or '', season, episode))
		return result

	def _build_requests(self, tmdb_id, imdb_id, season, episode):
		requests = []
		if imdb_id:
			app_params = {'imdb_id': imdb_id, 'season': season, 'episode': episode}
			requests.append(('introdb.app', '%s/segments?%s' % (app_api_base, urlencode(app_params)), False))
		params = {'season': season, 'episode': episode}
		if _valid_tmdb(tmdb_id): params['tmdb_id'] = str(tmdb_id).strip()
		elif imdb_id: params['imdb_id'] = imdb_id
		else: return requests
		requests.append(('theintrodb.org', '%s/media?%s' % (org_api_base, urlencode(params)), True))
		return requests

	def _request(self, url, source='', use_api_key=True):
		global _last_request_time
		try:
			gap = time.time() - _last_request_time
			if gap < min_request_gap: time.sleep(min_request_gap - gap)
			_last_request_time = time.time()
			request = Request(url)
			request.add_header('Accept', 'application/json')
			request.add_header('User-Agent', 'Fen Light Patched IntroDB/1.0')
			if use_api_key and self.api_key:
				request.add_header('Authorization', 'Bearer %s' % self.api_key)
			response = urlopen(request, timeout=request_timeout)
			body = response.read().decode('utf-8')
			if introdb_debug(): _log('%s response: %s' % (source or 'IntroDB', body[:500]))
			return json.loads(body)
		except HTTPError as error:
			if error.code == 404: _log('%s HTTP 404: episode not in IntroDB' % (source or 'IntroDB'))
			else: _log('%s HTTP %s during lookup' % (source or 'IntroDB', error.code))
		except URLError as error:
			_log('%s network error during lookup: %s' % (source or 'IntroDB', getattr(error, 'reason', error)))
		except:
			_log('%s lookup exception: %s' % (source or 'IntroDB', traceback.format_exc().strip()))
		return None

	def _parse_response(self, data):
		if not data or not isinstance(data, (dict, list)): return {}
		if isinstance(data, list): raw_segments = data
		else:
			if data.get('error'):
				_log('API error: %s' % data.get('error'), force=True)
				return {}
			raw_segments = []
			for segment_type in ('intro', 'recap', 'credits', 'outro', 'preview'):
				value = data.get(segment_type)
				if isinstance(value, dict): value = [value]
				for item in value or []:
					if isinstance(item, dict):
						item = dict(item)
						item['segment_type'] = item.get('segment_type') or item.get('type') or segment_type
						raw_segments.append(item)
			for item in data.get('segments', []) or []:
				if isinstance(item, dict): raw_segments.append(item)
		return self._normalize_segments(raw_segments)

	def _normalize_segments(self, raw_segments):
		segments = {'intro': [], 'recap': [], 'next_episode': []}
		for item in raw_segments:
			if not isinstance(item, dict): continue
			segment_type = str(item.get('segment_type') or item.get('type') or '').lower()
			if segment_type not in ('intro', 'recap', 'credits', 'outro', 'preview'): continue
			start = _segment_time(item, 'start')
			end = _segment_time(item, 'end')
			if segment_type in ('intro', 'recap'):
				if start is None: start = 0.0
				if end is None or end <= start: continue
				segments[segment_type].append({'type': segment_type, 'start': start, 'end': end, 'score': _segment_score(item)})
			else:
				if start is None or start <= 0: continue
				if end is not None and end <= start: continue
				segments['next_episode'].append({'type': segment_type, 'start': start, 'end': end, 'score': _segment_score(item)})
		result = {}
		for segment_type in ('intro', 'recap'):
			if segments[segment_type]:
				segments[segment_type].sort(key=lambda i: i['score'], reverse=True)
				result[segment_type] = segments[segment_type][0]
		if segments['next_episode']:
			segments['next_episode'].sort(key=lambda i: (i['start'], -i['score']))
			result['next_episode'] = segments['next_episode'][0]
		return result
