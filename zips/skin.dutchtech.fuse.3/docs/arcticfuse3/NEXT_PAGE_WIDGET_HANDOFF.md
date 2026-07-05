# AF3 Next-Page Widget Handoff

Last updated: 2026-06-17 20:50 CEST.

## Scope

This work is being tested in the live Kodi install first:

`/Users/kalter/Library/Application Support/Kodi/addons/skin.arctic.fuse.3`

The cleaned live fix has now been ported into the two repo forks and their
`zips/` snapshots.

## User-Visible Goal

Port the cleaner AF2/AH2-style "Next Page" fanart treatment into AF3. Addon
next-page screens now look acceptable. The remaining focus has been home widget
rows, especially "fresh" widgets after switching Films/Series categories.

Desired widget result:

- Show `media/fallback/next-page-background.png` as the full-screen next-page
  background.
- Show the page marker (`Page 1`, `Page 2`, etc.) centered above the three blue
  dots.
- Avoid the original addon-supplied Imgur fanart with the large low chevron
  flashing through behind the widget row.

## Current State

The main widget issue is fixed enough that the user said they are happy with how
it is working now. The brief first-load chevron flash was handled by dynamically
hiding old flixart/blur layers when `Exp_NextPageBackground` becomes true and by
setting the final fallback overlay fade time to `0`.

The cleaned fix has been copied into:

- `/Users/kalter/Documents/CODEX/kodirepo/skin.dutchtech.fuse.3`
- `/Users/kalter/Documents/CODEX/kodirepo/zips/skin.dutchtech.fuse.3`
- `/Users/kalter/Documents/CODEX/KodiEnglish/skin.dutchtech.fuse.3.kodienglish`
- `/Users/kalter/Documents/CODEX/KodiEnglish/zips/skin.dutchtech.fuse.3.kodienglish`

## Important Discoveries

- The affected Films/Series category widgets are generated as
  `Hub_Combined_Widget` / `Hub_Wall_Widget` using containers `501+`, not the
  simpler `Widget_Row` path.
- Row-level `<onfocus>` fires when entering the widget row, but not on every
  left/right item movement.
- AF3 already has a focused-layout hook,
  `List_Widget_Row_HiddenButton`, but the hub widget includes were not enabling
  it. Passing `hidden_button_enabled=true` and
  `hidden_button=List_Widget_Row_HiddenButton` into `Hub_Combined_Widget` and
  `Hub_Wall_Widget` made item-level next-page detection fire.
- The focused hook was clearing `NextPage.Widget` unconditionally before setting
  it again. On a next-page item this created bad timing. The clear now only runs
  for non-next-page items.
- The visible page marker and the visible chevron were coming from different
  layers. `Background_NextPage_PageMarker` was dynamic, but the fallback image
  include was created conditionally. For fresh widgets, Kodi could build the
  window while the condition was false, so the fallback image layer did not exist
  when focus later moved to the next-page item.
- The real fix for the persistent low chevron was to always instantiate the
  final fallback `Background_Image` layer in `Background_Main_Plain` and
  `Background_Main_Standard`, then toggle it with a dynamic `<visible>` param.

## Live Files Touched

- `1080i/Includes_Background.xml`
  - Added a `visible` param to `Background_Image`.
  - Always instantiates the final `fallback/next-page-background.png` image
    layer in plain and standard backgrounds, using
    `<visible>$EXP[Exp_NextPageBackground]</visible>`.
  - Latest flash patch adds a dynamic `visible` param to `Background_FlixArt`,
    dynamically hides flixart/blur layers while next-page background is active,
    and sets the final fallback overlay `fadetime` to `0`.
- `1080i/Includes_Hubs.xml`
  - Hub combined/wall widgets now enable `List_Widget_Row_HiddenButton`.
- `1080i/Includes_Lists.xml`
  - The `NextPage.Widget` clear action now only runs on non-next-page items.
- `1080i/Includes_Expressions.xml`
  - Contains the next-page detection expressions:
    `Exp_NextPageItem`, `Exp_FocusedContainer_NextPage`,
    `Exp_HomeWidget_NextPage`, `Exp_HomeWidget_NextPage_Active`, and
    `Exp_NextPageBackground`.
- `1080i/Includes_Images.xml`
  - Background/foreground variables were made next-page-aware earlier in the
    debugging pass.
- `extras/scripts/nextpage_debug.py`
  - Removed after the fix was confirmed. Historical traces used prefix
    `AF3-NEXTPAGE`.

## Log Evidence

Kodi debug log:

`/Users/kalter/Library/Logs/kodi.log`

Historical log pattern after the hub focused-layout hook was enabled:

```text
AF3-NEXTPAGE | source=List_Widget_Row_HiddenButton_Control | state=match | container=501 | tmdb=501 | nextprop=True | label=Next Page (2) >> | icon=https://i.imgur.com/D2wG9Ak.png | fanart=https://i.imgur.com/YpaXaLM.png | folder=plugin://plugin.video.fenlight.patched/?new_page=2...
```

After the conditional-clear patch, there should be no
`source=List_Widget_Row_HiddenButton_Control | state=clear` while focused on the
next-page item.

## Test Protocol

1. Reload or restart Kodi after each XML patch.
2. Go to a fresh Films/Series home widget category.
3. Move to the widget row and focus the next-page item.
4. Confirm the low Imgur chevron is covered by the cleaner fallback artwork.
5. Switch categories and repeat, because category switching was one of the
   original failure paths.
6. Watch for the remaining flash: a brief big low chevron before the fallback
   appears. The latest `Includes_Background.xml` patch is meant to address this.

## Cleanup / Porting Status

Diagnostic logging cleanup has already been done in the live skin:

- Removed `extras/scripts/nextpage_debug.py`.
- Removed temporary `RunScript(...nextpage_debug.py...)` hooks from:
  - `Includes_Hubs.xml`
  - `Includes_Widgets.xml`
  - `Includes_Lists.xml`

- These behavioral fixes were kept and ported:
  - hub widgets enabling `List_Widget_Row_HiddenButton`
  - next-page conditional clear in `List_Widget_Row_HiddenButton_OnFocus`
  - dynamic final fallback image layer in `Background_Main_Plain` /
    `Background_Main_Standard`
  - dynamic hide of stale flixart/blur layers
- Port validation completed:
  - `xmllint --noout` passes for touched XMLs in both repo forks and `zips/`.
  - `nextpage_debug`, `AF3-NEXTPAGE`, and temporary `source=...` params are not
    present in the ported skin XMLs.
  - Source skin folders and their matching `zips/` snapshots match for the
    touched XML files and `media/fallback/next-page-background.png`.

## 2026-06-14 Regression Note

After the user switched back to `skin.dutchtech.fuse.3`, the background/widget
parts of the next-page fix were present, but the small page marker variable was
missing from `Includes_Labels.xml`, and `Info_Panel` was still allowed to render
the large `Next Page (2) >>` title. The repo commit
`9670c00 Publish DutchTech Fuse 3 next-page background update` had not included
`Includes_Labels.xml` or `Includes_Info.xml`.

Fix reapplied:

- Added `Label_NextPageIndicator` to `Includes_Labels.xml`, mapping
  `Next Page (2)` through `Next Page (20)` to `Page 1` through `Page 19`.
- Added `!$EXP[Exp_NextPageBackground]` visibility to the root `Info_Panel`
  grouplist in `Includes_Info.xml`, so normal hero info is hidden while the
  dedicated next-page background is active.
- Applied the same two files to the live DutchTech skin, `kodirepo` source and
  zip snapshot, and KodiEnglish source and zip snapshot.

## 2026-06-14 Background Include Regression

Kodi debug logging showed repeated `Skin has invalid include:
Background_Blur_Quadrants` warnings after the next-page marker restore. The
cause was a `<param>` added to `Background_Blur_Quadrants` without wrapping the
include body in `<definition>`. Kodi rejected the include, which could prevent
normal movie/show blur artwork from drawing after next-page navigation.

Fix:

- Wrapped the `Background_Blur_Quadrants` group in `<definition>`.
- Applied live and repo copies.

## 2026-06-17 Films/Series Hub Stale Blur Edge Case

The last stubborn case was in the generated Films hub (`window 11102` in
`kodi.log`). The repro was:

1. Go to Films.
2. Move to the end of a widget row and focus the next-page tile.
3. Press Up to the hub category strip (`Trending`, `In Progress`, etc.).

Earlier patches hid the big `Next Page (2) >>` info title, but the large chevron
still remained in the upper background. That meant the chevron was no longer
being drawn by the dedicated `Exp_NextPageBackground` fallback layer. The
confirmed cause was stale TMDbHelper blur properties still pointing at the
plugin's next-page artwork while the normal background variables were active.

Working solution:

- Added `Exp_NextPageBlurImage` to detect stale next-page blur/current-blur
  properties on `Window.Property(TMDbHelper.ListItem.BlurImage*)` and
  `Window(Home).Property(TMDbHelper.ListItem.Current.BlurImage*)`.
- Added `Exp_NextPageBlurImage` blank values to `Image_Current_Background`,
  `Image_Background`, `Image_Background_Tiled`, and `Image_Foreground`.
- Kept `Exp_NextPageBackground` for the real focused next-page state, so the
  clean fallback art and small page marker still display on the actual tile.
- Narrowed generic `Exp_NextPageItem` and `Exp_FocusedContainer_NextPage` so
  path-only `page=` / `new_page=` values do not keep the fallback active after
  moving focus up to category controls.
- Marked hub selector focus as `TMDbHelper.WidgetContainer=601`, cleared
  `NextPage.Widget`, and hid hub info panel / generic fanart while selector or
  top controls are focused.

Ported files:

- `1080i/Includes_Expressions.xml`
- `1080i/Includes_Images.xml`
- `1080i/Includes_Hubs.xml`
- `1080i/Includes_Home.xml`

Repo release versions for this pass:

- `kodirepo/skin.dutchtech.fuse.3` -> `3.2.9.7`
- `KodiEnglish/skin.dutchtech.fuse.3.kodienglish` -> `3.2.9.1006`

## Tuner Note

The local tuner at `tools/next-page-marker-tuner.html` is useful only for rough
placement. Its coordinates did not match Kodi reality exactly, so Kodi visual
testing is the source of truth.
