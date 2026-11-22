# Main Repo Scripts

This directory contains the helper scripts that build and publish the main
DutchTech Kodi repository.

For the Kodi 21/22 catalog split, independent Piers skin source, version
ordering rule, and first Kodi 22 test findings, read `../KODI_22_HANDOVER.md`.

## `build_repo.py`

Use this when the repository addon or the repo-wide metadata needs a full
rebuild.

What it does:

- ensures the repository addon source exists
- bumps the repository addon version
- rebuilds every addon package under `zips/`
- regenerates `addons.xml` and `addons.xml.md5`
- updates the repository install zip in the repo root
- refreshes the tiny GitHub Pages install site under `docs/`
- commits and pushes to `main`

Use cases:

- repository artwork or metadata changed
- repo layout changed
- you want a clean full rebuild of everything

## `publish_addon_update.py`

Use this for addon updates when you do not want to bump the repository addon
version.

The command-line script expects the classic workflow:

1. put a packaged addon zip in the repo root
2. run the script

What it does:

- imports the root zip into the matching source directory
- rebuilds the matching `zips/<addon-id>/` output
- regenerates `addons.xml` and `addons.xml.md5`
- commits and pushes to `main`

## `build_piers.py`

Builds the Kodi 22-only catalog and ZIPs from independent source directories
under `piers/<addon-id>/`. The first such source is
`piers/skin.dutchtech.fuse.3/`. Edit that tree for Piers skin changes; editing
the root skin tree does not change Piers source or package contents.

When changing Piers source, bump both its `addon.xml` version and the matching
entry in `piers/releases.json`, then run `python3 scripts/build_piers.py` and
`python3 scripts/validate_repo_packages.py`. This script builds locally; it
does not commit or push. It refuses to overwrite a changed same-version ZIP.
The validator checks that every Piers package requires a Kodi 22 API version,
matches its source byte for byte, and is newer than any shared release of the
same addon ID. The Git release hook runs that validation before commit/push.

## Important Future-Agent Nuance

If you already edited the unpacked source tree in place, the CLI entrypoint is
not always the right tool because it expects a root zip to import first.

For in-place source edits, the safe pattern is:

- use the helper functions from `publish_addon_update.py`
- regenerate the target addon output in `zips/<addon-id>/`
- rebuild `addons.xml` and `addons.xml.md5` if needed
- commit and push intentionally

Before committing, run:

```bash
python3 scripts/validate_repo_packages.py
```

This checks that each shared source `addon.xml` version has a valid matching
archive under `zips/<addon-id>/`. It also checks Piers source, catalog, and
package consistency. Regenerate and inspect shared `addons.xml` after a source
version bump; the shared package check does not compare that catalog against
every source manifest. Both normal publish scripts run validation automatically.

Do not rebuild `addons.xml` from a source tree unless every addon whose source
version changed has also had its package output regenerated. The a4k 3.23.47
incident was caused by publishing global metadata that advertised a newer source
version while retaining the older ZIP.

That is the correct pattern for doc-only or source-tree-only edits.

## Main-Only Versioning

`DutchTechTestRepo` is retired from the normal workflow. Publish approved
Kodi-visible updates directly from this main repo, and make each affected addon
advertise a fresh version higher than the version already published here.

Also do not replace an already-published same-version package zip and call it an
update. Kodi decides repository updates from the advertised addon version in
`addon.xml` / `addons.xml`, and clients may cache same-version zips. For a real
Kodi-visible release, bump the addon source version first, regenerate
`zips/<addon-id>/<addon-id>-<new-version>.zip`, regenerate `addons.xml` and
`addons.xml.md5`, then commit and push that new version.

## Helpers Worth Knowing

From `publish_addon_update.py`:

- `update_addon_outputs(...)`
- `publish_changes(...)`

From `build_repo.py`:

- `get_source_dirs(...)`
- `mirror_addon_source(...)`
- `package_addon(...)`
- `build_addons_xml(...)`
- `write_md5(...)`

## Generated Files

Never hand-edit:

- `zips/`
- `addons.xml`
- `addons.xml.md5`

Treat them as derived outputs from the source trees plus the build helpers.

## GitHub Pages

GitHub Pages should be configured to serve `main` / `docs`, not the repository
root. The `docs/` folder only needs the bootstrap install page and
`repository.dutchtech-<version>.zip`; Kodi itself reads `addons.xml`,
`addons.xml.md5`, and `zips/` from the raw GitHub URLs in
`repository.dutchtech/addon.xml`.
