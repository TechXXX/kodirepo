# DutchTech Kodi Repository

This directory is a static Kodi add-on repository for hosting DutchTech packages on GitHub Pages.

## Layout

- `plugin.video.fenlight/`: unpacked addon source extracted from the release zip
- `skin.arctic.horizon.2.1/`: unpacked skin source extracted from the release zip
- `repository.dutchtech/`: generated Kodi repository add-on source
- `zips/`: installable package archives for each addon id
- `addons.xml`: repository metadata consumed by Kodi
- `addons.xml.md5`: checksum for `addons.xml`
- `scripts/build_repo.py`: rebuilds packages and metadata

## Rebuild

Run:

```bash
python3 scripts/build_repo.py --base-url https://TechXXX.github.io/kodirepo/
```

You can also set `KODI_REPO_BASE_URL` instead of passing `--base-url`.
Kodi repository metadata defaults to `https://raw.githubusercontent.com/TechXXX/kodirepo/main/`.

## Publish

1. Push this directory to a GitHub repository.
2. Enable GitHub Pages for the repository.
3. Rebuild with your real GitHub Pages URL.
4. Download `repository.dutchtech-1.0.29.zip` from the site in a browser.
5. Install that local zip file in Kodi.

The checked-in install page is configured for `https://TechXXX.github.io/kodirepo/`.
The repository addon itself is configured to fetch metadata and zips from `https://raw.githubusercontent.com/TechXXX/kodirepo/main/`.

## Important note about GitHub Pages

GitHub Pages serves direct files but does not expose a browsable directory listing for `zips/`.
That means Kodi will not show hosted zip files when you browse a GitHub Pages source in `Install from zip file`.

Use this flow instead:

1. Download `repository.dutchtech-1.0.29.zip` directly from the site.
2. In Kodi, install that local zip file.
3. Then use `Install from repository` for `DutchTech`.
