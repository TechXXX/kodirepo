from threading import Thread

from xbmcgui import WindowXMLDialog

from tmdbhelper.lib.addon.plugin import ADDON, ADDONPATH


class TraktAuthWindow(WindowXMLDialog):
    ACTION_CLOSE = (9, 10, 13, 92)

    def __init__(self, *args, **kwargs):
        self.heading = kwargs.get('heading') or ''
        self.content = kwargs.get('content') or ''
        self.qrcode = kwargs.get('qrcode') or ''
        self.logo = kwargs.get('logo') or ADDON.getAddonInfo('icon')
        self.percent = 0
        self.is_canceled = False
        self.is_initialised = False

    def onInit(self):
        self.is_initialised = True
        self.set_controls()

    def onAction(self, action):
        action_id = action.getId() if hasattr(action, 'getId') else action
        if action_id in self.ACTION_CLOSE:
            self.is_canceled = True
            self.close()

    def set_controls(self):
        self.getControl(1000).setImage(self.logo)
        self.getControl(200).setImage(self.qrcode)
        self.getControl(2000).setLabel(self.heading)
        self.getControl(2001).setText(self.content)
        self.getControl(5000).setPercent(self.percent)

    def update(self, percent=0):
        self.percent = percent
        if not self.is_initialised:
            return
        try:
            self.getControl(5000).setPercent(percent)
        except RuntimeError:
            pass

    def iscanceled(self):
        return self.is_canceled


class TraktAuthDialog:
    def __init__(self, heading='', content='', qrcode=''):
        self.window = TraktAuthWindow(
            'script-tmdbhelper-trakt-auth.xml',
            ADDONPATH,
            'default',
            '1080i',
            heading=heading,
            content=content,
            qrcode=qrcode,
        )
        self.thread = None

    def create(self):
        self.thread = Thread(target=self.window.doModal)
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self, percent=0):
        self.window.update(percent)

    def iscanceled(self):
        return self.window.iscanceled()

    def close(self):
        try:
            self.window.close()
        except RuntimeError:
            pass
