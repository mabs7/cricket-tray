import requests

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
        
        # Simple string comparison for version tags assuming format like 'vX.Y.Z'
        if latest_version and latest_version != current_version:
            # Check if latest version is actually greater (simple check)
            # In Python, 'v2.6.2' > 'v2.6.1' works lexicographically for well-formed semver
            if latest_version > current_version:
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
