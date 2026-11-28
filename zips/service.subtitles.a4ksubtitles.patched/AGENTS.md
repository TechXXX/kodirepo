# Agent notes for this addon

Read `README.md` for the addon contract and
`docs/subtitle-timing-validation.md` before changing automatic subtitle
selection. The timing note records measured MKV index behavior, live Kodi
outcomes, thresholds, and verification commands.

Read `docs/service-structure.md` before changing the playback service
(`service.py`, `service_state.py`, `subtitle_attach.py`, `selector_handoff.py`,
`ai_translate.py`, `ai_source_timing.py`, `background_sync.py`,
`timing_rules.py`, `runtime_languages.py`). It maps the modules, the state
they share, the path one video takes, and the decisions that must not change.
Update it whenever you move, add or remove a function there.

- Keep per-playback state in `PlaybackState` (`ctx.state`), not in module
  globals or closures, and reach Kodi only through `ctx.core` so the
  `tests/service_fakes.py` fakes keep working.
- Keep imports one-way as described in that note; nothing imports `service.py`.
- Add or update a test in `tests/test_service_flow.py` or
  `tests/test_service_modules.py` for any change to these modules.

- Keep timing-based replacement conservative. A weak or ambiguous embedded
  sample leaves Kodi's active subtitle in place. Compare all downloaded
  fallback candidates before selecting a confirmed winner.
- The runtime probe uses cue starts only. Preserve its bounded remote reads,
  one-to-one matching, playback-change guards, normal-English preference when
  its evidence is comparable to SDH, and `preserve_existing=True` downloads.
- Test source changes, then keep this source directory, the unpacked
  `../zips/service.subtitles.a4ksubtitles.patched` copy, and the installed
  Kodi addon copy synchronized. Avoid unrelated conflicted package files.
- Kodi must restart to load a changed long-running service module. Never
  restart it automatically during active playback.
- The Kodi log can contain signed media and subtitle URLs. Do not copy those
  URLs into documentation or reports.
