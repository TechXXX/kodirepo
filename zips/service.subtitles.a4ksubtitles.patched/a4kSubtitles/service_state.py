# -*- coding: utf-8 -*-
"""State the playback service keeps between poll iterations.

One `ServiceContext` is created by `service.start()` and passed to every
service module. Code reads and writes `ctx.state.<field>`; nothing else keeps
per-playback state.
"""


class PlaybackState(object):
    """Per-playback state. `reset()` runs when playback stops or the video changes."""

    def __init__(self):
        # The subtitle that was last attached or translated. Not cleared by
        # reset(): the loop compares it with the file in temp to notice a new one.
        self.last_subfile = None
        self.reset()

    def reset(self):
        # True once this video has been handled (subtitle attached, or nothing to do).
        self.has_done_subs_check = False
        # Kodi's Player.Filenameandpath of the video being handled.
        self.prev_playing_filename = ''
        # Poll faster until this time while a selector payload is waiting.
        self.fast_selector_poll_until = 0.0
        # When the service noticed this video, and the latest time to wait for an
        # embedded preferred-language track before taking a sidecar or downloading.
        self.playback_started_at = 0.0
        self.subtitle_stream_settle_until = 0.0
        # Set once Kodi has listed the video's own tracks, so the wait above ends early.
        self.embedded_wait_over = False
        # The wait decision already logged for this video, so it is logged once.
        self.embedded_wait_logged = ''
        # Chunked AI translation: playback time of the last chunk, and failures in a row.
        self.ai_last_timestamp = None
        self.ai_tries = 0
        # True while the chunked (60-second) AI translation keeps running; full-file translation never sets it.
        self.ai_translation_active = False
        # Label of the AI translation source, for example 'downloaded_english_full'.
        self.ai_translation_source = ''
        # True while a4k's attached subtitle is in use, so the temp folder is kept.
        self.attached_subtitle_active = False
        # Background sync workers already started, as 'playback_url|subtitle_path'.
        self.sync_started_subfiles = set()


class ServiceContext(object):
    def __init__(self, api, monitor):
        self.api = api
        self.core = api.core
        self.monitor = monitor
        self.state = PlaybackState()
