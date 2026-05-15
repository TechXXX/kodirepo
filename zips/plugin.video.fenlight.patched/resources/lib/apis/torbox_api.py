import requests
from threading import Thread
from urllib.parse import quote, urlencode
from caches.settings_cache import get_setting, set_setting
from caches.main_cache import cache_object
from modules.source_utils import supported_video_extensions, seas_ep_filter, EXTRAS
from modules.kodi_utils import make_session, kodi_dialog, ok_dialog, notification, confirm_dialog, sleep, logger

base_url = 'https://api.torbox.app/v1/api/'
search_base_url = 'https://search-api.torbox.app/'
stats = 'user/me'
download = 'torrents/requestdl'
remove = 'torrents/controltorrent'
history = 'torrents/mylist'
explore = 'torrents/mylist?id=%s'
cache = 'torrents/checkcached'
cloud = 'torrents/createtorrent'
cloud_usenet = 'usenet/createusenetdownload'
download_usenet = 'usenet/requestdl'
remove_usenet = 'usenet/controlusenetdownload'
history_usenet = 'usenet/mylist'
explore_usenet = 'usenet/mylist?id=%s'
search_usenet = 'usenet/search/%s'
download_webdl = 'webdl/requestdl'
remove_webdl = 'webdl/controlwebdownload'
history_webdl = 'webdl/mylist'
explore_webdl = 'webdl/mylist?id=%s'
user_agent = 'Mozilla/5.0'
timeout = 20.0
session = make_session(base_url)
search_session = make_session(search_base_url)

class TorBoxAPI:

	def __init__(self):
		self.token = get_setting('fenlight.tb.token')

	def _get(self, url, data={}):
		if self.token in ('empty_setting', ''): return None
		headers = {'Authorization': 'Bearer %s' % self.token}
		url = base_url + url
		response = session.get(url, params=data, headers=headers, timeout=timeout)
		return response.json()

	def _post(self, url, params=None, json=None, data=None):
		if self.token in ('empty_setting', '') and not 'token' in url: return None
		headers = {'Authorization': 'Bearer %s' % self.token}
		url = base_url + url
		response = session.post(url, params=params, json=json, data=data, headers=headers, timeout=timeout)
		return response.json()

	def _search_get(self, url, data={}):
		if self.token in ('empty_setting', ''): return None
		headers = {'Authorization': 'Bearer %s' % self.token, 'User-Agent': user_agent}
		url = search_base_url + url
		response = search_session.get(url, params=data, headers=headers, timeout=timeout)
		return response.json()

	def add_headers_to_url(self, url):
		return url + '|' + urlencode({'User-Agent': user_agent})

	def account_info(self):
		return self._get(stats)

	def user_cloud(self):
		string = 'tb_user_cloud'
		url = history
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_usenet(self):
		string = 'tb_user_cloud_usenet'
		url = history_usenet
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_webdl(self):
		string = 'tb_user_cloud_webdl'
		url = history_webdl
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_info(self, request_id=''):
		string = 'tb_user_cloud_%s' % request_id
		url = explore % request_id
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_info_usenet(self, request_id=''):
		string = 'tb_user_cloud_usenet_%s' % request_id
		url = explore_usenet % request_id
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_info_webdl(self, request_id=''):
		string = 'tb_user_cloud_webdl_%s' % request_id
		url = explore_webdl % request_id
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_clear(self):
		if not confirm_dialog(): return
		data = {'all': True, 'operation': 'delete'}
		self._post(remove, json=data)
		self._post(remove_usenet, json=data)
		self._post(remove_webdl, json=data)
		self.clear_cache()

	def torrent_info(self, request_id=''):
		url = explore % request_id
		return self._get(url)

	def delete_torrent(self, request_id=''):
		data = {'torrent_id': request_id, 'operation': 'delete'}
		return self._post(remove, json=data)

	def delete_usenet(self, request_id=''):
		data = {'usenet_id': request_id, 'operation': 'delete'}
		return self._post(remove_usenet, json=data)

	def delete_webdl(self, request_id=''):
		data = {'webdl_id': request_id, 'operation': 'delete'}
		return self._post(remove_webdl, json=data)

	def unrestrict_link(self, file_id):
		torrent_id, file_id = file_id.split(',')
		data = {'token': self.token, 'torrent_id': torrent_id, 'file_id': file_id}
		try: return self._get(download, data=data)['data']
		except: return None

	def unrestrict_usenet(self, file_id):
		usenet_id, file_id = file_id.split(',')
		params = {'token': self.token, 'usenet_id': usenet_id, 'file_id': file_id, 'user_ip': True}
		try: return self._get(download_usenet, data=params)['data']
		except: return None

	def unrestrict_webdl(self, file_id):
		web_id, file_id = file_id.split(',')
		params = {'token': self.token, 'web_id': web_id, 'file_id': file_id, 'user_ip': True}
		try: return self._get(download_webdl, data=params)['data']
		except: return None

	def add_magnet(self, magnet):
		data = {'magnet': magnet, 'seed': 3, 'allow_zip': False}
		return self._post(cloud, data=data)

	def add_usenet(self, link, name=''):
		data = {'link': link, 'post_processing': -1, 'as_queued': False, 'add_only_if_cached': True}
		if name: data['name'] = name
		return self._post(cloud_usenet, data=data)

	def search_usenet(self, query, metadata=False, check_cache=True, check_owned=True, search_user_engines=False, cached_only=True):
		data = {'metadata': metadata, 'check_cache': check_cache, 'check_owned': check_owned,
				'search_user_engines': search_user_engines, 'cached_only': cached_only}
		url = search_usenet % quote(query, safe='')
		string = 'tb_search_usenet_%s_%s_%s_%s_%s_%s' % (query, metadata, check_cache, check_owned, search_user_engines, cached_only)
		return cache_object(self._search_get, string, [url, data], False, 1)

	def check_cache_single(self, _hash):
		return self._get(cache, data={'hash': _hash, 'format': 'list'})

	def check_cache(self, hashlist):
		data = {'hashes': hashlist}
		return self._post(cache, params={'format': 'list'}, json=data)

	def create_transfer(self, magnet_url):
		result = self.add_magnet(magnet_url)
		if not result['success']: return ''
		return result['data'].get('torrent_id', '')

	def create_usenet_transfer(self, link, name=''):
		result = self.add_usenet(link, name)
		if not result or not result.get('success'): return ''
		data = result.get('data') or {}
		if isinstance(data, int): return data
		return data.get('usenet_id') or data.get('usenetdownload_id') or data.get('usenetdownloadId') or data.get('id') or ''

	def resolve_usenet_search(self, link, name, title, season, episode):
		try:
			file_url, usenet_id = None, None
			extensions = supported_video_extensions()
			extras_filtering_list = tuple(i for i in EXTRAS if not i in (title or '').lower())
			logger('Fen Light Patched', 'TorBox Usenet Search resolve start | name=%s | title=%s | season=%s | episode=%s' % (name, title, season, episode))
			usenet_id = self.create_usenet_transfer(link, name)
			if not usenet_id:
				logger('Fen Light Patched', 'TorBox Usenet Search resolve failed | reason=create_transfer | name=%s' % name)
				return None
			selected_files = self._usenet_transfer_video_files(usenet_id, extensions)
			logger('Fen Light Patched', 'TorBox Usenet Search transfer files | usenet_id=%s | count=%s | files=%s' % (
				usenet_id, len(selected_files), self._debug_usenet_files(selected_files)))
			if not selected_files:
				logger('Fen Light Patched', 'TorBox Usenet Search resolve failed | reason=no_video_files | usenet_id=%s' % usenet_id)
				return None
			if season:
				pre_filter_count = len(selected_files)
				selected_files = [i for i in selected_files if seas_ep_filter(season, episode, i['filename'])]
				if not selected_files:
					logger('Fen Light Patched', 'TorBox Usenet Search resolve failed | reason=episode_filter | usenet_id=%s | before=%s | target=S%02dE%02d' % (
						usenet_id, pre_filter_count, int(season), int(episode)))
			else:
				if self._m2ts_check(selected_files):
					logger('Fen Light Patched', 'TorBox Usenet Search resolve failed | reason=m2ts_folder | usenet_id=%s' % usenet_id)
					return None
				selected_files = [i for i in selected_files if not any(x in i['filename'] for x in extras_filtering_list)]
				selected_files.sort(key=lambda k: k['size'], reverse=True)
			if not selected_files: return None
			chosen_file = selected_files[0]
			logger('Fen Light Patched', 'TorBox Usenet Search selected file | usenet_id=%s | filename=%s | size=%s' % (
				usenet_id, chosen_file.get('filename'), chosen_file.get('size')))
			file_key = chosen_file['url']
			file_url = self.unrestrict_usenet(file_key)
			logger('Fen Light Patched', 'TorBox Usenet Search requestdl | usenet_id=%s | success=%s' % (usenet_id, bool(file_url)))
			if not int(get_setting('fenlight.store_resolved_to_cloud.torbox', '0')) == 1:
				Thread(target=self.delete_usenet, args=(usenet_id,)).start()
			return file_url
		except Exception as e:
			logger('Fen Light Patched', 'TorBox Usenet Search resolve exception | usenet_id=%s | error=%s' % (usenet_id, str(e)))
			if usenet_id: self.delete_usenet(usenet_id)
			return None

	def _debug_usenet_files(self, selected_files):
		return ' / '.join(['%s (%s)' % (i.get('filename', '')[:120], i.get('size')) for i in selected_files[:5]])

	def _usenet_transfer_video_files(self, usenet_id, extensions):
		for _ in range(8):
			try:
				transfer = self._get(explore_usenet % usenet_id, data={'bypass_cache': True})
				files = (transfer.get('data') or {}).get('files') or []
				selected_files = []
				for item in files:
					filename = item.get('short_name') or item.get('name') or ''
					if not filename.lower().endswith(tuple(extensions)): continue
					selected_files.append({'url': '%d,%d' % (int(usenet_id), item['id']), 'filename': filename, 'size': item['size']})
				if selected_files: return selected_files
			except: pass
			sleep(1000)
		return []

	def resolve_magnet(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		try:
			file_url, match, torrent_id = None, False, None
			extensions = supported_video_extensions()
			extras_filtering_list = tuple(i for i in EXTRAS if not i in title.lower())
			torrent = self.add_magnet(magnet_url)
			if not torrent['success']: return None
			torrent_id = torrent['data']['torrent_id']
			torrent_files = self.torrent_info(torrent_id)
			selected_files = [{'url': '%d,%d' % (torrent_id, item['id']), 'filename': item['short_name'], 'size': item['size']} \
							for item in torrent_files['data']['files'] if item['short_name'].lower().endswith(tuple(extensions))]
			if not selected_files: return None
			if season:
				selected_files = [i for i in selected_files if seas_ep_filter(season, episode, i['filename'])]
			else:
				if self._m2ts_check(selected_files): return None
				selected_files = [i for i in selected_files if not any(x in i['filename'] for x in extras_filtering_list)]
				selected_files.sort(key=lambda k: k['size'], reverse=True)
			if not selected_files: return None
			file_key = selected_files[0]['url']
			file_url = self.unrestrict_link(file_key)
			if not store_to_cloud: Thread(target=self.delete_torrent, args=(torrent_id,)).start()
			return file_url
		except:
			if torrent_id: self.delete_torrent(torrent_id)
			return None

	def display_magnet_pack(self, magnet_url, info_hash):
		from modules.source_utils import supported_video_extensions
		try:
			torrent_id = None
			extensions = supported_video_extensions()
			torrent = self.add_magnet(magnet_url)
			if not torrent['success']: return None
			torrent_id = torrent['data']['torrent_id']
			torrent_files = self.torrent_info(torrent_id)
			torrent_files = [{'link': '%d,%d' % (torrent_id, item['id']), 'filename': item['short_name'], 'size': item['size']} \
							for item in torrent_files['data']['files'] if item['short_name'].lower().endswith(tuple(extensions))]
			Thread(target=self.delete_torrent, args=(torrent_id,)).start()
			return torrent_files or None
		except Exception:
			if torrent_id: self.delete_torrent(torrent_id)
			return None

	def _m2ts_check(self, folder_items):
		for item in folder_items:
			if item['filename'].endswith('.m2ts'): return True
		return False

	def auth(self):
		api_key = kodi_dialog().input('TorBox API Key:')
		if not api_key: return
		try:
			self.token = api_key
			r = self.account_info()
			customer = r['data']['customer']
			set_setting('tb.token', api_key)
			set_setting('tb.enabled', 'true')
			message = 'Success'
		except: message = 'An Error Occurred'
		ok_dialog(text=message)

	def revoke(self):
		if not confirm_dialog(): return
		set_setting('tb.token', 'empty_setting')
		set_setting('tb.enabled', 'false')
		notification('TorBox Authorization Reset', 3000)

	def clear_cache(self, clear_hashes=True):
		try:
			from caches.debrid_cache import debrid_cache
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			# USER CLOUD
			try:
				dbcon.execute("""DELETE FROM maincache WHERE id=?""", ('tb_user_cloud',))
				dbcon.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('tb_user_cloud%',))
				dbcon.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('tb_search_usenet_%',))
				user_cloud_success = True
			except: user_cloud_success = False
			# HASH CACHED STATUS
			if clear_hashes:
				try:
					debrid_cache.clear_debrid_results('tb')
					hash_cache_status_success = True
				except: hash_cache_status_success = False
			else: hash_cache_status_success = True
		except: return False
		if False in (user_cloud_success, hash_cache_status_success): return False
		return True
