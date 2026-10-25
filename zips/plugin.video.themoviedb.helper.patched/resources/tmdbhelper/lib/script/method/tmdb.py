# Module: default
# Author: jurialmunkey
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html
from tmdbhelper.lib.script.method.decorators import is_in_kwargs, get_tmdb_id
from tmdbhelper.lib.addon.plugin import get_localized


@is_in_kwargs({'tmdb_type': ['movie', 'tv']})
@get_tmdb_id
def sync_tmdb(tmdb_type=None, tmdb_id=None, season=None, episode=None, sync_type=None, **kwargs):
    """ Open sync trakt menu for item """
    from tmdbhelper.lib.script.sync.tmdb.menu import sync_item
    sync_item(tmdb_type=tmdb_type, tmdb_id=tmdb_id, season=season, episode=episode, sync_type=sync_type)


def refresh_item(tmdb_type, tmdb_id, season=None, episode=None, **kwargs):
    import xbmcgui
    from tmdbhelper.lib.addon.dialog import BusyDialog
    from tmdbhelper.lib.script.method.kodi_utils import container_refresh
    from tmdbhelper.lib.addon.plugin import get_localized, convert_type
    from tmdbhelper.lib.items.database.baseitem_factories.factory import BaseItemFactory

    def refresh_item_factory(season=None, episode=None):
        mediatype = convert_type(tmdb_type, 'dbtype', season, episode)
        sync = BaseItemFactory(mediatype)
        sync.tmdb_id = tmdb_id
        sync.season = season
        sync.episode = episode
        sync.cache_refresh = 'force'
        sync.cache_translations = True
        sync.data

    with BusyDialog():
        refresh_item_factory(season, episode)

        if episode is not None:
            refresh_item_factory(season)

        if season is not None:
            refresh_item_factory()

    xbmcgui.Dialog().ok(get_localized(32233), f'{tmdb_type} {tmdb_id} {season if season else ""} {episode if episode else ""}')
    container_refresh()


def refresh_cacheonly(path=None, **kwargs):
    from urllib.parse import unquote_plus, urlencode
    from tmdbhelper.lib.addon.logger import kodi_log
    from tmdbhelper.lib.items.router import Router
    from tmdbhelper.lib.script.method.kodi_utils import container_refresh

    if path:
        paramstring = unquote_plus(path)
    else:
        params = {k: v for k, v in kwargs.items() if k not in ('refresh_cacheonly', 'path') and v is not None}
        if not params:
            return
        params['cacheonly'] = 'false'
        params['tmdbhelper_cache_refresh'] = 'true'
        paramstring = urlencode(params, doseq=True)

    kodi_log(['lib.script.method.tmdb - refresh_cacheonly\n', paramstring], 1)
    try:
        items = Router(-1, paramstring).get_directory(items_only=True)
    except Exception as exc:
        kodi_log(['lib.script.method.tmdb - refresh_cacheonly failed\n', f'{exc}'], 1)
        return
    if items:
        container_refresh()


def delete_itemtype(mediatype=None, confirmation=True, **kwargs):
    from xbmcgui import Dialog
    from tmdbhelper.lib.addon.dialog import ProgressDialog
    from tmdbhelper.lib.addon.logger import TimerFunc
    from tmdbhelper.lib.items.database.database import ItemDetailsDatabase

    routes = {
        'movie': {
            'baseitems': ('movie', 'collection', ),
            'tables': (),
        },
        'tvshow': {
            'baseitems': ('tvshow', 'season', 'episode', ),
            'tables': (),
        },
        'all': {
            'baseitems': ('person', 'tvshow', 'season', 'episode', 'movie', 'collection', ),
            'tables': (),
        },
    }

    if not mediatype:
        choices = [i for i in routes.keys()]
        x = Dialog().select('Choose mediatype', choices)
        if x == -1:
            return
        mediatype = choices[x]

    if mediatype not in routes:
        raise Exception(f'The mediatype {mediatype} is not valid!')

    if not Dialog().yesno(
        (
            f'{get_localized(32387).format(mediatype.capitalize())}: '
            f'{get_localized(19194)}'
        ),
        (
            f'[B][COLOR=red][UPPERCASE]{get_localized(14117)}[/UPPERCASE][/COLOR][/B] - '
            f'{get_localized(32053)}'
        )
    ):
        return

    with ProgressDialog(
        title=f'{get_localized(32387).format(mediatype.capitalize())}',
        total=(len(routes[mediatype]['baseitems']) + len(routes[mediatype]['tables']) + 1),
        background=False,
    ) as progress_dialog:
        database = ItemDetailsDatabase()
        with TimerFunc(f'Deleting mediatype {mediatype}:', inline=True):
            for i in routes[mediatype]['baseitems']:
                statement = f'DELETE FROM baseitem WHERE mediatype="{i}"'
                progress_dialog.update(statement)
                database.execute_sql(statement)
            for i in routes[mediatype]['tables']:
                statement = f'DELETE FROM {i}'
                progress_dialog.update(statement)
                database.execute_sql(statement)
            progress_dialog.update('Vacuuming database...')
            database.execute_sql('VACUUM')

    if confirmation:
        head = get_localized(32387).format(mediatype.capitalize())
        data = get_localized(32051).format(mediatype)
        Dialog().ok(head, data)


def delete_listdata(patterns=(), **kwargs):
    from tmdbhelper.lib.addon.dialog import ProgressDialog
    from tmdbhelper.lib.addon.logger import TimerFunc
    from tmdbhelper.lib.files.bcache import BasicCache

    with ProgressDialog(
        title=f'{get_localized(32387).format("List")}',
        total=len(patterns) + 1 if patterns else 2,
        background=False,
    ) as progress_dialog:
        database = BasicCache(filename='ItemContainer.db').ret_cache()
        with TimerFunc(f'Deleting list data:', inline=True):
            for pattern in patterns:
                statement = f'DELETE FROM simplecache WHERE id LIKE "{pattern}"'
                progress_dialog.update(statement)
                database._execute_sql(statement)
            if not patterns:
                statement = f'DELETE FROM simplecache'
                progress_dialog.update(statement)
                database._execute_sql(statement)
            progress_dialog.update('Vacuuming database...')
            database._execute_sql('VACUUM')
