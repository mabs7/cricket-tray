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
        assert app.popup.resizable() == (1, 1)
        service.data.update(matches=[match], updated_at=1, revision=1)
        app.render_details(service.snapshot())
        assert len(app.cards.winfo_children()) == 1
        service.data.update(matches=[match, dict(match, id="124")], revision=2)
        app.render_details(service.snapshot())
        assert len(app.cards.winfo_children()) == 2
        service.data.update(matches=[], revision=3)
        app.render_details(service.snapshot())
        assert len(app.cards.winfo_children()) == 1
        app.select("123")
        assert app.preferences["selected"] == "123"
        app.resize_text(1)
        assert app.preferences["text_size"] == 11
        app.toggle_topmost()
        assert app.preferences["topmost"] is False
        app.close_details()
        assert app.popup is None
        app.show_details()
        app.popup.withdraw()
        app.root.update()
        print("Windows UI smoke check passed: startup, dynamic cards, resizing, pinning, preferences, popup lifecycle")
    finally:
        app.quit()
