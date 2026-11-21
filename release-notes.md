## Cricket Tray v3.0.0

### Rebrand from PAK Cricket to Cricket Tray
- Renamed the desktop app and release packages from **PAK Cricket** (`PakCricket.exe` / `PakCricket.app`) to **Cricket Tray** (`CricketTray.exe` / `CricketTray.app`), reflecting support for all 12 international teams and 6 major T20/Hundred leagues alongside Pakistan cricket.
- Preferences automatically migrate from `PakCricket/settings.json` to `CricketTray/settings.json` on first run.

### On-Demand Match Details (Batters, Bowler, Last Wicket & Recent Balls)
- Kept the floating strip (Windows) and menu bar ticker (macOS) minimal and score-focused at a glance.
- Added an expandable **`More ▾`** drawer in Windows **Match Center** (also toggled by clicking a match card) displaying batters at the crease (`runs`, `balls`, `4s`, `6s`, `SR`), active bowlers (`O-M-R-W`, `Econ`), last wicket, CRR/RRR, partnership, target, and color-coded recent balls.
- Added inline live batting, bowling, and recent ball rows for the active match plus expandable per-match submenus on macOS.

### Windows & macOS UI Polish
- **Windows:** Rounded DWM floating strip with drag grip (`⋮`), semantic status badge hierarchy (red LIVE, sky breaks, amber upcoming, green primary actions), deterministic control bar width, dark Match Center title bar on Windows 10/11, monitor-aware popup placement, smooth touchpad scrolling with auto-hiding scrollbar, 2-column compact team scoreboards, `Next`/`Previous Match` tray items, and sharper 4× supersampled tray/app icons.
- **macOS:** More compact menu bar formatting with grouped Test innings, top-positioned update prompt, consolidated `Feed` selector menu, and per-match action submenus.

### Downloads & Upgrade Note
- **Windows:** Unzip `CricketTray-Windows.zip` and run `CricketTray.exe`. Existing Windows `v2.8.0` / `v2.9.1` users can upgrade seamlessly from inside the app (a compatibility `PakCricket-Windows.zip` bridge asset is included in this release).
- **macOS:** Unzip `CricketTray-Mac.zip` and open `CricketTray.app` (macOS users upgrading from `v2.9.1` should install `CricketTray.app` from this release and remove the older `PakCricket.app`).

The app remains unsigned, free, API-key-free, and telemetry-free; upstream feed format changes can still interrupt updates while retaining the last reliable score.
