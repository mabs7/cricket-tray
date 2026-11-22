## Cricket Tray v3.0.1

### macOS Persistent Floating Score Bar & Display Mode Choice
- Added a native, draggable, non-activating **Floating Score Bar** (`MacFloatingBar`) on macOS that stays visible across app switches (e.g., Chrome, IDEs) and macOS Spaces without stealing focus, while keeping the menu bar item compact (`🏏`) so it stays clear of menu bar overflow and notches.
- Preserved the original **Menu Bar Ticker (Classic)** as an explicit user choice via `Display Mode` (saved locally in `CricketTray/settings.json` as `mac_display_mode`), letting you switch between **Floating Score Bar** and **Menu Bar Ticker (Classic)** anytime from the Scorecard Box, floating bar right-click menu, or menu bar dropdown.

### macOS Prominent Boxed Scorecard & High-Contrast Menu
- Clicking the floating bar (or choosing **Open Scorecard Box** in the menu bar dropdown) opens a high-contrast dark-slate **Boxed Scorecard** (`MacScorecardPanel`) featuring bold white team names, large emerald scores, semantic status pills (`LIVE`, `STUMPS`/break phases, `TODAY`, `COMPLETED`), aligned **BATTER** (`R`, `B`, `4s`, `6s`, `SR`) and **BOWLER** (`O`, `M`, `R`, `W`, `ECON`) tables, `CRR`/`RRR`/`P'ship`/`Target`, `Last wkt`, color-coded recent-ball chips, match selection, `Feed` selector, and `Open on Cricbuzz ↗`.
- Styled informational dropdown rows in the classic `rumps` menu bar menu with bright `NSAttributedString` text instead of dimmed disabled gray.

### Downloads & Upgrade Note
- **Windows:** Unzip `CricketTray-Windows.zip` and run `CricketTray.exe` (a temporary `PakCricket-Windows.zip` bridge asset remains included for Windows `v2.8.0` / `v2.9.1` upgraders).
- **macOS:** Unzip `CricketTray-Mac.zip` and open `CricketTray.app`.

The app remains unsigned, free, API-key-free, and telemetry-free; upstream feed format changes can still interrupt updates while retaining the last reliable score.
