# Fen Light Kodi Repository

This directory is a static Kodi addon repository for hosting `plugin.video.fenlight` on GitHub Pages.

## Layout

- `plugin.video.fenlight/`: unpacked addon source extracted from the release zip
- `repository.fenlight/`: generated Kodi repository addon source
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

## Publish

1. Push this directory to a GitHub repository.
2. Enable GitHub Pages for the repository.
3. Rebuild with your real GitHub Pages URL.
4. Download `repository.fenlight-1.0.0.zip` from the site in a browser.
5. Install that local zip file in Kodi.

The checked-in files are configured for `https://TechXXX.github.io/kodirepo/`.

## Important note about GitHub Pages

GitHub Pages serves direct files but does not expose a browsable directory listing for `zips/`.
That means Kodi will not show hosted zip files when you browse a GitHub Pages source in `Install from zip file`.

Use this flow instead:

1. Download `repository.fenlight-1.0.0.zip` directly from the site.
2. In Kodi, install that local zip file.
3. Then use `Install from repository` for `Fen Light`.
