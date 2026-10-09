"""Small per-user preference file; scores are never written to disk."""
import json
import os
from pathlib import Path

DEFAULTS = {"position": None, "hidden": False, "topmost": True, "text_size": 10, "selected": None, "notified_version": None}

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
        if isinstance(data.get("selected"), str):
            values["selected"] = data["selected"]
        if isinstance(data.get("notified_version"), str):
            values["notified_version"] = data["notified_version"]
    except (OSError, ValueError, TypeError):
        pass
    return values

def save_settings(values, path=None):
    try:
        target = path or settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(values), encoding="utf-8")
        temporary.replace(target)
    except OSError:
        pass
