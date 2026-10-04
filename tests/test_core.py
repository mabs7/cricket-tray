import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import requests
from scraper import parse_page, ScrapeError, get_all_matches, match_url
from filter import get_match_state, is_pakistan_match
from scores import ScoreService
from settings import load_settings, save_settings, DEFAULTS
from updater import version_tuple

FIXTURES = Path(__file__).parent / "fixtures"

def record(ident=123, state="In Progress", status="In Progress", start=1791201600000):
    return {"matchInfo": {"matchId": ident, "team1": {"teamName": "Pakistan", "teamSName": "PAK"},
                         "team2": {"teamName": "New Zealand", "teamSName": "NZ"}, "state": state,
                         "status": status, "startDate": start, "seriesName": "Pakistan tour of New Zealand"},
            "matchScore": {"team1Score": {"inngs1": {"runs": 156, "wickets": 4, "overs": 18.2}},
                           "team2Score": {"inngs1": {"runs": 172, "wickets": 7, "overs": 19.6}}}}

def embedded(records, flight=False):
    data = json.dumps({"matches": records})
    if flight:
        # Next.js may split its stream in the middle of a match record.
        mid = len(data) // 2
        return "".join("<script>self.__next_f.push(" + json.dumps([1, chunk]) + ")</script>" for chunk in (data[:mid], data[mid:]))
    return '<script type="application/json">' + data + '</script>'

class ParserTests(unittest.TestCase):
    def test_observed_cricbuzz_flight_records(self):
        matches = parse_page((FIXTURES / "observed-flight.html").read_text(encoding="utf-8"))
        state, selected = get_match_state({"live": matches})
        self.assertEqual(state, "completed")
        self.assertEqual(selected[0]["id"], "171070")
        self.assertIn("PAK 192/6 (20 ov)", selected[0]["score"])
        self.assertEqual(selected[0]["parser"], "embedded")

    def test_split_flight_normalizes_overs(self):
        match = parse_page(embedded([record()], True))[0]
        self.assertEqual(match["scores"][1]["overs"], "20")
        self.assertEqual(match["state"], "live")

    def test_completed_and_interrupted(self):
        for status, expected in [("Rain delay", "live"), ("Stumps", "live"), ("Match tied", "completed"), ("Match abandoned", "completed"), ("Pakistan won by 5 runs", "completed")]:
            with self.subTest(status=status):
                self.assertEqual(parse_page(embedded([record(status=status)]))[0]["state"], expected)

    def test_scoped_html_excludes_other_matches(self):
        matches = parse_page((FIXTURES / "cards.html").read_text())
        pak = next(m for m in matches if m["id"] == "123")
        self.assertEqual(pak["teams"], "Pakistan vs New Zealand")
        self.assertEqual(pak["status"], "Rain delay")
        self.assertEqual([r["team"] for r in pak["scores"]], ["PAK", "NZ"])
        self.assertNotIn("999", pak["score"])
        self.assertNotIn("ENG", pak["score"])

    def test_jsonld_date_and_future_not_today(self):
        matches = parse_page((FIXTURES / "scheduled.html").read_text(), "upcoming")
        state, _ = get_match_state({"upcoming": matches}, datetime(2026, 10, 4, tzinfo=timezone.utc))
        self.assertEqual(state, "scheduled")

    def test_invalid_score_is_failure(self):
        value = record()
        value["matchScore"]["team1Score"]["inngs1"]["wickets"] = 12
        with self.assertRaises(ScrapeError):
            parse_page(embedded([value]))

    def test_blocked_and_explicit_empty(self):
        with self.assertRaises(ScrapeError):
            parse_page("<html>Verify you are human</html>")
        self.assertEqual(parse_page("<p>No live matches</p>"), [])

    def test_deduplicate_by_id_not_teams(self):
        matches = parse_page(embedded([record(1), record(2)]))
        self.assertEqual(len(get_match_state({"live": matches, "recent": matches})[1]), 2)

    def test_filter_excludes_champions_and_generic_kings(self):
        self.assertFalse(is_pakistan_match({"teams": "Pakistan Champions vs England Champions"}))
        self.assertFalse(is_pakistan_match({"teams": "Chennai Super Kings vs Punjab Kings"}))
        self.assertTrue(is_pakistan_match({"teams": "Pakistan Women vs India Women"}))
        self.assertTrue(is_pakistan_match({"teams": "Lahore Qalandars vs Karachi Kings"}))

    def test_fetch_error_is_explicit(self):
        with patch("scraper.get_live_matches", side_effect=requests.Timeout("timeout")), patch("scraper.get_recent_matches", return_value=[]), patch("scraper.get_upcoming_matches", return_value=[]):
            self.assertIn("live", get_all_matches()["errors"])

    def test_source_link_stays_on_cricbuzz(self):
        self.assertEqual(match_url({"href": "https://evil.example/live-cricket-scores/123/foo"}), "https://www.cricbuzz.com/live-cricket-scores/123/foo")
        self.assertEqual(match_url({"href": "javascript:alert(1)"}), "")

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.matches = parse_page(embedded([record()]))
        self.result = {"live": self.matches, "recent": [], "upcoming": [], "errors": {}}
        self.service = ScoreService(lambda: self.result)

    def test_failure_keeps_last_score_and_timestamp(self):
        self.service.refresh()
        before = self.service.snapshot()
        self.result = {"errors": {"upcoming": "timeout"}, "live": []}
        self.service.refresh()
        after = self.service.snapshot()
        self.assertEqual(after["matches"], before["matches"])
        self.assertEqual(after["updated_at"], before["updated_at"])
        self.assertTrue(after["errors"])

    def test_disappearing_live_score_is_stale(self):
        self.service.refresh()
        self.result = copy.deepcopy(self.result)
        self.result["live"][0].update(score="", scores=[])
        self.service.refresh()
        self.assertTrue(self.service.snapshot()["errors"])
        self.assertTrue(self.service.snapshot()["matches"][0]["score"])

    def test_recovery_and_snapshot_isolation(self):
        self.service.refresh()
        snap = self.service.snapshot()
        snap["matches"].clear()
        self.assertTrue(self.service.snapshot()["matches"])
        self.result = {"live": [], "recent": [], "upcoming": [], "errors": {}}
        self.service.refresh()
        self.assertEqual(self.service.snapshot()["matches"], [])

    def test_fetch_exception_does_not_stop_refresh(self):
        def fail():
            raise RuntimeError("broken parser")
        self.service.fetcher = fail
        self.service.refresh()
        self.assertFalse(self.service.snapshot()["refreshing"])
        self.assertTrue(self.service.snapshot()["errors"])

class PreferenceTests(unittest.TestCase):
    def test_roundtrip_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            values = dict(DEFAULTS, position=[10, 20], hidden=True, text_size=14)
            save_settings(values, path)
            self.assertEqual(load_settings(path), values)
            path.write_text("broken")
            self.assertEqual(load_settings(path), DEFAULTS)
            path.write_text("[]")
            self.assertEqual(load_settings(path), DEFAULTS)

    def test_numeric_version_order(self):
        self.assertGreater(version_tuple("v2.10.0"), version_tuple("v2.9.0"))
        self.assertIsNone(version_tuple("v2.7.0-beta"))

if __name__ == "__main__":
    unittest.main()
