# DutchTech Kodi Repository

This repository is the main GitHub Pages distribution channel for DutchTech
Kodi packages.

For subtitle-selector migration work, this repo matters because it is the
production-facing package source for the patched Fenlight and patched a4k
addons.

## Addons In This Repo

Current source-tree roles when this document was updated:

- `plugin.video.fenlight`
  Baseline Fenlight package.
- `plugin.video.fenlight.patched`
  Main patched Fenlight build that bundles the selector locally and uses the
  centralized subtitle-aware retry-pool architecture.
- `service.subtitles.a4ksubtitles.patched`
  Main patched a4k build used with selector-aware Fenlight.
- `service.kodi.favourites.sync`
  Separate Google Drive favourites sync addon.
- `skin.arctic.horizon.2.1`
  Forked skin package shipped by this repo.
- `repository.dutchtech`
  The repository addon Kodi installs first.

## Layout

- `plugin.video.fenlight.patched/`
  Unpacked patched Fenlight source.
- `service.subtitles.a4ksubtitles.patched/`
  Unpacked patched a4k source.
- `plugin.video.fenlight/`
  Baseline Fenlight source kept for comparison or non-patched shipping.
- `service.kodi.favourites.sync/`
  Favourites sync service source.
- `skin.arctic.horizon.2.1/`
  Forked skin source.
- `scripts/`
  Repo build and publish helpers.
- `zips/`
  Generated installable addon packages. Do not hand-edit these.
- `addons.xml`
  Kodi metadata for every addon in the repo.
- `addons.xml.md5`
  Checksum for `addons.xml`.

## Docs To Read First

For selector or packaging work in this repo, read:

1. `README.md`
2. `scripts/README.md`
3. `plugin.video.fenlight.patched/resources/lib/modules/sources.md`
4. `plugin.video.fenlight.patched/resources/lib/modules/player.md`
5. `service.subtitles.a4ksubtitles.patched/README.md`
6. `skin.arctic.horizon.2.1/Readme.md`

## Selector-Relevant Addon Responsibilities

### `plugin.video.fenlight.patched`

This addon now owns:

- source scraping and filtering
- one-shot subtitle gather orchestration
- selector-backed retry-pool promotion
- playback resolution and player handoff

It should not own the detailed subtitle policy rules. Those belong in the
selector package and its vendored copy.

### `service.subtitles.a4ksubtitles.patched`

This addon now owns:

- subtitle provider queries
- OpenSubtitles translation-flag capture
- addon-side subtitle ordering and download handling
- manual-search UI badges like `[AI]` and `[MT]`
- built-in subtitle preference before external download

It should not own Fenlight playback logic.

### `skin.arctic.horizon.2.1`

This addon owns Kodi-side rendering, not subtitle policy.

That distinction matters because:

- addon-only text changes show everywhere
- extra badge or icon slots in dialogs require skin layout support

## Script Workflows

The scripts are documented in `scripts/README.md`.

Short version:

- use `scripts/build_repo.py` when the repository addon itself or the repo-wide
  metadata needs a full rebuild
- use `scripts/publish_addon_update.py` when publishing an addon update without
  bumping the repository addon version

Important future-agent nuance:

- the `publish_addon_update.py` command-line flow is built around the "drop a
  new addon zip in the repo root" workflow
- if you already edited the unpacked source tree in place, you may need to call
  that script's helper functions or regenerate `zips/<addon-id>/` manually
  instead of relying on the CLI import step

## Generated Output Rules

- treat `zips/` as generated output
- if addon-local docs change, regenerate the matching package mirror under
  `zips/`
- keep addon `addon.xml` files focused on Kodi metadata, not release-history
  storage
- do not turn addon `addon.xml` `<news>` blocks into multi-version changelogs;
  use dedicated changelog files such as `CHANGELOG.md` or addon-owned changelog
  text files instead
- if `addon.xml` changes, also regenerate `addons.xml`
- do not edit `addons.xml.md5` by hand

## Scope Guard Rails

- subtitle-selector migration work belongs primarily in:
  - `plugin.video.fenlight.patched`
  - `service.subtitles.a4ksubtitles.patched`
- baseline Fenlight is a reference point, not the main landing zone for new
  selector behavior
- unrelated addons and the skin should only be touched when the user-facing
  behavior truly depends on them
