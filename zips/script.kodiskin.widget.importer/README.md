# KodiSkin Widget Importer

Kodi script add-on for importing Skin Shortcuts and Arctic Fuse 3 widget backups from preloaded sources, ZIP file, direct URL, network path, local path, pCloud public link, or pCloud short link. It can also import bundled MacBook skin settings presets for AH2 and AF3.

## What it imports

For Skin Shortcuts skins:

- `skin.*-*.DATA.xml` files from `userdata/addon_data/script.skinshortcuts`
- `skin.*.properties`
- optional `script-skinshortcuts-includes.xml` if the ZIP contains it and you confirm the extra copy

For Arctic Fuse 3 / Skin Variables skins:

- `skinvariables-shortcut-*widgets.json` files from `userdata/addon_data/script.skinvariables/nodes/<skin-id>`
- widget defaults from an AF3 skin package `shortcuts/` folder
- bundled MacBook AF3 widget nodes

For skin settings:

- preloaded MacBook `settings.xml` for `skin.arctic.horizon.2.patched`
- preloaded MacBook `settings.xml` for `skin.arctic.fuse.3`

The add-on imports AF3 widget JSON into the active skin's Skin Variables node folder. This supports AF3 forks with their own add-on IDs, such as `skin.dutchtech.fuse.3` and `skin.dutchtech.fuse.3.kodienglish`.

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

Skin Shortcuts XML backups are not converted into Arctic Fuse 3 Skin Variables JSON. To import into AF3, use an AF3/Skin Variables widget backup.

Skin settings imports overwrite the active skin's `settings.xml` after making a backup. The preset can be imported into compatible forks because the add-on writes to the currently active skin id.

## Video add-on retargeting

Before import, the add-on scans widget paths for Fen-style video add-ons. If it finds one, it asks whether to keep the original add-on IDs or retarget those widget links to another video add-on.

Built-in choices include Fen, Fen Light, Fen Light Patched, Fen Light AI Search, and the KodiEnglish Fen Light forks. It does not list every installed video add-on, because these widget paths are Fen/Fen Light-specific and are not expected to work with unrelated video add-ons. You can also enter a custom Fen/Fen Light-style add-on ID such as `plugin.video.fenlight.yourfork`.

The retarget only changes the `plugin://plugin.video...` add-on ID. It leaves the rest of the widget URL untouched.

## Usage

1. Install the ZIP package for this add-on in Kodi.
2. Run **KodiSkin Widget Importer** from Program add-ons.
3. Choose **Import widgets** or **Import preloaded skin settings**.
4. For widgets, choose **Preloaded widgets**, paste a pCloud public link, pCloud short link, direct ZIP URL, local ZIP path, or network ZIP path, or browse for a local ZIP.
5. For widgets, choose whether to keep or retarget detected video add-on widget paths.
6. For widgets, choose whether to overwrite matching local widget files or add onto them.
7. For skin settings, choose the MacBook AH2 or AF3 preset and confirm the active target skin.
8. Reload the skin or restart Kodi if the skin does not refresh immediately.

The built-in preloaded widget sources are:

```text
DutchTech AH2 preloaded widgets: https://e.pcloud.link/publink/show?code=8Vdy6alK
MacBook Arctic Fuse 3 widgets: bundled with the add-on
```

The built-in preloaded skin settings presets are:

```text
MacBook Arctic Horizon 2 settings
MacBook Arctic Fuse 3 settings
```

## Import modes

- **Overwrite matching local widget files** replaces matching Skin Shortcuts DATA/properties files or AF3 Skin Variables widget JSON files after a backup is made.
- **Add onto existing local widget files** merges structurally: imported shortcut XML entries are appended when they are not already present, imported properties are added only when they do not conflict with an existing menu/id/property key, and AF3 widget JSON rows are appended when they are not already present.

Generated includes are not copied in add-on mode because they are compiled output. The local Skin Shortcuts hash is still removed, and AF3 Skin Variables rebuild is still triggered, so Kodi can rebuild from the merged data.

Backups of overwritten files are stored under:

```text
special://profile/addon_data/script.kodiskin.widget.importer/backups/
```
