"""Select team-focused or international/major-league fixtures using stable match IDs."""
import re
from datetime import datetime, timezone
from scraper import parse_date

PSL_TEAMS = ("lahore qalandars", "karachi kings", "peshawar zalmi", "quetta gladiators",
             "islamabad united", "multan sultans", "hyderabad kingsmen", "rawalpindi pindiz")
# Major men's franchise leagues, matched on Cricbuzz series names.
LEAGUES = (("PSL", re.compile(r"pakistan super league|\bpsl\b", re.I)),
           ("IPL", re.compile(r"indian premier league|\bipl\b", re.I)),
           ("BPL", re.compile(r"bangladesh premier league|\bbpl\b", re.I)),
           ("BBL", re.compile(r"big bash league|\bbbl\b", re.I)),
           ("SA20", re.compile(r"\bsa20\b", re.I)),
           ("The Hundred", re.compile(r"\bthe hundred\b", re.I)))
TEAMS = {
    "Pakistan": {"pattern": r"(?:pakistan|pak)", "league": "PSL"},
    "India": {"pattern": r"(?:india|ind)", "league": "IPL"},
    "Australia": {"pattern": r"(?:australia|aus)", "league": "BBL"},
    "England": {"pattern": r"(?:england|eng)", "league": "The Hundred"},
    "South Africa": {"pattern": r"(?:south africa|sa|rsa)", "league": "SA20"},
    "Bangladesh": {"pattern": r"(?:bangladesh|ban)", "league": "BPL"},
    "New Zealand": {"pattern": r"(?:new zealand|nz)", "league": None},
    "Sri Lanka": {"pattern": r"(?:sri lanka|sl)", "league": None},
    "West Indies": {"pattern": r"(?:west indies|wi)", "league": None},
    "Afghanistan": {"pattern": r"(?:afghanistan|afg)", "league": None},
    "Zimbabwe": {"pattern": r"(?:zimbabwe|zim)", "league": None},
    "Ireland": {"pattern": r"(?:ireland|ire)", "league": None},
}
TEAM_NAMES = tuple(TEAMS.keys())
CATEGORIES = ("All", "Pakistan", "International", "PSL", "IPL", "BPL", "BBL", "SA20", "The Hundred")
WOMEN = re.compile(r"\bwom[ae]n'?s?\b|\bwbbl\b", re.I)
# Used only when Cricbuzz's International/League/Domestic/Women grouping is unavailable.
INTERNATIONAL_SERIES = re.compile(r"\btour of\b|\bicc\b|world cup|champions trophy|asia cup|tri-?series|\bvs\b.+\bin\b", re.I)
NOT_SENIOR_TEAM = re.compile(r"\b(?:a|xi|u19|u-19|under[- ]19|lions|shaheens|champions|legends|wom[ae]n|emerging)\b", re.I)
PRIORITY = {"Pakistan": 0, "PSL": 0, "International": 1}
SCHEDULED_LIMIT, COMPLETED_LIMIT = 12, 8

def _names(match):
    names = match.get("team_names") or match.get("teams", "").split(" vs ")
    return [n.lower().strip() for n in names]

def is_psl_match(match):
    series = match.get("series", "").lower()
    return bool(match.get("is_psl", False) or "pakistan super league" in series or re.search(r"\bpsl\b", series) or any(n in PSL_TEAMS for n in _names(match)))

def is_pakistan_match(match):
    return is_team_match(match, "Pakistan")

def is_team_match(match, team):
    spec = TEAMS.get(team)
    if not spec:
        return False
    names = _names(match)
    regex = rf"{spec['pattern']}(?: women| u19| u-19| under[- ]19| a| lions| shaheens| emerging)?"
    if any(re.fullmatch(regex, n) for n in names):
        return True
    league = spec.get("league")
    if not league:
        return False
    if league == "PSL":
        return is_psl_match(match)
    series = match.get("series", "")
    if WOMEN.search(series) or any(WOMEN.search(n) for n in names):
        return False
    return any(label == league and pattern.search(series) for label, pattern in LEAGUES)

def competition(match):
    """Return the coverage label for a match, or "" when it is outside the app's scope."""
    if is_psl_match(match):
        return "PSL"
    if is_pakistan_match(match):
        return "Pakistan"
    series = match.get("series", "")
    category = match.get("category", "")
    names = _names(match)
    is_women = category == "women" or bool(WOMEN.search(series)) or any(WOMEN.search(n) for n in names)
    if not is_women:
        league = next((label for label, pattern in LEAGUES if pattern.search(series)), "")
        if league:
            return league
    if is_women or any(NOT_SENIOR_TEAM.search(n) for n in names):
        return ""
    if category == "international":
        return "International"
    if not category and INTERNATIONAL_SERIES.search(series):
        return "International"
    return ""

def categories_for_scope(scope=None, team=None):
    if scope == "team":
        team = team if team in TEAMS else "Pakistan"
        league = TEAMS[team].get("league")
        return ("All", team, league) if league else ("All", team)
    if scope == "international":
        return ("All", "International", "PSL", "IPL", "BPL", "BBL", "SA20", "The Hundred")
    return CATEGORIES

def matches_category(match, category="All", scope=None):
    """Check whether a match belongs to a UI filter category."""
    if not category or category == "All":
        return True
    comp = match.get("competition") or competition(match)
    if scope == "team":
        return comp == category
    if category in TEAMS:
        return is_team_match(match, category) if category != "Pakistan" else (comp in {"Pakistan", "PSL"} or is_pakistan_match(match))
    if category == "International":
        return comp == "International" or (comp == "Pakistan" and not is_psl_match(match))
    return comp == category

def filter_pakistan_matches(matches):
    return [m for m in matches if is_pakistan_match(m)]

def filter_covered_matches(matches):
    return [dict(m, competition=label) for m in matches for label in [competition(m)] if label]

def filter_for_scope(matches, scope=None, team=None):
    if scope == "team":
        team = team if team in TEAMS else "Pakistan"
        league = TEAMS[team].get("league")
        selected = []
        for m in matches:
            if not is_team_match(m, team):
                continue
            comp = competition(m)
            label = league if (league and comp == league) else team
            selected.append(dict(m, competition=label))
        return selected
    if scope == "international":
        selected = []
        for m in matches:
            comp = competition(m)
            if not comp:
                continue
            # Keep senior internationals and major leagues in International mode;
            # youth/women's matches remain available under "My Team".
            if comp == "Pakistan":
                if m.get("category") in {"domestic", "women"} or WOMEN.search(m.get("series", "")) or any(NOT_SENIOR_TEAM.search(n) for n in _names(m)):
                    continue
                comp = "International"
            selected.append(dict(m, competition=comp))
        return selected
    return filter_covered_matches(matches)

def _deduplicate(matches):
    result = {}
    for m in matches:
        key = m.get("id") or m.get("href") or m.get("teams")
        if key not in result or (m.get("state") == "completed" and result[key].get("state") != "completed") or (m.get("state") == result[key].get("state") and len(m.get("score", "")) > len(result[key].get("score", ""))):
            result[key] = m
    return list(result.values())

def _rank(match, scope=None, team=None):
    comp = match.get("competition")
    if scope == "team":
        team = team if team in TEAMS else "Pakistan"
        return 0 if comp == team else 1
    if scope == "international":
        return 0 if comp == "International" else 1
    return PRIORITY.get(comp, 2)

def _limit(matches, limit, scope=None, team=None):
    """Keep higher-priority fixtures first, then fill remaining slots in the given order."""
    keep = [m for m in matches if _rank(m, scope, team) == 0][:limit]
    keep += [m for m in matches if _rank(m, scope, team) != 0][:max(0, limit - len(keep))]
    chosen = {id(m) for m in keep}
    return [m for m in matches if id(m) in chosen]

def get_match_state(all_matches, now=None, scope=None, team=None):
    now = now or datetime.now(timezone.utc)
    matches = _deduplicate(filter_for_scope(sum((all_matches.get(k, []) for k in ("live", "recent", "upcoming")), []), scope, team))
    live = sorted((m for m in matches if m.get("state") == "live"), key=lambda m: _rank(m, scope, team))
    paused = sorted((m for m in matches if m.get("state") == "paused"), key=lambda m: _rank(m, scope, team))
    scheduled = [m for m in matches if m.get("state") in {"scheduled", "unknown"}]
    completed = [m for m in matches if m.get("state") == "completed"]
    scheduled.sort(key=lambda m: parse_date(m.get("start_time")) or datetime.max.replace(tzinfo=timezone.utc))
    completed.sort(key=lambda m: parse_date(m.get("start_time")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    scheduled, completed = _limit(scheduled, SCHEDULED_LIMIT, scope, team), _limit(completed, COMPLETED_LIMIT, scope, team)
    ordered = live + paused + scheduled + completed
    if live:
        return "live", ordered
    if paused:
        return "paused", ordered
    if scheduled:
        start = parse_date(scheduled[0].get("start_time"))
        return ("today" if start and start.astimezone().date() == now.astimezone().date() else "scheduled"), ordered
    return ("completed", ordered) if completed else ("none", [])

def get_display_text(match):
    text = match.get("score") or match.get("teams", "Unknown match")
    status = match.get("status", "")
    if status and status.lower() not in {"in progress", "scheduled", "preview"}:
        text += f" · {status}"
    return text
