
# DutchTech Fuse [![License](https://img.shields.io/badge/license-CC--NC--SA%204.0-green)](http://creativecommons.org/licenses/by-nc-sa/4.0/)

This work is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 Unported License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/
or send a letter to Creative Commons, 171 Second Street, Suite 300, San Francisco, California, 94105, USA.

## DutchTech Fork

This package is a DutchTech-maintained fork of Jurialmunkey's Arctic Fuse 3 v3.2.9 with a separate Kodi addon id, custom artwork, and patched TMDb Helper routing.

## Maintainer Notes

- Add-on id: `skin.dutchtech.fuse.3`.
- Current source version: `3.2.9.12`.
- Patched TMDb Helper dependency: `plugin.video.themoviedb.helper.patched`.
- Most fork-specific differences from upstream AF3 are add-on identity,
  artwork, and TMDb Helper route rewrites.
- Main XML entry points:
  - `1080i/Home.xml` starts the home window and delegates to `Hub_Window`.
  - `1080i/Includes.xml` is the include index for constants, views, widgets,
    OSD, search, paths, and generated SkinVariables includes.
  - `1080i/Includes_Home.xml` controls the home switcher and submenu behavior.
  - `1080i/Includes_Hubs.xml` controls spotlight, hub modes, widget groups,
    selectors, and info panels.
  - `1080i/Includes_Widgets.xml` contains reusable widget rows and loading/no
    results states.
  - `1080i/Includes_Paths.xml` centralizes TMDb Helper plugin paths.
  - `1080i/Includes_SkinSettings.xml`, `1080i/Custom_1115_Window_Shortcuts.xml`,
    and `1080i/Custom_1116_Dialog_Shortcuts.xml` drive the customization UI.
  - `1080i/VideoOSD.xml` and `1080i/Includes_OSD.xml` drive playback controls.
- Home menu and widget defaults are generated from files under `shortcuts/`,
  especially `shortcuts/skinvariables-generator.json` and
  `shortcuts/generator/data/`.
- Test visual changes first on the live Mac Kodi install when possible, then
  port accepted changes here with the patched helper id preserved.

## 2026-07-05 Favourites Browser Note

The custom favourites dialog now hands off to Kodi's native favourites browser,
and `MyFavourites.xml` uses the skin's dialog panel/list treatment instead of
the older media-info panel layout.

## 2026-07-06 Notification Recovery Note

`DialogNotification.xml` now schedules a silent recovery script. The script only
calls `ReplaceWindow(Home)` when Kodi reports invalid active window and dialog
ids, which avoids forcing Home during ordinary notifications.
