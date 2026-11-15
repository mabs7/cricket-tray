# 🏏 PAK Cricket — Live Desktop Score Widget

A lightweight desktop score widget for **Windows** and **macOS** that keeps **Pakistan matches**, **senior men's international cricket**, and **6 major T20/Hundred leagues** (**PSL, IPL, BPL, Big Bash League, SA20, and The Hundred**) right on your screen while you work — free, portable, and ready out of the box with no API key or sign-up required.

- **Windows:** A draggable, always-on-top floating score strip and system tray app.
- **macOS:** A live ticker directly in your top-right menu bar.

🌐 Website & interactive preview: **[mabs7.github.io/cricket-tray](https://mabs7.github.io/cricket-tray/)**

---

## Download & Install

| Platform | Download | Quick Setup |
|---|---|---|
| **Windows** (10 / 11) | [PakCricket-Windows.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/PakCricket-Windows.zip) | Unzip → double-click `PakCricket.exe` |
| **macOS** | [PakCricket-Mac.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/PakCricket-Mac.zip) | Unzip → open `PakCricket.app` |

> **First-run security prompt (unsigned app):**
> - **Windows SmartScreen:** Click **More info** → **Run anyway**.
> - **macOS Gatekeeper:** Open **System Settings → Privacy & Security** and allow `PakCricket.app` to open.

---

## What It Does

- **Always-visible score strip / menu bar:** Glance at live scores, overs, and match status without keeping browser tabs open.
- **Follow My Team or International:** Pick your team (**Pakistan + PSL**, **India + IPL**, **Australia + BBL**, **England + The Hundred**, **South Africa + SA20**, **Bangladesh + BPL**, or other Test nations) or switch to **International** for all senior international matches and 6 major leagues. Your selection stays saved automatically.
- **Match Center & Quick Strip Pinning:** Open Match Center (Windows) or the menu bar dropdown (macOS) to browse live, paused, upcoming, and recent matches, filter by competition, or pin any match to the bar (`Show on Live Strip` or `◀` / `▶` buttons).
- **Accurate Break & Delay Labels:** Displays **STUMPS**, **LUNCH**, **TEA**, **DINNER**, **DRINKS**, **INNINGS BREAK**, **RAIN DELAY**, **WET OUTFIELD**, or **BAD LIGHT** instead of a misleading `LIVE` badge when play is paused, plus chronological Test innings and declared totals (e.g., `434/9d`).
- **Smart Refresh Schedule:** Polls every **45 seconds** during active play, **2 minutes** during mid-day breaks/delays, **5 minutes** overnight at Stumps or ahead of today's scheduled matches, and **30 minutes** when no fixtures are scheduled.
- **Resilient & Private:** If a refresh fails temporarily, the previous valid score stays visible along with how old it is. No accounts, no tracking, and zero analytics.
- **Built-in Update Notifications:** Checks automatically for new releases at launch and every 6 hours, with one-click in-app updates on Windows (verified and backed up before restarting).

---

## Windows Guide

1. Download [PakCricket-Windows.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/PakCricket-Windows.zip).
2. Extract it anywhere (e.g., Desktop or `C:\Apps\PakCricket\`). No installer or admin rights needed.
3. Double-click `PakCricket.exe` — the floating score bar appears in the top-right corner of your screen.

| Control | What it does |
|---|---|
| **Drag the bar** | Move it anywhere on screen (position is remembered) |
| **`◀` / `▶` buttons** | Cycle through available matches directly from the bar |
| **`Matches` button / Double-click** | Open **Match Center** with competition filters and team selector |
| **Right-click the bar** | Refresh now, adjust text size, toggle Always on top, Hide, or Quit |
| **`Show on Live Strip`** | Pin any match from Match Center onto the floating bar |
| **System tray icon** | Show Match Center, Hide/Show Bar, Check for updates, or Quit |
| **`Update available` button** | Download, verify, apply the latest Windows release, and restart |

### Optional: Start automatically with Windows
1. Right-click `PakCricket.exe` → **Create Shortcut**.
2. Press `Win + R`, type `shell:startup`, and press **Enter**.
3. Move the shortcut into the Startup folder.

---

## macOS Guide

1. Download [PakCricket-Mac.zip](https://github.com/mabs7/cricket-tray/releases/latest/download/PakCricket-Mac.zip).
2. Unzip the archive and drag `PakCricket.app` to Applications (or run it directly).
3. Double-click `PakCricket.app` — live scores appear in the top-right menu bar.

| Control | What it does |
|---|---|
| **Menu bar ticker** | Shows the active match score, status, or break label |
| **Click the menu bar item** | View full scores, upcoming matches, and refresh age |
| **Select a match** | Pin that match to the menu bar |
| **Feed switcher** | Toggle between **Pick a Team** and **International & Leagues** |
| **Refresh now / Quit** | Fetch scores manually or exit the widget |

### Optional: Start automatically on macOS
Open **System Settings → General → Login Items** and add `PakCricket.app`.

---

## Troubleshooting

- **Floating bar disappeared on Windows?** Check the system tray (bottom-right) and click **Show Bar** (exclusive full-screen games or Windows lock screens can temporarily cover desktop overlays).
- **Scores look paused or delayed?** Check the refresh timestamp inside Match Center or the macOS menu. Temporary network or feed interruptions keep your last reliable score on screen until updates resume.
- **Blocked on first launch?** Because the app is free and unsigned, approve it once via Windows SmartScreen (**More info → Run anyway**) or macOS **System Settings → Privacy & Security**.

---

*Built for cricket fans — enjoy the match! 🏏*
