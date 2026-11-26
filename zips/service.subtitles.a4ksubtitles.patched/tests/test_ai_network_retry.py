"""Network retry and batch requeue checks for AI subtitle translation."""
from pathlib import Path
import json, sys, tempfile, types, unittest
from unittest import mock
THIRD_PARTY = Path(__file__).resolve().parents[1] / 'a4kSubtitles' / 'lib' / 'third_party'
sys.path.insert(0, str(THIRD_PARTY))
import requests
import gptsubtrans
from PySubtitle.Providers.OpenAI import OpenAIClient as client_module
from PySubtitle.Providers.OpenAI.OpenAIClient import OpenAIClient
from PySubtitle.SubtitleError import TranslationImpossibleError, TranslationProviderUnavailableError
from PySubtitle.SubtitleBatcher import SubtitleBatcher
from PySubtitle.SubtitleLine import SubtitleLine
from PySubtitle.SubtitleTranslator import SubtitleTranslator
from PySubtitle.TranslationProvider import TranslationProvider


def http_error(status, body=None, headers=None):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body or {}).encode()
    response.headers.update(headers or {})
    return requests.HTTPError(f"{status} error", response=response)


class ClientRetryTests(unittest.TestCase):
    def make_client(self, outcomes):
        client = OpenAIClient.__new__(OpenAIClient)
        client.settings = {'max_retries': 3, 'backoff_time': 5.0}
        client.aborted = False
        client.client = object()
        calls = {'n': 0}
        def send(_content, _temperature):
            outcome = outcomes[min(calls['n'], len(outcomes) - 1)]
            calls['n'] += 1
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        client._send_messages = send
        return client, calls

    def run_client(self, outcomes):
        client, calls = self.make_client(outcomes)
        sleeps = []
        with mock.patch.object(client_module.time, 'sleep', sleeps.append):
            try:
                result = client._try_send_messages(types.SimpleNamespace(content=[]), 0.0)
            except Exception as error:
                result = error
        return result, calls['n'], sleeps

    def test_connection_errors_and_timeouts_retry_then_succeed(self):
        result, n, sleeps = self.run_client([requests.ConnectionError('reset'), requests.Timeout('slow'), {'ok': 1}])
        self.assertEqual({'ok': 1}, result)
        self.assertEqual(3, n)
        self.assertEqual([5.0, 10.0], sleeps)

    def test_server_errors_exhaust_retries_and_skip_batch(self):
        result, n, sleeps = self.run_client([http_error(502)])
        self.assertIsInstance(result, TranslationProviderUnavailableError)
        self.assertEqual(4, n)
        self.assertEqual([5.0, 10.0, 20.0], sleeps)

    def test_bad_response_json_is_retried(self):
        result, n, _ = self.run_client([json.JSONDecodeError('bad', 'x', 0), {'ok': 2}])
        self.assertEqual({'ok': 2}, result)

    def test_auth_and_bad_request_stop_immediately(self):
        for status in (400, 401, 403, 404):
            result, n, sleeps = self.run_client([http_error(status)])
            self.assertIsInstance(result, TranslationImpossibleError)
            self.assertNotIsInstance(result, TranslationProviderUnavailableError)
            self.assertEqual((1, []), (n, sleeps))

    def test_rate_limit_waits_but_quota_stops(self):
        result, n, sleeps = self.run_client([http_error(429, headers={'Retry-After': '7'}), {'ok': 3}])
        self.assertEqual(({'ok': 3}, [7.0]), (result, sleeps))
        result, n, sleeps = self.run_client([http_error(429), {'ok': 4}])
        self.assertEqual(({'ok': 4}, [5.0]), (result, sleeps))
        result, n, _ = self.run_client([http_error(429, body={'error': {'code': 'insufficient_quota'}})])
        self.assertIsInstance(result, TranslationImpossibleError)
        self.assertEqual(1, n)

    def test_retry_delay_is_capped(self):
        result, n, sleeps = self.run_client([http_error(429, headers={'Retry-After': '20m'}), {'ok': 5}])
        self.assertEqual([60.0], sleeps)

    def test_stops_after_five_unreachable_batches_in_a_row_and_resets_on_success(self):
        client, _ = self.make_client([requests.ConnectionError('down')])
        with mock.patch.object(client_module.time, 'sleep', lambda _s: None):
            prompt = types.SimpleNamespace(content=[])
            for _ in range(4):
                with self.assertRaises(TranslationProviderUnavailableError):
                    client._try_send_messages(prompt, 0.0)
            client._send_messages = lambda *_: {'ok': 6}
            self.assertEqual({'ok': 6}, client._try_send_messages(prompt, 0.0))
            client._send_messages = mock.Mock(side_effect=requests.ConnectionError('down'))
            for _ in range(4):
                with self.assertRaises(TranslationProviderUnavailableError):
                    client._try_send_messages(prompt, 0.0)
            with self.assertRaises(TranslationImpossibleError) as raised:
                client._try_send_messages(prompt, 0.0)
            self.assertNotIsInstance(raised.exception, TranslationProviderUnavailableError)


class RequeueTests(unittest.TestCase):
    def test_unreachable_batch_is_retried_later_and_file_is_complete(self):
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

        attempts = []
        def fake_translate_batch(_translator, batch, _line_numbers, _context):
            attempts.append(batch.number)
            if batch.number == 2 and attempts.count(2) == 1:
                raise TranslationProviderUnavailableError('down')
            batch.errors = []
            for source in batch.originals:
                translated = SubtitleLine.Construct(source.number, source.start, source.end, 'NL ' + source.text)
                batch.AddTranslatedLine(translated)
                source.translated = translated

        logs = []
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / 'source.srt'; output_path = Path(directory) / 'dutch.srt'
            source_path.write_text('\n'.join('%d\n00:%02d:00,000 --> 00:%02d:04,000\nLine %d\n' % (n, n * 10, n * 10, n) for n in range(1, 5)), encoding='utf-8')
            with mock.patch.object(TranslationProvider, 'get_provider', return_value=FakeProvider()), \
                    mock.patch.object(SubtitleTranslator, '__init__', fake_init), \
                    mock.patch.object(SubtitleTranslator, 'TranslateBatch', fake_translate_batch):
                gptsubtrans.translate(str(source_path), 'Dutch', str(output_path), max_batch_size=1, scene_threshold=1000,
                                      priority_seconds=0.0, playback_position=lambda: 0.0, log=logs.append)
            output = output_path.read_text(encoding='utf-8')
        self.assertEqual(2, attempts.count(2))
        self.assertEqual(4, output.count('NL Line'))
        self.assertTrue(any('Retrying batch' in line for line in logs))
        self.assertTrue(any('attempted 4/4 batches, 4 fully translated' in line for line in logs), logs[-1])


if __name__ == '__main__':
    unittest.main()
