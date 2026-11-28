"""The OpenAI model pin, reasoning-model routing and notification label."""

import ast
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

ADDON = Path(__file__).resolve().parents[1]
THIRD_PARTY = ADDON / 'a4kSubtitles' / 'lib' / 'third_party'
sys.path.insert(0, str(THIRD_PARTY))

import gptsubtrans  # noqa: F401  (adds PySubtitle to the import path)
from PySubtitle.Providers.OpenAI.MinimalOpenAIClient import MinimalOpenAIClient
from PySubtitle.Providers.OpenAI.OpenAIReasoningClient import OpenAIReasoningClient
from PySubtitle.Providers.OpenAI.ChatGPTClient import ChatGPTClient
from PySubtitle.Providers.Provider_OpenAI import OpenAiProvider


def pinned(path, name):
    match = re.search(r"^%s\s*=\s*['\"]([^'\"]+)['\"]" % name, (ADDON / path).read_text(), re.M)
    return match.group(1)


class ModelPinTests(unittest.TestCase):
    def test_all_three_pins_agree_on_gpt_6_luna(self):
        pins = {
            pinned('a4kSubtitles/ai_translate.py', 'OPENAI_TRANSLATION_MODEL'),
            pinned('a4kSubtitles/lib/third_party/gptsubtrans/__init__.py', 'FORCED_OPENAI_MODEL'),
            pinned('a4kSubtitles/lib/third_party/gptsubtrans/PySubtitle/Providers/Provider_OpenAI.py', 'FORCED_OPENAI_MODEL'),
        }
        self.assertEqual({'gpt-6-luna'}, pins)

    def test_gpt_6_luna_uses_the_reasoning_client(self):
        provider = OpenAiProvider({'api_key': 'test-key'})
        client = provider.GetTranslationClient({'model': 'gpt-6-luna', 'instructions': 'x'})
        self.assertIsInstance(client, OpenAIReasoningClient)
        self.assertEqual('low', client.reasoning_effort)

    def test_gpt_4_models_keep_the_chat_client(self):
        provider = OpenAiProvider({'api_key': 'test-key'})
        with mock.patch.object(OpenAiProvider, 'selected_model', new_callable=mock.PropertyMock,
                               return_value='gpt-4.1-mini-2025-04-14'):
            client = provider.GetTranslationClient({'model': 'gpt-4.1-mini-2025-04-14', 'instructions': 'x'})
        self.assertIsInstance(client, ChatGPTClient)
        self.assertNotIsInstance(client, OpenAIReasoningClient)

    def test_temperature_is_only_sent_when_given(self):
        client = MinimalOpenAIClient('test-key')
        sent = []
        response = mock.Mock(json=lambda: {'choices': []}, raise_for_status=lambda: None)
        with mock.patch.object(client.session, 'post', side_effect=lambda url, json, timeout: sent.append(json) or response):
            client.chat_completion('gpt-6-luna', [], reasoning_effort='low')
            client.chat_completion('gpt-4.1-mini-2025-04-14', [], temperature=0.0)
        self.assertNotIn('temperature', sent[0])
        self.assertEqual('low', sent[0]['reasoning_effort'])
        self.assertEqual(0.0, sent[1]['temperature'])


class NotificationLabelTests(unittest.TestCase):
    def test_model_display_names(self):
        tree = ast.parse((ADDON / 'a4kSubtitles' / 'lib' / 'kodi.py').read_text())
        function = [node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'ai_model_display_name']
        namespace = {}
        exec(compile(ast.Module(function, []), 'kodi.py', 'exec'), namespace)
        name = namespace['ai_model_display_name']
        self.assertEqual('GPT-6 Luna', name('gpt-6-luna'))
        self.assertEqual('GPT-4.1 Mini', name('gpt-4.1-mini-2025-04-14'))
        self.assertEqual('AI', name(None))


if __name__ == '__main__':
    unittest.main()
