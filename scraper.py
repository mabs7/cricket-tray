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
MINI_PATTERN = re.compile(r"^[A-Z]{2,5}\s+vs\s+[A-Z]{2,5}\s+-\s+")
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


def _parse_matches(url, page_type="live"):
    """
    page_type: 'live', 'recent', 'upcoming'
    Only matches on the LIVE page can be is_live=True.
    """
    soup = _fetch_soup(url)
    if not soup:
        return []

    match_map = {}

    for link in soup.find_all("a", href=MATCH_HREF):
        href = link.get("href", "")
        link_text = link.get_text(separator=" ", strip=True)

        if len(link_text) < 5:
            continue
        if "Live Score" in link_text:
            continue
        if MINI_PATTERN.match(link_text):
            continue
        if "•" in link_text:
            continue

        teams = STRIP_SUFFIX.sub("", link_text).strip()
        if not teams or len(teams) < 5:
            continue

        # Series name
        series = ""
        series_link = link.find_previous("a", href=re.compile(r"^/cricket-series/"))
        if series_link:
            series = series_link.get_text(strip=True)

        # PSL detection from href
        is_psl = "pakistan-super-league" in href or "psl" in href.lower()

        # Status from link text only (not href — avoids false "live" from nav)
        lt = link_text.lower()
        status = ""
        if "preview" in lt:
            status = "Preview"
        elif "won" in lt:
            status = (
                link_text.split(" - ")[-1].strip() if " - " in link_text else "Result"
            )
        elif "lost" in lt:
            status = (
                link_text.split(" - ")[-1].strip() if " - " in link_text else "Result"
            )
        elif "abandon" in lt:
            status = "Abandoned"
        elif "stumps" in lt:
            status = "Stumps"
        elif "opt to" in lt:
            status = link_text.split(" - ")[-1].strip() if " - " in link_text else ""

        # is_live only if we're on the live page AND no preview/result status
        is_live = (page_type == "live") and (
            status not in ["Preview", "Result", "Abandoned"]
        )

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

    # Only fetch individual scores for matches that are actually live
    for href, match in match_map.items():
        if match["is_live"]:
            _enrich_with_score(match)

    return list(match_map.values())


def _enrich_with_score(match):
    """Fetch individual match page to get live score. Only called for live matches."""
    href = match.get("href", "")
    if not href:
        return

    try:
        url = f"https://www.cricbuzz.com{href}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        joined = " ".join(lines)

        # Score is split across lines like:
        # "LHQ 199 / 6 ( 20 ) HYDK 130 ( 20 )"
        # After joining, pattern is: TEAM digits / digits ( digits ) ...
        score_pattern = re.compile(
            r"([A-Z]{2,5})\s+(\d+)\s*/\s*(\d+)\s*\(\s*([\d.]+)\s*\)"
        )
        scores = score_pattern.findall(joined)

        if scores:
            parts = []
            for team, runs, wkts, overs in scores:
                parts.append(f"{team} {runs}/{wkts} ({overs} ov)")
            match["score"] = "  |  ".join(parts)

            # CRR for live matches
            crr = re.search(r"CRR\s*:?\s*([\d.]+)", joined)
            if crr:
                match["score"] += f"  CRR: {crr.group(1)}"
        else:
            # Try without wickets (all out): TEAM digits ( digits )
            score_pattern2 = re.compile(r"([A-Z]{2,5})\s+(\d+)\s*\(\s*([\d.]+)\s*\)")
            scores2 = score_pattern2.findall(joined)
            if scores2:
                parts = []
                for team, runs, overs in scores2:
                    parts.append(f"{team} {runs} ({overs} ov)")
                match["score"] = "  |  ".join(parts)

        # Find result/status from individual lines (not joined) to avoid nav pollution
        # Look for short result line — must be under 60 chars
        status_found = False
        for line in lines:
            ll = line.lower()
            # Result line
            if (
                "won by" in ll
                or "match drawn" in ll
                or "tied" in ll
                or "no result" in ll
            ) and len(line) < 80:
                match["status"] = line.strip()
                match["is_live"] = False
                status_found = True
                break
            # Live status
            if (
                any(
                    kw in ll
                    for kw in [
                        "opt to bat",
                        "opt to field",
                        "innings break",
                        "stumps",
                        "rain",
                        "drinks",
                    ]
                )
                and 5 < len(line) < 60
            ):
                match["status"] = line.strip()
                status_found = True
                break

        # If no score found, match hasn't started
        if not match.get("score"):
            match["is_live"] = False
            if not status_found:
                match["status"] = "Preview"

    except Exception:
        pass


def get_live_matches():
    return _parse_matches(LIVE_URL, page_type="live")


def get_recent_matches():
    return _parse_matches(RECENT_URL, page_type="recent")


def get_upcoming_matches():
    return _parse_matches(UPCOMING_URL, page_type="upcoming")


def get_all_matches():
    return {
        "live": get_live_matches(),
        "recent": get_recent_matches(),
        "upcoming": get_upcoming_matches(),
    }
