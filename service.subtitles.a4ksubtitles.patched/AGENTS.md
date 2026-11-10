# Agent notes for this addon

Read `README.md` for the addon contract and
`docs/subtitle-timing-validation.md` before changing automatic subtitle
selection. The timing note records measured MKV index behavior, live Kodi
outcomes, thresholds, and verification commands.

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
