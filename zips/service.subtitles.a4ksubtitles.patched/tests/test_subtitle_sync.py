from __future__ import absolute_import

import json
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
ADDON_ROOT = os.path.dirname(HERE)
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)

os.environ.setdefault('A4KSUBTITLES_API_MODE', '{"kodi": true}')

from a4kSubtitles.subtitle_sync import find_offset, retime_srt, subtitle_starts
from a4kSubtitles.lib import kodi


class SubtitleSyncTest(unittest.TestCase):
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

    def test_srt_retime_preserves_body_and_moves_cues(self):
        source = '1\n00:00:07,133 --> 00:00:08,000\nTest line\n'
        shifted = retime_srt(source, 1000)
        self.assertEqual([8133], subtitle_starts(shifted))
        self.assertIn('Test line', shifted)

    def test_existing_profiles_are_migrated_to_explicit_opt_in_once(self):
        kodi.set_setting('migration.auto_sync_subtitles_opt_in_v1', '')
        kodi.set_setting('general', 'auto_sync_subtitles', 'true')
        self.assertTrue(kodi.migrate_auto_sync_subtitles_to_opt_in())
        self.assertFalse(kodi.get_bool_setting('general', 'auto_sync_subtitles'))

        kodi.set_setting('general', 'auto_sync_subtitles', 'true')
        self.assertFalse(kodi.migrate_auto_sync_subtitles_to_opt_in())
        self.assertTrue(kodi.get_bool_setting('general', 'auto_sync_subtitles'))


if __name__ == '__main__':
    unittest.main()
