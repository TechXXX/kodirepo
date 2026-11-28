"""The service modules split out of service.py: state, selector hand-off, languages and AI settings."""
from __future__ import absolute_import

import json
import unittest

from service_fakes import make_core, make_ctx, result

from a4kSubtitles import selector_handoff as selector
from a4kSubtitles.ai_translate import (
    OPENAI_TRANSLATION_MODEL,
    ai_settings,
    ai_translated_subfile_path,
    disable_ai_without_api_key,
)
from a4kSubtitles.runtime_languages import (
    language_code,
    normalize_language_list,
    remove_english_search_languages_for_ai,
    subtitle_result_matches_languages,
)
from a4kSubtitles.service_state import PlaybackState

SOURCE_KEY = 'Show.S01E01.1080p.WEB-DL-GRP|Show S01E01 1080p WEB DL GRP|external|TorBox'


class PlaybackStateTest(unittest.TestCase):
    def test_reset_clears_playback_state_but_keeps_last_subfile(self):
        state = PlaybackState()
        state.last_subfile = '/tmp/a.srt'
        state.has_done_subs_check = True
        state.prev_playing_filename = 'x.mkv'
        state.ai_tries = 2
        state.ai_translation_active = True
        state.attached_subtitle_active = True
        state.sync_started_subfiles.add('url|a.srt')
        state.reset()
        self.assertEqual('/tmp/a.srt', state.last_subfile)
        self.assertFalse(state.has_done_subs_check)
        self.assertEqual('', state.prev_playing_filename)
        self.assertEqual(0, state.ai_tries)
        self.assertFalse(state.ai_translation_active)
        self.assertFalse(state.attached_subtitle_active)
        self.assertEqual(set(), state.sync_started_subfiles)


class SelectorHandoffTest(unittest.TestCase):
    def payload_core(self, payload, source_key=SOURCE_KEY):
        return make_core(properties={
            selector.selector_source_key_prop: source_key,
            selector.selector_payload_prop: json.dumps(payload),
        })

    def test_release_key_ignores_path_extension_and_separators(self):
        self.assertEqual(
            'show s01e01 1080p web dl grp',
            selector.release_key('https://host/dl/Show.S01E01.1080p.WEB-DL-GRP.mkv?token=abc'),
        )

    def test_payload_for_the_playing_video_is_used(self):
        matched = result('Show.S01E01.1080p.WEB-DL-GRP', 'Dutch')
        core = self.payload_core({'source_key': SOURCE_KEY, 'matched_subtitle': matched})
        self.assertEqual((matched, {'source_key': SOURCE_KEY, 'matched_subtitle': matched}),
                         selector.forced_subtitle_result(core))

    def test_stale_payload_is_ignored_and_cleared(self):
        core = self.payload_core({'source_key': 'Other.Show.S02E03|x', 'matched_subtitle': result('x')})
        matched, payload = selector.forced_subtitle_result(core)
        self.assertIsNone(matched)
        self.assertEqual('Other.Show.S02E03|x', payload['source_key'])
        self.assertEqual('', core.kodi.get_property(selector.selector_payload_prop))

    def test_payload_for_another_video_is_ignored(self):
        core = self.payload_core({'source_key': 'Other.Movie.2026.2160p|Other Movie', 'matched_subtitle': result('x')},
                                 source_key='Other.Movie.2026.2160p|Other Movie')
        matched, _payload = selector.forced_subtitle_result(core)
        self.assertIsNone(matched)
        self.assertIn('ignored for non-Fen/current playback', core.logger.text())

    def test_payload_without_service_is_not_used(self):
        core = self.payload_core({'source_key': SOURCE_KEY, 'matched_subtitle': {'name': 'x'}})
        self.assertIsNone(selector.forced_subtitle_result(core)[0])

    def test_direct_playback_url_prefers_the_selector_url_over_a_plugin_url(self):
        core = make_core(properties={selector.selector_playback_url_prop: 'https://cdn.test/video.mkv'})
        core.kodi.playing_file = 'plugin://plugin.video.fenlight.patched/play'
        self.assertEqual('https://cdn.test/video.mkv', selector.direct_playback_url(core))
        core.kodi.properties.clear()
        self.assertEqual('', selector.direct_playback_url(core))

    def test_payload_requires_ai_translation(self):
        self.assertTrue(selector.payload_requires_ai_translation({'requires_ai_translation': True}))
        self.assertFalse(selector.payload_requires_ai_translation(None))


class RuntimeLanguagesTest(unittest.TestCase):
    def test_language_code_and_list(self):
        core = make_core()
        self.assertEqual('nld', language_code(core, 'Dutch'))
        self.assertEqual('', language_code(core, 'none'))
        self.assertEqual(['Dutch', 'English'], normalize_language_list('Dutch, English'))

    def test_english_is_only_removed_from_the_search_when_ai_is_on(self):
        core = make_core()
        self.assertEqual(['Dutch'], remove_english_search_languages_for_ai(core, ['Dutch', 'English'], 'Dutch', True))
        self.assertEqual(['Dutch', 'English'], remove_english_search_languages_for_ai(core, ['Dutch', 'English'], 'Dutch', False))

    def test_result_language_match(self):
        core = make_core()
        self.assertTrue(subtitle_result_matches_languages(core, result('a', 'Dutch'), ['Dutch']))
        self.assertFalse(subtitle_result_matches_languages(core, result('a', 'English'), ['Dutch']))


class AiSettingsTest(unittest.TestCase):
    def test_openai_is_pinned_to_the_translation_model(self):
        core = make_core(settings={'ai_model': 'gpt-4o-mini'})
        self.assertEqual((True, 'OpenAI', 'sk-test', OPENAI_TRANSLATION_MODEL), ai_settings(core, True))
        self.assertEqual(OPENAI_TRANSLATION_MODEL, core.kodi.settings['ai_model'])

    def test_ai_off_or_missing_key_cannot_translate(self):
        self.assertFalse(ai_settings(make_core(), False)[0])
        self.assertFalse(ai_settings(make_core(settings={'ai_api_key': 'empty_setting'}), True)[0])
        self.assertFalse(ai_settings(make_core(settings={'ai_provider': '1', 'ai_model': ''}), True)[0])

    def test_use_ai_is_switched_off_without_a_key(self):
        core = make_core(settings={'ai_api_key': ''})
        self.assertTrue(disable_ai_without_api_key(core))
        self.assertEqual('false', core.kodi.settings['use_ai'])
        self.assertFalse(disable_ai_without_api_key(make_core()))

    def test_translated_file_names(self):
        core = make_core()
        self.assertEqual('/t/Show.translated.nld.srt', ai_translated_subfile_path(core, '/t/Show.eng.srt', 'nld'))
        self.assertEqual('/t/Show.translated.live.nld.srt', ai_translated_subfile_path(core, '/t/Show.eng.srt', 'nld', True))


if __name__ == '__main__':
    unittest.main()
