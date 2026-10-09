## PAK Cricket v2.8.0

### Sticky Windows score bar
- Restore bar visibility and always-on-top state without stealing keyboard focus.
- Respect explicit Hide, Quit, and the Always on top preference.
- Keep refresh callbacks running after recoverable UI errors and record bounded local diagnostics.

### Portable updates
- Check GitHub at startup and every six hours, with a manual Check for updates action.
- Show an update button on the Windows bar and notify once per new version.
- Download and verify Windows releases after the user chooses Update, then replace and restart the app.
- Keep the previous executable and automatically restore it if the new app fails to initialize.
- Preserve preferences; offer another save location when the current folder cannot be written.
- macOS users receive update notifications and continue to install from the release page.

### Maintainer download report
- Run `python download_counts.py` to report GitHub release downloads by version and platform.
- Download counts are not unique users. No widget telemetry was added.

### Downloads
- Windows: unzip `PakCricket-Windows.zip` and run `PakCricket.exe`.
- macOS: unzip `PakCricket-Mac.zip` and open `PakCricket.app`.

Users of v2.7.0 and earlier must download this release manually once. Subsequent Windows releases can be installed inside the portable app. No installer is required.

The app is unsigned. Security screens and exclusive full-screen applications may cover the bar. Cricbuzz format changes can still interrupt score updates; the last successful scores are retained.
