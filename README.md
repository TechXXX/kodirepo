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
4. Install `zips/repository.fenlight/repository.fenlight-1.0.0.zip` in Kodi.

The checked-in files are configured for `https://TechXXX.github.io/kodirepo/`.
