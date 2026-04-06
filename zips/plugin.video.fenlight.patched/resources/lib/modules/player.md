## player.py notes

- `FenLightPlayer.run()` is the preferred playback entry point for resolved video sources.
- `run()` goes through `play_video()` and calls `self.play(self.url, self.make_listing())`.
- `run_resolved()` exists, but it uses `setResolvedUrl()` and was linked to playback failures on at least one macOS Kodi install.
- Practical rule: if a resolved Real-Debrid or similar direct media URL should start playback, prefer `run()` unless there is a verified reason to switch back.

## Responsibilities

- Build the Kodi listitem used for playback.
- Start playback and detect whether playback really began.
- Close progress dialogs once playback is confirmed.
- Monitor playback for bookmarks, watched state, and next-episode behavior.

## Debugging guidance

- If logs show a source resolves correctly but playback never starts, inspect the caller in `sources.py` first.
- If logs show `VideoPlayer::OpenFile` followed by demux failure, the issue may be below Fenlight in Kodi/player/runtime handling.
- Be careful about changing `run()` vs `run_resolved()` behavior without testing on the target Kodi environment.
