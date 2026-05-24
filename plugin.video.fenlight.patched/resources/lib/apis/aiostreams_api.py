# -*- coding: utf-8 -*-
import re
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from modules.kodi_utils import make_session, logger
from caches.settings_cache import get_setting

user_agent = 'AIOStreams/FenLight'
default_base_url = 'https://aiostreams.elfhosted.com'
timeout = 25.0
session = make_session(default_base_url)


class AIOStreamsAPI:
	def __init__(self, manifest_url=None):
		self.manifest_url = manifest_url or get_setting('fenlight.tb.usenet_search.aiostreams_manifest', 'empty_setting')
		self.stream_base = self._stream_base_from_manifest(self.manifest_url)

	def enabled(self):
		return bool(self.stream_base)

	def usenet_streams(self, media_type, imdb_id='', tmdb_id='', season=None, episode=None):
		try:
			if not self.enabled(): return []
			stremio_type, stremio_id = self._stremio_request_id(media_type, imdb_id, tmdb_id, season, episode)
			if not stremio_type or not stremio_id: return []
			url = '%s/stream/%s/%s.json' % (self.stream_base, stremio_type, quote(stremio_id, safe=':'))
			response = session.get(url, headers={'User-Agent': user_agent, 'Accept': 'application/json'}, timeout=timeout)
			data = response.json()
			streams = data.get('streams') or []
			return [i for i in (self._parse_stream(stream) for stream in streams) if i]
		except Exception as e:
			logger('Fen Light Patched', 'AIOStreams TorBox Usenet Search exception | %s' % str(e))
			return []

	def _stream_base_from_manifest(self, manifest_url):
		manifest_url = (manifest_url or '').strip()
		if manifest_url in ('', 'empty_setting'): return ''
		if manifest_url.startswith('stremio://'): manifest_url = 'https://%s' % manifest_url.split('://', 1)[1]
		elif manifest_url.startswith('://'): manifest_url = 'https%s' % manifest_url
		elif manifest_url.startswith('aiostreams.'): manifest_url = 'https://%s' % manifest_url
		elif re.match(r'^[0-9a-f-]{36}/[^/]+/?(?:manifest\.json)?$', manifest_url, re.I):
			manifest_url = '%s/stremio/%s' % (default_base_url, manifest_url)
		parts = urlsplit(manifest_url)
		if not parts.scheme or not parts.netloc: return ''
		path = parts.path.strip('/')
		if path.endswith('manifest.json'): path = path.rsplit('/', 1)[0]
		path_parts = path.split('/') if path else []
		try: stremio_index = path_parts.index('stremio')
		except ValueError: return ''
		if len(path_parts) < stremio_index + 3: return ''
		base_path = '/' + '/'.join(path_parts[:stremio_index + 3])
		return urlunsplit((parts.scheme, parts.netloc, base_path, '', '')).rstrip('/')

	def _stremio_request_id(self, media_type, imdb_id='', tmdb_id='', season=None, episode=None):
		imdb_id = (imdb_id or '').strip()
		tmdb_id = str(tmdb_id or '').strip()
		if re.match(r'^tt\d+$', imdb_id) and imdb_id != 'tt0000000': base_id = imdb_id
		elif tmdb_id: base_id = 'tmdb:%s' % tmdb_id
		else: return '', ''
		if media_type == 'movie': return 'movie', base_id
		if not season or not episode: return '', ''
		return 'series', '%s:%s:%s' % (base_id, int(season), int(episode))

	def _parse_stream(self, stream):
		stream_data = stream.get('streamData') or {}
		if not stream_data: return self._parse_stream_fallback(stream)
		service = stream_data.get('service') or {}
		if stream_data.get('type') != 'usenet': return None
		if service.get('id') != 'torbox' or service.get('cached') is not True: return None
		addon = stream_data.get('addon') or ''
		if addon and addon != 'TorBox Search': return None
		url = stream.get('url')
		if not url: return None
		behavior = stream.get('behaviorHints') or {}
		file_name = stream_data.get('filename') or behavior.get('filename') or stream_data.get('folderName') or self._fallback_name(stream)
		if not file_name: return None
		size = self._to_int(behavior.get('videoSize') or stream_data.get('size'))
		folder_size = self._to_int(behavior.get('folderSize') or stream_data.get('folderSize'))
		return {
			'name': file_name, 'short_name': file_name, 'size': size or folder_size or 0,
			'url': self._absolute_url(url), 'hash': stream.get('infoHash') or stream_data.get('nzbUrl') or '',
			'direct_debrid_link': 'aiostreams_usenet', 'package': '',
			'package_size': folder_size if folder_size and size and folder_size > size else 0,
			'indexer': stream_data.get('indexer'), 'age': stream_data.get('age')
		}

	def _parse_stream_fallback(self, stream):
		name = stream.get('name') or ''
		description = stream.get('description') or ''
		if 'TorBox Search' not in name or not name.startswith('[TB'): return None
		if '\u26a1' not in name or '\u23f3' in name: return None
		if 'Newznab' not in description and 'NZB' not in description.upper(): return None
		url = stream.get('url')
		if not url: return None
		behavior = stream.get('behaviorHints') or {}
		file_name = behavior.get('filename') or self._filename_from_description(description) or self._fallback_name(stream)
		if not file_name: return None
		size = self._to_int(behavior.get('videoSize'))
		return {
			'name': file_name, 'short_name': file_name, 'size': size,
			'url': self._absolute_url(url), 'hash': '',
			'direct_debrid_link': 'aiostreams_usenet', 'package': '', 'package_size': 0,
			'indexer': self._description_value(description, '\U0001f50d'), 'age': self._description_value(description, '\U0001f4c5')
		}

	def _absolute_url(self, url):
		if url.startswith(('http://', 'https://')): return url
		parts = urlsplit(self.stream_base)
		return urljoin('%s://%s' % (parts.scheme, parts.netloc), url)

	def _fallback_name(self, stream):
		description = stream.get('description') or ''
		for item in description.splitlines():
			item = item.strip()
			if item: return item
		return (stream.get('name') or '').strip()

	def _filename_from_description(self, description):
		return self._description_value(description, '\U0001f4c1')

	def _description_value(self, description, marker):
		try:
			if not marker in description: return ''
			value = description.split(marker, 1)[1].split('|', 1)[0].strip()
			return value
		except: return ''

	def _to_int(self, value):
		try: return int(float(value))
		except: return 0
