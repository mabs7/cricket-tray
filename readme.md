# 🏏 Pakistan Cricket Live Score Widget

A lightweight cross-platform widget that shows live Pakistan cricket scores — no API key, no cost, fully free.

- **macOS** → score appears in the **menu bar** (top right)
- **Windows** → score appears in a **floating bar** (always on top, draggable)

---

## Download (No Python Required)

| Platform | Download | Instructions |
|---|---|---|
| 🍎 macOS | [PakCricket.zip](../../releases/latest) | Unzip → double-click `PakCricket.app` |
| 🪟 Windows | [PakCricket-Windows.zip](../../releases/latest) | Unzip → double-click `PakCricket.exe` |

---

## Features

- 🔴 **Live match** → red indicator, refreshes every **45 seconds**
- 🟠 **Match scheduled today** → orange icon, refreshes every **5 minutes**
- ⚫ **No match** → grey icon, refreshes every **30 minutes**
- **Floating bar** (Windows) — always visible score bar, drag anywhere on screen
- **Menu bar** (macOS) — score shown as text in the top-right menu bar
- Details button/double-click → resizable, scrollable match detail popup
- Pin any relevant match to the bar; open its Cricbuzz page or refresh manually
- Saved bar position, visibility, font size, and always-on-top preference
- Windows bar restores its visibility and always-on-top state without taking keyboard focus; explicit Hide and Quit are respected
- Automatic update checks at startup and every six hours, with a visible update button and one notification per version
- Portable Windows updates download, verify, replace, and restart the app after you click Update; settings and the previous executable are preserved
- Failed updates keep the last successful scores and display their age
- Filters: **Pakistan international + PSL matches only**
- No API key needed — reads Cricbuzz's embedded match data with scoped HTML fallback
- Portable on Windows — no installation required

---

## Windows Usage

1. Download `PakCricket-Windows.zip` from [Releases](../../releases/latest)
2. Unzip it anywhere (Desktop, `C:\Apps\PakCricket\`, etc.)
3. Double-click `PakCricket.exe` to run
4. A floating score bar appears in the **top-right corner** of your screen

| Action | Result |
|---|---|
| Drag the bar | Move it anywhere on screen |
| Double-click the bar | Opens full score popup |
| Details button or Enter | Opens full score popup |
| Right-click the bar | Refresh, open source, text size, always-on-top, hide, and quit |
| Pin to bar in details | Select the match shown on the floating bar |
| Escape in details | Closes the popup |
| Update available button | Downloads and verifies the new Windows version, then restarts after confirmation |
| Tray → Check for updates | Checks for a release immediately |
| Tray icon → Show Score | Opens full score popup |
| Tray icon → Hide/Show Bar | Toggle floating bar visibility |
| Tray icon → Quit | Closes the widget |

### Auto-start with Windows (optional)
1. Right-click `PakCricket.exe` → **Create Shortcut**
2. Press `Win + R` → type `shell:startup` → press Enter
3. Move the shortcut into that folder

### Portable updates
The app remains portable; no installer or administrator access is needed in a writable folder. Install the first version supporting in-app updates manually. Future Windows updates can be applied from the score bar or tray menu. The app verifies the release ZIP against GitHub's SHA-256 digest, retains a `PakCricket.previous-*.exe` backup, and restores it if the new app fails to start. If the current folder is not writable, choose another folder for the updated executable. macOS and source runs continue to open the release page for installation.

The bar watchdog respects Hide and the Always on top preference. Windows security screens and exclusive full-screen applications can still cover the bar. Local diagnostics are kept in `%APPDATA%/PakCricket/app.log` if needed to investigate a disappearance.

---

## macOS Usage

1. Download `PakCricket.zip` from [Releases](../../releases/latest)
2. Unzip it
3. Double-click `PakCricket.app` to run
4. Score appears in your **menu bar** (top right)

| Action | Result |
|---|---|
| Look at menu bar | See live score as text |
| Click the icon | Opens match details in the dropdown |
| Select a match | Changes the score shown in the menu bar |
| Click "Refresh now" | Fetches scores immediately |
| Click "Open on Cricbuzz" | Opens the selected match's source page |
| Click "Quit" | Closes the widget |

### Auto-start with macOS (optional)
System Settings → General → Login Items → add `PakCricket.app`

---

## Run from Source (Developers)

### Requirements
- Python 3.11+

### macOS

```bash
git clone https://github.com/mabs7/cricket-tray.git
cd cricket-tray

python3 -m venv venv
source venv/bin/activate

pip install requests beautifulsoup4 lxml rumps
python3 main.py
```

### Windows

```bash
git clone https://github.com/mabs7/cricket-tray.git
cd cricket-tray

python -m venv venv
venv\Scripts\activate        # CMD
source venv/Scripts/activate # Git Bash / VS Code terminal

pip install requests beautifulsoup4 lxml pystray Pillow
python main.py
```

---

## Build from Source

### macOS → .app
```bash
pip install pyinstaller
python3 create_icon.py
pyinstaller --onefile --windowed --icon=icon.icns --name PakCricket main.py
cd dist && zip -r PakCricket.zip PakCricket.app
```

### Windows → .exe
```bash
pip install pyinstaller
python create_icon.py
pyinstaller --onefile --windowed --icon=icon.ico --name PakCricket main.py
cd dist
powershell Compress-Archive PakCricket.exe PakCricket-Windows.zip
```

---

## Tech Stack

| Component | Library |
|---|---|
| Scraping | `requests` + `BeautifulSoup` |
| macOS menu bar | `rumps` |
| Windows tray + floating bar | `pystray` + `tkinter` + `Pillow` |
| Packaging | `pyinstaller` |

---

## Troubleshooting

- **No scores showing?** Check the refresh status. No fixtures and failed updates are shown separately.
- **Updates delayed?** The last successful scores remain visible while the app retries every minute. Cricbuzz may be unavailable or its data format may have changed.
- **Floating bar not appearing?** Check your system tray (bottom-right) — use "Hide/Show Bar" to toggle it.
- **Mac permissions issue?** Go to System Settings → Privacy & Security and allow the app.
- **Scores delayed?** Normal — data is scraped from Cricbuzz, not a real-time API.

---

## Contributing

Pull requests welcome! The parser first decodes embedded JSON and Next.js flight chunks, then falls back to HTML scoped to individual match IDs. JSON-LD supplies fixture dates when available. It validates wickets and overs and reports unrecognized pages as refresh failures.

Run the offline regression suite with `python -m unittest discover -s tests -v`. Run `python test_scraper.py` for a live network diagnostic. On Windows, `python tests/ui_smoke.py` checks temporary Tk windows and controls without starting the tray or fetching scores. After building, `python tests/packaged_update_smoke.py` verifies replacement and restart using disposable executable copies; it briefly starts a test score bar.

Maintainers can run `python download_counts.py` to see GitHub release download counts by platform and version. This is not a unique-user count. The widget has no analytics or anonymous usage-reporting endpoint.

Upcoming, live, and recent pages are fetched concurrently. A failed refresh preserves the previous complete snapshot; cached scores are kept in memory only. Preferences are stored in `%APPDATA%/PakCricket/settings.json` on Windows. Page formats can still change; fallback parsing is best effort and does not bypass access restrictions.

---

*Built with ❤️ for Pakistan cricket fans. Good luck PAKISTAN! 🏏*
