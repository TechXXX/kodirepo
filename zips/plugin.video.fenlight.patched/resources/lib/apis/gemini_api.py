# -*- coding: utf-8 -*-
import hashlib
import json
from caches.main_cache import main_cache
from modules.kodi_utils import make_session
from modules.settings import gemini_api_keys

base_url = 'https://generativelanguage.googleapis.com/v1beta'
model = 'gemini-2.5-flash'
timeout = 20.0
cache_expiration = 168
cache_prefix = 'ai_search_gemini_intent_v3_'
empty_setting_check = (None, '', 'empty_setting')
session = make_session(base_url)

response_schema = {
	'type': 'object',
	'properties': {
		'media_type': {
			'type': 'string',
			'enum': ['movie', 'tvshow'],
			'description': 'Choose the single best media type for the request.'
		},
		'genres': {
			'type': 'array',
			'items': {'type': 'string'},
			'description': 'Canonical genre labels inferred from the prompt.'
		},
		'keywords': {
			'type': 'array',
			'items': {'type': 'string'},
			'description': 'Concrete searchable themes, concepts, or motifs.'
		},
		'people': {
			'type': 'array',
			'items': {'type': 'string'},
			'description': 'Named actors, performers, directors, or creators explicitly implied by the request.'
		},
		'tone_descriptors': {
			'type': 'array',
			'items': {'type': 'string'},
			'description': 'Short mood or tone descriptors that could map to TMDb keywords.'
		},
		'example_titles': {
			'type': 'array',
			'items': {'type': 'string'},
			'description': 'A few example titles that match the request.'
		},
		'year_range': {
			'type': 'object',
			'properties': {
				'start': {'type': ['integer', 'null']},
				'end': {'type': ['integer', 'null']}
			},
			'required': ['start', 'end'],
			'description': 'Optional inclusive year range inferred from the request.'
		},
		'exclude_terms': {
			'type': 'array',
			'items': {'type': 'string'},
			'description': 'Titles, genres, or terms the user wants to avoid.'
		}
	},
	'required': ['media_type', 'genres', 'keywords', 'people', 'tone_descriptors', 'example_titles', 'year_range', 'exclude_terms']
}

prompt_template = '''Interpret this natural-language movie or TV discovery request for a Kodi addon.
Return only JSON matching the provided schema.

Rules:
- Choose exactly one media_type: "movie" or "tvshow".
- Do not return anime as a separate type.
- The request is always about movies or TV shows. Do not interpret it as a generic non-screen-media topic.
- If the request is short, title-like, or looks like a franchise name, treat it as likely referring to an existing movie or TV title/franchise.
- For short title-like prompts, preserve the literal intent of the prompt and prefer direct title/franchise matches in example_titles.
- Do not over-generalize short prompts into broad themes if a well-known title or franchise match is plausible.
- genres should be short canonical labels, not sentences.
- keywords should focus on themes, hooks, settings, or motifs.
- If the request mentions a specific actor, comedian, performer, director, or creator, put that person in people.
- Use canonical person spellings when you know them.
- Do not treat a named person as just a loose keyword when they are clearly intended as cast or creator guidance.
- tone_descriptors should be short mood descriptors.
- example_titles should contain at most 3 titles.
- If the prompt is a likely title or franchise, use example_titles to include the most likely matching known titles.
- Use null for unknown year_range values.
- exclude_terms should contain explicit avoid terms only.
- Do not explain your reasoning.

User request: %s'''

media_type_aliases = {
	'movie': 'movie',
	'film': 'movie',
	'tv': 'tvshow',
	'tv_show': 'tvshow',
	'tvshow': 'tvshow',
	'show': 'tvshow',
	'series': 'tvshow',
	'television': 'tvshow'
}

class GeminiAPI:
	def __init__(self):
		self.api_keys = gemini_api_keys()

	def interpret_prompt(self, prompt):
		if not self.api_keys or not prompt: return None
		cache_key = cache_prefix + hashlib.md5(prompt.encode('utf-8')).hexdigest()
		cached_result = main_cache.get(cache_key)
		if cached_result is not None: return cached_result
		response = self._request(prompt)
		if not response: return None
		parsed_result = self._parse_response(response)
		if not parsed_result: return None
		main_cache.set(cache_key, parsed_result, expiration=cache_expiration)
		return parsed_result

	def _request(self, prompt):
		url = '%s/models/%s:generateContent' % (base_url, model)
		payload = {
			'contents': [{'parts': [{'text': prompt_template % prompt}]}],
			'generationConfig': {
				'temperature': 0.2,
				'responseMimeType': 'application/json',
				'responseJsonSchema': response_schema
			}
		}
		for api_key in self.api_keys:
			response, error_details = self._request_with_key(url, payload, api_key)
			if response is not None: return response
			if not self._should_try_next_key(error_details): return None
		return None

	def _request_with_key(self, url, payload, api_key):
		headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}
		try:
			response = session.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
			if response.ok: return response.json(), None
			return None, self._error_details(response)
		except:
			return None, None

	def _error_details(self, response):
		status = ''
		message = ''
		try:
			data = response.json()
			error = data.get('error') or {}
			status = error.get('status') or ''
			message = error.get('message') or ''
		except:
			pass
		return {'status_code': response.status_code, 'status': status, 'message': message}

	def _should_try_next_key(self, error_details):
		if not error_details: return False
		if error_details.get('status_code') == 429: return True
		return error_details.get('status') == 'RESOURCE_EXHAUSTED'

	def _parse_response(self, response):
		try:
			text = self._extract_text(response)
			if not text: return None
			try: parsed = json.loads(text)
			except:
				text = text.replace('```json', '').replace('```', '').strip()
				parsed = json.loads(text)
			return self._normalize(parsed)
		except: return None

	def _extract_text(self, response):
		try:
			candidates = response.get('candidates') or []
			for candidate in candidates:
				content = candidate.get('content') or {}
				for part in content.get('parts', []):
					text = part.get('text')
					if text: return text
		except: pass
		return None

	def _normalize(self, data):
		def clean_list(value, limit):
			if not isinstance(value, list): return []
			results = []
			append = results.append
			for item in value:
				try: item = str(item).strip()
				except: continue
				if not item or item in results: continue
				append(item)
				if len(results) == limit: break
			return results
		def int_or_none(value):
			try: return int(value)
			except: return None
		media_type = media_type_aliases.get(str(data.get('media_type', '')).strip().lower(), 'movie')
		year_range = data.get('year_range') or {}
		start_year, end_year = int_or_none(year_range.get('start')), int_or_none(year_range.get('end'))
		if all((start_year, end_year)) and start_year > end_year: start_year, end_year = end_year, start_year
		return {
			'media_type': media_type,
			'genres': clean_list(data.get('genres'), 5),
			'keywords': clean_list(data.get('keywords'), 5),
			'people': clean_list(data.get('people'), 4),
			'tone_descriptors': clean_list(data.get('tone_descriptors'), 5),
			'example_titles': clean_list(data.get('example_titles'), 3),
			'year_range': {'start': start_year, 'end': end_year},
			'exclude_terms': clean_list(data.get('exclude_terms'), 5)
		}
