from ..plugin import Plugin
from ..DI import DI
import xbmc

HTTP_TIMEOUT = (5, 20)

class http(Plugin):
    name = "http"
    priority = 0

    def get_list(self, url):
        if url.startswith("http"):
            try:
                return DI.session.get(url, timeout=HTTP_TIMEOUT).text
            except Exception as exc:
                xbmc.log(f"FOD HTTP failed for {url}: {exc}", xbmc.LOGINFO)
