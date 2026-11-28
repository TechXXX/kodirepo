# -*- coding: utf-8 -*-
"""Fen Light Patched's subtitle selector hands a4k its pick through Kodi window properties.

Before playback, Fen's selector stores the matched subtitle (or an English
subtitle to AI-translate) in `subs.selector_payload`, plus the source key, the
player filename and the direct playback URL. The service reads them here and
only trusts a payload that belongs to the video that is playing now.
"""

selector_source_key_prop = 'subs.selector_source_key'
selector_payload_prop = 'subs.selector_payload'
selector_player_filename_prop = 'subs.player_filename'
selector_playback_url_prop = 'subs.selector_playback_url'


def matched_subtitle_name(result):
    if not isinstance(result, dict):
        return ''

    action_args = result.get('action_args') or {}
    return result.get('name') or action_args.get('filename') or result.get('filename') or ''


def result_identity(result):
    """Service, URL and release name: what makes two search results the same subtitle."""
    result = result or {}
    action_args = result.get('action_args') or {}
    return (
        result.get('service_name') or '',
        str(action_args.get('url') or ''),
        action_args.get('release_name') or action_args.get('filename') or result.get('name') or '',
    )


def clear_runtime_state(core, clear_temp=False):
    for prop in (
        selector_source_key_prop,
        selector_payload_prop,
        selector_player_filename_prop,
        selector_playback_url_prop,
    ):
        try:
            core.kodi.clear_property(prop)
        except:
            pass

    if clear_temp:
        try:
            core.shutil.rmtree(core.utils.temp_dir, ignore_errors=True)
        except:
            pass


def current_playing_url(core):
    return (
        core.kodi.xbmc.getInfoLabel('Player.FilenameAndPath')
        or core.kodi.xbmc.getInfoLabel('Player.Filenameandpath')
        or core.kodi.xbmc.Player().getPlayingFile()
        or ''
    )


def direct_playback_url(core):
    """The stream URL to range-read: Kodi's, or the selector's while Kodi still reports the Fen plugin URL."""
    playback_url = current_playing_url(core)
    if playback_url.startswith('plugin://'):
        playback_url = core.kodi.get_property(selector_playback_url_prop) or ''
    if not playback_url or playback_url.startswith('plugin://'):
        return ''
    return playback_url


def playback_labels(core):
    labels = []
    for label in ('Player.FilenameAndPath', 'Player.Filenameandpath', 'Player.Filename'):
        try:
            value = core.kodi.xbmc.getInfoLabel(label)
        except:
            value = ''
        if value:
            labels.append(str(value))
    try:
        value = core.kodi.xbmc.Player().getPlayingFile()
    except:
        value = ''
    if value:
        labels.append(str(value))
    return labels


def is_fen_playback(labels):
    fen_prefixes = (
        'plugin://plugin.video.fenlight.patched/',
    )
    for label in labels:
        lowered = str(label or '').strip().lower()
        for prefix in fen_prefixes:
            if lowered.startswith(prefix):
                return True
    return False


def path_leaf(value):
    value = str(value or '').strip()
    for separator in ('?', '#'):
        if separator in value:
            value = value.split(separator, 1)[0]
    value = value.replace('\\', '/')
    if '/' in value:
        value = value.rsplit('/', 1)[-1]
    return value


def release_key(value):
    value = path_leaf(value).lower()
    for encoded, replacement in (
        ('%20', ' '),
        ('%2e', '.'),
        ('%2d', '-'),
        ('%5f', '_'),
        ('+', ' '),
    ):
        value = value.replace(encoded, replacement)
    for extension in ('.mkv', '.mp4', '.avi', '.m2ts', '.ts', '.srt', '.sub', '.ass', '.ssa', '.vtt'):
        if value.endswith(extension):
            value = value[:-len(extension)]
            break
    for separator in ('.', '_', '-', '[', ']', '(', ')'):
        value = value.replace(separator, ' ')
    return ' '.join(value.split())


def text_matches_current_playback(expected, labels):
    expected_key = release_key(expected)
    if len(expected_key) < 8:
        return False

    for label in labels:
        label_key = release_key(label)
        if len(label_key) < 8:
            continue
        if expected_key == label_key:
            return True
        if len(expected_key) >= 12 and expected_key in label_key:
            return True
        if len(label_key) >= 12 and label_key in expected_key:
            return True
    return False


def value_matches_current_label(expected, labels):
    expected = str(expected or '').strip()
    if len(expected) < 12:
        return False

    expected_lower = expected.lower()
    for label in labels:
        label = str(label or '').strip()
        label_lower = label.lower()
        if expected_lower == label_lower:
            return True
        if len(expected_lower) >= 40 and len(label_lower) >= 40 and (
            expected_lower in label_lower or label_lower in expected_lower
        ):
            return True
    return False


def source_key_matches_current_playback(source_key, labels):
    for part in str(source_key or '').split('|'):
        if text_matches_current_playback(part, labels):
            return True
    return False


def payload_matches_current_playback(core, current_source_key, payload):
    labels = playback_labels(core)
    if not labels:
        return True

    if is_fen_playback(labels):
        return True

    if value_matches_current_label(core.kodi.get_property(selector_playback_url_prop), labels):
        return True

    fen_player_filename = core.kodi.get_property(selector_player_filename_prop)
    if text_matches_current_playback(fen_player_filename, labels):
        return True

    if source_key_matches_current_playback(current_source_key, labels):
        return True

    return source_key_matches_current_playback(payload.get('source_key', ''), labels)


def short_text(value, limit=180):
    value = str(value or '')
    if len(value) <= limit:
        return value
    return value[:limit] + '...'


def forced_subtitle_result(core):
    """Return (matched_subtitle, payload) from the selector, or (None, payload/None) when it cannot be used."""
    payload_text = core.kodi.get_property(selector_payload_prop)
    if not payload_text:
        return (None, None)

    current_source_key = core.kodi.get_property(selector_source_key_prop)
    if not current_source_key:
        core.logger.debug('selector subtitle payload ignored because source key is missing')
        clear_runtime_state(core, clear_temp=True)
        return (None, None)

    try:
        payload = core.json.loads(payload_text)
    except Exception as exc:
        core.logger.debug('selector subtitle payload parse failed: %s' % exc)
        clear_runtime_state(core, clear_temp=True)
        return (None, None)

    payload_source_key = payload.get('source_key', '')
    if payload_source_key and payload_source_key != current_source_key:
        core.logger.debug(
            'selector subtitle payload ignored for stale source key | payload=%s | current=%s' % (
                payload_source_key,
                current_source_key,
            )
        )
        clear_runtime_state(core, clear_temp=True)
        return (None, payload)

    if not payload_matches_current_playback(core, current_source_key, payload):
        core.logger.debug(
            'selector subtitle payload ignored for non-Fen/current playback | player=%s | fen_player_filename=%s | source_key=%s' % (
                short_text(' || '.join(playback_labels(core))),
                short_text(core.kodi.get_property(selector_player_filename_prop)),
                short_text(current_source_key),
            )
        )
        clear_runtime_state(core, clear_temp=True)
        return (None, payload)

    matched_subtitle = payload.get('matched_subtitle')
    if not isinstance(matched_subtitle, dict):
        return (None, payload)

    if not matched_subtitle.get('service_name') or not isinstance(matched_subtitle.get('action_args'), dict):
        core.logger.debug('selector subtitle payload missing service/action_args')
        return (None, payload)

    return (matched_subtitle, payload)


def payload_requires_ai_translation(payload):
    if not isinstance(payload, dict):
        return False
    return bool(payload.get('requires_ai_translation'))
