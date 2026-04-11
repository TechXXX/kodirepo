# -*- coding: utf-8 -*-

import os
import json
import importlib

api_mode_env_name = 'A4KSUBTITLES_API_MODE'

class A4kSubtitlesApi(object):
    def __init__(self, mocks=None):
        if mocks is None:
            mocks = {}

        api_mode = {
            'kodi': False,
            'xbmc': False,
            'xbmcaddon': False,
            'xbmcplugin': False,
            'xbmcgui': False,
            'xbmcvfs': False,
        }

        api_mode.update(mocks)
        os.environ[api_mode_env_name] = json.dumps(api_mode)
        self.core = importlib.import_module('a4kSubtitles.core')

    def __mock_video_meta(self, meta):
        def build_mock_meta():
            filename = meta.get('filename', '') or meta.get('title', '')
            filename_without_ext = filename
            try:
                filename_without_ext = os.path.splitext(filename)[0]
            except:
                pass

            mocked_meta = self.core.utils.DictAsObject({
                'year': str(meta.get('year', '') or ''),
                'season': str(meta.get('season', '') or ''),
                'episode': str(meta.get('episode', '') or ''),
                'tvshow': str(meta.get('tvshow', '') or ''),
                'title': str(meta.get('title', '') or ''),
                'imdb_id': str(meta.get('imdb_id', '') or ''),
                'tvshow_year': str(meta.get('tvshow_year', '') or ''),
                'filename': str(filename or ''),
                'filename_without_ext': str(filename_without_ext or ''),
                'filesize': str(meta.get('filesize', '') or ''),
                'filehash': str(meta.get('filehash', '') or ''),
                'tvshow_year_thread': None,
            })

            mocked_meta.tv_show_imdb_id = mocked_meta.imdb_id
            mocked_meta.is_tvshow = mocked_meta.tvshow != ''
            mocked_meta.is_movie = not mocked_meta.is_tvshow
            if mocked_meta.is_tvshow and mocked_meta.tvshow_year == '':
                mocked_meta.tvshow_year = mocked_meta.year

            try:
                if len(mocked_meta.imdb_id) > 2:
                    mocked_meta.imdb_id_as_int = int(mocked_meta.imdb_id[2:].lstrip('0'))
            except:
                mocked_meta.imdb_id_as_int = 0

            return mocked_meta

        def get_info_label(label):
            if label == 'System.BuildVersionCode':
                return meta.get('version', '19.1.0')
            if label == 'VideoPlayer.Year':
                return meta.get('year', '')
            if label == 'VideoPlayer.Season':
                return meta.get('season', '')
            if label == 'VideoPlayer.Episode':
                return meta.get('episode', '')
            if label == 'VideoPlayer.TVShowTitle':
                return meta.get('tvshow', '')
            if label == 'VideoPlayer.OriginalTitle':
                return meta.get('title', '')
            if label == 'VideoPlayer.Title':
                return meta.get('_title', '')
            if label == 'VideoPlayer.IMDBNumber':
                return meta.get('imdb_id', '')
            if label == 'Player.FilenameAndPath':
                return meta.get('url', '')
        default = self.core.kodi.xbmc.getInfoLabel
        self.core.kodi.xbmc.getInfoLabel = get_info_label

        player = self.core.kodi.xbmc.Player()
        player_get_playing_file_restore = None
        video_get_filename_restore = None
        video_get_meta_restore = self.core.video.get_meta
        file_size_restore = None
        file_hash_restore = None
        self.core.video.get_meta = lambda _core: build_mock_meta()
        try:
            default_ = player.getPlayingFile
            player.getPlayingFile = lambda: meta.get('filename', '')
            player_get_playing_file_restore = default_
        except AttributeError:
            # In live Kodi, the Player method can be read-only. Fall back to overriding
            # a4kSubtitles' filename helper so API-mode searches still use the mocked release name.
            video_get_filename_restore = getattr(self.core.video, '__get_filename')
            setattr(self.core.video, '__get_filename', lambda title: meta.get('filename', '') or title)

        try:
            file_size_restore = self.core.kodi.xbmcvfs.File.size
            self.core.kodi.xbmcvfs.File.size = lambda: meta.get('filesize', '')
        except (AttributeError, TypeError):
            file_size_restore = None

        try:
            file_hash_restore = self.core.kodi.xbmcvfs.File.hash
            self.core.kodi.xbmcvfs.File.hash = lambda: meta.get('filehash', '')
        except (AttributeError, TypeError):
            file_hash_restore = None

        def restore():
            self.core.kodi.xbmc.getInfoLabel = default
            self.core.video.get_meta = video_get_meta_restore
            if player_get_playing_file_restore is not None:
                try:
                    player.getPlayingFile = player_get_playing_file_restore
                except AttributeError:
                    pass
            if video_get_filename_restore is not None:
                setattr(self.core.video, '__get_filename', video_get_filename_restore)
            if file_size_restore is not None:
                try:
                    self.core.kodi.xbmcvfs.File.size = file_size_restore
                except (AttributeError, TypeError):
                    pass
            if file_hash_restore is not None:
                try:
                    self.core.kodi.xbmcvfs.File.hash = file_hash_restore
                except (AttributeError, TypeError):
                    pass
        return restore

    def mock_settings(self, settings):
        default_get_setting = self.core.kodi.get_setting
        default_get_int_setting = self.core.kodi.get_int_setting
        default_get_bool_setting = self.core.kodi.get_bool_setting

        def get_setting(group, id=None):
            key = '%s.%s' % (group, id) if id else group
            setting = settings.get(key, None)
            if setting is None:
                return default_get_setting(group, id)
            return str(setting).strip()

        def get_int_setting(group, id=None):
            return int(get_setting(group, id))

        def get_bool_setting(group, id=None):
            return get_setting(group, id).lower() == 'true'

        self.core.kodi.get_setting = get_setting
        self.core.kodi.get_int_setting = get_int_setting
        self.core.kodi.get_bool_setting = get_bool_setting

        def restore():
            self.core.kodi.get_setting = default_get_setting
            self.core.kodi.get_int_setting = default_get_int_setting
            self.core.kodi.get_bool_setting = default_get_bool_setting
        return restore

    def search(self, params, settings=None, video_meta=None):
        restore_settings = None
        restore_video_meta = None
        restore_shadow_snapshot_alias_mode = getattr(self.core, 'shadow_snapshot_alias_mode', 'pairable')

        try:
            if settings is not None:
                restore_settings = self.mock_settings(settings)

            if video_meta is not None:
                restore_video_meta = self.__mock_video_meta(video_meta)
                self.core.shadow_snapshot_alias_mode = 'pairable'
            else:
                self.core.shadow_snapshot_alias_mode = 'history_only'

            return self.core.search(self.core, params)
        finally:
            self.core.shadow_snapshot_alias_mode = restore_shadow_snapshot_alias_mode
            if restore_settings:
                restore_settings()
            if restore_video_meta:
                restore_video_meta()

    def download(self, params, settings=None):
        restore_settings = None

        try:
            if settings:
                restore_settings = self.mock_settings(settings)

            return self.core.download(self.core, params)
        finally:
            if restore_settings:
                restore_settings()

    def auto_load_enabled(self, settings=None):
        restore_settings = None

        try:
            if settings:
                restore_settings = self.mock_settings(settings)

            return self.core.kodi.get_bool_setting('general.auto_search') and self.core.kodi.get_bool_setting('general.auto_download')
        finally:
            if restore_settings:
                restore_settings()
