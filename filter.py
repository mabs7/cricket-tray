"""
filter.py
Filters match data to Pakistan and PSL matches only.
"""

PAK_KEYWORDS = [
    # Country / league name
    "pakistan",
    "pak",
    "psl",
    "pakistan super league",
    "hbl psl",
    # PSL 2026 team names
    "lahore qalandars",
    "karachi kings",
    "peshawar zalmi",
    "quetta gladiators",
    "islamabad united",
    "multan sultans",
    "hyderabad kingsmen",
    "rawalpindi pindiz",
]


def is_pakistan_match(match: dict) -> bool:
    """Return True if the match involves Pakistan or is a PSL match."""
    # Check is_psl flag set by scraper from href
    if match.get("is_psl"):
        return True

    searchable = " ".join(
        [
            match.get("teams", ""),
            match.get("series", ""),
            match.get("status", ""),
            match.get("href", ""),
        ]
    ).lower()

    return any(keyword in searchable for keyword in PAK_KEYWORDS)


def filter_pakistan_matches(matches: list) -> list:
    """Filter a list of match dicts to Pakistan/PSL only."""
    return [m for m in matches if is_pakistan_match(m)]


def get_display_text(match: dict) -> str:
    """Format a match dict into a compact tray/menu string."""
    teams = match.get("teams", "Unknown")
    score = match.get("score", "")
    status = match.get("status", "")

    # If we have an active score, it already contains the abbreviations!
    if score:
        # If there is a notable interruption (like Rain Delay or Innings Break), show it.
        # Otherwise, just show the clean score to save space.
        if status and status not in ["In Progress", "Scheduled", "Preview"]:
            return f"🏏 {score}  [{status}]"
        return f"🏏 {score}"

    # If there is no score yet (Scheduled match), show the full team names
    parts = [f"🏏 {teams}"]
    if status:
        parts.append(status)

    return "  |  ".join(parts)


def _deduplicate(matches: list) -> list:
    """Remove duplicate matches by teams name."""
    seen = set()
    result = []
    for m in matches:
        key = m.get("teams", "").lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(m)
    return result


def get_match_state(all_matches: dict) -> tuple:
    """
    Analyse all_matches dict and return (state, pak_matches).
    Strictly isolates the single most relevant match to prevent UI clutter.
    """
    # Separate the pools instead of smashing them together
    live_pool = filter_pakistan_matches(all_matches.get("live", []))
    upcoming_pool = filter_pakistan_matches(all_matches.get("upcoming", []))
    recent_pool = filter_pakistan_matches(all_matches.get("recent", []))

    # 1. LIVE MATCHES: Must have a score and not be finished/scheduled
    actual_live = []
    for m in live_pool:
        status = m.get("status", "").lower()
        # Explicitly exclude finished or purely scheduled matches
        is_finished = any(x in status for x in ["won by", "result", "abandoned", "drawn", "no result"])
        is_scheduled = any(x in status for x in ["preview", "starts at", "tomorrow", "scheduled", "time", "yet to begin"])
        
        # If it's flagged live, has a score (even a partial one), and isn't finished/scheduled
        if m.get("is_live") and not is_finished and not is_scheduled:
            actual_live.append(m)
            
    if actual_live:
        # Return only the genuinely live matches (usually just 1)
        return "live", _deduplicate(actual_live)

    # 2. TODAY'S UPCOMING MATCHES
    # Look in both live_pool (Cricbuzz sometimes puts today's unstarted matches here) and upcoming_pool
    today_unstarted = []
    for m in live_pool + upcoming_pool:
        status = m.get("status", "").lower()
        is_finished = any(x in status for x in ["won by", "result", "abandoned", "drawn", "no result"])
        
        # If it doesn't have a score and isn't finished, it's upcoming
        if not m.get("score") and not is_finished and not m.get("is_live"):
            today_unstarted.append(m)
            
    if today_unstarted:
        # Return JUST the very next scheduled match (slice the list to 1)
        today_unstarted = _deduplicate(today_unstarted)
        return "today", today_unstarted[:1]

    # 3. RECENT MATCHES
    # Look in recent_pool (or live_pool if a match just finished moments ago)
    recent_finished = []
    for m in live_pool + recent_pool:
        status = m.get("status", "").lower()
        is_finished = any(x in status for x in ["won by", "result", "abandoned", "drawn", "no result"])
        if is_finished:
            recent_finished.append(m)
            
    if recent_finished:
        # Return JUST the single most recent match (slice the list to 1)
        recent_finished = _deduplicate(recent_finished)
        return "none", recent_finished[:1] 

    return "none", []