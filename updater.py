"""GitHub release checks and verified, user-initiated portable Windows updates."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
import zipfile
import requests
from update_engine import UpdateError, sha256_file

CHECK_INTERVAL = 6 * 60 * 60
MAX_DOWNLOAD = 150 * 1024 * 1024
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "Cricket-Tray-Updater"}

def version_tuple(value):
    found = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", value or "")
    return tuple(int(n or 0) for n in found.groups()) if found else None

def trusted_url(url, repository, tag, asset=None):
    parsed = urlparse(url)
    expected = f"/{repository}/releases/" + (f"download/{tag}/{asset}" if asset else f"tag/{tag}")
    return parsed.scheme == "https" and parsed.netloc == "github.com" and parsed.path == expected and not parsed.query and not parsed.fragment

def check_for_updates(current_version, github_repo):
    result = {"update_available": False, "latest_version": current_version, "release_url": "", "assets": [], "error": ""}
    try:
        response = requests.get(f"https://api.github.com/repos/{github_repo}/releases/latest", headers=HEADERS, timeout=(5, 15))
        response.raise_for_status()
        data = response.json()
        tag = data.get("tag_name", "")
        latest, current = version_tuple(tag), version_tuple(current_version)
        if latest and current and latest > current and not data.get("draft") and not data.get("prerelease"):
            if not trusted_url(data.get("html_url", ""), github_repo, tag):
                raise UpdateError("Unrecognized release URL")
            result.update(update_available=True, latest_version=tag, release_url=data["html_url"], assets=data.get("assets", []), repository=github_repo)
    except Exception as exc:
        result["error"] = str(exc)
        logging.warning("Update check failed: %s", exc)
    return result

def monitor_updates(current_version, repo, deliver, stop, request):
    while not stop.is_set():
        request.clear()
        deliver(check_for_updates(current_version, repo))
        # Retry a failed check later, including apps left open throughout a match.
        request.wait(CHECK_INTERVAL)

def select_windows_asset(info):
    asset = next((a for a in info.get("assets", []) if a.get("name") == "PakCricket-Windows.zip"), None)
    if not asset or not trusted_url(asset.get("browser_download_url", ""), info["repository"], info["latest_version"], asset["name"]):
        raise UpdateError("The Windows download is not available yet")
    digest = asset.get("digest") or ""
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise UpdateError("This release has no verifiable download digest; use the release page instead")
    if not 0 < asset.get("size", 0) <= MAX_DOWNLOAD:
        raise UpdateError("Unexpected release size")
    return asset

def extract_executable(archive, destination):
    """Extract only the expected root executable; never extract arbitrary paths."""
    with zipfile.ZipFile(archive) as source:
        files = [i for i in source.infolist() if not i.is_dir()]
        if len(files) != 1 or files[0].filename != "PakCricket.exe" or not 0 < files[0].file_size <= MAX_DOWNLOAD:
            raise UpdateError("The release archive has an unexpected layout")
        if (files[0].external_attr >> 16) & 0o170000 == 0o120000:
            raise UpdateError("The executable cannot be a symbolic link")
        with source.open(files[0]) as incoming, Path(destination).open("wb") as output:
            shutil.copyfileobj(incoming, output)
    with Path(destination).open("rb") as source:
        if source.read(2) != b"MZ":
            raise UpdateError("The download is not a Windows executable")

def download_windows_update(info, stage, progress=lambda _: None):
    asset = select_windows_asset(info)
    archive = Path(stage) / "download.zip"
    digest, received = hashlib.sha256(), 0
    with requests.get(asset["browser_download_url"], stream=True, timeout=(10, 30)) as response:
        response.raise_for_status()
        if urlparse(response.url).scheme != "https":
            raise UpdateError("The download redirected to an insecure URL")
        with archive.open("wb") as output:
            for chunk in response.iter_content(256 * 1024):
                if not chunk:
                    continue
                received += len(chunk)
                if received > MAX_DOWNLOAD or received > asset["size"]:
                    raise UpdateError("The download exceeded its expected size")
                output.write(chunk)
                digest.update(chunk)
                progress(min(100, received * 100 // asset["size"]))
    if received != asset["size"] or digest.hexdigest() != asset["digest"].split(":", 1)[1].lower():
        raise UpdateError("Download verification failed; the running app was not changed")
    incoming = Path(stage) / "PakCricket.exe"
    extract_executable(archive, incoming)
    return incoming

def prepare_windows_update(info, progress=lambda _: None):
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise UpdateError("In-app replacement is available in the portable Windows .exe. Source runs and macOS use the release page.")
    target = Path(sys.executable).resolve()
    fallback = False
    try:
        stage = Path(tempfile.mkdtemp(prefix=".pakcricket-update-", dir=target.parent))
    except OSError:
        # Download still works when the original app folder cannot be written.
        stage = Path(tempfile.mkdtemp(prefix=".pakcricket-update-"))
        fallback = True
    try:
        incoming = download_windows_update(info, stage, progress)
        if fallback:
            return {"save_as": True, "incoming": str(incoming), "stage": str(stage)}
        helper = stage / "updater-helper.exe"
        shutil.copy2(target, helper)
        plan = {"target": str(target), "incoming": str(incoming), "pid": os.getpid(),
                "backup": str(target.with_name(f"{target.stem}.previous-{stage.name[-8:]}.exe")),
                "sha256": sha256_file(incoming)}
        plan_path = stage / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return {"save_as": False, "helper": str(helper), "plan": str(plan_path), "stage": str(stage)}
    except Exception:
        discard_stage(stage)
        raise

def start_update_helper(prepared):
    # List arguments avoid shell interpolation, including paths with spaces.
    environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    return subprocess.Popen([prepared["helper"], "--apply-update", prepared["plan"]],
                            cwd=prepared["stage"], env=environment,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

def discard_stage(stage):
    stage = Path(stage).resolve()
    if not stage.name.startswith(".pakcricket-update-"):
        return
    for name in ("download.zip", "PakCricket.exe", "updater-helper.exe", "plan.json"):
        try:
            (stage / name).unlink(missing_ok=True)
        except OSError:
            return
    try:
        stage.rmdir()
    except OSError:
        pass
