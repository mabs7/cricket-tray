"""Verify the real frozen Windows helper and startup handshake on disposable copies.

Run after building dist/PakCricket.exe. This briefly launches a test score bar.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from update_engine import launch_app, sha256_file

def main():
    binary = Path(__file__).resolve().parents[1] / "dist" / "PakCricket.exe"
    if not binary.is_file():
        raise RuntimeError("Build dist/PakCricket.exe first")
    work = Path(tempfile.mkdtemp(prefix="packaged-update-", dir=binary.parent))
    target = work / f"PakCricket-smoke-{work.name[-8:]}.exe"
    stage = work / ".pakcricket-update-smoke"
    stage.mkdir()
    incoming, helper = stage / "PakCricket.exe", stage / "updater-helper.exe"
    for destination in (target, incoming, helper):
        shutil.copy2(binary, destination)
    # All test state and logs stay in the disposable directory.
    os.environ["APPDATA"] = str(work / "preferences")
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1)"])
    plan = {"target": str(target), "incoming": str(incoming), "backup": str(work / "previous.exe"), "pid": parent.pid, "sha256": sha256_file(incoming)}
    plan_path = stage / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    process = launch_app(helper, ("--apply-update", plan_path))
    try:
        deadline = time.monotonic() + 75
        while not (stage / "complete").exists():
            if (stage / "update-error.txt").exists():
                raise RuntimeError((stage / "update-error.txt").read_text())
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Packaged helper did not complete its startup handshake")
            time.sleep(0.5)
        assert (stage / "ready").exists()
        assert (work / "previous.exe").is_file()
        assert sha256_file(target) == sha256_file(binary)
        process.wait(timeout=15)
        print("Packaged updater passed: parent wait, file replacement, backup, independent restart, GUI startup handshake")
    finally:
        # The unique temporary executable name cannot match the user's normal app.
        subprocess.run([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"), "/IM", target.name, "/T", "/F"], capture_output=True)
        if process.poll() is None:
            subprocess.run([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"), "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        parent.wait(timeout=10)
        time.sleep(1)
        # Remove only files created by this test, after checking the resolved scope.
        if work.resolve().parent == binary.parent.resolve() and work.name.startswith("packaged-update-"):
            shutil.rmtree(work)

if __name__ == "__main__":
    main()
