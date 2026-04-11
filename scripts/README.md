# Main Repo Scripts

This directory contains the helper scripts that build and publish the main
DutchTech Kodi repository.

## `build_repo.py`

Use this when the repository addon or the repo-wide metadata needs a full
rebuild.

What it does:

- ensures the repository addon source exists
- bumps the repository addon version
- rebuilds every addon package under `zips/`
- regenerates `addons.xml` and `addons.xml.md5`
- updates the repository install zip in the repo root
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

## Important Future-Agent Nuance

If you already edited the unpacked source tree in place, the CLI entrypoint is
not always the right tool because it expects a root zip to import first.

For in-place source edits, the safe pattern is:

- use the helper functions from `publish_addon_update.py`
- regenerate the target addon output in `zips/<addon-id>/`
- rebuild `addons.xml` and `addons.xml.md5` if needed
- commit and push intentionally

That is the correct pattern for doc-only or source-tree-only edits.

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
