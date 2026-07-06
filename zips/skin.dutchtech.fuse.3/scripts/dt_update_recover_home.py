import xbmc
import xbmcgui


LOG_PREFIX = '###DT-SKIN-RECOVERY###'
INVALID_WINDOW_IDS = {0, 9999}


def _safe_window_id(getter, label):
    try:
        return int(getter())
    except Exception as exc:
        xbmc.log(
            f'{LOG_PREFIX} unable to read {label}: {type(exc).__name__}: {exc}',
            xbmc.LOGINFO)
        return 9999


def main():
    current_window = _safe_window_id(xbmcgui.getCurrentWindowId, 'current_window')
    current_dialog = _safe_window_id(xbmcgui.getCurrentWindowDialogId, 'current_dialog')
    xbmc.log(
        f'{LOG_PREFIX} check current={current_window} dialog={current_dialog}',
        xbmc.LOGINFO)

    if current_window not in INVALID_WINDOW_IDS:
        return
    if current_dialog not in INVALID_WINDOW_IDS:
        return

    xbmc.log(f'{LOG_PREFIX} recovering to Home', xbmc.LOGINFO)
    xbmc.executebuiltin('ReplaceWindow(Home)')


if __name__ == '__main__':
    main()
