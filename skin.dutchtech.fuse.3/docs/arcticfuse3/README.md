# Arctic Fuse 3 Customisation Notes

This folder is the working notebook for AF3 customisation on this Mac. The
actual source repos currently live next to it:

- `/Users/kalter/Documents/CODEX/kodirepo`
- `/Users/kalter/Documents/CODEX/KodiEnglish`

## Repo Map

- `kodirepo/skin.dutchtech.fuse.3`
  - Add-on id: `skin.dutchtech.fuse.3`
  - Name: `DutchTech Fuse 3`
  - Current version read from source: `3.2.9.7`
  - TMDb Helper dependency and routes point to
    `plugin.video.themoviedb.helper.patched`.
- `KodiEnglish/skin.dutchtech.fuse.3.kodienglish`
  - Add-on id: `skin.dutchtech.fuse.3.kodienglish`
  - Name: `Kodi English Fuse 3`
  - Current version read from source: `3.2.9.1006`
  - TMDb Helper dependency and routes point to
    `plugin.video.themoviedb.helper.patched.kodienglish`.
- Both forks are based on Jurialmunkey Arctic Fuse 3 `v3.2.9` and use the same
  broad file layout as the live upstream install.
- Generated repo output lives under `zips/`; do not hand-edit it.

## Live Kodi Install

The MacBook live install currently has the upstream AF3 id:

- `/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.3`
- `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/skin.arctic.fuse.3/settings.xml`

The live add-on reports version `3.2.9` and is patched locally to depend on
`plugin.video.themoviedb.helper.patched`. It has a `.git` file, but that
metadata points at a missing submodule path, so use explicit backups or external
diffs rather than relying on git status inside the live add-on folder.

The live install also has:

- `skin.arctic.fuse.2`
- `skin.arctic.horizon.2.patched`

## Useful Skin Entry Points

- `1080i/Home.xml` starts the home window, runs SkinVariables, sets TMDb Helper
  window IDs, and delegates the actual screen to `Hub_Window`.
- `1080i/Includes.xml` is the main include index. It loads constants, home,
  hub, widget, layout, OSD, search, generated SkinVariables includes, and
  fallback includes.
- `1080i/Includes_Home.xml` controls the top or side home switcher, focus
  movement, home icons, submenu panel, and menu object behavior.
- `1080i/Includes_Hubs.xml` controls the hub window body: spotlight, widget
  groups, widget selector, info panels, and standard/wall/combined modes.
- `1080i/Includes_Widgets.xml` contains reusable widget rows, loading states,
  no-results states, and widget labels.
- `1080i/Includes_Layouts.xml` contains shared item layouts and dialog layouts.
- `1080i/Includes_Constants.xml` and aspect-ratio constant files hold most
  geometry values for views, widgets, dialogs, OSD, keyboard, and artwork.
- `1080i/Includes_Paths.xml` centralizes TMDb Helper/plugin paths used by OSD,
  details pages, cast/crew, recommendations, trailers, comments, artwork, and
  search helpers.
- `1080i/Includes_Search.xml` and `1080i/Custom_1105_Search.xml` drive the AF3
  search hub.
- `1080i/VideoOSD.xml`, `1080i/Includes_OSD.xml`, and `1080i/Custom_1147_OSD_SubtitleStreams.xml`
  drive playback controls and stream selectors.
- `1080i/Includes_SkinSettings.xml`, `1080i/Custom_1115_Window_Shortcuts.xml`,
  and `1080i/Custom_1116_Dialog_Shortcuts.xml` drive the user-facing
  customisation screens.

## SkinVariables And Generated Files

Home menu and widget configuration is built through SkinVariables:

- `shortcuts/skinvariables-generator.json`
- `shortcuts/skinvariables-shortcut-homewidgets.json`
- `shortcuts/skinvariables-shortcut-homesubmenu.json`
- `shortcuts/skinvariables-shortcut-searchwidgets.json`
- `shortcuts/generator/data/base/*.xml`
- `shortcuts/generator/data/setup/*.xml`

Generated include files are loaded by `1080i/Includes.xml`, including
`script-skinvariables-generator-includes-.xml` for the default skin user and
`script-skinvariables-skinusers.xml` for named skin users. The live install has
a generated `script-skinvariables-generator-includes-.xml` that is not present
in the repo source tree.

## Customisation Workflow

1. Prototype on the live Kodi install at
   `/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.3`.
2. Keep a before/after diff or explicit backup for every live file edited.
3. If the change is wanted permanently, port it into:
   - `kodirepo/skin.dutchtech.fuse.3`
   - `KodiEnglish/skin.dutchtech.fuse.3.kodienglish`, when appropriate.
4. Preserve the add-on-specific route names:
   - local live AF3 prototype: `plugin.video.themoviedb.helper.patched`
   - DutchTech repo fork: `plugin.video.themoviedb.helper.patched`
   - KodiEnglish fork: `plugin.video.themoviedb.helper.patched.kodienglish`
5. For publishable repo changes, bump the source add-on version, regenerate the
   package output and `addons.xml`, then commit intentionally. Do not edit
   generated `zips/`, `addons.xml`, or `addons.xml.md5` by hand.

## AF2 List Media Port Notes

AF2 names the screenshot view "List Media" as view ID `552`; AF3 already has the
equivalent label/icon slot as view ID `507`. In the live AF3 install, `507` was
defined and implemented, but not offered for sparse plugin/file contexts such as
`Container.Content(files)`, which is the context shown by Fen Light folders.

Live prototype change made on 2026-06-12:

- Added AF3 view `507` to the `videos`, `files`, `sources`, `addons`, and
  fallback `none` view rules in
  `/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.3/shortcuts/skinviewtypes.json`.
- Placed `507` before `506` in those sparse rules so the chooser shows
  `List Media` before `List Basic`, matching the AF2 dialog order.
- Replaced the live AF3
  `/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.3/extras/viewtypes/list-media.jpg`
  with AF2's preview image from
  `/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.2/extras/viewtypes/list-media.jpg`.
- Backups were created beside the live AF3 files with suffix
  `.bak-af2-listmedia-20260612-205043`.
- Fen Light had an existing per-plugin SkinVariables override in userdata:
  `/Users/kalter/Library/Application Support/Kodi/userdata/addon_data/script.skinvariables/skin.arctic.fuse.3-viewtypes.json`
  mapped `plugin.video.fenlight.patched` files to `506`. The live prototype
  changes that active mapping to `507`.
- The generated live include
  `/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.3/1080i/script-skinviewtypes-includes.xml`
  was also patched so `Exp_View_507` is active for Fen Light files immediately.
  Backups for these generated/userdata files use suffix
  `.bak-af2-listmedia-20260612-205408`.

## Live TMDb Helper Patch Notes

OSD episode and cast panels are wired through `Path_OSD_Episodes` and
`Path_OSD_Cast` in `1080i/Includes_Paths.xml`. On 2026-06-13, Kodi logs showed
these calls failing because the live AF3 install still requested the disabled
upstream helper id, `plugin.video.themoviedb.helper`, while the enabled helper
on this Mac is `plugin.video.themoviedb.helper.patched`.

Live prototype change made on 2026-06-13:

- Replaced live AF3 helper routes with `plugin.video.themoviedb.helper.patched`
  across the 23 skin files that referenced TMDb Helper.
- Updated the live `addon.xml` dependency to
  `plugin.video.themoviedb.helper.patched` version `6.15.2.11`.
- Backup archive:
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-tmdbhelperpatched-20260613-005350.tgz`.
- Validation: no remaining unpatched helper routes, no `.patched.patched`
  routes, and the touched XML/JSON files pass `xmllint`/`jq`.

## Live Add-on Browser Update Check Notes

AF3's add-on browser includes an "Available updates" category, but it did not
expose Estuary's standard "Check for updates" action. The live
`1080i/AddonBrowser.xml` already called `SendClick(9)` from add-on category
selection, but the file did not define the standard hidden/side-menu control
`id="9"` that Kodi uses for repository update checks.

Live prototype change made on 2026-06-14:

- Added a visible `$LOCALIZE[24034]` "Check for updates" row to the add-on
  browser category list.
- Added an offscreen `control type="button" id="9"` labeled `$LOCALIZE[24034]`
  so `SendClick(9)` can invoke Kodi's built-in repository update check.
- Backup archive:
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-addonbrowser-checkupdates-20260614-081317.tgz`.
- Validation: live `1080i/AddonBrowser.xml` passes `xmllint --noout`.
- Ported to both repo forks on 2026-06-14:
  `kodirepo/skin.dutchtech.fuse.3` and
  `KodiEnglish/skin.dutchtech.fuse.3.kodienglish`.

## Live Next Page Artwork Notes

The large "Next Page" chevron fanart in AF3 comes from plugin next-page artwork,
not from a normal movie/show fanart path. Fen Light's generated next-page item
uses the `D2wG9Ak` icon URL, which the live AF3 background blur path was treating
like real fanart.

Live prototype change made on 2026-06-13:

- Ported the calmer AH2 `fallback/next-page-background.png` asset into live AF3.
- Added next-page detection for `D2wG9Ak`, `YpaXaLM`, `Next Page`, `page=`, and
  `new_page=` markers in the live background/artwork variables.
- The focused next-page tile now prefers AF3's existing `fallback/more-items.png`
  or `fallback/more-items-wide.png` instead of the plugin's large arrow artwork.
- Added `Image_Background_Tiled` so blur mode does not append `-tiled.jpg` to the
  static next-page fallback PNG.
- Suppressed next-page title/plot/lower-label variables so the hero area no
  longer renders the oversized `Next Page (2) >>` text over the fallback art.
- Follow-up on 2026-06-13: AF3's blur mode was drawing the fallback through its
  200% quadrant layer, which pushed the chevron down behind the widget row. Added
  `Exp_NextPageBackground`, bypassed the quadrant layer for next-page artwork,
  and hid `Info_Panel` when its selected item is a next-page card.
- Follow-up page marker: added `Label_NextPageIndicator` and
  `Background_NextPage_PageMarker`, which show a small marker such as `Page 1`
  above the next-page chevron. The mapped range is next pages 2-20, with a raw
  `Next Page (...)` fallback.
- Backup archives:
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-fanart-20260613-102326.tgz`
  and
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-background-include-20260613-103026.tgz`
  and
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-labels-20260613-103513.tgz`
  and
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-background-layout-20260613-111553.tgz`
  and
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-info-panel-20260613-111904.tgz`
  and
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-page-marker-20260613-112703.tgz`.
- Follow-up backup for the marker wording/position:
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-page-marker-position-20260613-113308.tgz`.
- Follow-up backup for centering the marker over the three blue dots:
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-page-marker-dot-align-20260613-113759.tgz`.
- Manual marker tuning: the live marker is in
  `/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.3/1080i/Includes_Background.xml`
  under `Background_NextPage_PageMarker`. Smaller `<right>` moves it right,
  larger `<right>` moves it left; smaller `<top>` moves it up, larger `<top>`
  moves it down. A local browser tuner exists at
  `/Users/kalter/Documents/CODEX/ArcticFuse3/tools/next-page-marker-tuner.html`,
  but Kodi's rendered placement differs from the raw PNG preview, so use it only
  for rough placement and confirm in Kodi after a restart/reload.
- Reverted an attempted widget-only split after restart showed the single marker
  position was correct. Backup of that reverted split attempt:
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-widget-marker-split-20260613-115420.tgz`.
- Fresh-widget follow-up: fresh home widgets could show the plugin's raw
  next-page fanart until opening/backing out primed TMDbHelper's current image
  properties. Added `NextPage.Widget` focus tracking in `Includes_Lists.xml`
  and routed `Image_Current_Background`, `Image_Background`,
  `Image_Background_Tiled`, `Image_Foreground_NoService`, `Image_Foreground`,
  and `Image_FanartFallback` through `Exp_NextPageBackground`. Backup:
  `/Users/kalter/Documents/CODEX/ArcticFuse3/backups/skin.arctic.fuse.3-nextpage-fresh-widget-detect-20260613-120749.tgz`.
- Fresh-widget correction: `List_Widget_Row_HiddenButton` also needs to pass
  `Container($PARAM[id]).` into `List_Widget_Row_HiddenButton_OnFocus`; otherwise
  the hidden-button focus route can clear `NextPage.Widget` without being able to
  set it again for a next-page item.
- Category-switch correction: switching between home categories can focus a fresh
  widget row without re-running the item hidden-button focus path. `Widget_Row`
  and `Widget_Info_Row` now set/clear `NextPage.Widget` directly from their active
  containers, and the hub zoom/flixart artwork layer is disabled whenever
  `Exp_NextPageBackground` is true.
- Category-switch route correction: the Films/Series category-tab widgets are
  generated as `Hub_Combined_Widget` / `Hub_Wall_Widget`, not `Widget_Row`, so
  those hub includes also need to set/clear `NextPage.Widget` from their active
  `Container($PARAM[id]).ListItem`.
- Log-driven category-switch correction: Kodi's debug log showed category
  switches refreshing generated home widget containers `501+` while focus could
  remain on the selector row. Added `Exp_HomeWidget_NextPage_Active` for active
  generated widget containers `501-516`, stopped the selector focus path from
  clearing `NextPage.Widget`, and made the non-blur next-page branch use the
  same next-page-aware background image.
- Fresh-widget layering correction: the page marker could be visible while a
  stale helper/foreground next-page arrow remained lower in the background stack.
  `Background_Main_Plain` and `Background_Main_Standard` now draw
  `fallback/next-page-background.png` as the final background layer whenever
  `Exp_NextPageBackground` is true, with the page marker redrawn above it.
- Temporary diagnostic logging was used and then removed from the live skin.
  Historical `AF3-NEXTPAGE` traces showed row focus fires on entry but not on
  left/right item movement, so `Exp_FocusedContainer_NextPage` now also checks
  `Container.ListItem.*` directly for the selected widget item.
- Films/Series hub edge-case fix on 2026-06-17: moving up from a widget
  next-page tile to the hub category strip could hide the `Next Page (2) >>`
  title while leaving the large chevron fanart in the background. That chevron
  was no longer coming from `Exp_NextPageBackground`; it was stale
  `TMDbHelper.ListItem.BlurImage*` / `Current.BlurImage*` data still flowing
  through the normal background variables. The working fix adds
  `Exp_NextPageBlurImage` and blanks `Image_Current_Background`,
  `Image_Background`, `Image_Background_Tiled`, and `Image_Foreground` whenever
  those helper blur properties still point at the plugin next-page art
  (`D2wG9Ak`, `YpaXaLM`, `nextpage`, or `next-page`). The normal next-page
  state is still handled by `Exp_NextPageBackground`, so the clean fallback art
  and page marker remain visible on the actual next-page tile.
- The same 2026-06-17 pass tightened the selector/top-control state: generic
  `Exp_NextPageItem` and `Exp_FocusedContainer_NextPage` no longer treat
  `page=` / `new_page=` paths alone as a background trigger, hub selector focus
  marks `TMDbHelper.WidgetContainer` as `601` and clears `NextPage.Widget`, and
  hub info/background fanart variables are guarded while the selector/home
  controls have focus.
- Validation: touched XML files pass `xmllint`, and all referenced fallback
  image files exist in the live AF3 skin.
- Repo port on 2026-06-13: the cleaned next-page widget fix was copied into
  both `kodirepo` and `KodiEnglish` source skin folders and their matching
  `zips/` snapshots, including `media/fallback/next-page-background.png`.
- Repo port on 2026-06-17: the stale blur edge-case fix was copied into both
  repo forks and packaged as `skin.dutchtech.fuse.3` `3.2.9.7` and
  `skin.dutchtech.fuse.3.kodienglish` `3.2.9.1006`.
- Detailed next-page widget handoff for future agents:
  `NEXT_PAGE_WIDGET_HANDOFF.md`.

## KodiEnglish Guardrail

KodiEnglish has an explicit handover rule: do not port subtitle selector or a4k
subtitle integration work there unless the user explicitly asks for it in the
same conversation. Visual skin customisation is allowed, but subtitle-selector
logic belongs in the normal/test repos.
