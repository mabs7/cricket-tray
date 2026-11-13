"""PAK Cricket desktop UI. Network work runs outside the UI thread."""
import queue
import logging
from pathlib import Path
import shutil
import sys
import threading
import webbrowser
from filter import TEAMS, TEAM_NAMES, categories_for_scope, matches_category
from scraper import match_url, parse_date
from scores import ScoreService, freshness
from settings import load_settings, save_settings
from updater import (monitor_updates, prepare_windows_update,
                     start_update_helper, discard_stage)
from update_engine import apply_update, confirm_update, cleanup_update, cleanup_old_updates, launch_app
from version import CURRENT_VERSION, GITHUB_REPO

# A copied portable executable acts as the helper, before any GUI is created.
if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--apply-update":
    sys.exit(apply_update(sys.argv[2]))

LABELS = {"live": "LIVE", "paused": "PAUSED", "today": "TODAY", "scheduled": "SCHEDULED", "completed": "COMPLETED", "none": "NO FIXTURES", "unknown": "STATUS UNKNOWN"}
COLORS = {"live": "#ef6262", "paused": "#7ec8f8", "today": "#f0b95c", "scheduled": "#f0b95c", "completed": "#92a3b8", "none": "#92a3b8", "unknown": "#92a3b8"}
BG, SURFACE, CARD, CARD_HOVER, CARD_ACTIVE = "#0f1620", "#141e2b", "#1a2636", "#223247", "#1e3044"
BORDER, FG, MUTED, GREEN = "#2a3b52", "#eef3f8", "#9eb0c4", "#64d4a4"

def chosen_match(snapshot, selected=None):
    return next((m for m in snapshot["matches"] if m["id"] == selected), next(iter(snapshot["matches"]), None))

def state_label(match, state=None):
    """LIVE/TODAY/... or, for an interrupted match, its phase such as STUMPS or TEA."""
    if match:
        if match.get("state") == "paused" and match.get("phase"):
            return match["phase"].upper()
        if match.get("state") == "scheduled":
            start = parse_date(match.get("start_time"))
            if start and start.astimezone().date() == start.now().astimezone().date():
                return LABELS["today"]
        state = match.get("state")
    return LABELS.get(state, LABELS["unknown"])

def series_line(match):
    return " · ".join(part for part in (match.get("competition", ""), match.get("series", "")) if part)

def team_option_label(team):
    league = TEAMS.get(team, {}).get("league")
    return f"{team} (+ {league})" if league else team

def feed_title(scope, team):
    if scope == "international":
        return "International & Leagues"
    team = team if team in TEAMS else "Pakistan"
    return team_option_label(team)

def compact_text(match):
    if not match:
        return "No matches to show"
    rows = match.get("scores", [])
    if rows:
        return "  ·  ".join(
            f"{r['team']} {r['runs']}"
            + (f"/{r['wickets']}" if r['wickets'] is not None else "")
            + ("d" if r.get("declared") else "")
            + (f" ({r['overs']})" if r['overs'] else "")
            for r in rows
        )
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
            self.preferences = load_settings()
            self.selected = self.preferences.get("selected")
            scope = self.preferences.get("scope") or "team"
            raw_team = self.preferences.get("team")
            team = raw_team if raw_team in TEAMS else "Pakistan"
            self.service = ScoreService(scope=scope, team=team)
            self.update = None
            self.updates = queue.Queue()
            self.update_stop, self.update_request = threading.Event(), threading.Event()
            self.notified_version = self.preferences["notified_version"]
            self._menu_key = None
            self._fresh_item = None
            self.menu = [rumps.MenuItem("Fetching scores…")]
            self.service.start()
            self.timer = rumps.Timer(self.tick, 2)
            self.timer.start()
            threading.Thread(target=self.check_update, daemon=True).start()

        def check_update(self):
            monitor_updates(CURRENT_VERSION, GITHUB_REPO, self.updates.put, self.update_stop, self.update_request)

        def set_feed(self, scope, team=None):
            self.preferences["scope"] = scope
            if team in TEAMS:
                self.preferences["team"] = team
            elif scope == "team" and self.preferences.get("team") not in TEAMS:
                self.preferences["team"] = "Pakistan"
            self.selected = None
            self.preferences["selected"] = None
            save_settings(self.preferences)
            self.service.set_filter(scope, self.preferences.get("team"))
            self.tick(None)

        def tick(self, _):
            while not self.updates.empty():
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
            label = "DELAYED" if snapshot["errors"] and not snapshot["matches"] else (
                "FETCHING" if snapshot["updated_at"] is None and not snapshot["matches"] else state_label(match, snapshot["state"])
            )
            self.title = ("⚠ " if snapshot["errors"] else "") + label + " · " + (compact_text(match) if snapshot["updated_at"] else freshness(snapshot))
            if len(self.title) > 65:
                self.title = self.title[:62] + "…"
            scope = self.preferences.get("scope") or "team"
            raw_team = self.preferences.get("team")
            team = raw_team if raw_team in TEAMS else "Pakistan"
            latest_ver = self.update["latest_version"] if (self.update and self.update.get("update_available")) else None
            menu_key = (snapshot["revision"], self.selected, scope, team, latest_ver)
            if menu_key == self._menu_key and self._fresh_item is not None:
                self._fresh_item.title = freshness(snapshot)
                return
            self._menu_key = menu_key
            self._fresh_item = rumps.MenuItem(freshness(snapshot))
            items = [rumps.MenuItem(f"{label} · {feed_title(scope, team)}"), self._fresh_item, None]
            for m in snapshot["matches"]:
                prefix = f"[{m['competition']}] " if m.get("competition") else ""
                item = rumps.MenuItem(f"{prefix}{m['teams']} ({state_label(m)})", callback=lambda _, ident=m["id"]: self.select(ident))
                item.state = bool(match and m["id"] == match["id"])
                items.append(item)
                for row in m.get("scores", []):
                    decl = "d" if row.get("declared") else ""
                    overs = f"  {row['overs']} overs" if row.get("overs") else ""
                    items.append(rumps.MenuItem(f"  {row['team']} {row['runs']}" + (f"/{row['wickets']}" if row['wickets'] is not None else "") + decl + overs))
                items.append(rumps.MenuItem(m.get("status") or start_label(m)))
                if series_line(m):
                    items.append(rumps.MenuItem(series_line(m)))
            intl_item = rumps.MenuItem("Feed: International & Leagues", callback=lambda _: self.set_feed("international"))
            intl_item.state = scope == "international"
            team_menu = rumps.MenuItem("Feed: Pick a Team")
            for name in TEAM_NAMES:
                entry = rumps.MenuItem(team_option_label(name), callback=lambda _, t=name: self.set_feed("team", t))
                entry.state = scope == "team" and team == name
                team_menu.add(entry)
            items += [None, intl_item, team_menu, None,
                      rumps.MenuItem("Refresh now", callback=lambda _: self.service.request_refresh()),
                      rumps.MenuItem("Open on Cricbuzz", callback=lambda _: self.open_source()), None]
            items.append(rumps.MenuItem("Check for updates", callback=lambda _: self.update_request.set()))
            if latest_ver:
                items.append(rumps.MenuItem(f"Download {latest_ver}", callback=lambda _: webbrowser.open(self.update["release_url"])))
            items.append(rumps.MenuItem("Quit", callback=self.quit))
            self.menu.clear()
            self.menu.update(items)

        def select(self, ident):
            self.selected = None if self.selected == ident else ident
            self.preferences["selected"] = self.selected
            save_settings(self.preferences)
            self.tick(None)

        def open_source(self):
            match = chosen_match(self.service.snapshot(), self.selected)
            if match and match_url(match):
                webbrowser.open(match_url(match))

        def quit(self, _):
            try:
                self.timer.stop()
            except Exception:
                pass
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

    def _style_button(btn, normal_bg=CARD, hover_bg=CARD_HOVER, fg=FG):
        btn.configure(bg=normal_bg, fg=fg, activebackground=hover_bg, activeforeground=fg,
                      relief="flat", bd=0, cursor="hand2", highlightthickness=0)
        btn.bind("<Enter>", lambda _: btn.configure(bg=hover_bg) if str(btn["state"]) != "disabled" else None)
        btn.bind("<Leave>", lambda _: btn.configure(bg=normal_bg) if str(btn["state"]) != "disabled" else None)
        return btn

    class CricketApp:
        def __init__(self, service=None, preferences=None, tray=True):
            from tkinter import font
            self.preferences = preferences if preferences is not None else load_settings()
            eff_scope = self.preferences.get("scope") or "team"
            raw_team = self.preferences.get("team")
            eff_team = raw_team if raw_team in TEAMS else "Pakistan"
            self.service = service or ScoreService(scope=eff_scope, team=eff_team)
            self.commands = queue.Queue()
            self.popup = None
            self.header = None
            self.cards_revision = None
            self.category = "All"
            self.team_picker_open = self.preferences.get("scope") is None
            self.tray_icon = None
            self.tray_thread = None
            self.tray_ready = threading.Event()
            self.update = None
            self.update_busy = False
            self.update_dialog_open = False
            self.manual_update_check = False
            self.update_progress = None
            self.update_stop, self.update_request = threading.Event(), threading.Event()
            self.notified_version = self.preferences["notified_version"]
            self.closing = False
            self.drag_origin = None
            self._bar_font = None
            self._text_fit_cache = None
            self.root = tk.Tk()
            self.root.report_callback_exception = self.report_ui_error
            self.root.protocol("WM_DELETE_WINDOW", self.quit)
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", self.preferences["topmost"])
            self.root.configure(bg=BG, highlightbackground=BORDER, highlightthickness=1)
            from window_visibility import monitor_work_area
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            bar_h = self._bar_height()
            width = min(660, sw - 20)
            pos = self.preferences["position"] or [sw - width - 10, 10]
            left, top, right, bottom = monitor_work_area(pos[0], pos[1], sw, sh)
            x = min(max(left, pos[0]), max(left, right - width))
            y = min(max(top, pos[1]), max(top, bottom - bar_h))
            self.root.geometry(f"{width}x{bar_h}+{x}+{y}")
            self.status = tk.Label(self.root, text="●", fg=MUTED, bg=BG, font=("Segoe UI", 9, "bold"), padx=10)
            self.status.pack(side="left")
            self._bar_font = font.Font(family="Segoe UI", size=self.preferences["text_size"], weight="bold")
            self.label = tk.Label(self.root, text="Fetching scores…", fg=FG, bg=BG,
                                  font=self._bar_font, anchor="w")
            self.label.pack(side="left", fill="both", expand=True)
            self.details = _style_button(tk.Button(self.root, text="Matches ▾", command=self.show_details,
                                                   font=("Segoe UI", 9, "bold"), padx=11, pady=4, takefocus=True))
            self.details.pack(side="right", padx=6, pady=6)
            self.next_btn = _style_button(tk.Button(self.root, text="▶", command=lambda: self.cycle_match(1),
                                                    font=("Segoe UI", 8, "bold"), padx=6, pady=4))
            self.prev_btn = _style_button(tk.Button(self.root, text="◀", command=lambda: self.cycle_match(-1),
                                                    font=("Segoe UI", 8, "bold"), padx=6, pady=4))
            self.update_badge = _style_button(tk.Button(self.root, text="Update", command=self.open_update,
                                                        font=("Segoe UI", 9, "bold"), padx=9, pady=4),
                                              normal_bg=GREEN, hover_bg="#7ce0b5", fg=BG)
            self.context = tk.Menu(self.root, tearoff=False, bg=SURFACE, fg=FG, activebackground=CARD_HOVER, activeforeground=FG, bd=1)
            for name, command in [("Select Match / Feed", self.show_details),
                                  ("Next match on bar", lambda: self.cycle_match(1)),
                                  ("Previous match on bar", lambda: self.cycle_match(-1)),
                                  ("Auto-select top match", lambda: self.select(None)),
                                  ("Refresh now", self.service.request_refresh),
                                  ("Open on Cricbuzz", self.open_source), ("Hide bar", self.toggle_bar),
                                  ("Always on top", self.toggle_topmost), ("Increase text size", lambda: self.resize_text(1)),
                                  ("Check for updates", self.request_manual_update_check),
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
            if self.preferences.get("scope") is None and not self.preferences["hidden"] and tray:
                self.root.after(250, self.show_details)
            threading.Thread(target=self.check_update, daemon=True).start()
            health_stage = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == "--update-health" else None
            if getattr(sys, "frozen", False):
                cleanup_old_updates(sys.executable, skip_stage=health_stage)
            if health_stage:
                self.root.after(1500, lambda: confirm_update(health_stage, sys.executable))
                self.root.after(15000, lambda: cleanup_update(health_stage, sys.executable))

        def _bar_height(self):
            return max(46, self.preferences["text_size"] * 3 + 16)

        def save(self):
            save_settings(self.preferences)

        def create_tray(self):
            def action(name):
                return lambda icon, item: self.commands.put(name)
            self.tray_icon = pystray.Icon("PAK Cricket", self.icon_image(MUTED), "PAK Cricket",
                pystray.Menu(pystray.MenuItem("Select Match / Feed", action("details"), default=True),
                             pystray.MenuItem("Refresh now", action("refresh")),
                             pystray.MenuItem("Hide/Show Bar", action("toggle")),
                             pystray.MenuItem("Check for updates", action("check_update")),
                             pystray.MenuItem("Update now", action("install_update")),
                             pystray.MenuItem("Always on top", action("topmost"), checked=lambda _: self.preferences["topmost"]),
                             pystray.MenuItem("Quit", action("quit"))))
            def on_setup(icon):
                icon.visible = True
                self.tray_ready.set()
            self.tray_thread = threading.Thread(target=lambda: self.tray_icon.run(setup=on_setup), daemon=True)
            self.tray_thread.start()

        def request_manual_update_check(self):
            self.manual_update_check = True
            self.update_request.set()

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
                    try:
                        self.root.after(2000, self.keep_visible)
                    except tk.TclError:
                        pass

        def drag_start(self, event):
            self.drag_origin = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

        def drag_move(self, event):
            if not self.drag_origin:
                return
            from window_visibility import monitor_work_area
            a, b, x, y = self.drag_origin
            nx, ny = x + event.x_root - a, y + event.y_root - b
            left, top, right, bottom = monitor_work_area(nx, ny, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
            w, h = max(120, self.root.winfo_width()), max(46, self.root.winfo_height())
            cx = min(max(left, nx), max(left, right - w))
            cy = min(max(top, ny), max(top, bottom - h))
            self.root.geometry(f"+{cx}+{cy}")

        def drag_end(self, _):
            if not self.drag_origin:
                return
            self.drag_origin = None
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
            if self.tray_icon and self.tray_ready.is_set():
                try:
                    self.tray_icon.update_menu()
                except Exception:
                    pass

        def resize_text(self, step):
            self.preferences["text_size"] = min(16, max(9, self.preferences["text_size"] + step))
            if self._bar_font is not None:
                self._bar_font.configure(size=self.preferences["text_size"])
            else:
                self.label.configure(font=("Segoe UI", self.preferences["text_size"], "bold"))
            self._text_fit_cache = None
            w = max(120, self.root.winfo_width())
            if w > 120:
                self.root.geometry(f"{w}x{self._bar_height()}")
            self.save()

        def set_feed(self, scope, team=None):
            """Switch between a single team feed and International mode, and save it."""
            if scope not in {"team", "international"}:
                return
            self.preferences["scope"] = scope
            if team in TEAMS:
                self.preferences["team"] = team
            elif scope == "team" and self.preferences.get("team") not in TEAMS:
                self.preferences["team"] = "Pakistan"
            self.preferences["selected"] = None
            self.team_picker_open = False
            self.category = "All"
            self.save()
            self.service.set_filter(scope, self.preferences.get("team"))
            self.cards_revision = None
            if self.popup and self.popup.winfo_exists():
                self.canvas.yview_moveto(0.0)
            self._render_bar(self.service.snapshot())

        def toggle_team_picker(self):
            self.team_picker_open = not self.team_picker_open
            self.cards_revision = None
            if self.popup and self.popup.winfo_exists():
                self.render_details(self.service.snapshot())

        def select(self, ident, toggle=True):
            """Select a match to display on the floating live strip and refresh immediately."""
            if ident is None:
                self.preferences["selected"] = None
            elif toggle and self.preferences["selected"] == ident:
                self.preferences["selected"] = None
            else:
                self.preferences["selected"] = ident
            self.save()
            self.cards_revision = None
            self._render_bar(self.service.snapshot())

        def cycle_match(self, step=1):
            snapshot = self.service.snapshot()
            matches = snapshot.get("matches", [])
            if not matches:
                return
            current = chosen_match(snapshot, self.preferences["selected"])
            ids = [m["id"] for m in matches]
            idx = ids.index(current["id"]) if current and current["id"] in ids else 0
            self.select(ids[(idx + step) % len(ids)], toggle=False)

        def set_category(self, category):
            self.category = category
            self.cards_revision = None
            if self.popup and self.popup.winfo_exists():
                self.canvas.yview_moveto(0.0)
                self.render_details(self.service.snapshot())

        def open_source(self, match=None):
            match = match or chosen_match(self.service.snapshot(), self.preferences["selected"])
            if match and match_url(match):
                webbrowser.open(match_url(match))

        def _configure_scrollbar_style(self):
            try:
                style = ttk.Style(self.root)
                if "clam" in style.theme_names():
                    style.theme_use("clam")
                style.configure("Dark.Vertical.TScrollbar", background=CARD, troughcolor=BG,
                                bordercolor=BG, arrowcolor=MUTED, darkcolor=CARD, lightcolor=CARD, relief="flat")
                style.map("Dark.Vertical.TScrollbar", background=[("active", CARD_HOVER)])
            except Exception:
                logging.debug("Could not apply custom scrollbar theme", exc_info=True)

        def show_details(self):
            if self.popup and self.popup.winfo_exists():
                self.popup.lift()
                return
            self._configure_scrollbar_style()
            self.popup = tk.Toplevel(self.root)
            self.popup.title("PAK Cricket · Match Center")
            self.popup.configure(bg=BG)
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            pw, ph = min(640, max(360, sw - 40)), min(620, max(360, sh - 80))
            self.popup.geometry(f"{pw}x{ph}")
            self.popup.minsize(min(480, pw), min(420, ph))
            self.popup.protocol("WM_DELETE_WINDOW", self.close_details)
            self.popup.bind("<Escape>", lambda _: self.close_details())

            self.header = tk.Frame(self.popup, bg=SURFACE, padx=20, pady=14, highlightbackground=BORDER, highlightthickness=1)
            self.header.pack(fill="x")
            top_row = tk.Frame(self.header, bg=SURFACE)
            top_row.pack(fill="x")
            tk.Label(top_row, text="Match Center", bg=SURFACE, fg=FG,
                     font=("Segoe UI", 16, "bold"), anchor="w").pack(side="left")
            self.auto_btn = _style_button(tk.Button(top_row, text="Auto-select top match",
                                                    command=lambda: self.select(None),
                                                    font=("Segoe UI", 8, "bold"), padx=10, pady=4),
                                          normal_bg=CARD, hover_bg=CARD_HOVER, fg=MUTED)
            self.fresh_label = tk.Label(self.header, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), anchor="w")
            self.fresh_label.pack(fill="x", pady=(3, 0))
            self.active_bar_banner = tk.Label(self.header, bg=SURFACE, fg=GREEN, font=("Segoe UI", 9, "bold"), anchor="w")
            self.active_bar_banner.pack(fill="x", pady=(4, 0))

            # Persistent feed switcher: always lets the user pick a team or International.
            self.feed_bar = tk.Frame(self.header, bg=SURFACE)
            self.feed_bar.pack(fill="x", pady=(10, 0))
            self.mode_team_btn = tk.Button(self.feed_bar, text="My Team",
                                           command=lambda: self.set_feed("team", self.preferences.get("team") or "Pakistan"),
                                           font=("Segoe UI", 9, "bold"), padx=11, pady=5)
            self.mode_team_btn.pack(side="left", padx=(0, 6))
            self.change_team_btn = _style_button(tk.Button(self.feed_bar, text="Change Team ▾",
                                                           command=self.toggle_team_picker,
                                                           font=("Segoe UI", 9, "bold"), padx=10, pady=5),
                                                 normal_bg=CARD, hover_bg=CARD_HOVER, fg=FG)
            self.change_team_btn.pack(side="left", padx=(0, 8))
            self.mode_intl_btn = tk.Button(self.feed_bar, text="International",
                                           command=lambda: self.set_feed("international"),
                                           font=("Segoe UI", 9, "bold"), padx=12, pady=5)
            self.mode_intl_btn.pack(side="left")

            self.team_picker_frame = tk.Frame(self.popup, bg=SURFACE, padx=18, pady=12,
                                              highlightbackground=BORDER, highlightthickness=1)

            self.filter_bar = tk.Frame(self.popup, bg=BG, padx=18, pady=8)
            self.filter_bar.pack(fill="x")

            body = tk.Frame(self.popup, bg=BG)
            body.pack(fill="both", expand=True)
            self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
            scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview, style="Dark.Vertical.TScrollbar")
            scrollbar.pack(side="right", fill="y")
            self.canvas.pack(side="left", fill="both", expand=True)
            self.canvas.configure(yscrollcommand=scrollbar.set)
            self.cards = tk.Frame(self.canvas, bg=BG)
            self.cards_window = self.canvas.create_window((0, 0), window=self.cards, anchor="nw")
            self.cards.bind("<Configure>", lambda _: self._sync_scrollregion())
            self.canvas.bind("<Configure>", self.layout_cards)
            self.popup.bind("<MouseWheel>", self._on_mousewheel)

            footer = tk.Frame(self.popup, bg=SURFACE, padx=20, pady=12, highlightbackground=BORDER, highlightthickness=1)
            footer.pack(fill="x")
            _style_button(tk.Button(footer, text="⟳ Refresh now", command=self.service.request_refresh,
                                    font=("Segoe UI", 9, "bold"), padx=12, pady=5)).pack(side="left")
            self.update_button = _style_button(tk.Button(footer, text="", command=self.open_update,
                                                         font=("Segoe UI", 9, "bold"), padx=12, pady=5),
                                               normal_bg=GREEN, hover_bg="#7ce0b5", fg=BG)
            _style_button(tk.Button(footer, text="Close", command=self.close_details,
                                    font=("Segoe UI", 9, "bold"), padx=14, pady=5)).pack(side="right")
            self.cards_revision = None
            self.render_details(self.service.snapshot())

        def _sync_scrollregion(self):
            try:
                if self.popup and self.popup.winfo_exists() and self.canvas.winfo_exists():
                    bbox = self.canvas.bbox("all")
                    if bbox:
                        self.canvas.configure(scrollregion=bbox)
            except tk.TclError:
                pass

        def _on_mousewheel(self, event):
            try:
                if not (self.popup and self.popup.winfo_exists() and self.canvas.winfo_exists()):
                    return
                bbox = self.canvas.bbox("all")
                if not bbox or (bbox[3] - bbox[1]) <= self.canvas.winfo_height():
                    return
                delta = event.delta
                if delta == 0:
                    return
                steps = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
                self.canvas.yview_scroll(steps, "units")
            except tk.TclError:
                pass

        def layout_cards(self, event):
            try:
                if not self.popup or not self.popup.winfo_exists() or not self.canvas.winfo_exists():
                    return
                self.canvas.itemconfigure(self.cards_window, width=event.width)
                for label in list(getattr(self, "wrapped_labels", [])):
                    try:
                        if label.winfo_exists():
                            label.configure(wraplength=max(250, event.width - 68))
                    except tk.TclError:
                        pass
            except tk.TclError:
                return

        def close_details(self):
            if self.popup:
                try:
                    self.popup.destroy()
                except tk.TclError:
                    pass
                self.popup = None
                self.header = None

        def _render_feed_controls(self):
            scope = self.preferences.get("scope")
            raw_team = self.preferences.get("team")
            team = raw_team if raw_team in TEAMS else "Pakistan"
            self.mode_team_btn.configure(text=f"My Team: {team}" if scope == "team" else f"Team: {team}")
            if scope == "team":
                _style_button(self.mode_team_btn, normal_bg=GREEN, hover_bg="#7ce0b5", fg=BG)
            else:
                _style_button(self.mode_team_btn, normal_bg=CARD, hover_bg=CARD_HOVER, fg=FG)
            if scope == "international":
                _style_button(self.mode_intl_btn, normal_bg=GREEN, hover_bg="#7ce0b5", fg=BG)
            else:
                _style_button(self.mode_intl_btn, normal_bg=CARD, hover_bg=CARD_HOVER, fg=FG)

            for child in self.team_picker_frame.winfo_children():
                child.destroy()
            if not self.team_picker_open:
                self.team_picker_frame.pack_forget()
                self.change_team_btn.configure(text="Change Team ▾")
                return

            self.change_team_btn.configure(text="Change Team ▴")
            if self.header and self.header.winfo_exists():
                self.team_picker_frame.pack(fill="x", after=self.header)
            else:
                self.team_picker_frame.pack(fill="x")
            heading = "Choose your team or click International above:" if scope is None else "Select a team to follow (saved automatically):"
            tk.Label(self.team_picker_frame, text=heading, bg=SURFACE, fg=FG,
                     font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
            grid = tk.Frame(self.team_picker_frame, bg=SURFACE)
            grid.pack(fill="x")
            cols = 3
            for c in range(cols):
                grid.columnconfigure(c, weight=1)
            for idx, name in enumerate(TEAM_NAMES):
                is_current = scope == "team" and team == name
                btn = tk.Button(grid, text=team_option_label(name),
                                command=lambda t=name: self.set_feed("team", t),
                                font=("Segoe UI", 8, "bold"), padx=8, pady=5)
                if is_current:
                    _style_button(btn, normal_bg=GREEN, hover_bg="#7ce0b5", fg=BG)
                else:
                    _style_button(btn, normal_bg=CARD, hover_bg=CARD_HOVER, fg=FG)
                btn.grid(row=idx // cols, column=idx % cols, sticky="ew", padx=3, pady=3)

        def _render_filter_pills(self, matches):
            for child in self.filter_bar.winfo_children():
                child.destroy()
            scope = self.preferences.get("scope") or "team"
            raw_team = self.preferences.get("team")
            team = raw_team if raw_team in TEAMS else "Pakistan"
            available = categories_for_scope(scope, team)
            if self.category not in available:
                self.category = "All"
            counts = {cat: sum(1 for m in matches if matches_category(m, cat, scope)) for cat in available}
            max_width = max(420, (self.popup.winfo_width() or 620) - 48)
            row, col, used_width = 0, 0, 0
            for cat in available:
                if cat not in {"All", "International", team} and counts[cat] == 0 and self.category != cat:
                    continue
                active = self.category == cat
                text = f"{cat} ({counts[cat]})" if counts[cat] else cat
                pill = tk.Button(self.filter_bar, text=text, command=lambda c=cat: self.set_category(c),
                                 font=("Segoe UI", 8, "bold"), padx=10, pady=4)
                if active:
                    _style_button(pill, normal_bg=GREEN, hover_bg="#7ce0b5", fg=BG)
                else:
                    _style_button(pill, normal_bg=CARD, hover_bg=CARD_HOVER, fg=FG if counts[cat] else MUTED)
                est_w = max(56, len(text) * 7 + 26)
                if col > 0 and used_width + est_w > max_width:
                    row += 1
                    col, used_width = 0, 0
                pill.grid(row=row, column=col, sticky="w", padx=(0, 6), pady=2)
                col += 1
                used_width += est_w + 6

        def render_details(self, snapshot):
            if not self.popup or not self.popup.winfo_exists():
                return
            self.fresh_label.configure(text=freshness(snapshot), fg=COLORS["scheduled"] if snapshot["errors"] else MUTED)
            active_match = chosen_match(snapshot, self.preferences["selected"])
            pinned_exact = bool(active_match and self.preferences["selected"] == active_match["id"])
            if active_match:
                mode = "Pinned to live strip" if pinned_exact else "Showing on live strip (Auto)"
                self.active_bar_banner.configure(text=f"▸ {mode}: {active_match['teams']} ({state_label(active_match)})")
            else:
                self.active_bar_banner.configure(text="▸ Select any match below to display it on the floating live strip")
            if pinned_exact:
                self.auto_btn.pack(side="right")
            else:
                self.auto_btn.pack_forget()
            if self.update and self.update.get("update_available"):
                self.update_button.configure(text=f"Update to {self.update['latest_version']}", state="disabled" if self.update_busy else "normal")
                self.update_button.pack(side="left", padx=10)
            if self.cards_revision == snapshot["revision"]:
                return
            self.cards_revision = snapshot["revision"]
            position = self.canvas.yview()[0]
            self._render_feed_controls()
            self._render_filter_pills(snapshot["matches"])
            for child in self.cards.winfo_children():
                child.destroy()
            self.wrapped_labels = []
            scope = self.preferences.get("scope") or "team"
            filtered = [m for m in snapshot["matches"] if matches_category(m, self.category, scope)]
            if not filtered:
                if snapshot["errors"] and not snapshot["matches"]:
                    message = "Unable to fetch scores. Retrying automatically."
                elif snapshot["updated_at"] is None:
                    message = "Fetching scores…"
                elif snapshot["matches"]:
                    message = f"No {self.category} matches right now. Switch to 'All' to view other fixtures."
                else:
                    label_name = feed_title(scope, self.preferences.get("team"))
                    message = f"No {label_name} matches right now. Try switching to International or another team above."
                empty_lbl = tk.Label(self.cards, text=message, bg=BG, fg=MUTED, font=("Segoe UI", 10),
                                     wraplength=480, justify="center", pady=34)
                empty_lbl.pack()
                self.wrapped_labels.append(empty_lbl)
            for match in filtered:
                is_on_bar = bool(active_match and match["id"] == active_match["id"])
                is_pinned = self.preferences["selected"] == match["id"]
                card_bg = CARD_ACTIVE if is_on_bar else CARD
                border_color = GREEN if is_on_bar else BORDER
                card = tk.Frame(self.cards, bg=card_bg, padx=16, pady=12,
                                highlightbackground=border_color, highlightthickness=2 if is_on_bar else 1)
                card.pack(fill="x", padx=18, pady=(0, 10))

                # Top row: pack right-side badge before series text so long titles don't clip the badge.
                top = tk.Frame(card, bg=card_bg)
                top.pack(fill="x")
                s_label = state_label(match)
                s_color = COLORS.get(match["state"], MUTED)
                tk.Label(top, text=f"● {s_label}", bg=card_bg, fg=s_color,
                         font=("Segoe UI", 9, "bold")).pack(side="left")
                if is_on_bar:
                    badge_text = "📌 ON LIVE STRIP" if is_pinned else "● ON LIVE STRIP (AUTO)"
                    tk.Label(top, text=badge_text, bg=GREEN if is_pinned else "#243b55",
                             fg=BG if is_pinned else "#7ec8f8",
                             font=("Segoe UI", 8, "bold"), padx=7, pady=2).pack(side="right")
                if series_line(match):
                    tk.Label(top, text=f"  ·  {series_line(match)}", bg=card_bg, fg=MUTED,
                             font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True)

                def label(text, color=FG, size=10, bold=False, pad=(3, 0)):
                    item = tk.Label(card, text=text, bg=card_bg, fg=color, anchor="w", justify="left",
                                    font=("Segoe UI", size, "bold" if bold else "normal"), wraplength=500, cursor="hand2")
                    item.pack(fill="x", pady=pad)
                    item.bind("<ButtonRelease-1>", lambda _, ident=match["id"]: self.select(ident, toggle=False))
                    self.wrapped_labels.append(item)

                label(match["teams"], FG, 13, True, pad=(6, 2))
                for row in match.get("scores", []):
                    decl = "d" if row.get("declared") else ""
                    score = str(row["runs"]) + (f"/{row['wickets']}" if row['wickets'] is not None else "") + decl
                    overs_text = f"  ({row['overs']} ov)" if row.get("overs") else ""
                    label(f"{row['team']}   {score}{overs_text}", GREEN, 13, True, pad=(2, 0))
                if not match.get("scores"):
                    label(start_label(match), MUTED, 10, False, pad=(2, 0))
                label(match.get("status") or "Status unavailable", MUTED, 9, False, pad=(4, 2))

                controls = tk.Frame(card, bg=card_bg)
                controls.pack(fill="x", pady=(8, 0))
                if is_pinned:
                    select_btn = _style_button(tk.Button(controls, text="✓ Showing on Live Strip (Click to Auto)",
                                                         command=lambda ident=match["id"]: self.select(ident, toggle=True),
                                                         font=("Segoe UI", 9, "bold"), padx=11, pady=4),
                                               normal_bg=GREEN, hover_bg="#7ce0b5", fg=BG)
                elif is_on_bar:
                    select_btn = _style_button(tk.Button(controls, text="📌 Pin This Match to Live Strip",
                                                         command=lambda ident=match["id"]: self.select(ident, toggle=False),
                                                         font=("Segoe UI", 9, "bold"), padx=11, pady=4),
                                               normal_bg="#243b55", hover_bg="#2f4d6e", fg="#7ec8f8")
                else:
                    select_btn = _style_button(tk.Button(controls, text="Show on Live Strip",
                                                         command=lambda ident=match["id"]: self.select(ident, toggle=False),
                                                         font=("Segoe UI", 9, "bold"), padx=11, pady=4),
                                               normal_bg=SURFACE, hover_bg=CARD_HOVER, fg=FG)
                select_btn.pack(side="left")
                _style_button(tk.Button(controls, text="Open on Cricbuzz ↗",
                                        command=lambda m=match: self.open_source(m),
                                        font=("Segoe UI", 9), padx=10, pady=4),
                              normal_bg=SURFACE, hover_bg=CARD_HOVER, fg=MUTED).pack(side="right")
                card.bind("<ButtonRelease-1>", lambda _, ident=match["id"]: self.select(ident, toggle=False))
            self.cards.update_idletasks()
            if self.canvas.bbox("all"):
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.canvas.yview_moveto(position)

        def _dialog_parent(self):
            if self.popup and self.popup.winfo_exists():
                return self.popup
            return self.root

        def open_update(self):
            from tkinter import messagebox
            if self.update_busy or self.update_dialog_open or self.closing:
                return
            self.update_dialog_open = True
            try:
                if not self.update or not self.update.get("update_available"):
                    self.request_manual_update_check()
                    messagebox.showinfo("PAK Cricket", "Checking for updates. You will be notified once the check completes.", parent=self._dialog_parent())
                    return
                if not getattr(sys, "frozen", False):
                    webbrowser.open(self.update["release_url"])
                    return
                confirmed = messagebox.askyesno(
                    "Update available",
                    f"Download {self.update['latest_version']} and restart PAK Cricket?\n\nYour settings will be preserved and the current executable kept as a backup.",
                    parent=self._dialog_parent(),
                )
            finally:
                self.update_dialog_open = False
            if self.closing or not confirmed:
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
            self.update_dialog_open = True
            try:
                if prepared["save_as"]:
                    destination = filedialog.asksaveasfilename(title="Choose a writable folder for the updated app", initialfile="PakCricket.exe", defaultextension=".exe", filetypes=[("Windows executable", "*.exe")], parent=self._dialog_parent())
                    if self.closing:
                        discard_stage(prepared["stage"])
                        return
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
                if not self.closing:
                    messagebox.showerror("Update failed", f"{exc}\n\nThe running app has not been replaced.", parent=self._dialog_parent())
            finally:
                self.update_dialog_open = False

        def tick(self):
            try:
                self.tick_content()
            except Exception:
                logging.exception("Score bar refresh failed")
            finally:
                if not self.closing:
                    try:
                        self.root.after(1000, self.tick)
                    except tk.TclError:
                        pass

        def tick_content(self):
            if self.closing:
                return
            while not self.commands.empty():
                command = self.commands.get()
                if isinstance(command, tuple):
                    kind, value = command
                    if kind == "update":
                        manual = self.manual_update_check
                        self.manual_update_check = False
                        if not value.get("error"):
                            self.update = value
                        elif manual and not self.closing and not self.update_dialog_open:
                            from tkinter import messagebox
                            messagebox.showwarning("Update check failed", f"Could not check GitHub for updates right now.\n\n{value['error']}", parent=self._dialog_parent())
                        if self.update and self.update.get("update_available") and self.notified_version != self.update["latest_version"]:
                            self.notified_version = self.update["latest_version"]
                            self.preferences["notified_version"] = self.notified_version
                            self.save()
                            if self.tray_icon and self.tray_ready.is_set():
                                try:
                                    self.tray_icon.notify(f"{self.notified_version} is available. Click Update on the score bar.", "PAK Cricket update")
                                except Exception:
                                    logging.exception("Update notification failed")
                        elif manual and not value.get("error") and not value.get("update_available") and not self.closing and not self.update_dialog_open:
                            from tkinter import messagebox
                            messagebox.showinfo("Up to date", f"You are already running the latest version ({CURRENT_VERSION}).", parent=self._dialog_parent())
                    elif kind == "progress":
                        self.update_progress = value
                    elif kind == "prepared_update":
                        self.finish_update(value)
                        if self.closing:
                            return
                    elif kind == "update_error":
                        from tkinter import messagebox
                        self.update_busy, self.update_progress = False, None
                        if not self.closing:
                            messagebox.showerror("Update failed", f"{value}\n\nThe running app was not changed. Try again or download from the release page.", parent=self._dialog_parent())
                elif command == "quit":
                    self.quit()
                    return
                else:
                    {"details": self.show_details, "refresh": self.service.request_refresh,
                     "toggle": self.toggle_bar, "topmost": self.toggle_topmost,
                     "check_update": self.request_manual_update_check, "install_update": self.open_update}[command]()
            self._render_bar(self.service.snapshot())

        def _render_bar(self, snapshot):
            if self.closing:
                return
            if self.update and self.update.get("update_available"):
                self.update_badge.configure(text=f"Updating {self.update_progress}%" if self.update_busy else "Update available", state="disabled" if self.update_busy else "normal")
                self.update_badge.pack(side="right", padx=3, pady=6)
            else:
                self.update_badge.pack_forget()
            total = len(snapshot["matches"])
            self.details.configure(text=f"Matches ({total}) ▾" if total else "Matches ▾")
            if total > 1:
                self.next_btn.pack(side="right", padx=(1, 2), pady=6)
                self.prev_btn.pack(side="right", padx=(2, 1), pady=6)
            else:
                self.next_btn.pack_forget()
                self.prev_btn.pack_forget()
            match = chosen_match(snapshot, self.preferences["selected"])
            state = match["state"] if match else snapshot["state"]
            delayed = bool(snapshot["errors"])
            status = "DELAYED" if delayed else "FETCHING" if snapshot["updated_at"] is None else state_label(match, snapshot["state"])
            pinned = bool(match and self.preferences["selected"] == match["id"])
            prefix = "📌" if pinned else "●"
            self.status.configure(text=f"{prefix} {status}", fg=COLORS["scheduled"] if delayed else COLORS.get(state, MUTED))
            text = compact_text(match) if snapshot["updated_at"] else freshness(snapshot)
            # Fit the available label width, caching measurement when text/size/width are unchanged.
            available = max(80, self.label.winfo_width() - 8)
            cache_key = (text, self.preferences["text_size"], available)
            if self._text_fit_cache and self._text_fit_cache[0] == cache_key:
                fitted = self._text_fit_cache[1]
            else:
                from tkinter import font
                face = self._bar_font or font.Font(font=self.label.cget("font"))
                shown = text
                while len(shown) > 1 and face.measure(shown + ("…" if shown != text else "")) > available:
                    shown = shown[:-1]
                fitted = shown + ("…" if shown != text else "")
                self._text_fit_cache = (cache_key, fitted)
            self.label.configure(text=fitted)
            if self.tray_icon and self.tray_ready.is_set():
                fresh_text = freshness(snapshot)
                title = (f"{status} · {text}" + (f" · {fresh_text}" if snapshot["updated_at"] else ""))[:127]
                if self.tray_icon.title != title:
                    self.tray_icon.title = title
                color = COLORS["scheduled"] if delayed else COLORS.get(state, MUTED)
                if getattr(self, "tray_color", None) != color:
                    self.tray_icon.icon = self.icon_image(color)
                    self.tray_color = color
            self.render_details(snapshot)

        def quit(self):
            if self.closing:
                return
            self.closing = True
            self.update_stop.set()
            self.update_request.set()
            self.service.stop()
            if self.tray_icon:
                try:
                    self.tray_icon.visible = False
                    self.tray_icon.stop()
                except Exception:
                    pass
                if self.tray_thread and self.tray_thread.is_alive():
                    self.tray_thread.join(timeout=1.0)
            try:
                self.root.destroy()
            except tk.TclError:
                pass

        def run(self):
            self.root.mainloop()

    def main():
        CricketApp().run()

if __name__ == "__main__":
    from app_logging import configure_logging
    configure_logging()
    main()
