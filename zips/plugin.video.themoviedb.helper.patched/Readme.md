# TMDb Helper Patched [![License](https://img.shields.io/badge/License-GPLv3-blue)](https://github.com/jurialmunkey/plugin.video.themoviedb.helper/blob/master/LICENSE.txt)

<table><tr><td><img src="https://github.githubassets.com/images/modules/site/icons/funding_platforms/ko_fi.svg" width="48" height="48" /></td><td><b>Buy me a Coffee</b><br>https://ko-fi.com/jurialmunkey</td></tr></table>

<img src="https://github.com/jurialmunkey/plugin.video.themoviedb.helper/blob/matrix/icon.png" width="256" height="256" />

Patched staging fork based on TMDb Helper `v6.15.2`.

See the [TMDbHelper Wiki](https://github.com/jurialmunkey/plugin.video.themoviedb.helper/wiki) for upstream usage details.



## Installation 

Install via the repository that ships this patched fork to ensure all module dependencies are up to date. 


Kodi File Manager Source:
https://jurialmunkey.github.io/repository.jurialmunkey/

Direct ZIP Install:
https://jurialmunkey.github.io/repository.jurialmunkey/repository.jurialmunkey-3.4.zip 

Instructions:

1. Enable "Unknown Sources" in Kodi Settings > System > Add-ons
2. Enable "Update official add-ons from: Any repositories" in Kodi Settings > System > Add-ons
3. Install my repository using either the zip or file manager source linked above
4. Install the latest version of `plugin.video.themoviedb.helper.patched` from your repo

## Patched Agent Notes

This patched fork is part of the local Fen Light Patched / a4kSubtitles
Patched setup. For playback, TMDb Helper is usually the launcher, not the
source resolver.

For the broader cross-addon handover, including Fen Light Patched, POV,
Umbrella, FenLight AM, IntroDB, Trakt/resume boundaries, and known no-source
edge cases, read `../AGENT_HANDOVER.md`.

Bundled Fen Light Patched player definitions live in:

- `resources/players/fenlight.patched.auto.json`
- `resources/players/fenlight.patched.select.json`

Both set `is_resolvable=false` and launch:

- `plugin://plugin.video.fenlight.patched/?mode=playback.media...&autoplay=true`
- `plugin://plugin.video.fenlight.patched/?mode=playback.media...&autoplay=false`

After that launch, Fen owns metadata lookup, source scraping, resolving,
playback, subtitle-aware retry-pool ordering, watched/progress updates, and
resume behavior. TMDb Helper should not be expected to supply sources or force
Fen to seek correctly after another player takes over.

Kodi may use user-profile player copies instead of these bundled defaults. On
this Mac, check:

`/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/plugin.video.themoviedb.helper.patched/players`

### Trakt Boundary

TMDb Helper's Trakt authorization is real, but scoped. It supports TMDb Helper
lists, indicators, progress metadata, player placeholders, and scrobbling when
the TMDb Helper monitor can see enough Kodi playback metadata.

It does not authorize external player addons. Fen, POV, Umbrella, Magneto, and
similar launched players still own their own Trakt/resume integration and
their own local playback state. A TMDb Helper resume prompt can pass intent
into a launch path, but the launched player must preserve or apply the seek.
