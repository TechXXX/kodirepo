"""AI translation stops before the next batch when asked to."""
from pathlib import Path
import sys, tempfile, types, unittest
from unittest import mock
THIRD_PARTY = Path(__file__).resolve().parents[1] / 'a4kSubtitles' / 'lib' / 'third_party'
sys.path.insert(0, str(THIRD_PARTY))
import gptsubtrans
from PySubtitle.SubtitleBatcher import SubtitleBatcher
from PySubtitle.SubtitleLine import SubtitleLine
from PySubtitle.SubtitleTranslator import SubtitleTranslator
from PySubtitle.TranslationProvider import TranslationProvider


class StopTests(unittest.TestCase):
    def run_translate(self, should_stop, playback=True):
        class FakeProvider:
            validation_message = ''
            def ValidateSettings(self):
                return True

        def fake_init(translator, options, _provider):
            translator.batcher = SubtitleBatcher(options)
            translator.events = types.SimpleNamespace(preprocessed=lambda _s: None, batch_translated=lambda _b: None, scene_translated=lambda _s: None)
            translator.resume = False; translator.retranslate = False; translator.aborted = False
            translator.max_lines = None; translator.lines_processed = 0; translator.errors = []
            translator.stop_on_error = False; translator.max_history = 0
            translator._get_best_summary = lambda _v: None
            translator.client = types.SimpleNamespace(AbortTranslation=lambda: None)

        attempts = []
        def fake_translate_batch(_translator, batch, _line_numbers, _context):
            attempts.append(batch.number)
            batch.errors = []
            for source in batch.originals:
                translated = SubtitleLine.Construct(source.number, source.start, source.end, 'NL ' + source.text)
                batch.AddTranslatedLine(translated)
                source.translated = translated

        logs = []
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.srt'; output = Path(directory) / 'dutch.srt'
            source.write_text('\n'.join('%d\n00:%02d:00,000 --> 00:%02d:04,000\nLine %d\n' % (n, n * 10, n * 10, n) for n in range(1, 6)), encoding='utf-8')
            with mock.patch.object(TranslationProvider, 'get_provider', return_value=FakeProvider()), \
                    mock.patch.object(SubtitleTranslator, '__init__', fake_init), \
                    mock.patch.object(SubtitleTranslator, 'TranslateBatch', fake_translate_batch):
                result = gptsubtrans.translate(str(source), 'Dutch', str(output), max_batch_size=1, scene_threshold=1000,
                                               priority_seconds=0.0, playback_position=(lambda: 0.0) if playback else None,
                                               log=logs.append, should_stop=should_stop)
            written = output.read_text(encoding='utf-8').count('NL Line') if output.exists() else 0
        return result, attempts, written, logs

    def test_stops_before_the_next_batch_and_saves_what_is_done(self):
        calls = {'n': 0}
        def stop_after_two():
            calls['n'] += 1
            return 'playback stopped' if calls['n'] > 2 else None
        for playback in (True, False):
            with self.subTest(playback_aware=playback):
                calls['n'] = 0
                result, attempts, written, logs = self.run_translate(stop_after_two, playback)
                self.assertEqual('playback stopped', result)
                self.assertEqual(2, len(attempts))
                self.assertEqual(2, written)
                self.assertTrue(any('Translation stopped (playback stopped): attempted 2/5' in line for line in logs), logs[-2:])

    def test_without_a_stop_check_everything_is_translated(self):
        result, attempts, written, logs = self.run_translate(None)
        self.assertIsNone(result)
        self.assertEqual((5, 5), (len(attempts), written))
        self.assertTrue(any('Translation finished: attempted 5/5' in line for line in logs))

    def test_a_failing_stop_check_does_not_stop_translation(self):
        def broken():
            raise RuntimeError('player gone')
        result, attempts, written, logs = self.run_translate(broken)
        self.assertIsNone(result)
        self.assertEqual(5, written)
        self.assertTrue(any('stop check failed' in line for line in logs))


if __name__ == '__main__':
    unittest.main()
