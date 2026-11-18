"""Local dependency health, cached update discovery, and observable install jobs.

No update lookup runs on the pywebview request thread. The local probes use the
same resolvers as video processing, and polling reads job state without spawning
pip or launching another installer.
"""

import copy
import importlib.metadata
import json
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from utils.dependency_manager import DENO_VERSION, DependencyManager
from utils.helpers import get_app_dir, get_deno_path, get_ffmpeg_path, get_ytdlp_path


DEPENDENCIES = ("ytdlp", "ffmpeg", "deno", "whisper", "tzdata")
ACTIVE_STATES = {"queued", "running"}


def version_tuple(value):
    """Compare dotted numeric versions, including yt-dlp's calendar versions."""
    match = re.search(r"\d+(?:\.\d+)+", str(value or ""))
    if not match:
        return ()
    parts = tuple(int(part) for part in match.group().split("."))
    return parts + (0,) * max(0, 4 - len(parts))


def _package_version(package):
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _binary_info(path, flag="--version"):
    resolved = str(path) if path else None
    if not resolved or not (Path(resolved).is_file() or shutil.which(resolved)):
        return False, None, resolved
    try:
        result = subprocess.run(
            [resolved, flag], capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            return False, None, resolved
        match = re.search(r"\d+(?:\.\d+)+", result.stdout or result.stderr or "")
        return True, match.group() if match else None, resolved
    except (OSError, subprocess.SubprocessError):
        return False, None, resolved


class DependencyService:
    def __init__(self, app_dir=None, online_checks=True):
        self.app_dir = Path(app_dir) if app_dir is not None else get_app_dir()
        self.online_checks = online_checks
        self._lock = threading.RLock()
        self._probe_lock = threading.Lock()
        self._local = None
        self._local_at = 0
        self._latest = {}
        self._updates = {"status": "idle", "checked_at": None, "error": None}
        self._updates_at = 0
        self._jobs = {}

    def _probe_local(self):
        result = {}
        for name, path, flag in (
            ("ffmpeg", get_ffmpeg_path(), "-version"),
            ("deno", get_deno_path(), "--version"),
        ):
            installed, version, resolved = _binary_info(path, flag)
            result[name] = {"installed": installed, "version": version, "path": resolved}
        resolved = get_ytdlp_path()
        if resolved == "yt_dlp_module":
            result["ytdlp"] = {"installed": True, "version": _package_version("yt-dlp"), "path": resolved}
        else:
            installed, version, resolved = _binary_info(resolved)
            result["ytdlp"] = {"installed": installed, "version": version, "path": resolved}
        result["whisper"] = {
            "installed": DependencyManager._module_available("faster_whisper"),
            "version": _package_version("faster-whisper"), "path": "faster_whisper",
        }
        timezone_ready = DependencyManager._timezone_available()
        timezone_version = _package_version("tzdata")
        result["tzdata"] = {
            "installed": timezone_ready, "version": timezone_version,
            "path": "tzdata" if timezone_version else "system zoneinfo",
            "error": None if timezone_ready else (
                "Data zona waktu untuk jadwal upload tidak tersedia. Klik Install pada tzdata di Settings."
            ),
        }
        return result

    def _local_details(self, refresh=False):
        # One probe per TTL even if pywebview receives concurrent requests.
        with self._probe_lock:
            with self._lock:
                cached = self._local is not None and time.monotonic() - self._local_at < 30
                if cached and not refresh:
                    return copy.deepcopy(self._local)
            details = self._probe_local()
            with self._lock:
                self._local = details
                self._local_at = time.monotonic()
                return copy.deepcopy(details)

    @staticmethod
    def _fetch_latest(package):
        request = urllib.request.Request(
            f"https://pypi.org/pypi/{package}/json",
            headers={"User-Agent": "SSR_CLIPPER dependency checker", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.load(response)
        version = payload.get("info", {}).get("version")
        if not version_tuple(version):
            raise ValueError(f"Versi terbaru {package} tidak tersedia")
        return str(version)

    def refresh_updates(self, force=False):
        """Schedule one cached background lookup; never run pip list --outdated."""
        with self._lock:
            if not self.online_checks:
                return copy.deepcopy(self._updates)
            if self._updates["status"] == "running":
                return copy.deepcopy(self._updates)
            if self._updates_at and time.monotonic() - self._updates_at < 3600 and not force:
                return copy.deepcopy(self._updates)
            self._updates = {"status": "running", "checked_at": self._updates["checked_at"], "error": None}
            thread = threading.Thread(target=self._lookup_updates, name="dependency-updates", daemon=True)
            thread.start()
            return copy.deepcopy(self._updates)

    def _lookup_updates(self):
        latest, errors = {}, []
        for name, package in (("ytdlp", "yt-dlp"), ("whisper", "faster-whisper")):
            try:
                latest[name] = self._fetch_latest(package)
            except Exception as exc:
                errors.append(f"{package}: {exc}")
        with self._lock:
            self._latest.update(latest)
            self._updates_at = time.monotonic()
            self._updates = {
                "status": "failed" if errors else "complete", "checked_at": time.time(),
                "error": "; ".join(errors) or None,
            }

    def detailed(self, refresh=False):
        details = self._local_details(refresh)
        self.refresh_updates()
        with self._lock:
            latest = dict(self._latest, deno=DENO_VERSION)
            jobs = copy.deepcopy(self._jobs)
            update_info = copy.deepcopy(self._updates)
        for name, info in details.items():
            info["latest"] = latest.get(name)
            installed_version = version_tuple(info["version"])
            target_version = version_tuple(info["latest"])
            if not info["installed"]:
                info["status"] = "not_installed"
            elif installed_version and target_version:
                info["status"] = "update_available" if installed_version < target_version else "up_to_date"
            else:
                # Installed does not claim that an offline/unknown version is current.
                info["status"] = "installed"
            info["job"] = jobs.get(name, {"status": "idle"})
            info["restart_required"] = bool(info["job"].get("restart_required"))
        details["cookies"] = (self.app_dir / "cookies.txt").is_file()
        details["update_check"] = update_info
        return details

    def install_status(self):
        with self._lock:
            jobs = {name: copy.deepcopy(self._jobs.get(name, {"dep": name, "status": "idle"})) for name in DEPENDENCIES}
        return {"jobs": jobs, "active": any(job["status"] in ACTIVE_STATES for job in jobs.values())}

    def start_install(self, name, upgrade=True):
        if name not in DEPENDENCIES:
            return {"status": "error", "message": f"Unknown dependency: {name}"}
        with self._lock:
            current = self._jobs.get(name)
            if current and current["status"] in ACTIVE_STATES:
                return {"status": "already_running", "dep": name, "job_id": current["id"]}
            job = {
                "id": uuid.uuid4().hex, "dep": name, "status": "queued", "upgrade": bool(upgrade),
                "started_at": time.time(), "finished_at": None, "error": None, "restart_required": False,
            }
            self._jobs[name] = job
            try:
                threading.Thread(target=self._install, args=(name, job["id"], upgrade), daemon=True).start()
            except Exception as exc:
                job.update(status="failed", error=str(exc), finished_at=time.time())
                return {"status": "error", "dep": name, "message": str(exc)}
            return {"status": "started", "dep": name, "job_id": job["id"]}

    def _install(self, name, job_id, upgrade):
        with self._lock:
            self._jobs[name]["status"] = "running"
        manager = DependencyManager(self.app_dir)
        error, restart_required = None, False
        try:
            if not manager.install(name, upgrade=upgrade):
                raise RuntimeError(manager.last_error or f"Instalasi {name} gagal")
            restart_required = manager.restart_required
        except Exception as exc:
            error = str(exc)
        finally:
            with self._lock:
                job = self._jobs[name]
                if job["id"] == job_id:
                    job.update(
                        status="failed" if error else "succeeded", error=error,
                        finished_at=time.time(), restart_required=restart_required,
                    )
                self._local = None

    def install_all(self):
        details = self.detailed()
        results = {}
        for name in DEPENDENCIES:
            info = details[name]
            if info["status"] in {"not_installed", "update_available"} or info["job"]["status"] == "failed":
                results[name] = self.start_install(name, upgrade=info["installed"])
            elif info["job"]["status"] in ACTIVE_STATES:
                results[name] = self.start_install(name)
        return {"status": "started" if results else "complete", "dependencies": results}


class DependencyMixin:
    """Bridge-compatible API, initialized lazily to keep WebAPI startup unchanged."""

    _dependency_init_lock = threading.Lock()

    def _dependency_service(self):
        with self._dependency_init_lock:
            if not hasattr(self, "_dependency_manager_service"):
                self._dependency_manager_service = DependencyService()
            return self._dependency_manager_service

    def check_dependencies(self):
        details = self.check_dependencies_detailed()
        return {"cookies": details["cookies"], **{name: details[name]["installed"] for name in DEPENDENCIES}}

    def check_dependencies_detailed(self):
        return self._dependency_service().detailed()

    def check_dependency_updates(self):
        return self._dependency_service().refresh_updates(force=True)

    def install_single_dependency(self, dep_name):
        return self._dependency_service().start_install(dep_name, upgrade=True)

    def install_dependencies(self):
        return self._dependency_service().install_all()

    def get_dependency_install_status(self):
        return self._dependency_service().install_status()
