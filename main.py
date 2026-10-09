"""PAK Cricket desktop UI. Network work runs outside the UI thread."""
import queue
import logging
from pathlib import Path
import shutil
import sys
import threading
import webbrowser
from scraper import match_url, parse_date
from scores import ScoreService, freshness
from settings import load_settings, save_settings
from updater import (monitor_updates, prepare_windows_update,
                     start_update_helper, discard_stage)
from update_engine import apply_update, confirm_update, cleanup_update, launch_app
from version import CURRENT_VERSION, GITHUB_REPO

# A copied portable executable acts as the helper, before any GUI is created.
if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--apply-update":
    sys.exit(apply_update(sys.argv[2]))

LABELS = {"live": "LIVE", "today": "TODAY", "scheduled": "SCHEDULED", "completed": "COMPLETED", "none": "NO FIXTURES", "unknown": "STATUS UNKNOWN"}
COLORS = {"live": "#ef6262", "today": "#f0b95c", "scheduled": "#f0b95c", "completed": "#92a3b8", "none": "#92a3b8", "unknown": "#92a3b8"}
BG, CARD, FG, MUTED, GREEN = "#121a24", "#1d2938", "#eef3f8", "#a6b5c7", "#64d4a4"

def chosen_match(snapshot, selected=None):
    return next((m for m in snapshot["matches"] if m["id"] == selected), next(iter(snapshot["matches"]), None))

def compact_text(match):
    if not match:
        return "No Pakistan or PSL fixtures"
    rows = match.get("scores", [])
    if rows:
        return "  ·  ".join(f"{r['team']} {r['runs']}" + (f"/{r['wickets']}" if r['wickets'] is not None else "") + (f" ({r['overs']})" if r['overs'] else "") for r in rows)
    start = parse_date(match.get("start_time"))
    return match["teams"] + (f" · {start.astimezone():%d %b %H:%M}" if start else "")

def start_label(match):
    start = parse_date(match.get("start_time"))
    prefix = "Played" if match.get("state") == "completed" else "Starts"
    return f"{prefix} {start.astimezone():%a %d %b, %H:%M %Z}" if start else "Start time unavailable"

if sys.platform == "darwin":
    import rumps

    class CricketApp(rumps.App):
        def __init__(self):
            super().__init__("PAK Cricket", title="Fetching…", quit_button=None)
            self.service, self.selected, self.update = ScoreService(), None, None
            self.updates = queue.Queue()
            self.update_stop, self.update_request = threading.Event(), threading.Event()
            self.preferences = load_settings()
            self.notified_version = self.preferences["notified_version"]
            self.menu = [rumps.MenuItem("Fetching scores…")]
            self.service.start()
            self.timer = rumps.Timer(self.tick, 2)
            self.timer.start()
            threading.Thread(target=self.check_update, daemon=True).start()

        def check_update(self):
            monitor_updates(CURRENT_VERSION, GITHUB_REPO, self.updates.put, self.update_stop, self.update_request)

        def tick(self, _):
            if not self.updates.empty():
                result = self.updates.get()
                if not result.get("error"):
                    self.update = result
                if self.update and self.update.get("update_available") and self.notified_version != self.update["latest_version"]:
                    self.notified_version = self.update["latest_version"]
                    self.preferences["notified_version"] = self.notified_version
                    save_settings(self.preferences)
                    try:
                        rumps.notification("PAK Cricket", "Update available", f"{self.notified_version} is available in the menu.")
                    except Exception:
                        logging.exception("macOS update notification failed")
            snapshot = self.service.snapshot()
            match = chosen_match(snapshot, self.selected)
            state = match["state"] if match else snapshot["state"]
            self.title = ("⚠ " if snapshot["errors"] else "") + LABELS[state] + " · " + (compact_text(match) if snapshot["updated_at"] else freshness(snapshot))
            if len(self.title) > 65:
                self.title = self.title[:62] + "…"
            items = [rumps.MenuItem(LABELS[state]), rumps.MenuItem(freshness(snapshot)), None]
            for m in snapshot["matches"]:
                item = rumps.MenuItem(m["teams"], callback=lambda _, ident=m["id"]: self.select(ident))
                item.state = bool(match and m["id"] == match["id"])
                items.append(item)
                for row in m.get("scores", []):
                    items.append(rumps.MenuItem(f"  {row['team']} {row['runs']}" + (f"/{row['wickets']}" if row['wickets'] is not None else "") + f"  {row['overs']} overs"))
                items.append(rumps.MenuItem(m.get("status") or start_label(m)))
                if m.get("series"):
                    items.append(rumps.MenuItem(m["series"]))
            items += [None, rumps.MenuItem("Refresh now", callback=lambda _: self.service.request_refresh()),
                      rumps.MenuItem("Open on Cricbuzz", callback=lambda _: self.open_source()), None]
            items.append(rumps.MenuItem("Check for updates", callback=lambda _: self.update_request.set()))
            if self.update and self.update.get("update_available"):
                items.append(rumps.MenuItem(f"Download {self.update['latest_version']}", callback=lambda _: webbrowser.open(self.update["release_url"])))
            items.append(rumps.MenuItem("Quit", callback=self.quit))
            self.menu.clear()
            self.menu.update(items)

        def select(self, ident):
            self.selected = ident
            self.tick(None)

        def open_source(self):
            match = chosen_match(self.service.snapshot(), self.selected)
            if match and match_url(match):
                webbrowser.open(match_url(match))

        def quit(self, _):
            self.update_stop.set()
            self.update_request.set()
            self.service.stop()
            rumps.quit_application()

    def main():
        CricketApp().run()

else:
    import tkinter as tk
    from tkinter import ttk
    import pystray
    from PIL import Image, ImageDraw

    class CricketApp:
        def __init__(self, service=None, preferences=None, tray=True):
            self.service = service or ScoreService()
            self.preferences = preferences if preferences is not None else load_settings()
            self.commands = queue.Queue()
            self.popup = None
            self.cards_revision = None
            self.card_selection = None
            self.tray_icon = None
            self.update = None
            self.update_busy = False
            self.update_progress = None
            self.update_stop, self.update_request = threading.Event(), threading.Event()
            self.notified_version = self.preferences["notified_version"]
            self.closing = False
            self.root = tk.Tk()
            self.root.report_callback_exception = self.report_ui_error
            self.root.protocol("WM_DELETE_WINDOW", self.quit)
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", self.preferences["topmost"])
            self.root.configure(bg=BG)
            width = min(640, self.root.winfo_screenwidth() - 20)
            pos = self.preferences["position"] or [self.root.winfo_screenwidth() - width - 10, 10]
            # Clamp restored coordinates to the current primary screen.
            x = min(max(0, pos[0]), self.root.winfo_screenwidth() - width)
            y = min(max(0, pos[1]), self.root.winfo_screenheight() - 44)
            self.root.geometry(f"{width}x44+{x}+{y}")
            self.status = tk.Label(self.root, text="●", fg=MUTED, bg=BG, padx=8)
            self.status.pack(side="left")
            self.label = tk.Label(self.root, text="Fetching scores…", fg=FG, bg=BG,
                                  font=("Segoe UI", self.preferences["text_size"], "bold"), anchor="w")
            self.label.pack(side="left", fill="both", expand=True)
            self.details = tk.Button(self.root, text="Details ▾", command=self.show_details, bg=CARD, fg=FG,
                                     relief="flat", padx=10, takefocus=True)
            self.details.pack(side="right", padx=6, pady=7)
            self.update_badge = tk.Button(self.root, text="Update", command=self.open_update,
                                          bg=GREEN, fg=BG, relief="flat", padx=8)
            self.context = tk.Menu(self.root, tearoff=False)
            for name, command in [("Details", self.show_details), ("Refresh now", self.service.request_refresh),
                                  ("Open on Cricbuzz", self.open_source), ("Hide bar", self.toggle_bar),
                                  ("Always on top", self.toggle_topmost), ("Increase text size", lambda: self.resize_text(1)),
                                  ("Check for updates", self.update_request.set),
                                  ("Update now", self.open_update),
                                  ("Decrease text size", lambda: self.resize_text(-1)), ("Quit", self.quit)]:
                self.context.add_command(label=name, command=command)
            for widget in (self.root, self.status, self.label):
                widget.bind("<ButtonPress-1>", self.drag_start)
                widget.bind("<B1-Motion>", self.drag_move)
                widget.bind("<ButtonRelease-1>", self.drag_end)
                widget.bind("<Double-Button-1>", lambda _: self.show_details())
                widget.bind("<Button-3>", lambda e: self.context.tk_popup(e.x_root, e.y_root))
            self.root.bind("<Return>", lambda _: self.show_details())
            if tray:
                self.create_tray()
            # A hidden bar remains accessible through the tray; without it show the bar.
            if self.preferences["hidden"] and self.tray_icon:
                self.root.withdraw()
            self.service.start()
            self.root.after(100, self.tick)
            self.root.after(2000, self.keep_visible)
            threading.Thread(target=self.check_update, daemon=True).start()
            if len(sys.argv) == 3 and sys.argv[1] == "--update-health":
                self.root.after(1500, lambda: confirm_update(sys.argv[2], sys.executable))
                self.root.after(60000, lambda: cleanup_update(sys.argv[2], sys.executable))

        def save(self):
            save_settings(self.preferences)

        def create_tray(self):
            def action(name):
                return lambda icon, item: self.commands.put(name)
            self.tray_icon = pystray.Icon("PAK Cricket", self.icon_image(MUTED), "PAK Cricket",
                pystray.Menu(pystray.MenuItem("Show Score", action("details"), default=True),
                             pystray.MenuItem("Refresh now", action("refresh")),
                             pystray.MenuItem("Hide/Show Bar", action("toggle")),
                             pystray.MenuItem("Check for updates", action("check_update")),
                             pystray.MenuItem("Update now", action("install_update")),
                             pystray.MenuItem("Always on top", action("topmost"), checked=lambda _: self.preferences["topmost"]),
                             pystray.MenuItem("Quit", action("quit"))))
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

        @staticmethod
        def icon_image(color):
            image = Image.new("RGBA", (32, 32))
            draw = ImageDraw.Draw(image)
            draw.ellipse((3, 3, 29, 29), fill=color)
            draw.arc((7, 5, 25, 27), 70, 250, fill="white", width=2)
            return image

        def check_update(self):
            monitor_updates(CURRENT_VERSION, GITHUB_REPO,
                            lambda result: self.commands.put(("update", result)),
                            self.update_stop, self.update_request)

        def report_ui_error(self, kind, error, trace):
            logging.error("UI callback failed", exc_info=(kind, error, trace))

        def keep_visible(self):
            try:
                from window_visibility import ensure_bar_visible
                ensure_bar_visible(self.root, self.preferences["hidden"], self.preferences["topmost"])
            except Exception:
                logging.exception("Could not restore score bar visibility")
            finally:
                if not self.closing:
                    self.root.after(2000, self.keep_visible)

        def drag_start(self, event):
            self.drag_origin = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

        def drag_move(self, event):
            a, b, x, y = self.drag_origin
            self.root.geometry(f"+{max(0, x + event.x_root - a)}+{max(0, y + event.y_root - b)}")

        def drag_end(self, _):
            self.preferences["position"] = [self.root.winfo_x(), self.root.winfo_y()]
            self.save()

        def toggle_bar(self):
            self.preferences["hidden"] = not self.preferences["hidden"]
            self.root.withdraw() if self.preferences["hidden"] else self.root.deiconify()
            self.save()

        def toggle_topmost(self):
            self.preferences["topmost"] = not self.preferences["topmost"]
            self.root.attributes("-topmost", self.preferences["topmost"])
            self.save()

        def resize_text(self, step):
            self.preferences["text_size"] = min(16, max(9, self.preferences["text_size"] + step))
            self.label.configure(font=("Segoe UI", self.preferences["text_size"], "bold"))
            self.save()

        def select(self, ident):
            self.preferences["selected"] = None if self.preferences["selected"] == ident else ident
            self.save()
            self.cards_revision = None

        def open_source(self, match=None):
            match = match or chosen_match(self.service.snapshot(), self.preferences["selected"])
            if match and match_url(match):
                webbrowser.open(match_url(match))

        def show_details(self):
            if self.popup and self.popup.winfo_exists():
                self.popup.lift()
                return
            self.popup = tk.Toplevel(self.root)
            self.popup.title("PAK Cricket · Match details")
            self.popup.configure(bg=BG)
            self.popup.geometry("560x520")
            self.popup.minsize(420, 320)
            self.popup.protocol("WM_DELETE_WINDOW", self.close_details)
            self.popup.bind("<Escape>", lambda _: self.close_details())
            tk.Label(self.popup, text="Pakistan & PSL", bg=BG, fg=FG, font=("Segoe UI", 17, "bold"), anchor="w").pack(fill="x", padx=20, pady=(18, 4))
            self.fresh_label = tk.Label(self.popup, bg=BG, fg=MUTED, anchor="w")
            self.fresh_label.pack(fill="x", padx=20, pady=(0, 12))
            body = tk.Frame(self.popup, bg=BG)
            body.pack(fill="both", expand=True)
            self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
            scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
            scrollbar.pack(side="right", fill="y")
            self.canvas.pack(side="left", fill="both", expand=True)
            self.canvas.configure(yscrollcommand=scrollbar.set)
            self.cards = tk.Frame(self.canvas, bg=BG)
            self.cards_window = self.canvas.create_window((0, 0), window=self.cards, anchor="nw")
            self.cards.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.canvas.bind("<Configure>", self.layout_cards)
            self.popup.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta / 120), "units"))
            footer = tk.Frame(self.popup, bg=BG)
            footer.pack(fill="x", padx=20, pady=14)
            tk.Button(footer, text="Refresh now", command=self.service.request_refresh).pack(side="left")
            self.update_button = tk.Button(footer, text="", command=self.open_update)
            tk.Button(footer, text="Close", command=self.close_details).pack(side="right")
            self.cards_revision = None
            self.render_details(self.service.snapshot())

        def layout_cards(self, event):
            self.canvas.itemconfigure(self.cards_window, width=event.width)
            for label in self.wrapped_labels:
                label.configure(wraplength=max(250, event.width - 60))

        def close_details(self):
            if self.popup:
                self.popup.destroy()
                self.popup = None

        def render_details(self, snapshot):
            if not self.popup:
                return
            self.fresh_label.configure(text=freshness(snapshot), fg=COLORS["scheduled"] if snapshot["errors"] else MUTED)
            if self.update and self.update.get("update_available"):
                self.update_button.configure(text=f"Update to {self.update['latest_version']}", state="disabled" if self.update_busy else "normal")
                self.update_button.pack(side="left", padx=10)
            if self.cards_revision == snapshot["revision"]:
                return
            self.cards_revision = snapshot["revision"]
            position = self.canvas.yview()[0]
            for child in self.cards.winfo_children():
                child.destroy()
            self.wrapped_labels = []
            if not snapshot["matches"]:
                message = "Unable to fetch scores. Retrying automatically." if snapshot["errors"] else "Fetching scores…" if snapshot["updated_at"] is None else "No Pakistan or PSL fixtures available."
                tk.Label(self.cards, text=message, bg=BG, fg=MUTED, pady=30).pack()
            for match in snapshot["matches"]:
                card = tk.Frame(self.cards, bg=CARD, padx=14, pady=12)
                card.pack(fill="x", padx=20, pady=(0, 12))
                def label(text, color=FG, size=10, bold=False):
                    item = tk.Label(card, text=text, bg=CARD, fg=color, anchor="w", justify="left",
                                    font=("Segoe UI", size, "bold" if bold else "normal"), wraplength=460)
                    item.pack(fill="x", pady=3)
                    self.wrapped_labels.append(item)
                label(LABELS[match["state"]], COLORS[match["state"]], 9, True)
                label(match["teams"], size=13, bold=True)
                label(match.get("series", ""), MUTED, 9)
                for row in match.get("scores", []):
                    score = str(row["runs"]) + (f"/{row['wickets']}" if row['wickets'] is not None else "")
                    label(f"{row['team']}     {score}     {row['overs']} overs", GREEN, 14, True)
                if not match.get("scores"):
                    label(start_label(match), MUTED)
                label(match.get("status") or "Status unavailable", MUTED)
                controls = tk.Frame(card, bg=CARD)
                controls.pack(fill="x", pady=(8, 0))
                pinned = self.preferences["selected"] == match["id"]
                tk.Button(controls, text="Unpin from bar" if pinned else "Pin to bar", command=lambda ident=match["id"]: self.select(ident)).pack(side="left")
                tk.Button(controls, text="Open on Cricbuzz", command=lambda m=match: self.open_source(m)).pack(side="right")
            self.canvas.yview_moveto(position)

        def open_update(self):
            from tkinter import messagebox
            if self.update_busy:
                return
            if not self.update or not self.update.get("update_available"):
                self.update_request.set()
                messagebox.showinfo("PAK Cricket", "Checking for updates. A button will appear when a new release is available.", parent=self.root)
                return
            if not getattr(sys, "frozen", False):
                webbrowser.open(self.update["release_url"])
                return
            if not messagebox.askyesno("Update available", f"Download {self.update['latest_version']} and restart PAK Cricket?\n\nYour settings will be preserved and the current executable kept as a backup.", parent=self.root):
                return
            self.update_busy = True
            self.update_progress = 0
            info = dict(self.update)
            def download():
                try:
                    prepared = prepare_windows_update(info, lambda percent: self.commands.put(("progress", percent)))
                    self.commands.put(("prepared_update", prepared))
                except Exception as exc:
                    logging.exception("Update download failed")
                    self.commands.put(("update_error", str(exc)))
            threading.Thread(target=download, daemon=True).start()

        def finish_update(self, prepared):
            from tkinter import filedialog, messagebox
            try:
                if prepared["save_as"]:
                    destination = filedialog.asksaveasfilename(title="Choose a writable folder for the updated app", initialfile="PakCricket.exe", defaultextension=".exe", filetypes=[("Windows executable", "*.exe")], parent=self.root)
                    if not destination:
                        discard_stage(prepared["stage"])
                        self.update_busy, self.update_progress = False, None
                        return
                    if Path(destination).resolve() == Path(sys.executable).resolve():
                        raise RuntimeError("Choose a different location; the current folder cannot be updated")
                    shutil.copy2(prepared["incoming"], destination)
                    launch_app(Path(destination).resolve())
                    discard_stage(prepared["stage"])
                else:
                    start_update_helper(prepared)
                self.quit()
            except Exception as exc:
                self.update_busy, self.update_progress = False, None
                discard_stage(prepared["stage"])
                logging.exception("Could not start update")
                messagebox.showerror("Update failed", f"{exc}\n\nThe running app has not been replaced.", parent=self.root)

        def tick(self):
            try:
                self.tick_content()
            except Exception:
                logging.exception("Score bar refresh failed")
            finally:
                if not self.closing:
                    self.root.after(1000, self.tick)

        def tick_content(self):
            while not self.commands.empty():
                command = self.commands.get()
                if isinstance(command, tuple):
                    kind, value = command
                    if kind == "update":
                        if not value.get("error"):
                            self.update = value
                        if self.update and self.update.get("update_available") and self.notified_version != self.update["latest_version"]:
                            self.notified_version = self.update["latest_version"]
                            self.preferences["notified_version"] = self.notified_version
                            self.save()
                            if self.tray_icon:
                                try:
                                    self.tray_icon.notify(f"{self.notified_version} is available. Click Update on the score bar.", "PAK Cricket update")
                                except Exception:
                                    logging.exception("Update notification failed")
                    elif kind == "progress":
                        self.update_progress = value
                    elif kind == "prepared_update":
                        self.finish_update(value)
                        if self.closing:
                            return
                    elif kind == "update_error":
                        from tkinter import messagebox
                        self.update_busy, self.update_progress = False, None
                        messagebox.showerror("Update failed", f"{value}\n\nThe running app was not changed. Try again or download from the release page.", parent=self.root)
                elif command == "quit":
                    self.quit()
                    return
                else:
                    {"details": self.show_details, "refresh": self.service.request_refresh,
                     "toggle": self.toggle_bar, "topmost": self.toggle_topmost,
                     "check_update": self.update_request.set, "install_update": self.open_update}[command]()
            if self.update and self.update.get("update_available"):
                self.update_badge.configure(text=f"Updating {self.update_progress}%" if self.update_busy else "Update available", state="disabled" if self.update_busy else "normal")
                self.update_badge.pack(side="right", padx=3, pady=7)
            else:
                self.update_badge.pack_forget()
            snapshot = self.service.snapshot()
            match = chosen_match(snapshot, self.preferences["selected"])
            state = match["state"] if match else snapshot["state"]
            delayed = bool(snapshot["errors"])
            status = "DELAYED" if delayed else "FETCHING" if snapshot["updated_at"] is None else LABELS[state]
            self.status.configure(text=f"● {status}", fg=COLORS["scheduled"] if delayed else COLORS[state])
            text = compact_text(match) if snapshot["updated_at"] else freshness(snapshot)
            # Fit the available label width; full text is available in details/tray.
            from tkinter import font
            available = max(80, self.label.winfo_width() - 8)
            face = font.Font(font=self.label.cget("font"))
            shown = text
            while len(shown) > 1 and face.measure(shown + ("…" if shown != text else "")) > available:
                shown = shown[:-1]
            self.label.configure(text=shown + ("…" if shown != text else ""))
            if self.tray_icon:
                title = f"{status} · {text} · {freshness(snapshot)}"[:127]
                if self.tray_icon.title != title:
                    self.tray_icon.title = title
                color = COLORS["scheduled"] if delayed else COLORS[state]
                if getattr(self, "tray_color", None) != color:
                    self.tray_icon.icon = self.icon_image(color)
                    self.tray_color = color
            self.render_details(snapshot)

        def quit(self):
            self.closing = True
            self.update_stop.set()
            self.update_request.set()
            self.service.stop()
            if self.tray_icon:
                self.tray_icon.stop()
            self.root.destroy()

        def run(self):
            self.root.mainloop()

    def main():
        CricketApp().run()

if __name__ == "__main__":
    from app_logging import configure_logging
    configure_logging()
    main()
