# -*- coding: utf-8 -*-
from modules import kodi_utils
from windows.base_window import BaseDialog

button_skip = 11
button_close = 12
labels = {
	'en': {'intro': 'Skip Intro', 'recap': 'Skip Recap', 'skip': 'Skip', 'close': 'Close'},
	'nl': {'intro': 'Intro overslaan', 'recap': 'Samenvatting overslaan', 'skip': 'Overslaan', 'close': 'Sluiten'}
}


def _is_dutch_language():
	try:
		xbmc = kodi_utils.xbmc
		language_values = []
		for lang_format in (getattr(xbmc, 'ISO_639_1', None), getattr(xbmc, 'ISO_639_2', None), getattr(xbmc, 'ENGLISH_NAME', None)):
			if lang_format is None: continue
			try: language_values.append(xbmc.getLanguage(lang_format, False))
			except TypeError:
				try: language_values.append(xbmc.getLanguage(lang_format))
				except: pass
			except: pass
		try: language_values.append(xbmc.getLanguage())
		except: pass
		language_values = [str(i).lower() for i in language_values if i]
		return any(i.startswith('nl') or i.startswith('dut') or 'dutch' in i or 'nederlands' in i for i in language_values)
	except: return False


class IntroSkip(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.meta = kwargs.get('meta') or {}
		self.segment_type = kwargs.get('segment_type', 'intro')
		self.start_time = float(kwargs.get('start_time', 0) or 0)
		self.end_time = float(kwargs.get('end_time', 0) or 0)
		self.skip_target = float(kwargs.get('skip_target', self.end_time) or self.end_time)
		self.selected = 'close'
		self.closed = False
		self.set_properties()

	def onInit(self):
		self.setFocusId(button_skip)
		self.monitor()

	def run(self):
		self.doModal()
		self.clearProperties()
		return self.selected

	def onAction(self, action):
		if action in self.closing_actions:
			self.closed = True
			self.selected = 'close'
			self.close()

	def onClick(self, controlID):
		if controlID == button_skip:
			try:
				if self.player.isPlayingVideo(): self.player.seekTime(self.skip_target)
				self.selected = 'skip'
			except: self.selected = 'close'
		self.closed = True
		self.close()

	def set_properties(self):
		dialog_labels = labels['nl'] if _is_dutch_language() else labels['en']
		label = dialog_labels.get(self.segment_type, dialog_labels['intro'])
		title = self.meta.get('title') or ''
		season = int(self.meta.get('season') or 0)
		episode = int(self.meta.get('episode') or 0)
		ep_name = self.meta.get('ep_name') or self.meta.get('title') or ''
		if season and episode:
			episode_label = '%s[B] | [/B]%02dx%02d[B] | [/B]%s' % (title, season, episode, ep_name)
		else: episode_label = title or ep_name
		self.setProperty('thumb', self.meta.get('ep_thumb', None) or self.meta.get('fanart', ''))
		self.setProperty('clearlogo', self.meta.get('clearlogo', ''))
		self.setProperty('segment_label', label)
		self.setProperty('episode_label', episode_label)
		self.setProperty('button_skip_label', dialog_labels['skip'])
		self.setProperty('button_close_label', dialog_labels['close'])

	def monitor(self):
		while self.player.isPlayingVideo():
			if self.closed: break
			try:
				current_time = self.player.getTime()
				if current_time >= self.end_time - 0.25: break
				if current_time < self.start_time - 2: break
			except: break
			self.sleep(250)
		self.closed = True
		self.close()
