"""Select Pakistan internationals and PSL fixtures using stable match IDs."""
import re
from datetime import datetime, timezone
from scraper import parse_date

PSL_TEAMS = ("lahore qalandars", "karachi kings", "peshawar zalmi", "quetta gladiators",
             "islamabad united", "multan sultans", "hyderabad kingsmen", "rawalpindi pindiz")

def is_pakistan_match(match):
    names = match.get("team_names") or match.get("teams", "").lower().split(" vs ")
    names = [n.lower().strip() for n in names]
    international = any(re.fullmatch(r"pak(?:istan)?(?: women| u19| under[- ]19| a)?", n) for n in names)
    series = match.get("series", "").lower()
    return international or match.get("is_psl", False) or "pakistan super league" in series or bool(re.search(r"\bpsl\b", series)) or any(n in PSL_TEAMS for n in names)

def filter_pakistan_matches(matches):
    return [m for m in matches if is_pakistan_match(m)]

def _deduplicate(matches):
    result = {}
    for m in matches:
        key = m.get("id") or m.get("href") or m.get("teams")
        if key not in result or (m.get("state") == "completed" and result[key].get("state") != "completed") or (m.get("state") == result[key].get("state") and len(m.get("score", "")) > len(result[key].get("score", ""))):
            result[key] = m
    return list(result.values())

def get_match_state(all_matches, now=None):
    now = now or datetime.now(timezone.utc)
    matches = _deduplicate(filter_pakistan_matches(sum((all_matches.get(k, []) for k in ("live", "recent", "upcoming")), [])))
    live = [m for m in matches if m.get("state") == "live"]
    scheduled = [m for m in matches if m.get("state") in {"scheduled", "unknown"}]
    completed = [m for m in matches if m.get("state") == "completed"]
    scheduled.sort(key=lambda m: parse_date(m.get("start_time")) or datetime.max.replace(tzinfo=timezone.utc))
    completed.sort(key=lambda m: parse_date(m.get("start_time")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    ordered = live + scheduled + completed[:3]
    if live:
        return "live", ordered
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
