# Kodi testing workflow

For Kodi behavior changes and experiments in this repository, follow these steps in order.

1. **Edit live on the MacBook first.** Make the code changes directly in the installed addon in the MacBook's Kodi (`~/Library/Application Support/Kodi/addons/<addon-id>/`). Do not change the installed `addon.xml` version: it must stay at the version currently published in the repo. Restart Kodi when needed (for example, for service addons) so the edited code is loaded.
2. **The owner tests it.** The owner exercises the change in Kodi. Iterate on the live files until the owner says they are happy with the result. Static checks and package validation do not replace this test.
3. **Publish to the repo.** Only after the owner approves, copy the same changes into the repo source, bump the addon version there, regenerate the package and `addons.xml`, then commit and push.
4. **Do not update the MacBook in place.** After publishing, do not bump the installed `addon.xml`, copy the new files into Kodi's addons folder, or install the new zip by hand. The MacBook must get the new version from the repo, so the repository update path is tested.
5. **The owner checks the repo update and tests again.** The owner does this step personally: they check that Kodi on the MacBook updates to the new version from the repo, then test the change again. The agent's work ends after the push. Do not restart Kodi, trigger a repo refresh, or check the update unless the owner asks.

If a step cannot be completed, report that and hold the release.
