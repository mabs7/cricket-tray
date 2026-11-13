"""Portable Windows replacement helper. Uses only the standard library."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

class UpdateError(RuntimeError):
    pass

def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_plan(plan, plan_path):
    stage = Path(plan_path).resolve().parent
    target = Path(plan["target"]).resolve()
    incoming = Path(plan["incoming"]).resolve()
    backup = Path(plan["backup"]).resolve()
    if not stage.name.startswith(".pakcricket-update-") or stage.parent != target.parent:
        raise UpdateError("Invalid update staging directory")
    if incoming != stage / "PakCricket.exe" or backup.parent != target.parent or backup == target:
        raise UpdateError("Invalid update paths")
    if target.suffix.lower() != ".exe" or not target.is_file() or backup.exists():
        raise UpdateError("Target unavailable or backup already exists")
    if sha256_file(incoming) != plan["sha256"]:
        raise UpdateError("The staged executable failed verification")
    return stage, target, incoming, backup

def wait_for_parent(pid, timeout=60):
    if type(pid) is not int or pid <= 0:
        raise UpdateError("Invalid parent process ID")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        if ctypes.get_last_error() == 87:  # process has already exited
            return
        raise UpdateError("Could not wait for the running app to close")
    try:
        if kernel.WaitForSingleObject(handle, timeout * 1000) != 0:
            raise UpdateError("The running app did not close in time")
    finally:
        kernel.CloseHandle(handle)

def launch_app(executable, args=()):
    environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    return subprocess.Popen([str(executable), *map(str, args)], cwd=str(executable.parent),
                            env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

def stop_process(child):
    # PyInstaller's one-file app has a bootloader parent and a GUI child.
    # Stop the owned process tree before restoring the locked executable.
    if sys.platform == "win32":
        subprocess.run([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"),
                        "/PID", str(child.pid), "/T", "/F"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass

def _replace_with_retry(source, destination, timeout=15):
    """Replace destination with source, retrying transient Windows file locks."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            source.replace(destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise UpdateError("The executable is still locked; the original app was preserved")
            time.sleep(0.5)

def replace_and_restart(plan, plan_path, wait=wait_for_parent, launch=launch_app, health_timeout=45):
    stage, target, incoming, backup = validate_plan(plan, plan_path)
    wait(int(plan["pid"]))
    if sha256_file(incoming) != plan["sha256"]:
        raise UpdateError("The staged executable failed verification before replacement")
    # Windows may keep the executable locked briefly during one-file shutdown.
    _replace_with_retry(target, backup, timeout=15)
    child = None
    try:
        _replace_with_retry(incoming, target, timeout=15)
        ready = stage / "ready"
        ready.unlink(missing_ok=True)
        child = launch(target, ("--update-health", stage))
        deadline = time.monotonic() + health_timeout
        while not ready.exists():
            if child.poll() is not None or time.monotonic() >= deadline:
                raise UpdateError("The new app did not start successfully")
            time.sleep(0.25)
    except Exception:
        if child and child.poll() is None:
            try:
                stop_process(child)
            except Exception:
                pass
        # Retain the failed new executable in staging, then restore the backup.
        if target.exists():
            try:
                _replace_with_retry(target, stage / "failed-version.exe", timeout=15)
            except Exception:
                pass
        if backup.exists():
            _replace_with_retry(backup, target, timeout=15)
            launch(target)
        raise
    return backup

def apply_update(plan_path):
    path = Path(plan_path).resolve()
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
        replace_and_restart(plan, path)
        (path.parent / "complete").write_text("ok", encoding="utf-8")
        return 0
    except Exception as exc:
        try:
            (path.parent / "update-error.txt").write_text(str(exc), encoding="utf-8")
        except OSError:
            pass
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
        user32.MessageBoxW.restype = ctypes.c_int
        user32.MessageBoxW(None, f"The update could not be completed.\n\n{exc}\n\nYour previous executable has been kept.", "PAK Cricket update", 0x10)
        return 1

def confirm_update(stage, executable):
    stage = Path(stage).resolve()
    if stage.name.startswith(".pakcricket-update-") and stage.parent == Path(executable).resolve().parent:
        (stage / "ready").write_text("ok", encoding="utf-8")

def cleanup_update(stage, executable):
    stage = Path(stage).resolve()
    if not stage.name.startswith(".pakcricket-update-") or stage.parent != Path(executable).resolve().parent or not (stage / "complete").exists():
        return
    for name in ("download.zip", "updater-helper.exe", "plan.json", "ready", "complete"):
        try:
            (stage / name).unlink(missing_ok=True)
        except OSError:
            return
    try:
        stage.rmdir()  # Never recursively remove unknown files.
    except OSError:
        pass

def cleanup_old_updates(executable, skip_stage=None, max_age=3600):
    """Conservatively prune stale staging folders and older backups in the app directory."""
    exe = Path(executable).resolve()
    folder = exe.parent
    skip = Path(skip_stage).resolve() if skip_stage else None
    cutoff = time.time() - max_age
    known_files = ("download.zip", "PakCricket.exe", "updater-helper.exe", "plan.json",
                   "ready", "complete", "failed-version.exe", "update-error.txt")
    for entry in folder.glob(".pakcricket-update-*"):
        try:
            if not entry.is_dir() or (skip and entry.resolve() == skip):
                continue
            if entry.stat().st_mtime > cutoff and not (entry / "complete").exists():
                continue
            for name in known_files:
                (entry / name).unlink(missing_ok=True)
            entry.rmdir()
        except OSError:
            pass
    backups = sorted(folder.glob(f"{exe.stem}.previous-*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old_backup in backups[1:]:
        try:
            old_backup.unlink(missing_ok=True)
        except OSError:
            pass
