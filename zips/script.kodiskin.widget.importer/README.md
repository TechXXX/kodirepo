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
supported Kodi devices. The optional path-retargeting feature is deliberately
limited to Fen/Fen Light-compatible add-ons: replacing only the add-on ID in an
unrelated add-on's URL would leave its different route parameters behind and
produce broken widgets.

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

- preloaded Dutch `settings.xml` for `skin.arctic.horizon.2.patched`
- preloaded English `settings.xml` for `skin.arctic.fuse.3`

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

The preloaded DutchTech AF3 setup imports the DutchTech shortcut nodes and also replaces the active skin's `settings.xml` with the bundled English AF3 settings after making backups. The on-screen label calls this out explicitly.

The preloaded AH2 Dutch setup import overwrites matching Skin Shortcuts files and also replaces the active skin's `settings.xml` with the bundled Dutch profile settings after making backups.

## Video add-on retargeting

Before import, the add-on scans shortcut paths for Fen-style video add-ons. If it finds one, it asks whether to keep the original add-on IDs or retarget those links to another video add-on.

Built-in choices include Fen, Fen Light, Fen Light Patched, Fen Light AI Search, and the KodiEnglish Fen Light forks. It does not list every installed video add-on, because these widget paths are Fen/Fen Light-specific and are not expected to work with unrelated video add-ons. You can also enter a custom Fen/Fen Light-style add-on ID such as `plugin.video.fenlight.yourfork`.

The retarget only changes the `plugin://plugin.video...` add-on ID. It leaves the rest of the shortcut URL untouched.

## Usage

1. Install the ZIP package for this add-on in Kodi.
2. Run **KodiSkin Widget Importer** from Program add-ons.
3. Choose **Preloaded DutchTech AF3 widgets + English settings** for the bundled DutchTech shortcut nodes together with the English AF3 settings, **Preloaded English AF3 widgets** for the bundled English AF3 shortcut nodes, **Import widgets from source** for URL/path/ZIP imports, or **Preloaded Dutch AH2 setup** for the bundled Dutch AH2 widget source and settings.
4. For widget sources, choose **Preloaded widgets**, paste a pCloud public link, pCloud short link, direct ZIP URL, local ZIP path, or network ZIP path, or browse for a local ZIP.
5. For widget sources, choose whether to keep or retarget detected video add-on paths.
6. For widget sources, choose whether to overwrite matching local shortcut files or add onto them.
7. For skin settings, choose the Dutch AH2 or English AF3 preset and confirm the active target skin.
8. Reload the skin or restart Kodi if the skin does not refresh immediately.

The built-in preloaded widget sources are:

```text
Preloaded Dutch AH2 widgets: https://e.pcloud.link/publink/show?code=8Vdy6alK
DutchTech AF3 widgets: bundled with the add-on
English AF3 widgets: bundled with the add-on
```

The built-in preloaded skin settings presets are:

```text
Dutch Arctic Horizon 2 settings
English Arctic Fuse 3 settings
```

## Import modes

- **Overwrite matching local widget files** replaces matching Skin Shortcuts DATA/properties files or AF3 Skin Variables shortcut JSON files after a backup is made.
- **Add onto existing local widget files** merges structurally: imported shortcut XML entries are appended when they are not already present, imported properties are added only when they do not conflict with an existing menu/id/property key, and AF3 shortcut JSON rows are appended when they are not already present.

Generated includes are not copied in add-on mode because they are compiled output. The local Skin Shortcuts hash is still removed, and AF3 Skin Variables rebuild is still triggered, so Kodi can rebuild from the merged data.

Backups of overwritten files are stored under:

```text
special://profile/addon_data/script.kodiskin.widget.importer/backups/
```
