# -*- coding: utf-8 -*-
import json
import re
import time
import traceback
from difflib import SequenceMatcher
from threading import Thread
import itertools
from windows.base_window import open_window, create_window
from caches.episode_groups_cache import episode_groups_cache
from caches.settings_cache import get_setting
from scrapers import external, folders
from modules import debrid, kodi_utils, settings, metadata, watched_status
from modules.player import FenLightPlayer
from modules.source_utils import get_cache_expiry, make_alias_dict
from modules.utils import clean_file_name, string_to_float, safe_string, remove_accents, get_datetime, append_module_to_syspath, manual_function_import, manual_module_import
logger = kodi_utils.logger

get_icon, notification, sleep, xbmc_monitor = kodi_utils.get_icon, kodi_utils.notification, kodi_utils.sleep, kodi_utils.xbmc_monitor
select_dialog, confirm_dialog, close_all_dialog = kodi_utils.select_dialog, kodi_utils.confirm_dialog, kodi_utils.close_all_dialog
show_busy_dialog, hide_busy_dialog, xbmc_player = kodi_utils.show_busy_dialog, kodi_utils.hide_busy_dialog, kodi_utils.xbmc_player
get_property, set_property, clear_property = kodi_utils.get_property, kodi_utils.set_property, kodi_utils.clear_property
jsonrpc_get_system_setting = kodi_utils.jsonrpc_get_system_setting
auto_play, active_internal_scrapers, provider_sort_ranks, audio_filters = settings.auto_play, settings.active_internal_scrapers, settings.provider_sort_ranks, settings.audio_filters
check_prescrape_sources, external_scraper_info, auto_resume = settings.check_prescrape_sources, settings.external_scraper_info, settings.auto_resume
store_resolved_to_cloud, source_folders_directory, watched_indicators = settings.store_resolved_to_cloud, settings.source_folders_directory, settings.watched_indicators
quality_filter, sort_to_top, tmdb_api_key, mpaa_region = settings.quality_filter, settings.sort_to_top, settings.tmdb_api_key, settings.mpaa_region
scraping_settings, include_prerelease_results, auto_rescrape_with_all = settings.scraping_settings, settings.include_prerelease_results, settings.auto_rescrape_with_all
ignore_results_filter, results_sort_order, results_format, filter_status = settings.ignore_results_filter, settings.results_sort_order, settings.results_format, settings.filter_status
autoplay_next_episode, autoscrape_next_episode, limit_resolve = settings.autoplay_next_episode, settings.autoscrape_next_episode, settings.limit_resolve
auto_episode_group, preferred_autoplay, debrid_enabled = settings.auto_episode_group, settings.preferred_autoplay, debrid.debrid_enabled
get_progress_status_movie, get_bookmarks_movie, erase_bookmark = watched_status.get_progress_status_movie, watched_status.get_bookmarks_movie, watched_status.erase_bookmark
get_progress_status_episode, get_bookmarks_episode = watched_status.get_progress_status_episode, watched_status.get_bookmarks_episode
internal_include_list = ['easynews', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud']
external_exclude_list = ['easynews', 'gdrive', 'library', 'filepursuit', 'plexshare']
sd_check = ('SD', 'CAM', 'TELE', 'SYNC')
rd_info, pm_info, ad_info = ('apis.real_debrid_api', 'RealDebridAPI'), ('apis.premiumize_api', 'PremiumizeAPI'), ('apis.alldebrid_api', 'AllDebridAPI')
oc_info, ed_info, tb_info = ('apis.offcloud_api', 'OffcloudAPI'), ('apis.easydebrid_api', 'EasyDebridAPI'), ('apis.torbox_api', 'TorBoxAPI')
debrids = {'Real-Debrid': rd_info, 'rd_cloud': rd_info, 'rd_browse': rd_info, 'Premiumize.me': pm_info, 'pm_cloud': pm_info, 'pm_browse': pm_info,
			'AllDebrid': ad_info, 'ad_cloud': ad_info, 'ad_browse': ad_info, 'Offcloud': oc_info, 'oc_cloud': oc_info, 'oc_browse': oc_info,
			'EasyDebrid': ed_info, 'ed_cloud': ed_info, 'ed_browse': ed_info, 'TorBox': tb_info, 'tb_cloud': tb_info, 'tb_browse': tb_info}
debrid_providers = ('Real-Debrid', 'Premiumize.me', 'AllDebrid', 'Offcloud', 'EasyDebrid', 'TorBox')
debrid_token_dict = {'Real-Debrid': 'rd.token', 'Premiumize.me': 'pm.token', 'AllDebrid': 'ad.token', 'Offcloud': 'oc.token', 'EasyDebrid': 'ed.token', 'TorBox': 'tb.token'}
quality_ranks = {'4K': 1, '1080p': 2, '720p': 3, 'SD': 4, 'SCR': 5, 'CAM': 5, 'TELE': 5}
cloud_scrapers, folder_scrapers = ('rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud'), ('folder1', 'folder2', 'folder3', 'folder4', 'folder5')
default_internal_scrapers = ('easynews', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud', 'folders')
main_line = '%s[CR]%s[CR]%s'
int_window_prop = 'fenlight.internal_results.%s'
scraper_timeout = 25
a4k_subtitles_addon_path = 'special://home/addons/service.subtitles.a4ksubtitles.patched'
subtitle_autoplay_probe_limit = 50
release_group_stopwords = {'proper', 'repack', 'rerip', 'internal', 'multi', 'dubbed', 'subbed', 'readnfo', 'limited', 'extended', 'remux', 'hybrid', 'hdr', 'dv', 'uhd'}
release_group_suffix_stopwords = {'eztv', 'eztvx', 'eztvx.to', 'ettv', 'tgx', 'torrentgalaxy', 'v2', 'v3', 'v4'}
release_group_domain_stopwords = {'to', 'com', 'org', 'net', 'cc', 'io', 'me'}
release_group_extension_stopwords = {'mkv', 'mp4', 'avi', 'ts', 'm2ts', 'srt', 'sub', 'ass', 'ssa'}
release_family_groups = (
	('bluray', {'bluray', 'bd', 'bdrip', 'brrip', 'bdmv', 'bdscr', 'remux', 'bdremux', 'uhdremux', 'uhdbdremux', 'uhdbluray'}),
	('web', {'web', 'webdl', 'webrip', 'webr', 'webdlrip', 'webcap'}),
	('dvd', {'dvd', 'dvd5', 'dvd9', 'dvdr', 'dvdrip', 'dvdscr'}),
	('prerelease', {'scr', 'screener', 'r5', 'r6', 'cam', 'camrip', 'hdcam', 'tele', 'telesync', 'ts'}),
)
quality_family_groups = (
	('2160p', {'4k', '2160p', '2160', '4kuhd', '4kultrahd', 'ultrahd', 'uhd'}),
	('1080p', {'1080p', '1080'}),
	('720p', {'720p', '720'}),
	('480p', {'480p'}),
	('low', {'360p', '240p', '144p'}),
)
service_family_groups = (
	('netflix', {'netflix', 'nflx', 'nf'}),
	('amazon', {'amazon', 'amzn', 'primevideo'}),
	('hulu', {'hulu', 'hlu'}),
	('crunchyroll', {'crunchyroll', 'cr'}),
	('disney', {'disney', 'disneyplus'}),
	('hbo', {'hbo', 'hbonow', 'hbogo', 'hbomax', 'hmax'}),
	('bbc', {'bbc'}),
	('sky', {'sky', 'skyq'}),
	('syfy', {'syfy'}),
	('atvp', {'atvp', 'atvplus'}),
	('pcok', {'pcok', 'peacock'}),
)
codec_family_groups = (
	('h264', {'x264', 'h264', '264', 'avc'}),
	('h265', {'x265', 'h265', '265', 'hevc'}),
	('modern', {'av1', 'vp9', 'vp8', 'divx', 'xvid'}),
)
audio_family_groups = (
	('dts', {'dts', 'dtshd', 'atmos', 'truehd'}),
	('aac', {'aac', 'ac'}),
	('dd', {'dd', 'ddp', 'ddp5', 'dd5', 'dd2', 'dd1', 'dd7', 'ddp7'}),
)
color_family_groups = (
	('hdr', {'hdr', '10bit', '12bit', 'hdr10', 'hdr10plus', 'dolbyvision', 'dolby', 'vision'}),
	('sdr', {'sdr', '8bit'}),
)
release_group_metadata_stopwords = set().union(
	release_group_stopwords, release_group_suffix_stopwords, release_group_domain_stopwords, release_group_extension_stopwords,
	{i for _, group in release_family_groups for i in group},
	{i for _, group in quality_family_groups for i in group},
	{i for _, group in service_family_groups for i in group},
	{i for _, group in codec_family_groups for i in group},
	{i for _, group in audio_family_groups for i in group},
	{i for _, group in color_family_groups for i in group},
	{'sub', 'subs', 'subtitle', 'multi', 'multiple'}
)
filter_keys = {'hevc': '[B]HEVC[/B]', '3d': '[B]3D[/B]', 'hdr': '[B]HDR[/B]', 'dv': '[B]D/VISION[/B]', 'av1': '[B]AV1[/B]', 'enhanced_upscaled': '[B]AI ENHANCED/UPSCALED[/B]'}
preference_values = {0:100, 1:50, 2:20, 3:10, 4:5, 5:2}

class Sources():
	def __init__(self):
		self.params = {}
		self.prescrape_scrapers, self.prescrape_threads, self.prescrape_sources, self.uncached_results = [], [], [], []
		self.threads, self.providers, self.sources, self.internal_scraper_names, self.remove_scrapers = [], [], [], [], ['external']
		self.rescrape_with_all, self.rescrape_with_episode_group = False, False
		self.clear_properties, self.filters_ignored, self.active_folders, self.resolve_dialog_made, self.episode_group_used = True, False, False, False, False
		self.sources_total = self.sources_4k = self.sources_1080p = self.sources_720p = self.sources_sd = 0
		self.prescrape, self.disabled_ext_ignored, self.default_ext_only = 'true', 'false', 'false'
		self.ext_name, self.ext_folder, self.provider_defaults, self.ext_sources = '', '', [], None
		self.progress_dialog, self.progress_thread = None, None
		self.playing_filename = ''
		self.a4k_subtitles_api, self.a4k_subtitles_checked, self.subtitle_probe_cache = None, False, {}
		self.count_tuple = (('sources_4k', '4K', self._quality_length), ('sources_1080p', '1080p', self._quality_length), ('sources_720p', '720p', self._quality_length),
							('sources_sd', '', self._quality_length_sd), ('sources_total', '', self._quality_length_final))

	def playback_prep(self, params=None):
		hide_busy_dialog()
		if params: self.params = params
		params_get = self.params.get
		self.play_type, self.background, self.prescrape = params_get('play_type', ''), params_get('background', 'false') == 'true', params_get('prescrape', self.prescrape) == 'true'
		self.random, self.random_continual = params_get('random', 'false') == 'true', params_get('random_continual', 'false') == 'true'
		if self.play_type:
			if self.play_type == 'autoplay_nextep': self.autoplay_nextep, self.autoscrape_nextep = True, False
			elif self.play_type == 'random_continual': self.autoplay_nextep, self.autoscrape_nextep = False, False
			else: self.autoplay_nextep, self.autoscrape_nextep = False, True
		else: self.autoplay_nextep, self.autoscrape_nextep = autoplay_next_episode(), autoscrape_next_episode()
		self.autoscrape = self.autoscrape_nextep and self.background
		self.auto_rescrape_with_all, self.auto_episode_group = auto_rescrape_with_all(), auto_episode_group()
		self.nextep_settings, self.disable_autoplay_next_episode = params_get('nextep_settings', {}), params_get('disable_autoplay_next_episode', 'false') == 'true'
		self.ignore_scrape_filters = params_get('ignore_scrape_filters', 'false') == 'true'
		self.disabled_ext_ignored = params_get('disabled_ext_ignored', self.disabled_ext_ignored) == 'true'
		self.default_ext_only = params_get('default_ext_only', self.default_ext_only) == 'true'
		self.folders_ignore_filters = get_setting('fenlight.results.folders_ignore_filters', 'false') == 'true'
		self.filter_size_method = int(get_setting('fenlight.results.filter_size_method', '0'))
		self.media_type, self.tmdb_id = params_get('media_type'), params_get('tmdb_id')		
		self.custom_title, self.custom_year = params_get('custom_title', None), params_get('custom_year', None)
		self.episode_group_label = params_get('episode_group_label', '')
		if self.media_type == 'episode':
			self.season, self.episode = int(params_get('season')), int(params_get('episode'))
			self.custom_season, self.custom_episode = params_get('custom_season', None), params_get('custom_episode', None)
			self.check_episode_group()
		else: self.season, self.episode, self.custom_season, self.custom_episode = '', '', '', ''
		if 'autoplay' in self.params: self.autoplay = params_get('autoplay', 'false') == 'true'
		else: self.autoplay = auto_play(self.media_type)
		self.get_meta()
		self.determine_scrapers_status()
		self.sleep_time, self.provider_sort_ranks, self.scraper_settings = 100, provider_sort_ranks(), scraping_settings()
		self.include_prerelease_results, self.ignore_results_filter, self.limit_resolve = include_prerelease_results(), ignore_results_filter(), limit_resolve()
		self.sort_function, self.quality_filter = results_sort_order(), self._quality_filter()
		self.include_unknown_size = get_setting('fenlight.results.size_unknown', 'false') == 'true'
		self.make_search_info()
		if self.autoscrape: self.autoscrape_nextep_handler()
		else: return self.get_sources()

	def check_episode_group(self):
		try:
			if any([self.custom_season, self.custom_episode]) or 'skip_episode_group_check' in self.params: return
			group_info = episode_groups_cache.get(self.tmdb_id)
			if not group_info: return
			group_details = metadata.group_episode_data(metadata.group_details(group_info['id']), None, self.season, self.episode)
			if group_details:
				self.custom_season, self.custom_episode, self.episode_group_used = group_details['season'], group_details['episode'], True
				self.episode_group_label = '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (self.custom_season, self.custom_episode)
		except: self.custom_season, self.custom_episode = None, None

	def determine_scrapers_status(self):
		self.active_internal_scrapers = active_internal_scrapers()
		if not 'external' in self.active_internal_scrapers and (self.disabled_ext_ignored or self.default_ext_only): self.active_internal_scrapers.append('external')
		self.active_external = 'external' in self.active_internal_scrapers
		if self.active_external:
			self.debrid_enabled = debrid_enabled()
			if not self.debrid_enabled: return self.disable_external('No Debrid Services Enabled')
			self.ext_folder, self.ext_name = external_scraper_info()
			if not self.ext_folder or not self.ext_name: return self.disable_external('Error Importing External Module')

	def get_sources(self):
		if not self.progress_dialog and not self.background: self._make_progress_dialog()
		results = []
		if self.prescrape and any(x in self.active_internal_scrapers for x in default_internal_scrapers):
			if self.prepare_internal_scrapers():
				results = self.collect_prescrape_results()
				if results: results = self.process_results(results)
		if not results:
			self.prescrape = False
			self.prepare_internal_scrapers()
			if self.active_external: self.activate_external_providers()
			elif not self.active_internal_scrapers: self._kill_progress_dialog()
			self.orig_results = self.collect_results()
			if not self.orig_results and not self.active_external: self._kill_progress_dialog()
			results = self.process_results(self.orig_results)
		if not results: return self._process_post_results()
		if self.autoscrape: return results
		else: return self.play_source(results)

	def collect_results(self):
		self.sources.extend(self.prescrape_sources)
		threads_append = self.threads.append
		if self.active_folders: self.append_folder_scrapers(self.providers)
		self.providers.extend(self.internal_sources())
		if self.providers:
			for i in self.providers: threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], False), name=i[2]))
			[i.start() for i in self.threads]
		if self.active_external or self.background:
			if self.active_external:
				if any((i[0] == 'comet' for i in self.external_providers)):
					debrid_service = self.debrid_enabled[0]
					debrid_token = get_setting('fenlight.%s' % debrid_token_dict[debrid_service])
				else: debrid_service, debrid_token = '', ''
				self.external_args = (self.meta, self.external_providers, self.debrid_enabled, debrid_service, debrid_token, self.internal_scraper_names,
										self.prescrape_sources, self.progress_dialog, self.disabled_ext_ignored)
				self.activate_providers('external', external, False)
			if self.background: [i.join() for i in self.threads]
		elif self.active_internal_scrapers: self.scrapers_dialog()
		return self.sources

	def collect_prescrape_results(self):
		threads_append = self.prescrape_threads.append
		if self.active_folders:
			if self.autoplay or check_prescrape_sources('folders', self.media_type):
				self.append_folder_scrapers(self.prescrape_scrapers)
				self.remove_scrapers.append('folders')
		self.prescrape_scrapers.extend(self.internal_sources(True))
		if not self.prescrape_scrapers: return []
		for i in self.prescrape_scrapers: threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], True), name=i[2]))
		[i.start() for i in self.prescrape_threads]
		self.remove_scrapers.extend(i[2] for i in self.prescrape_scrapers)
		if self.background: [i.join() for i in self.prescrape_threads]
		else: self.scrapers_dialog()
		return self.prescrape_sources

	def process_results(self, results):
		if self.prescrape: self.all_scrapers = self.active_internal_scrapers
		else:
			self.all_scrapers = list(set(self.active_internal_scrapers + self.remove_scrapers))
			clear_property('fs_filterless_search')
		self.uncached_results = self.sort_results([i for i in results if 'Uncached' in i.get('cache_provider', '')])
		results = [i for i in results if not i in self.uncached_results]
		if self.ignore_scrape_filters:
			self.filters_ignored = True
			results = self.sort_results(results)
		else:
			results = self.sort_results(results)
			results = self.filter_results(results)
			results = self.filter_audio(results)
			for file_type in filter_keys: results = self.special_filter(results, file_type)
		results = self.sort_preferred_autoplay(results)
		results = self.sort_first(results)
		results = self.sort_subtitle_ready_autoplay(results)
		return results

	def sort_results(self, results):
		for item in results:
			provider = item['scrape_provider']
			if provider == 'external': account_type = item['debrid'].lower()
			else: account_type = provider.lower()
			item['provider_rank'] = self._get_provider_rank(account_type)
			item['quality_rank'] = self._get_quality_rank(item.get('quality', 'SD'))
		results.sort(key=self.sort_function)
		results = self._sort_uncached_results(results)
		return results

	def filter_results(self, results):
		if self.folders_ignore_filters:
			folder_results = [i for i in results if i['scrape_provider'] == 'folders']
			results = [i for i in results if not i in folder_results]
		else: folder_results = []
		results = [i for i in results if i['quality'] in self.quality_filter]
		if self.filter_size_method:
			min_size = string_to_float(get_setting('fenlight.results.%s_size_min' % self.media_type, '0'), '0') / 1000
			if min_size == 0.0 and not self.include_unknown_size: min_size = 0.02
			if self.filter_size_method == 1:
				duration = self.meta['duration'] or (5400 if self.media_type == 'movie' else 2400)
				max_size = ((0.125 * (0.90 * string_to_float(get_setting('results.line_speed', '25'), '25'))) * duration)/1000
			elif self.filter_size_method == 2:
				max_size = string_to_float(get_setting('fenlight.results.%s_size_max' % self.media_type, '10000'), '10000') / 1000
			results = [i for i in results if i['scrape_provider'] == 'folders' or min_size <= i['size'] <= max_size]
		results += folder_results
		return results

	def filter_audio(self, results):
		return [i for i in results if not any(x in i['extraInfo'] for x in audio_filters())]

	def special_filter(self, results, file_type):
		enable_setting, key = filter_status(file_type), filter_keys[file_type]
		if key == '[B]HEVC[/B]' and enable_setting == 0:
			hevc_max_quality = self._get_quality_rank(get_setting('fenlight.filter.hevc.%s' % ('max_autoplay_quality' if self.autoplay else 'max_quality'), '4K'))
			results = [i for i in results if not key in i['extraInfo'] or i['quality_rank'] >= hevc_max_quality]
		if enable_setting == 1:
			if key == '[B]D/VISION[/B]' and filter_status('hdr') == 0:
				results = [i for i in results if all(x in i['extraInfo'] for x in (key, '[B]HDR[/B]')) or not key in i['extraInfo']]
			else: results = [i for i in results if not key in i['extraInfo']]
		return results

	def sort_first(self, results):
		try:
			sort_first_scrapers = []
			if 'folders' in self.all_scrapers and sort_to_top('folders'): sort_first_scrapers.append('folders')
			sort_first_scrapers.extend([i for i in self.all_scrapers if i in cloud_scrapers and sort_to_top(i)])
			if not sort_first_scrapers: return results
			sort_first = [i for i in results if i['scrape_provider'] in sort_first_scrapers]
			sort_first.sort(key=lambda k: (self._sort_folder_to_top(k['scrape_provider']), k['quality_rank']))
			sort_last = [i for i in results if not i in sort_first]
			results = sort_first + sort_last
		except: pass
		return results

	def sort_preferred_autoplay(self, results):
		if not self.autoplay: return results
		try:
			preferences = preferred_autoplay()
			if not preferences: return results
			preference_results = [i for i in results if any(x in i['extraInfo'] for x in preferences)]
			if not preference_results: return results
			results = [i for i in results if not i in preference_results]
			preference_results = sorted([dict(item, **{'pref_includes': sum([preference_values[preferences.index(x)] for x in [i for i in preferences if i in item['extraInfo']]])}) \
						for item in preference_results], key=lambda k: k['pref_includes'], reverse=True)
			return preference_results + results
		except: return results

	def sort_subtitle_ready_autoplay(self, results):
		if not self.autoplay or not results: return results
		search_params = self._a4k_search_params()
		if not search_params:
			logger('Fen Light Patched', 'Subtitle probe skipped: no subtitle language settings available')
			return results
		a4k_api = self._get_a4k_subtitles_api()
		if not a4k_api:
			logger('Fen Light Patched', 'Subtitle probe skipped: a4kSubtitles Patched API unavailable')
			return results
		try:
			probe_limit = min(len(results), subtitle_autoplay_probe_limit)
			logger('Fen Light Patched', 'Subtitle probe starting for %s of %s autoplay results' % (probe_limit, len(results)))
			probed_results = []
			for item in results[:probe_limit]:
				subtitle_hit, subtitle_names, subtitle_match_score = self._a4k_result_available(a4k_api, search_params, item)
				item = dict(item, **{'subtitle_hit': subtitle_hit, 'subtitle_names': subtitle_names, 'subtitle_match_score': subtitle_match_score})
				probed_results.append(item)
			subtitle_matches = [i for i in probed_results if i.get('subtitle_hit')]
			if not subtitle_matches:
				logger('Fen Light Patched', 'Subtitle probe found no subtitle-backed autoplay sources')
				return results
			subtitle_matches.sort(key=lambda k: k.get('subtitle_match_score', 0), reverse=True)
			logger('Fen Light Patched', 'Subtitle probe promoted %s source(s). First promoted source: %s' % (len(subtitle_matches), subtitle_matches[0].get('name', subtitle_matches[0].get('display_name', 'UNKNOWN'))))
			no_subtitle_matches = [i for i in probed_results if not i.get('subtitle_hit')]
			return subtitle_matches + no_subtitle_matches + results[probe_limit:]
		except: return results

	def _get_a4k_subtitles_api(self):
		if self.a4k_subtitles_checked: return self.a4k_subtitles_api
		self.a4k_subtitles_checked = True
		try:
			append_module_to_syspath(a4k_subtitles_addon_path)
			self.a4k_subtitles_api = manual_function_import('a4kSubtitles.api', 'A4kSubtitlesApi')()
			logger('Fen Light Patched', 'Subtitle probe connected to a4kSubtitles Patched API')
		except: self.a4k_subtitles_api = None
		return self.a4k_subtitles_api

	def _a4k_search_params(self):
		try:
			languages = jsonrpc_get_system_setting('subtitles.languages', [])
			preferred_language = jsonrpc_get_system_setting('locale.subtitlelanguage', 'default')
			if isinstance(languages, str): languages = [languages]
			languages = [i for i in languages if i not in (None, '', 'none')]
			if not languages and preferred_language not in (None, '', 'none'): languages = [preferred_language]
			if not languages: return None
			if preferred_language in (None, '', 'none'): preferred_language = languages[0]
			return {'action': 'search', 'languages': ','.join(languages), 'preferredlanguage': preferred_language}
		except: return None

	def _a4k_result_available(self, a4k_api, search_params, item):
		cache_key = '%s|%s|%s|%s|%s' % (self.media_type, self.meta.get('imdb_id', ''), self.meta.get('season', ''), self.meta.get('episode', ''), item.get('name', item.get('display_name', '')))
		if cache_key in self.subtitle_probe_cache:
			cached_hit, cached_names, cached_score = self.subtitle_probe_cache[cache_key]
			logger('Fen Light Patched', 'Subtitle probe cache hit for %s | match=%s | score=%s | subtitles=%s' % (item.get('name', item.get('display_name', 'UNKNOWN')), cached_hit, cached_score, ' | '.join(cached_names[:3]) or 'None'))
			return self.subtitle_probe_cache[cache_key]
		try:
			results = a4k_api.search(search_params, video_meta=self._a4k_video_meta(item))
			subtitle_names, subtitle_match_score = self._match_a4k_results_to_source(results, item)
			has_result = subtitle_match_score > 0
			logger('Fen Light Patched', 'Subtitle probe checked source=%s | match=%s | score=%s | results=%s | subtitles=%s' % (
				item.get('name', item.get('display_name', 'UNKNOWN')), has_result, subtitle_match_score, self._a4k_results_debug_summary(results), ' | '.join(subtitle_names[:3]) or 'None'))
		except:
			has_result, subtitle_names, subtitle_match_score = False, [], 0
			logger('Fen Light Patched', 'Subtitle probe failed for source=%s | error=%s' % (item.get('name', item.get('display_name', 'UNKNOWN')), traceback.format_exc().replace('\n', ' | ')))
		self.subtitle_probe_cache[cache_key] = (has_result, subtitle_names, subtitle_match_score)
		return self.subtitle_probe_cache[cache_key]

	def _match_a4k_results_to_source(self, results, item):
		source_name = item.get('name', '') or item.get('display_name', '') or ''
		source_norm = self._normalize_release_name(source_name)
		source_group = self._extract_release_group(source_name)
		best_score, best_result_index, matched_names = 0, None, []
		for result_index, result in enumerate(results):
			candidate_names = self._a4k_result_names(result)
			result_best_score, result_best_names = 0, []
			for candidate_name in candidate_names:
				score = self._subtitle_source_match_score(source_norm, source_group, candidate_name)
				if score <= 0: continue
				score = self._apply_subtitle_candidate_priority(score, source_group, candidate_name)
				if score > result_best_score:
					result_best_score = score
					result_best_names = [candidate_name]
				elif score == result_best_score and not candidate_name in result_best_names:
					result_best_names.append(candidate_name)
			if result_best_score <= 0: continue
			if best_result_index == None or result_index < best_result_index or (result_index == best_result_index and result_best_score > best_score):
				best_result_index = result_index
				best_score = result_best_score
				matched_names = result_best_names
		if matched_names: return matched_names, self._subtitle_probe_result_score(best_result_index, best_score)
		return [i for i in list(itertools.chain.from_iterable(self._a4k_result_names(result) for result in results)) if i][:3], 0

	def _apply_subtitle_candidate_priority(self, score, source_group, subtitle_name):
		subtitle_group = self._extract_release_group(subtitle_name)
		if source_group and subtitle_group and source_group == subtitle_group:
			return min(100, score + 8)
		return score

	def _subtitle_probe_result_score(self, result_index, match_score):
		rank_bonus = max(0, 100 - (result_index * 5))
		match_bonus = min(9, int(match_score / 12))
		return rank_bonus + match_bonus

	def _a4k_result_names(self, result):
		names = []
		for key in ('name', 'release', 'filename'):
			value = result.get(key, '')
			if value and not value in names: names.append(value)
		action_args = result.get('action_args', {})
		if action_args:
			for key in ('filename', 'release'):
				value = action_args.get(key, '')
				if value and not value in names: names.append(value)
		return names

	def _a4k_results_debug_summary(self, results):
		try:
			if results is None: return 'type=None count=0'
			if not isinstance(results, list): return 'type=%s' % type(results).__name__
			if not results: return 'type=list count=0'
			sample_names = []
			for result in results[:3]:
				for name in self._a4k_result_names(result):
					if name and not name in sample_names:
						sample_names.append(name)
				if len(sample_names) >= 3: break
			first_keys = ','.join(sorted(results[0].keys())[:6]) if isinstance(results[0], dict) else type(results[0]).__name__
			return 'type=list count=%s sample_keys=%s sample_names=%s' % (len(results), first_keys or 'None', ' | '.join(sample_names[:3]) or 'None')
		except:
			return 'debug_error=%s' % traceback.format_exc().replace('\n', ' | ')

	def _subtitle_source_match_score(self, source_norm, source_group, subtitle_name):
		subtitle_norm = self._normalize_release_name(subtitle_name)
		if not source_norm or not subtitle_norm: return 0
		subtitle_group = self._extract_release_group(subtitle_name)
		feature_score = self._release_feature_alignment_score(source_norm, subtitle_norm)
		if source_norm == subtitle_norm: return 100
		source_tokens = [i for i in source_norm.split('.') if i]
		subtitle_tokens = [i for i in subtitle_norm.split('.') if i]
		source_tail = self._effective_name_tail(source_tokens)
		subtitle_tail = self._effective_name_tail(subtitle_tokens)
		if source_group and subtitle_group:
			if source_group != subtitle_group: return feature_score
			if subtitle_norm in source_norm or source_norm in subtitle_norm: return 98
			tail_score = SequenceMatcher(None, source_tail, subtitle_tail).ratio() if source_tail and subtitle_tail else 0.0
			ratio_score = SequenceMatcher(None, source_norm, subtitle_norm).ratio()
			confidence = (tail_score * 0.75) + (ratio_score * 0.25)
			if confidence >= 0.97: return 98
			if confidence >= 0.9: return 95
			if confidence >= 0.82: return 92
			if confidence >= 0.72: return 88
			return max(84, feature_score)
		if subtitle_norm in source_norm or source_norm in subtitle_norm: return max(95, feature_score)
		if source_tail and subtitle_tail:
			tail_score = SequenceMatcher(None, source_tail, subtitle_tail).ratio()
			ratio_score = SequenceMatcher(None, source_norm, subtitle_norm).ratio()
			confidence = (tail_score * 0.75) + (ratio_score * 0.25)
			if confidence >= 0.9: return max(72, feature_score)
			if confidence >= 0.82: return max(64, feature_score)
			if confidence >= 0.74: return max(55, feature_score)
		return feature_score

	def _release_feature_alignment_score(self, source_norm, subtitle_norm):
		source_features = self._release_features(source_norm)
		subtitle_features = self._release_features(subtitle_norm)
		score, matched_categories = 0, 0
		if source_features['release'] and subtitle_features['release']:
			if source_features['release'] == subtitle_features['release']:
				score += 22
				matched_categories += 1
			elif 'prerelease' in (source_features['release'], subtitle_features['release']):
				return 0
			else:
				score -= 10
		if source_features['quality'] and subtitle_features['quality']:
			if source_features['quality'] == subtitle_features['quality']:
				score += 28
				matched_categories += 1
			else:
				score -= 12
		if source_features['service'] and subtitle_features['service']:
			if source_features['service'] == subtitle_features['service']:
				score += 10
				matched_categories += 1
			else:
				score -= 4
		if source_features['codec'] and subtitle_features['codec']:
			if source_features['codec'] == subtitle_features['codec']:
				score += 10
				matched_categories += 1
			else:
				score -= 3
		if source_features['audio'] and subtitle_features['audio']:
			if source_features['audio'] == subtitle_features['audio']:
				score += 6
				matched_categories += 1
		if source_features['color'] and subtitle_features['color']:
			if source_features['color'] == subtitle_features['color']:
				score += 8
				matched_categories += 1
			else:
				score -= 3
		if matched_categories >= 3 and score >= 36: return min(94, 40 + score)
		if matched_categories >= 2 and score >= 22: return min(84, 34 + score)
		if matched_categories == 1 and score >= 28: return min(72, 28 + score)
		return 0

	def _release_features(self, normalized_name):
		tokens = {i for i in normalized_name.split('.') if i}
		return {
			'release': self._token_group_match(tokens, release_family_groups),
			'quality': self._token_group_match(tokens, quality_family_groups),
			'service': self._token_group_match(tokens, service_family_groups),
			'codec': self._token_group_match(tokens, codec_family_groups),
			'audio': self._token_group_match(tokens, audio_family_groups),
			'color': self._token_group_match(tokens, color_family_groups),
		}

	def _token_group_match(self, tokens, groups):
		for label, group in groups:
			if any(i in tokens for i in group):
				return label
		return ''

	def _effective_name_tail(self, tokens, size=4):
		filtered = [i for i in tokens if i not in release_group_stopwords and i not in release_group_suffix_stopwords and not re.fullmatch(r'v\d+', i)]
		if not filtered: return ''
		return '.'.join(filtered[-size:])

	def _normalize_release_name(self, name):
		if not name: return ''
		name = clean_file_name(name).lower()
		name = re.sub(r'\[[^\]]+\]', '', name)
		name = re.sub(r'\.(mkv|mp4|avi|ts|m2ts|srt|sub|ass|ssa)$', '', name)
		name = re.sub(r'[^a-z0-9]+', '.', name).strip('.')
		return name

	def _extract_release_group(self, name):
		if not name: return ''
		raw_name = clean_file_name(name)
		raw_name = re.sub(r'\.(mkv|mp4|avi|ts|m2ts|srt|sub|ass|ssa)$', '', raw_name, flags=re.I)
		candidates = []
		bracket_match = re.search(r'\[([^\]]+)\]\s*$', raw_name)
		if bracket_match:
			candidates.append(bracket_match.group(1))
		hyphen_match = re.search(r'-([A-Za-z0-9][A-Za-z0-9 ._]+)$', raw_name)
		if hyphen_match:
			candidates.append(hyphen_match.group(1))
		for candidate in candidates:
			candidate = self._normalize_release_name(candidate)
			parts = [i for i in candidate.split('.') if i]
			for token in reversed(parts):
				if token in release_group_metadata_stopwords: continue
				if re.fullmatch(r'v\d+', token): continue
				if token.isdigit(): continue
				if len(token) < 2: continue
				return token
		return ''

	def _a4k_video_meta(self, item):
		release_name = item.get('name', '') or item.get('display_name', '') or ''
		if '.' not in release_name: release_name = '%s.mkv' % release_name
		meta = {'version': kodi_utils.get_infolabel('System.BuildVersionCode') or '20.0.0', 'year': str(self.meta.get('year', '') or ''),
				'season': str(self.meta.get('season', '') or ''), 'episode': str(self.meta.get('episode', '') or ''), 'tvshow': '', 'title': '', '_title': '',
				'imdb_id': self.meta.get('imdb_id', '') or '', 'url': item.get('url', '') or '', 'filename': release_name, 'filesize': '', 'filehash': ''}
		if self.media_type == 'movie':
			title = self.meta.get('original_title') or self.meta.get('title') or ''
			meta.update({'title': title, '_title': title})
		else:
			meta.update({'tvshow': self.meta.get('title') or '', 'title': self.meta.get('original_title') or self.meta.get('ep_name') or '',
						'_title': self.meta.get('ep_name') or self.meta.get('title') or ''})
		return meta

	def prepare_internal_scrapers(self):
		if self.active_external and len(self.active_internal_scrapers) == 1: return
		active_internal_scrapers = [i for i in self.active_internal_scrapers if not i in self.remove_scrapers]
		if self.prescrape and not self.active_external and all([check_prescrape_sources(i, self.media_type) for i in active_internal_scrapers]): return False
		if 'folders' in active_internal_scrapers:
			self.folder_info = [i for i in self.get_folderscraper_info() if source_folders_directory(self.media_type, i[1])]
			if self.folder_info:
				self.active_folders = True
				self.internal_scraper_names = [i for i in active_internal_scrapers if not i == 'folders'] + [i[0] for i in self.folder_info]
			else: self.internal_scraper_names = [i for i in active_internal_scrapers if not i == 'folders']
		else:
			self.folder_info = []
			self.internal_scraper_names = active_internal_scrapers[:]
		self.active_internal_scrapers = active_internal_scrapers
		if self.clear_properties: self._clear_properties()
		return True

	def activate_providers(self, module_type, function, prescrape):
		sources = self._get_module(module_type, function).results(self.search_info)
		if not sources: return
		if prescrape: self.prescrape_sources.extend(sources)
		else: self.sources.extend(sources)

	def activate_external_providers(self):
		if not self.import_external_scrapers(): return self.disable_external('Error Importing External Module')
		self.external_providers = self.external_sources()
		if not self.external_providers: self.disable_external('No External Providers Enabled')
	
	def import_external_scrapers(self):
		try:
			append_module_to_syspath('special://home/addons/%s/lib' % self.ext_folder)
			self.ext_sources = manual_module_import('%s.sources_%s' % (self.ext_name, self.ext_name))
			self.provider_defaults = [k.split('.')[1] for k, v in manual_function_import('%s.modules.control' % self.ext_name, 'getProviderDefaults')().items() if v == 'true']
		except: return False
		return True

	def disable_external(self, line1=''):
		if line1: notification(line1, 2000)
		try: self.active_internal_scrapers.remove('external')
		except: pass
		self.active_external, self.external_providers = False, []

	def internal_sources(self, prescrape=False):
		active_sources = [i for i in self.active_internal_scrapers if i in internal_include_list]
		try: sourceDict = [('internal', manual_function_import('scrapers.%s' % i, 'source'), i) for i in active_sources \
												if not (prescrape and not check_prescrape_sources(i, self.media_type))]
		except: sourceDict = []
		return sourceDict

	def external_sources(self):
		try:
			all_sources = self.ext_sources.total_providers['torrents']
			if self.disabled_ext_ignored: active_sources = all_sources
			elif self.default_ext_only: active_sources = [i for i in self.provider_defaults if i in all_sources]
			else: active_sources = [i for i in all_sources if json.loads(get_property('%s_settings' % self.ext_name)).get('provider.%s' % i, 'false') == 'true']
			sourceDict = [(i, manual_function_import('%s.sources_%s.%s.%s' % (self.ext_name, self.ext_name, 'torrents', i), 'source')) for i in active_sources]
		except: sourceDict = self.legacy_external_sources()
		return sourceDict

	def legacy_external_sources(self):
		try: sourceDict = manual_function_import(self.ext_name, 'sources')(specified_folders=['torrents'], ret_all=self.disabled_ext_ignored)
		except: sourceDict = []
		return sourceDict

	def folder_sources(self):
		def import_info():
			for item in self.folder_info:
				scraper_name = item[0]
				module = manual_function_import('scrapers.folders', 'source')
				yield ('folders', (module, (item[1], scraper_name, item[2])), scraper_name)
		sourceDict = list(import_info())
		try: sourceDict = list(import_info())
		except: sourceDict = []
		return sourceDict

	def play_source(self, results):
		if self.background or self.autoplay: return self.play_file(results)
		return self.display_results(results)

	def append_folder_scrapers(self, current_list):
		current_list.extend(self.folder_sources())

	def get_folderscraper_info(self):
		folder_info = [(get_setting('fenlight.%s.display_name' % i), i, source_folders_directory(self.media_type, i)) for i in folder_scrapers]
		return [i for i in folder_info if not i[0] in (None, 'None', '') and i[2]]

	def scrapers_dialog(self):
		def _scraperDialog():
			monitor = xbmc_monitor()
			start_time = time.time()
			while not self.progress_dialog.iscanceled() and not monitor.abortRequested():
				try:
					remaining_providers = [x.getName() for x in _threads if x.is_alive() is True]
					self._process_internal_results()
					current_progress = max((time.time() - start_time), 0)
					line1 = ', '.join(remaining_providers).upper()
					percent = int((current_progress/float(scraper_timeout))*100)
					self.progress_dialog.update_scraper(self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent)
					sleep(self.sleep_time)
					if len(remaining_providers) == 0: break
					if percent >= 100: break
				except:	return self._kill_progress_dialog()
		if self.prescrape: scraper_list, _threads = self.prescrape_scrapers, self.prescrape_threads
		else: scraper_list, _threads = self.providers, self.threads
		self.internal_scrapers = self._get_active_scraper_names(scraper_list)
		if not self.internal_scrapers: return
		_scraperDialog()
		try: del monitor
		except: pass

	def display_results(self, results):
		window_format, window_number = results_format()
		action, chosen_item = open_window(('windows.sources', 'SourcesResults'), 'sources_results.xml',
				window_format=window_format, window_id=window_number, results=results, meta=self.meta, episode_group_label=self.episode_group_label,
				scraper_settings=self.scraper_settings, prescrape=self.prescrape, filters_ignored=self.filters_ignored, uncached_results=self.uncached_results)
		if not action: self._kill_progress_dialog()
		elif action == 'play': return self.play_file(results, chosen_item)
		elif self.prescrape and action == 'perform_full_search':
			self.prescrape, self.clear_properties = False, False
			return self.get_sources()

	def _get_active_scraper_names(self, scraper_list):
		return [i[2] for i in scraper_list]

	def _process_post_results(self):
		if self.auto_rescrape_with_all in (1, 2) and self.active_external and not self.rescrape_with_all:
			self.rescrape_with_all = True
			if self.auto_rescrape_with_all == 1 or confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With All Scrapers?'):
				self.threads, self.disabled_ext_ignored, self.prescrape = [], True, False
				return self.get_sources()
		if self.media_type == 'episode' and self.auto_episode_group in (1, 2) and not self.rescrape_with_episode_group:
			self.rescrape_with_episode_group = True
			if self.auto_episode_group == 1 or confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With Custom Episode Group if Possible?'):
				if self.episode_group_used:
					self.params.update({'custom_season': None, 'custom_episode': None, 'episode_group_label': '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (self.season, self.episode),
										'skip_episode_group_check': True})
					self.threads, self.rescrape_with_all, self.disabled_ext_ignored, self.prescrape = [], True, True, False
					return self.playback_prep()
				if self.auto_episode_group == 2:
					from indexers.dialogs import episode_groups_choice
					try: group_id = episode_groups_choice({'meta': self.meta, 'poster': self.meta['poster']})
					except: group_id = None
				else:
					try: group_id = metadata.episode_groups(self.tmdb_id)[0]['id']
					except: group_id = None
				if group_id:
					try: group_details = metadata.group_episode_data(metadata.group_details(group_id), None, self.season, self.episode)
					except: group_details = None
					if group_details:
						season, episode = group_details['season'], group_details['episode']
						self.params.update({'custom_season': season, 'custom_episode': episode, 'episode_group_label': '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (season, episode)})
						self.threads, self.rescrape_with_episode_group, self.rescrape_with_all, self.disabled_ext_ignored, self.prescrape = [], True, True, True, False
						return self.playback_prep()
		if self.orig_results and not self.background:
			if self.ignore_results_filter == 0: return self._no_results()
			if self.ignore_results_filter == 1 or confirm_dialog(heading=self.meta.get('rootname', ''), text='No results. Access Filtered Results?'):
				return self._process_ignore_filters()
		return self._no_results()

	def _process_ignore_filters(self):
		if self.autoplay: notification('Filters Ignored & Autoplay Disabled')
		self.filters_ignored, self.autoplay = True, False
		results = self.sort_results(self.orig_results)
		results = self.sort_preferred_autoplay(results)
		results = self.sort_first(results)
		return self.play_source(results)

	def _no_results(self):
		self._kill_progress_dialog()
		hide_busy_dialog()
		if self.background: return notification('[B]Next Up:[/B] No Results', 5000)
		notification('No Results', 2000)

	def get_search_title(self):
		search_title = self.meta.get('custom_title', None) or self.meta.get('english_title') or self.meta.get('title')
		return search_title

	def get_search_year(self):
		year = self.meta.get('custom_year', None) or self.meta.get('year')
		return year

	def get_season(self):
		season = self.meta.get('custom_season', None) or self.meta.get('season')
		try: season = int(season)
		except: season = None
		return season

	def get_episode(self):
		episode = self.meta.get('custom_episode', None) or self.meta.get('episode')
		try: episode = int(episode)
		except: episode = None
		return episode

	def get_ep_name(self):
		ep_name = None
		if self.meta['media_type'] == 'episode':
			ep_name = self.meta.get('ep_name')
			try: ep_name = safe_string(remove_accents(ep_name))
			except: ep_name = safe_string(ep_name)
		return ep_name

	def _process_internal_results(self):
		for i in self.internal_scrapers:
			win_property = get_property(int_window_prop % i)
			if win_property in ('checked', '', None): continue
			try: sources = json.loads(win_property)
			except: continue
			set_property(int_window_prop % i, 'checked')
			self._sources_quality_count(sources)
	
	def _sources_quality_count(self, sources):
		for item in self.count_tuple: setattr(self, item[0], getattr(self, item[0]) + item[2](sources, item[1]))

	def _quality_filter(self):
		setting = 'results_quality_%s' % self.media_type if not self.autoplay else 'autoplay_quality_%s' % self.media_type
		filter_list = quality_filter(setting)
		if self.include_prerelease_results and 'SD' in filter_list: filter_list += ['SCR', 'CAM', 'TELE']
		return filter_list

	def _get_quality_rank(self, quality):
		return quality_ranks[quality]

	def _get_provider_rank(self, account_type):
		return self.provider_sort_ranks[account_type] or 11

	def _sort_folder_to_top(self, provider):
		if provider == 'folders': return 0
		else: return 1

	def _sort_uncached_results(self, results):
		uncached = [i for i in results if 'Uncached' in i.get('cache_provider', '')]
		cached = [i for i in results if not i in uncached]
		return cached + uncached

	def get_meta(self):
		if self.media_type == 'movie': self.meta = metadata.movie_meta('tmdb_id', self.tmdb_id, tmdb_api_key(), mpaa_region(), get_datetime())
		else:
			try:
				self.meta = metadata.tvshow_meta('tmdb_id', self.tmdb_id, tmdb_api_key(), mpaa_region(), get_datetime())
				episodes_data = metadata.episodes_meta(self.season, self.meta)
				episode_data = [i for i in episodes_data if i['episode'] == self.episode][0]
				ep_thumb = episode_data.get('thumb', None) or self.meta.get('fanart') or ''
				episode_type = episode_data.get('episode_type', '')
				self.meta.update({'season': episode_data['season'], 'episode': episode_data['episode'], 'premiered': episode_data['premiered'], 'episode_type': episode_type,
								'ep_name': episode_data['title'], 'ep_thumb': ep_thumb, 'plot': episode_data['plot'], 'tvshow_plot': self.meta['plot'],
								'custom_season': self.custom_season, 'custom_episode': self.custom_episode})
			except: pass
		self.meta.update({'media_type': self.media_type, 'background': self.background, 'custom_title': self.custom_title, 'custom_year': self.custom_year})

	def make_search_info(self):
		title, year, ep_name = self.get_search_title(), self.get_search_year(), self.get_ep_name()
		aliases = make_alias_dict(self.meta, title)
		expiry_times = get_cache_expiry(self.media_type, self.meta, self.season)
		self.search_info = {'media_type': self.media_type, 'title': title, 'year': year, 'tmdb_id': self.tmdb_id, 'imdb_id': self.meta.get('imdb_id'), 'aliases': aliases,
							'season': self.get_season(), 'episode': self.get_episode(), 'tvdb_id': self.meta.get('tvdb_id'), 'ep_name': ep_name, 'expiry_times': expiry_times,
							'total_seasons': self.meta.get('total_seasons', 1)}

	def _get_module(self, module_type, function):
		if module_type == 'external': module = function.source(*self.external_args)
		elif module_type == 'folders': module = function[0](*function[1])
		else: module = function()
		return module

	def _clear_properties(self):
		for item in default_internal_scrapers: clear_property(int_window_prop % item)
		if self.active_folders:
			for item in self.folder_info: clear_property(int_window_prop % item[0])

	def _make_progress_dialog(self):
		self.progress_dialog = create_window(('windows.sources', 'SourcesPlayback'), 'sources_playback.xml', meta=self.meta)
		self.progress_thread = Thread(target=self.progress_dialog.run)
		self.progress_thread.start()

	def _make_resolve_dialog(self):
		self.resolve_dialog_made = True
		if not self.progress_dialog: self._make_progress_dialog()
		self.progress_dialog.enable_resolver()

	def _make_resume_dialog(self, percent):
		if not self.progress_dialog: self._make_progress_dialog()
		self.progress_dialog.enable_resume(percent)
		return self.progress_dialog.resume_choice

	def _make_nextep_dialog(self, default_action='cancel'):
		try: action = open_window(('windows.next_episode', 'NextEpisode'), 'next_episode.xml', meta=self.meta, default_action=default_action)
		except: action = 'cancel'
		return action

	def _kill_progress_dialog(self):
		success = 0
		try:
			self.progress_dialog.close()
			success += 1
		except: pass
		try:
			self.progress_thread.join()
			success += 1
		except: pass
		if not success == 2: close_all_dialog()
		del self.progress_dialog
		del self.progress_thread
		self.progress_dialog, self.progress_thread = None, None

	def debridPacks(self, debrid_provider, name, magnet_url, info_hash, download=False):
		show_busy_dialog()
		debrid_info = {'Real-Debrid': 'rd_browse', 'Premiumize.me': 'pm_browse', 'AllDebrid': 'ad_browse',
						'Offcloud': 'oc_browse', 'EasyDebrid': 'ed_browse', 'TorBox': 'tb_browse'}[debrid_provider]
		debrid_function = self.debrid_importer(debrid_info)
		try: debrid_files = debrid_function().display_magnet_pack(magnet_url, info_hash)
		except: debrid_files = None
		hide_busy_dialog()
		if not debrid_files: return notification('Error')
		debrid_files.sort(key=lambda k: k['filename'].lower())
		if download: return debrid_files, debrid_function
		list_items = [{'line1': '%.2f GB | %s' % (float(item['size'])/1073741824, clean_file_name(item['filename']).upper())} for item in debrid_files]
		kwargs = {'items': json.dumps(list_items), 'heading': name, 'enumerate': 'true', 'narrow_window': 'true'}
		chosen_result = select_dialog(debrid_files, **kwargs)
		if chosen_result is None: return None
		link = self.resolve_internal(debrid_info, chosen_result['link'], '')
		name = chosen_result['filename']
		self._kill_progress_dialog()
		return FenLightPlayer().run(link, 'video')

	def play_file(self, results, source={}):
		self.playback_successful, self.cancel_all_playback = None, False
		try:
			hide_busy_dialog()
			url = None
			results = [i for i in results if not 'Uncached' in i.get('cache_provider', '')]
			if not source: source = results[0]
			items = [source]
			if not self.limit_resolve: 
				source_index = results.index(source)
				results.remove(source)
				items_prev = results[:source_index]
				items_prev.reverse()
				items_next = results[source_index:]
				items = items + items_next + items_prev
			processed_items = []
			processed_items_append = processed_items.append
			for count, item in enumerate(items, 1):
				resolve_item = dict(item)
				provider = item['scrape_provider']
				if provider == 'external': provider = item['debrid'].replace('.me', '')
				elif provider == 'folders': provider = item['source']
				provider_text = provider.upper()
				extra_info = '[B]%s[/B] | [B]%s[/B] | %s' %  (item['quality'], item['size_label'], item['extraInfo'])
				display_name = item['display_name'].upper()
				resolve_item['resolve_display'] = '%02d. [B]%s[/B][CR]%s[CR]%s' % (count, provider_text, extra_info, display_name)
				processed_items_append(resolve_item)
				if provider == 'easynews':
					for retry in range(1, 2):
						resolve_item = dict(item)
						resolve_item['resolve_display'] = '%02d. [B]%s (RETRYx%s)[/B][CR]%s[CR]%s' % (count, provider_text, retry, extra_info, display_name)
						processed_items_append(resolve_item)
			items = list(processed_items)
			if not self.continue_resolve_check(): return self._kill_progress_dialog()
			hide_busy_dialog()
			self.playback_percent = self.get_playback_percent()
			if self.playback_percent == None: return self._kill_progress_dialog()
			if not self.resolve_dialog_made: self._make_resolve_dialog()
			if self.background: sleep(1000)
			monitor = xbmc_monitor()
			for count, item in enumerate(items, 1):
				try:
					hide_busy_dialog()
					if not self.progress_dialog: break
					self.progress_dialog.reset_is_cancelled()
					self.progress_dialog.update_resolver(text=item['resolve_display'])
					self.progress_dialog.busy_spinner()
					if count > 1:
						sleep(200)
						try: del player
						except: pass
					url, self.playback_successful, self.cancel_all_playback = None, None, False
					self.playing_filename = item['name']
					self.playing_item = item
					player = FenLightPlayer()
					try:
						if self.progress_dialog.iscanceled() or monitor.abortRequested(): break
						url = self.resolve_sources(item)
						if url:
							resolve_percent = 0
							self.progress_dialog.busy_spinner('false')
							self.progress_dialog.update_resolver(percent=resolve_percent)
							sleep(200)
							player.run(url, self)
						else: continue
						if self.cancel_all_playback: break
						if self.playback_successful: break
						if count == len(items):
							self.cancel_all_playback = True
							player.stop()
							break
					except: pass
				except: pass
		except: self._kill_progress_dialog()
		if self.cancel_all_playback: return self._kill_progress_dialog()
		if not self.playback_successful or not url: self.playback_failed_action()
		try: del monitor
		except: pass

	def get_playback_percent(self):
		if self.media_type == 'movie': percent = get_progress_status_movie(get_bookmarks_movie(), str(self.tmdb_id))
		elif any((self.random, self.random_continual)): return 0.0
		else: percent = get_progress_status_episode(get_bookmarks_episode(self.tmdb_id, self.season), self.episode)
		if not percent: return 0.0
		action = self.get_resume_status(percent)
		if action == 'cancel': return None
		if action == 'start_over':
			erase_bookmark(self.media_type, self.tmdb_id, self.season, self.episode)
			return 0.0
		return float(percent)

	def get_resume_status(self, percent):
		if auto_resume(self.media_type): return float(percent)
		return self._make_resume_dialog(percent)

	def playback_failed_action(self):
		self._kill_progress_dialog()
		if self.prescrape and self.autoplay:
			self.resolve_dialog_made, self.prescrape, self.prescrape_sources = False, False, []
			self.get_sources()

	def continue_resolve_check(self):
		try:
			if not self.background or self.autoscrape_nextep: return True
			if self.autoplay_nextep: return self.autoplay_nextep_handler()
			return self.random_continual_handler()
		except: return False

	def random_continual_handler(self):
		notification('[B]Next Up:[/B] %s S%02dE%02d' % (self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')), 6500, self.meta.get('poster'))
		player = xbmc_player()
		while player.isPlayingVideo(): sleep(100)
		self._make_resolve_dialog()
		return True

	def autoplay_nextep_handler(self):
		if not self.nextep_settings: return False
		player = xbmc_player()
		if player.isPlayingVideo():
			total_time = player.getTotalTime()
			use_window, window_time, default_action = self.nextep_settings['use_window'], self.nextep_settings['window_time'], self.nextep_settings['default_action']
			action = None if use_window else 'close'
			continue_nextep = False
			while player.isPlayingVideo():
				try:
					remaining_time = round(total_time - player.getTime())
					if remaining_time <= window_time:
						continue_nextep = True
						break
					sleep(100)
				except: pass
			if continue_nextep:
				if use_window: action = self._make_nextep_dialog(default_action=default_action)
				else: notification('[B]Next Up:[/B] %s S%02dE%02d' % (self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')), 6500, self.meta.get('poster'))
				if not action: action = default_action
				if action == 'cancel': return False
				elif action == 'pause':
					player.stop()
					return False
				elif action == 'play':
					self._make_resolve_dialog()
					player.stop()
					return True
				else:
					while player.isPlayingVideo(): sleep(100)
					self._make_resolve_dialog()
					return True
			else: return False
		else: return False

	def autoscrape_nextep_handler(self):
		player = xbmc_player()
		if player.isPlayingVideo():
			results = self.get_sources()
			if not results: return notification(33092, 3000)
			else:
				notification('[B]Next Episode Ready:[/B] %s S%02dE%02d' % (self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')), 6500, self.meta.get('poster'))
				while player.isPlayingVideo(): sleep(100)
			self.display_results(results)
		else: return

	def debrid_importer(self, debrid_provider):
		return manual_function_import(*debrids[debrid_provider])

	def resolve_sources(self, item, meta=None):
		if meta: self.meta = meta
		url = None
		try:
			if 'cache_provider' in item:
				cache_provider = item['cache_provider']
				if self.meta['media_type'] == 'episode':
					if hasattr(self, 'search_info'):
						title, season, episode, pack = self.search_info['title'], self.search_info['season'], self.search_info['episode'], 'package' in item
					else: title, season, episode, pack = self.get_ep_name(), self.get_season(), self.get_episode(), 'package' in item
				else: title, season, episode, pack = self.get_search_title(), None, None, False
				if cache_provider in debrid_providers: url = self.resolve_cached(cache_provider, item['url'], item['hash'], title, season, episode, pack)
			elif item.get('scrape_provider', None) in default_internal_scrapers:
				url = self.resolve_internal(item['scrape_provider'], item['id'], item['url_dl'], item.get('direct_debrid_link', False))
			else: url = item['url']
		except: pass
		return url

	def resolve_cached(self, debrid_provider, item_url, _hash, title, season, episode, pack):
		debrid_function = self.debrid_importer(debrid_provider)
		store_to_cloud = store_resolved_to_cloud(debrid_provider, pack)
		try: url = debrid_function().resolve_magnet(item_url, _hash, store_to_cloud, title, season, episode)
		except: url = None
		return url

	def resolve_internal(self, scrape_provider, item_id, url_dl, direct_debrid_link=False):
		url = None
		try:
			if direct_debrid_link or scrape_provider == 'folders': url = url_dl
			elif scrape_provider == 'easynews':
				from indexers.easynews import resolve_easynews
				url = resolve_easynews({'url_dl': url_dl, 'play': 'false'})
			else:
				debrid_function = self.debrid_importer(scrape_provider)
				if any(i in scrape_provider for i in ('rd_', 'ad_', 'tb_')):
					url = debrid_function().unrestrict_link(item_id)
				else:
					if '_cloud' in scrape_provider: item_id = debrid_function().get_item_details(item_id)['link']
					url = debrid_function().add_headers_to_url(item_id)
		except: pass
		return url

	def _quality_length(self, items, quality):
		return len([i for i in items if i['quality'] == quality])

	def _quality_length_sd(self, items, dummy):
		return len([i for i in items if i['quality'] in sd_check])

	def _quality_length_final(self, items, dummy):
		return len(items)
