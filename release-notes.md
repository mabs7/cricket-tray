## PAK Cricket v2.9.0

### Expanded cricket coverage & team selector
- Follow **My Team** (Pakistan + PSL, India + IPL, Australia + BBL, England + The Hundred, South Africa + SA20, Bangladesh + BPL, or other Test nations) or switch to **International** mode for senior men's internationals and 6 major leagues (**PSL**, **IPL**, **BPL**, **Big Bash League**, **SA20**, **The Hundred**).
- Your feed mode, chosen team, and pinned strip match are saved in `settings.json` and can be changed anytime from Match Center or the macOS menu.

### Match Center & live strip selection
- View all matching fixtures in the scrollable Match Center with competition filter pills (`All`, team/league tabs, `International`) while pinning any single match to the floating strip (`Show on Live Strip` or `◀` / `▶` controls).
- Modernized Windows buttons, cards, borders, category pills, and scrollbars, plus responsive multi-monitor work-area clamping.

### Accurate break & Test innings states
- Show **STUMPS**, **LUNCH**, **TEA**, **DINNER**, **DRINKS**, **INNINGS BREAK**, **RAIN DELAY**, **WET OUTFIELD**, or **BAD LIGHT** instead of **LIVE** when play stops, while keeping active play phrases (such as `"resumes after lunch"`) as live.
- Poll every 45s during live play, 2 minutes during mid-day breaks/delays, and 5 minutes overnight at Stumps.
- Order Test innings chronologically and format declared totals with `d` (e.g., `PAK 434/9d`).

### Reliability & portable updater hardening
- Added `ETag` / `If-None-Match` release checks, bounded streaming Cricbuzz fetches, atomic settings saves, `PermissionError` retry on Windows update rollback, stale update-folder pruning, and reduced menu rebuild overhead on macOS.

### Downloads
- Windows: unzip `PakCricket-Windows.zip` and run `PakCricket.exe`.
- macOS: unzip `PakCricket-Mac.zip` and open `PakCricket.app`.

Portable Windows users on v2.8.0 can upgrade from inside the app after the release finishes building. The app remains unsigned, free, API-key-free, and telemetry-free; Cricbuzz format changes can still interrupt updates while retaining the last reliable score.
