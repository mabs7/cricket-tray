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
import webbrowser

from scraper import get_all_matches
from filter import get_match_state, get_display_text
from version import CURRENT_VERSION, GITHUB_REPO
from updater import check_for_updates

# ── Refresh intervals ──────────────────────────────────────────────────────────
INTERVAL_LIVE = 45
INTERVAL_TODAY = 300
INTERVAL_NONE = 1800

# ── Shared state ───────────────────────────────────────────────────────────────
current_matches = []
current_state = "none"
current_text = "🏏 Fetching..."


def fetch_scores():
    """Fetch latest scores and update globals. Returns interval for next fetch."""
    global current_matches, current_state, current_text

    all_data = get_all_matches()
    state, matches = get_match_state(all_data)

    current_state = state
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
            threading.Thread(target=self._check_update_startup, daemon=True).start()

        def _check_update_startup(self):
            update_info = check_for_updates(CURRENT_VERSION, GITHUB_REPO)
            if update_info.get("update_available"):
                response = rumps.alert(
                    title="Update Available",
                    message=f"A new version ({update_info['latest_version']}) of PAK Cricket is available.\nWould you like to download it now?",
                    ok="Download",
                    cancel="Cancel",
                )
                if response == 1:
                    webbrowser.open(update_info["release_url"])

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
            state_label = {
                "live": "🔴 LIVE",
                "today": "🟠 Scheduled Today",
                "none": "⚫ Recent",
            }
            lines.append(state_label.get(current_state, ""))
            lines.append("")
            for match in current_matches:
                lines.append(f"▶ {match.get('teams', '')}")
                if match.get("score"):
                    lines.append(f"   Score: {match['score']}")
                if match.get("status"):
                    lines.append(f"   Status: {match['status']}")
                if match.get("series"):
                    lines.append(f"   Series: {match['series']}")
                lines.append("")

            rumps.alert(
                title="🏏 Pakistan Cricket",
                message="\n".join(lines).strip(),
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

    tray_icon = None
    float_bar = None  # the always-on-top floating window
    bar_label = None  # label inside the bar
    bar_hidden = False  # toggle visibility
    popup_open = False  # prevent multiple popups

    # ── Icon drawing ──────────────────────────────────────────────────────────
    def create_icon_image(color="#00A550"):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 30, 30], fill=color, outline="white", width=2)
        draw.arc([6, 6, 26, 26], start=30, end=150, fill="white", width=2)
        draw.arc([6, 6, 26, 26], start=210, end=330, fill="white", width=2)
        return img

    def get_icon_color(state):
        return {"live": "#CC0000", "today": "#FFA500", "none": "#555555"}.get(
            state, "#555555"
        )

    def get_bar_color(state):
        return {"live": "#8B0000", "today": "#7A4000", "none": "#1a1a2e"}.get(
            state, "#1a1a2e"
        )

    # ── Floating bar ──────────────────────────────────────────────────────────
    def create_floating_bar():
        global float_bar, bar_label

        float_bar = tk.Tk()
        float_bar.overrideredirect(True)  # no title bar / borders
        float_bar.attributes("-topmost", True)  # always on top
        float_bar.attributes("-alpha", 0.92)  # slight transparency
        float_bar.configure(bg="#1a1a2e")

        # Position: top-right corner
        sw = float_bar.winfo_screenwidth()
        float_bar.geometry(f"480x32+{sw - 490}+10")

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
        float_bar.bind("<ButtonPress-1>", _drag_start)
        float_bar.bind("<B1-Motion>", _drag_move)
        bar_label.bind("<ButtonPress-1>", _drag_start)
        bar_label.bind("<B1-Motion>", _drag_move)

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
        """Refresh the floating bar text and colour. Always reschedules itself."""
        try:
            if bar_label and float_bar and not bar_hidden:
                # Show score if available, otherwise show teams
                display = current_text
                bar_label.config(text=display, bg=get_bar_color(current_state))
                float_bar.configure(bg=get_bar_color(current_state))
        except Exception:
            pass  # never let a crash kill the loop
        finally:
            float_bar.after(2000, update_bar)  # always reschedule

    # ── Detail popup ──────────────────────────────────────────────────────────
    def _restore_bar():
        """Safely restore floating bar after popup closes."""
        try:
            float_bar.lift()
            float_bar.attributes("-topmost", True)
            float_bar.deiconify()
        except Exception:
            pass

    def show_detail_popup():
        global popup_open
        if popup_open:
            return  # block if already open

        popup_open = True
        popup = tk.Toplevel()
        popup.title("PAK Cricket")
        popup.geometry("420x340")
        popup.configure(bg="#1a1a2e")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        _restore_bar()

        def on_popup_close():
            global popup_open
            popup_open = False
            popup.destroy()
            float_bar.after(100, _restore_bar)

        popup.protocol("WM_DELETE_WINDOW", on_popup_close)

        tk.Label(
            popup,
            text="🏏 Pakistan Cricket",
            font=("Segoe UI", 14, "bold"),
            fg="#00A550",
            bg="#1a1a2e",
            pady=10,
        ).pack(fill="x")
        tk.Frame(popup, bg="#00A550", height=2).pack(fill="x", padx=10)

        frame = tk.Frame(popup, bg="#1a1a2e")
        frame.pack(fill="both", expand=True, padx=15, pady=10)

        # Dynamic labels that auto-update
        score_labels = []  # list of (teams_var, score_var, status_var)

        if not current_matches:
            no_match_lbl = tk.Label(
                frame,
                text="No Pakistan match right now.",
                font=("Segoe UI", 11),
                fg="#aaaaaa",
                bg="#1a1a2e",
            )
            no_match_lbl.pack(pady=20)
        else:
            for match in current_matches:
                card = tk.Frame(frame, bg="#16213e")
                card.pack(fill="x", pady=5, ipady=8, ipadx=8)

                teams_var = tk.StringVar(value=match.get("teams", ""))
                score_var = tk.StringVar(value=match.get("score", "No score yet"))
                status_var = tk.StringVar(value=match.get("status", ""))

                tk.Label(
                    card,
                    textvariable=teams_var,
                    font=("Segoe UI", 12, "bold"),
                    fg="#ffffff",
                    bg="#16213e",
                    anchor="w",
                ).pack(fill="x", padx=8)
                tk.Label(
                    card,
                    textvariable=score_var,
                    font=("Segoe UI", 11),
                    fg="#FFD700",
                    bg="#16213e",
                    anchor="w",
                ).pack(fill="x", padx=8)
                tk.Label(
                    card,
                    textvariable=status_var,
                    font=("Segoe UI", 10),
                    fg="#CC0000",
                    bg="#16213e",
                    anchor="w",
                ).pack(fill="x", padx=8)

                score_labels.append((teams_var, score_var, status_var))

        def refresh_popup():
            """Update popup labels with latest score data every 5 seconds."""
            try:
                for i, (tv, sv, stv) in enumerate(score_labels):
                    if i < len(current_matches):
                        m = current_matches[i]
                        tv.set(m.get("teams", ""))
                        sv.set(m.get("score", "No score yet"))
                        stv.set(m.get("status", ""))
                if popup.winfo_exists():
                    popup.after(5000, refresh_popup)
            except Exception:
                pass

        popup.after(5000, refresh_popup)  # start auto-refresh

        state_map = {
            "live": "🔴 LIVE",
            "today": "🟠 Scheduled",
            "none": "⚫ No live match",
        }
        tk.Label(
            popup,
            text=state_map.get(current_state, ""),
            font=("Segoe UI", 9),
            fg="#888888",
            bg="#1a1a2e",
            pady=6,
        ).pack()
        tk.Button(
            popup,
            text="Close",
            command=on_popup_close,
            bg="#00A550",
            fg="white",
            font=("Segoe UI", 10),
            relief="flat",
            padx=20,
        ).pack(pady=(0, 10))
        # Restore bar if user clicks away from popup without using Close button
        popup.bind("<FocusOut>", lambda e: _restore_bar())

    # ── Tray menu actions ─────────────────────────────────────────────────────
    def toggle_bar(icon, item):
        """Thread-safe toggle — schedule on tkinter main thread."""

        def _do_toggle():
            global bar_hidden
            bar_hidden = not bar_hidden
            if bar_hidden:
                float_bar.withdraw()
            else:
                float_bar.deiconify()
                float_bar.attributes("-topmost", True)  # re-assert topmost on show

        float_bar.after(0, _do_toggle)

    def show_popup_from_tray(icon, item):
        """Thread-safe popup — schedule on tkinter main thread."""
        float_bar.after(0, show_detail_popup)

    def quit_app(icon, item):
        float_bar.after(0, float_bar.destroy)
        icon.stop()

    # ── Refresh loop ──────────────────────────────────────────────────────────
    def refresh_loop():
        while True:
            interval = fetch_scores()
            if tray_icon:
                tray_icon.icon = create_icon_image(get_icon_color(current_state))
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

        # Update check
        def check_update_windows():
            update_info = check_for_updates(CURRENT_VERSION, GITHUB_REPO)
            if update_info.get("update_available"):
                def show_update():
                    from tkinter import messagebox
                    response = messagebox.askyesno(
                        "Update Available",
                        f"A new version ({update_info['latest_version']}) of PAK Cricket is available.\nWould you like to download it now?",
                        parent=bar
                    )
                    if response:
                        webbrowser.open(update_info["release_url"])
                bar.after(2000, show_update)

        threading.Thread(target=check_update_windows, daemon=True).start()

        bar.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
