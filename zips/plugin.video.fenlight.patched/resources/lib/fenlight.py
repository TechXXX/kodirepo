# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl
from modules.router import routing, sys_exit_check
# from modules.kodi_utils import logger

routing(sys)
params = dict(parse_qsl(sys.argv[2][1:], keep_blank_values=True))
mode = params.get('mode', 'navigator.main')
if mode not in ('playback.media', 'playback.video') and sys_exit_check(): sys.exit(1)
