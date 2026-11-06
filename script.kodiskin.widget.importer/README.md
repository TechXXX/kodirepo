# KodiSkin Widget Importer

Kodi script add-on for importing preloaded AF3/AH2 setups or custom Skin Shortcuts and Arctic Fuse 3 shortcut backups from ZIP file, direct URL, network path, local path, pCloud public link, or pCloud short link.

## Platform and device support

KodiSkin Widget Importer uses Kodi's own virtual file-system APIs, so the same
package and workflow work across Kodi platforms: Android and Android TV
(including NVIDIA Shield), CoreELEC/LibreELEC, Windows, macOS, and Linux.
The source can be a local file, network path, or URL that the device can read.

Compatibility is determined by the active skin's widget format, not by the
device:

- Skin Shortcuts XML backups import into Skin Shortcuts skins.
- Arctic Fuse 3 / Skin Variables JSON backups import into compatible AF3 / Skin
  Variables skins.
- The importer does not convert one widget format into the other.

Widget paths from video add-ons such as POV or Umbrella are retained exactly
when importing that add-on's own backup, so those backups are portable between
supported Kodi devices. The optional retargeting feature can change compatible
Fen-family widget paths to Fen, Fen Light, Red Light, or POV. Umbrella uses a
different route format, so the importer translates the stable, known
Fen/POV/Red Light routes into their Umbrella equivalents. A route with no safe
Umbrella equivalent is deliberately left pointing to its original add-on.

## What it imports

For Skin Shortcuts skins:

- `skin.*-*.DATA.xml` files from `userdata/addon_data/script.skinshortcuts`
- `skin.*.properties`
- optional `script-skinshortcuts-includes.xml` if the ZIP contains it and you confirm the extra copy

For Arctic Fuse 3 / Skin Variables skins:

- `skinvariables-shortcut-*.json` node files from `userdata/addon_data/script.skinvariables/nodes/<skin-id>`, including widgets, submenus, and powermenu files
- shortcut defaults from an AF3 skin package `shortcuts/` folder
- bundled DutchTech AF3 shortcut nodes
- bundled English AF3 shortcut nodes

For skin settings:

- a bundled `settings.xml` for `skin.arctic.horizon.2.patched`
- a bundled `settings.xml` for `skin.arctic.fuse.3`

The add-on imports AF3 shortcut JSON into the active skin's Skin Variables node folder. This supports AF3 forks with their own add-on IDs, such as `skin.dutchtech.fuse.3` and `skin.dutchtech.fuse.3.kodienglish`.

For Skin Shortcuts, the add-on renames the source skin prefix to the currently active Kodi skin. For example:

```text
skin.arctic.horizon.2.patched-tvshows-1.DATA.xml
```

becomes:

```text
<current-active-skin>-tvshows-1.DATA.xml
```

It does not import the source `.hash` file. Instead it backs up and removes the local hash for the active skin so Skin Shortcuts rebuilds the generated include after you reload the skin or restart Kodi.

For Arctic Fuse 3, generated Skin Variables include XML is not imported. The add-on writes the editable JSON nodes and then triggers a Skin Variables rebuild.

Skin Shortcuts XML backups are not converted into Arctic Fuse 3 Skin Variables JSON. To import into AF3, use an AF3/Skin Variables shortcut backup.

Skin settings imports overwrite the active skin's `settings.xml` after making a backup. When the target skin is active, the add-on also applies the imported settings through Kodi skin builtins so Kodi's in-memory settings do not overwrite the imported file on shutdown. The preset can be imported into compatible forks because the add-on writes to the currently active skin id.

Both preloaded AF3 setups import their respective shortcut nodes and also replace the active skin's `settings.xml` with the bundled AF3 settings file after making backups.

The preloaded Dutch AH2 setup import overwrites matching Skin Shortcuts files and also replaces the active skin's `settings.xml` with the bundled AH2 settings file after making backups.

## Video add-on retargeting

Before import, the add-on scans Fen-family paths, including POV and Red Light. If it finds one, it asks whether to keep the original add-on IDs or retarget those links to another video add-on.

Built-in choices include Fen, Fen Light, Fen Light Patched, Fen Light AI Search, the KodiEnglish Fen Light forks, **Red Light** (`plugin.video.redlight`), **POV** (`plugin.video.pov`), and **Umbrella** (`plugin.video.umbrella`). Red Light is a Fen Light fork and POV is Fen-derived, so their compatible routes can use the same ID-rewrite workflow. You can also enter a custom Fen/Fen Light-style add-on ID such as `plugin.video.fenlight.yourfork`.

For Fen, Fen Light, Red Light, and POV, retargeting changes only the `plugin://plugin.video...` add-on ID and preserves the rest of the shortcut URL. Choosing Umbrella activates a separate converter for the supported common routes: Trakt movie/TV trends, most watched, box office, common TMDb movie lists, watched/in-progress lists, searches, movie genres/years, and Trakt user lists. Other paths, such as AI search, provider menus, or a route with no exact Umbrella counterpart, remain on their original add-on rather than being converted incorrectly.

## Usage

1. Install the ZIP package for this add-on in Kodi.
2. Run **KodiSkin Widget Importer** from Program add-ons.
3. Choose **Preloaded Dutch AF3 Widgets + Settings file** or **Preloaded English AF3 Widgets + Settings file** for a complete AF3 preset. The preloaded Dutch AH2 preset follows those AF3 choices; **Import widgets from source** is kept separately for URL/path/ZIP imports.
4. For widget sources, choose **Preloaded widgets**, paste a pCloud public link, pCloud short link, direct ZIP URL, local ZIP path, or network ZIP path, or browse for a local ZIP.
5. For widget sources, choose whether to keep or retarget detected video add-on paths.
6. For widget sources, choose whether to overwrite matching local shortcut files or add onto them.
7. Each preloaded preset includes its matching bundled settings file; confirm the active target skin before it is replaced.
8. Choose **Export active widgets to ZIP** to create a portable backup of the active skin's widget files (skin settings are not included). Save it locally, to a Kodi network location such as `smb://`, or to another Kodi-supported virtual path; import it later using **Import widgets from source**.
9. Reload the skin or restart Kodi if the skin does not refresh immediately.

Public HTTP and pCloud links are download-only sources, so they cannot be used as
export destinations without an authenticated upload connection. A folder mounted
in Kodi, including a network share, can be used for both importing and exporting.

The built-in preloaded widget sources are:

```text
Preloaded Dutch AH2 widgets: https://e.pcloud.link/publink/show?code=8Vdy6alK
DutchTech AF3 widgets: bundled with the add-on
English AF3 widgets: bundled with the add-on
```

The built-in preloaded skin settings presets are:

```text
Arctic Horizon 2 settings file
Arctic Fuse 3 settings file
```

## Import modes

- **Overwrite matching local widget files** replaces matching Skin Shortcuts DATA/properties files or AF3 Skin Variables shortcut JSON files after a backup is made.
- **Add onto existing local widget files** merges structurally: imported shortcut XML entries are appended when they are not already present, imported properties are added only when they do not conflict with an existing menu/id/property key, and AF3 shortcut JSON rows are appended when they are not already present.

Generated includes are not copied in add-on mode because they are compiled output. The local Skin Shortcuts hash is still removed, and AF3 Skin Variables rebuild is still triggered, so Kodi can rebuild from the merged data.

Backups of overwritten files are stored under:

```text
special://profile/addon_data/script.kodiskin.widget.importer/backups/
```
