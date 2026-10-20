from __future__ import absolute_import

import ast
import os
import unittest


HERE = os.path.dirname(__file__)
SEARCH_PATH = os.path.join(os.path.dirname(HERE), 'a4kSubtitles', 'search.py')


def load_apply_limit():
    with open(SEARCH_PATH, 'r') as handle:
        tree = ast.parse(handle.read(), filename=SEARCH_PATH)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == '__apply_limit'
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), SEARCH_PATH, 'exec'), namespace)
    return namespace['__apply_limit']


class EmptyLanguageLimitTest(unittest.TestCase):
    def test_empty_languages_return_no_results(self):
        apply_limit = load_apply_limit()

        class Kodi(object):
            @staticmethod
            def get_int_setting(_setting):
                return 20

        class Core(object):
            kodi = Kodi()

        class Meta(object):
            languages = []

        self.assertEqual([], apply_limit(Core(), [{'lang': 'eng'}], Meta()))


if __name__ == '__main__':
    unittest.main()
