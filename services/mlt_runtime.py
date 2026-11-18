"""Standalone MLT command line rendering. Never starts an authoring editor."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from functools import lru_cache

from template_sdk.ssr_template_engine import TemplateError, instantiate
from template_sdk.ssr_template_engine.package import manifest_digest
from .editing import probe_media


def application_root():
    import sys
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def runtime_executable():
    configured = os.environ.get("SSR_MLT_PATH")
    if configured:
        path = Path(configured).expanduser().resolve()
        if path.name.casefold() not in {"melt", "melt.exe"} or not path.is_file():
            raise TemplateError("SSR_MLT_PATH harus menunjuk ke executable melt, bukan editor.")
        return path
    for candidate in [application_root() / "_runtime" / "mlt" / "bin" / "melt.exe",
                      application_root() / "_runtime" / "mlt" / "bin" / "melt"]:
        if candidate.is_file():
            return candidate
    found = shutil.which("melt")
    if found:
        return Path(found).resolve()
    raise TemplateError("Runtime MLT belum tersedia. Jalankan tools/setup_mlt_runtime.py; Kdenlive tidak perlu dipasang.")


def _environment(executable):
    env = os.environ.copy()
    base = executable.parent.parent
    env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
    repository = base / "lib" / "render-mlt" if (base / "lib" / "render-mlt").is_dir() else base / "lib" / "mlt"
    for variable, path in {"MLT_REPOSITORY": repository, "MLT_DATA": base / "share" / "mlt",
                           "MLT_PROFILES_PATH": base / "share" / "mlt" / "profiles", "QT_PLUGIN_PATH": executable.parent,
                           "FREI0R_PATH": base / "lib" / "frei0r-1"}.items():
        if path.is_dir():
            env[variable] = str(path)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_OPENGL"] = "software"
    env["LC_ALL"] = "C"
    env["LC_NUMERIC"] = "C"
    return env


def _options(executable):
    return {"env": _environment(executable), "creationflags": subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            "stdin": subprocess.DEVNULL}


@lru_cache(maxsize=4)
def _inventory(path, fingerprint):
    executable = Path(path)
    options = _options(executable)
    version = subprocess.run([str(executable), "-version"], capture_output=True, timeout=15, **options)
    version_text = (version.stdout + version.stderr).decode("utf-8", errors="replace").strip()
    if version.returncode != 0 or not re.search(r"melt(?:\.exe)?\s+[0-9]", version_text, re.I):
        raise TemplateError("Runtime MLT tidak dapat dijalankan: " + version_text[-300:])
    available = set()
    for category in ("producers", "filters", "transitions"):
        # Windows can scan native plugins on their first load. Keep a finite
        # wait, without accepting a partial inventory or launching an editor.
        try:
            result = subprocess.run([str(executable), "-query", category], capture_output=True, timeout=45, **options)
        except subprocess.TimeoutExpired as exc:
            raise TemplateError("Runtime MLT belum selesai membaca efek dalam 45 detik. Coba ulang preview atau render template.") from exc
        if result.returncode != 0:
            raise TemplateError("Tidak dapat membaca layanan runtime MLT.")
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        available.update(re.findall(r"^\s+-\s+([\w.:-]+)\s*$", output, re.M))
    return version_text.splitlines()[0], tuple(sorted(available))


def runtime_status(required_services=()):
    executable = runtime_executable()
    repository = Path(_environment(executable).get("MLT_REPOSITORY", executable.parent))
    fingerprint = (executable.stat().st_mtime_ns, tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                    for p in sorted(repository.glob("*.dll"))))
    version, available = _inventory(str(executable), fingerprint)
    missing = sorted(set(required_services) - set(available))
    if missing:
        raise TemplateError("Efek template belum tersedia pada runtime MLT: " + ", ".join(missing))
    return {"status": "ok", "executable": str(executable), "version": version,
            "services": sorted(available), "editor_required": False}


def render_template(directory, source, output, *, title="", ffmpeg="ffmpeg", progress=None, cancelled=None, expected_package_sha256=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output:
        raise TemplateError("Template output must differ from its source.")
    info = probe_media(source, ffmpeg)
    data, manifest, frames = instantiate(directory, source, info["duration"], title)
    if expected_package_sha256 and manifest_digest(manifest) != expected_package_sha256:
        raise TemplateError("Isi versi template berubah sejak job dibuat; pulihkan paket aslinya.")
    status = runtime_status(manifest["required_services"])
    executable = Path(status["executable"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mlt-render-", dir=output.parent) as temp:
        timeline = Path(temp) / "render.mlt"
        partial = Path(temp) / "render.mp4"
        log_path = Path(temp) / "render.log"
        timeline.write_bytes(data)
        command = [str(executable), str(timeline), "-progress", "-consumer", "avformat:" + partial.as_posix(),
                   "vcodec=libx264", "acodec=aac", "crf=18", "preset=fast", "pix_fmt=yuv420p", "threads=2",
                   "real_time=-1", "movflags=+faststart", "an=1"]
        start, reported = time.monotonic(), -1
        process = None
        try:
            with log_path.open("wb") as log:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log, **_options(executable))
                while process.poll() is None:
                    if cancelled and cancelled():
                        raise TemplateError("Render template dibatalkan.")
                    if time.monotonic() - start > max(180, info["duration"] * 45):
                        raise TemplateError("Render template melewati batas waktu.")
                    if progress:
                        with log_path.open("rb") as reader:
                            reader.seek(max(0, log_path.stat().st_size - 4096))
                            messages = reader.read().decode("utf-8", errors="replace")
                        percentages = re.findall(r"percentage:\s*(\d+)", messages)
                        if percentages and int(percentages[-1]) != reported:
                            reported = int(percentages[-1])
                            progress(min(.99, reported / 100))
                    time.sleep(.1)
            messages = log_path.read_bytes().decode("utf-8", errors="replace")
            tail = messages[-3000:]
            if process.returncode != 0 or not partial.is_file():
                raise TemplateError("MLT gagal merender template: " + tail[-1200:])
            # MLT sometimes exits successfully after reporting a failed filter.
            if re.search(r"(?:failed to load|failed to create|not found|invalid producer|No producer)", messages, re.I):
                raise TemplateError("MLT melaporkan resource/efek tidak tersedia: " + tail[-1200:])
            # Templates compose visuals. Speech, source audio, and music belong
            # to the clipping pipeline. Never let an editor's track mute/mix
            # silently discard the speaker before the required music stage.
            if info["has_audio"]:
                restored = Path(temp) / "with-source-audio.mp4"
                result = subprocess.run([str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(partial),
                    "-i", str(source), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-t", str(frames / manifest["canvas"]["fps"]), "-movflags", "+faststart", str(restored)],
                    capture_output=True, timeout=max(60, info["duration"] * 2),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode != 0:
                    raise TemplateError("Audio ucapan gagal dipertahankan: " + result.stderr.decode("utf-8", errors="replace")[-500:])
                os.replace(restored, partial)
            actual = probe_media(partial, ffmpeg)
            fps, canvas = manifest["canvas"]["fps"], manifest["canvas"]
            if (not actual["has_video"] or (actual["width"], actual["height"]) != (canvas["width"], canvas["height"])
                    or abs(actual["duration"] - frames / fps) > max(.12, 2/fps)
                    or actual["duration"] + 1/fps + .01 < info["duration"]
                    or (info["has_audio"] and not actual["has_audio"])):
                raise TemplateError("Hasil template tidak mempertahankan dimensi, durasi, atau audio sumber.")
            os.replace(partial, output)
            if progress:
                progress(1)
            return {"engine": "mlt", "template_id": manifest["id"], "version": manifest["version"],
                    "timeline_sha256": manifest["files"]["timeline.mlt"], "frames": frames,
                    "package_sha256": manifest_digest(manifest),
                    "duration_policy": manifest["duration_policy"], "runtime_version": status["version"],
                    "source_audio_preserved": info["has_audio"], "editor_required": False}
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
