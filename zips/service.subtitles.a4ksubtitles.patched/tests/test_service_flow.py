"""End-to-end paths through the split service modules, with a fake Kodi and fake translator."""
from __future__ import absolute_import

import os
import types
import unittest
from unittest import mock

from service_fakes import embedded, make_ctx, result, srt, timeline

from a4kSubtitles import ai_source_timing, subtitle_attach
from a4kSubtitles.ai_translate import translate_and_attach_subfile, translate_next_chunk

PLAYING = timeline(seed=1)


class FakeTranslator(object):
    def __init__(self, stop_reason=None, error=None):
        self.calls = []
        self.stop_reason = stop_reason
        self.error = error

    def translate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        with open(kwargs['output_file'], 'w', encoding='utf-8') as handle:
            handle.write(srt(PLAYING))
        return self.stop_reason


def write(ctx, name, starts):
    path = os.path.join(ctx.core.utils.temp_dir, name)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(srt(starts))
    return path


class AiSourceTimingTest(unittest.TestCase):
    def check(self, ctx, subfile, reference):
        with mock.patch.object(ai_source_timing, 'embedded_cue_candidates', return_value=reference):
            return ai_source_timing.timing_checked_ai_source(ctx, subfile, result('selected'), 'English')

    def test_aligned_source_is_translated_as_is(self):
        ctx = make_ctx()
        subfile = write(ctx, 'selected.eng.srt', PLAYING)
        self.assertEqual(subfile, self.check(ctx, subfile, embedded(PLAYING)))
        self.assertIn('source matches embedded timing', ctx.core.logger.text())

    def test_shifted_source_gets_a_retimed_copy(self):
        ctx = make_ctx()
        subfile = write(ctx, 'selected.eng.srt', [start - 2000 for start in PLAYING])
        chosen = self.check(ctx, subfile, embedded(PLAYING))
        self.assertTrue(chosen.endswith('.autosync.plus2000ms.srt'), chosen)
        self.assertTrue(os.path.exists(chosen))

    def test_mismatched_source_is_replaced_by_a_matching_alternative(self):
        ctx = make_ctx(files={'other-episode': srt(timeline(seed=7)), 'right-release': srt(PLAYING)},
                       results=[result('selected'), result('other-episode'), result('right-release')])
        subfile = write(ctx, 'selected.eng.srt', timeline(seed=9))
        chosen = self.check(ctx, subfile, embedded(PLAYING))
        self.assertTrue(chosen.endswith('right-release.srt'), chosen)
        self.assertEqual(['other-episode', 'right-release'], ctx.api.downloads)
        self.assertFalse(os.path.exists(os.path.join(ctx.core.utils.temp_dir, 'other-episode.srt')))

    def test_no_match_anywhere_keeps_the_selected_subtitle(self):
        ctx = make_ctx(files={'other': srt(timeline(seed=7))}, results=[result('other')])
        subfile = write(ctx, 'selected.eng.srt', timeline(seed=9))
        self.assertEqual(subfile, self.check(ctx, subfile, embedded(PLAYING)))
        self.assertIn('translating the selected one anyway', ctx.core.logger.text())

    def test_too_little_evidence_or_sync_off_keeps_the_subtitle(self):
        ctx = make_ctx()
        subfile = write(ctx, 'selected.eng.srt', timeline(seed=9))
        self.assertEqual(subfile, self.check(ctx, subfile, embedded(PLAYING[:5])))
        ctx.core.kodi.settings['auto_sync_subtitles'] = False
        self.assertEqual(subfile, self.check(ctx, subfile, embedded(PLAYING)))


class TranslateTest(unittest.TestCase):
    def test_full_file_translation_attaches_and_marks_the_video_done(self):
        ctx = make_ctx()
        translator = FakeTranslator()
        ctx.core.utils.gptsubtrans = translator
        subfile = write(ctx, 'Show.eng.srt', PLAYING)
        self.assertTrue(translate_and_attach_subfile(
            ctx, subfile, 'Dutch', 'OpenAI', 'sk-test', 'gpt-6-luna', 'test', 'downloaded_english_full', True))
        call = translator.calls[0]
        self.assertIsNone(call['begin_seconds'])
        self.assertEqual(120.0, call['priority_seconds'])
        self.assertIsNotNone(call['should_stop'])
        self.assertTrue(ctx.core.kodi.attached[-1].endswith('Show.translated.nld.srt'))
        self.assertTrue(ctx.state.has_done_subs_check)
        self.assertFalse(ctx.state.ai_translation_active)
        self.assertEqual('downloaded_english_full', ctx.state.ai_translation_source)
        self.assertEqual(subfile, ctx.state.last_subfile)

    def test_stopped_translation_attaches_nothing(self):
        ctx = make_ctx()
        ctx.core.utils.gptsubtrans = FakeTranslator(stop_reason='playback stopped')
        subfile = write(ctx, 'Show.eng.srt', PLAYING)
        self.assertTrue(translate_and_attach_subfile(ctx, subfile, 'Dutch', 'OpenAI', 'k', 'm', 'test', '', True))
        self.assertEqual([], ctx.core.kodi.attached)
        self.assertFalse(ctx.state.has_done_subs_check)

    def test_stop_check_reports_playback_stopped(self):
        ctx = make_ctx()
        translator = FakeTranslator()
        ctx.core.utils.gptsubtrans = translator
        subfile = write(ctx, 'Show.eng.srt', PLAYING)
        translate_and_attach_subfile(ctx, subfile, 'Dutch', 'OpenAI', 'k', 'm', 'test', '', True)
        should_stop = translator.calls[0]['should_stop']
        self.assertIsNone(should_stop())
        ctx.core.kodi.playing_file = 'https://example.test/Another.Video.mkv'
        self.assertEqual('a different video is playing', should_stop())
        ctx.core.kodi.playing = False
        self.assertEqual('playback stopped', should_stop())

    def test_chunk_translation_gives_up_after_three_failures(self):
        ctx = make_ctx()
        ctx.core.utils.gptsubtrans = FakeTranslator(error=RuntimeError('network'))
        subfile = write(ctx, 'Show.eng.srt', PLAYING)
        self.assertTrue(translate_next_chunk(ctx, subfile, 'OpenAI', 'k', 'm'))
        self.assertTrue(translate_next_chunk(ctx, subfile, 'OpenAI', 'k', 'm'))
        self.assertFalse(translate_next_chunk(ctx, subfile, 'OpenAI', 'k', 'm'))
        self.assertEqual(3, ctx.state.ai_tries)


class AttachTest(unittest.TestCase):
    def test_dutch_result_is_attached_directly_and_synced_in_the_background(self):
        ctx = make_ctx(files={'Show.S01E01.nld': srt(PLAYING)})
        with mock.patch.object(subtitle_attach, 'start_background_subtitle_sync') as sync, \
                mock.patch.object(subtitle_attach, 'translate_and_attach_subfile') as translate:
            self.assertTrue(subtitle_attach.download_and_attach_result(
                ctx, result('Show.S01E01.nld', 'Dutch'), 'Dutch', 'Dutch', False, '', '', ''))
        self.assertTrue(ctx.core.kodi.attached[-1].endswith('Show.S01E01.nld.srt'))
        self.assertTrue(ctx.state.attached_subtitle_active)
        sync.assert_called_once()
        translate.assert_not_called()

    def test_english_fallback_is_timing_checked_then_translated_as_a_full_file(self):
        ctx = make_ctx(files={'Show.S01E01.eng': srt(PLAYING)})
        with mock.patch.object(subtitle_attach, 'timing_checked_ai_source', side_effect=lambda _c, path, _r, _l: path) as check, \
                mock.patch.object(subtitle_attach, 'translate_and_attach_subfile', return_value=True) as translate:
            self.assertTrue(subtitle_attach.download_and_attach_result(
                ctx, result('Show.S01E01.eng'), 'English', 'Dutch', True, 'OpenAI', 'k', 'm', True))
        check.assert_called_once()
        args = translate.call_args[0]
        self.assertEqual(('Dutch', 'OpenAI', 'k', 'm', 'downloaded subtitle fallback', 'downloaded_english_full', True), args[2:])

    def test_existing_dutch_stream_wins_over_the_selector_english_fallback(self):
        import json
        from a4kSubtitles import selector_handoff as selector
        key = 'Show.S01E01.1080p.WEB-DL-GRP|Show S01E01'
        ctx = make_ctx(properties={
            selector.selector_source_key_prop: key,
            selector.selector_payload_prop: json.dumps({
                'source_key': key, 'requires_ai_translation': True, 'matched_subtitle': result('Show.S01E01.eng')}),
        })
        ctx.core.kodi.player_subtitles = [
            {'index': 0, 'language': 'eng', 'name': 'English', 'isforced': False, 'isimpaired': False},
            {'index': 1, 'language': 'nld', 'name': 'Dutch (External)', 'isforced': False, 'isimpaired': False},
        ]
        # The Dutch stream the player already has is picked before the selector's English fallback is used.
        with mock.patch.object(subtitle_attach, 'download_and_attach_result') as download:
            subtitle_attach.attach_runtime_subtitle(ctx, True, 'OpenAI', 'k', 'm')
        download.assert_not_called()
        self.assertEqual(1, ctx.core.kodi.selected_stream)



class ServiceLoopTest(unittest.TestCase):
    def test_poll_loop_attaches_the_selector_dutch_subtitle_once(self):
        import json
        from a4kSubtitles import selector_handoff as selector
        from a4kSubtitles import service
        from service_fakes import Monitor
        key = 'Show.S01E01.1080p.WEB-DL-GRP|Show S01E01'
        ctx = make_ctx(files={'Show.S01E01.nld': srt(PLAYING)}, properties={
            selector.selector_source_key_prop: key,
            selector.selector_payload_prop: json.dumps({
                'source_key': key, 'matched_subtitle': result('Show.S01E01.nld', 'Dutch')}),
        })
        ctx.core.kodi.monitor = Monitor(polls=12)
        # Each poll is a second later, so the 5-second wait for an embedded Dutch track runs out.
        clock = {'now': 1000.0}

        def tick():
            clock['now'] += 1.0
            return clock['now']
        ctx.core.time = types.SimpleNamespace(time=tick)
        # start() clears the temp folder; keep it so the fake download can write there.
        ctx.core.shutil = types.SimpleNamespace(rmtree=lambda *_args, **_kwargs: None)
        with mock.patch.object(subtitle_attach, 'start_background_subtitle_sync') as sync:
            service.start(ctx.api)
        sync.assert_called_once()
        self.assertEqual(['Show.S01E01.nld'], ctx.api.downloads)
        self.assertTrue(ctx.core.kodi.attached[-1].endswith('Show.S01E01.nld.srt'))


if __name__ == '__main__':
    unittest.main()
