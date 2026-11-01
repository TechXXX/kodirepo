# Kodi 20 Nexus Compatibility

`skin.dutchtech.fuse.3.nexus` is the Kodi 20 edition of DutchTech Fuse 3.

- Add-on ID: `skin.dutchtech.fuse.3.nexus`
- Kodi GUI API floor: `xbmc.gui` `5.16.0`
- Source baseline: DutchTech Fuse 3 `3.2.9.19`

The Kodi 21 Omega skin remains `skin.dutchtech.fuse.3` and requires
`xbmc.gui` `5.17.0`. Do not merge the two IDs or lower the Omega skin's API
requirement.

The separate ID is required because Skin Variables stores generated includes,
widget nodes, and per-user data under the skin ID. A shared ID would allow one
Kodi version to overwrite the other's generated state.

When porting a DutchTech skin change from the Omega source, verify the changed
Kodi labels, controls, and includes remain available in Kodi 20 before copying
it here. Rebuild this add-on's package and run:

```bash
python3 scripts/validate_repo_packages.py
```
