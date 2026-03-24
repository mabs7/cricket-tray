# 🏏 Pakistan Cricket Live Score Tray Widget

A lightweight Windows system tray widget that shows live Pakistan cricket scores — no API key required.

---

## Features
- 🔴 Live match → red icon, refreshes every **60 seconds**
- 🟠 Match scheduled today → orange icon, refreshes every **5 minutes**
- ⚫ No match → grey icon, refreshes every **30 minutes**
- Click icon → popup with full match details
- Filters: Pakistan international + PSL matches only

---

## Setup

### 1. Install Python
Download Python 3.11+ from https://python.org and install it.
Make sure to check **"Add Python to PATH"** during install.

### 2. Install dependencies
Open a terminal (CMD or PowerShell) in this folder and run:
```
pip install -r requirements.txt
```

### 3. Run the widget
```
python main.py
```
The cricket ball icon will appear in your system tray (bottom-right taskbar area).

---

## Usage
- **Hover** over the tray icon → see current score as tooltip
- **Left-click** or **right-click → Show Score** → opens score popup
- **Right-click → Quit** → closes the widget

---

## Auto-start with Windows (optional)
1. Press `Win + R`, type `shell:startup`, press Enter
2. Create a shortcut to `main.py` (or the `.exe`) in that folder

---

## Package as .exe (optional)
To share with others without Python installed:
```
pip install pyinstaller
pyinstaller --onefile --windowed --name PakCricket main.py
```
The `.exe` will be in the `dist/` folder.

---

## Troubleshooting
- **No scores showing?** Cricbuzz may have updated their HTML. Run `scraper.py` standalone to debug.
- **Icon not appearing?** Make sure `pystray` and `Pillow` installed correctly.
- **Scores delayed?** This is normal — data is scraped from Cricbuzz, not a real-time API.