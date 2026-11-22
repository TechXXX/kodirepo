# Kodi 21 and Kodi 22 release handover

Status checked on 2026-11-22. This records the DutchTech Omega/Piers work and
the first Kodi 22 RC2 test. Verify versions and upstream activity again before
a later release; the numbers below are a dated snapshot.

## The important distinction

This is one GitHub repository and one installed repository add-on, with two
catalogs. `repository.dutchtech` 1.0.51 has an unrestricted shared `<dir>` for
`addons.xml` and a second `<dir minversion="21.90.901">` for
`piers/zips/addons.xml`. Kodi 21 sees only the shared catalog. Kodi 22 RC2
(internal version 21.90.902) and later see both. This follows Kodi's documented
repository `<dir>` version filters; the Kodi 22 prerelease threshold is below
22.0.0 so RC builds are included.

The same addon ID can occur in both catalogs. Kodi does **not** give the Piers
catalog automatic priority: on Kodi 22 it selects the highest compatible
version. Thus shared skin 3.2.9.30 would beat Piers skin 3.2.9.27. The Piers
version must remain higher for an addon advertised in both catalogs.
`scripts/build_piers.py` checks this against both the shared source and the
shared catalog. `scripts/validate_repo_packages.py` and the Git commit/push
hook run the catalog check. Do not bypass a failed check by replacing an
already published ZIP at the same version.

The Piers skin ZIP itself requires `xbmc.gui` 5.18.0; the shared Omega skin
requires 5.17.0. Kodi 21 therefore cannot install the Piers ZIP even if it is
obtained outside the catalog. The Piers builder accepts Kodi 22-only API gates
(`xbmc.gui` 5.18.0 and `xbmc.python` 3.1.2). Verify the Python gate on the
specific Kodi 22 build before adding the first Piers Python addon.

## Source trees and published output

| Purpose | Path | Current version |
| --- | --- | --- |
| Shared/Omega Fuse 3 source | `skin.dutchtech.fuse.3/` | 3.2.9.26, `xbmc.gui` 5.17.0 |
| Piers Fuse 3 source | `piers/skin.dutchtech.fuse.3/` | 3.2.9.27, `xbmc.gui` 5.18.0 |
| Shared catalog and ZIPs | `addons.xml`, `addons.xml.md5`, `zips/` | 47 advertised addons |
| Piers release configuration | `piers/releases.json` | one addon: Fuse 3 |
| Piers catalog and ZIPs | `piers/zips/` | Fuse 3 3.2.9.27 |
| Installed repository add-on | `repository.dutchtech/` | 1.0.51 |

The Piers source tree was split **after** the first Piers feed went live. Before
commit `4e52d4b`, `piers/` held only release configuration and generated output;
its ZIP was built from the shared skin source with an XML override. The Piers
source now contains the exact files in that already published ZIP. The source
split did not change the ZIP bytes or trigger a Kodi update. At the split, the
two source trees differed only in `addon.xml`. Future Piers edits belong under
`piers/skin.dutchtech.fuse.3/`; shared skin edits do not copy over automatically.

The other add-ons remain shared, including Fen Light Patched 2.0.137, TMDb
Helper Patched 6.15.2.17, Skin Variables 2.3.12, and Texture Maker 0.2.11.
There is no Piers source or ZIP for them yet. A Kodi 22 client installs their
shared releases. Do not describe those addons as Kodi 22-only or claim they
have completed Kodi 22 playback testing.

## Publishing without crossing release tracks

For a Piers skin change:

1. Edit `piers/skin.dutchtech.fuse.3/`, not the shared skin source.
2. Bump the version in its `addon.xml` and in `piers/releases.json` together.
3. Keep the required `xbmc.gui` version at least 5.18.0.
4. Run `python3 scripts/build_piers.py` and
   `python3 scripts/validate_repo_packages.py`.
5. Inspect the Piers catalog and ZIP, then commit and push the intended files.

The Piers build refuses to overwrite a changed same-version ZIP. The validator
rebuilds a candidate ZIP from Piers source and compares it byte for byte with
the published package. A Piers-only update does not require a repository
add-on version bump because 1.0.51 already points to the Piers catalog.

For a shared addon change, follow `scripts/README.md`: bump the source version,
rebuild its `zips/<addon-id>/` package, regenerate shared `addons.xml` and its
checksum, then validate. The `publish_addon_update.py` CLI imports a new root
ZIP; it is not an in-place source editor. If the addon also has a Piers release,
check the version ordering before publishing. A shared source change does not
change Piers code, but a shared version that catches Piers still requires a
higher Piers release under the current overlapping-catalog design. The build
and release hook reject the out-of-order state.

For a new Piers addon, create an independent `piers/<addon-id>/` source tree,
give it the same ID as the shared addon, declare a suitable Kodi 22-only API
dependency in its `addon.xml`, and add its version and gate to
`piers/releases.json`. Run the Piers build and validator. Do not merely copy a
newer ZIP into `piers/zips/` or raise a version number without checking its
source and dependency manifest.

`scripts/build_repo.py` is the full repository rebuild and **automatically
commits and pushes**. It also bumps the repository add-on version and rebuilds
all shared ZIPs, so inspect its scope before using it. `scripts/build_piers.py`
only builds locally. GitHub Pages `docs/` is the small repository installer
page; Kodi fetches package metadata from the raw GitHub URLs in
`repository.dutchtech/addon.xml`. The repository's `.githooks` invoke
`scripts/release_safety_check.py`, which includes package feed validation.
The packaging file filter checks paths *inside* each add-on, so managed
worktrees under a hidden `.codex` directory build the same ZIPs as the main
checkout. A whole-path hidden-file check once produced an empty candidate ZIP
in such a worktree; the release validator caught it before publishing.

## Upstream reference: Jurial

Jurial's `repository.jurialmunkey` also has Omega and Piers **folders** on its
`master` branch, plus an overlapping Piers `<dir minversion="21.90.901">`.
His Fuse 3 skin source has separate `omega` and `piers` branches referenced by
repository submodules. As checked on 2026-11-22, the Omega catalog advertised
Fuse 3 3.5.7 (`xbmc.gui` 5.17.0) and the Piers catalog 3.5.8 (`xbmc.gui`
5.18.0). Omega was still being updated on 2026-11-21; Piers was updated on
2026-11-22. The Piers 3.5.8 commit changed only the version field, but followed
Piers-specific code changes. This is a release bump, not evidence that Omega
was abandoned. A much higher Piers version number would reduce ordering
collisions, but every changed Piers package still needs a new version.

Primary references:

- Kodi repository directory filters: https://kodi.wiki/view/Add-on_repositories
- Kodi latest-version selection: https://github.com/xbmc/xbmc/blob/master/xbmc/addons/AddonRepos.cpp
- Kodi API dependency behavior: https://kodi.wiki/view/Addon.xml
- Jurial repository manifest: https://github.com/jurialmunkey/repository.jurialmunkey/blob/master/repo/repository.jurialmunkey/addon.xml
- Jurial source branch mapping: https://github.com/jurialmunkey/repository.jurialmunkey/blob/master/.gitmodules

## First Kodi 22 test and open compatibility work

The initial Windows ARM64 portable test used Kodi `22.0-RC2 (21.90.902)` at
`C:\Kodi 22 First Try\portable_data\`. Its `kodi.old.log`
covered startup, initial setup and a clean shutdown; the next `kodi.log`
showed another successful startup. No Fen Light Python traceback or Kodi crash
was seen. This was **not** a playback test or a full compatibility pass.

Findings to revisit on the Piers source and on Kodi 21 where relevant:

- The test profile had Skin Variables 2.2.1, whereas this repo now ships
  2.3.12 (commit `873c384`). Update the test install before judging the newer
  helper's behavior. Texture Maker was 0.2.11, matching this repo.
- The skin references `Settings_InfoText` without defining the include.
  `Includes_Images.xml` uses `purle_blur.jpg`, while the actual file is
  `purple_blur.jpg`. Both issues are present in the shared and Piers skin
  sources after the split. They produced real skin warnings and a missing
  texture error. Fix both trees if the fix should reach both Kodi versions.
- Kodi repeatedly warned about missing `1080i/Timers.xml`. Neither source
  tree currently uses skin timers, so this looked nonfatal; confirm if timers
  are introduced later. Temporary missing Skin Variables widget includes
  appeared during initial generation but did not recur after rebuild.
- Fen Light's attempt to set Kodi `myvideos.selectaction` returned `false` on
  Kodi 22, although Fen's own Always Resume settings were set. Investigate
  before claiming resume behavior is correct.
- Kodi Setup Kit skipped a4kSubtitles credentials because a4kSubtitles Patched
  was absent in that test profile. It also logged `Invalid setting type`
  without identifying the setting. Other warnings included unsupported control
  type 7 and Python's deprecated `None`-as-string argument; their sources and
  user-visible effects still need investigation.

The Piers feed's first package was verified locally with
`python3 scripts/validate_repo_packages.py`. Checks also simulated Kodi 21.3
seeing only the shared catalog and Kodi 22 RC2 seeing both, confirmed the
Piers package requires `xbmc.gui` 5.18.0, confirmed repository installer and
catalog checksums, and verified the published Piers ZIP URL responded with
HTTP 200. Those packaging checks do not replace an on-device functional test.

## Release history for this work

- `873c384`: shared Skin Variables updated to 2.3.12.
- `2c3b110`: first Piers feed, Kodi 22-gated skin 3.2.9.27, repository add-on
  1.0.51.
- `e4e3a85`: reject a Piers version older than the shared catalog; simulated
  shared 3.2.9.30 against Piers 3.2.9.27 and confirmed the check failed.
- `4e52d4b`: created independent Piers skin source without changing the
  published Piers ZIP.
