from __future__ import absolute_import

import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

HERE = os.path.dirname(__file__)
ADDON_ROOT = os.path.dirname(HERE)
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)

os.environ.setdefault('A4KSUBTITLES_API_MODE', '{"kodi": true}')

from a4kSubtitles import subtitle_sync
from a4kSubtitles.subtitle_sync import _is_english, _is_sdh, _spread_cluster_positions, _tracks, find_best_offset, find_offset, retime_srt, subtitle_starts
from a4kSubtitles.service import _autosync_path, _best_embedded_match, _fallback_match_is_confirmed, _fallback_match_rank, _offset_to_apply
from a4kSubtitles.lib import kodi


class SubtitleSyncTest(unittest.TestCase):
    def test_low_index_sampling_spreads_across_the_whole_timeline(self):
        positions = list(range(120))
        sampled = _spread_cluster_positions(positions)
        self.assertLessEqual(len(sampled), 72)
        self.assertLess(min(sampled), 6)
        self.assertGreater(max(sampled), 114)
        self.assertTrue(any(54 <= value <= 66 for value in sampled))
        self.assertEqual(24, len(sampled[:24]))
        self.assertLess(min(sampled[:24]), 6)
        self.assertGreater(max(sampled[:24]), 114)

    def test_ten_indexed_starts_still_trigger_cluster_sampling(self):
        class Reader(object):
            def __init__(self, source):
                pass

            def read(self, offset, length):
                return b'\x1aE\xdf\xa3'

        with patch.object(subtitle_sync, 'RangeReader', Reader), \
             patch.object(subtitle_sync, '_first', return_value=(0, 0, 0)), \
             patch.object(subtitle_sync, '_seek_positions', return_value={}), \
             patch.object(subtitle_sync, '_tracks', return_value=[{'number': 3, 'language': 'en', 'name': ''}]), \
             patch.object(subtitle_sync, '_cue_times', return_value=list(range(10))), \
             patch.object(subtitle_sync, '_cue_cluster_positions', return_value=[100, 200]), \
             patch.object(subtitle_sync, '_sample_cluster_times', return_value=list(range(10, 16))) as sample:
            candidates = subtitle_sync.embedded_cue_candidates('example.mkv')
        sample.assert_called_once()
        self.assertEqual(16, len(candidates[0]['starts']))

    def test_range_window_reads_subtitle_cues_from_multiple_clusters(self):
        def cluster(timecode):
            payload = (
                b'\xe7\x82' + bytes((timecode >> 8, timecode & 255)) +
                b'\xa3\x84\x83\x00\x00\x80'
            )
            return b'\x1f\x43\xb6\x75' + bytes((0x80 | len(payload),)) + payload

        window = cluster(1000) + cluster(2000)
        self.assertEqual([1000, 2000], subtitle_sync._cluster_times(window, 3, 1000000))

    def test_tracks_reads_languageietf_and_sdh_name(self):
        entry = (
            b'\xd7\x81\x03'  # TrackNumber = 3
            b'\x83\x81\x11'  # TrackType = subtitle
            b'\x86\x8bS_TEXT/UTF8'
            b'\x22\xb5\x9d\x82en'  # LanguageIETF
            b'\x53\x6e\x83SDH'  # Name
        )
        data = b'\x16\x54\xae\x6b\xa1\xae\x9f' + entry
        tracks = _tracks(data)
        self.assertEqual(1, len(tracks))
        self.assertEqual('en', tracks[0]['language'])
        self.assertEqual('SDH', tracks[0]['name'])

    def test_tracks_uses_matroska_english_default_when_language_is_absent(self):
        payload = b'\xd7\x81\x03\x83\x81\x11\x86\x8bS_TEXT/UTF8'
        entry = b'\xae' + bytes((0x80 | len(payload),)) + payload
        data = b'\x16\x54\xae\x6b' + bytes((0x80 | len(entry),)) + entry
        self.assertEqual('eng', _tracks(data)[0]['language'])

    def test_languageietf_wins_even_when_legacy_language_follows_it(self):
        payload = (
            b'\xd7\x81\x03\x83\x81\x11\x86\x8bS_TEXT/UTF8'
            b'\x22\xb5\x9d\x82en'
            b'\x22\xb5\x9c\x83ger'
        )
        entry = b'\xae' + bytes((0x80 | len(payload),)) + payload
        data = b'\x16\x54\xae\x6b' + bytes((0x80 | len(entry),)) + entry
        self.assertEqual('en', _tracks(data)[0]['language'])

    def test_undefined_language_can_use_explicit_english_track_name(self):
        self.assertTrue(_is_english({'language': 'und', 'name': 'English [CC]'}))
        self.assertTrue(_is_sdh({'name': 'English [CC]'}))
        self.assertTrue(_is_english({'language': 'und', 'name': 'ENG Forced'}))
        self.assertFalse(_is_english({'language': 'und', 'name': 'Englishman'}))
        self.assertFalse(_is_english({'language': 'dut', 'name': 'English [CC]'}))

    def test_best_offset_prefers_non_sdh_only_on_an_equal_match(self):
        target = [0, 2236, 6340, 8108, 15349, 18318, 20888, 23957, 25826, 28962, 32533, 35885]
        reference = [value + 8000 for value in target]
        result = find_best_offset([
            {'starts': reference, 'track_number': 4, 'track_name': 'English SDH', 'is_sdh': True},
            {'starts': reference, 'track_number': 3, 'track_name': 'English', 'is_sdh': False},
        ], target)
        self.assertIsNotNone(result)
        self.assertEqual(8000, result['offset_ms'])
        self.assertEqual(3, result['track_number'])

    def test_best_offset_keeps_a_materially_stronger_sdh_match(self):
        target = [0, 2236, 6340, 8108, 15349, 18318, 20888, 23957, 25826, 28962, 32533, 35885]
        result = find_best_offset([
            {'starts': [value + 8000 for value in target], 'track_number': 4, 'track_name': 'English SDH', 'is_sdh': True},
            {'starts': [value + 8000 for value in target[:7]], 'track_number': 3, 'track_name': 'English', 'is_sdh': False},
        ], target)
        self.assertIsNotNone(result)
        self.assertEqual(4, result['track_number'])

    def test_service_prefers_comparable_normal_english_over_sdh(self):
        target = [0, 2236, 6340, 8108, 15349, 18318, 20888, 23957, 25826, 28962, 32533, 35885]
        reference = [value + 8000 for value in target]
        tracks = [
            {'starts': reference, 'track_number': 4, 'track_name': 'English SDH', 'is_sdh': True},
            {'starts': reference[:-1], 'track_number': 3, 'track_name': 'English', 'is_sdh': False},
        ]
        self.assertEqual(3, _best_embedded_match(tracks, target)['track_number'])
        tracks[1]['starts'] = reference[:8]
        self.assertEqual(4, _best_embedded_match(tracks, target)['track_number'])

    def test_ordered_matcher_discards_split_cues_and_finds_the_shared_timeline(self):
        # The Dutch track has one extra cue between each matching event, and
        # each real partner is jittered by 200 ms. Exact-start voting splits
        # the evidence between 800 and 1200 ms; ordered matching keeps only
        # one-to-one neighbours and recovers the 1000 ms global delay.
        reference = [5000, 9200, 14200, 18000, 23500, 29000, 35000, 39700, 45000, 51000, 57200, 64000]
        target = []
        for index, value in enumerate(reference):
            target.append(value - 1000 + (200 if index % 2 else -200))
            if index < len(reference) - 1:
                # Extra translated-caption boundaries vary by sentence, so
                # they must not form a competing fixed-offset timeline.
                target.append(value + 100 + (index % 5) * 350)
        result = find_offset(reference, sorted(target))
        self.assertIsNotNone(result)
        self.assertEqual('ordered', result['method'])
        self.assertEqual(1000, result['offset_ms'])
        self.assertEqual(len(reference), result['matched_cues'])

    def test_californication_s04e05_timing_profile_detects_one_second_delay(self):
        # Derived from the local Californication S04E05 manual regression pair.
        # Numeric cue timing is sufficient: no episode video or subtitle text is
        # stored in the repository.
        fixture_path = os.path.join(HERE, 'fixtures', 'californication_s04e05_timing.json')
        with open(fixture_path, 'r') as handle:
            fixture = json.load(handle)
        result = find_offset(fixture['embedded_start_ms'], fixture['external_start_ms'])
        self.assertIsNotNone(result)
        self.assertEqual(fixture['expected_offset_ms'], result['offset_ms'])
        self.assertEqual(16, result['matched_cues'])

    def test_ambiguous_timeline_is_left_unchanged(self):
        reference = list(range(1000, 26000, 1000))
        target = list(range(500, 25500, 1000))
        self.assertIsNone(find_offset(reference, target))

    def test_sparse_embedded_samples_can_confirm_a_fixed_offset(self):
        # Representative timing samples from Californication S04E06.  A
        # front-loaded bounded Cluster scan finds these early English cues;
        # their Dutch counterparts consistently need an eight-second delay.
        reference = [8008, 10218, 13138, 15473, 17892, 23356, 24733, 28862, 33783]
        target = [0, 2236, 6340, 8108, 15349, 18318, 20888, 23957, 25826, 28962, 32533, 35885]
        result = find_offset(reference, target)
        self.assertIsNotNone(result)
        self.assertEqual(8000, result['offset_ms'])

    def test_fallback_replacement_requires_a_strong_timing_match(self):
        self.assertTrue(_fallback_match_is_confirmed({
            'matched_cues': 8,
            'mean_abs_residual_ms': 250,
        }))
        self.assertFalse(_fallback_match_is_confirmed({
            'matched_cues': 7,
            'mean_abs_residual_ms': 1,
        }))
        self.assertFalse(_fallback_match_is_confirmed({
            'matched_cues': 8,
            'mean_abs_residual_ms': 251,
        }))
        self.assertFalse(_fallback_match_is_confirmed({
            'matched_cues': 7,
            'mean_abs_residual_ms': 20,
            'offset_ms': -26700,
        }))
        self.assertFalse(_fallback_match_is_confirmed({
            'method': 'histogram',
            'matched_cues': 12,
            'median_residual_ms': 0,
        }))

    def test_equal_timing_fits_prefer_the_subtitle_needing_less_shift(self):
        nogrp = {'matched_cues': 22, 'mean_abs_residual_ms': 146, 'offset_ms': 200}
        immerse = {'matched_cues': 22, 'mean_abs_residual_ms': 146, 'offset_ms': 8500}
        self.assertGreater(_fallback_match_rank(nogrp), _fallback_match_rank(immerse))

    def test_small_offset_requires_material_gain_over_zero(self):
        # S01E01's dense timeline makes 300 ms win by a few pairs even though
        # the zero-offset residual is lower. NoGRP's sparse probe similarly
        # reports 200 ms while the full-file comparison puts it at zero.
        self.assertEqual(0, _offset_to_apply({
            'offset_ms': 300, 'matched_cues': 260, 'mean_abs_residual_ms': 197,
            'zero_offset_matches': 249, 'zero_offset_mean_abs_residual_ms': 193,
        }))
        self.assertEqual(0, _offset_to_apply({
            'offset_ms': 200, 'matched_cues': 22, 'mean_abs_residual_ms': 146,
            'zero_offset_matches': 18, 'zero_offset_mean_abs_residual_ms': 185,
        }))
        self.assertEqual(250, _offset_to_apply({
            'offset_ms': 250, 'matched_cues': 20, 'mean_abs_residual_ms': 40,
            'zero_offset_matches': 19, 'zero_offset_mean_abs_residual_ms': 240,
        }))

    def test_srt_retime_preserves_body_and_moves_cues(self):
        source = '1\n00:00:07,133 --> 00:00:08,000\nTest line\n'
        shifted = retime_srt(source, 1000)
        self.assertEqual([8133], subtitle_starts(shifted))
        self.assertIn('Test line', shifted)

    def test_autosync_filename_spells_out_offset_direction(self):
        self.assertEqual('sub.autosync.minus600ms.srt', _autosync_path('sub.srt', -600))
        self.assertEqual('sub.autosync.plus600ms.srt', _autosync_path('sub.srt', 600))

    def test_auto_sync_defaults_on_and_migrates_existing_profiles_once(self):
        settings = ET.parse(os.path.join(ADDON_ROOT, 'resources', 'settings.xml'))
        setting = settings.find(".//setting[@id='general.auto_sync_subtitles']")
        self.assertEqual('true', setting.findtext('default'))
        kodi.set_setting('migration.auto_sync_subtitles_default_on_v1', '')
        kodi.set_setting('general', 'auto_sync_subtitles', 'false')
        self.assertTrue(kodi.migrate_auto_sync_subtitles_default_on())
        self.assertTrue(kodi.get_bool_setting('general', 'auto_sync_subtitles'))
        self.assertTrue(kodi.get_bool_setting('migration.auto_sync_subtitles_default_on_v1'))

        kodi.set_setting('general', 'auto_sync_subtitles', 'false')
        self.assertFalse(kodi.migrate_auto_sync_subtitles_default_on())
        self.assertFalse(kodi.get_bool_setting('general', 'auto_sync_subtitles'))


if __name__ == '__main__':
    unittest.main()
