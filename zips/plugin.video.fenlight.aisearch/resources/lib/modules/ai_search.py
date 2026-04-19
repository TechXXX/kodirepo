# -*- coding: utf-8 -*-
import hashlib
import re
from datetime import date
from urllib.parse import unquote
from apis import tmdb_api
from apis.gemini_api import GeminiAPI
from caches.main_cache import main_cache
from indexers.movies import Movies
from indexers.tvshows import TVShows
from modules import kodi_utils, meta_lists
from modules.search import add_to_search
from modules.settings import gemini_api_key
from modules.utils import remove_accents, safe_string

notification, build_url, kodi_dialog = kodi_utils.notification, kodi_utils.build_url, kodi_utils.kodi_dialog
execute_builtin, close_all_dialog = kodi_utils.execute_builtin, kodi_utils.close_all_dialog
external = kodi_utils.external
empty_setting_check = (None, '', 'empty_setting')
results_cache_prefix = 'ai_search_results_v1_'
results_cache_expiration = 24

genre_aliases = {
	'movie': {
		'sci fi': ['science fiction'],
		'scifi': ['science fiction'],
		'science fiction': ['science fiction'],
		'rom com': ['romance', 'comedy'],
		'romcom': ['romance', 'comedy'],
		'action adventure': ['action', 'adventure']
	},
	'tvshow': {
		'sci fi': ['sci fi fantasy'],
		'scifi': ['sci fi fantasy'],
		'science fiction': ['sci fi fantasy'],
		'science fiction fantasy': ['sci fi fantasy'],
		'action adventure': ['action adventure'],
		'war politics': ['war politics']
	}
}

def run(params):
	close_all_dialog()
	prompt = _get_prompt(params, allow_input=True)
	if not prompt: return
	if gemini_api_key() in empty_setting_check:
		return notification('Please set a Gemini API Key')
	add_to_search(prompt, 'ai_search_queries')
	result_payload = _get_result_payload(prompt, params)
	if not result_payload:
		return notification('No AI Search results found.')
	cache_id = _store_results(prompt, result_payload)
	command = 'ActivateWindow(Videos,%s,return)' if external() else 'Container.Update(%s)'
	return execute_builtin(command % build_url({'mode': 'ai_search.results', 'cache_id': cache_id}))

def widget(params):
	prompt = _get_prompt(params, allow_input=not external())
	fallback_type = _requested_media_type(params)
	if not prompt:
		return _render_empty_results(params, fallback_type)
	result_payload = _cached_results(prompt) or _get_result_payload(prompt, params)
	if not result_payload:
		if not external():
			if gemini_api_key() in empty_setting_check: notification('Please set a Gemini API Key')
			else: notification('No AI Search results found.')
		return _render_empty_results(params, fallback_type, prompt)
	return _render_results(_apply_label_overrides(result_payload, params, prompt))

def results(params):
	cache_id = params.get('cache_id')
	if not cache_id: return notification('AI Search results are unavailable.')
	result_payload = main_cache.get(cache_id)
	if not result_payload: return notification('AI Search results expired. Please try again.')
	return _render_results(result_payload)

def _get_prompt(params, allow_input=False):
	prompt = params.get('key_id') or params.get('query')
	if not prompt and allow_input: prompt = kodi_dialog().input('Describe what you want to watch')
	if not prompt: return None
	prompt = unquote(prompt).strip()
	return prompt or None

def _requested_media_type(params):
	media_type = params.get('media_type')
	if media_type in ('movie', 'tvshow'): return media_type
	return None

def _result_cache_id(prompt):
	return results_cache_prefix + hashlib.md5(prompt.encode('utf-8')).hexdigest()

def _cached_results(prompt):
	return main_cache.get(_result_cache_id(prompt))

def _get_result_payload(prompt, params=None):
	result_payload = _cached_results(prompt)
	if result_payload: return _apply_label_overrides(result_payload, params or {}, prompt)
	if gemini_api_key() in empty_setting_check: return None
	intent = GeminiAPI().interpret_prompt(prompt)
	if not intent: return None
	result_payload = _build_result_payload(prompt, intent, params or {})
	if not result_payload: return None
	_store_results(prompt, result_payload)
	return result_payload

def _build_result_payload(prompt, intent, params=None):
	params = params or {}
	media_type = _requested_media_type(params) or intent.get('media_type', 'movie')
	category_name = params.get('category_name') or params.get('name') or 'AI Search: %s' % prompt
	discover_url = _build_discover_url(media_type, intent)
	if discover_url and _discover_has_results(media_type, discover_url):
		action = 'tmdb_movies_discover' if media_type == 'movie' else 'tmdb_tv_discover'
		params = {'action': action, 'url': discover_url, 'name': category_name, 'category_name': category_name}
		return {'media_type': media_type, 'params': params}
	result_ids = _title_seed_results(media_type, intent)
	if len(result_ids) < 12:
		for item in _keyword_fallback_results(media_type, intent):
			if item in result_ids: continue
			result_ids.append(item)
			if len(result_ids) == 20: break
	if not result_ids: return None
	params = {'list': result_ids[:20], 'id_type': 'tmdb_id', 'name': category_name, 'category_name': category_name}
	return {'media_type': media_type, 'params': params}

def _store_results(prompt, payload):
	cache_id = _result_cache_id(prompt)
	main_cache.set(cache_id, payload, expiration=results_cache_expiration)
	return cache_id

def _apply_label_overrides(result_payload, params, prompt):
	if not params: return result_payload
	category_name = params.get('category_name') or params.get('name')
	if not category_name: return result_payload
	new_payload = {'media_type': result_payload.get('media_type', 'movie'), 'params': dict(result_payload.get('params', {}))}
	new_payload['params'].update({'name': category_name, 'category_name': category_name})
	return new_payload

def _render_results(result_payload):
	media_type = result_payload.get('media_type', 'movie')
	builder = Movies if media_type == 'movie' else TVShows
	return builder(result_payload.get('params', {})).fetch_list()

def _render_empty_results(params=None, media_type=None, prompt=None):
	params = params or {}
	media_type = media_type or 'movie'
	category_name = params.get('category_name') or params.get('name') or ('AI Search: %s' % prompt if prompt else 'AI Search')
	return _render_results({'media_type': media_type, 'params': {'list': [], 'id_type': 'tmdb_id', 'name': category_name, 'category_name': category_name}})

def _build_discover_url(media_type, intent):
	genre_ids = _resolve_genre_ids(media_type, intent.get('genres', []))
	keyword_ids = _resolve_keyword_ids(intent.get('keywords', []) + intent.get('tone_descriptors', []))
	if not any((genre_ids, keyword_ids)): return None
	base_type = 'movie' if media_type == 'movie' else 'tv'
	current_date = str(date.today())
	url = 'https://api.themoviedb.org/3/discover/%s?language=en-US&region=US&sort_by=popularity.desc' % base_type
	if media_type == 'movie': url += '&primary_release_date.lte=%s' % current_date
	else: url += '&include_null_first_air_dates=false&first_air_date.lte=%s' % current_date
	start_year, end_year = _year_range(intent)
	if start_year:
		if media_type == 'movie': url += '&primary_release_date.gte=%s-01-01' % start_year
		else: url += '&first_air_date.gte=%s-01-01' % start_year
	if end_year:
		if media_type == 'movie': url += '&primary_release_date.lte=%s-12-31' % end_year
		else: url += '&first_air_date.lte=%s-12-31' % end_year
	if genre_ids: url += '&with_genres=%s' % '|'.join(genre_ids[:4])
	if keyword_ids: url += '&with_keywords=%s' % '|'.join(keyword_ids[:5])
	return url

def _discover_has_results(media_type, discover_url):
	try:
		if media_type == 'movie': data = tmdb_api.tmdb_movies_discover(discover_url, 1)
		else: data = tmdb_api.tmdb_tv_discover(discover_url, 1)
		return bool(data.get('results', []))
	except: return False

def _title_seed_results(media_type, intent):
	search_function = tmdb_api.tmdb_movies_search if media_type == 'movie' else tmdb_api.tmdb_tv_search
	recommend_function = tmdb_api.tmdb_movies_recommendations if media_type == 'movie' else tmdb_api.tmdb_tv_recommendations
	result_ids, seed_ids = [], []
	append_result, append_seed = result_ids.append, seed_ids.append
	for title in intent.get('example_titles', [])[:3]:
		try: data = search_function(title, 1)
		except: continue
		if not isinstance(data, dict): continue
		results = data.get('results', [])
		if not results: continue
		filtered = _filter_results(results, media_type, intent)
		seed_result = filtered[0] if filtered else results[0]
		seed_id = seed_result['id']
		if seed_id not in result_ids: append_result(seed_id)
		if seed_id not in seed_ids: append_seed(seed_id)
	for seed_id in seed_ids[:3]:
		try: recommendations = recommend_function(seed_id, 1).get('results', [])
		except: continue
		for item in _filter_results(recommendations, media_type, intent):
			item_id = item.get('id')
			if not item_id or item_id in result_ids: continue
			append_result(item_id)
			if len(result_ids) == 20: return result_ids
	return result_ids

def _keyword_fallback_results(media_type, intent):
	result_ids = []
	append = result_ids.append
	keyword_function = tmdb_api.tmdb_movie_keyword_results_direct if media_type == 'movie' else tmdb_api.tmdb_tv_keyword_results_direct
	for keyword in intent.get('keywords', [])[:3] + intent.get('tone_descriptors', [])[:2]:
		try: data = keyword_function(keyword, 1)
		except: continue
		if not data: continue
		for item in _filter_results(data.get('results', []), media_type, intent):
			item_id = item.get('id')
			if not item_id or item_id in result_ids: continue
			append(item_id)
			if len(result_ids) == 20: return result_ids
	return result_ids

def _resolve_genre_ids(media_type, genres):
	genre_list = meta_lists.movie_genres if media_type == 'movie' else meta_lists.tvshow_genres
	genre_lookup = {_normalize(item['name']): item['id'] for item in genre_list}
	resolved_ids = []
	append = resolved_ids.append
	alias_lookup = genre_aliases[media_type]
	for genre in genres:
		normalized_genre = _normalize(genre)
		lookup_values = alias_lookup.get(normalized_genre, [normalized_genre])
		for lookup_key in lookup_values:
			genre_id = genre_lookup.get(lookup_key)
			if genre_id and genre_id not in resolved_ids: append(genre_id)
	return resolved_ids

def _resolve_keyword_ids(keyword_list):
	keyword_ids = []
	append = keyword_ids.append
	for keyword in _clean_list(keyword_list, 6):
		try: results = tmdb_api.tmdb_keywords_by_query(keyword, 1).get('results', [])
		except: continue
		if not results: continue
		match = _best_keyword_match(keyword, results)
		match_id = str(match.get('id'))
		if match_id and match_id not in keyword_ids: append(match_id)
	return keyword_ids

def _best_keyword_match(keyword, results):
	normalized_keyword = _normalize(keyword)
	for item in results:
		if _normalize(item.get('name', '')) == normalized_keyword: return item
	return results[0]

def _filter_results(results, media_type, intent):
	start_year, end_year = _year_range(intent)
	exclude_terms = [_normalize(item) for item in intent.get('exclude_terms', []) if item]
	filtered = []
	append = filtered.append
	for item in results:
		title = safe_string(item.get('title') or item.get('name') or '')
		normalized_title = _normalize(title)
		if exclude_terms and any(term in normalized_title for term in exclude_terms): continue
		result_year = _result_year(item, media_type)
		if start_year and result_year and result_year < start_year: continue
		if end_year and result_year and result_year > end_year: continue
		append(item)
	return filtered

def _year_range(intent):
	year_range = intent.get('year_range', {}) or {}
	start_year, end_year = year_range.get('start'), year_range.get('end')
	try: start_year = int(start_year) if start_year else None
	except: start_year = None
	try: end_year = int(end_year) if end_year else None
	except: end_year = None
	if all((start_year, end_year)) and start_year > end_year: start_year, end_year = end_year, start_year
	return start_year, end_year

def _result_year(item, media_type):
	date_value = item.get('release_date') if media_type == 'movie' else item.get('first_air_date')
	try: return int(str(date_value)[:4])
	except: return None

def _clean_list(items, limit):
	results = []
	append = results.append
	for item in items:
		item = safe_string(item).strip()
		if not item or item in results: continue
		append(item)
		if len(results) == limit: break
	return results

def _normalize(value):
	value = remove_accents(safe_string(value)).lower()
	value = value.replace('&', ' ')
	value = re.sub(r'[^a-z0-9]+', ' ', value)
	return ' '.join(value.split())
