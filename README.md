# DutchTech Kodi Repository

This directory is a static Kodi add-on repository for hosting DutchTech packages on GitHub Pages.

## Add-ons in this repo

- `plugin.video.fenlight` (`Fen Light`) - version `2.0.07`
- `service.kodi.favourites.sync` (`Kodi Favourites Sync`) - version `0.2.34`
- `skin.arctic.horizon.2.1` (`Arctic Horizon 2.1`) - version `0.0.1`
- `repository.dutchtech` (`DutchTech Repository`) - version `1.0.38`

## Layout

- `plugin.video.fenlight/`: unpacked addon source extracted from the release zip
- `service.kodi.favourites.sync/`: unpacked service source extracted from the release zip
- `skin.arctic.horizon.2.1/`: unpacked skin source extracted from the release zip
- `repository.dutchtech/`: generated Kodi repository add-on source
- `zips/`: installable package archives for each addon id
- `addons.xml`: repository metadata consumed by Kodi
- `addons.xml.md5`: checksum for `addons.xml`
- `scripts/build_repo.py`: full repo publish, including repository version bump
- `scripts/publish_addon_update.py`: minimal addon update publish without repo version bump

## Publish workflows

### Full repo publish

```bash
python3 scripts/build_repo.py --base-url https://TechXXX.github.io/kodirepo/
```

Use this when you change the repository itself, for example:

- repository metadata or structure
- repository artwork
- repository install flow

This script:

- rebuilds packages and metadata for the whole repo
- bumps `repository.dutchtech`
- commits and pushes to `main`

You can also set `KODI_REPO_BASE_URL` instead of passing `--base-url`. Kodi repository metadata defaults to `https://raw.githubusercontent.com/TechXXX/kodirepo/main/`.

### Add-on update publish

Drop a new addon zip in the repo root and run:

```bash
python3 scripts/publish_addon_update.py
```

Use this when you only have a new version of an add-on, service, or skin and do not want to bump `repository.dutchtech`.

This script:

- imports the new addon zip from the repo root
- replaces the matching unpacked addon source directory
- rebuilds only that addon package under `zips/<addon-id>/`
- regenerates `addons.xml` and `addons.xml.md5`
- commits and pushes to `main`

## Publish

1. Push this directory to a GitHub repository.
2. Enable GitHub Pages for the repository.
3. Rebuild with your real GitHub Pages URL.
4. Download the current `repository.dutchtech-<version>.zip` from the site in a browser.
5. Install that local zip file in Kodi.

The checked-in install page is configured for `https://TechXXX.github.io/kodirepo/`.
The repository addon itself is configured to fetch metadata and zips from `https://raw.githubusercontent.com/TechXXX/kodirepo/main/`.

## Important note about GitHub Pages

GitHub Pages serves direct files but does not expose a browsable directory listing for `zips/`.
That means Kodi will not show hosted zip files when you browse a GitHub Pages source in `Install from zip file`.

Use this flow instead:

1. Download the current `repository.dutchtech-<version>.zip` directly from the site.
2. In Kodi, install that local zip file.
3. Then use `Install from repository` for `DutchTech`.
