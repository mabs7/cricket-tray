## PAK Cricket v2.7.0

### More resilient scores
- Read structured Cricbuzz match data first, with scoped HTML fallback.
- Validate scores and deduplicate matches using stable match IDs.
- Preserve the last successful scores during failed refreshes and show update age.
- Distinguish scheduled, live, completed, and unavailable scores.

### Desktop improvements
- Clearer Windows score bar and resizable, scrollable match details.
- Refresh now, open on Cricbuzz, and pin/unpin a match to the bar.
- Remember bar position, visibility, text size, and always-on-top preference.
- Show match details and refresh actions in the macOS menu.
- Start fetching in the background so the interface appears immediately.
- Compare release versions numerically.

### Downloads
- Windows: unzip `PakCricket-Windows.zip` and run `PakCricket.exe`.
- macOS: unzip `PakCricket-Mac.zip` and open `PakCricket.app`.

These builds are unsigned. Cricbuzz data formats can still change; failed refreshes retain the last successful score while retrying.
