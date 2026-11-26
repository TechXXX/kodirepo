"""Regression cases from live AI subtitle numbering and seek failures."""

from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


THIRD_PARTY = Path(__file__).resolve().parents[1] / 'a4kSubtitles' / 'lib' / 'third_party'
sys.path.insert(0, str(THIRD_PARTY))

import gptsubtrans
from PySubtitle.Instructions import DEFAULT_TASK_TYPE
from PySubtitle.Options import Options
from PySubtitle.SubtitleBatch import SubtitleBatch
from PySubtitle.SubtitleBatcher import SubtitleBatcher
from PySubtitle.SubtitleLine import SubtitleLine
from PySubtitle.SubtitleTranslator import SubtitleTranslator
from PySubtitle.Translation import Translation
from PySubtitle.TranslationParser import TranslationParser
from PySubtitle.TranslationProvider import TranslationProvider


class AiTranslationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.options = Options({'target_language': 'Dutch', 'provider': 'OpenAI'})

    def make_batch(self, sources):
        batch = SubtitleBatch({'scene': 1, 'number': 1})
        batch.originals = [
            SubtitleLine.Construct(number, '00:00:%02d,000' % index,
                                   '00:00:%02d,000' % (index + 1), text)
            for index, (number, text) in enumerate(sources)
        ]
        return batch

    def process_batch(self, sources, response):
        batch = self.make_batch(sources)
        translator = SubtitleTranslator.__new__(SubtitleTranslator)
        translator.client = types.SimpleNamespace(
            GetParser=lambda task: TranslationParser(task, self.options)
        )
        translator.task_type = DEFAULT_TASK_TYPE
        translator.max_lines = None
        translator.substitutions = None
        translator.postprocessor = None
        translator.ProcessBatchTranslation(batch, Translation({'text': response}), None)
        return batch

    def test_misnumbered_cue_recovers_from_unique_source_text(self):
        batch = self.process_batch(
            [(1678, 'Alpha'), (1679, 'Bravo')],
            '#1698\nOriginal>\nAlpha\nTranslation>\nAlfa\n\n'
            '#1679\nOriginal>\nBravo\nTranslation>\nBravo NL\n',
        )
        self.assertTrue(batch.all_translated)
        self.assertEqual([], batch.errors)
        self.assertEqual([1678, 1679], [line.number for line in batch.translated])

    def test_swapped_and_duplicate_response_numbers_do_not_steal_cues(self):
        for response in (
            '#1679\nOriginal>\nAlpha\nTranslation>\nAlfa\n\n'
            '#1678\nOriginal>\nBravo\nTranslation>\nBravo NL\n',
            '#1679\nOriginal>\nAlpha\nTranslation>\nAlfa\n\n'
            '#1679\nOriginal>\nBravo\nTranslation>\nBravo NL\n',
        ):
            with self.subTest(response=response):
                batch = self.process_batch([(1678, 'Alpha'), (1679, 'Bravo')], response)
                self.assertTrue(batch.all_translated)
                self.assertEqual([], batch.errors)
                self.assertEqual(['Alfa', 'Bravo NL'],
                                 [line.text.strip() for line in batch.translated])

    def test_ambiguous_source_text_remains_untranslated(self):
        batch = self.process_batch(
            [(1678, 'Yes'), (1679, 'Yes')],
            '#1698\nOriginal>\nYes\nTranslation>\nJa\n\n'
            '#1679\nOriginal>\nYes\nTranslation>\nJa\n',
        )
        self.assertFalse(batch.all_translated)
        self.assertEqual([1679], [line.number for line in batch.translated])
        self.assertTrue(batch.errors)

    def test_unmatched_cue_diagnostics_log_numbers_only(self):
        with self.assertLogs(level='WARNING') as captured:
            batch = self.process_batch(
                [(1678, 'Secret alpha words'), (1679, 'Hidden bravo'), (1698, 'Secret alpha words')],
                '#1678\nOriginal>\nSecret alpha words\nTranslation>\nGeheime alfa woorden\n\n'
                '#1679\nOriginal>\nHidden bravo\nTranslation>\nVerborgen bravo\n',
            )
        log = '\n'.join(captured.output)
        self.assertFalse(batch.all_translated)
        for text in ('Secret', 'alpha', 'Hidden', 'Geheime', 'Verborgen'):
            self.assertNotIn(text, log)
        self.assertIn('AI subtitle unmatched cue: number=1698', log)
        self.assertIn('duplicate_source=True', log)

    def test_full_file_follows_resume_and_seeks_then_saves_every_cue(self):
        class FakeProvider:
            validation_message = ''

            def ValidateSettings(self):
                return True

        playhead = {'seconds': 6000.0}
        selected = []

        def fake_init(translator, options, _provider):
            translator.batcher = SubtitleBatcher(options)
            translator.events = types.SimpleNamespace(
                preprocessed=lambda _scenes: None,
                batch_translated=lambda _batch: None,
                scene_translated=lambda _scene: None,
            )
            translator.resume = False
            translator.retranslate = False
            translator.aborted = False
            translator.max_lines = None
            translator.lines_processed = 0
            translator.errors = []
            translator.stop_on_error = False
            translator.max_history = 0
            translator._get_best_summary = lambda _values: None

        def fake_translate_batch(_translator, batch, _line_numbers, _context):
            selected.append(int(batch.originals[0].start.total_seconds()))
            for source in batch.originals:
                translated = SubtitleLine.Construct(
                    source.number, source.start, source.end, 'NL ' + source.text
                )
                batch.AddTranslatedLine(translated)
                source.translated = translated
            if len(selected) <= 3:
                playhead['seconds'] = (1200.0, 2400.0, 3600.0)[len(selected) - 1]

        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / 'source.srt'
            output_path = Path(directory) / 'dutch.srt'
            cues = []
            for number, minutes in enumerate((0, 20, 40, 60, 80, 100, 120), 1):
                hours, minute = divmod(minutes, 60)
                cues.append(
                    '%d\n%02d:%02d:00,000 --> %02d:%02d:04,000\nLine %d\n'
                    % (number, hours, minute, hours, minute, number)
                )
            source_path.write_text('\n'.join(cues), encoding='utf-8')

            with mock.patch.object(TranslationProvider, 'get_provider',
                                   return_value=FakeProvider()), \
                    mock.patch.object(SubtitleTranslator, '__init__', fake_init), \
                    mock.patch.object(SubtitleTranslator, 'TranslateBatch',
                                      fake_translate_batch):
                gptsubtrans.translate(
                    str(source_path), 'Dutch', str(output_path),
                    max_batch_size=1, scene_threshold=1000,
                    priority_seconds=6000.0,
                    playback_position=lambda: playhead['seconds'],
                    log=lambda _message: None,
                )

            self.assertEqual([6000, 1200, 2400, 3600], selected[:4])
            output = output_path.read_text(encoding='utf-8')
            self.assertEqual(7, output.count('-->'))
            self.assertLess(output.index('NL Line 1'), output.index('NL Line 6'))


if __name__ == '__main__':
    unittest.main()
