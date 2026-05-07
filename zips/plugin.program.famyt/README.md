# famYT

Kodi program add-on that installs family YouTube API credentials into the
official YouTube add-on.

The add-on does not contain credentials. It prompts for the shared family
password, calls the configured famYT Vercel bridge, and writes:

```text
special://profile/addon_data/plugin.video.youtube/api_keys.json
```

The bridge URL is configured in the add-on settings as `famYT bridge URL`.

After installation, each person opens the YouTube add-on and signs in with
their own Google account.
