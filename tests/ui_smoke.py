"""Desktop-only Tk smoke check: run explicitly, separate from headless tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy
from unittest.mock import patch
from main import CricketApp
from scores import ScoreService
from settings import DEFAULTS

service = ScoreService(lambda: {"live": [], "recent": [], "upcoming": [], "errors": {}})
match = {"id": "123", "teams": "Pakistan vs New Zealand", "state": "live", "series": "Pakistan tour of New Zealand",
         "status": "Pakistan need 17 runs from 10 balls", "scores": [{"team": "PAK", "runs": 156, "wickets": 4, "overs": "18.2"}],
         "score": "PAK 156/4 (18.2 ov)", "href": "/live-cricket-scores/123/pak-vs-nz/", "start_time": None}
with patch.object(service, "start"), patch.object(CricketApp, "check_update"), patch("main.save_settings"):
    app = CricketApp(service=service, preferences=dict(DEFAULTS), tray=False)
    app.root.withdraw()
    try:
        app.show_details()
        app.popup.withdraw()
        app.root.update()
        # A hidden user preference must win over the visibility watchdog.
        app.preferences["hidden"] = True
        app.keep_visible()
        assert app.root.state() == "withdrawn"
        app.preferences["hidden"] = False
        app.keep_visible()
        app.root.update()
        assert app.root.winfo_viewable()
        app.root.withdraw()
        # Update availability is visible without opening details.
        app.commands.put(("update", {"update_available": True, "latest_version": "v9.0.0", "error": ""}))
        app.tick_content()
        app.root.update()
        assert app.update_badge.winfo_manager() == "pack"
        # An exception in a refresh must not stop scheduling the next refresh.
        with patch.object(app, "tick_content", side_effect=RuntimeError("simulated UI failure")), patch.object(app.root, "after") as scheduled:
            app.tick()
            scheduled.assert_called_once_with(1000, app.tick)
        assert app.popup.resizable() == (1, 1)
        assert app.team_picker_open is True
        app.set_feed("international")
        assert app.preferences["scope"] == "international"
        assert service.scope == "international"
        assert app.team_picker_open is False
        app.toggle_team_picker()
        assert app.team_picker_open is True
        assert app.team_picker_frame.winfo_manager() == "pack"
        app.set_feed("team", "India")
        assert app.preferences["scope"] == "team"
        assert app.preferences["team"] == "India"
        assert service.team == "India"
        assert app.team_picker_open is False
        assert any("India" in btn.cget("text") for btn in app.filter_bar.winfo_children())
        app.set_feed("team", "Pakistan")
        assert any("Pakistan" in btn.cget("text") for btn in app.filter_bar.winfo_children())
        service.data.update(matches=[match], updated_at=1, revision=1)
        app.render_details(service.snapshot())
        assert len(app.cards.winfo_children()) == 1
        second = dict(match, id="124", teams="Lahore Qalandars vs Karachi Kings",
                      series="Pakistan Super League 2026", competition="PSL",
                      scores=[{"team": "LQ", "runs": 188, "wickets": 5, "overs": "20"}])
        service.data.update(matches=[dict(match, competition="International"), second], revision=2)
        app.render_details(service.snapshot())
        assert len(app.cards.winfo_children()) == 2
        # Selecting a match in Match Center immediately updates the live strip.
        app.select("124", toggle=False)
        assert app.preferences["selected"] == "124"
        assert "LQ 188/5" in app.label.cget("text")
        assert app.status.cget("text").startswith("📌")
        # Category filter tabs narrow the Match Center list while preserving the selected strip match.
        app.set_category("PSL")
        assert len(app.cards.winfo_children()) == 1
        assert app.preferences["selected"] == "124"
        app.set_category("All")
        assert len(app.cards.winfo_children()) == 2
        app.cycle_match(1)
        assert app.preferences["selected"] == "123"
        service.data.update(matches=[], revision=3)
        app.render_details(service.snapshot())
        assert len(app.cards.winfo_children()) == 1
        app.select("123", toggle=False)
        assert app.preferences["selected"] == "123"
        app.resize_text(1)
        assert app.preferences["text_size"] == 11
        app.toggle_topmost()
        assert app.preferences["topmost"] is False
        # Calling drag_move before drag_start must be a safe no-op.
        class Event:
            x_root = 10
            y_root = 10
        app.drag_move(Event())
        app.close_details()
        assert app.popup is None
        app.show_details()
        app.popup.withdraw()
        app.root.update()
        print("Windows UI smoke check passed: visibility recovery, intentional hiding, update badge, refresh recovery, and popup controls")
    finally:
        app.quit()
        app.quit()  # Idempotent quit must not raise on repeated invocation.
