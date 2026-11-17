"""Temporary TorBox transfer cleanup without Kodi or a TorBox account."""
import ast
import sqlite3
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from time import time


SOURCE = Path(__file__).resolve().parents[1] / 'plugin.video.fenlight.patched/resources/lib/apis/torbox_api.py'


class ImmediateThread:
	def __init__(self, target, args):
		self.target, self.args = target, args

	def start(self):
		self.target(*self.args)


class TorBoxCleanupTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
		node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'TorBoxAPI')
		cls.namespace = {'time': time, 'Thread': ImmediateThread, 'sha256': sha256,
					 'logger': lambda *args: None,
					 'get_setting': lambda *args: '0',
					 'supported_video_extensions': lambda: ('.mkv',),
					 'EXTRAS': (),
					 'seas_ep_filter': lambda *args: True}
		exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), cls.namespace)
		cls.api_class = cls.namespace['TorBoxAPI']

	def setUp(self):
		self.tempdir = tempfile.TemporaryDirectory()
		self.addCleanup(self.tempdir.cleanup)
		path = Path(self.tempdir.name) / 'maincache.db'
		self.namespace['connect_database'] = lambda name: sqlite3.connect(path, isolation_level=None)
		self.api = self.api_class.__new__(self.api_class)
		self.api.token = 'test-token'
		self.api.clear_user_cloud_cache = lambda: True

	def pending(self):
		with self.namespace['connect_database']('maincache_db') as db:
			try: return db.execute('SELECT kind, transfer_id, attempts FROM torbox_cleanup').fetchall()
			except sqlite3.OperationalError: return []

	def test_failed_delete_is_retried_and_manual_items_are_untouched(self):
		called = []
		def delete(transfer_id):
			called.append(transfer_id)
			return {'success': len(called) > 1}
		self.api.delete_torrent = delete
		self.api._queue_temporary_transfer('torrent', 10)
		self.assertFalse(self.api.cleanup_temporary_transfer('torrent', 10))
		self.assertEqual([('torrent', 10, 1)], self.pending())
		with self.namespace['connect_database']('maincache_db') as db:
			db.execute('UPDATE torbox_cleanup SET retry_at=0')
		other_account = self.api_class.__new__(self.api_class)
		other_account.token = 'other-token'
		self.assertEqual(0, other_account.retry_pending_cleanup())
		self.assertEqual([10], called)
		self.assertEqual(1, self.api.retry_pending_cleanup())
		self.assertEqual([], self.pending())
		self.assertEqual([10, 10], called)

	def test_usenet_early_return_still_deletes_transfer(self):
		deleted = []
		self.api.create_usenet_transfer = lambda *args: 20
		self.api._usenet_transfer_video_files = lambda *args: []
		self.api._debug_usenet_files = lambda *args: ''
		self.api.delete_usenet = lambda transfer_id: deleted.append(transfer_id) or {'success': True}
		self.assertIsNone(self.api.resolve_usenet_search('nzb', 'release', 'Show', 1, 1))
		self.assertEqual([20], deleted)
		self.assertEqual([], self.pending())

	def test_torrent_early_return_still_deletes_transfer(self):
		deleted = []
		self.api.add_magnet = lambda *args: {'success': True, 'data': {'torrent_id': 30}}
		self.api.torrent_info = lambda *args: {'data': {'files': []}}
		self.api.delete_torrent = lambda transfer_id: deleted.append(transfer_id) or {'success': True}
		self.assertIsNone(self.api.resolve_magnet('magnet', 'hash', False, 'Show', 1, 1))
		self.assertEqual([30], deleted)
		self.assertEqual([], self.pending())

	def test_intentionally_stored_transfer_is_not_deleted(self):
		deleted = []
		self.api.add_magnet = lambda *args: {'success': True, 'data': {'torrent_id': 40}}
		self.api.torrent_info = lambda *args: {'data': {'files': [{'id': 1, 'short_name': 'Show.S01E01.mkv', 'size': 10}]}}
		self.api.unrestrict_link = lambda *args: 'https://example.invalid/video'
		self.api.delete_torrent = lambda transfer_id: deleted.append(transfer_id) or {'success': True}
		self.assertEqual('https://example.invalid/video', self.api.resolve_magnet('magnet', 'hash', True, 'Show', 1, 1))
		self.assertEqual([], deleted)
		self.assertEqual([], self.pending())


if __name__ == '__main__':
	unittest.main()
