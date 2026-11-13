"""Parse embedded Cricbuzz data first, with scoped HTML as a fallback."""
import json
import logging
import re
import time
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
MAX_PAGE_BYTES = 10 * 1024 * 1024
PAGE_TIMEOUT = 20
MATCH_HREF = re.compile(r"^/live-cricket-scores/(\d+)(?:/|$)")
FINISHED = re.compile(r"\bwon\b(?! the toss)|\bbeat\b|\bdraw[n]?\b|\btied\b|no result|abandon|cancel|\bcomplete(?:d)?\b", re.I)
SCHEDULED = re.compile(r"preview|scheduled|upcoming|starts at|yet to begin", re.I)
# Interruptions where a match is in progress but play has stopped. Cricbuzz
# reports these in matchInfo.state (e.g. "Stumps") and/or the status text
# (e.g. "Day 3: Stumps - Sri Lanka trail by 30 runs").
PAUSE_STATES = {"stumps": "Stumps", "innings break": "Innings Break", "lunch": "Lunch", "tea": "Tea",
                "dinner": "Dinner", "drink": "Drinks", "drinks": "Drinks", "rain": "Rain Delay",
                "wet outfield": "Wet Outfield", "bad light": "Bad Light", "delay": "Delayed"}
ACTIVE_STATUS = re.compile(r"\b(?:resum(?:e|es|ed)\s+(?:after|following)|after\s+(?:tea|lunch|dinner|drinks|rain)|until\s+(?:tea|lunch|stumps)|post-(?:tea|lunch)|before\s+(?:tea|lunch|stumps))\b", re.I)
PAUSE_TEXT = [("Stumps", re.compile(r"\bstumps\b", re.I)),
              ("Innings Break", re.compile(r"\binnings break\b", re.I)),
              ("Lunch", re.compile(r"\blunch\b", re.I)),
              ("Tea", re.compile(r"\btea\b", re.I)),
              ("Dinner", re.compile(r"\bdinner\b", re.I)),
              ("Drinks", re.compile(r"\bdrinks\b", re.I)),
              ("Rain Delay", re.compile(r"\brain\s+(?:stops|stopped|delay|delayed|interrupts?)\b|\b(?:play|match|start|toss)\s+(?:stopped|delayed|halted|suspended)\s+(?:due to|by)\s+rain\b|\bdelayed\s+(?:due to|by)\s+rain\b", re.I)),
              ("Wet Outfield", re.compile(r"\bwet outfield\b", re.I)),
              ("Bad Light", re.compile(r"\bbad light\b", re.I))]
SCORE = re.compile(r"\b([A-Z][A-Z0-9]{1,7})\s+(\d{1,4})(?:\s*[/\-]\s*(\d{1,2}))?\s*(?:d\s*)?\(\s*(\d+(?:\.\d)?)\s*(?:ov(?:s|ers)?)?\s*\)")

class ScrapeError(RuntimeError):
    pass

def match_id(href):
    found = MATCH_HREF.match(urlparse(href).path)
    return found.group(1) if found else ""

def match_url(match):
    path = urlparse(match.get("href", "")).path
    if any(ch.isspace() or ord(ch) < 32 for ch in path):
        return ""
    return BASE_URL + path if MATCH_HREF.match(path) else ""

def parse_date(value):
    try:
        if str(value).isdigit():
            return datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.astimezone(timezone.utc) if date.tzinfo else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None

def match_state(status, state="", has_score=False):
    """Return (state, phase). phase names the interruption for paused matches."""
    status, key = status or "", (state or "").strip().lower()
    if FINISHED.search(status) or key in {"complete", "completed"}:
        return "completed", ""
    if key in {"preview", "upcoming"}:
        return "scheduled", ""
    phase = "" if (ACTIVE_STATUS.search(status) and key not in PAUSE_STATES) else (
        next((label for label, pattern in PAUSE_TEXT if pattern.search(status)), "") or PAUSE_STATES.get(key, "")
    )
    if SCHEDULED.search(status):
        # A match with scores whose next session has not begun is paused, not upcoming.
        return ("paused", phase or "Break") if has_score else ("scheduled", "")
    if phase:
        return "paused", phase
    if key in {"in progress", "live", "toss"} or has_score:
        return "live", ""
    return "unknown", ""

def classify(status, state="", has_score=False):
    return match_state(status, state, has_score)[0]

def _score_row(team, runs, wickets, overs, normalize=False, declared=False):
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
        row = {"team": team, "runs": runs, "wickets": wickets, "overs": ov}
        if declared:
            row["declared"] = True
        return row
    except (TypeError, ValueError):
        return None

def format_scores(rows):
    return "  |  ".join(
        f"{r['team']} {r['runs']}"
        + (f"/{r['wickets']}" if r['wickets'] is not None else "")
        + ("d" if r.get("declared") else "")
        + (f" ({r['overs']} ov)" if r['overs'] else "")
        for r in rows
    )

def _structured_match(record):
    info = record.get("matchInfo") or {}
    if not isinstance(info, dict):
        return None
    teams = [info.get("team1") or {}, info.get("team2") or {}]
    if not all(isinstance(t, dict) and t.get("teamName") for t in teams) or not str(info.get("matchId") or "").isdigit():
        return None
    match_score = record.get("matchScore") or {}
    if not isinstance(match_score, dict):
        match_score = {}
    numbered_rows = []
    invalid_score = False
    seq = 0
    for index, team in enumerate(teams, 1):
        team_score = match_score.get(f"team{index}Score") or {}
        if not isinstance(team_score, dict):
            continue
        for key, value in team_score.items():
            if key.startswith("inngs") and isinstance(value, dict) and "runs" in value:
                row = _score_row(team.get("teamSName") or team["teamName"], value["runs"], value.get("wickets"),
                                 value.get("overs"), True, declared=bool(value.get("isDeclared")))
                if row:
                    innings_id = value.get("inningsId")
                    sort_id = int(innings_id) if isinstance(innings_id, int) and not isinstance(innings_id, bool) else (1000 + seq)
                    numbered_rows.append((sort_id, seq, row))
                    seq += 1
                else:
                    invalid_score = True
    if invalid_score:
        raise ScrapeError(f"Invalid score data for match {info['matchId']}")
    numbered_rows.sort(key=lambda item: (item[0], item[1]))
    rows = [item[2] for item in numbered_rows]
    status = info.get("status") or ""
    series_name = info.get("seriesName") or ""
    state, phase = match_state(status, info.get("state") or "", bool(rows))
    return {"id": str(info["matchId"]), "teams": " vs ".join(t["teamName"] for t in teams),
            "team_names": [t["teamName"] for t in teams], "team_codes": [t.get("teamSName") or "" for t in teams],
            "score": format_scores(rows), "scores": rows, "status": status, "series": series_name,
            "start_time": info.get("startDate"), "state": state, "phase": phase, "is_live": state == "live",
            "is_psl": "pakistan super league" in series_name.lower(),
            "category": str(info.get("matchType") or "").strip().lower(),
            "href": f"/live-cricket-scores/{info['matchId']}/", "parser": "embedded"}

def _walk_match_ids(root, found):
    stack = [root]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            match_info = value.get("matchInfo")
            if isinstance(match_info, dict):
                ident = match_info.get("matchId")
                if ident is not None:
                    found.append(str(ident))
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return found

def _categories(text, decoder):
    """Map match IDs to Cricbuzz's grouping (International, League, Domestic, Women)."""
    result = {}
    for hit in re.finditer(r'"typeMatches"\s*:\s*\[', text):
        try:
            groups, _ = decoder.raw_decode(text, hit.end() - 1)
        except ValueError:
            continue
        if isinstance(groups, list):
            for group in groups:
                if isinstance(group, dict) and group.get("matchType"):
                    cat = str(group["matchType"]).strip().lower()
                    for ident in _walk_match_ids(group.get("seriesMatches", []), []):
                        result.setdefault(ident, cat)
    if result:
        return result
    for hit in re.finditer(r'\{\s*"matchType"\s*:\s*"([^"]+)"\s*,\s*"seriesMatches"\s*:', text):
        try:
            group, _ = decoder.raw_decode(text, hit.start())
        except ValueError:
            continue
        if isinstance(group, dict):
            for ident in _walk_match_ids(group.get("seriesMatches", []), []):
                result.setdefault(ident, hit.group(1).strip().lower())
    return result

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
    decoder, result, categories = json.JSONDecoder(), {}, {}
    for text in texts:
        for ident, category in _categories(text, decoder).items():
            categories.setdefault(ident, category)
        for hit in re.finditer(r'\{\s*"matchInfo"\s*:', text):
            try:
                record, _ = decoder.raw_decode(text, hit.start())
                match = _structured_match(record)
                if match:
                    old = result.get(match["id"])
                    if not old or len(match["scores"]) >= len(old["scores"]):
                        match["category"] = match["category"] or (old or {}).get("category", "")
                        result[match["id"]] = match
            except (ValueError, TypeError, AttributeError):
                logging.debug("Unrecognized match record", exc_info=True)
    for ident, match in result.items():
        match["category"] = categories.get(ident) or match["category"]
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
        state, phase = match_state(status, "Preview" if page_type == "upcoming" else "", bool(rows))
        series = card.find_previous("a", href=re.compile(r"^/cricket-series/"))
        series_name = series.get_text(strip=True) if series else ""
        matches[ident] = {"id": ident, "teams": title, "team_names": names, "team_codes": codes,
                          "scores": rows, "score": format_scores(rows), "status": status,
                          "series": series_name, "href": urlparse(card["href"]).path,
                          "start_time": None, "state": state, "phase": phase, "is_live": state == "live",
                          "is_psl": "pakistan super league" in series_name.lower(), "category": "", "parser": "html"}
    # Standard JSON-LD remains useful if the application payload changes.
    def visit(root):
        stack = [root]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                if value.get("@type") == "SportsEvent":
                    names = [t.get("name") for t in value.get("competitor", []) if isinstance(t, dict)]
                    for match in matches.values():
                        if match["parser"] == "html" and len(names) == 2 and set(names) == set(match["team_names"]):
                            match["start_time"] = value.get("startDate")
                            match["status"] = value.get("eventStatus", match["status"])
                            match["state"], match["phase"] = match_state(match["status"], has_score=bool(match["scores"]))
                            match["is_live"] = match["state"] == "live"
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            visit(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue
    if not matches and not soup.find(string=re.compile(r"no (?:live |upcoming |recent )?matches", re.I)):
        raise ScrapeError("No recognizable match data; the page may be blocked or its layout changed")
    return list(matches.values())

def _parse_matches(url, page_type="live"):
    deadline = time.monotonic() + PAGE_TIMEOUT
    with requests.get(url, headers=HEADERS, timeout=(5, 15), stream=True) as response:
        response.raise_for_status()
        for hopped in [*response.history, response]:
            parsed = urlparse(hopped.url)
            if parsed.scheme != "https" or parsed.hostname not in {"www.cricbuzz.com", "cricbuzz.com"}:
                raise ScrapeError("Unexpected redirect outside Cricbuzz HTTPS")
        chunks, total = [], 0
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                total += len(chunk)
                if total > MAX_PAGE_BYTES:
                    raise ScrapeError("Page exceeded maximum size")
                chunks.append(chunk)
            if time.monotonic() > deadline:
                raise ScrapeError("Page download exceeded overall timeout")
        encoding = response.encoding or "utf-8"
        html = b"".join(chunks).decode(encoding, errors="replace")
    return parse_page(html, page_type)

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
