"""The embedded-track wait ends once Kodi lists the video's tracks; timing reads still start 5 s in."""
from __future__ import absolute_import

import json
import types
import unittest
from unittest import mock

from service_fakes import embedded, make_ctx, result, srt, timeline

from a4kSubtitles import ai_source_timing, selector_handoff as selector, subtitle_attach
from a4kSubtitles.timing_rules import TIMING_READ_START_DELAY_SECONDS

PLAYING = timeline(seed=1)
KEY = 'Show.S01E01.1080p.WEB-DL-GRP|Show S01E01'
ENGLISH = {'index': 0, 'language': 'eng', 'name': 'English', 'isforced': False, 'isimpaired': False}
DUTCH_SIDECAR = {'index': 1, 'language': 'nld', 'name': 'Dutch (External)', 'isforced': False, 'isimpaired': False}


def started_ctx(**kwargs):
    """A video that started at 1000.0 and is now 1.5 s in, still inside the 5-second wait."""
    ctx = make_ctx(**kwargs)
    ctx.core.time = types.SimpleNamespace(time=lambda: 1001.5)
    ctx.state.playback_started_at = 1000.0
    ctx.state.subtitle_stream_settle_until = 1005.0
    return ctx


def selector_ctx():
    return started_ctx(properties={
        selector.selector_source_key_prop: KEY,
        selector.selector_payload_prop: json.dumps({'source_key': KEY, 'matched_subtitle': result('Show.S01E01.nld', 'Dutch')}),
    })


class EmbeddedWaitTest(unittest.TestCase):
    def attach(self, ctx):
        with mock.patch.object(subtitle_attach, 'download_and_attach_result', return_value=True) as download:
            subtitle_attach.attach_runtime_subtitle(ctx, False, '', '', '')
        return download

    def test_listed_embedded_tracks_end_the_wait_and_the_selector_sub_is_used(self):
        ctx = selector_ctx()
        ctx.core.kodi.player_subtitles = [ENGLISH]
        self.attach(ctx).assert_called_once()
        self.assertTrue(ctx.state.embedded_wait_over)
        self.assertIn('Embedded-track wait ended early', ctx.core.logger.text())
        self.assertIn('waited=1.5s', ctx.core.logger.text())

    def test_audio_alone_ends_the_wait_for_a_video_without_subtitle_tracks(self):
        ctx = selector_ctx()
        ctx.core.kodi.audio_streams = ['eng']
        self.attach(ctx).assert_called_once()

    def test_nothing_listed_yet_keeps_waiting(self):
        ctx = selector_ctx()
        self.attach(ctx).assert_not_called()
        self.assertFalse(ctx.state.has_done_subs_check)

    def test_a_sidecar_alone_does_not_end_the_wait(self):
        ctx = selector_ctx()
        ctx.core.kodi.player_subtitles = [DUTCH_SIDECAR]
        self.attach(ctx).assert_not_called()
        self.assertIsNone(ctx.core.kodi.selected_stream)

    def test_ts_and_m2ts_videos_wait_the_full_five_seconds(self):
        for name in ('Movie.2026.BluRay.Remux.m2ts', 'Channel.Recording.ts'):
            ctx = selector_ctx()
            ctx.core.kodi.playing_file = 'https://example.test/' + name + '?token=x'
            ctx.core.kodi.player_subtitles = [ENGLISH]
            ctx.core.kodi.audio_streams = ['eng']
            self.attach(ctx).assert_not_called()
            self.assertIn('Embedded-track wait kept', ctx.core.logger.text())

    def test_the_wait_still_ends_after_five_seconds(self):
        ctx = selector_ctx()
        ctx.core.time = types.SimpleNamespace(time=lambda: 1005.0)
        self.attach(ctx).assert_called_once()

    def test_dutch_sidecar_is_accepted_once_the_video_tracks_are_listed(self):
        ctx = started_ctx()
        ctx.core.kodi.player_subtitles = [ENGLISH, DUTCH_SIDECAR]
        self.assertTrue(subtitle_attach.update_sub_stream(ctx, 'Dutch', False, False))
        self.assertEqual(1, ctx.core.kodi.selected_stream)

    def test_dutch_sidecar_still_waits_while_only_it_is_listed(self):
        ctx = started_ctx()
        ctx.core.kodi.player_subtitles = [DUTCH_SIDECAR]
        self.assertIsNone(subtitle_attach.update_sub_stream(ctx, 'Dutch', False, False))
        self.assertIn('Waiting for an embedded Dutch subtitle', ctx.core.logger.text())


class TimingReadDelayTest(unittest.TestCase):
    def test_ai_source_check_waits_until_five_seconds_after_start(self):
        ctx = started_ctx()
        subfile = ctx.core.utils.temp_dir + '/selected.eng.srt'
        with open(subfile, 'w', encoding='utf-8') as handle:
            handle.write(srt(PLAYING))
        with mock.patch.object(ai_source_timing, 'embedded_cue_candidates', return_value=embedded(PLAYING)):
            self.assertEqual(subfile, ai_source_timing.timing_checked_ai_source(ctx, subfile, result('selected'), 'English'))
        self.assertEqual([TIMING_READ_START_DELAY_SECONDS - 1.5], ctx.monitor.waits)

    def test_no_translation_when_playback_stops_during_the_delay(self):
        ctx = started_ctx()
        subfile = ctx.core.utils.temp_dir + '/selected.eng.srt'
        with open(subfile, 'w', encoding='utf-8') as handle:
            handle.write(srt(PLAYING))

        def stop_playback(_seconds):
            ctx.core.kodi.playing = False
            return False
        ctx.monitor.waitForAbort = stop_playback
        with mock.patch.object(ai_source_timing, 'embedded_cue_candidates') as probe:
            self.assertIsNone(ai_source_timing.timing_checked_ai_source(ctx, subfile, result('selected'), 'English'))
        probe.assert_not_called()

    def test_stopped_playback_means_the_english_fallback_is_not_translated(self):
        ctx = started_ctx(files={'Show.S01E01.eng': srt(PLAYING)})
        with mock.patch.object(subtitle_attach, 'timing_checked_ai_source', return_value=None), \
                mock.patch.object(subtitle_attach, 'translate_and_attach_subfile') as translate:
            self.assertTrue(subtitle_attach.download_and_attach_result(
                ctx, result('Show.S01E01.eng'), 'English', 'Dutch', True, 'OpenAI', 'k', 'm', True))
        translate.assert_not_called()

    def test_background_sync_reads_the_timing_only_five_seconds_after_start(self):
        from a4kSubtitles import background_sync

        class InlineThread(object):
            def __init__(self, target, name=''):
                self.target = target

            def start(self):
                self.target()
        ctx = started_ctx()
        subfile = ctx.core.utils.temp_dir + '/Show.S01E01.nld.srt'
        with open(subfile, 'w', encoding='utf-8') as handle:
            handle.write(srt(PLAYING))
        with mock.patch.object(background_sync.threading, 'Thread', InlineThread), \
                mock.patch.object(background_sync, 'embedded_cue_candidates', return_value=embedded(PLAYING)):
            background_sync.start_background_subtitle_sync(ctx, subfile, result('Show.S01E01.nld', 'Dutch'))
        self.assertEqual([TIMING_READ_START_DELAY_SECONDS - 1.5], ctx.monitor.waits)
        self.assertIn('subtitle already aligned', ctx.core.logger.text())

    def test_no_delay_once_five_seconds_have_passed(self):
        ctx = started_ctx()
        ctx.core.time = types.SimpleNamespace(time=lambda: 1007.0)
        from a4kSubtitles.timing_rules import wait_before_timing_reads
        self.assertTrue(wait_before_timing_reads(ctx.core, ctx.monitor, ctx.state.playback_started_at, 'x'))
        self.assertEqual([], ctx.monitor.waits)


if __name__ == '__main__':
    unittest.main()
