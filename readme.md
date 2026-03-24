# 🏏 Pakistan Cricket Live Score Widget

A lightweight cross-platform widget that shows live Pakistan cricket scores — no API key, no cost, fully free.

- **macOS** → score appears in the **menu bar** (top right)
- **Windows** → score appears in a **floating bar** (always on top, draggable)

---

## Download (No Python Required)

| Platform | Download |
|---|---|
| 🍎 macOS | [PakCricket.zip](../../releases/latest) — unzip and double-click `PakCricket.app` |
| 🪟 Windows | Coming soon |

---

## Features

- 🔴 **Live match** → red icon, refreshes every **60 seconds**
- 🟠 **Match scheduled today** → orange icon, refreshes every **5 minutes**
- ⚫ **No match** → grey icon, refreshes every **30 minutes**
- **Floating bar** (Windows) — always visible score bar, drag anywhere on screen
- **Menu bar** (macOS) — score shown as text in the top-right menu bar
- Click/double-click → full match detail popup
- Filters: **Pakistan international + PSL matches only**
- No API key needed — scrapes Cricbuzz directly
- Portable on Windows — no installation required

---

## Windows Usage

1. Download `PakCricket.Windows.zip` from [Releases](../../releases/latest)
2. Unzip it anywhere (Desktop, `C:\Apps\PakCricket\`, etc.)
3. Double-click `PakCricket.exe` to run
4. A floating score bar appears in the **top-right corner** of your screen

| Action | Result |
|---|---|
| Drag the bar | Move it anywhere on screen |
| Double-click the bar | Opens full score popup |
| Tray icon → Show Score | Opens full score popup |
| Tray icon → Hide/Show Bar | Toggle floating bar visibility |
| Tray icon → Quit | Closes the widget |

### Auto-start with Windows (optional)
1. Right-click `PakCricket.exe` → **Create Shortcut**
2. Press `Win + R` → type `shell:startup` → press Enter
3. Move the shortcut into that folder

---

## macOS Usage

1. Download `PakCricket.zip` from [Releases](../../releases/latest)
2. Unzip it
3. Double-click `PakCricket.app` to run
4. Score appears in your **menu bar** (top right)

| Action | Result |
|---|---|
| Look at menu bar | See live score as text |
| Click the icon | Opens score popup |
| Click "Show Score" | Full match details |
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

- **No scores showing?** There may be no Pakistan match today — this is expected behaviour.
- **Scores look wrong?** Cricbuzz occasionally updates their HTML. Open an issue and it'll be fixed quickly.
- **Floating bar not appearing?** Check your system tray (bottom-right) — use "Hide/Show Bar" to toggle it.
- **Mac permissions issue?** Go to System Settings → Privacy & Security and allow the app.
- **Scores delayed?** Normal — data is scraped from Cricbuzz, not a real-time API.

---

## Contributing

Pull requests welcome! If Cricbuzz updates their HTML and scores break, the fix is usually a one-line class name change in `scraper.py`.

---

*Built with ❤️ for Pakistan cricket fans*