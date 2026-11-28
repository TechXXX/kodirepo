# -*- coding: utf-8 -*-
"""Language helpers for the playback service."""


def normalize_language_list(value):
    if isinstance(value, str):
        values = value.split(',') if ',' in value else [value]
    else:
        values = list(value or [])
    return [str(item).strip() for item in values if item not in (None, '', 'none')]


def language_code(core, value):
    """ISO 639-2 code for a Kodi language name or code, '' for none."""
    if value in (None, '', 'none'):
        return ''
    value = str(value).strip()
    if not value:
        return ''
    return core.utils.get_lang_id(value, core.kodi.xbmc.ISO_639_2) or value.lower()


def subtitle_result_matches_languages(core, result, languages):
    action_args = result.get('action_args') or {}
    allowed_codes = {language_code(core, value) for value in languages}
    result_codes = {
        language_code(core, value)
        for value in (
            result.get('lang'),
            result.get('lang_code'),
            action_args.get('lang'),
            action_args.get('language'),
        )
    }
    allowed_codes.discard('')
    result_codes.discard('')
    return not allowed_codes or not result_codes or bool(allowed_codes & result_codes)


def remove_english_search_languages_for_ai(core, languages, preferredlang, use_ai):
    if not use_ai or language_code(core, preferredlang) == 'eng':
        return languages
    filtered = [language for language in languages if language_code(core, language) != 'eng']
    if len(filtered) != len(languages):
        core.logger.debug('Removed English search language while AI translation is enabled')
    return filtered or ([preferredlang] if preferredlang else filtered)
