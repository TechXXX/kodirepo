# famYT

Kodi program add-on that installs family setup values into Kodi.

The add-on does not contain credentials. It prompts for the shared family
password, calls the configured famYT Vercel bridge, and offers menu actions to:

- install YouTube API credentials
- install a TorBox API key for Fen Light
- install OpenSubtitles and AI translation settings for a4kSubtitles Patched
- install Cocoscrapers undesirable filters
- install everything at once

The YouTube action writes:

```text
special://profile/addon_data/plugin.video.youtube/api_keys.json
```

The TorBox action writes Fen Light's `tb.token` and `tb.enabled` settings into
Fen Light's settings database for the current Kodi profile.

The a4kSubtitles action writes:

```text
opensubtitles.username
opensubtitles.password
opensubtitles.enabled
general.ai_api_key
general.use_ai
general.ai_provider
general.ai_model
```

The Cocoscrapers action enables `filter.undesirables`, seeds the undesirable
keyword database, and adds the family extra filters:

```text
.hc.
.hin.
.hindi.
.ita.
.rus.
.ukr.
```

The bridge URL is configured in the add-on settings as `famYT bridge URL`.

After installation, each person opens the YouTube add-on and signs in with
their own Google account.
