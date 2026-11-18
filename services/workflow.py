"""Desktop workflow bridge: durable jobs, exact-file review and publication tracking."""
import copy
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone

from .storage import WorkflowStore, atomic_json, digest, file_digest, utc_now
from .publishing import ReplizClient, plan_distribution, validate_reservation, schedule_update
from .scheduling import display_schedule_time, normalize_upload_times, parse_schedule_time, publication_day, scheduling_timezone
from .account_tags import platform_captions, publication_caption, tags_for_platform, caption_has_term


class WorkflowMixin:
    _workflow_init_lock = threading.RLock()

    def _get_store(self):
        with self._workflow_init_lock:
            if not hasattr(self, "_workflow_store"):
                root = Path(self.config_file).resolve().parent
                self._workflow_store = WorkflowStore(root / "workflow.sqlite3")
                if getattr(self, "worker_enabled", True):
                    self._workflow_store.recover_interrupted()
                self._job_lock = threading.RLock()
                self._upload_lock = threading.Lock()
                self._provider_lock = threading.RLock()
                self._cancel_event = threading.Event()
                self._last_sync = 0
                self._last_index = 0
                self._job_event_lock = threading.RLock()
                self._job_live = {}
                self._job_flush_at = {}
                self._title_queue = queue.Queue()
                self._title_pending = set()
                self._title_thread = None
            return self._workflow_store

    def browse_source_video(self):
        import webview
        paths = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=("Video (*.mp4;*.mov;*.mkv;*.webm)",))
        return {"status": "ok", "path": str(paths[0])} if paths else {"status": "cancelled"}

    def get_editing_templates(self):
        from .editing import list_templates
        return {"status": "ok", "templates": list_templates()}

    def get_campaign_editing_presets(self, campaign_id=None):
        from .campaigns import EDITING_PRESETS
        from .external_templates import list_presets
        try:
            presets = copy.deepcopy(list(EDITING_PRESETS.values())) + list_presets()
            if campaign_id:
                campaign = next((item for item in self._get_cfg().get('campaigns', []) if item.get('id') == campaign_id), None)
                if campaign is None:
                    raise ValueError('Campaign tidak ditemukan.')
                editing = campaign.get('editing', {})
                selected = [item['preset_id'] for item in editing.get('template_pool', []) if item.get('enabled')]
                if not selected and editing.get('preset_id'):
                    selected = [editing['preset_id']]
                available = {item['id'] for item in presets}
                from .campaigns import resolve_editing_preset
                for preset_id in dict.fromkeys(selected):
                    if preset_id not in available:
                        preset = resolve_editing_preset(preset_id)
                        preset['archived'] = True
                        presets.append(preset)
            return {"status": "ok", "presets": presets}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_template_preview(self, template_id):
        try:
            from .editing import resolve_template, _run, probe_media, validate_render_canvas, RENDER_VALIDATION_VERSION
            from .media_preview import MediaPreview
            from clipper_core import AutoClipperCore
            from types import SimpleNamespace
            from utils.helpers import get_ffmpeg_path
            if str(template_id).startswith(("mlt:", "design:")):
                from .external_templates import resolve_preset, template_directory
                preset = resolve_preset(template_id)
                ext = preset["external_template"]
                root = Path(self.config_file).resolve().parent / "_workflow_previews"
                root.mkdir(parents=True, exist_ok=True)
                design_engine = ext["engine"] == "design"
                checksum = ext["design_sha256"] if design_engine else ext["timeline_sha256"]
                output = root / f"{ext['engine']}-{ext['id']}-v{ext['version']}-{checksum[:12]}-rv{RENDER_VALIDATION_VERSION}.mp4"
                with self._workflow_init_lock:
                    if not output.is_file():
                        with tempfile.TemporaryDirectory(dir=root) as temp:
                            source = Path(temp) / "source.mp4"
                            _run([get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                  "testsrc2=s=640x360:r=30:d=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], timeout=60)
                            if design_engine:
                                from template_sdk.ssr_template_engine.design import load_design, render_design
                                directory = template_directory(template_id)
                                words = [{"word": w, "start": i*.45, "end": (i+1)*.45} for i,w in enumerate("Potongan terbaik untuk cerita kamu".split())]
                                render_design(load_design(directory), directory, source, output, title="Cerita terbaik untuk kamu", subtitle_words=words, ffmpeg=get_ffmpeg_path())
                            else:
                                from .mlt_runtime import render_template
                                render_template(template_directory(template_id), source, output, title="Cerita terbaik untuk kamu", ffmpeg=get_ffmpeg_path())
                    validate_render_canvas(probe_media(output, get_ffmpeg_path()), ext["canvas"], "Preview template")
                    if not hasattr(self, "_media_preview"):
                        self._media_preview = MediaPreview()
                    return {"status": "ok", "preview_url": self._media_preview.register(output), "template": preset}
            template = resolve_template(template_id)
            root = Path(self.config_file).resolve().parent / "_workflow_previews"
            root.mkdir(parents=True, exist_ok=True)
            revision = '-ruang3' if template_id in {'ruang_founder','ruang_witness'} else ''
            output = root / f"{template_id}-v{template['version']}{revision}-rv{RENDER_VALIDATION_VERSION}.mp4"
            expected_canvas = template.get("canvas", {"width": 540, "height": 960})
            with self._workflow_init_lock:
                if not output.exists():
                    core = AutoClipperCore(client=None, output_dir=root, log_callback=lambda *_: None)
                    words = [SimpleNamespace(word=w, start=i*.45, end=(i+1)*.45) for i,w in enumerate("Potongan terbaik untuk cerita kamu".split())]
                    transcript = SimpleNamespace(words=words, segments=[SimpleNamespace(text="Potongan terbaik untuk cerita kamu", start=0, end=2.25, words=words)])
                    subtitle = root / (template_id + ".ass")
                    partial = root / (template_id + ".partial.mp4")
                    background = root / (template_id + ".background.mp4")
                    framed = root / (template_id + ".framed.mp4")
                    broll_demo = root / (template_id + ".broll-demo.mp4")
                    try:
                        if template_id in {"timothy_focus", "timothy_cinematic", "ruang_founder", "ruang_witness"}:
                            from .reference_templates import template_spec, render_layout, render_captions
                            canvas = template_spec(template_id)
                            _run([get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"color=c=0x4b5048:s={canvas['width']}x{canvas['height']}:r=30:d=6", "-c:v", "libx264",
                                "-pix_fmt", "yuv420p", str(background)], timeout=90)
                            demo_campaign = {}
                            if template_id.startswith('ruang_'):
                                _run([get_ffmpeg_path(), '-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                                    'testsrc2=s=540x960:r=30:d=6', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(broll_demo)], timeout=90)
                                demo_campaign = {'assets':[{'id':'preview','path':str(broll_demo),'role':'broll','name':'Contoh B-roll','opener':True}]}
                                words = [SimpleNamespace(word=w,start=5.2+i*.45,end=5.2+(i+1)*.45) for i,w in enumerate('Potongan terbaik untuk cerita kamu'.split())]
                                transcript = SimpleNamespace(words=words,segments=[])
                            if template_id == "timothy_cinematic":
                                _run([get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                    "color=c=0x927253:s=960x540:r=30:d=3", "-vf",
                                    "drawbox=x=180:y=80:w=600:h=380:color=0x35483b:t=fill,drawbox=x=440:y=80:w=90:h=380:color=0xb59264:t=fill",
                                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(broll_demo)], timeout=60)
                                demo_campaign = {"assets": [{"id": "preview", "path": str(broll_demo), "role": "broll", "name": "Contoh B-roll"}]}
                                words = [SimpleNamespace(word=w, start=i*.4, end=(i+1)*.4) for i,w in enumerate(
                                    "potongan terbaik untuk cerita kamu ayo lakukan sekarang".split())]
                                transcript = SimpleNamespace(words=words, segments=[])
                            render_layout(background, framed, template_id, demo_campaign, get_ffmpeg_path(), title='Cerita terbaik untuk kamu')
                            render_captions(framed, partial, transcript, template_id, get_ffmpeg_path())
                        elif template_id == "podcast_square":
                            from .podcast_template import render_layout, render_word_captions
                            _run([get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                  "color=c=0x30383e:s=720x720:r=30:d=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(background)], timeout=60)
                            render_layout(background, framed, get_ffmpeg_path())
                            render_word_captions(framed, partial, transcript, get_ffmpeg_path())
                        else:
                            core.create_ass_subtitle_capcut(transcript, str(subtitle), style=template["subtitle_style"])
                            escaped = str(subtitle).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
                            _run([get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                  "color=c=0x25452f:s=540x960:r=24:d=3", "-vf", f"ass='{escaped}'", "-c:v", "libx264",
                                  "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(partial)], timeout=60)
                        validate_render_canvas(probe_media(partial, get_ffmpeg_path()), expected_canvas, "Preview template")
                        os.replace(partial, output)
                    finally:
                        core.cleanup()
                        partial.unlink(missing_ok=True)
                        subtitle.unlink(missing_ok=True)
                        background.unlink(missing_ok=True)
                        framed.unlink(missing_ok=True)
                        broll_demo.unlink(missing_ok=True)
                validate_render_canvas(probe_media(output, get_ffmpeg_path()), expected_canvas, "Preview tersimpan")
                if not hasattr(self, "_media_preview"):
                    self._media_preview = MediaPreview()
                return {"status": "ok", "preview_url": self._media_preview.register(output), "template": template}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def start_processing(self, url, num_clips=5, add_captions=True, add_hook=False, subtitle_lang="id", portrait=False,
                         highlight_finder=True, yt_title_maker=True, campaign_id=None, subtitle_style="v2", clip_mode="fixed"):
        return self.enqueue_sources([url], campaign_id, {
            "num_clips": num_clips, "add_captions": add_captions, "add_hook": add_hook,
            "subtitle_lang": subtitle_lang, "portrait": portrait, "highlight_finder": highlight_finder,
            "yt_title_maker": yt_title_maker, "subtitle_style": subtitle_style, "clip_mode": clip_mode,
        })

    def enqueue_sources(self, sources, campaign_id, options=None):
        from .editing import fingerprint_source
        from .campaigns import normalize_campaign, campaign_processing_options, campaign_version_record
        try:
            store = self._get_store()
            campaign = next((c for c in self._get_cfg().get("campaigns", []) if c.get("id") == campaign_id), None)
            if not campaign:
                raise ValueError("Pilih campaign sebelum membuat clip.")
            campaign = normalize_campaign(campaign)
            from .additionals import platform_key
            assigned = set(campaign.get("account_ids", []))
            configured_platforms = {platform_key(p.get("platform", "")) for p in store.list("account_profile")
                                    if p.get("account_id", p.get("id")) in assigned and p.get("platform")}
            allowed_platforms = set(campaign.get("brief", {}).get("platforms") or [])
            if allowed_platforms:
                configured_platforms &= allowed_platforms
            if configured_platforms:
                campaign["render_platforms"] = sorted(configured_platforms)
            readiness = self._campaign_readiness(campaign)
            if not readiness["production_ready"]:
                raise ValueError("; ".join(readiness["production_blockers"]))
            if campaign.get("status") != "active":
                raise ValueError("Aktifkan campaign setelah memeriksa brief dan aset.")
            if not isinstance(sources, list) or not 1 <= len(sources) <= 50:
                raise ValueError("Masukkan 1–50 sumber video.")
            options = campaign_processing_options(campaign, (options or {}).get("num_clips", 5))
            identities = [fingerprint_source(str(source).strip()) for source in sources]
            # Migrating a legacy campaign for a new job must not reuse a version
            # id whose stored snapshot still describes the old editing choices.
            version = campaign_version_record(campaign)
            version_id = version["id"]
            if store.get("campaign_version", version_id) is None:
                store.put("campaign_version", version_id, version)
            campaign["version_id"] = version_id
            jobs = []
            for source, identity in zip(sources, identities):
                job_id = "job_" + uuid.uuid4().hex
                job = {"id": job_id, "source": str(source).strip(), "source_id": identity["source_id"],
                       "campaign_id": campaign_id, "campaign": copy.deepcopy(campaign), "options": options,
                       "title": Path(identity["path"]).name if identity["kind"] == "local" else "Memuat judul…",
                       "title_status": "ready" if identity["kind"] == "local" else "pending",
                       "status": "queued", "step": "Menunggu antrean", "clips": [], "logs": [],
                       "progress": 0, "created_at": utc_now(), "queued_at": utc_now(), "error": None}
                store.put("job", job_id, job)
                jobs.append(job)
            self._queue_job_titles(jobs)
            self._start_next_job()
            return {"status": "started", "jobs": [j["id"] for j in jobs]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _start_next_job(self):
        if not getattr(self, "worker_enabled", True):
            return
        self._get_store()
        with self._job_lock:
            if self.thread and self.thread.is_alive():
                return
            job = self._get_store().claim_job()
            if not job:
                return
            self._cancel_event.clear()
            self.thread = threading.Thread(target=self._run_job_queue, args=(job,), daemon=True)
            self.thread.start()

    def _run_job_queue(self, job):
        """Drain the serial render queue independently of which page is open."""
        while job:
            self._execute_job(job)
            with self._job_lock:
                job = self._get_store().claim_job()
                if job:
                    self._cancel_event.clear()
                else:
                    self.thread = None

    def _record_job_event(self, job_id, *, force=False, message=None, **fields):
        """Keep per-job live state and checkpoint at most twice a second."""
        store = self._get_store()
        with self._job_event_lock:
            live = self._job_live.setdefault(job_id, {})
            if message is not None:
                if "logs" not in live:
                    live["logs"] = list((store.get("job", job_id) or {}).get("logs", []))
                live["logs"].append({"timestamp": utc_now(), "message": str(message)[:4000]})
                live["logs"] = live["logs"][-100:]
            live.update(copy.deepcopy(fields))
            now = time.monotonic()
            if force or now - self._job_flush_at.get(job_id, 0) >= .5:
                store.update("job", job_id, live)
                self._job_flush_at[job_id] = now

    def _queue_job_titles(self, jobs):
        """Use one bounded metadata worker; enqueue never waits for the network."""
        self._get_store()
        with self._job_event_lock:
            for job in jobs:
                if job.get("title_status") != "pending" or job["id"] in self._title_pending:
                    continue
                self._title_pending.add(job["id"])
                self._title_queue.put((job["id"], job["source"]))
            if self._title_queue.empty() or (self._title_thread and self._title_thread.is_alive()):
                return
            self._title_thread = threading.Thread(target=self._resolve_job_titles, daemon=True)
            self._title_thread.start()

    def _fetch_source_title(self, source):
        """Metadata only, with a hard process timeout and no downloaded video."""
        from utils.helpers import get_ytdlp_path
        executable = get_ytdlp_path()
        if executable == "yt_dlp_module" and getattr(sys, "frozen", False):
            bundled = Path(sys.executable).resolve().parent / "yt-dlp.exe"
            executable = str(bundled) if bundled.is_file() else shutil.which("yt-dlp")
            if not executable:
                raise ValueError("Judul akan dibaca ketika proses video dimulai.")
        command = [executable] if executable and executable != "yt_dlp_module" else [sys.executable, "-m", "yt_dlp"]
        command += ["--ignore-config", "--skip-download", "--no-playlist", "--quiet", "--no-warnings",
                    "--socket-timeout", "10", "--retries", "0", "--extractor-retries", "0", "--dump-single-json"]
        cookies = Path(self.config_file).resolve().parent / "cookies.txt"
        with tempfile.TemporaryDirectory(prefix="ssr-source-title-") as folder:
            if cookies.is_file():
                # yt-dlp can write its cookie jar on exit. Metadata lookups use
                # an isolated copy, avoiding a race with the actual download.
                cookie_copy = Path(folder) / "cookies.txt"
                shutil.copyfile(cookies, cookie_copy)
                command += ["--cookies", str(cookie_copy)]
            response = subprocess.run([*command, source], capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if response.returncode:
            raise ValueError("Judul sumber belum dapat dibaca; akan dicoba saat proses video.")
        title = str(json.loads(response.stdout).get("title") or "").strip()
        if not title:
            raise ValueError("Sumber tidak memberikan judul video.")
        return title[:500]

    def _resolve_job_titles(self):
        while True:
            with self._job_event_lock:
                try:
                    job_id, source = self._title_queue.get_nowait()
                except queue.Empty:
                    self._title_thread = None
                    return
            try:
                title = self._fetch_source_title(source)
                fields = {"title": title, "title_status": "ready", "title_error": None}
            except Exception:
                fields = {"title": source, "title_status": "unavailable",
                          "title_error": "Judul belum tersedia; sumber tetap dapat diproses."}
            with self._job_event_lock:
                # The renderer may already have authoritative video metadata.
                job = self._get_store().get("job", job_id)
                if job and job.get("title_status") != "ready":
                    self._get_store().update("job", job_id, fields)
                    if job_id in self._job_live:
                        self._job_live[job_id].update(fields)
                self._title_pending.discard(job_id)
                self._title_queue.task_done()

    def _execute_job(self, job):
        self.core = None
        self.progress = 0.0
        self.status = "running"
        self.current_job = {**job, "progress": 0}
        self._active_job = job
        options = job.get("options", {})
        try:
            self._record_job_event(job["id"], force=True, progress=0, step="Memulai", clips=[], message="Memulai proses sumber video.")
            cfg = self._get_cfg()
            self._run(job["source"], options.get("num_clips", 5), options.get("add_captions", True),
                      options.get("add_hook", False), options.get("subtitle_lang", "id"), options.get("portrait", True),
                      options.get("highlight_finder", True), options.get("yt_title_maker", True), job["campaign_id"],
                      options.get("subtitle_style", "v2"), int(cfg.get("max_highlights", 30)),
                      options.get("num_clips", 5) if options.get("clip_mode", "fixed") == "fixed" else None,
                      int(cfg.get("ai_decides_min_score", 6)) if options.get("clip_mode") == "ai" else None)
            clips = self.core.get_clips_state() if self.core and getattr(self.core, "job_id", None) == job["id"] else []
            failures = [c for c in clips if c.get("status") == "error"]
            with self._job_lock:
                state = "cancelled" if self._cancel_event.is_set() else "failed" if str(self.status).startswith("error") else "completed"
                if failures and state == "completed":
                    state = "partial" if any(c.get("status") == "done" for c in clips) else "failed"
                self._record_job_event(job["id"], force=True, clips=clips, progress=self.progress,
                                       step={"completed": "Selesai", "partial": "Sebagian clip gagal", "failed": "Gagal", "cancelled": "Dibatalkan"}[state])
                self._get_store().update("job", job["id"], {"status": state, "progress": self.progress,
                    "error": "; ".join(str(c.get("error", "Render gagal")) for c in failures) if failures else str(self.status) if state == "failed" else None,
                    "clips": clips, "finished_at": utc_now()})
            if state == "completed" and job["campaign"].get("editing", {}).get("review_mode") == "automatic":
                self._auto_publish_job(job)
        except Exception as exc:
            self.status = "error: " + str(exc)
            with self._job_lock:
                state = "cancelled" if self._cancel_event.is_set() else "failed"
                self._record_job_event(job["id"], force=True, step="Dibatalkan" if state == "cancelled" else "Gagal", message=str(exc))
                self._get_store().update("job", job["id"], {"status": state, "error": str(exc), "finished_at": utc_now()})
        finally:
            with self._job_lock:
                self.current_job = None
                self._active_job = None
                with self._job_event_lock:
                    self._job_live.pop(job["id"], None)
                    self._job_flush_at.pop(job["id"], None)

    def _configure_workflow_core(self, core):
        job = getattr(self, "_active_job", None)
        if not job:
            return
        root = Path(self._get_cfg().get("output_dir", self.output_dir))
        core.campaign_config = copy.deepcopy(job["campaign"])
        core.job_id = job["id"]
        core.expected_source_id = job["source_id"]
        core.work_dir = root / "_cache" / digest(job["source_id"])[:24]
        core.resume_dir = root / ("job-" + job["id"].removeprefix("job_")[:16])
        core.is_cancelled = self._cancel_event.is_set
        core.highlight_overrides = job.get("highlight_overrides")
        core.finalize_callback = lambda directory, metadata: self._finalize_workflow_clip(directory, metadata, job)
        core.music_selector_callback = lambda metadata: self._select_workflow_music(metadata, job, core.work_dir)
        core.workflow_state_callback = lambda **fields: self._record_job_event(job["id"], force=True, **fields)
        update_clip = core._update_clip_state
        def update_clip_state(index, **fields):
            update_clip(index, **fields)
            self._record_job_event(job["id"], clips=core.get_clips_state())
        core._update_clip_state = update_clip_state

    def _select_workflow_music(self, metadata, job, cache_dir):
        from .editing import music_settings
        music = music_settings(job["campaign"])
        if music.get("policy") != "auto":
            return None
        selected = self._select_background_sound(metadata.get("transcript", ""), metadata.get("title", ""),
                                                   metadata.get("hook_text", ""), metadata.get("duration_seconds", 0), job["campaign"])
        if not selected:
            return None
        import requests
        path = Path(selected["path"]) if selected.get("path") else Path(cache_dir) / "music" / (digest(selected.get("audiodownload"))[:24] + ".mp3")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            response = requests.get(selected["audiodownload"], timeout=60, stream=True)
            response.raise_for_status()
            temporary = path.with_name(f"{path.stem}-{uuid.uuid4().hex}.part")
            try:
                size = 0
                with temporary.open("wb") as stream:
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 100 * 1024 * 1024:
                            raise ValueError("File musik melebihi batas 100 MB.")
                        stream.write(chunk)
                os.replace(temporary, path)
            finally:
                response.close()
                temporary.unlink(missing_ok=True)
        return {**music, "path": str(path), "start_seconds": selected.get("start", 0), "required": True,
                "selection": selected.get("selection"),
                "attribution": {k: selected.get(k) for k in ("id", "name", "artist", "license_ccurl")}}

    def _finalize_workflow_clip(self, directory, metadata, job):
        previous = self._get_store().get("clip", metadata.get("clip_id", ""))
        if previous and previous.get("file_hash") == metadata.get("final_sha256") and previous.get("render_key") == metadata.get("render_key"):
            return previous  # Resume must preserve a user's later caption/review revision.
        campaign = job["campaign"]
        brief = campaign.get("brief", {})
        caption_parts = [metadata.get("description") or metadata.get("title", ""), brief.get("cta", ""),
                         " ".join(brief.get("hashtags", []))]
        attribution = metadata.get("music", {}).get("attribution", {})
        if attribution.get("artist"):
            caption_parts.append(f"Musik: {attribution.get('name', '')} — {attribution['artist']}")
        caption, captions = platform_captions("\n\n".join(str(p).strip() for p in caption_parts if p), brief)
        metadata.update(caption=caption, captions=captions,
                        campaign_id=job["campaign_id"], campaign_version_id=campaign.get("version_id"),
                        job_id=job["id"], source_url=job["source"], campaign_snapshot=campaign)
        clip = self._register_clip(Path(metadata.get("final_path") or Path(directory) / "master.mp4"), metadata)
        metadata["clip_id"] = clip["id"]
        metadata["revision_id"] = clip["revision_id"]
        atomic_json(Path(directory) / "data.json", metadata)
        return metadata

    def _register_clip(self, path, metadata, legacy=False):
        path = Path(path).resolve()
        clip_id = metadata.get("clip_id") or "clip_" + digest(str(path))[:24]
        previous = self._get_store().get("clip", clip_id)
        if previous and legacy:
            return previous
        file_hash = file_digest(path)
        revision = "rev_" + digest({"clip_id": clip_id, "file": file_hash, "title": metadata.get("title"), "caption": metadata.get("caption", ""), "campaign": metadata.get("campaign_version_id")})[:24]
        clip = {**metadata, "id": clip_id, "path": str(path), "file_hash": file_hash, "revision_id": revision,
                "review_status": "pending", "approval_hash": None, "created_at": metadata.get("created_at", utc_now()),
                "folder_id": path.parent.parent.name if path.name == "master.mp4" else path.parent.name,
                "caption": metadata.get("caption", ""), "captions": metadata.get("captions", {}),
                "warnings": metadata.get("warnings", []), "blockers": metadata.get("blockers", [])}
        self._get_store().put("clip", clip_id, clip)
        self._get_store().put("clip_revision", revision, clip)
        return clip

    def _index_legacy_clips(self):
        if time.monotonic() - self._last_index < 10:
            return
        self._last_index = time.monotonic()
        known = {str(Path(c["path"]).resolve()) for c in self._get_store().list("clip")}
        for legacy in self._legacy_get_stock_clips():
            path = Path(legacy["path"]).resolve()
            if str(path) in known or path.name.startswith(("temp_", "segment_")):
                continue
            try:
                meta_path = path.parent / "data.json"
                metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
                if path.parent.parent.name.startswith("job-") and not metadata.get("final_sha256"):
                    continue  # A render in progress has not reached its finalization checkpoint.
                clip = self._register_clip(path, {**legacy, **metadata}, legacy=True)
                known.add(str(path))
                # Import history for accounting only; legacy success does not prove publication.
                entries = metadata.get("scheduled_uploads", [])
                if not entries and metadata.get("upload_status") == "sukses":
                    entries = [{"id": "unverified", "account_id": "legacy-unknown", "status": "sukses"}]
                for entry in entries:
                    key = digest({"clip_id": clip["id"], "account_id": entry.get("account_id", "legacy-unknown")})
                    publication = {"id": "legacy_" + digest([clip["id"], entry.get("id")])[:24], "dedupe_key": key,
                        "clip_id": clip["id"], "clip_title": clip.get("title", ""), "clip_path": str(path),
                        "campaign_id": clip.get("campaign_id"), "account_id": entry.get("account_id", "legacy-unknown"),
                        "account_name": entry.get("account_id", "Legacy"), "platform": entry.get("platform", ""),
                        "scheduled_at": entry.get("scheduled_at") or utc_now(), "local_day": str(entry.get("scheduled_at") or utc_now())[:10],
                        "status": "scheduled" if entry.get("repliz_schedule_id") else "needs_attention", "caption": entry.get("caption", ""),
                        "schedule_id": entry.get("repliz_schedule_id"), "source_ranges": clip.get("source_ranges", []),
                        "error": None if entry.get("repliz_schedule_id") else "Riwayat lama belum terverifikasi; periksa posting di akun."}
                    try:
                        self._get_store().save_publication(publication)
                    except Exception:
                        pass
            except (OSError, ValueError):
                continue

    def get_stock_clips(self, folder_id=None):
        store = self._get_store()
        self._index_legacy_clips()
        publications = store.publications()
        result = []
        for clip in store.list("clip"):
            if folder_id and clip.get("folder_id") != folder_id:
                continue
            if not Path(clip["path"]).exists():
                continue
            items = [p for p in publications if p["clip_id"] == clip["id"]]
            statuses = {p["status"] for p in items}
            status = "sukses" if statuses and statuses <= {"published"} else "gagal" if "failed" in statuses else "uploading" if statuses & {"uploading", "publishing"} else "terjadwal" if statuses else "belum_diupload"
            seconds = int(float(clip.get("duration_seconds", 0)))
            result.append({**clip, "upload_status": status, "duration": f"{seconds // 60:02d}:{seconds % 60:02d}",
                           "date": Path(clip["path"]).stat().st_mtime * 1000, "publications": items})
        return result

    def get_review_clip(self, clip_id):
        clip = self._get_store().get("clip", clip_id)
        if not clip:
            return {"status": "error", "message": "Clip tidak ditemukan."}
        if not Path(clip["path"]).is_file():
            return {"status": "error", "message": "File clip tidak tersedia."}
        feedback = self._get_store().get("highlight_feedback", self._highlight_feedback_id(clip))
        if feedback:
            clip = {**clip, "highlight_feedback": feedback}
        music_feedback = self._get_store().get("music_feedback", "music_" + self._highlight_feedback_id(clip))
        if music_feedback:
            clip = {**clip, "music_feedback": music_feedback}
        from .media_preview import MediaPreview
        with self._workflow_init_lock:
            if not hasattr(self, "_media_preview"):
                self._media_preview = MediaPreview()
        preview_urls = {p: self._media_preview.register(value["path"]) for p, value in (clip.get("platform_variants") or {}).items()
                        if Path(value["path"]).is_file()}
        return {"status": "ok", "clip": clip, "preview_url": self._media_preview.register(clip["path"]), "preview_urls": preview_urls}

    @staticmethod
    def _highlight_feedback_id(clip):
        # Caption reviews may create a new revision while the selected story
        # stays identical. Bind feedback to the rendered file and its campaign,
        # leaving prior renders available for reference and never changing approval.
        return "feedback_" + digest({key: clip.get(key) for key in
            ("id", "file_hash", "campaign_version_id", "source_ranges")})[:32]

    def record_highlight_feedback(self, clip_id, payload):
        try:
            if not isinstance(payload, dict):
                raise ValueError("Masukan review highlight tidak valid.")
            labels = payload.get("labels", [])
            allowed = {"audience_fit", "off_topic", "needs_context", "incomplete_ending"}
            if (not isinstance(labels, list) or not labels or len(labels) > 4
                    or any(not isinstance(value, str) or value not in allowed for value in labels)):
                raise ValueError("Pilih penilaian highlight yang tersedia.")
            if "audience_fit" in labels and "off_topic" in labels:
                raise ValueError("Pilih cocok dengan audiens atau di luar topik.")
            note = payload.get("note", "")
            if not isinstance(note, str) or len(note) > 2000:
                raise ValueError("Catatan review maksimal 2.000 karakter.")
            store = self._get_store()
            with store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT data FROM entities WHERE kind='clip' AND id=?", (str(clip_id),)).fetchone()
                if not row:
                    raise ValueError("Clip tidak ditemukan.")
                clip = json.loads(row["data"])
                if payload.get("revision_id") and payload["revision_id"] != clip.get("revision_id"):
                    raise ValueError("Review clip sudah berubah. Muat ulang sebelum mengirim penilaian.")
                if not Path(clip["path"]).is_file() or file_digest(clip["path"]) != clip.get("file_hash"):
                    raise ValueError("File clip berubah atau tidak tersedia. Muat ulang review.")
                selection = clip.get("selection") or clip.get("clip_plan", {}).get("selection") or {}
                feedback = {"id": self._highlight_feedback_id(clip), "clip_id": clip["id"],
                    "revision_id": clip.get("revision_id"), "file_hash": clip.get("file_hash"),
                    "campaign_id": clip.get("campaign_id"), "campaign_version_id": clip.get("campaign_version_id"),
                    "profile_hash": selection.get("profile_hash"), "title": str(clip.get("title", ""))[:300],
                    "labels": list(dict.fromkeys(labels)), "note": note.strip(), "created_at": utc_now()}
                store._put(connection, "highlight_feedback", feedback["id"], feedback)
            return {"status": "ok", "feedback": feedback}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _highlight_feedback_for_campaign(self, campaign_id, limit=50):
        feedback = [item for item in self._get_store().list("highlight_feedback")
                    if item.get("campaign_id") == campaign_id]
        fields = ("clip_id", "title", "campaign_version_id", "profile_hash", "labels", "note", "created_at")
        return [{key: item.get(key) for key in fields} for item in feedback[:max(0, min(int(limit), 50))]]

    @staticmethod
    def _approval_digest(clip):
        values = {k: clip.get(k) for k in ("file_hash", "revision_id", "title", "caption", "captions", "campaign_id", "campaign_version_id")}
        for key in ("platform_variants", "platform_eligibility", "default_platform"):
            if key in clip:
                values[key] = clip[key]
        return digest(values)

    def review_clip(self, clip_id, payload):
        try:
            clip = self._get_store().get("clip", clip_id)
            if not clip:
                raise ValueError("Clip tidak ditemukan.")
            if any(p["clip_id"] == clip_id and p["status"] in ("queued", "uploading", "publishing") for p in self._get_store().publications()):
                raise ValueError("Batalkan antrean publikasi sebelum mengubah review.")
            clip = copy.deepcopy(clip)
            for field in ("title", "caption"):
                if field in payload:
                    clip[field] = str(payload[field]).strip()
            current_hash = file_digest(clip["path"])
            if current_hash != clip["file_hash"]:
                clip.update(file_hash=current_hash, review_status="pending", approval_hash=None)
                self._get_store().put("clip", clip_id, clip)
                raise ValueError("File video berubah. Muat preview ulang sebelum menyetujui.")
            action = payload.get("action", "save")
            if action not in ("approve", "save", "reject"):
                raise ValueError("Tindakan review tidak valid.")
            if action == "approve":
                from .clip_variants import verify_clip_files
                try:
                    verify_clip_files(clip)
                except ValueError:
                    clip.update(review_status="pending", approval_hash=None)
                    self._get_store().put("clip", clip_id, clip)
                    raise
            campaign = clip.get("campaign_snapshot") or next((c for c in self._get_cfg().get("campaigns", []) if c.get("id") == clip.get("campaign_id")), {})
            brief = campaign.get("brief", {})
            # Regenerate destination captions from the reviewed base and this
            # clip's campaign. Older UI payloads cannot override campaign tags,
            # and editing the base must never leave cached captions stale.
            _, clip["captions"] = platform_captions(clip.get("caption", ""), brief)
            from .additionals import destination_platforms
            platforms = set(destination_platforms(campaign)) | set(clip.get("captions", {}))
            for platform in ["", *sorted(platforms)]:
                if clip.get("platform_eligibility", {}).get(platform) is False:
                    continue
                required = list(brief.get("hashtags", [])) + (tags_for_platform(brief, platform) if platform else brief.get("tagged_accounts", []))
                caption = publication_caption(clip, platform)
                missing = [term for term in required if not caption_has_term(caption, term)]
                if brief.get("cta") and brief["cta"].casefold() not in caption.casefold():
                    missing.append(brief["cta"])
                if action == "approve" and missing:
                    label = {"tiktok": "TikTok", "instagram": "Instagram"}.get(platform, platform)
                    raise ValueError("Caption" + (" " + label if label else "") + " belum memuat: " + ", ".join(missing))
            if action == "approve" and clip.get("blockers"):
                raise ValueError("; ".join(clip["blockers"]))
            if action == "approve" and not clip.get("caption"):
                raise ValueError("Lengkapi caption publikasi.")
            if action == "approve" and not clip.get("title"):
                raise ValueError("Lengkapi judul clip.")
            clip["revision_id"] = "rev_" + digest({k: clip.get(k) for k in ("id", "file_hash", "title", "caption", "captions", "campaign_version_id")})[:24]
            clip["review_status"] = "approved" if action == "approve" else "rejected" if action == "reject" else "pending"
            clip["approval_hash"] = self._approval_digest(clip) if action == "approve" else None
            clip["reviewed_at"] = utc_now()
            self._get_store().put("clip", clip_id, clip)
            self._get_store().put("clip_revision", clip["revision_id"], clip)
            return {"status": "ok", "clip": clip}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def rerender_clip(self, clip_id, editing):
        try:
            clip = self._get_store().get("clip", clip_id)
            if not clip or not clip.get("source_url") or not clip.get("highlight"):
                raise ValueError("Clip lama belum memiliki rencana sumber. Buat ulang dari sumber video.")
            from .campaigns import normalize_campaign, campaign_processing_options, campaign_version_record
            campaign = copy.deepcopy(clip["campaign_snapshot"])
            campaign["id"] = clip["campaign_id"]
            original_preset = campaign.get("editing", {}).get("preset_id")
            original_pool = copy.deepcopy(campaign.get("editing", {}).get("template_pool"))
            original_mode = campaign.get("editing", {}).get("selection_mode")
            original_additional = copy.deepcopy(campaign.get("editing", {}).get("additional", []))
            campaign["editing"].update(editing)
            # Campaign additions are not revision controls. A stale/malicious
            # caller cannot remove the face gate or replace its reference photo.
            campaign["editing"]["additional"] = original_additional
            if original_pool is not None:
                campaign["editing"]["template_pool"] = original_pool
                campaign["editing"]["selection_mode"] = "weighted_random"
            else:
                campaign["editing"].pop("template_pool", None)
                if original_mode is None:
                    campaign["editing"].pop("selection_mode", None)
                else:
                    campaign["editing"]["selection_mode"] = original_mode
            if original_preset:
                # A caller cannot downgrade a preset clip into the legacy path
                # by clearing its preset identifier through a stale review UI.
                campaign["editing"]["preset_id"] = original_preset
            if "template_id" in editing:
                campaign["editing"]["template_mode"] = "fixed"
            uses_preset = original_pool is not None or bool(campaign["editing"].get("preset_id"))
            # Existing clips keep legacy editing on revision; new preset clips
            # cannot override fixed features through an old review UI.
            campaign = normalize_campaign(campaign, apply_preset=uses_preset)
            options = campaign_processing_options(campaign, 1) if uses_preset else {
                "num_clips": 1, "portrait": True, "add_captions": clip.get("has_captions", True),
                "add_hook": clip.get("has_hook", False), "subtitle_lang": campaign.get("language") or "id"}
            job = {"id": "job_" + uuid.uuid4().hex, "source": clip["source_url"], "source_id": clip["source_id"],
                "campaign_id": clip["campaign_id"], "campaign": campaign,
                "options": options,
                "highlight_overrides": [clip["highlight"]], "status": "queued", "progress": 0, "created_at": utc_now()}
            # A revision is always reviewed explicitly, even for automatic campaigns.
            job["campaign"]["editing"]["review_mode"] = "manual"
            version = campaign_version_record(job["campaign"])
            if self._get_store().get("campaign_version", version["id"]) is None:
                self._get_store().put("campaign_version", version["id"], version)
            job["campaign"]["version_id"] = version["id"]
            self._get_store().put("job", job["id"], job)
            self._start_next_job()
            return {"status": "ok", "job_id": job["id"]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_workflow_jobs(self):
        store = self._get_store()
        self._start_next_job()
        jobs = store.list("job")
        with self._job_event_lock:
            live = copy.deepcopy(self._job_live)
        generated = {}
        for clip in store.list("clip"):
            if clip.get("job_id"):
                generated.setdefault(clip["job_id"], []).append(clip)
        queue_order = {j["id"]: i for i, j in enumerate(sorted(
            [j for j in jobs if j.get("status") == "queued"],
            key=lambda j: (j.get("queued_at") or j.get("created_at") or "", j["id"])), 1)}
        for job in jobs:
            job.update(live.get(job["id"], {}))
            job.setdefault("title", Path(job.get("source", "")).name or job.get("source", ""))
            job.setdefault("logs", [])
            job.setdefault("clips", [])
            # Render states belong to this job. Add final clip identifiers only
            # from the same job, so review links never point at another source.
            outputs = generated.get(job["id"], [])
            by_index = {int(Path(c["path"]).parent.name.removeprefix("clip-")): c for c in outputs
                        if Path(c.get("path", "")).parent.name.removeprefix("clip-").isdigit()}
            seen = set()
            for clip in job["clips"]:
                final = by_index.get(clip.get("index"))
                if final:
                    clip.update(clip_id=final["id"], path=final["path"], review_status=final.get("review_status"))
                    seen.add(final["id"])
            for clip in outputs:
                if clip["id"] not in seen:
                    job["clips"].append({"index": len(job["clips"])+1, "title": clip.get("title", ""),
                        "status": "done", "step": "Selesai", "step_progress": 1,
                        "clip_id": clip["id"], "path": clip["path"], "review_status": clip.get("review_status")})
            states = job["clips"]
            job["counts"] = {"requested": job.get("options", {}).get("num_clips") or None,
                "planned": len(states), "completed": sum(c.get("status") == "done" for c in states),
                "failed": sum(c.get("status") == "error" for c in states),
                "cancelled": sum(c.get("status") == "cancelled" for c in states)}
            job["queue_position"] = queue_order.get(job["id"])
        jobs.sort(key=lambda j: (j.get("created_at") or "", j["id"]), reverse=True)
        if getattr(self, "worker_enabled", True):
            self._queue_job_titles(jobs)
        return {"status": "ok", "jobs": jobs, "worker_note": None if getattr(self, "worker_enabled", True) else "Pekerjaan dikendalikan oleh jendela SSR_CLIPPER lain yang masih terbuka."}

    def control_job(self, job_id, action):
        if not getattr(self, "worker_enabled", True):
            return {"status": "error", "message": "Gunakan jendela SSR_CLIPPER yang menjalankan pekerjaan untuk mengubah antrean."}
        store = self._get_store()
        with self._job_lock:
            job = store.get("job", job_id)
            if not job:
                return {"status": "error", "message": "Pekerjaan tidak ditemukan."}
            if action == "cancel" and job["status"] in ("queued", "paused", "running"):
                if job["status"] == "running":
                    self._cancel_event.set()
                store.update("job", job_id, {"status": "cancelling" if job["status"] == "running" else "cancelled",
                                            "step": "Membatalkan" if job["status"] == "running" else "Dibatalkan"})
            elif action == "resume" and job["status"] in ("interrupted", "failed", "partial", "cancelled", "paused"):
                store.update("job", job_id, {"status": "queued", "error": None, "queued_at": utc_now(), "step": "Menunggu antrean"})
                self._start_next_job()
            elif action == "pause" and job["status"] == "queued":
                store.update("job", job_id, {"status": "paused", "step": "Dijeda"})
            else:
                return {"status": "error", "message": "Tindakan tidak tersedia untuk status pekerjaan ini."}
        return {"status": "ok"}

    def preview_distribution(self, clip_ids, campaign_id=None, max_per_account_per_day=2):
        try:
            store = self._get_store()
            clips = [store.get("clip", cid) for cid in dict.fromkeys(clip_ids)]
            if not clips or any(c is None for c in clips):
                raise ValueError("Pilih clip yang tersedia.")
            for clip in clips:
                if clip.get("approval_hash") != self._approval_digest(clip):
                    raise ValueError("Review clip sudah berubah. Setujui kembali sebelum distribusi.")
                if file_digest(clip["path"]) != clip.get("file_hash"):
                    store.update("clip", clip["id"], {"review_status": "pending", "approval_hash": None})
                    raise ValueError("File berubah setelah review.")
                from .clip_variants import verify_clip_files
                verify_clip_files(clip)
            accounts = self.get_repliz_accounts()
            if accounts.get("status") != "ok":
                raise ValueError(accounts.get("message", "Akun tidak dapat dimuat."))
            cfg = self._get_cfg()
            zone_name = scheduling_timezone(cfg)
            assignments = plan_distribution(clips, cfg.get("campaigns", []), store.list("account_profile"), accounts.get("accounts", []), store.publications(), timezone_name=zone_name)
            token = "preview_" + uuid.uuid4().hex
            store.put("distribution_preview", token, {"id": token, "assignments": assignments, "timezone": zone_name, "created": time.time()})
            return {"status": "ok", "preview_id": token, "assignments": assignments, "timezone": zone_name, "campaign_name": "Campaign sesuai clip"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _validate_distribution_preview(self, record, accounts):
        """Check current policy for the persisted batch before edits or reservation."""
        if not record or time.time() - record["created"] > 900:
            raise ValueError("Preview kedaluwarsa. Buat preview distribusi ulang.")
        if accounts.get("status") != "ok":
            raise ValueError("Tidak dapat memvalidasi akun tujuan.")
        from .publishing import eligible_accounts, account_limit
        cfg = self._get_cfg()
        zone_name = scheduling_timezone(cfg)
        if record.get("timezone", "Asia/Makassar") != zone_name:
            raise ValueError("Zona waktu global berubah. Buat preview distribusi ulang.")
        store = self._get_store()
        profiles = store.list("account_profile")
        campaigns = cfg.get("campaigns", [])
        for assignment in record["assignments"]:
            clip = store.get("clip", assignment["clip_id"])
            if (not clip or clip.get("review_status") != "approved"
                    or clip.get("approval_hash") != assignment.get("approval_hash")
                    or clip.get("approval_hash") != self._approval_digest(clip)):
                raise ValueError("Review clip berubah. Buat preview ulang.")
            from .clip_variants import publication_media, verify_clip_files
            verify_clip_files(clip)
            media = publication_media(clip, assignment["platform"])
            if media["path"] != assignment["clip_path"] or media["file_hash"] != assignment["file_hash"]:
                raise ValueError("Versi video platform berubah setelah review.")
            campaign = next((c for c in campaigns if c.get("id") == assignment["campaign_id"]), {})
            if campaign.get("status") != "active":
                raise ValueError("Campaign tidak aktif.")
            allowed = eligible_accounts(campaign, profiles, accounts["accounts"])
            profile = next((p for a, p in allowed if str(a.get("_id", a.get("id"))) == assignment["account_id"]), None)
            if profile is None:
                raise ValueError("Akun tujuan tidak lagi cocok dengan campaign.")
            if (assignment.get("timezone") != zone_name
                    or account_limit(campaign, profile) != assignment["daily_limit"]
                    or normalize_upload_times(profile.get("upload_times")) != normalize_upload_times(assignment.get("upload_times"))):
                raise ValueError("Jadwal, kuota akun, atau zona waktu berubah. Buat preview distribusi ulang.")
            if parse_schedule_time(assignment["scheduled_at"], zone_name) <= datetime.now(timezone.utc):
                raise ValueError("Jadwal preview sudah lewat. Buat preview distribusi ulang.")
        return zone_name

    def update_distribution_schedule(self, preview_id, assignment_id, scheduled_at):
        try:
            store = self._get_store()
            accounts = self.get_repliz_accounts()
            def edit(record, existing):
                zone_name = scheduling_timezone(self._get_cfg())
                target = next((a for a in record["assignments"] if a["id"] == assignment_id), None)
                if target is None:
                    raise ValueError("Baris jadwal tidak ditemukan dalam preview ini.")
                when = parse_schedule_time(scheduled_at, zone_name)
                target["scheduled_at"] = when.isoformat()
                target["local_day"] = publication_day(target, zone_name)
                target["schedule_edited"] = True
                self._validate_distribution_preview(record, accounts)
                history = list(existing)
                for assignment in record["assignments"]:
                    validate_reservation(assignment, history)
                    history.append(assignment)
            record = store.edit_distribution_preview(preview_id, edit)
            return {"status": "ok", "preview_id": record["id"], "assignments": record["assignments"], "timezone": record["timezone"]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def confirm_distribution(self, preview):
        try:
            store = self._get_store()
            accounts = self.get_repliz_accounts()
            inserted = store.reserve_distribution_preview(preview if isinstance(preview, str) else "",
                lambda record: self._validate_distribution_preview(record, accounts), validate_reservation)
            self._start_upload_worker()
            return {"status": "ok", "total_scheduled": len(inserted), "message": "Publikasi masuk antrean." if inserted else "Paket ini sudah masuk antrean."}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def quick_upload(self, clip_ids):
        return {"status": "review_required", "message": "Review clip, lalu periksa preview distribusi sebelum upload."}

    def _start_upload_worker(self):
        if not getattr(self, "worker_enabled", True):
            return
        self._get_store()
        if not self._upload_lock.acquire(blocking=False):
            return
        threading.Thread(target=self._upload_pending, daemon=True).start()

    def _upload_pending(self):
        try:
            while True:
                publication = self._get_store().claim_publication()
                if not publication:
                    return
                self._send_publication(publication)
        finally:
            self._upload_lock.release()

    def _send_publication(self, publication):
        store = self._get_store()
        sent_schedule = False
        try:
            if datetime.fromisoformat(publication["scheduled_at"]) <= datetime.now(timezone.utc):
                raise ValueError("Jadwal sudah lewat. Batalkan paket ini lalu buat preview distribusi baru.")
            clip = store.get("clip", publication["clip_id"])
            if not clip or clip.get("approval_hash") != publication.get("approval_hash"):
                raise ValueError("Review berubah setelah paket dijadwalkan.")
            if clip.get("review_status") != "approved" or clip.get("approval_hash") != self._approval_digest(clip):
                raise ValueError("Clip harus disetujui kembali sebelum dikirim.")
            from .clip_variants import publication_media, verify_clip_files
            verify_clip_files(clip)
            media = publication_media(clip, publication["platform"])
            if media["path"] != publication["clip_path"] or media["file_hash"] != publication["file_hash"]:
                raise ValueError("Versi platform berbeda dari file yang disetujui.")
            if file_digest(publication["clip_path"]) != publication["file_hash"]:
                raise ValueError("File berubah; upload dibatalkan sebelum pengiriman.")
            from .publishing import eligible_accounts, account_limit
            campaign = next((c for c in self._get_cfg().get("campaigns", []) if c.get("id") == publication["campaign_id"]), {})
            if campaign.get("status") != "active":
                raise ValueError("Campaign tidak aktif; periksa paket publikasi.")
            accounts = self.get_repliz_accounts()
            if accounts.get("status") != "ok":
                raise ValueError(accounts.get("message", "Akun belum dapat diperiksa."))
            allowed = eligible_accounts(campaign, store.list("account_profile"), accounts["accounts"])
            profile = next((p for a,p in allowed if str(a.get("_id",a.get("id"))) == publication["account_id"]), None)
            if profile is None:
                raise ValueError("Profil akun tujuan berubah; buat preview distribusi ulang.")
            zone_name = scheduling_timezone(self._get_cfg())
            validate_reservation({**publication, "timezone": zone_name, "local_day": publication_day(publication, zone_name),
                                  "daily_limit": account_limit(campaign, profile)},
                                 [p for p in store.publications() if p["id"] != publication["id"]])
            cfg = self._get_cfg().get("repliz", {})
            if not cfg.get("access_key") or not cfg.get("secret_key"):
                raise ValueError("Repliz keys belum dikonfigurasi.")
            uploader = self._make_uploader(cfg)
            media_url = publication.get("media_url")
            if not media_url:
                ok, result = uploader.upload_video_to_storage(publication["clip_path"])
                if not ok:
                    raise ValueError(str(result))
                media_url = result
                store.update_publication(publication["id"], {"media_url": media_url})
            store.update_publication(publication["id"], {"status": "publishing"})
            sent_schedule = True
            when = datetime.fromisoformat(publication["scheduled_at"]).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            ok, result = uploader.create_schedule(publication["account_id"], publication["clip_title"], publication["caption"], media_url, when)
            if not ok:
                if isinstance(result, dict):
                    # Only an explicit adapter guarantee permits another submission.
                    # Legacy string errors and unknown outcomes remain uncertain.
                    sent_schedule = result.get("uncertain_submission") is not False
                    raise ValueError(result.get("message") or "Provider tidak mengembalikan ID jadwal.")
                raise ValueError(str(result) or "Provider tidak mengembalikan ID jadwal.")
            if not result:
                raise ValueError(str(result) or "Provider tidak mengembalikan ID jadwal.")
            store.update_publication(publication["id"], {"status": "scheduled", "schedule_id": result, "error": None, "uncertain_submission": False})
        except Exception as exc:
            store.update_publication(publication["id"], {"status": "needs_attention" if sent_schedule else "failed", "error": str(exc), "uncertain_submission": sent_schedule})

    def _auto_publish_job(self, job):
        clips = [c for c in self._get_store().list("clip") if c.get("job_id") == job["id"]]
        ready = []
        for clip in clips:
            if clip.get("warnings") or clip.get("blockers"):
                continue
            if self.review_clip(clip["id"], {"action": "approve"}).get("status") == "ok":
                ready.append(clip["id"])
        if ready:
            preview = self.preview_distribution(ready)
            if preview.get("status") == "ok":
                self.confirm_distribution(preview["preview_id"])
            else:
                self._get_store().update("job", job["id"], {"attention": preview.get("message")})

    def sync_publications(self, force=True):
        if not getattr(self, "worker_enabled", True):
            return {"status": "error", "message": "Sinkronisasi berjalan melalui jendela SSR_CLIPPER utama."}
        try:
            self._get_store()
            with self._workflow_init_lock:
                if getattr(self, "_sync_running", False):
                    return {"status": "running"}
                self._sync_running = True
            threading.Thread(target=self._sync_publications, args=(force,), daemon=True).start()
            return {"status": "started"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _sync_publications(self, force=True):
        with self._provider_lock:
            self._sync_provider_locked(force)

    def _sync_provider_locked(self, force=True):
        try:
            self._sync_error = None
            cfg = self._get_cfg().get("repliz", {})
            client = ReplizClient(cfg.get("access_key"), cfg.get("secret_key"))
            for publication in self._get_store().publications():
                if not force and publication.get("next_sync_at", 0) > time.time():
                    continue
                try:
                    if not publication.get("schedule_id"):
                        if publication["status"] == "needs_attention" and publication.get("media_url"):
                            fields = client.reconcile(publication)
                            publication = self._get_store().update_publication(publication["id"], fields)
                        else:
                            continue
                    fields = schedule_update(client.schedule(publication["schedule_id"]))
                    fields.update(sync_failures=0, next_sync_at=0)
                    current = self._get_store().update_publication(publication["id"], fields)
                    if current.get("status") == "published" and current.get("post_id"):
                        try:
                            metrics = client.statistics(current["post_id"], current["account_id"])
                            self._get_store().put("metric_snapshot", uuid.uuid4().hex, {"publication_id": current["id"], "observed_at": utc_now(), "metrics": metrics})
                            self._get_store().update_publication(current["id"], {"metrics": metrics, "metrics_at": utc_now(), "metrics_error": None})
                        except Exception as exc:
                            self._get_store().update_publication(current["id"], {"metrics_error": str(exc)})
                        if not current.get("post_url"):
                            try:
                                content = client.content(current["post_id"], current["account_id"])
                                content = content.get("data", content)
                                url = content.get("permalink") or content.get("url") or content.get("postUrl")
                                if url:
                                    self._get_store().update_publication(current["id"], {"post_url": url})
                            except Exception:
                                pass
                except Exception as exc:
                    failures = int(publication.get("sync_failures", 0)) + 1
                    self._get_store().update_publication(publication["id"], {"sync_error": str(exc), "sync_attempted_at": utc_now(),
                        "sync_failures": failures, "next_sync_at": time.time() + min(3600, 300 * 2**min(failures, 4))})
        except Exception as exc:
            self._sync_error = str(exc)
        finally:
            self._last_sync = time.monotonic()
            self._sync_running = False

    def get_publication_tracking(self):
        try:
            store = self._get_store()
            return {"status": "ok", "publications": store.publications(), "timezone": scheduling_timezone(self._get_cfg()),
                    "sync_running": getattr(self, "_sync_running", False), "sync_error": getattr(self, "_sync_error", None)}
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    def control_publication(self, publication_id, action):
        if not getattr(self, "worker_enabled", True):
            return {"status": "error", "message": "Gunakan jendela SSR_CLIPPER utama untuk mengubah publikasi."}
        self._get_store()
        with self._provider_lock:
            try:
                return self._control_publication_locked(publication_id, action)
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

    def _control_publication_locked(self, publication_id, action):
        store = self._get_store()
        publication = store.publication(publication_id)
        if not publication:
            return {"status": "error", "message": "Publikasi tidak ditemukan."}
        if action == "cancel" and publication["status"] in ("queued", "failed") and not publication.get("schedule_id") and not publication.get("uncertain_submission"):
            store.update_publication(publication_id, {"status": "cancelled"}, expected_status=("queued", "failed"))
        elif action == "retry" and publication["status"] == "failed" and not publication.get("schedule_id") and not publication.get("uncertain_submission"):
            store.update_publication(publication_id, {"status": "queued", "error": None}, expected_status=("failed",))
            self._start_upload_worker()
        elif action == "retry" and publication["status"] == "failed" and publication.get("schedule_id"):
            cfg = self._get_cfg().get("repliz", {})
            client = ReplizClient(cfg.get("access_key"), cfg.get("secret_key"))
            fresh = schedule_update(client.schedule(publication["schedule_id"]))
            if fresh.get("status") != "failed":
                store.update_publication(publication_id, fresh)
                raise ValueError("Status provider sudah berubah. Tracking diperbarui.")
            store.update_publication(publication_id, {"status": "needs_attention", "error": "Menunggu hasil pengulangan jadwal provider."}, expected_status=("failed",))
            client.retry(publication["schedule_id"])
            store.update_publication(publication_id, {"status": "scheduled", "error": None})
        else:
            return {"status": "error", "message": "Periksa jadwal di provider untuk publikasi yang sudah terkirim atau tidak pasti."}
        return {"status": "ok"}

    def export_tracking_csv(self):
        import csv
        import webview
        paths = webview.windows[0].create_file_dialog(webview.SAVE_DIALOG, save_filename="clip-tracking.csv", file_types=("CSV (*.csv)",))
        if not paths:
            return {"status": "cancelled"}
        path = paths if isinstance(paths, str) else paths[0]
        zone_name = scheduling_timezone(self._get_cfg())
        fields = ("id", "clip_title", "campaign_id", "account_name", "platform", "status", "scheduled_at", "post_url", "metrics_at", "metrics", "metrics_error")
        with open(path, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for publication in self._get_store().publications():
                row = {k: publication.get(k, "") for k in fields}
                for key in ("scheduled_at", "metrics_at"):
                    row[key] = display_schedule_time(publication.get(key), zone_name)
                row["metrics"] = json.dumps(publication.get("metrics", {}), ensure_ascii=False)
                row = {k: "'" + str(v) if str(v).startswith(("=", "+", "-", "@")) else v for k, v in row.items()}
                writer.writerow(row)
        return {"status": "ok", "path": path}

    def workflow_tick(self):
        if not getattr(self, "worker_enabled", True):
            # An already-open secondary window can take over once the first exits.
            if not self._worker_lease.acquire():
                return
            self.worker_enabled = True
            self._get_store().recover_interrupted()
        self._get_store()
        self._start_next_job()
        self._start_upload_worker()
        if time.monotonic() - self._last_sync > 300 and any(p.get("schedule_id") or p["status"] == "needs_attention" for p in self._get_store().publications()):
            self.sync_publications(force=False)
