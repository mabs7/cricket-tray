import re
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

MATCH_HREF = re.compile(r"^/live-cricket-scores/\d+/")

# Mini scorecard links: "LHQ vs HYDK - Preview" or "RSA vs NZ - RSA won"
# These have ' - ' in them and use abbreviations
MINI_PATTERN = re.compile(r"^[A-Z]{2,5}\s+vs\s+[A-Z]{2,5}\s+-\s+")

# Status suffixes to strip from team names
STRIP_SUFFIX = re.compile(
    r"\s*\d*(st|nd|rd|th)?\s*(Match|T20I?|ODI|Test|Final|Semi\s*Final|Qualifier|Preview|Cancelled|Abandoned).*",
    re.I,
)


def _fetch_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException:
        return None


def _parse_matches(url):
    soup = _fetch_soup(url)
    if not soup:
        return []

    matches = []
    # Use href as key to keep best version of each match
    match_map = {}

    all_links = soup.find_all("a", href=MATCH_HREF)

    for link in all_links:
        href = link.get("href", "")
        link_text = link.get_text(separator=" ", strip=True)

        # Skip empty or very short
        if len(link_text) < 5:
            continue

        # Skip "Live Score |" links
        if "Live Score" in link_text:
            continue

        # Skip mini scorecards at top (e.g. "LHQ vs HYDK - Preview")
        if MINI_PATTERN.match(link_text):
            continue

        # Skip venue/score dump links (contain bullet •)
        if "•" in link_text:
            continue

        # Clean team names
        teams = STRIP_SUFFIX.sub("", link_text).strip()
        if not teams or len(teams) < 5:
            continue

        # Get series name from nearest preceding series link
        series = ""
        series_link = link.find_previous("a", href=re.compile(r"^/cricket-series/"))
        if series_link:
            series = series_link.get_text(strip=True)

        # Detect if PSL from href
        is_psl = "pakistan-super-league" in href or "psl" in href.lower()

        # Detect live/status from link text and href
        is_live = False
        status = ""
        lt = link_text.lower()
        ht = href.lower()
        if "preview" in lt or "preview" in ht:
            status = "Preview — match not started"
        elif "won" in lt or "lost" in lt or "draw" in lt:
            status = link_text.split(" - ")[-1].strip() if " - " in link_text else ""
        elif "live" in lt or "live" in ht:
            is_live = True
            status = "🔴 Live"

        # Store — prefer the full name version over abbreviation version
        # Full name version has spaces and longer text
        if href not in match_map or len(teams) > len(match_map[href]["teams"]):
            match_map[href] = {
                "teams": teams,
                "score": "",
                "status": status,
                "series": series,
                "is_live": is_live,
                "is_psl": is_psl,
                "href": href,
            }

    # Now fetch scores for each match individually
    for href, match in match_map.items():
        _enrich_with_score(match)

    return list(match_map.values())


def _enrich_with_score(match):
    """Try to extract score from the match card on the list page."""
    # Score comes from the venue/score dump link we skipped earlier
    # It's embedded in href text like:
    # "Qualifier • Gqeberha Warriors WAR 204 (49.3) Titans TIT 209-6 (43.1) Titans won by 4 wkts"
    # We already have that data — parse it from series context
    # For now leave score empty; it will be populated when match is live
    pass


def get_live_matches():
    return _parse_matches(LIVE_URL)


def get_recent_matches():
    return _parse_matches(RECENT_URL)


def get_upcoming_matches():
    return _parse_matches(UPCOMING_URL)


def get_all_matches():
    return {
        "live": get_live_matches(),
        "recent": get_recent_matches(),
        "upcoming": get_upcoming_matches(),
    }
