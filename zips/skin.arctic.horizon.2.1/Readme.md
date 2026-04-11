# Arctic Horizon 2.1 Maintainer Notes

This directory is the forked skin package shipped in the main DutchTech Kodi
repo.

Future agents usually do not need to touch it for selector work, but it becomes
important whenever a user asks for subtitle-dialog visuals or any other Kodi UI
change that cannot be delivered by addon text alone.

## Why This Skin Matters For Addon Work

Kodi addons supply data such as labels, thumbs, icons, and properties. The
skin decides what actually appears on screen.

That distinction matters for subtitle UI:

- addon-only text changes show on every skin
- extra icon or badge slots require skin layout support
- existing flag, `SYNC`, and `CC` visuals come from skin layout code, not from
  a4k drawing arbitrary artwork directly

## Important Files

- `addon.xml`
  Skin metadata and versioning.
- `1080i/DialogSubtitles.xml`
  The subtitle dialog window shell and list wiring.
- `1080i/Includes_Layouts.xml`
  Contains `Layout_DialogSubtitles`, which renders each subtitle row.
- `1080i/Font.xml`
  Font definitions that affect text rendering and badge readability.
- `1080i/Includes_Colors.xml`
  Shared color definitions used across dialogs.

## Subtitle Dialog Notes

Current subtitle-row rendering in `Layout_DialogSubtitles` uses:

- `ListItem.Thumb` for the language flag
- `ListItem.Label` for the language name
- `ListItem.Label2` for the subtitle title line
- `ListItem.ActualIcon` for the star-rating block
- `ListItem.Property(sync)` for the `SYNC` badge
- `ListItem.Property(hearing_imp)` for the `CC` badge

That is why a4k can add universal `[AI]` and `[MT]` text badges without skin
changes, but a true extra robot icon would need a new placeholder here.

## When To Edit This Skin

Edit this skin only when:

- the user explicitly wants a skin-specific visual improvement
- the default/shared Kodi field set is not enough
- a dialog layout bug is clearly caused by this skin

Prefer addon-only changes when the goal is cross-skin compatibility.

## Future-Agent Guard Rails

- Do not assume a4k can create new visual slots without skin work.
- If you add a skin-only affordance, document the addon-side data contract in
  the relevant addon README too.
- Keep upstream attribution and license notes intact.
- Re-test subtitle dialogs after layout changes because small spacing tweaks can
  affect list readability.

## Attribution

Original skin by Jurial Munkey.

This fork is maintained in the DutchTech repo as a packaged skin copy.

Icon images from iconmonstr.com. Classification icons are sourced from
wyrm65's classification icon pack. Language flags are sourced from im85288's
language flag icon pack.

License references:

- GPLv3:
  `https://github.com/DeFiNiek/skin.arctic.horizon.2/blob/main/LICENSE.txt`
- CC BY-NC-SA 4.0:
  `http://creativecommons.org/licenses/by-nc-sa/4.0/`
