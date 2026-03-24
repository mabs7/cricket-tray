import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

LIVE_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
RECENT_URL = "https://www.cricbuzz.com/cricket-match/live-scores/recent-matches"
UPCOMING_URL = "https://www.cricbuzz.com/cricket-match/live-scores/upcoming-matches"


def _parse_matches(url):
    """Fetch and parse match blocks from a Cricbuzz scores page."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    matches = []

    # Each match block lives in a div with class cb-lv-main
    blocks = soup.find_all("div", class_="cb-col cb-col-100 cb-plyr-tbody cb-rank-hdr cb-lv-main")

    for block in blocks:
        match = _extract_match(block)
        if match:
            matches.append(match)

    return matches


def _extract_match(block):
    """Extract match details from a single match block."""
    try:
        # Series / tour name
        series_tag = block.find("div", class_="cb-lv-scrs-col")
        series = series_tag.get_text(strip=True) if series_tag else ""

        # Match header (teams)
        header_tag = block.find("a", class_="cb-lv-scrs-well-live") or \
                     block.find("a", class_="cb-lv-scrs-well")
        if not header_tag:
            # Try any anchor inside cb-hmscg-tm-nm
            team_tags = block.find_all("div", class_="cb-hmscg-tm-nm")
            teams = " vs ".join(t.get_text(strip=True) for t in team_tags) if team_tags else ""
        else:
            teams = header_tag.get_text(strip=True)

        # Score lines
        score_tags = block.find_all("div", class_="cb-hmscg-tm-nm")
        # Try score divs
        bat_score = block.find("div", class_="cb-hmscg-bat-txt")
        bowl_score = block.find("div", class_="cb-hmscg-bwl-txt")

        score = ""
        if bat_score:
            score = bat_score.get_text(strip=True)
        if bowl_score and bowl_score.get_text(strip=True):
            score += "  |  " + bowl_score.get_text(strip=True)

        # Match status / result text
        status_tag = block.find("div", class_="cb-text-live") or \
                     block.find("div", class_="cb-text-complete") or \
                     block.find("div", class_="cb-text-stumps") or \
                     block.find("div", class_="cb-text-inprogress")
        status = status_tag.get_text(strip=True) if status_tag else ""

        # Is it live?
        is_live = bool(block.find("div", class_="cb-text-live") or
                       block.find("div", class_="cb-text-inprogress"))

        return {
            "series": series,
            "teams": teams,
            "score": score,
            "status": status,
            "is_live": is_live,
        }

    except Exception:
        return None


def get_live_matches():
    """Return all currently live matches."""
    return _parse_matches(LIVE_URL)


def get_recent_matches():
    """Return recently completed matches."""
    return _parse_matches(RECENT_URL)


def get_upcoming_matches():
    """Return upcoming scheduled matches."""
    return _parse_matches(UPCOMING_URL)


def get_all_matches():
    """Return live + recent + upcoming matches combined."""
    live = get_live_matches()
    recent = get_recent_matches()
    upcoming = get_upcoming_matches()
    return {"live": live, "recent": recent, "upcoming": upcoming}