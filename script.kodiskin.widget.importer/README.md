# KodiSkin Widget Importer

Kodi script add-on for importing Skin Shortcuts widget backups from a ZIP file, direct URL, network path, local path, or pCloud public link.

## What it imports

- `skin.*-*.DATA.xml` files from `userdata/addon_data/script.skinshortcuts`
- `skin.*.properties`
- optional `script-skinshortcuts-includes.xml` if the ZIP contains it and you confirm the extra copy

The add-on renames the source skin prefix to the currently active Kodi skin. For example:

```text
skin.arctic.horizon.2.patched-tvshows-1.DATA.xml
```

becomes:

```text
<current-active-skin>-tvshows-1.DATA.xml
```

It does not import the source `.hash` file. Instead it backs up and removes the local hash for the active skin so Skin Shortcuts rebuilds the generated include after you reload the skin or restart Kodi.

## Video add-on retargeting

Before import, the add-on scans widget paths for Fen-style video add-ons. If it finds one, it asks whether to keep the original add-on IDs or retarget those widget links to another video add-on.

Built-in choices include Fen, Fen Light, Fen Light Patched, Fen Light AI Search, and the KodiEnglish Fen Light forks. It does not list every installed video add-on, because these widget paths are Fen/Fen Light-specific and are not expected to work with unrelated video add-ons. You can also enter a custom Fen/Fen Light-style add-on ID such as `plugin.video.fenlight.yourfork`.

The retarget only changes the `plugin://plugin.video...` add-on ID. It leaves the rest of the widget URL untouched.

## Usage

1. Install the ZIP package for this add-on in Kodi.
2. Run **KodiSkin Widget Importer** from Program add-ons.
3. Paste a pCloud public link, direct ZIP URL, local ZIP path, or network ZIP path, or browse for a local ZIP.
4. Choose whether to keep or retarget detected video add-on widget paths.
5. Choose whether to overwrite matching local widget files or add onto them.
6. Confirm the source skin and target skin shown by the add-on.
7. Reload the skin or restart Kodi.

## Import modes

- **Overwrite matching local widget files** keeps the previous behavior: matching Skin Shortcuts DATA/properties files are replaced after a backup is made.
- **Add onto existing local widget files** merges structurally: imported shortcut XML entries are appended when they are not already present, and imported properties are added only when they do not conflict with an existing menu/id/property key.

Generated includes are not copied in add-on mode because they are compiled output. The local Skin Shortcuts hash is still removed so Kodi can rebuild the include from the merged data.

Backups of overwritten files are stored under:

```text
special://profile/addon_data/script.kodiskin.widget.importer/backups/
```
