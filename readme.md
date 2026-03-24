# 🏏 Pakistan Cricket Live Score Widget

A lightweight cross-platform menu bar / system tray widget that shows live Pakistan cricket scores — no API key, no cost, fully free.

---

## Download (No Python Required)

| Platform | Download |
|---|---|
| 🍎 macOS | [PakCricket.zip](../../releases/latest) — unzip and double-click `PakCricket.app` |
| 🪟 Windows | [PakCricket.Windows.zip](../../releases/latest) — unzip and double-click `PakCricket.app` |

---

## Features

- 🔴 **Live match** → red icon, refreshes every **60 seconds**
- 🟠 **Match scheduled today** → orange icon, refreshes every **5 minutes**
- ⚫ **No match** → grey icon, refreshes every **30 minutes**
- Click icon → popup with full match details
- Filters: **Pakistan international + PSL matches only**
- No API key needed — scrapes Cricbuzz directly
- Works on **macOS** (menu bar) and **Windows** (system tray)

---

## Run from Source (Developers)

### Requirements
- Python 3.11+
- pip

### macOS

```bash
git clone https://github.com/YOUR_USERNAME/cricket-tray.git
cd cricket-tray

python3 -m venv venv
source venv/bin/activate

pip install requests beautifulsoup4 lxml rumps
python3 main.py
```

The score appears in your **menu bar** (top right).

### Windows

```bash
git clone https://github.com/YOUR_USERNAME/cricket-tray.git
cd cricket-tray

python -m venv venv
venv\Scripts\activate

pip install requests beautifulsoup4 lxml pystray Pillow
python main.py
```

The score appears in your **system tray** (bottom right).

---

## Usage

| Action | Result |
|---|---|
| Look at menu bar / tray | See live score as text |
| Click the icon | Opens score popup |
| Click "Show Score" | Full match details |
| Click "Quit" | Closes the widget |

---

## Auto-start (optional)

**macOS:** System Settings → General → Login Items → add `PakCricket.app`

**Windows:** Press `Win + R` → type `shell:startup` → create a shortcut to `PakCricket.exe`

---

## Troubleshooting

- **No scores showing?** There may be no Pakistan match today — this is expected behaviour.
- **Scores look wrong?** Cricbuzz occasionally updates their HTML structure. Open an issue and it'll be fixed quickly.
- **Icon not appearing on Mac?** Make sure you allowed permissions in System Settings → Privacy & Security.
- **Scores delayed?** Normal — data is scraped from Cricbuzz, not a real-time API.

---

## Tech Stack

- `requests` + `BeautifulSoup` — scrapes Cricbuzz live scores
- `rumps` — macOS menu bar
- `pystray` + `Pillow` — Windows system tray
- `pyinstaller` — packaging

---

## Contributing

Pull requests welcome! If Cricbuzz updates their HTML and scores break, the fix is usually a one-line class name change in `scraper.py`.

---

*Built with ❤️ for Pakistan cricket fans*
