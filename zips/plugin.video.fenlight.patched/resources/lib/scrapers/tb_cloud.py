# -*- coding: utf-8 -*-
# Thanks to kodifitzwell for allowing me to borrow his code
import re
from threading import Thread
from apis.torbox_api import TorBoxAPI
from modules import source_utils
from modules.utils import clean_file_name, normalize
from modules.settings import enabled_debrids_check, filter_by_name, torbox_usenet_search_enabled
# from modules.kodi_utils import logger


internal_results, check_title, clean_title, get_aliases_titles = source_utils.internal_results, source_utils.check_title, source_utils.clean_title, source_utils.get_aliases_titles
get_file_info, release_info_format, seas_ep_filter = source_utils.get_file_info, source_utils.release_info_format, source_utils.seas_ep_filter
TorBox = TorBoxAPI()
extensions = source_utils.supported_video_extensions()

class source:
	def __init__(self):
		self.scrape_provider = 'tb_cloud'
		self.sources = []

	def results(self, info):
		try:
			if not enabled_debrids_check('tb'): return internal_results(self.scrape_provider, self.sources)
			self.folder_results, self.scrape_results = [], []
			filter_title = filter_by_name(self.scrape_provider)
			self.media_type, title = info.get('media_type'), info.get('title')
			self.year, self.season, self.episode = int(info.get('year')), info.get('season'), info.get('episode')
			self.tmdb_id = info.get('tmdb_id')
			self.force_usenet_search = info.get('force_tb_usenet_search') in (True, 'true', 'True')
			self.search_title = clean_file_name(title).replace('&', 'and')
			self.aliases = get_aliases_titles(info.get('aliases', []))
			self.aliases += [i for i in self._alternate_search_titles(title) if not i in self.aliases]
			self.folder_query = clean_title(normalize(title))
			self._scrape_cloud()
			self._scrape_cloud_usenet()
			self._scrape_cloud_webdl()
			self._scrape_usenet_search()
			if not self.scrape_results: return internal_results(self.scrape_provider, self.sources)
			def _process():
				for item in self.scrape_results:
					try:
						file_name = normalize(item.get('short_name') or item.get('name') or '')
						if not file_name: continue
						if filter_title:
							if item.get('package'):
								if not self._title_matches_pack(file_name): continue
							elif not check_title(title, file_name, self.aliases, self.year, self.season, self.episode): continue
						display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
						direct_debrid_link = item.get('direct_debrid_link', False)
						source_label = ''
						if direct_debrid_link == 'usenet_search':
							is_pack = item.get('package') and not item.get('package') == 'episode'
							source_label = 'TB USENET SEARCH PACK' if is_pack else 'TB USENET SEARCH'
							file_dl = item['nzb']
							source_id = file_name
						else:
							file_dl = '%d,%d' % (int(item['folder_id']), item['id'])
							source_id = file_dl
							if direct_debrid_link == 'usenet': source_label = 'TB USENET CLOUD'
							elif direct_debrid_link == 'webdl': source_label = 'TB WEBDL CLOUD'
						if source_label: display_name = '[%s] %s' % (source_label, display_name)
						try: size_bytes = int(item.get('size') or 0)
						except: size_bytes = 0
						size = round(float(size_bytes)/1073741824, 2)
						size_label = '%.2f GB' % size
						if item.get('package_size'):
							try: size_label = 'PACK %.2f GB' % round(float(int(item['package_size']))/1073741824, 2)
							except: pass
						video_quality, details = get_file_info(name_info=release_info_format(file_name))
						if source_label: details = ' | '.join([i for i in (details, source_label) if i])
						source_item = {'name': file_name, 'display_name': display_name, 'quality': video_quality, 'size': size, 'size_label': size_label,
									'extraInfo': details, 'url_dl': file_dl, 'id': source_id, 'downloads': False, 'direct': True, 'source': self.scrape_provider,
									'scrape_provider': self.scrape_provider, 'direct_debrid_link': direct_debrid_link, 'hash': item.get('hash')}
						yield source_item
					except: pass
			self.sources = list(_process())
		except Exception as e:
			from modules.kodi_utils import logger
			logger('torbox scraper Exception', str(e))
		internal_results(self.scrape_provider, self.sources)
		return self.sources

	def _scrape_cloud(self):
		try:
			append = self.scrape_results.append
			year_query_list = self._year_query_list()
			try: my_cloud_files = TorBox.user_cloud()
			except: return self.sources
			for item in my_cloud_files['data']:
				if not item['download_finished']: continue
				if not self.folder_query in clean_title(normalize(item['name'])): continue
				folder_id = item['id']
				for file in item['files']:
					if not file['short_name'].endswith(tuple(extensions)): continue
					normalized = normalize(file['short_name'])
					folder_name = clean_title(normalized)
					if self.media_type == 'movie':
						if not any(x in normalized for x in year_query_list): continue
					elif not seas_ep_filter(self.season, self.episode, normalized): continue
					file['folder_id'] = folder_id
					append(file)
		except: return

	def _scrape_cloud_usenet(self):
		try:
			append = self.scrape_results.append
			year_query_list = self._year_query_list()
			try: my_cloud_files_usenet = TorBox.user_cloud_usenet()
			except: return self.sources
			for item in my_cloud_files_usenet['data']:
				if not item['download_finished']: continue
				if not self.folder_query in clean_title(normalize(item['name'])): continue
				folder_id = item['id']
				for file in item['files']:
					if not file['short_name'].endswith(tuple(extensions)): continue
					normalized = normalize(file['short_name'])
					folder_name = clean_title(normalized)
					if self.media_type == 'movie':
						if not any(x in normalized for x in year_query_list): continue
					elif not seas_ep_filter(self.season, self.episode, normalized): continue
					file['folder_id'] = folder_id
					file['direct_debrid_link'] = 'usenet'
					append(file)
		except: return

	def _scrape_cloud_webdl(self):
		try:
			append = self.scrape_results.append
			year_query_list = self._year_query_list()
			try: my_cloud_files_webdl = TorBox.user_cloud_webdl()
			except: return self.sources
			for item in my_cloud_files_webdl['data']:
				if not item['download_finished']: continue
				if not self.folder_query in clean_title(normalize(item['name'])): continue
				folder_id = item['id']
				for file in item['files']:
					file_name = file.get('short_name') or file.get('name') or ''
					if not file_name.endswith(tuple(extensions)): continue
					normalized = normalize(file_name)
					folder_name = clean_title(normalized)
					if self.media_type == 'movie':
						if not any(x in normalized for x in year_query_list): continue
					elif not seas_ep_filter(self.season, self.episode, normalized): continue
					file['short_name'] = file_name
					file['name'] = file_name
					file['folder_id'] = folder_id
					file['direct_debrid_link'] = 'webdl'
					append(file)
		except: return

	def _scrape_usenet_search(self):
		try:
			if not torbox_usenet_search_enabled(self.media_type, self.force_usenet_search): return
			append = self.scrape_results.append
			seen = set()
			for query in self._search_names():
				try: search_results = TorBox.search_usenet(query)
				except: continue
				nzbs = ((search_results or {}).get('data') or {}).get('nzbs') or []
				for item in nzbs:
					try:
						if not item.get('cached'): continue
						nzb_link = item.get('nzb')
						if not nzb_link or nzb_link in seen: continue
						file_name = item.get('raw_title') or item.get('title') or ''
						if not file_name: continue
						package = ''
						size = item.get('size', 0)
						package_size = 0
						if self.media_type == 'episode':
							package = self._episode_result_type(file_name)
							if not package: continue
							if package != 'episode':
								package_size = size
								size = 0
						seen.add(nzb_link)
						append({'name': file_name, 'short_name': file_name, 'size': size, 'nzb': nzb_link,
								'hash': item.get('hash'), 'direct_debrid_link': 'usenet_search', 'package': package, 'package_size': package_size})
					except: pass
		except: return

	def _search_names(self):
		if self.media_type == 'movie':
			queries = ['%s %d' % (title, self.year) for title in self._query_titles()]
		else:
			queries = []
			for title in self._query_titles():
				queries.extend(('%s S%02dE%02d' % (title, self.season, self.episode),
								'%s S%02d' % (title, self.season),
								'%s Season %d' % (title, self.season)))
		return [i for n, i in enumerate(queries) if i and not i in queries[:n]]

	def _query_titles(self):
		titles = [self.search_title]
		for title in self.aliases:
			title = clean_file_name(title).replace('&', 'and')
			if title and not title in titles: titles.append(title)
		return titles[:3]

	def _episode_result_type(self, file_name):
		if not self._title_matches_pack(file_name): return ''
		if seas_ep_filter(self.season, self.episode, file_name): return 'episode'
		if self._episode_in_range(file_name): return 'season'
		if self._has_wrong_single_episode(file_name): return ''
		if self._has_season_marker(file_name): return 'season'
		return ''

	def _title_matches_pack(self, file_name):
		stem = self._release_stem(file_name)
		if not stem: return False
		for title in self._query_titles():
			if stem == clean_title(normalize(title)): return True
		return False

	def _release_stem(self, file_name):
		release = '.%s.' % re.sub(r'[^a-z0-9]+', '.', normalize(file_name).lower()).strip('.')
		season, season_fill = str(self.season), str(self.season).zfill(2)
		split_markers = ('.s%s.' % season, '.s%s.' % season_fill, '.s%se' % season, '.s%se' % season_fill,
						'.season.%s.' % season, '.season%s.' % season,
						'.season.%s.' % season_fill, '.season%s.' % season_fill)
		for marker in split_markers:
			if marker in release:
				return clean_title(release.split(marker, 1)[0])
		return ''

	def _has_season_marker(self, file_name):
		release = '.%s.' % re.sub(r'[^a-z0-9]+', '.', normalize(file_name).lower()).strip('.')
		season, season_fill = str(self.season), str(self.season).zfill(2)
		return any(i in release for i in ('.s%s.' % season, '.s%s.' % season_fill,
										'.season.%s.' % season, '.season%s.' % season,
										'.season.%s.' % season_fill, '.season%s.' % season_fill))

	def _has_wrong_single_episode(self, file_name):
		release = re.sub(r'[^a-z0-9]+', '.', normalize(file_name).lower())
		season = str(self.season)
		episode, episode_fill = str(self.episode), str(self.episode).zfill(2)
		pattern = r'(?:^|\.)(?:s0?%s|season\.?0?%s)\.?e(?:p|pisode)?\.?0?(\d{1,3})(?:\.|$)' % (season, season)
		match = re.search(pattern, release)
		if not match: return False
		return match.group(1).lstrip('0') not in (episode, episode_fill.lstrip('0'))

	def _episode_in_range(self, file_name):
		release = re.sub(r'[^a-z0-9]+', '.', normalize(file_name).lower())
		season, episode = int(self.season), int(self.episode)
		range_patterns = (r's0?%d\.?e0?(\d{1,3})(?:\.?e0?|\.to\.e?0?)(\d{1,3})(?!p|bit|gb|\d)' % season,
							r's0?%d\.?e0?(\d{1,3})\.to\.e?0?(\d{1,3})(?!p|bit|gb|\d)' % season,
							r'season\.?0?%d\.?episode\.?0?(\d{1,3})\.?episode?\.?0?(\d{1,3})(?!p|bit|gb|\d)' % season)
		for pattern in range_patterns:
			match = re.search(pattern, release)
			if not match: continue
			start, end = int(match.group(1)), int(match.group(2))
			if start <= episode <= end: return True
		return False

	def _alternate_search_titles(self, title):
		title = title or ''
		candidates = []
		if ' - ' in title: candidates.append(title.split(' - ', 1)[1])
		if ':' in title: candidates.append(title.split(':', 1)[1])
		results = []
		for item in candidates:
			item = clean_file_name(item).replace('&', 'and').strip()
			if item and not item in results: results.append(item)
		return results

	def _year_query_list(self):
		return (str(self.year), str(self.year+1), str(self.year-1))
