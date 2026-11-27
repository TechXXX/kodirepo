"""Automatic searches skip other sites' AI/machine translations when a4k can translate itself."""
from __future__ import absolute_import

import ast
import os
import types
import unittest


HERE = os.path.dirname(__file__)
SEARCH_PATH = os.path.join(os.path.dirname(HERE), 'a4kSubtitles', 'search.py')
FUNCTIONS = ('__own_ai_translation_ready', '__is_translated_result', '__drop_translated_results')


def load_drop_translated_results():
    with open(SEARCH_PATH, 'r') as handle:
        tree = ast.parse(handle.read(), filename=SEARCH_PATH)
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    namespace = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), SEARCH_PATH, 'exec'), namespace)
    return namespace['__drop_translated_results']


class Kodi(object):
    def __init__(self, use_ai=True, ai_api_key='sk-test', ai_provider='0', ai_model=''):
        self.values = {'use_ai': use_ai, 'ai_api_key': ai_api_key, 'ai_provider': ai_provider, 'ai_model': ai_model}

    def get_bool_setting(self, _group, setting_id):
        return bool(self.values[setting_id])

    def get_setting(self, _group, setting_id):
        return self.values[setting_id]


def make_core(api_mode=True, **settings):
    logged = []
    core = types.SimpleNamespace(
        api_mode_enabled=api_mode,
        kodi=Kodi(**settings),
        logger=types.SimpleNamespace(debug=logged.append),
    )
    return core, logged


RESULTS = [
    {'name': 'os-auto Dutch', 'action_args': {'ai_translated': True, 'machine_translated': False}},
    {'name': 'machine Dutch', 'action_args': {'ai_translated': False, 'machine_translated': True}},
    {'name': 'human Dutch', 'action_args': {'ai_translated': False, 'machine_translated': False}},
    {'name': 'flag on result', 'ai_translated': True, 'action_args': {}},
]


def names(results):
    return [result['name'] for result in results]


class SkipTranslatedResultsTest(unittest.TestCase):
    def setUp(self):
        self.drop = load_drop_translated_results()

    def test_automatic_search_drops_translated_results_when_ai_is_ready(self):
        core, logged = make_core()
        self.assertEqual(['human Dutch'], names(self.drop(core, RESULTS)))
        self.assertIn('dropped 3', logged[0])

    def test_manual_search_keeps_translated_results(self):
        core, logged = make_core(api_mode=False)
        self.assertEqual(names(RESULTS), names(self.drop(core, RESULTS)))
        self.assertEqual([], logged)

    def test_translated_results_kept_when_own_ai_cannot_run(self):
        for settings in ({'use_ai': False}, {'ai_api_key': ''}, {'ai_api_key': 'empty_setting'},
                         {'ai_provider': '1', 'ai_model': ''}):
            core, _logged = make_core(**settings)
            self.assertEqual(names(RESULTS), names(self.drop(core, RESULTS)), settings)

    def test_other_provider_with_model_counts_as_ready(self):
        core, _logged = make_core(ai_provider='1', ai_model='some-model')
        self.assertEqual(['human Dutch'], names(self.drop(core, RESULTS)))


if __name__ == '__main__':
    unittest.main()
