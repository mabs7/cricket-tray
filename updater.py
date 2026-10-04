import requests
import re

def version_tuple(value):
    found = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", value)
    return tuple(int(n or 0) for n in found.groups()) if found else None

def check_for_updates(current_version, github_repo):
    """
    Checks the GitHub API for the latest release.
    Returns a dict with 'update_available', 'latest_version', and 'release_url'.
    """
    url = f"https://api.github.com/repos/{github_repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Cricket-Tray-Updater"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        latest_version = data.get("tag_name", "")
        release_url = data.get("html_url", "")
        
        # Compare numeric release components; prereleases are not upgrade prompts.
        latest, current = version_tuple(latest_version), version_tuple(current_version)
        if latest and current:
            if latest > current:
                return {
                    "update_available": True,
                    "latest_version": latest_version,
                    "release_url": release_url
                }
    except Exception:
        pass # Silently fail if no internet or GitHub API limit reached
        
    return {
        "update_available": False,
        "latest_version": current_version,
        "release_url": ""
    }
