# External subtitle timing validation

This note records the implementation and the local evidence gathered on
2026-11-10. Read it with `README.md` before changing automatic subtitle
selection. The goal is to use embedded English subtitle **start times** to
confirm a better external candidate while playback continues. A weak probe
must leave Kodi's current subtitle in place.

## Runtime path and decision rules

1. `a4kSubtitles/service.py` attaches the selector's chosen external UTF-8
   SRT first, then starts a daemon timing worker. Every attachment is guarded
   against a changed playback URL and selector source.
2. `a4kSubtitles/subtitle_sync.py` reads Matroska `LanguageIETF` when present
   and considers every English text track. The service prefers a normal
   English track when it independently confirms a match with at least 90% of
   the strongest track's ordered pairs and no more than 25 ms extra mean
   residual. SDH can still serve as the reference when normal English is
   inconclusive or materially weaker. SDH caption text is never copied into
   the external SRT; only cue start times are compared.
   It reads the Cue index first. When that index has fewer than 16 subtitle
   starts, it samples 4 MiB ranges at Cue-indexed Cluster positions across
   24 timeline windows. Each range is parsed for **all** Clusters it contains,
   including unindexed Clusters. The remote budget is 150 MiB, 80 requests,
   and a 30-second deadline. An in-flight request can finish just after the
   deadline. The parser reads timestamps and block headers, never embedded
   subtitle text, audio, or cue end times.

   Matroska's omitted legacy `Language` element defaults to `eng`, as specified
   in the [Matroska element table](https://www.matroska.org/technical/elements.html).
   The parser applies that default, preserves an explicit non-English value,
   and gives `LanguageIETF` priority regardless of element order. When the
   language is explicitly `und`, a track name beginning `English` or `ENG`
   supplies narrow fallback evidence; a specified non-English language still
   wins over the free-form name.
3. Validation needs at least 16 starts from **one** embedded track and 30
   starts from the external SRT. The ordered matcher pairs starts one to one
   within 400 ms, searches fixed offsets within 30 seconds in 100 ms steps,
   and rejects an ambiguous offset peak. A subtitle change also requires at
   least eight ordered pairs and at most 250 ms mean absolute residual. The
   legacy histogram result is diagnostic only; it cannot change Kodi's
   subtitle.
4. A detected shift below 150 ms is ignored. From 150 to 399 ms, retiming
   requires a material gain over zero offset: zero has at most 75% as many
   ordered matches, or its mean absolute residual is at least 75 ms worse.
   Shifts of 400 ms or more still require the strong match in step 3. The
   400 ms **pairing window** is separate from this retiming decision.
   Generated filenames use `autosync.minus600ms` for a negative offset (cues
   moved earlier) and `autosync.plus600ms` for a positive offset (cues moved
   later). Kodi's subtitle stream list strips punctuation signs from filenames,
   so the spelled-out direction remains visible after the notification fades.
5. If the initially selected SRT has no strong match, the worker searches
   again and downloads up to three other ranked results with
   `preserve_existing=True`. It compares **all** downloaded alternatives
   before choosing the strongest confirmed result by match count, mean
   residual, then absolute correction. An equal fit needing less correction
   wins. Unconfirmed alternatives are logged as rejected. If none confirms,
   the original remains active. Only the winner is attached and notified.

The original SRT must remain available while alternatives are downloaded.
Fallback files have distinct names so provider releases cannot overwrite the
subtitle Kodi is rendering. A worker that outlives its playback must not
attach its result to the next episode. Changes to the long-running service
module require a Kodi restart; do not restart during active playback.

## What the MKV survey showed

The Cue index is the important distinction in the files measured here. Show
release year alone does not predict whether subtitle cues are indexed.

| Source | Matroska encoder | English subtitle starts in Cue index | Full English starts from local ffprobe |
| --- | --- | ---: | ---: |
| Three Californication season 4 files | `mkv2rls v1.4 (date: 2011 mar 29)` | 0 in each | 432, 456, 461 |
| Storm of the Century S01E01, normal / SDH tracks | `libebml v1.4.2 + libmatroska v1.6.4` | 934 / 1,038 | 934 / 1,038 |
| MobLand S01E01 | `Lavf61.5.101` | 1,122 | Not measured over the remote stream |

The Californication files' CuePoints reference video track 1 only. They
contain complete embedded English subtitles, but the probe has to discover
their starts by bounded Cluster sampling. Storm's CuePoints include every
subtitle packet on tracks 3 and 4, and MobLand's include 1,122 starts on
track 3. Those runs can validate timing from the index in roughly one second.
This small sample supports a **muxing/indexing** explanation for why the
newer files reveal more cues; it does not establish that every newer MKV does.
The local Carrie file was excluded because ffprobe reports repeated EBML
parse errors and only a partial subtitle scan.

## Reproducible playback findings

- **Californication S04E02:** The fully downloaded file
  `b7a3493c-2b16-4992-9e88-fa946a85291e.mp4` has 432 embedded English
  starts. Against all four Dutch SRTs at zero offset, ordered 400 ms matches
  were NoGRP 216, generic 88, IMMERSE 72, and FQM 57. IMMERSE has essentially
  the same start timeline as NoGRP shifted 8.3 seconds early, so retiming it
  also produces 216 matches. NoGRP is best **as downloaded**. The older
  one-Cluster probe found 16 starts in about 30 seconds and could not safely
  distinguish the candidates. Reading every Cluster in each 4 MiB range
  found 49 starts in the live run (88.8 MiB, 31 seconds); the worker rejected
  FQM and generic, confirmed NoGRP and shifted IMMERSE with 21 pairs each,
  and attached NoGRP without retiming. A separate remote diagnostic obtained
  52 starts in 30.3 seconds using 116.8 MiB and reached the same decision.
- **Californication S04E03:** The remote probe found 18 embedded starts with
  51% sampled timeline coverage. The selected SRT, IMMERSE, and generic
  release had no strong match. DVDRip XviD-CLUE had 15 exact ordered matches
  at +1,000 ms and was attached with that correction. This is evidence from
  the sampled portion, not a full-file comparison.
- **Californication S04E04:** Two runs each found 33 embedded starts with 64%
  sampled timeline coverage and applied +1,400 ms to the initially selected
  SRT based on 17 ordered matches. No alternatives were downloaded because
  the selected SRT matched strongly.
- **Storm of the Century S01E01:** Both embedded English tracks were indexed
  (934 normal, 1,038 SDH). The selected Dutch SRT had 556 starts. The best
  result used the SDH track with 260 ordered pairs and detected +300 ms, but
  zero offset still had 249 pairs and a slightly *lower* mean residual
  (193 ms versus 197 ms). The small-shift rule kept the original timing.
  S01E03 likewise had 1,247 indexed starts on its richest English track and
  kept the initially selected SRT.
- **MobLand S01E01:** The index exposed 1,122 English starts in 0.8 seconds.
  The selected Dutch SRT had 805 starts and 625 ordered matches at a detected
  +200 ms. Zero offset still had 544 matches; its mean residual was only
  26 ms worse (188 versus 162 ms). The worker kept the SRT unchanged and did
  not download alternatives.
- **SEAL Team S07E08:** The index exposed 702 normal English starts and 800
  SDH starts. The selected Dutch SRT had 407 starts. The earlier track
  ranking chose SDH with 313 ordered matches at -400 ms, versus 312 matches
  and only 1 ms more mean residual on normal English. Both tracks independently
  confirm the same offset. This prompted the comparable-normal preference
  above; rerunning the matcher selects normal English with 312 matches and
  still applies -400 ms. Four preceding SEAL Team probes found no usable
  embedded English text track and therefore retained their original SRTs.
- **Mad Men S01E05 and three other sampled episodes:** The first S01E05 run
  reported zero embedded tracks because its English SubRip track omitted the
  Matroska `Language` element. ffprobe correctly reported `eng`, but the old
  parser incorrectly used `und`. After the default-language fix, a read-only
  remote re-probe found 18 English starts in 30.9 seconds using 80.8 MiB and
  covering 80% of the indexed timeline. This reaches the minimum evidence
  count, but no subtitle was changed during the diagnostic. S02E11, S04E10,
  and S06E12 exposed no subtitle streams in ffprobe and correctly retained
  their originally selected SRTs.
- **Modern Family S09E06:** The old probe returned no English text track,
  although ffprobe found a SubRip track titled `English [CC]`. Its Matroska
  language is explicitly `und`, and the Cue index contains 602 starts for
  that track. The narrow track-name fallback above now exposes those 602
  starts in about 0.4 seconds. The earlier playback kept its selected SRT;
  no live timing decision with the corrected parser has yet been observed.

The local diagnostic video files are under Fen Light's Kodi userdata
`TV Show Downloads` directory, despite several Matroska files having `.mp4`
names. ffprobe identifies the actual container. The live log is
`~/Library/Logs/kodi.log`. Avoid copying signed playback or subtitle download
URLs from that log into issues or documentation.

## Verification for future changes

Run from this addon directory:

```sh
python3 -m py_compile a4kSubtitles/subtitle_sync.py a4kSubtitles/service.py
python3 -m unittest discover -s tests -v
```

The timing tests include multi-Cluster range parsing, one-to-one matching,
SDH track selection, conservative replacement, and the small-offset cases
above. For a live run, inspect `Background subtitle sync probe complete`,
`Background subtitle sync sampling`, `Background subtitle fallback comparing
candidate`, each confirmed or rejected result, and the final `applied` or
`already aligned` line. Logs distinguish `detected_offset_ms` from
`applied_offset_ms` for fallback replacements. A 30-second probe that finds
few cues or covers only part of the timeline is a limited sample, not proof
that an external subtitle is wrong.

When updating the addon, keep the source, the unpacked copy at
`../zips/service.subtitles.a4ksubtitles.patched`, and the installed copy at
`~/Library/Application Support/Kodi/addons/service.subtitles.a4ksubtitles.patched`
in sync. Do not overwrite unrelated conflicted package files.
