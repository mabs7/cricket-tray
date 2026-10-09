"""Maintainer report of GitHub release downloads; no widget telemetry."""
import sys
import requests
from version import GITHUB_REPO

def summarize(releases):
    rows = []
    for release in releases:
        if release.get("draft"):
            continue
        windows, mac = 0, 0
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name in {"PakCricket-Windows.zip", "PakCricket.Windows.zip"}:
                windows += asset.get("download_count", 0)
            elif name in {"PakCricket-Mac.zip", "PakCricket.zip"}:
                mac += asset.get("download_count", 0)
        rows.append((release["tag_name"], windows, mac))
    return rows

def get_download_counts(repo=GITHUB_REPO):
    releases, page = [], 1
    while True:
        response = requests.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 100, "page": page},
                                headers={"User-Agent": "PakCricket-download-report"}, timeout=(5, 15))
        response.raise_for_status()
        batch = response.json()
        releases.extend(batch)
        if len(batch) < 100:
            return summarize(releases)
        page += 1

def main():
    try:
        rows = get_download_counts()
    except Exception as exc:
        print(f"Could not fetch download counts: {exc}", file=sys.stderr)
        return 1
    print(f"{'Release':<16} {'Windows':>8} {'macOS':>8} {'Total':>8}")
    for version, windows, mac in rows:
        print(f"{version:<16} {windows:>8} {mac:>8} {windows + mac:>8}")
    windows, mac = sum(r[1] for r in rows), sum(r[2] for r in rows)
    print(f"{'All releases':<16} {windows:>8} {mac:>8} {windows + mac:>8}")
    print("Downloads are not unique users or active installations.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
