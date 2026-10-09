import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import zipfile
from download_counts import summarize
from update_engine import UpdateError, replace_and_restart, sha256_file
from updater import (check_for_updates, select_windows_asset, download_windows_update,
                     extract_executable, monitor_updates, CHECK_INTERVAL)
from window_visibility import ensure_bar_visible

def release(content=b"", digest=None):
    return {"tag_name": "v9.0.0", "html_url": "https://github.com/mabs7/cricket-tray/releases/tag/v9.0.0",
            "assets": [{"name": "PakCricket-Windows.zip", "size": len(content),
                        "digest": digest or "sha256:" + hashlib.sha256(content).hexdigest(),
                        "browser_download_url": "https://github.com/mabs7/cricket-tray/releases/download/v9.0.0/PakCricket-Windows.zip"}]}

def archive(name="PakCricket.exe", data=b"MZnew executable"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as target:
        target.writestr(name, data)
    return output.getvalue()

class DownloadTests(unittest.TestCase):
    def info(self, content):
        data = release(content)
        return dict(data, latest_version=data["tag_name"], repository="mabs7/cricket-tray")

    def test_release_check_selects_new_stable_version(self):
        response = Mock()
        response.json.return_value = release(archive())
        with patch("updater.requests.get", return_value=response):
            self.assertTrue(check_for_updates("v2.7.0", "mabs7/cricket-tray")["update_available"])
            response.json.return_value["prerelease"] = True
            self.assertFalse(check_for_updates("v2.7.0", "mabs7/cricket-tray")["update_available"])

    def test_untrusted_release_url_is_rejected(self):
        response = Mock()
        data = release(archive())
        data["html_url"] = "https://evil.example/update"
        response.json.return_value = data
        with patch("updater.requests.get", return_value=response):
            result = check_for_updates("v2.7.0", "mabs7/cricket-tray")
        self.assertFalse(result["update_available"])
        self.assertTrue(result["error"])

    def test_asset_requires_digest_and_correct_repository(self):
        info = self.info(archive())
        info["assets"][0]["digest"] = None
        with self.assertRaises(UpdateError):
            select_windows_asset(info)
        info = self.info(archive())
        info["assets"][0]["browser_download_url"] = "https://github.com/other/repo/releases/download/v9.0.0/PakCricket-Windows.zip"
        with self.assertRaises(UpdateError):
            select_windows_asset(info)

    def test_verified_download_extracts_expected_file(self):
        content = archive()
        response = Mock()
        response.url = "https://release-assets.githubusercontent.com/download"
        response.iter_content.return_value = [content[:20], content[20:]]
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as directory, patch("updater.requests.get", return_value=context):
            progress = []
            executable = download_windows_update(self.info(content), directory, progress.append)
            self.assertEqual(executable.read_bytes(), b"MZnew executable")
            self.assertEqual(progress[-1], 100)

    def test_corrupted_download_is_not_extracted(self):
        content = archive()
        response = Mock(url="https://github.com/download")
        response.iter_content.return_value = [content[:-1] + b"X"]
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as directory, patch("updater.requests.get", return_value=context):
            with self.assertRaises(UpdateError):
                download_windows_update(self.info(content), directory)
            self.assertFalse((Path(directory) / "PakCricket.exe").exists())

    def test_archive_traversal_and_non_executable_rejected(self):
        for content in (archive("../PakCricket.exe"), archive(data=b"not an exe")):
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "download.zip"
                source.write_bytes(content)
                with self.assertRaises(UpdateError):
                    extract_executable(source, Path(directory) / "incoming.exe")

    def test_periodic_check_can_be_woken_manually(self):
        stop, request = threading.Event(), Mock()
        delivered = []
        def wait(seconds):
            self.assertEqual(seconds, CHECK_INTERVAL)
            if len(delivered) == 2:
                stop.set()
        request.wait.side_effect = wait
        with patch("updater.check_for_updates", return_value={"update_available": False}) as check:
            monitor_updates("v2.7.0", "mabs7/cricket-tray", delivered.append, stop, request)
        self.assertEqual(check.call_count, 2)

class ReplacementTests(unittest.TestCase):
    def setup_plan(self, directory):
        target = Path(directory) / "PAK Cricket.exe"
        target.write_bytes(b"MZold")
        stage = Path(directory) / ".pakcricket-update-test"
        stage.mkdir()
        incoming = stage / "PakCricket.exe"
        incoming.write_bytes(b"MZnew")
        plan = {"target": str(target), "incoming": str(incoming), "backup": str(Path(directory) / "previous.exe"), "sha256": sha256_file(incoming), "pid": 123}
        return plan, stage / "plan.json", target

    def test_success_keeps_backup_and_launches_after_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            plan, path, target = self.setup_plan(directory)
            waited = []
            def launch(exe, args):
                self.assertEqual(waited, [123])
                (path.parent / "ready").write_text("ok")
                return Mock()
            backup = replace_and_restart(plan, path, wait=waited.append, launch=launch)
            self.assertEqual(target.read_bytes(), b"MZnew")
            self.assertEqual(backup.read_bytes(), b"MZold")

    def test_failed_start_rolls_back_and_restarts_old_version(self):
        with tempfile.TemporaryDirectory() as directory:
            plan, path, target = self.setup_plan(directory)
            child = Mock()
            child.poll.return_value = 1
            launch = Mock(return_value=child)
            with self.assertRaises(UpdateError):
                replace_and_restart(plan, path, wait=lambda _: None, launch=launch, health_timeout=0)
            self.assertEqual(target.read_bytes(), b"MZold")
            self.assertEqual(launch.call_count, 2)

    def test_tampering_does_not_touch_original(self):
        with tempfile.TemporaryDirectory() as directory:
            plan, path, target = self.setup_plan(directory)
            Path(plan["incoming"]).write_bytes(b"MZchanged")
            with self.assertRaises(UpdateError):
                replace_and_restart(plan, path, wait=Mock(), launch=Mock())
            self.assertEqual(target.read_bytes(), b"MZold")

    def test_invalid_stage_cannot_replace_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            plan, path, target = self.setup_plan(directory)
            plan["target"] = str(Path(directory) / "other" / "app.exe")
            with self.assertRaises(UpdateError):
                replace_and_restart(plan, path, wait=Mock(), launch=Mock())
            self.assertEqual(target.read_bytes(), b"MZold")

class VisibilityTests(unittest.TestCase):
    def test_intentionally_hidden_bar_is_not_restored(self):
        root = Mock()
        ensure_bar_visible(root, hidden=True, topmost=True)
        root.winfo_id.assert_not_called()

    def test_windows_topmost_does_not_activate(self):
        root, api = Mock(), Mock()
        api.GetAncestor.return_value = 123
        api.IsWindowVisible.return_value = False
        api.IsIconic.return_value = False
        api.SetWindowPos.return_value = 1
        with patch("window_visibility.sys.platform", "win32"), patch("window_visibility.ctypes.WinDLL", return_value=api, create=True):
            ensure_bar_visible(root, hidden=False, topmost=True)
        api.ShowWindow.assert_called_once_with(123, 4)
        self.assertEqual(api.SetWindowPos.call_args.args[-1] & 0x10, 0x10)

    def test_disabled_topmost_does_not_override_preference(self):
        root, api = Mock(), Mock()
        api.IsWindowVisible.return_value = True
        api.IsIconic.return_value = False
        with patch("window_visibility.sys.platform", "win32"), patch("window_visibility.ctypes.WinDLL", return_value=api, create=True):
            ensure_bar_visible(root, hidden=False, topmost=False)
        api.SetWindowPos.assert_not_called()

    def test_download_report_counts_assets_not_people(self):
        self.assertEqual(summarize([{"tag_name": "v2.7.0", "assets": [{"name": "PakCricket-Windows.zip", "download_count": 2}, {"name": "PakCricket-Mac.zip", "download_count": 1}]}]), [("v2.7.0", 2, 1)])

if __name__ == "__main__":
    unittest.main()
