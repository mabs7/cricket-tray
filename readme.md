# 🏏 Cricket Tray — Live Desktop Score Widget

A lightweight desktop score widget for **Windows** and **macOS** that keeps **Pakistan**, **senior men's international cricket**, and **6 major T20/Hundred leagues** (**PSL, IPL, BPL, Big Bash League, SA20, and The Hundred**) right on your screen while you work — free, portable, and ready out of the box with no API key or sign-up required.

- **Windows:** A draggable, always-on-top floating score strip and system tray app.
- **macOS:** A live ticker directly in your top-right menu bar.

🌐 Website & interactive preview: **[mabs7.github.io/cricket-tray](https://mabs7.github.io/cricket-tray/)**

---

## Download & Install

| Platform | Download | Quick Setup |
|---|---|---|
| **Windows** (10 / 11) | [CricketTray-Windows.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/CricketTray-Windows.zip) | Unzip → double-click `CricketTray.exe` |
| **macOS** | [CricketTray-Mac.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/CricketTray-Mac.zip) | Unzip → open `CricketTray.app` |

> **First-run security prompt (unsigned app):**
> - **Windows SmartScreen:** Click **More info** → **Run anyway**.
> - **macOS Gatekeeper:** Open **System Settings → Privacy & Security** and allow `CricketTray.app` to open.

---

## What It Does

- **Always-visible score strip / menu bar:** Glance at live scores, overs, and match status without keeping browser tabs open.
- **Follow My Team or International:** Pick your team (**Pakistan + PSL**, **India + IPL**, **Australia + BBL**, **England + The Hundred**, **South Africa + SA20**, **Bangladesh + BPL**, or other Test nations) or switch to **International** for all senior international matches and 6 major leagues. Your selection stays saved automatically (and legacy `PAK Cricket` preferences migrate automatically).
- **Minimal Bar, Full Match Details On Demand:** Keep the floating score strip distraction-free, then open **Match Center** (or click **`More ▾`** / any match card on Windows, or open the dropdown/match submenu on macOS) for current batters (`runs`, `balls`, `4s`, `6s`, `SR`), active bowler (`O-M-R-W`, `Econ`), last wicket, run rates, partnership, and recent balls.
- **Match Center & Quick Strip Pinning:** Browse live, paused, upcoming, and recent matches, filter by competition, or pin any match to the bar (`Show on Live Strip` or `◀` / `▶` controls).
- **Accurate Break & Delay Labels:** Displays **STUMPS**, **LUNCH**, **TEA**, **DINNER**, **DRINKS**, **INNINGS BREAK**, **RAIN DELAY**, **WET OUTFIELD**, or **BAD LIGHT** instead of a misleading `LIVE` badge when play is paused, plus chronological Test innings and declared totals (e.g., `434/9d`).
- **Smart Refresh Schedule:** Polls every **45 seconds** during active play, **2 minutes** during mid-day breaks/delays, **5 minutes** overnight at Stumps or ahead of today's scheduled matches, and **30 minutes** when no fixtures are scheduled.
- **Resilient & Private:** If a refresh fails temporarily, the previous valid score stays visible along with how old it is. No accounts, no tracking, and zero analytics.
- **Built-in Update Notifications:** Checks automatically for new releases at launch and every 6 hours, with one-click in-app updates on Windows (verified and backed up before restarting).

---

## Windows Guide

1. Download [CricketTray-Windows.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/CricketTray-Windows.zip).
2. Extract it anywhere (e.g., Desktop or `C:\Apps\CricketTray\`). No installer or admin rights needed.
3. Double-click `CricketTray.exe` — the floating score bar appears in the top-right corner of your screen.

| Control | What it does |
|---|---|
| **Drag the bar (`⋮`)** | Move it anywhere on screen (position is remembered) |
| **`◀` / `▶` buttons** | Cycle through available matches directly from the bar |
| **`Matches` button / Double-click** | Open **Match Center** with competition filters and team selector |
| **Click a match card / `More ▾`** | Expand batters, active bowler, last wicket, run rates, and recent balls |
| **`Show on Live Strip`** | Pin any match from Match Center onto the floating bar |
| **Right-click the bar** | Refresh now, adjust text size, toggle Always on top, Hide, or Quit |
| **System tray icon** | Next/Previous Match, Show Match Center, Hide/Show Bar, Check for updates, Quit |
| **`↑ Update` button** | Download, verify, apply the latest Windows release, and restart |

### Optional: Start automatically with Windows
1. Right-click `CricketTray.exe` → **Create Shortcut**.
2. Press `Win + R`, type `shell:startup`, and press **Enter**.
3. Move the shortcut into the Startup folder.

---

## macOS Guide

1. Download [CricketTray-Mac.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/CricketTray-Mac.zip).
2. Unzip the archive and drag `CricketTray.app` to Applications (or run it directly).
3. Double-click `CricketTray.app` — live scores appear in the top-right menu bar.

| Control | What it does |
|---|---|
| **Menu bar ticker** | Shows the active match score, status, or break label |
| **Click the menu bar item** | View scores, inline batters/bowler/recent balls, upcoming matches, and refresh age |
| **Match submenus** | Expand any fixture for batters, bowlers, last wicket, recent overs, or pin to bar |
| **Feed menu** | Switch between **International & Leagues** and **My Team** |
| **Refresh now / Quit** | Fetch scores manually or exit the widget |

### Optional: Start automatically on macOS
Open **System Settings → General → Login Items** and add `CricketTray.app`.

---

## Troubleshooting

- **Floating bar disappeared on Windows?** Check the system tray (bottom-right) and click **Show Bar** (exclusive full-screen games or Windows lock screens can temporarily cover desktop overlays).
- **Scores look paused or delayed?** Check the refresh timestamp inside Match Center or the macOS menu. Temporary network or feed interruptions keep your last reliable score on screen until updates resume.
- **Blocked on first launch?** Because the app is free and unsigned, approve it once via Windows SmartScreen (**More info → Run anyway**) or macOS **System Settings → Privacy & Security**.

---

*Built for cricket fans — enjoy the match! 🏏*
