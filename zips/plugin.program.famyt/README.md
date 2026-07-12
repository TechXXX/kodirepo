# Kodi Setup Kit

Private setup helper for a configured family Kodi environment.

This package contains no credentials. It is intended only for the private
family setup it was built for and is not useful without the matching private
access details.

Bundled profile presets include GUI settings, skin settings, Fen Light settings,
a4kSubtitles settings, keymaps, Kodi sources, and default favourites.

Menu items marked `[ALL]` are included when running Install everything.
Private Kodi webserver credentials are supplied by the bridge, not bundled in
the GUI preset.

Operational notes are kept outside the public repository.

## What It Does

Kodi Setup Kit installs a repeatable family profile setup:

- YouTube API key, OAuth client ID, and OAuth client secret from the private
  Vercel bridge
- TorBox API key and AIOStreams manifest URL for detected Fen Light variants
- Gemini API keys for Fen Light AI Search
- a4kSubtitles Patched preset plus OpenSubtitles and AI credentials
- Cocoscrapers undesirable filters
- Kodi `advancedsettings.xml` network settings
- Kodi webserver credentials from the private Vercel bridge
- bundled `sources.xml`, GUI settings, skin settings, Fen Light settings, and
  keymaps
- bundled `favourites.xml`, merged into the live profile without removing
  existing favourites
- maintenance utilities such as thumbnail cache cleanup and debug bundle export

## Install Everything Order

Menu items marked `[ALL]` are the curated setup flow:

1. Kodi sources
2. Fen Light settings preset
3. a4kSubtitles settings preset
4. YouTube credentials
5. TorBox API key and Manifest URL
6. a4kSubtitles credentials
7. Cocoscrapers filters
8. Kodi network/webserver settings
9. Kodi keymaps
10. Default favourites

Fen Light Gemini AI Search keys are available as a separate menu action.

The order matters. Fen Light settings can wipe TorBox values if restored after
TorBox, and the sanitized a4k preset can wipe a4k credentials if restored after
the credential step. `Install everything` already runs the safe order.

## Secrets

Secrets come from `famyt-vercel`, not this repository. Keep bundled presets
sanitized. The GUI preset may enable the webserver and authentication, but the
username/password must come from the bridge.

## Full Handover

Read the repository-level `KODI_SETUP_KIT_HANDOVER.md` for the detailed
architecture, Vercel contract, publishing flow, live-testing paths, and
troubleshooting notes.
