"""Dependency regression tests. No downloads, pip writes, or live services."""

import copy
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfoNotFoundError

from services.dependencies import DependencyMixin, DependencyService, version_tuple
from utils.dependency_manager import DependencyManager, setup_deno


def installed_details():
    return {
        "ffmpeg": {"installed": True, "version": "7.1.0", "path": "local-ffmpeg"},
        "deno": {"installed": True, "version": "2.10.0", "path": "local-deno"},
        "ytdlp": {"installed": True, "version": "2026.9.1", "path": "yt_dlp_module"},
        "whisper": {"installed": True, "version": "1.2.0", "path": "faster_whisper"},
        "tzdata": {"installed": True, "version": "2026.1", "path": "tzdata"},
    }


class ObservableService(DependencyService):
    def __init__(self, **kwargs):
        super().__init__(online_checks=False, **kwargs)
        self.done = threading.Event()

    def _install(self, *args):
        try:
            super()._install(*args)
        finally:
            self.done.set()


class DependencyInstallerTests(unittest.TestCase):
    @patch("utils.dependency_manager.get_ytdlp_path", return_value="yt_dlp_module")
    @patch.object(DependencyManager, "_module_available", return_value=True)
    @patch("utils.dependency_manager.subprocess.run")
    def test_explicit_update_installs_already_installed_package(self, run, available, resolver):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        manager = DependencyManager()
        with patch.object(sys, "frozen", False, create=True):
            self.assertTrue(manager._install_ytdlp(upgrade=True))
            self.assertTrue(manager._install_whisper(upgrade=True))
        self.assertEqual(run.call_count, 2)
        self.assertIn("--upgrade", run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[0].args[0][-1], "yt-dlp")
        self.assertEqual(run.call_args_list[1].args[0][-1], "faster-whisper")

    @patch.object(DependencyManager, "_module_available", return_value=True)
    @patch("utils.dependency_manager.subprocess.run")
    def test_non_update_does_not_reinstall_available_package(self, run, available):
        self.assertTrue(DependencyManager()._install_whisper())
        run.assert_not_called()

    @patch("utils.dependency_manager.subprocess.run")
    def test_frozen_package_update_never_launches_desktop_executable(self, run):
        manager = DependencyManager()
        with patch.object(sys, "frozen", True, create=True):
            self.assertFalse(manager._install_whisper(upgrade=True))
        self.assertIn("Perbarui aplikasi", manager.last_error)
        run.assert_not_called()

    @patch("utils.dependency_manager.get_ytdlp_path", return_value="selected-yt-dlp")
    @patch("utils.dependency_manager.shutil.which", return_value="selected-yt-dlp")
    @patch("utils.dependency_manager.subprocess.run")
    def test_binary_update_targets_runtime_resolved_binary(self, run, which, resolver):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(sys, "frozen", True, create=True):
            self.assertTrue(DependencyManager()._install_ytdlp(upgrade=True))
        self.assertEqual(run.call_args.args[0], ["selected-yt-dlp", "--update"])

    @patch("utils.dependency_manager.subprocess.run")
    def test_installer_failure_is_returned_with_stderr(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "No disk space")
        manager = DependencyManager()
        with patch.object(sys, "frozen", False, create=True):
            self.assertFalse(manager._install_whisper(upgrade=True))
        self.assertEqual(manager.last_error, "No disk space")

    @patch("utils.dependency_manager.download_file", return_value=True)
    @patch("utils.dependency_manager.extract_zip", return_value=True)
    @patch("utils.dependency_manager.debug_log")
    def test_deno_missing_binary_is_install_failure(self, log, extract, download):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(setup_deno(Path(directory)))

    @patch("utils.dependency_manager.ZoneInfo")
    def test_timezone_health_checks_actual_uncached_zone_files(self, zone):
        zone.no_cache.side_effect = [object(), ZoneInfoNotFoundError("Asia/Makassar")]
        self.assertFalse(DependencyManager._timezone_available())
        self.assertEqual([call.args[0] for call in zone.no_cache.call_args_list], ["UTC", "Asia/Makassar"])

    @patch.object(DependencyManager, "_install_package")
    @patch.object(DependencyManager, "_timezone_available", return_value=True)
    def test_existing_timezone_database_needs_no_install(self, available, install):
        self.assertTrue(DependencyManager()._install_tzdata())
        install.assert_not_called()

    @patch("utils.dependency_manager.ZoneInfo")
    @patch.object(DependencyManager, "_install_package", return_value=True)
    @patch.object(DependencyManager, "_timezone_available")
    def test_timezone_install_reprobes_data_after_pip_success(self, available, install, zone):
        for repaired in (True, False):
            with self.subTest(repaired=repaired):
                available.side_effect = [False, repaired]
                manager = DependencyManager()
                self.assertEqual(manager._install_tzdata(), repaired)
                install.assert_called_with("tzdata", "tzdata", upgrade=True, force_reinstall=True)
                zone.clear_cache.assert_called()
                if not repaired:
                    self.assertIn("belum dapat dibaca", manager.last_error)

    @patch.object(DependencyManager, "_timezone_available", return_value=False)
    @patch("utils.dependency_manager.subprocess.run")
    def test_frozen_missing_timezone_data_requires_app_update(self, run, available):
        manager = DependencyManager()
        with patch.object(sys, "frozen", True, create=True):
            self.assertFalse(manager._install_tzdata())
        self.assertIn("Perbarui aplikasi", manager.last_error)
        run.assert_not_called()

    @patch("utils.dependency_manager.subprocess.run")
    @patch.object(DependencyManager, "_timezone_available")
    def test_timezone_repair_forces_reinstall_of_corrupt_current_package(self, available, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        for healthy in (False, True):
            with self.subTest(healthy=healthy), patch.object(sys, "frozen", False, create=True):
                available.side_effect = [healthy, True]
                self.assertTrue(DependencyManager()._install_tzdata(upgrade=True))
                command = run.call_args.args[0]
                self.assertEqual(command[-1], "tzdata")
                self.assertEqual("--force-reinstall" in command, not healthy)


class DependencyServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ObservableService()
        self.details = installed_details()
        self.probe = patch.object(self.service, "_probe_local", side_effect=lambda: copy.deepcopy(self.details))
        self.probe_mock = self.probe.start()
        self.addCleanup(self.probe.stop)

    def test_versions_compare_numbers_not_strings(self):
        self.assertGreater(version_tuple("2.10.0"), version_tuple("2.6.7"))
        self.assertEqual(version_tuple("v2.6.7"), version_tuple("2.6.7.0"))
        self.assertGreater(version_tuple("2026.10.1"), version_tuple("2026.9.30"))
        self.assertEqual(self.service.detailed()["deno"]["status"], "up_to_date")

    @patch("services.dependencies.subprocess.run")
    def test_local_status_is_cached_without_pip_or_network(self, run):
        self.service.detailed()
        self.service.detailed()
        self.service.install_status()
        self.assertEqual(self.probe_mock.call_count, 1)
        run.assert_not_called()
        self.assertEqual(self.service.detailed()["ytdlp"]["status"], "installed")

    def test_unknown_dependency_is_rejected_before_worker(self):
        self.assertEqual(self.service.start_install("invalid")["status"], "error")
        self.assertFalse(self.service.install_status()["active"])

    @patch("services.dependencies.DependencyManager")
    def test_duplicate_click_single_flight_then_real_failure(self, manager_type):
        entered, release = threading.Event(), threading.Event()
        manager = manager_type.return_value
        manager.last_error = "network unavailable"
        manager.restart_required = False

        def blocked_install(*args, **kwargs):
            entered.set()
            release.wait(3)
            return False

        manager.install.side_effect = blocked_install
        try:
            first = self.service.start_install("ytdlp")
            self.assertTrue(entered.wait(2))
            duplicate = self.service.start_install("ytdlp")
            self.assertEqual(first["job_id"], duplicate["job_id"])
            self.assertEqual(duplicate["status"], "already_running")
            self.assertTrue(self.service.install_status()["active"])
            self.assertEqual(self.service.install_status()["jobs"]["ytdlp"]["status"], "running")
        finally:
            release.set()
        self.assertTrue(self.service.done.wait(2))
        result = self.service.install_status()
        self.assertFalse(result["active"])
        self.assertEqual(result["jobs"]["ytdlp"]["status"], "failed")
        self.assertEqual(result["jobs"]["ytdlp"]["error"], "network unavailable")
        manager.install.assert_called_once_with("ytdlp", upgrade=True)

    @patch("services.dependencies.DependencyManager")
    def test_success_clears_local_cache_and_reports_restart(self, manager_type):
        manager = manager_type.return_value
        manager.install.return_value = True
        manager.restart_required = True
        self.service.detailed()
        self.service.start_install("whisper")
        self.assertTrue(self.service.done.wait(2))
        status = self.service.install_status()["jobs"]["whisper"]
        self.assertEqual(status["status"], "succeeded")
        self.assertTrue(status["restart_required"])
        self.service.detailed()
        self.assertEqual(self.probe_mock.call_count, 2)

    def test_install_all_does_not_end_updates_based_on_installed_flag(self):
        self.service._latest["ytdlp"] = "2026.10.1"
        with patch.object(self.service, "start_install", return_value={"status": "started"}) as start:
            result = self.service.install_all()
        self.assertEqual(result["status"], "started")
        start.assert_called_once_with("ytdlp", upgrade=True)

    def test_online_lookup_is_background_cached_and_single_flight(self):
        service = DependencyService()
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()

        def lookup(package):
            entered.set()
            release.wait(3)
            return "2026.10.1" if package == "yt-dlp" else "1.3.0"

        original = service._lookup_updates

        def observed():
            try:
                original()
            finally:
                completed.set()

        with patch.object(service, "_fetch_latest", side_effect=lookup) as fetch, patch.object(service, "_lookup_updates", side_effect=observed):
            try:
                self.assertEqual(service.refresh_updates()["status"], "running")
                self.assertTrue(entered.wait(2))
                self.assertEqual(service.refresh_updates(force=True)["status"], "running")
                self.assertEqual(fetch.call_count, 1)
            finally:
                release.set()
            self.assertTrue(completed.wait(2))
            self.assertEqual(service.refresh_updates()["status"], "complete")
            self.assertEqual(fetch.call_count, 2)

    @patch("services.dependencies.get_deno_path", return_value="bundled-deno")
    @patch("services.dependencies.get_ffmpeg_path", return_value="bundled-ffmpeg")
    @patch("services.dependencies.get_ytdlp_path", return_value="yt_dlp_module")
    @patch("services.dependencies._package_version", return_value="1.2.0")
    @patch.object(DependencyManager, "_module_available", return_value=False)
    @patch("services.dependencies._binary_info", return_value=(True, "2.10.0", "resolved"))
    def test_health_uses_execution_resolvers_and_correct_whisper(self, binary, module, version, ytdlp, ffmpeg, deno):
        result = DependencyService(online_checks=False)._probe_local()
        binary.assert_any_call("bundled-deno", "--version")
        binary.assert_any_call("bundled-ffmpeg", "-version")
        module.assert_called_once_with("faster_whisper")
        self.assertFalse(result["whisper"]["installed"])

    def test_bridge_keeps_boolean_compatibility(self):
        bridge = DependencyMixin()
        bridge._dependency_manager_service = self.service
        self.assertEqual(set(bridge.check_dependencies()), {"ffmpeg", "deno", "ytdlp", "whisper", "tzdata", "cookies"})
        self.assertTrue(bridge.check_dependencies()["deno"])

    def test_missing_timezone_data_is_visible_and_installable(self):
        self.details["tzdata"]["installed"] = False
        self.assertEqual(self.service.detailed()["tzdata"]["status"], "not_installed")
        with patch.object(self.service, "start_install", return_value={"status": "started"}) as start:
            self.service.install_all()
        start.assert_called_once_with("tzdata", upgrade=False)


if __name__ == "__main__":
    unittest.main()
