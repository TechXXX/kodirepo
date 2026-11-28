"""Small fake Kodi `core` and `ctx` objects for testing the service modules without Kodi."""
from __future__ import absolute_import

import json
import os
import random
import shutil
import sys
import tempfile
import time
import types

HERE = os.path.dirname(__file__)
ADDON_ROOT = os.path.dirname(HERE)
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)

from a4kSubtitles.service_state import PlaybackState  # noqa: E402

LANG_IDS = {'dutch': 'nld', 'nld': 'nld', 'dut': 'nld', 'english': 'eng', 'eng': 'eng', 'en': 'eng', 'nl': 'nld'}


class Logger(object):
    def __init__(self):
        self.lines = []

    def debug(self, message):
        self.lines.append(message)

    info = error = debug

    def text(self):
        return '\n'.join(self.lines)


class Player(object):
    def __init__(self, kodi):
        self.kodi = kodi

    def isPlayingVideo(self):
        return self.kodi.playing

    def isPlaying(self):
        return self.kodi.playing

    def getTime(self):
        return self.kodi.playhead

    def getPlayingFile(self):
        return self.kodi.playing_file

    def setSubtitles(self, path):
        self.kodi.attached.append(path)

    def showSubtitles(self, _visible):
        pass

    def getAvailableAudioStreams(self):
        return list(self.kodi.audio_streams)

    def getAvailableSubtitleStreams(self):
        return [sub['language'] for sub in self.kodi.player_subtitles]

    def setSubtitleStream(self, index):
        self.kodi.selected_stream = index


class Kodi(object):
    def __init__(self, settings=None, properties=None):
        self.settings = {
            'use_ai': True, 'ai_api_key': 'sk-test', 'ai_provider': '0', 'ai_model': 'gpt-6-luna',
            'auto_sync_subtitles': True, 'auto_select': True, 'auto_download': True,
            'prefer_sdh': False, 'prefer_forced': False, 'auto_search': True,
        }
        self.settings.update(settings or {})
        self.properties = dict(properties or {})
        self.playing = True
        self.playhead = 120.0
        self.playing_file = 'https://example.test/Show.S01E01.1080p.WEB-DL-GRP.mkv'
        self.attached = []
        self.notifications = []
        self.player_subtitles = []
        self.audio_streams = []
        self.selected_stream = None
        self.kodi_settings = {'locale.subtitlelanguage': 'Dutch', 'subtitles.languages': 'Dutch'}
        self.xbmc = types.SimpleNamespace(
            Player=lambda: Player(self),
            getInfoLabel=self.get_info_label,
            ISO_639_2=2,
            executebuiltin=lambda _command: None,
            getCondVisibility=lambda _condition: self.playing,
            Monitor=lambda: self.monitor,
        )
        self.monitor = Monitor()
        self.xbmcvfs = types.SimpleNamespace(exists=os.path.exists, delete=lambda _path: None)

    def get_info_label(self, label):
        if label in ('Player.FilenameAndPath', 'Player.Filenameandpath'):
            return self.playing_file if self.playing else ''
        if label == 'Player.Filename':
            return os.path.basename(self.playing_file) if self.playing else ''
        return ''

    def get_bool_setting(self, _group, setting_id):
        return bool(self.settings[setting_id])

    def get_setting(self, _group, setting_id):
        return self.settings.get(setting_id)

    def set_setting(self, _group, setting_id, value):
        self.settings[setting_id] = value

    def get_property(self, name):
        return self.properties.get(name, '')

    def clear_property(self, name):
        self.properties.pop(name, None)

    def notification(self, text, time=0):
        self.notifications.append(text)

    def gpt_translated_notification_text(self, model):
        return 'Translated by %s' % model

    def migrate_auto_sync_subtitles_default_on(self):
        return False

    def get_kodi_setting(self, name):
        return self.kodi_settings.get(name)

    def parse_language(self, value):
        return value

    def get_kodi_player_subtitles(self):
        current = self.player_subtitles[0] if self.player_subtitles else None
        return {'subtitles': self.player_subtitles, 'currentsubtitle': current}


def get_lang_id(value, _format):
    return LANG_IDS.get(str(value).strip().lower(), '')


def make_core(settings=None, properties=None):
    temp_dir = tempfile.mkdtemp(prefix='a4k-test-')
    core = types.SimpleNamespace(
        kodi=Kodi(settings, properties),
        logger=Logger(),
        utils=types.SimpleNamespace(
            get_lang_id=get_lang_id, temp_dir=temp_dir, gptsubtrans=None,
            suspend_service_file=os.path.join(temp_dir, 'suspend'), get_subfile_from_temp_dir=lambda: None,
        ),
        os=os,
        shutil=shutil,
        json=json,
        time=time,
        last_meta=types.SimpleNamespace(title='Show', year=2026),
    )
    return core


class Monitor(object):
    """Never aborts, unless `polls` is set: then the service loop stops after that many polls."""

    def __init__(self, polls=None):
        self.polls = polls
        self.waits = []

    def abortRequested(self):
        return self.polls is not None and self.polls <= 0

    def waitForAbort(self, seconds):
        self.waits.append(seconds)
        if self.polls is None:
            return False
        self.polls -= 1
        return self.polls < 0


class Api(object):
    """Search returns `results`; download writes the SRT text stored for a result's name."""

    def __init__(self, core, files=None, results=None):
        self.core = core
        self.files = dict(files or {})
        self.results = list(results or [])
        self.searches = []
        self.downloads = []

    def search(self, params):
        self.searches.append(params)
        return list(self.results)

    def download(self, result, preserve_existing=False):
        name = result['name']
        self.downloads.append(name)
        if name not in self.files:
            return None
        path = os.path.join(self.core.utils.temp_dir, name + '.srt')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(self.files[name])
        return path


def make_ctx(settings=None, properties=None, files=None, results=None):
    core = make_core(settings, properties)
    api = Api(core, files, results)
    return types.SimpleNamespace(api=api, core=core, monitor=Monitor(), state=PlaybackState())


def result(name, lang='English'):
    return {'name': name, 'lang': lang, 'service_name': 'opensubtitles', 'action_args': {'url': name, 'lang': lang}}


def timeline(seed, count=60):
    """Irregular cue starts in milliseconds, like real dialogue."""
    rng = random.Random(seed)
    starts, value = [], 5000
    for _ in range(count):
        value += rng.randint(1500, 6000)
        starts.append(value)
    return starts


def srt(starts):
    def stamp(ms):
        return '%02d:%02d:%02d,%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
    blocks = []
    for index, start in enumerate(starts, 1):
        blocks.append('%d\n%s --> %s\nLine %d\n' % (index, stamp(start), stamp(start + 1200), index))
    return '\n'.join(blocks)


def embedded(starts, track_number=3, is_sdh=False):
    return [{'starts': list(starts), 'track_number': track_number, 'track_name': 'English', 'is_sdh': is_sdh}]
