"""Small per-user preference file; scores are never written to disk."""
import json
import os
from pathlib import Path
import tempfile
from filter import TEAMS

DEFAULTS = {"position": None, "hidden": False, "topmost": True, "text_size": 10,
            "selected": None, "notified_version": None, "scope": None, "team": None}

def settings_path():
    root = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    return root / "PakCricket" / "settings.json"

def load_settings(path=None):
    values = dict(DEFAULTS)
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return values
        for key in ("hidden", "topmost"):
            if isinstance(data.get(key), bool):
                values[key] = data[key]
        if type(data.get("text_size")) is int and 9 <= data["text_size"] <= 16:
            values["text_size"] = data["text_size"]
        position = data.get("position")
        if isinstance(position, list) and len(position) == 2 and all(type(n) is int for n in position):
            values["position"] = position
        if isinstance(data.get("selected"), str) and len(data["selected"]) <= 64:
            values["selected"] = data["selected"]
        if isinstance(data.get("notified_version"), str) and len(data["notified_version"]) <= 64:
            values["notified_version"] = data["notified_version"]
        if data.get("scope") in {"team", "international"}:
            values["scope"] = data["scope"]
        team = data.get("team")
        if isinstance(team, str) and team.strip() in TEAMS:
            values["team"] = team.strip()
    except (OSError, ValueError, TypeError):
        pass
    return values

def save_settings(values, path=None):
    tmp_path = None
    try:
        target = path or settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=f"{target.stem}.", suffix=".tmp", delete=False) as handle:
            tmp_path = Path(handle.name)
            handle.write(json.dumps(values))
        tmp_path.replace(target)
        tmp_path = None
    except OSError:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
