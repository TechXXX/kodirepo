import xbmcaddon
import traceback
try:
    from resources.lib.DI import DI
    from resources.lib.plugin import run_hook, register_routes
except ImportError:
    from .resources.lib.DI import DI
    from .resources.lib.plugin import run_hook, register_routes

try:
    from resources.lib.util.common import *
except ImportError:
    from .resources.lib.util.common import *

root_xml_url = ownAddon.getSetting('root_xml') or "file://main.xml"

#root_xml_url =  "file://scraper_list.json"

plugin = DI.plugin
short_checker = ([
    'Adf.ly',
    'Bit.ly',
    'Chilp.it',
    'Clck.ru',
    'Cutt.ly',
    'Da.gd',
    'Git.io',
    'goo.gl',
    'Is.gd',
    'NullPointer',
    'Os.db',
    'Ow.ly',
    'Po.st',
    'Qps.ru',
    'Short.cm',
    'Tiny.cc',
    'TinyURL.com',
    'Git.io',
    'Tiny.cc',
     ])

@plugin.route("/")
def root() -> None:
    get_list(root_xml_url)

@plugin.route("/get_list/<path:url>")
def get_list(url: str) -> None:
    #do_log(f" Reading url at route >  {url}" )
    url = url.replace('.xmll', '.xml')
    _get_list(url)

def _display_empty(message=None):
    if message:
        xbmc.log(f"FOD: {message}", xbmc.LOGINFO)
    run_hook("display_list", [])

def _get_list(url):
    #do_log(f" Reading url >  {url}" )
    if any(check.lower() in url.lower() for check in short_checker):
        try:
            url = DI.session.get(url, timeout=(5, 20)).url
        except Exception as exc:
            _display_empty(f"Failed to resolve short URL {url}: {exc}")
            return
    try:
        response = run_hook("get_list", url)
    except Exception:
        _display_empty(f"Failed to load list {url}\n{traceback.format_exc()}")
        return
    if response:
        #do_log(f'default - response = \n {str(response)} ' )
        try:
            jen_list = run_hook("parse_list", url, response)
        except Exception:
            _display_empty(f"Failed to parse list {url}\n{traceback.format_exc()}")
            return
        #do_log(f'default - jen list = \n {str(jen_list)} ')
        if not isinstance(jen_list, list):
            _display_empty(f"No playable list items parsed from {url}")
            return
        if ownAddon.getSettingBool("use_cache") and not "tmdb/search" in url:
            DI.db.set(url, response)
        try:
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [item for item in jen_list if item]
            jen_list = [
                run_hook("get_metadata", item, return_item_on_failure=True)
                for item in jen_list
            ]
        except Exception:
            _display_empty(f"Failed to build list {url}\n{traceback.format_exc()}")
            return
        run_hook("display_list", jen_list)
    else:
        _display_empty(f"No response for list {url}")

@plugin.route("/play_video/<path:video>")
def play_video(video: str):
    _play_video(video)

def _play_video(video):
    import base64
    video_link = ''
    video = base64.urlsafe_b64decode(video)
    if '"link":' in str(video) :
        video_link = run_hook("pre_play", video)
        if video_link :
            run_hook("play_video", video_link)
    else :
        run_hook("play_video", video)

@plugin.route("/settings")
def settings():
    xbmcaddon.Addon().openSettings()

@plugin.route("/clear_cache")
def clear_cache():
    DI.db.clear_cache()
    import xbmc
    #xbmc.sleep(1000)
    xbmc.executebuiltin("Container.Refresh")

register_routes(plugin)

def main():
    plugin.run()
    return 0

if __name__ == "__main__":
    main()
