"""Parse embedded Cricbuzz data first, with scoped HTML as a fallback."""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cricbuzz.com"
LIVE_URL = BASE_URL + "/cricket-match/live-scores"
RECENT_URL = LIVE_URL + "/recent-matches"
UPCOMING_URL = LIVE_URL + "/upcoming-matches"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "text/html"}
MATCH_HREF = re.compile(r"^/live-cricket-scores/(\d+)(?:/|$)")
FINISHED = re.compile(r"won|\bbeat\b|drawn|\btied\b|no result|abandon|cancel|complete", re.I)
SCHEDULED = re.compile(r"preview|scheduled|upcoming|starts at|yet to begin", re.I)
SCORE = re.compile(r"\b([A-Z][A-Z0-9]{1,7})\s+(\d{1,4})(?:\s*[/\-]\s*(\d{1,2}))?\s*(?:d\s*)?\(\s*(\d+(?:\.\d)?)\s*(?:ov(?:s|ers)?)?\s*\)")

class ScrapeError(RuntimeError):
    pass

def match_id(href):
    found = MATCH_HREF.match(urlparse(href).path)
    return found.group(1) if found else ""

def match_url(match):
    path = urlparse(match.get("href", "")).path
    return BASE_URL + path if MATCH_HREF.match(path) else ""

def parse_date(value):
    try:
        if str(value).isdigit():
            return datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.astimezone(timezone.utc) if date.tzinfo else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None

def classify(status, state="", has_score=False):
    if FINISHED.search(status) or state.lower() in {"complete", "completed"}:
        return "completed"
    if SCHEDULED.search(status) or state.lower() in {"preview", "upcoming"}:
        return "scheduled"
    if state.lower() in {"in progress", "live", "innings break", "stumps", "rain", "toss"} or has_score:
        return "live"
    return "unknown"

def _score_row(team, runs, wickets, overs, normalize=False):
    try:
        runs = int(runs)
        wickets = int(wickets) if wickets is not None else None
        if not 0 <= runs <= 3000 or (wickets is not None and not 0 <= wickets <= 10):
            return None
        ov = str(overs) if overs is not None else ""
        if ov:
            whole, _, ball = ov.partition(".")
            if not whole.isdigit() or (ball and (len(ball) != 1 or not ball.isdigit())):
                return None
            balls = int(ball or 0)
            if normalize and balls == 6:  # Cricbuzz encodes completed overs as 19.6
                ov = str(int(whole) + 1)
            elif balls > 5:
                return None
        return {"team": team, "runs": runs, "wickets": wickets, "overs": ov}
    except (TypeError, ValueError):
        return None

def format_scores(rows):
    return "  |  ".join(f"{r['team']} {r['runs']}" + (f"/{r['wickets']}" if r['wickets'] is not None else "") + (f" ({r['overs']} ov)" if r['overs'] else "") for r in rows)

def _structured_match(record):
    info = record.get("matchInfo", {})
    teams = [info.get("team1", {}), info.get("team2", {})]
    if not str(info.get("matchId", "")).isdigit() or not all(t.get("teamName") for t in teams):
        return None
    rows = []
    invalid_score = False
    for index, team in enumerate(teams, 1):
        for key, value in record.get("matchScore", {}).get(f"team{index}Score", {}).items():
            if key.startswith("inngs") and isinstance(value, dict) and "runs" in value:
                row = _score_row(team.get("teamSName") or team["teamName"], value["runs"], value.get("wickets"), value.get("overs"), True)
                if row:
                    rows.append(row)
                else:
                    invalid_score = True
    if invalid_score:
        raise ScrapeError(f"Invalid score data for match {info['matchId']}")
    status = info.get("status", "")
    state = classify(status, info.get("state", ""), bool(rows))
    return {"id": str(info["matchId"]), "teams": " vs ".join(t["teamName"] for t in teams),
            "team_names": [t["teamName"] for t in teams], "team_codes": [t.get("teamSName", "") for t in teams],
            "score": format_scores(rows), "scores": rows, "status": status, "series": info.get("seriesName", ""),
            "start_time": info.get("startDate"), "state": state, "is_live": state == "live",
            "is_psl": "pakistan super league" in info.get("seriesName", "").lower(),
            "href": f"/live-cricket-scores/{info['matchId']}/", "parser": "embedded"}

def _embedded(soup):
    texts, flight = [], []
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if script.get("type") in {"application/json", "application/ld+json"}:
            texts.append(text)
        if text.startswith("self.__next_f.push("):
            try:
                payload = json.loads(text[text.index("(") + 1:text.rindex(")")])
                if len(payload) > 1 and isinstance(payload[1], str):
                    flight.append(payload[1])
            except (ValueError, TypeError, IndexError):
                continue
    texts.append("".join(flight))
    decoder, result = json.JSONDecoder(), {}
    for text in texts:
        for hit in re.finditer(r'\{\s*"matchInfo"\s*:', text):
            try:
                record, _ = decoder.raw_decode(text[hit.start():])
                match = _structured_match(record)
                if match:
                    old = result.get(match["id"])
                    if not old or len(match["scores"]) >= len(old["scores"]):
                        result[match["id"]] = match
            except (ValueError, TypeError, AttributeError):
                logging.debug("Unrecognized match record", exc_info=True)
    return result

def _text_scores(text, codes):
    rows, allowed = [], {c.upper() for c in codes if c}
    for code, runs, wickets, overs in SCORE.findall(text):
        if code not in allowed:
            continue
        row = _score_row(code, runs, wickets or None, overs)
        if row and row not in rows:
            rows.append(row)
    return rows

def parse_page(html, page_type="live"):
    """Pure parser; no network access and no execution of embedded scripts."""
    soup = BeautifulSoup(html, "html.parser")
    matches, links = _embedded(soup), {}
    for link in soup.find_all("a", href=True):
        ident = match_id(link["href"])
        if ident:
            links.setdefault(ident, []).append(link)
    for ident, group in links.items():
        if ident in matches:
            matches[ident]["href"] = urlparse(group[0]["href"]).path
            continue
        title = next((a.get_text(" ", strip=True) for a in group if " vs " in a.get_text(" ", strip=True) and " - " not in a.get_text(" ", strip=True)), "")
        if not title:
            continue
        title = re.split(r"\s+(?:\d+(?:st|nd|rd|th)\s+)?(?:Match|T20I?|ODI|Test|Final|Semi Final|Qualifier|Preview|Pool|Irani Cup)\b", title, flags=re.I)[0]
        names = title.split(" vs ")
        if len(names) != 2:
            continue
        card = max(group, key=lambda a: len(a.get_text()))
        container = card
        for _ in range(4):
            parent = container.parent
            if not parent or parent.name in {"body", "html", "nav", "header"}:
                break
            ids = {match_id(a.get("href", "")) for a in parent.find_all("a", href=True)} - {""}
            if ids != {ident}:
                break
            container = parent
        text = container.get_text(" ", strip=True)
        codes = [c for c in re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", text) if c not in {"ODI", "T20", "CRR", "RRR", "OVS", "LIVE"}]
        rows = _text_scores(text, codes)
        node = container.find(class_=re.compile(r"status|cb-text-(?:live|complete|preview)", re.I))
        status = node.get_text(" ", strip=True) if node else ""
        state = classify(status, "Preview" if page_type == "upcoming" else "", bool(rows))
        series = card.find_previous("a", href=re.compile(r"^/cricket-series/"))
        matches[ident] = {"id": ident, "teams": title, "team_names": names, "team_codes": codes,
                          "scores": rows, "score": format_scores(rows), "status": status,
                          "series": series.get_text(strip=True) if series else "", "href": urlparse(card["href"]).path,
                          "start_time": None, "state": state, "is_live": state == "live", "is_psl": False, "parser": "html"}
    # Standard JSON-LD remains useful if the application payload changes.
    def visit(value):
        if isinstance(value, dict):
            if value.get("@type") == "SportsEvent":
                names = [t.get("name") for t in value.get("competitor", []) if isinstance(t, dict)]
                for match in matches.values():
                    if match["parser"] == "html" and len(names) == 2 and set(names) == set(match["team_names"]):
                        match["start_time"] = value.get("startDate")
                        match["status"] = value.get("eventStatus", match["status"])
                        match["state"] = classify(match["status"], has_score=bool(match["scores"]))
                        match["is_live"] = match["state"] == "live"
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            visit(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue
    if not matches and not soup.find(string=re.compile(r"no (?:live |upcoming |recent )?matches", re.I)):
        raise ScrapeError("No recognizable match data; the page may be blocked or its layout changed")
    return list(matches.values())

def _parse_matches(url, page_type="live"):
    response = requests.get(url, headers=HEADERS, timeout=(5, 15))
    response.raise_for_status()
    return parse_page(response.text, page_type)

def get_live_matches():
    return _parse_matches(LIVE_URL)

def get_recent_matches():
    return _parse_matches(RECENT_URL, "recent")

def get_upcoming_matches():
    return _parse_matches(UPCOMING_URL, "upcoming")

def get_all_matches():
    result = {"live": [], "recent": [], "upcoming": [], "errors": {}}
    calls = {"live": get_live_matches, "recent": get_recent_matches, "upcoming": get_upcoming_matches}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(call) for name, call in calls.items()}
        for name, future in futures.items():
            try:
                result[name] = future.result()
            except (requests.RequestException, ScrapeError) as exc:
                result["errors"][name] = str(exc)
                logging.warning("%s fetch failed: %s", name, exc)
    return result
