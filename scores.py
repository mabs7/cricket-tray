"""Thread-safe refresh snapshots shared by the Windows and macOS interfaces."""
import copy
import threading
import time
from filter import get_match_state
from scraper import get_all_matches

INTERVALS = {"live": 45, "paused": 120, "today": 300, "scheduled": 300, "completed": 1800, "none": 1800}
STUMPS_INTERVAL = 300  # Overnight in a multi-day match: check at the match-day cadence.

def refresh_interval(state, matches):
    if state == "paused":
        paused = [m for m in matches if m.get("state") == "paused"]
        if paused and all(m.get("phase") == "Stumps" for m in paused):
            return STUMPS_INTERVAL
    return INTERVALS[state]

class ScoreService:
    def __init__(self, fetcher=get_all_matches, scope=None, team=None):
        self.fetcher = fetcher
        self.scope = scope
        self.team = team
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.pools = {"live": [], "recent": [], "upcoming": []}
        self.data = {"state": "none", "matches": [], "updated_at": None,
                     "errors": {}, "refreshing": False, "revision": 0}

    def set_filter(self, scope, team=None):
        with self.lock:
            self.scope = scope
            self.team = team
            if self.data["updated_at"] is not None or any(self.pools.values()):
                state, matches = get_match_state(self.pools, scope=self.scope, team=self.team)
                self.data.update(state=state, matches=matches, revision=self.data["revision"] + 1)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def refresh(self):
        with self.lock:
            self.data["refreshing"] = True
        try:
            result = self.fetcher()
            errors = result.get("errors", {})
        except Exception as exc:
            result, errors = {}, {"fetch": str(exc)}
        with self.lock:
            # Commit a complete refresh atomically. Partial failures preserve the
            # previous snapshot so conflicting pools cannot resurrect old matches.
            if not errors:
                previous = {m["id"]: m for m in self.data["matches"]}
                for name in self.pools:
                    for match in result.get(name, []):
                        old = previous.get(match["id"])
                        if old and old.get("score") and not match.get("score") and match.get("state") in {"live", "paused", "unknown"}:
                            errors = {"validation": "A previously available score disappeared; retaining the last successful refresh"}
                            break
            if not errors:
                self.pools = {name: result.get(name, []) for name in self.pools}
                state, matches = get_match_state(self.pools, scope=self.scope, team=self.team)
                self.data.update(state=state, matches=matches, updated_at=time.time())
            self.data.update(errors=errors, refreshing=False, revision=self.data["revision"] + 1)
        return 60 if errors else refresh_interval(self.data["state"], self.data["matches"])

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            self.wake.clear()
            interval = self.refresh()
            self.wake.wait(interval)

    def request_refresh(self):
        self.wake.set()

    def stop(self):
        self.stop_event.set()
        self.wake.set()

def freshness(snapshot):
    if snapshot["refreshing"]:
        return "Refreshing…"
    stamp = snapshot["updated_at"]
    if snapshot["errors"]:
        age = max(0, int(time.time() - stamp)) if stamp else 0
        return f"Updates delayed · last success {age // 60}m {age % 60}s ago" if stamp else "Unable to fetch scores · retrying"
    if stamp is None:
        return "Fetching scores…"
    age = max(0, int(time.time() - stamp))
    return f"Updated {age}s ago" if age < 60 else f"Updated {age // 60}m ago"
