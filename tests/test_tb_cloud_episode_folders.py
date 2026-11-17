"""TorBox cloud matching tests that run without Kodi's xbmc modules."""
import ast
import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1] / 'plugin.video.fenlight.patched'


def load_function(path, name, namespace):
	tree = ast.parse(path.read_text(encoding='utf-8'))
	node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
	exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
	return namespace[name]


def load_source(namespace):
	path = ROOT / 'resources/lib/scrapers/tb_cloud.py'
	tree = ast.parse(path.read_text(encoding='utf-8'))
	node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'source')
	exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
	return namespace['source']


class FakeTorBox:
	def __init__(self):
		self.torrent = []
		self.usenet = []
		self.webdl = []

	def user_cloud(self):
		return {'data': self.torrent}

	def user_cloud_usenet(self):
		return {'data': self.usenet}

	def user_cloud_webdl(self):
		return {'data': self.webdl}


class TorBoxEpisodeFolderTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		utils = ROOT / 'resources/lib/modules/source_utils.py'
		module_utils = ROOT / 'resources/lib/modules/utils.py'
		cls.globals = {'re': re, 'unquote': unquote, 'string': str,
					   'extensions': ('.mkv', '.mp4'),
					   'subtitle_extensions': ('.srt', '.ass', '.ssa', '.vtt', '.sub'),
					   'enabled_debrids_check': lambda provider: True,
					   'filter_by_name': lambda provider: True,
					   'get_aliases_titles': lambda aliases: aliases,
					   'clean_file_name': lambda title: title,
					   'check_title': lambda *args: False,
					   'get_file_info': lambda **kwargs: ('SD', ''),
					   'release_info_format': lambda name: name,
					   'internal_results': lambda *args: None,
					   'torbox_usenet_search_enabled': lambda *args: False}
		load_function(utils, 'clean_title', cls.globals)
		load_function(utils, 'seas_ep_filter', cls.globals)
		load_function(module_utils, 'normalize', cls.globals)
		cls.source = load_source(cls.globals)

	def setUp(self):
		self.torbox = FakeTorBox()
		self.globals['TorBox'] = self.torbox

	def results(self, show, episode_name, files, *, kind='usenet', season=1, episode=1, folder=None):
		folder = folder or show
		setattr(self.torbox, kind, [{'id': 11, 'name': folder, 'download_finished': True, 'files': files}])
		return self.source().results({'media_type': 'episode', 'title': show, 'year': 1994,
										  'season': season, 'episode': episode, 'ep_name': episode_name,
										  'aliases': []}) or []

	@staticmethod
	def video(name, id):
		return {'id': id, 'name': name, 'short_name': name, 'size': 1073741824}

	@staticmethod
	def subtitle(name, id):
		return {'id': id, 'name': name, 'short_name': name}

	def test_numbered_episode_title_and_subtitles_in_all_cloud_types(self):
		files = [self.subtitle('01 The Plague.EN.srt', 2), self.video('01 The Plague.mkv', 1),
				 self.subtitle('02 The Dreams.EN.srt', 4), self.video('02 The Dreams.mkv', 3)]
		for kind in ('torrent', 'usenet', 'webdl'):
			with self.subTest(kind=kind):
				results = self.results('The Stand', 'Aflevering 1', files, kind=kind, episode=1,
					folder='The Stand (1994 miniserie met NL en EN subs) nu kleiner!')
				self.assertEqual(['11,1'], [item['url_dl'] for item in results])
				self.assertEqual(['01 The Plague.EN.srt'],
					[item['name'] for item in results[0]['cloud_subtitles']])
				setattr(self.torbox, kind, [])
		results = self.results('The Stand', 'Aflevering 2', files, episode=2,
			folder='The Stand (1994 miniserie met NL en EN subs) nu kleiner!')
		self.assertEqual(['02 The Dreams.mkv'], [item['name'] for item in results])

	def test_numbered_multipart_episodes(self):
		files = [self.video('01a Thy Kingdom Come (Part 1).mkv', 1),
				 self.video('01b Thy Kingdom Come (Part 2).mkv', 2),
				 self.video("02 Death's Kingdom.mkv", 3)]
		results = self.results("Stephen King's Kingdom Hospital", 'Aflevering 1', files,
			folder="Stephen King's Kingdom Hospital (DVDrip EN NL subs)")
		self.assertEqual([1, 2], [int(item['url_dl'].split(',')[1]) for item in results])

	def test_unnumbered_episode_title_in_show_folder(self):
		files = [self.video('Thy Kingdom Come.mkv', 1), self.video("Death's Kingdom.mkv", 2)]
		results = self.results('Kingdom Hospital', 'Thy Kingdom Come', files,
						   folder="Kingdom Hospital 1 van 4 dvd's 2004 NL subs")
		self.assertEqual(['Thy Kingdom Come.mkv'], [item['name'] for item in results])

	def test_wrong_episode_and_wrong_show_are_rejected(self):
		files = [self.video('02 The Dreams.mkv', 1), self.video('The Dreams.mkv', 2),
				 self.video('S01E02 The Plague.mkv', 3)]
		self.assertEqual([], self.results('The Stand', 'The Plague', files,
										  folder='The Stand (1994)'))
		self.assertEqual([], self.results('The Stand', 'The Plague',
										  [self.video('The Plague.mkv', 4)], folder='Other Show'))

	def test_bare_number_and_conflicting_folder_season(self):
		self.assertEqual(['01.mkv'], [item['name'] for item in
			self.results('The Stand', '', [self.video('01.mkv', 1)], folder='The Stand')])
		self.assertEqual([], self.results('The Stand', 'The Plague',
										  [self.video('The Plague.mkv', 1)], folder='The Stand S02'))


if __name__ == '__main__':
	unittest.main()
