# -*- coding: utf-8 -*-

import json
import os
import sys
import threading
import copy
import shutil
import gzip
import difflib
import time
import hashlib
import re
import zipfile
from datetime import datetime, timedelta
from base64 import b64encode
from xml.etree import ElementTree
from io import BytesIO

from .lib import (
    cache,
    kodi,
    logger,
    num2ordinal,
    request,
    utils,
    video,
)

core = sys.modules[__name__]
utils.core = core

api_mode_enabled = True
handle = None
last_meta = None

progress_dialog = None
progress_text = ''

from .services import services
from .search import search
from .download import download
from .data import data

def main(handle, paramstring):  # pragma: no cover
    core.api_mode_enabled = False
    core.handle = handle
    params = dict(utils.parse_qsl(paramstring))
    action = params.get('action')
    if action == 'search' or not action:
        params.setdefault('languages', kodi.get_kodi_setting('subtitles.languages') or '')
        params.setdefault('preferredlanguage', kodi.get_kodi_setting('locale.subtitlelanguage') or 'default')
        if not action:
            params['action'] = 'search'
            action = 'search'
    logger.debug(
        'core.main invoked | handle=%s | paramstring=%s | action=%s | languages=%s | preferred=%s'
        % (
            handle,
            paramstring,
            action,
            params.get('languages', ''),
            params.get('preferredlanguage', ''),
        )
    )

    if action == 'manualsearch':
        kodi.notification('Manual search is not supported')
    elif action == 'search':
        core.progress_text = ''
        core.progress_dialog = kodi.get_progress_dialog()

        try:
            search(core, params)
        finally:
            core.progress_dialog.close()
            core.progress_dialog = None

    elif action == 'download':
        params['action_args'] = json.loads(params['action_args'])
        download(core, params)

    kodi.xbmcplugin.endOfDirectory(handle)
