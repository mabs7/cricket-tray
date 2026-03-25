"""
filter.py
Filters match data to Pakistan and PSL matches only.
"""

PAK_KEYWORDS = [
    # Country / league name
    "pakistan", "pak", "psl", "pakistan super league", "hbl psl",
    # PSL 2026 team names
    "lahore qalandars", "karachi kings", "peshawar zalmi",
    "quetta gladiators", "islamabad united", "multan sultans",
    "hyderabad kingsmen", "rawalpindi pindiz",
]


def is_pakistan_match(match: dict) -> bool:
    """Return True if the match involves Pakistan or is a PSL match."""
    searchable = " ".join([
        match.get("teams", ""),
        match.get("series", ""),
        match.get("status", ""),
    ]).lower()

    return any(keyword in searchable for keyword in PAK_KEYWORDS)


def filter_pakistan_matches(matches: list) -> list:
    """Filter a list of match dicts to Pakistan/PSL only."""
    return [m for m in matches if is_pakistan_match(m)]


def get_display_text(match: dict) -> str:
    """Format a match dict into a single tray tooltip string."""
    teams = match.get("teams", "Unknown")
    score = match.get("score", "")
    status = match.get("status", "")

    parts = [f"🏏 {teams}"]
    if score:
        parts.append(score)
    if status:
        parts.append(status)

    return "  |  ".join(parts)


def get_match_state(all_matches: dict) -> tuple:
    """
    Analyse all_matches dict and return (state, pak_matches).

    state:
        'live'     - Pakistan match is currently live
        'today'    - Pakistan match scheduled today but not started
        'none'     - No Pakistan match found anywhere
    """
    live_pak = filter_pakistan_matches(all_matches.get("live", []))
    if live_pak:
        return "live", live_pak

    upcoming_pak = filter_pakistan_matches(all_matches.get("upcoming", []))
    if upcoming_pak:
        return "today", upcoming_pak

    recent_pak = filter_pakistan_matches(all_matches.get("recent", []))
    if recent_pak:
        return "none", recent_pak  # show last result

    return "none", []