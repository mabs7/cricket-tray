import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import requests
from scraper import parse_page, ScrapeError, get_all_matches, match_url
from filter import categories_for_scope, competition, filter_covered_matches, get_match_state, is_pakistan_match, is_team_match, matches_category
from main import state_label, series_line
from scores import ScoreService, refresh_interval
from settings import load_settings, save_settings, DEFAULTS
from updater import version_tuple

FIXTURES = Path(__file__).parent / "fixtures"

def record(ident=123, state="In Progress", status="In Progress", start=1791201600000,
           series="Pakistan tour of New Zealand", team1=("Pakistan", "PAK"), team2=("New Zealand", "NZ"), match_type=""):
    info = {"matchId": ident, "team1": {"teamName": team1[0], "teamSName": team1[1]},
            "team2": {"teamName": team2[0], "teamSName": team2[1]}, "state": state,
            "status": status, "startDate": start, "seriesName": series}
    if match_type:
        info["matchType"] = match_type
    return {"matchInfo": info,
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
        cases = [("In Progress", "In Progress", "live", "", "LIVE"),
                 ("Stumps", "Day 3: Stumps - Sri Lanka trail by 30 runs", "paused", "Stumps", "STUMPS"),
                 ("Lunch", "Day 2: Lunch Break", "paused", "Lunch", "LUNCH"),
                 ("Tea", "Day 1: Tea Break", "paused", "Tea", "TEA"),
                 ("Innings Break", "Innings Break", "paused", "Innings Break", "INNINGS BREAK"),
                 ("Rain", "Rain delay", "paused", "Rain Delay", "RAIN DELAY"),
                 ("Complete", "Match tied", "completed", "", "COMPLETED"),
                 ("Complete", "Match abandoned", "completed", "", "COMPLETED"),
                 ("Complete", "Pakistan won by 5 runs", "completed", "", "COMPLETED")]
        for raw_state, status, expected_state, expected_phase, expected_label in cases:
            with self.subTest(state=raw_state, status=status):
                match = parse_page(embedded([record(state=raw_state, status=status)]))[0]
                self.assertEqual(match["state"], expected_state)
                self.assertEqual(match["phase"], expected_phase)
                self.assertEqual(state_label(match), expected_label)
                self.assertEqual(match["is_live"], expected_state == "live")

    def test_observed_typed_stumps_flight_and_categories(self):
        matches = parse_page((FIXTURES / "typed-stumps-flight.html").read_text(encoding="utf-8"))
        by_id = {m["id"]: m for m in matches}
        pak_test = by_id["170703"]
        self.assertEqual(pak_test["state"], "paused")
        self.assertEqual(pak_test["phase"], "Stumps")
        self.assertFalse(pak_test["is_live"])
        self.assertEqual(pak_test["category"], "international")
        self.assertEqual(state_label(pak_test), "STUMPS")
        state, selected = get_match_state({"live": matches})
        self.assertEqual(state, "paused")
        self.assertEqual(selected[0]["id"], "170703")
        # Sheffield Shield, Abu Dhabi T10, and WBBL are excluded; NZ vs IND is included.
        selected_ids = {m["id"] for m in selected}
        self.assertIn("170703", selected_ids)
        for m in selected:
            self.assertNotIn("Sheffield Shield", m["series"])
            self.assertNotIn("Abu Dhabi T10", m["series"])
            self.assertNotIn("WBBL", m["series"])
            self.assertNotIn("Womens Big Bash", m["series"])

    def test_scoped_html_excludes_other_matches(self):
        matches = parse_page((FIXTURES / "cards.html").read_text())
        pak = next(m for m in matches if m["id"] == "123")
        self.assertEqual(pak["teams"], "Pakistan vs New Zealand")
        self.assertEqual(pak["status"], "Rain delay")
        self.assertEqual(pak["state"], "paused")
        self.assertEqual(pak["phase"], "Rain Delay")
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

    def test_expanded_coverage_includes_internationals_and_six_major_leagues_only(self):
        included = [
            ({"teams": "Pakistan vs Sri Lanka", "series": "Sri Lanka tour of Pakistan, 2026", "category": "international"}, "Pakistan"),
            ({"teams": "India vs Australia", "series": "Border-Gavaskar Trophy 2026", "category": "international"}, "International"),
            ({"teams": "England vs South Africa", "series": "South Africa tour of England, 2026"}, "International"),
            ({"teams": "Chennai Super Kings vs Mumbai Indians", "series": "Indian Premier League 2026", "category": "league"}, "IPL"),
            ({"teams": "Lahore Qalandars vs Karachi Kings", "series": "Pakistan Super League 2026", "category": "league"}, "PSL"),
            ({"teams": "Comilla Victorians vs Rangpur Riders", "series": "Bangladesh Premier League 2026", "category": "league"}, "BPL"),
            ({"teams": "Sydney Sixers vs Perth Scorchers", "series": "Big Bash League 2026-27", "category": "league"}, "BBL"),
            ({"teams": "Sunrisers Eastern Cape vs Paarl Royals", "series": "SA20 2026", "category": "league"}, "SA20"),
            ({"teams": "Oval Invincibles vs Southern Brave", "series": "The Hundred Mens Competition 2026", "category": "league"}, "The Hundred"),
        ]
        for match, expected in included:
            with self.subTest(series=match["series"]):
                self.assertEqual(competition(match), expected)
        psl_match = {"teams": "Lahore Qalandars vs Karachi Kings", "series": "Pakistan Super League 2026", "competition": "PSL"}
        self.assertTrue(matches_category(psl_match, "PSL"))
        self.assertTrue(matches_category(psl_match, "Pakistan"))
        self.assertFalse(matches_category(psl_match, "International"))

        excluded = [
            {"teams": "New South Wales vs South Australia", "series": "Sheffield Shield 2026-27", "category": "domestic"},
            {"teams": "Royal Desert Champions vs UAE Bulls", "series": "Abu Dhabi T10 League 2026", "category": "league"},
            {"teams": "Biratnagar Kings vs Pokhara Avengers", "series": "Nepal Premier League 2026", "category": "league"},
            {"teams": "Titans vs Warriors", "series": "CSA T20 Challenge 2026", "category": "league"},
            {"teams": "Sydney Thunder Women vs Perth Scorchers Women", "series": "Womens Big Bash League 2026", "category": "women"},
            {"teams": "Oval Invincibles Women vs Southern Brave Women", "series": "The Hundred Womens Competition 2026", "category": "women"},
            {"teams": "Mumbai Indians Women vs Delhi Capitals Women", "series": "Womens Premier League 2026", "category": "women"},
            {"teams": "West Indies A vs England Lions", "series": "England Lions tour of West Indies, 2026", "category": "domestic"},
            {"teams": "South Africa Champions vs West Indies Champions", "series": "World Championship of Legends 2026"},
        ]
        for match in excluded:
            with self.subTest(series=match["series"]):
                self.assertEqual(competition(match), "")
                self.assertEqual(filter_covered_matches([match]), [])

    def test_priority_orders_pakistan_then_international_then_leagues(self):
        ipl = parse_page(embedded([record(1, series="Indian Premier League 2026", team1=("CSK", "CSK"), team2=("MI", "MI"), match_type="League")]))[0]
        intl = parse_page(embedded([record(2, series="India tour of Australia", team1=("Australia", "AUS"), team2=("India", "IND"), match_type="International")]))[0]
        pak = parse_page(embedded([record(3, series="Sri Lanka tour of Pakistan", team1=("Pakistan", "PAK"), team2=("Sri Lanka", "SL"), match_type="International")]))[0]
        state, ordered = get_match_state({"live": [ipl, intl, pak]})
        self.assertEqual(state, "live")
        self.assertEqual([m["id"] for m in ordered], ["3", "2", "1"])
        self.assertEqual(series_line(ordered[0]), "Pakistan · Sri Lanka tour of Pakistan")

    def test_live_match_takes_precedence_over_stumps_match(self):
        stumps = parse_page(embedded([record(1, state="Stumps", status="Day 2: Stumps", match_type="International")]))[0]
        live_ipl = parse_page(embedded([record(2, state="In Progress", status="In Progress", series="Indian Premier League 2026",
                                               team1=("CSK", "CSK"), team2=("MI", "MI"), match_type="League")]))[0]
        state, ordered = get_match_state({"live": [stumps, live_ipl]})
        self.assertEqual(state, "live")
        self.assertEqual([m["id"] for m in ordered], ["2", "1"])

    def test_scope_filtering_and_categories(self):
        pak = parse_page(embedded([record(1, series="Sri Lanka tour of Pakistan", team1=("Pakistan", "PAK"), team2=("Sri Lanka", "SL"), match_type="International")]))[0]
        psl = parse_page(embedded([record(2, series="Pakistan Super League 2026", team1=("Lahore Qalandars", "LQ"), team2=("Karachi Kings", "KK"), match_type="League")]))[0]
        ind = parse_page(embedded([record(3, series="India tour of Australia", team1=("Australia", "AUS"), team2=("India", "IND"), match_type="International")]))[0]
        ipl = parse_page(embedded([record(4, series="Indian Premier League 2026", team1=("CSK", "CSK"), team2=("MI", "MI"), match_type="League")]))[0]
        dom = parse_page(embedded([record(5, series="Sheffield Shield 2026-27", team1=("New South Wales", "NSW"), team2=("South Australia", "SA"), match_type="Domestic")]))[0]
        women = parse_page(embedded([record(6, series="Womens Premier League 2026", team1=("Mumbai Indians Women", "MIW"), team2=("Delhi Capitals Women", "DCW"), match_type="Women")]))[0]
        shaheens = parse_page(embedded([record(7, series="Pakistan Shaheens tour", team1=("Pakistan Shaheens", "PAKS"), team2=("Sri Lanka A", "SLA"), match_type="Domestic")]))[0]
        pak_w = parse_page(embedded([record(8, series="Pakistan Women vs India Women", team1=("Pakistan Women", "PAKW"), team2=("India Women", "INDW"), match_type="International")]))[0]

        self.assertTrue(is_team_match(pak, "Pakistan"))
        self.assertTrue(is_team_match(psl, "Pakistan"))
        self.assertTrue(is_team_match(shaheens, "Pakistan"))
        self.assertFalse(is_team_match(ind, "Pakistan"))
        self.assertTrue(is_team_match(ind, "India"))
        self.assertTrue(is_team_match(ipl, "India"))

        _, pak_feed = get_match_state({"live": [psl, ind, ipl, pak, dom, women]}, scope="team", team="Pakistan")
        self.assertEqual([m["id"] for m in pak_feed], ["1", "2"])
        self.assertTrue(matches_category(pak_feed[0], "Pakistan", "team"))
        self.assertFalse(matches_category(pak_feed[1], "Pakistan", "team"))
        self.assertTrue(matches_category(pak_feed[1], "PSL", "team"))

        _, ind_feed = get_match_state({"live": [pak, psl, ipl, ind, dom, women]}, scope="team", team="India")
        self.assertEqual([m["id"] for m in ind_feed], ["3", "4"])

        _, intl_feed = get_match_state({"live": [ipl, psl, ind, pak, dom, women, shaheens, pak_w]}, scope="international")
        self.assertEqual([m["id"] for m in intl_feed], ["3", "1", "4", "2"])

        self.assertEqual(categories_for_scope("team", "Pakistan"), ("All", "Pakistan", "PSL"))
        self.assertEqual(categories_for_scope("team", "India"), ("All", "India", "IPL"))
        self.assertEqual(categories_for_scope("team", "New Zealand"), ("All", "New Zealand"))
        self.assertIn("International", categories_for_scope("international"))
        self.assertIn("IPL", categories_for_scope("international"))

    def test_scraper_null_fields_reordered_categories_test_innings_and_pause_phrases(self):
        # Null matchScore/seriesName and reordered typeMatches keys remain parseable.
        payload = json.dumps({
            "typeMatches": [{
                "seriesMatches": [{"seriesAdWrapper": {"matches": [record(10, series="Border-Gavaskar Trophy 2026", team1=("Australia", "AUS"), team2=("India", "IND"))]}}],
                "matchType": "International",
            }],
            "extra": {"matchInfo": {"matchId": 11, "team1": {"teamName": "Pakistan", "teamSName": "PAK"}, "team2": {"teamName": "Sri Lanka", "teamSName": "SL"},
                                    "state": "Preview", "status": "Match starts soon", "seriesName": None}, "matchScore": None},
        })
        parsed = {m["id"]: m for m in parse_page(f'<script type="application/json">{payload}</script>')}
        self.assertEqual(parsed["10"]["category"], "international")
        self.assertEqual(parsed["11"]["series"], "")

        # Chronological inningsId ordering + isDeclared formatting.
        test_rec = {
            "matchInfo": {"matchId": 12, "team1": {"teamName": "Pakistan", "teamSName": "PAK"}, "team2": {"teamName": "Sri Lanka", "teamSName": "SL"},
                          "state": "In Progress", "status": "Day 4: 2nd Session", "seriesName": "Sri Lanka tour of Pakistan"},
            "matchScore": {
                "team1Score": {"inngs1": {"inningsId": 1, "runs": 434, "wickets": 9, "overs": "106.3", "isDeclared": True},
                               "inngs2": {"inningsId": 3, "runs": 120, "wickets": 2, "overs": "31.0"}},
                "team2Score": {"inngs1": {"inningsId": 2, "runs": 380, "wickets": 10, "overs": "99.1"}},
            },
        }
        test_match = parse_page(embedded([test_rec]))[0]
        self.assertEqual([r["runs"] for r in test_match["scores"]], [434, 380, 120])
        self.assertIn("PAK 434/9d (106.3 ov)", test_match["score"])

        # Active phrases stay live; rain phrasing pauses; draw completes without matching "incomplete".
        self.assertEqual(parse_page(embedded([record(13, state="In Progress", status="Play resumes after Lunch")]))[0]["state"], "live")
        self.assertEqual(parse_page(embedded([record(14, state="In Progress", status="Play stopped due to rain")]))[0]["phase"], "Rain Delay")
        self.assertEqual(parse_page(embedded([record(15, state="Complete", status="Match ends in a draw")]))[0]["state"], "completed")
        self.assertEqual(parse_page(embedded([record(16, state="In Progress", status="Incomplete over")]))[0]["state"], "live")

    def test_stumps_and_break_refresh_intervals(self):
        self.assertEqual(refresh_interval("paused", [{"state": "paused", "phase": "Stumps"}]), 300)
        self.assertEqual(refresh_interval("paused", [{"state": "paused", "phase": "Lunch"}]), 120)

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

    def test_set_filter_re_filters_cached_pools_and_bumps_revision(self):
        pak = parse_page(embedded([record(1, series="Pakistan tour of NZ", team1=("Pakistan", "PAK"), team2=("New Zealand", "NZ"), match_type="International")]))[0]
        ind = parse_page(embedded([record(2, series="India tour of Australia", team1=("Australia", "AUS"), team2=("India", "IND"), match_type="International")]))[0]
        calls = 0
        def fetch():
            nonlocal calls
            calls += 1
            return {"live": [pak, ind], "recent": [], "upcoming": [], "errors": {}}
        service = ScoreService(fetch, scope="team", team="Pakistan")
        service.refresh()
        self.assertEqual(calls, 1)
        snap1 = service.snapshot()
        self.assertEqual([m["id"] for m in snap1["matches"]], ["1"])
        rev1 = snap1["revision"]
        service.set_filter("international")
        self.assertEqual(calls, 1)
        self.assertGreater(service.snapshot()["revision"], rev1)
        self.assertEqual([m["id"] for m in service.snapshot()["matches"]], ["1", "2"])
        service.set_filter("team", "India")
        self.assertEqual([m["id"] for m in service.snapshot()["matches"]], ["2"])

class PreferenceTests(unittest.TestCase):
    def test_roundtrip_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            values = dict(DEFAULTS, position=[10, 20], hidden=True, text_size=14, scope="team", team="Pakistan")
            save_settings(values, path)
            self.assertEqual(load_settings(path), values)
            values_intl = dict(DEFAULTS, scope="international", team="India")
            save_settings(values_intl, path)
            self.assertEqual(load_settings(path), values_intl)
            path.write_text(json.dumps({"scope": "invalid", "team": "Martians"}))
            loaded = load_settings(path)
            self.assertIsNone(loaded["scope"])
            self.assertIsNone(loaded["team"])
            path.write_text("broken")
            self.assertEqual(load_settings(path), DEFAULTS)
            path.write_text("[]")
            self.assertEqual(load_settings(path), DEFAULTS)

    def test_numeric_version_order(self):
        self.assertGreater(version_tuple("v2.10.0"), version_tuple("v2.9.0"))
        self.assertIsNone(version_tuple("v2.7.0-beta"))

if __name__ == "__main__":
    unittest.main()
