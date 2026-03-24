"""
main.py
Entry point for the Pakistan Cricket Live Score Tray Widget.
Cross-platform: uses rumps on macOS, pystray on Windows.

Smart refresh intervals:
  - Live match    → every 60 seconds
  - Match today   → every 5 minutes (300s)
  - No match      → every 30 minutes (1800s)
"""

import sys
import threading
import time

from scraper import get_all_matches
from filter import get_match_state, get_display_text

# ── Refresh intervals ──────────────────────────────────────────────────────────
INTERVAL_LIVE  = 60
INTERVAL_TODAY = 300
INTERVAL_NONE  = 1800

# ── Shared state ───────────────────────────────────────────────────────────────
current_matches = []
current_state   = "none"
current_text    = "🏏 Fetching..."


def fetch_scores():
    """Fetch latest scores and update globals. Returns interval for next fetch."""
    global current_matches, current_state, current_text

    all_data = get_all_matches()
    state, matches = get_match_state(all_data)

    current_state   = state
    current_matches = matches

    if matches:
        current_text = get_display_text(matches[0])
        if len(matches) > 1:
            current_text += f"  (+{len(matches)-1} more)"
    else:
        current_text = "🏏 No PAK match"

    intervals = {"live": INTERVAL_LIVE, "today": INTERVAL_TODAY, "none": INTERVAL_NONE}
    return intervals[state]


# ══════════════════════════════════════════════════════════════════════════════
#  macOS — rumps
# ══════════════════════════════════════════════════════════════════════════════
if sys.platform == "darwin":
    import rumps

    class CricketApp(rumps.App):
        def __init__(self):
            super().__init__(
                name="PAK Cricket",
                title="🏏",
                quit_button="Quit",
            )
            self.menu = ["Show Score", None]
            self._start_refresh_thread()

        def _start_refresh_thread(self):
            def _run():
                while True:
                    interval = fetch_scores()
                    self._update_ui()
                    time.sleep(interval)
            threading.Thread(target=_run, daemon=True).start()

        def _update_ui(self):
            state_emoji = {"live": "🔴", "today": "🟠", "none": "⚫"}
            emoji = state_emoji.get(current_state, "🏏")
            self.title = f"{emoji} {current_text}"

        @rumps.clicked("Show Score")
        def show_score(self, sender):
            if not current_matches:
                rumps.alert(
                    title="PAK Cricket",
                    message="No Pakistan match right now.",
                    ok="Close",
                )
                return

            lines = []
            for match in current_matches:
                lines.append(match.get("teams", ""))
                if match.get("score"):
                    lines.append(match["score"])
                if match.get("status"):
                    lines.append(match["status"])
                lines.append("─" * 30)

            rumps.alert(
                title="🏏 Pakistan Cricket",
                message="\n".join(lines),
                ok="Close",
            )

    def main():
        CricketApp().run()


# ══════════════════════════════════════════════════════════════════════════════
#  Windows — pystray + tkinter floating bar
# ══════════════════════════════════════════════════════════════════════════════
else:
    import tkinter as tk
    import pystray
    from PIL import Image, ImageDraw

    tray_icon  = None
    float_bar  = None   # the always-on-top floating window
    bar_label  = None   # label inside the bar
    bar_hidden = False  # toggle visibility

    # ── Icon drawing ──────────────────────────────────────────────────────────
    def create_icon_image(color="#00A550"):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 30, 30], fill=color, outline="white", width=2)
        draw.arc([6, 6, 26, 26], start=30,  end=150, fill="white", width=2)
        draw.arc([6, 6, 26, 26], start=210, end=330, fill="white", width=2)
        return img

    def get_icon_color(state):
        return {"live": "#CC0000", "today": "#FFA500", "none": "#555555"}.get(state, "#555555")

    def get_bar_color(state):
        return {"live": "#8B0000", "today": "#7A4000", "none": "#1a1a2e"}.get(state, "#1a1a2e")

    # ── Floating bar ──────────────────────────────────────────────────────────
    def create_floating_bar():
        global float_bar, bar_label

        float_bar = tk.Tk()
        float_bar.overrideredirect(True)          # no title bar / borders
        float_bar.attributes("-topmost", True)    # always on top
        float_bar.attributes("-alpha", 0.92)      # slight transparency
        float_bar.configure(bg="#1a1a2e")

        # Position: top-right corner
        sw = float_bar.winfo_screenwidth()
        float_bar.geometry(f"340x32+{sw - 350}+10")

        # Score label
        bar_label = tk.Label(
            float_bar,
            text="🏏 Fetching...",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg="#1a1a2e",
            padx=10,
            pady=4,
            anchor="w",
        )
        bar_label.pack(fill="both", expand=True)

        # Drag to move
        float_bar.bind("<ButtonPress-1>",   _drag_start)
        float_bar.bind("<B1-Motion>",       _drag_move)
        bar_label.bind("<ButtonPress-1>",   _drag_start)
        bar_label.bind("<B1-Motion>",       _drag_move)

        # Double-click to show detail popup
        bar_label.bind("<Double-Button-1>", lambda e: show_detail_popup())
        float_bar.bind("<Double-Button-1>", lambda e: show_detail_popup())

        return float_bar

    # Drag helpers
    _drag_x = _drag_y = 0
    def _drag_start(event):
        global _drag_x, _drag_y
        _drag_x, _drag_y = event.x, event.y

    def _drag_move(event):
        x = float_bar.winfo_x() + event.x - _drag_x
        y = float_bar.winfo_y() + event.y - _drag_y
        float_bar.geometry(f"+{x}+{y}")

    def update_bar():
        """Refresh the floating bar text and colour. Called from main thread."""
        if bar_label and float_bar:
            bar_label.config(text=current_text, bg=get_bar_color(current_state))
            float_bar.configure(bg=get_bar_color(current_state))
        float_bar.after(2000, update_bar)   # re-check every 2s

    # ── Detail popup ──────────────────────────────────────────────────────────
    def show_detail_popup():
        popup = tk.Toplevel(float_bar)
        popup.title("PAK Cricket")
        popup.geometry("420x320")
        popup.configure(bg="#1a1a2e")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        tk.Label(popup, text="🏏 Pakistan Cricket", font=("Segoe UI", 14, "bold"),
                 fg="#00A550", bg="#1a1a2e", pady=10).pack(fill="x")
        tk.Frame(popup, bg="#00A550", height=2).pack(fill="x", padx=10)

        frame = tk.Frame(popup, bg="#1a1a2e")
        frame.pack(fill="both", expand=True, padx=15, pady=10)

        if not current_matches:
            tk.Label(frame, text="No Pakistan match right now.",
                     font=("Segoe UI", 11), fg="#aaaaaa", bg="#1a1a2e").pack(pady=20)
        else:
            for match in current_matches:
                card = tk.Frame(frame, bg="#16213e")
                card.pack(fill="x", pady=5, ipady=8, ipadx=8)
                tk.Label(card, text=match.get("teams", ""), font=("Segoe UI", 12, "bold"),
                         fg="#ffffff", bg="#16213e", anchor="w").pack(fill="x", padx=8)
                if match.get("score"):
                    tk.Label(card, text=match["score"], font=("Segoe UI", 11),
                             fg="#FFD700", bg="#16213e", anchor="w").pack(fill="x", padx=8)
                if match.get("status"):
                    clr = "#CC0000" if match.get("is_live") else "#aaaaaa"
                    tk.Label(card, text=match["status"], font=("Segoe UI", 10),
                             fg=clr, bg="#16213e", anchor="w").pack(fill="x", padx=8)

        state_map = {"live": "🔴 LIVE", "today": "🟠 Scheduled", "none": "⚫ No live match"}
        tk.Label(popup, text=state_map.get(current_state, ""), font=("Segoe UI", 9),
                 fg="#888888", bg="#1a1a2e", pady=6).pack()
        tk.Button(popup, text="Close", command=popup.destroy, bg="#00A550",
                  fg="white", font=("Segoe UI", 10), relief="flat", padx=20).pack(pady=(0, 10))

    # ── Tray menu actions ─────────────────────────────────────────────────────
    def toggle_bar(icon, item):
        global bar_hidden
        bar_hidden = not bar_hidden
        if bar_hidden:
            float_bar.withdraw()
        else:
            float_bar.deiconify()

    def show_popup_from_tray(icon, item):
        float_bar.after(0, show_detail_popup)

    def quit_app(icon, item):
        icon.stop()
        float_bar.destroy()

    # ── Refresh loop ──────────────────────────────────────────────────────────
    def refresh_loop():
        while True:
            interval = fetch_scores()
            if tray_icon:
                tray_icon.icon  = create_icon_image(get_icon_color(current_state))
                tray_icon.title = current_text
            time.sleep(interval)

    # ── Main ──────────────────────────────────────────────────────────────────
    def main():
        global tray_icon

        fetch_scores()

        # Tray icon
        tray_icon = pystray.Icon(
            name="PAK Cricket",
            icon=create_icon_image(get_icon_color(current_state)),
            title=current_text,
            menu=pystray.Menu(
                pystray.MenuItem("Show Score", show_popup_from_tray, default=True),
                pystray.MenuItem("Hide/Show Bar", toggle_bar),
                pystray.MenuItem("Quit", quit_app),
            ),
        )

        # Refresh thread
        threading.Thread(target=refresh_loop, daemon=True).start()

        # Tray runs in its own thread so tkinter can own the main thread
        threading.Thread(target=tray_icon.run, daemon=True).start()

        # Floating bar (owns main thread)
        bar = create_floating_bar()
        bar.after(2000, update_bar)
        bar.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()