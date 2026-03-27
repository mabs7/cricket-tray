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

    state:
        'live'     - Pakistan match is currently live
        'today'    - Pakistan match scheduled today but not started
        'none'     - No Pakistan match found anywhere
    """
    # Combine all matches and deduplicate
    all_pak = _deduplicate(
        filter_pakistan_matches(
            all_matches.get("live", [])
            + all_matches.get("upcoming", [])
            + all_matches.get("recent", [])
        )
    )

    # Check for truly live matches (enriched is_live flag)
    truly_live = [m for m in all_pak if m.get("is_live")]
    if truly_live:
        return "live", truly_live

    # Check for upcoming/preview matches
    upcoming = [m for m in all_pak if m.get("status") == "Preview"]
    if upcoming:
        return "today", upcoming

    # Fall back to recent results
    if all_pak:
        return "none", all_pak[:1]  # show only most recent

    return "none", []
