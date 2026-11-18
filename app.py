#!/usr/bin/python3.12
import os
import sys

# Explorer's Python launcher reads the shebang above. Also select the same
# installed interpreter when this entry point is run with another Python.
if (__name__ == "__main__" and sys.platform == "win32"
        and not getattr(sys, "frozen", False)
        and (sys.version_info[:2] != (3, 12) or sys.prefix != sys.base_prefix)):
    import subprocess
    from pathlib import Path
    raise SystemExit(subprocess.call([
        "py", "-3.12", str(Path(__file__).resolve()), *sys.argv[1:]
    ]))

import threading
import base64
import requests
import webview
import json
import subprocess
import logging
import traceback
import tempfile
from datetime import datetime
from pathlib import Path
from config.config_manager import ConfigManager
from utils.helpers import get_app_dir, get_bundle_dir, get_ffmpeg_path, get_ytdlp_path
from clipper_core import AutoClipperCore
from services.workflow import WorkflowMixin
from services.music_review import MusicReviewMixin
from services.campaigns import CampaignMixin
from services.dependencies import DependencyMixin

# ── Error Logging Setup ──
_log_file = get_app_dir() / "error.log"

def _setup_logger():
    logger = logging.getLogger("ssr_clipper")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(_log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    # pywebview reports native WebView2 initialization failures to its own
    # logger. Keep those errors next to our startup log, including failures
    # that never raise back into main().
    webview_logger = logging.getLogger("pywebview")
    webview_logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        if handler not in webview_logger.handlers:
            webview_logger.addHandler(handler)
    return logger

app_logger = _setup_logger()

def log_error(msg, exc=None):
    """Log error with optional exception traceback."""
    if exc:
        tb = traceback.format_exc()
        app_logger.error(f"{msg}\n{tb}")
    else:
        app_logger.error(msg)

# Redirect unhandled exceptions to error.log
def _global_except_hook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    app_logger.critical(f"UNHANDLED EXCEPTION:\n{tb_str}")
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _global_except_hook

class ReplizUploaderAdapter:
    def __init__(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key

    @staticmethod
    def _response_error(response):
        """Keep the HTTP status even when the provider supplies validation details."""
        message = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("error") or ""
            if isinstance(message, list):
                message = "; ".join(str(item) for item in message)
        except (ValueError, TypeError):
            pass
        return f"HTTP {response.status_code}" + (f": {message}" if message else "")

    def upload_video_to_storage(self, file_path):
        """Upload file video ke Repliz Storage pakai 3-step flow resmi:
        Init File -> PUT ke presigned URL -> Complete File.

        Returns:
            (True, public_url)      kalau sukses
            (False, error_message)  kalau gagal di step manapun — error_message berisi
                                     alasan SPESIFIK (HTTP code + pesan dari Repliz kalau ada),
                                     bukan pesan generik.
        """
        import requests
        from requests.auth import HTTPBasicAuth
        import os
        from urllib.parse import quote
        try:
            auth = HTTPBasicAuth(self.access_key, self.secret_key)
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            mimetype = "video/mp4"

            # Step 1: Init File
            init_res = requests.post(
                "https://api.repliz.com/public/storage/file/init",
                json={"filename": filename, "size": size, "mimetype": mimetype},
                auth=auth,
                timeout=30
            )
            # PENTING: terima SEMUA kode 2xx sebagai sukses, JANGAN cuma 1 kode spesifik.
            # Dokumentasi Repliz nunjukin contoh "200", tapi di real-world endpoint ini
            # kadang balikin 201 Created (karena secara REST dia memang MEMBUAT resource
            # baru, sebuah upload session). Kalau cuma nerima 200 doang, request yang
            # sebenarnya SUKSES (201) bakal salah dianggap gagal.
            if not (200 <= init_res.status_code < 300):
                return False, f"Init File gagal: {self._response_error(init_res)}"
            init_data = init_res.json()
            if isinstance(init_data, dict):
                init_data = init_data.get("data", init_data)
            if not isinstance(init_data, dict):
                return False, "Init File gagal: response bukan objek file."
            file_id = init_data.get("id")
            upload_url = init_data.get("upload")
            public_url = init_data.get("url")
            if not file_id or not upload_url or not public_url:
                return False, "Init File gagal: response tidak lengkap (id/upload/url kosong)"

            # Step 2: PUT raw binary ke presigned URL
            with open(file_path, "rb") as f:
                put_res = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": mimetype},
                    timeout=300
                )
            # Sama, terima semua 2xx (bukan cuma daftar kode tebakan 200/201/204).
            if not (200 <= put_res.status_code < 300):
                return False, f"Upload ke presigned URL gagal: HTTP {put_res.status_code}"

            # Step 3: Complete File
            # Endpoint ini per dokumentasi resmi balikin 204 No Content kalau sukses
            # (https://docs.repliz.com/api/storage/complete-file.html). Tapi supaya gak
            # kena masalah "kode beda dari dokumentasi" lagi kayak Step 1 barusan, kita
            # gak nebak kode pastinya satu-satu lagi — semua 2xx dianggap sukses.
            complete_res = requests.post(
                f"https://api.repliz.com/public/storage/file/{quote(str(file_id), safe='')}/complete",
                auth=auth,
                timeout=30
            )
            if not (200 <= complete_res.status_code < 300):
                return False, f"Complete File gagal: {self._response_error(complete_res)}"

            return True, public_url
        except Exception as e:
            return False, f"Exception saat upload ke storage: {str(e)}"

    def create_schedule(self, account_id, title, description, media_url, schedule_at_iso, music=None):
        """Buat scheduled post video lewat POST /public/schedule.

        Args:
            account_id: ID akun Repliz tujuan
            title: judul (dipakai platform tertentu, boleh string kosong)
            description: caption post
            media_url: URL video hasil upload_video_to_storage()
            schedule_at_iso: string ISO 8601, format "YYYY-MM-DDTHH:MM:SS.000Z"
            music: dict {"id","artist","name","thumbnail","volume"} atau None.
                volume berisi persentase video/music; nilai lama tanpa volume
                memakai default dokumentasi Repliz (50/100).

        Returns:
            (True, schedule_id) kalau sukses
            (False, {message, uncertain_submission, http_status}) kalau gagal.
            uncertain_submission=False hanya jika request pasti belum dikirim
            atau provider menolak request secara pasti.
        """
        import requests
        from requests.auth import HTTPBasicAuth
        request_started = False

        def failure(message, uncertain, http_status=None):
            return False, {"message": str(message), "uncertain_submission": uncertain,
                           "http_status": http_status}

        try:
            auth = HTTPBasicAuth(self.access_key, self.secret_key)
            body = {
                "title": title or "",
                "description": description or "",
                "topic": "",
                "type": "video",
                "medias": [{
                    "alt": "",
                    "customThumbnail": False,
                    "type": "video",
                    "thumbnail": "",
                    "url": media_url
                }],
                "meta": {"title": "", "description": "", "url": ""},
                "additionalInfo": {
                    "isAiGenerated": False,
                    "isDraft": False,
                    "isAutoAddMusic": False,
                    "collaborators": [],
                    "mentions": [],
                    "products": [],
                    "tags": []
                },
                "replies": [],
                "accountId": account_id,
                "scheduleAt": schedule_at_iso
            }
            # Music is optional. Sending an empty object invokes nested validation,
            # including the required volume.video and volume.music fields.
            if music:
                if not isinstance(music, dict) or not music.get("id"):
                    return failure("Musik Repliz harus menyertakan ID track.", False)
                volume = music.get("volume") or {}
                if not isinstance(volume, dict):
                    return failure("Volume musik Repliz harus berisi video dan music.", False)
                body["additionalInfo"]["music"] = {
                    **music, "volume": {"video": 50, "music": 100, **volume}
                }
            # Validate serialization before the transport boundary. A local payload
            # error cannot have created a schedule and remains safe to retry.
            json.dumps(body, allow_nan=False)
            request_started = True
            res = requests.post(
                "https://api.repliz.com/public/schedule",
                json=body,
                auth=auth,
                timeout=30
            )
            if 200 <= res.status_code < 300:
                try:
                    data = res.json()
                except ValueError:
                    return failure("Provider menerima request tetapi tidak mengembalikan ID jadwal.", True, res.status_code)
                if isinstance(data, dict):
                    data = data.get("data", data)
                schedule_id = (data.get("scheduleId") or data.get("_id") or data.get("id")) if isinstance(data, dict) else None
                if not schedule_id:
                    return failure("Provider menerima request tetapi tidak mengembalikan ID jadwal.", True, res.status_code)
                return True, schedule_id
            else:
                # 408/499 may come from a timeout at a proxy after forwarding the
                # request. Keep those, 5xx and unexpected responses for reconciliation.
                rejected = 400 <= res.status_code < 500 and res.status_code not in (408, 499)
                return failure(self._response_error(res), not rejected, res.status_code)
        except Exception as e:
            return failure(e, request_started)
    

# Fix for PyInstaller windowed mode (console=False)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')


from services.external_templates import ExternalTemplateMixin
from services.template_editor import TemplateEditorMixin


class WebAPI(MusicReviewMixin, WorkflowMixin, CampaignMixin, DependencyMixin, ExternalTemplateMixin, TemplateEditorMixin):
    def __init__(self):
        app_dir = get_app_dir()
        self.config_file = str(app_dir / "config.json")
        self.output_dir = str(app_dir / "output")
        self.status = "idle"
        self.progress = 0.0
        self.core = None
        self.thread = None
        self.current_job = None
        self.job_history = []
        from services.worker_lease import WorkerLease
        import atexit
        self._worker_lease = WorkerLease(app_dir / 'workflow.worker.lock')
        self.worker_enabled = self._worker_lease.acquire()
        atexit.register(self._worker_lease.close)
        self.output_dir = str(self._get_cfg().get('output_dir') or self.output_dir)

    def _make_uploader(self, config):
        return ReplizUploaderAdapter(config["access_key"], config["secret_key"])

    def get_progress(self):
        return {"status": self.status, "progress": self.progress}

    def get_clips_status(self):
        """Return per-clip processing state for frontend progress panel."""
        if self.core:
            return {"clips": self.core.get_clips_state()}
        return {"clips": []}

    def log_frontend_error(self, message, source="", lineno=0, colno=0, stack=""):
        """Called from JS window.onerror to record frontend errors in error.log"""
        log_error(
            f"[FRONTEND] {message}\n"
            f"  Source: {source}:{lineno}:{colno}\n"
            f"  Stack: {stack}"
        )
        return {"status": "ok"}

    def get_ai_settings(self):
        cfg = self._get_cfg()
        return cfg.get("ai_providers", {})

    def get_scheduling_settings(self):
        from services.scheduling import scheduling_timezone
        try:
            return {"status": "ok", "timezone": scheduling_timezone(self._get_cfg()), "time_format": "12h"}
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    def save_scheduling_settings(self, settings):
        from services.scheduling import scheduling_timezone
        try:
            if not isinstance(settings, dict) or not isinstance(settings.get("timezone"), str):
                raise ValueError("Pilih zona waktu global di Pengaturan.")
            zone = scheduling_timezone({"timezone": settings["timezone"].strip()})
            cfg = self._get_cfg()
            cfg["timezone"] = zone
            self._get_cfg_manager().save_config(cfg)
            return {"status": "ok", "timezone": zone, "time_format": "12h"}
        except (ValueError, OSError) as exc:
            return {"status": "error", "message": str(exc)}

    def get_provider_type(self):
        cfg = self._get_cfg()
        return {"provider_type": cfg.get("provider_type", "ytclip")}


    def get_models(self, base_url, api_key):
        if not base_url:
            return {"models": []}
            
        # Check if it's Gemini (Google AI Studio)
        if "generativelanguage.googleapis.com" in base_url:
            return {"models": [
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-pro-preview",
                "gemini-3-flash-preview",
                "gemini-3.1-flash-tts-preview"
                # Info audio/STT-capable model mana aja sekarang ada di
                # GEMINI_AUDIO_MODELS (web/app.js), gak perlu diulang di sini.
            ]}
            
        # Check if it's Anthropic
        if "api.anthropic.com" in base_url:
            return {"models": [
                "claude-3-5-sonnet-20240620", 
                "claude-3-opus-20240229", 
                "claude-3-sonnet-20240229", 
                "claude-3-haiku-20240307"
            ]}
            
        url = self._get_models_url(base_url)
        try:
            resp = requests.get(url, headers=self._auth_headers(api_key), timeout=15)
            if resp.status_code != 200:
                return {"models": [], "error": str(resp.status_code)}
            data = resp.json()
            items = data.get("data", [])
            models = []
            for item in items:
                mid = item.get("id")
                if mid:
                    models.append(mid)
            return {"models": models}
        except requests.exceptions.Timeout:
            return {"models": [], "error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"models": [], "error": "connection failed"}
        except Exception as e:
            return {"models": [], "error": str(e)[:60]}

    def test_model(self, base_url, api_key, model, model_type):
        """Test apakah model tertentu BENERAN bisa dipanggil (real call), bukan cuma ada di daftar."""
        if model_type == 'local':
            try:
                from faster_whisper.utils import download_model
            except ImportError:
                return {"status": "error", "message": "Error: whisper library belum terinstall"}
            try:
                download_model(model, local_files_only=True)
                return {"status": "ok", "message": "Ready - Installed"}
            except Exception:
                return {"status": "error", "message": "Error: model belum di-download"}

        if not base_url or not api_key:
            return {"status": "error", "message": "Empty"}
        if not model:
            return {"status": "error", "message": "Error: model belum dipilih"}

        headers = self._auth_headers(api_key)
        url = base_url.rstrip("/")

        try:
            if model_type == 'chat':
                endpoint = url if url.endswith("/chat/completions") else f"{url}/chat/completions"
                resp = requests.post(endpoint, headers=headers, json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1
                }, timeout=15)
                if resp.status_code == 200:
                    return {"status": "ok", "message": "Ready - API tested"}
                return {"status": "error", "message": f"Error {resp.status_code}"}

            elif model_type == 'tts':
                endpoint = url if url.endswith("/audio/speech") else f"{url}/audio/speech"
                tts_headers = dict(headers)
                tts_headers["Content-Type"] = "application/json"
                resp = requests.post(endpoint, headers=tts_headers, json={
                    "model": model,
                    "input": "test",
                    "voice": "alloy"
                }, timeout=20)
                if resp.status_code == 200 and resp.content:
                    return {"status": "ok", "message": "Ready - API tested"}
                return {"status": "error", "message": f"Error {resp.status_code}"}

            elif model_type == 'stt':
                endpoint = url if url.endswith("/audio/transcriptions") else f"{url}/audio/transcriptions"
                wav_bytes = self._generate_silent_wav()
                files = {'file': ('test.wav', wav_bytes, 'audio/wav')}
                data = {'model': model}
                resp = requests.post(endpoint, headers=headers, files=files, data=data, timeout=20)
                if resp.status_code == 200:
                    return {"status": "ok", "message": "Ready - API tested"}
                return {"status": "error", "message": f"Error {resp.status_code}"}

            else:
                return {"status": "error", "message": "Error: tipe model tidak dikenal"}

        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Error timeout"}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Error connection failed"}
        except Exception as e:
            return {"status": "error", "message": f"Error {str(e)[:60]}"}

    def _generate_silent_wav(self, duration_sec=0.5, sample_rate=16000):
        """Bikin file WAV silent kecil di memory, dipakai buat test endpoint STT/transcription."""
        import io
        import wave
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b'\x00\x00' * int(sample_rate * duration_sec))
        buf.seek(0)
        return buf.read()

    def save_ai_settings(self, settings):
        try:
            if not isinstance(settings, dict):
                return {"status": "error"}
            cfg_mgr = self._get_cfg_manager()
            cfg_mgr.config["ai_providers"] = settings
            provider_type = settings.get("_provider_type")
            if provider_type:
                cfg_mgr.config["provider_type"] = provider_type
            highlight_finder = settings.get("highlight_finder", {})
            cfg_mgr.config["api_key"] = highlight_finder.get("api_key", "")
            cfg_mgr.config["base_url"] = highlight_finder.get("base_url", "https://api.openai.com/v1")
            cfg_mgr.config["model"] = highlight_finder.get("model", "gpt-4.1")
            
            repliz_settings = settings.get("repliz")
            if repliz_settings:
                cfg_mgr.config["repliz"] = repliz_settings
            
            cfg_mgr.save()
            return {"status": "saved"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


    def _run(self, url, num_clips, add_captions, add_hook, subtitle_lang, portrait, highlight_finder, yt_title_maker, campaign_id=None, subtitle_style="v2", max_highlights=30, fixed_count=None, min_score=None):
        active_job_id = (getattr(self, "_active_job", None) or {}).get("id")
        def log_cb(msg):
            self.status = str(msg)
            if self.current_job:
                self.current_job["step"] = str(msg)
            if active_job_id:
                self._record_job_event(active_job_id, message=str(msg))

        def progress_cb(p, step=None):
            try:
                self.progress = max(0.0, min(1.0, float(p)))
                if self.current_job:
                    self.current_job["progress"] = int(self.progress * 100)
            except:
                self.progress = 0.0
            if active_job_id:
                fields = {"progress": self.progress}
                if step is not None:
                    fields["step"] = str(step)
                self._record_job_event(active_job_id, **fields)

        cfg = self._get_cfg()
        system_prompt = cfg.get("system_prompt", None)
        temperature = cfg.get("temperature", 1.0)
        tts_model = cfg.get("tts_model", "tts-1")
        watermark_settings = cfg.get("watermark", {"enabled": False})
        credit_watermark_settings = cfg.get("credit_watermark", {"enabled": False})
        hook_style_settings = cfg.get("hook_style", {})
        face_tracking_mode = cfg.get("face_tracking_mode", "opencv")
        mediapipe_settings = cfg.get("mediapipe_settings", {
            "lip_activity_threshold": 0.15,
            "switch_threshold": 0.3,
            "min_shot_duration": 90,
            "center_weight": 0.3
        })
        output_dir = cfg.get("output_dir", str(get_app_dir() / "output"))
        model = cfg.get("model", "gpt-4.1")
        ai_providers = cfg.get("ai_providers", {})
        
        whisper_model_name = ai_providers.get("whisper_model", "api")
        local_whisper_settings = {
            "enabled": whisper_model_name != "api",
            # NOTE: key must be "model_size" — AutoClipperCore._load_local_whisper()
            # reads settings.get("model_size", ...). It used to be "model" here,
            # which meant the user's chosen local Whisper model (e.g. "medium")
            # was silently ignored and always fell back to "large-v3-turbo".
            "model_size": whisper_model_name if whisper_model_name != "api" else "large-v3-turbo"
        }

        try:
            core = AutoClipperCore(
                client=None,
                ffmpeg_path=get_ffmpeg_path(),
                ytdlp_path=get_ytdlp_path(),
                output_dir=output_dir,
                model=model,
                tts_model=tts_model,
                temperature=temperature,
                system_prompt=system_prompt,
                watermark_settings=watermark_settings,
                credit_watermark_settings=credit_watermark_settings,
                hook_style_settings=hook_style_settings,
                face_tracking_mode=face_tracking_mode,
                mediapipe_settings=mediapipe_settings,
                ai_providers=ai_providers,
                subtitle_language=subtitle_lang,
                local_whisper_settings=local_whisper_settings,
                subtitle_style=subtitle_style,
                log_callback=log_cb,
                progress_callback=lambda s, p=None: progress_cb(p if p is not None else 0.0, s),
            )

            # NOTE: this was previously never called anywhere, so the "GPU
            # Acceleration" toggle in Settings had zero effect on processing -
            # every clip was always encoded on CPU (libx264) regardless of what
            # the user selected. Every FFmpeg encode step in the pipeline
            # (cut, portrait merge, hook, captions, watermark...) goes through
            # get_video_encoder_args(), which only returns GPU args if this is
            # called with enabled=True. GPUDetector's encoder settings target
            # equivalent visual quality to the CPU CRF 18 default (cq 19 /
            # global_quality 19 / qp 18-19, tuned per vendor), and any runtime
            # GPU encoder failure already falls back to CPU automatically
            # (see _run_ffmpeg_subprocess), so enabling it by default is safe.
            gpu_cfg = cfg.get("gpu_acceleration", {})
            core.enable_gpu_acceleration(bool(gpu_cfg.get("enabled", True)))
            self._configure_workflow_core(core)
            self.core = core

            dur_min = 58
            dur_max = 120
            if campaign_id:
                campaign_options = [self._active_job["campaign"]] if getattr(self, "_active_job", None) else cfg.get("campaigns", [])
                for c in campaign_options:
                    if c.get("id") == campaign_id:
                        brief = c.get("brief", {})
                        c_min = brief.get("durasi_min")
                        c_max = brief.get("durasi_max")
                        if c_min is not None: dur_min = float(c_min)
                        if c_max is not None: dur_max = float(c_max)
                        break

            self.status = "running"
            self.progress = 0.0
            core.process(url, num_clips=num_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait, highlight_finder=highlight_finder, yt_title_maker=yt_title_maker, campaign_id=campaign_id, max_highlights=max_highlights, fixed_count=fixed_count, min_score=min_score, dur_min=dur_min, dur_max=dur_max, subtitle_style=subtitle_style)
            self.status = "complete"
            self.progress = 1.0
            if self.current_job:
                self.current_job["status"] = "Complete"
                self.current_job["progress"] = 100
                self.job_history.append(self.current_job)
                self.current_job = None
        except Exception as e:
            self.status = f"error: {e}"
            if self.current_job:
                self.current_job["status"] = f"Failed: {e}"
                self.job_history.append(self.current_job)
                self.current_job = None
        # WorkflowMixin retains the worker until job finalization has completed.

    # --- NEW ENDPOINTS FOR WEB UI ---

    def reload_whisper_model(self):
        """Reloads the local whisper model."""
        try:
            import faster_whisper  # noqa
            return {"status": "success", "message": "Library whisper terdeteksi. Model akan dipakai ulang di run berikutnya."}
        except ImportError:
            return {"status": "error", "message": "Library whisper belum terinstall. Klik 'Install All' dulu."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def test_repliz_connection(self, access_key, secret_key):
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            url = "https://api.repliz.com/public/account"
            params = {"page": 1, "limit": 1}
            response = requests.get(
                url, 
                params=params,
                auth=HTTPBasicAuth(access_key, secret_key),
                timeout=10
            )
            if response.status_code == 200:
                return {"status": "success", "message": "Connection successful"}
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_msg = response.json().get("message", error_msg)
                except:
                    if response.status_code == 401:
                        error_msg = "Invalid authorization header"
                return {"status": "error", "message": error_msg}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_repliz_dashboard_url(self):
        """Returns the URL for Repliz Dashboard."""
        return "https://repliz.com/user/dashboard"

    def get_account_stats(self):
        """Returns statistics of connected social accounts, broken down by platform."""
        try:
            cfg = self._get_cfg()
            repliz_cfg = cfg.get("repliz", {})
            access_key = repliz_cfg.get("access_key")
            secret_key = repliz_cfg.get("secret_key")

            if not access_key or not secret_key:
                return {"error": True, "message": "Keys not configured"}

            import requests
            from requests.auth import HTTPBasicAuth
            url = "https://api.repliz.com/public/account"
            params = {"page": 1, "limit": 50}

            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(access_key, secret_key),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                docs = data.get("docs", [])
                total = data.get("totalDocs", len(docs))
                tiktok_count = sum(1 for a in docs if a.get("type") == "tiktok")
                youtube_count = sum(1 for a in docs if a.get("type") == "youtube")
                instagram_count = sum(1 for a in docs if a.get("type") == "instagram")
                return {
                    "campaigns": total,
                    "tiktok_count": tiktok_count,
                    "youtube_count": youtube_count,
                    "instagram_count": instagram_count,
                    "error": False
                }
            else:
                return {"error": True, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def get_repliz_accounts(self):
        """Read every account page before assigning campaign work."""
        from services.publishing import ReplizClient
        try:
            cfg = self._get_cfg().get("repliz", {})
            client = ReplizClient(cfg.get("access_key"), cfg.get("secret_key"))
            accounts = []
            for page in range(1, 101):
                result = client.get("account", {"page": page, "limit": 100})
                result = result.get("data", result)
                accounts.extend({"_id": a.get("_id", a.get("id")), "name": a.get("name"), "type": a.get("type"),
                                 "isConnected": a.get("isConnected", True)} for a in result.get("docs", []))
                if not result.get("hasNextPage"):
                    return {"status": "ok", "accounts": accounts}
            raise ValueError("Daftar akun melebihi batas pagination yang didukung.")
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_repliz_tiktok_music(self, genre="ALL", country_code="ID", date_range="7DAY"):
        """Fetch daftar musik trending TikTok dari Repliz.

        Args:
            genre: kategori genre musik, default "ALL" (lihat dokumentasi Repliz untuk daftar genre valid)
            country_code: ISO country code, default "ID"
            date_range: salah satu dari "1DAY", "7DAY", "30DAY", "90DAY", default "7DAY"

        Returns:
            {"status": "ok", "tracks": [ {id, artist, name, thumbnail, duration, url}, ... ]}
            atau
            {"status": "error", "message": "..."}
        """
        try:
            cfg = self._get_cfg()
            repliz_cfg = cfg.get("repliz", {})
            access_key = repliz_cfg.get("access_key")
            secret_key = repliz_cfg.get("secret_key")

            if not access_key or not secret_key:
                return {"status": "error", "message": "Repliz keys not configured"}

            import requests
            from requests.auth import HTTPBasicAuth
            url = "https://api.repliz.com/public/addon/tiktok/music"
            params = {
                "genre": genre,
                "countryCode": country_code,
                "dateRange": date_range
            }

            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(access_key, secret_key),
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                docs = data.get("docs", [])
                tracks = [
                    {
                        "id": d.get("id"),
                        "artist": d.get("artist"),
                        "name": d.get("name"),
                        "thumbnail": d.get("thumbnail"),
                        "duration": d.get("duration"),
                        "url": d.get("url")
                    }
                    for d in docs
                ]
                return {"status": "ok", "tracks": tracks}
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_msg = response.json().get("message", error_msg)
                except Exception:
                    pass
                return {"status": "error", "message": error_msg}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_jamendo_tracks(self, tags="", speed="", target_duration=30):
        """Cari track musik Jamendo, termasuk vokal, untuk pemilihan per clip:
        lisensi bukan Non-Commercial, dan boleh
        di-download. Filter durasi dilakukan di sisi kita sendiri (bukan parameter
        API) biar dijamin benar, lalu diurutkan dari yang durasinya paling deket ke
        target_duration.

        Args:
            tags: string tag mood/genre bahasa Inggris, dipisah spasi, contoh
                "happy upbeat" (dikirim sebagai parameter fuzzytags ke Jamendo)
            speed: salah satu dari "verylow","low","medium","high","veryhigh", atau
                "" buat skip filter tempo
            target_duration: perkiraan durasi clip (detik) — track yang lebih
                PENDEK dari ini otomatis dibuang (gak cukup buat di-trim jadi window
                sepanjang durasi clip)

        Returns:
            {"status": "ok", "tracks": [ {id, name, artist, duration, license_ccurl,
                audiodownload, waveform}, ... ]} — sudah terurut, kandidat terbaik di depan
            atau
            {"status": "error", "message": "..."}
        """
        try:
            cfg = self._get_cfg()
            jamendo_cfg = cfg.get("jamendo", {})
            client_id = jamendo_cfg.get("client_id")

            if not client_id:
                return {"status": "error", "message": "Jamendo client_id belum diisi di Settings"}

            import requests
            url = "https://api.jamendo.com/v3.0/tracks/"
            target_duration = int(target_duration) if target_duration else 30
            params = {
                "client_id": client_id,
                "format": "json",
                "limit": 30,
                "include": "musicinfo",
                "audioformat": "mp32",
                "audiodlformat": "mp32"
            }
            if tags:
                params["fuzzytags"] = tags
            if speed:
                params["speed"] = speed

            response = requests.get(url, params=params, timeout=15)

            if response.status_code != 200:
                return {"status": "error", "message": f"HTTP {response.status_code}"}

            data = response.json()
            results = data.get("results", [])

            tracks = []
            for t in results:
                if not t.get("audiodownload_allowed"):
                    continue
                license_url = t.get("license_ccurl") or ""
                license_segments = license_url.rstrip("/").split("/")
                license_code = license_segments[-2].lower() if len(license_segments) >= 2 else ""
                if "nc" in license_code.split("-"):
                    continue
                duration = t.get("duration") or 0
                if duration and duration < target_duration:
                    continue
                tracks.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "artist": t.get("artist_name"),
                    "duration": duration,
                    "license_ccurl": t.get("license_ccurl"),
                    "audiodownload": t.get("audiodownload"),
                    "waveform": t.get("waveform")
                })

            tracks.sort(key=lambda x: (x["duration"] or 0) - target_duration)

            return {"status": "ok", "tracks": tracks}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_campaigns(self):
        cfg = self._get_cfg()
        campaigns = cfg.get("campaigns", [])
        try:
            accounts_res = self.get_repliz_accounts()
            accounts_by_id = {a["_id"]: a for a in accounts_res.get("accounts", [])} if accounts_res.get("status") == "ok" else {}
        except Exception:
            accounts_by_id = {}
        result = []
        for camp in campaigns:
            acc_ids = camp.get("account_ids", [])
            camp_out = dict(camp)
            camp_out["account_names"] = [accounts_by_id[a]["name"] for a in acc_ids if a in accounts_by_id]
            stats = self.get_campaign_stats(camp.get("id"))
            camp_out["stats"] = stats
            result.append(camp_out)
        return result

    def create_campaign(self, payload):
        return self.save_campaign_workspace(None, payload)

    def update_campaign(self, campaign_id, payload):
        return self.save_campaign_workspace(campaign_id, payload)

    def delete_campaign(self, campaign_id):
        cfg = self._get_cfg()
        campaigns = cfg.get("campaigns", [])
        cfg["campaigns"] = [c for c in campaigns if c.get("id") != campaign_id]
        self._get_cfg_manager().save_config(cfg)
        return {"status": "ok"}

    def upload_campaign_banner(self, campaign_id, file_path):
        import shutil
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            return {"status": "error", "message": "Invalid extension"}
        
        assets_dir = get_app_dir() / "campaign_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        dest_path = assets_dir / f"{campaign_id}{ext}"
        
        try:
            shutil.copy2(file_path, dest_path)
            # Make relative to app dir
            rel_path = str(dest_path)
            
            # Update campaign
            cfg = self._get_cfg()
            campaigns = cfg.get("campaigns", [])
            for c in campaigns:
                if c.get("id") == campaign_id:
                    c["banner_path"] = rel_path
                    self._get_cfg_manager().save_config(cfg)
                    break
            return {"status": "ok", "banner_path": rel_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def read_file_as_base64(self, path):
        import base64
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def extract_campaign_brief(self, content_type, content):
        cfg = self._get_cfg()
        provider = cfg.get("ai_providers", {}).get("brief_extractor", {})
        api_key = provider.get("api_key")
        base_url = provider.get("base_url")
        model = provider.get("model")
        
        if not api_key:
            return {"status": "error", "message": "API Key Brief Extractor belum diset"}
        
        text_content = ""
        
        if content_type == "doc":
            try:
                ext = os.path.splitext(content)[1].lower()
                if ext in [".docx", ".doc"]:
                    import docx
                    doc = docx.Document(content)
                    text_content = "\n".join([p.text for p in doc.paragraphs])
                elif ext == ".pdf":
                    import pypdf
                    with open(content, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        text_content = "\n".join([page.extract_text() for page in reader.pages])
                else:
                    return {"status": "error", "message": "Format dokumen tidak didukung"}
            except Exception as e:
                return {"status": "error", "message": f"Gagal membaca dokumen, coba tempel teks manual. Error: {e}"}
        
        from openai import OpenAI
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            messages = [
                {"role": "system", "content": 'Kamu membaca brief campaign dari brand. Ekstrak informasinya ke JSON dengan schema berikut, HANYA output JSON, tanpa teks lain:\n{"name": "...", "brief": {"durasi_min": 0, "durasi_max": 0, "hashtags": [], "tagged_accounts": [], "hooks": [], "catatan": "...", "angles": [], "persona": "...", "tujuan": "...", "cta": "..."}, "do_rules": [], "dont_rules": [], "aturan_umum": [{"title":"...","description":"..."}]}\nKalau suatu field tidak ditemukan di brief, isi string kosong "" atau array kosong [], JANGAN mengarang.'}
            ]
            
            if content_type == "image":
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Ekstrak informasi dari gambar brief ini."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{content}"}}
                    ]
                })
            else:
                if content_type == "text":
                    text_content = content
                messages.append({"role": "user", "content": text_content})
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            return {"status": "ok", "extracted": json.loads(raw)}
        except Exception as e:
            return {"status": "error", "message": f"AI gagal memproses, coba lagi atau isi manual. Error: {str(e)[:100]}"}

    def get_campaign_stats(self, campaign_id):
        campaign = next((c for c in self._get_cfg().get("campaigns", []) if c.get("id") == campaign_id), {})
        clips = [c for c in self.get_stock_clips() if c.get("campaign_id") == campaign_id]
        publications = [p for p in self._get_store().publications() if p.get("campaign_id") == campaign_id]
        return {"account_count": len(campaign.get("account_ids", [])), "clip_in_stock": len(clips),
                "clip_uploaded": len({p["clip_id"] for p in publications if p["status"] == "published"}),
                "publication_count": len(publications), "scheduled": sum(p["status"] == "scheduled" for p in publications)}

    def get_app_config(self):
        """Returns safe global config properties for UI"""
        cfg = self._get_cfg()
        return {
            "owner_name": cfg.get("owner_name", "Local User")
        }

    def get_watermark_settings(self):
        """Returns watermark settings"""
        cfg = self._get_cfg()
        return cfg.get("watermark", {
            "enabled": False,
            "image_path": "",
            "position_x": 0.85,
            "position_y": 0.05,
            "opacity": 0.8,
            "scale": 0.15
        })

    def save_watermark_settings(self, settings):
        """Saves watermark settings"""
        try:
            cfg = self._get_cfg()
            cfg["watermark"] = {
                "enabled": bool(settings.get("enabled", False)),
                "image_path": str(settings.get("image_path", "")),
                "position_x": float(settings.get("position_x", 0.85)),
                "position_y": float(settings.get("position_y", 0.05)),
                "opacity": float(settings.get("opacity", 0.8)),
                "scale": float(settings.get("scale", 0.15))
            }
            self._get_cfg_manager().save_config(cfg)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_credit_watermark_settings(self):
        """Returns credit watermark settings"""
        cfg = self._get_cfg()
        return cfg.get("credit_watermark", {
            "enabled": False,
            "position_x": 0.5,
            "position_y": 0.95,
            "size": 0.03,
            "opacity": 0.7
        })

    def save_credit_watermark_settings(self, settings):
        """Saves credit watermark settings"""
        try:
            cfg = self._get_cfg()
            cfg["credit_watermark"] = {
                "enabled": bool(settings.get("enabled", False)),
                "position_x": float(settings.get("position_x", 0.5)),
                "position_y": float(settings.get("position_y", 0.95)),
                "size": float(settings.get("size", 0.03)),
                "opacity": float(settings.get("opacity", 0.7))
            }
            self._get_cfg_manager().save_config(cfg)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_system_fonts(self):
        """Returns list of system fonts"""
        try:
            from utils.font_scanner import get_font_names
            names = get_font_names()
            return {"status": "ok", "fonts": names if names else ["Arial"]}
        except Exception as e:
            return {"status": "error", "message": str(e), "fonts": ["Arial"]}

    def get_hook_style_settings(self):
        """Returns hook style settings"""
        cfg = self._get_cfg()
        return cfg.get("hook_style", {
            "font_name": "Arial",
            "font_size": 0.054,
            "font_color": "#FFD700",
            "bg_color": "#FFFFFF",
            "corner_radius": 0,
            "position_x": 0.5,
            "position_y": 0.333
        })

    def save_hook_style_settings(self, settings):
        """Saves hook style settings"""
        try:
            from utils.font_scanner import get_path_for_name
            font_name = str(settings.get("font_name", "Arial"))
            font_path = get_path_for_name(font_name) or ""
            cfg = self._get_cfg()
            cfg["hook_style"] = {
                "font_name": font_name,
                "font_path": font_path,
                "font_size": float(settings.get("font_size", 0.054)),
                "font_color": str(settings.get("font_color", "#FFD700")),
                "bg_color": str(settings.get("bg_color", "#FFFFFF")),
                "corner_radius": int(settings.get("corner_radius", 0)),
                "position_x": float(settings.get("position_x", 0.5)),
                "position_y": float(settings.get("position_y", 0.333))
            }
            self._get_cfg_manager().save_config(cfg)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_face_tracking_settings(self):
        """Returns face tracking mode and GPU acceleration settings"""
        cfg = self._get_cfg()
        gpu_cfg = cfg.get("gpu_acceleration", {})
        return {
            "face_tracking_mode": cfg.get("face_tracking_mode", "opencv"),
            "gpu_enabled": gpu_cfg.get("enabled", True)
        }

    def save_face_tracking_settings(self, settings):
        """Saves face tracking mode and GPU acceleration settings"""
        try:
            cfg = self._get_cfg()
            mode = str(settings.get("face_tracking_mode", "opencv"))
            if mode not in ("opencv", "mediapipe"):
                mode = "opencv"
            cfg["face_tracking_mode"] = mode
            cfg["gpu_acceleration"] = {
                "enabled": bool(settings.get("gpu_enabled", False))
            }
            self._get_cfg_manager().save_config(cfg)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def detect_gpu(self):
        """Detect GPU hardware and recommend encoder. Called from UI button."""
        try:
            from utils.gpu_detector import GPUDetector
            detector = GPUDetector()
            gpu_info = detector.detect_gpu()
            recommendation = detector.get_recommended_encoder()
            return {
                "status": "ok",
                "gpu": gpu_info,
                "recommendation": recommendation
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "gpu": {"type": None, "name": "Detection failed", "available": False},
                "recommendation": {"encoder": None, "preset": None, "available": False, "reason": str(e)}
            }

    def get_output_dir_settings(self):
        """Returns the output directory path"""
        cfg = self._get_cfg()
        return {
            "output_dir": cfg.get("output_dir", str(self.output_dir))
        }

    def save_output_dir_settings(self, settings):
        """Saves the output directory path. Creates dir if it doesn't exist."""
        try:
            from pathlib import Path
            output_dir = str(settings.get("output_dir", "")).strip()
            if not output_dir:
                return {"status": "error", "message": "Output directory is required"}
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            cfg = self._get_cfg()
            cfg["output_dir"] = output_dir
            self._get_cfg_manager().save_config(cfg)
            self.output_dir = output_dir
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def browse_output_dir(self):
        """Opens native folder dialog to pick output directory"""
        import webview
        try:
            if not webview.windows:
                return None
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG
            )
            if result and len(result) > 0:
                return {"status": "ok", "path": result[0]}
            return {"status": "cancelled"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def open_output_dir(self):
        """Opens the output folder in the system file explorer"""
        import subprocess
        import sys
        from pathlib import Path
        try:
            cfg = self._get_cfg()
            folder = cfg.get("output_dir", str(self.output_dir))
            if not folder or not Path(folder).exists():
                return {"status": "error", "message": "Output folder does not exist"}
            if sys.platform == "win32":
                subprocess.run(["explorer", folder])
            elif sys.platform == "darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_youtube_status(self):
        """Check YouTube connection status.
        Returns status string + channel info if connected.
        Reuses youtube_uploader.py exactly as the legacy youtube_api_settings.py did.
        """
        try:
            from youtube_uploader import YouTubeUploader
            uploader = YouTubeUploader()

            if not uploader.is_configured():
                return {
                    "status": "not_configured",
                    "message": "client_secret.json not found in app folder"
                }

            if uploader.is_authenticated():
                channel = uploader.get_channel_info()
                if channel:
                    return {
                        "status": "connected",
                        "channel": channel
                    }
                else:
                    return {
                        "status": "auth_error",
                        "message": "Authenticated but could not fetch channel info. Try reconnecting."
                    }
            else:
                return {
                    "status": "not_connected",
                    "message": "Click Connect to authorize"
                }
        except ImportError:
            return {
                "status": "module_error",
                "message": "YouTube module not available. Check dependencies."
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def connect_youtube(self):
        """Start YouTube OAuth flow. Opens browser for user login.
        This is a blocking call — pywebview runs it on a background thread.
        """
        try:
            from youtube_uploader import YouTubeUploader
            uploader = YouTubeUploader()

            if not uploader.is_configured():
                return {"status": "error", "message": "client_secret.json not found. Set up YouTube API credentials first."}

            uploader.authenticate()  # Opens browser, blocks until user completes OAuth
            channel = uploader.get_channel_info()
            if channel:
                return {"status": "connected", "channel": channel}
            return {"status": "connected", "channel": {"title": "Unknown"}}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def disconnect_youtube(self):
        """Remove YouTube credentials and disconnect."""
        import os
        try:
            from youtube_uploader import YouTubeUploader
            uploader = YouTubeUploader()
            uploader.disconnect()

            # Also remove credentials file directly (belt-and-suspenders)
            creds_file = "youtube_credentials.json"
            if os.path.exists(creds_file):
                os.remove(creds_file)

            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def browse_brief_file(self):
        """File dialog khusus brief campaign — terima gambar & dokumen, tanpa copy ke watermarks."""
        import webview
        try:
            if not webview.windows:
                return None
            result = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=('Brief Files (*.png;*.jpg;*.jpeg;*.webp;*.pdf;*.docx)',)
            )
            if result and len(result) > 0:
                return {"status": "ok", "path": result[0]}
            return {"status": "cancelled"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def browse_watermark_image(self):
        """Opens file dialog to pick an image and copies it to assets/watermarks"""
        import webview
        import shutil
        from pathlib import Path
        try:
            if not webview.windows:
                return None
            result = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=('Image Files (*.png;*.jpg;*.jpeg)',)
            )
            if result and len(result) > 0:
                file_path = result[0]
                watermarks_dir = Path("assets/watermarks")
                watermarks_dir.mkdir(parents=True, exist_ok=True)
                original_name = Path(file_path).stem
                extension = Path(file_path).suffix
                dest_filename = f"watermark_{original_name}{extension}"
                dest_path = watermarks_dir / dest_filename
                counter = 1
                while dest_path.exists():
                    dest_filename = f"watermark_{original_name}_{counter}{extension}"
                    dest_path = watermarks_dir / dest_filename
                    counter += 1
                shutil.copy2(file_path, dest_path)
                return {"status": "ok", "path": str(dest_path)}
            return {"status": "cancelled"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_dashboard_stats(self):
        """Returns statistics for the Dashboard."""
        out_dir = Path(self.output_dir)
        total_clips = len(self.get_stock_clips())
        storage_bytes = 0
        
        if out_dir.exists():
            for f in out_dir.rglob("*.mp4"):
                try:
                    storage_bytes += f.stat().st_size
                except:
                    pass
                    
        storage_gb = storage_bytes / (1024 * 1024 * 1024)
        
        # Format active job if any
        active_jobs = [self.current_job] if self.current_job else []
        
        return {
            "totalVideosClipped": total_clips,
            "totalModels": 4, # Just a static number matching UI design
            "storageUsed": f"{storage_gb:.1f} GB",
            "activeJobs": active_jobs,
            "recentJobs": self.job_history[-5:] # Last 5 jobs
        }
        
    def upload_cookies(self):
        """Opens a file dialog to select cookies.txt and saves it."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=('Text Files (*.txt)',)
            )
            if result and len(result) > 0:
                source_path = result[0]
                target_path = get_app_dir() / "cookies.txt"
                import shutil
                shutil.copy2(source_path, target_path)
                return {"status": "ok", "path": str(target_path)}
            return {"status": "cancelled"}
        except Exception as e:
            print(f"Error uploading cookies: {e}")
            return {"status": "error", "message": str(e)}

    def save_default_config(self, settings):
        """Saves default configuration from the Create Clip form."""
        if not isinstance(settings, dict):
            return {"status": "error"}
        cfg_mgr = self._get_cfg_manager()
        # You could store these under a specific key like 'default_clip_settings'
        cfg_mgr.config["default_clip_settings"] = settings
        cfg_mgr.save()
        return {"status": "saved"}

    def get_default_config(self):
        """Returns default configuration from the Create Clip form."""
        cfg_mgr = self._get_cfg_manager()
        cfg = cfg_mgr.get_all() if hasattr(cfg_mgr, "get_all") else cfg_mgr.config
        return cfg.get("default_clip_settings", {})

    def get_video_folders(self):
        """Returns list of video folders (jobs) for the Jobs panel.
        A 'video folder' = direct child of output_dir that has its own data.json
        containing a 'url' key (this is the marker that separates the new
        video-level data.json from the old per-clip data.json format)."""
        folders = []
        out_dir = Path(self.output_dir)

        if out_dir.exists():
            for child in out_dir.iterdir():
                if not child.is_dir():
                    continue
                meta_file = child / "data.json"
                if not meta_file.exists():
                    continue
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue
                if "url" not in data:
                    # Bukan folder video baru (kemungkinan folder clip lama/legacy), skip
                    continue
                clip_count = len(list(child.glob("*/*.mp4")))
                folders.append({
                    "id": child.name,
                    "title": data.get("title", child.name),
                    "clip_count": clip_count,
                    "date": data.get("created_at", ""),
                    "path": str(child),
                    "campaign_id": data.get("campaign_id")
                })

        folders.sort(key=lambda f: f.get("date", ""), reverse=True)
        return folders

    def _legacy_get_stock_clips(self, folder_id=None):
        """Returns a list of clips. If folder_id is given, only returns clips
        inside that video folder. Otherwise returns clips from ALL video folders."""
        clips = []
        out_dir = Path(self.output_dir)

        if not out_dir.exists():
            return clips

        if folder_id:
            target_folders = [out_dir / folder_id]
        else:
            target_folders = [c for c in out_dir.iterdir() if c.is_dir()]

        for video_folder in target_folders:
            if not video_folder.exists() or not video_folder.is_dir():
                continue

            video_meta_file = video_folder / "data.json"
            video_title = video_folder.name
            is_new_format = False

            if video_meta_file.exists():
                try:
                    with open(video_meta_file, 'r', encoding='utf-8') as f:
                        vdata = json.load(f)
                    if "url" in vdata:
                        video_title = vdata.get("title", video_title)
                        is_new_format = True
                except Exception as e:
                    print(f"Error parsing {video_meta_file}: {e}")

            if is_new_format:
                # Struktur baru: tiap clip ada di subfolder video_folder/<timestamp>/
                for clip_json in video_folder.glob("*/data.json"):
                    try:
                        with open(clip_json, 'r', encoding='utf-8') as f:
                            cdata = json.load(f)
                        mp4s = list(clip_json.parent.glob("*.mp4"))
                        if not mp4s:
                            continue
                        mp4_path = mp4s[0]
                        stat = mp4_path.stat()
                        duration_sec = int(cdata.get("duration_seconds", 0))
                        clips.append({
                            "id": clip_json.parent.name,
                            "title": cdata.get("hook_text", cdata.get("title", video_title)),
                            "video_title": video_title,
                            "date": stat.st_mtime * 1000,
                            "duration": f"{duration_sec // 60:02d}:{duration_sec % 60:02d}",
                            "path": str(mp4_path),
                            "upload_status": cdata.get("upload_status", "belum_diupload"),
                            "conflict_group_id": cdata.get("conflict_group_id"),
                            "campaign_id": cdata.get("campaign_id")
                        })
                    except Exception as e:
                        print(f"Error parsing {clip_json}: {e}")
            else:
                # Struktur lama (legacy): folder ini SENDIRI adalah 1 clip
                try:
                    if video_meta_file.exists():
                        with open(video_meta_file, 'r', encoding='utf-8') as f:
                            cdata = json.load(f)
                        mp4s = list(video_folder.glob("*.mp4"))
                        if mp4s:
                            mp4_path = mp4s[0]
                            stat = mp4_path.stat()
                            clips.append({
                                "id": video_folder.name,
                                "title": cdata.get("title", "Unknown Clip"),
                                "video_title": cdata.get("title", "Unknown Clip"),
                                "date": stat.st_mtime * 1000,
                                "duration": "00:00",
                                "path": str(mp4_path),
                                "upload_status": cdata.get("upload_status", "belum_diupload"),
                                "conflict_group_id": cdata.get("conflict_group_id"),
                                "campaign_id": cdata.get("campaign_id")
                            })
                except Exception as e:
                    print(f"Error parsing legacy {video_meta_file}: {e}")

        clips.sort(key=lambda x: x.get("date", 0), reverse=True)
        return clips
        
    def open_output_folder(self):
        """Opens the output directory in the native file explorer."""
        out_dir = str(Path(self.output_dir).absolute())
        try:
            if sys.platform == "win32":
                os.startfile(out_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out_dir])
            else:
                subprocess.Popen(["xdg-open", out_dir])
            return True
        except Exception as e:
            print(f"Error opening folder: {e}")
            return False




    def delete_clip(self, clip_path):
        """Delete a specific clip file and its parent folder if empty."""
        try:
            p = Path(clip_path)
            if p.exists() and p.is_file():
                parent = p.parent
                p.unlink()
                # Also remove the data.json if only that remains
                remaining = list(parent.iterdir())
                if not remaining or all(f.name == "data.json" for f in remaining):
                    import shutil
                    shutil.rmtree(str(parent), ignore_errors=True)
                return {"status": "ok"}
            return {"status": "not_found"}
        except Exception as e:
            print(f"Error deleting clip: {e}")
            return {"status": "error", "message": str(e)}


    def _build_caption(self, campaign_id):
        """Compose caption string from campaign brief (CTA + tagged accounts + hashtags)."""
        if not campaign_id or campaign_id == "default":
            return ""
        cfg = self._get_cfg()
        camp = next((c for c in cfg.get("campaigns", []) if c.get("id") == campaign_id), None)
        if not camp:
            return ""
        brief = camp.get("brief", {})
        parts = []
        if brief.get("cta"):
            parts.append(brief["cta"].strip())
        if brief.get("tagged_accounts"):
            parts.append(" ".join(brief["tagged_accounts"]))
        if brief.get("hashtags"):
            parts.append(" ".join(brief["hashtags"]))
        return "\n\n".join(p for p in parts if p)


    def update_clip_title(self, clip_path, new_title):
        """Legacy dashboard edits use the same review/revision store."""
        target = str(Path(clip_path).resolve())
        clip = next((c for c in self.get_stock_clips() if str(Path(c["path"]).resolve()) == target), None)
        if not clip:
            return {"status": "error", "message": "Clip tidak ditemukan."}
        return self.review_clip(clip["id"], {"title": new_title, "action": "save"})

    def delete_video_folder(self, folder_id):
        """Delete an entire video folder (and every clip inside it)."""
        try:
            target = Path(self.output_dir) / folder_id
            if target.exists() and target.is_dir():
                import shutil
                shutil.rmtree(str(target), ignore_errors=True)
                return {"status": "ok"}
            return {"status": "not_found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def upload_clip(self, clip_path, platform, options=None):
        """Compatibility entry point: final review owns all publication actions."""
        return {"status": "review_required", "message": "Gunakan Review & Upload untuk menyetujui video dan akun tujuan."}

    def play_clip(self, clip_path):
        """Open a clip file in the system default video player."""
        try:
            p = str(Path(clip_path).absolute())
            if sys.platform == "win32":
                os.startfile(p)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", p])
            else:
                subprocess.Popen(["xdg-open", p])
            return {"status": "ok"}
        except Exception as e:
            print(f"Error playing clip: {e}")
            return {"status": "error", "message": str(e)}



    def _select_background_sound(self, transcript, title, hook_text, clip_duration, campaign=None):
        """Compare real candidates per clip, with editorial context and audio evidence."""
        if not clip_duration or clip_duration <= 0:
            return None
        cfg = self._get_cfg()
        if not cfg.get("ai_providers", {}).get("highlight_finder", {}).get("api_key"):
            return None
        from services.music_selection import MusicSelector
        cache = Path(cfg.get("output_dir") or self.output_dir) / "_cache" / "music-selection"
        return MusicSelector(self, cfg, cache).select({"transcript": transcript, "title": title,
            "hook_text": hook_text, "duration_seconds": clip_duration}, campaign)

    def _find_best_music_window(self, waveform_raw, target_duration, track_duration):
        """Cari window sepanjang target_duration detik dengan energi tertinggi dari
        data waveform Jamendo (field 'peaks'), buat jadi titik potong (start,end) musik
        yang paling 'nendang' dipakai sebagai backsound — tanpa perlu download & analisis
        audio manual, karena Jamendo udah kasih peaks-nya langsung di response API.

        Args:
            waveform_raw: isi field "waveform" dari Jamendo (JSON string berisi
                {"peaks":[...]})
            target_duration: durasi clip (detik)
            track_duration: durasi total track musik (detik)

        Returns:
            (start_seconds, end_seconds) — float, sudah clamp ke batas durasi track.
            Fallback (0.0, target_duration) kalau data waveform gak ada / gagal diparse.
        """
        try:
            target_duration = max(1.0, float(target_duration))
            track_duration = max(target_duration, float(track_duration or target_duration))
            if target_duration >= track_duration:
                return 0.0, track_duration

            waveform = json.loads(waveform_raw) if isinstance(waveform_raw, str) else (waveform_raw or {})
            peaks = waveform.get("peaks", [])
            if not peaks:
                return 0.0, target_duration

            sec_per_peak = track_duration / len(peaks)
            window_size = max(1, int(target_duration / sec_per_peak))
            if window_size >= len(peaks):
                return 0.0, track_duration

            window_sum = sum(peaks[:window_size])
            best_sum = window_sum
            best_start_idx = 0
            for i in range(1, len(peaks) - window_size + 1):
                window_sum += peaks[i + window_size - 1] - peaks[i - 1]
                if window_sum > best_sum:
                    best_sum = window_sum
                    best_start_idx = i

            start = round(best_start_idx * sec_per_peak, 2)
            end = round(start + target_duration, 2)
            if end > track_duration:
                end = track_duration
                start = max(0.0, end - target_duration)
            return start, end
        except Exception:
            return 0.0, min(target_duration, track_duration)

    def _mix_music_into_video(self, video_path, music_info, clip_duration):
        """Download track musik terpilih dari Jamendo, trim ke window yang sudah
        dihitung _find_best_music_window(), lalu mix ke video pakai ffmpeg dengan
        auto-ducking (sidechaincompress) — musik otomatis pelan pas ada dialog di clip
        dan naik lagi pas jeda, plus fade in/out biar transisinya halus. Audio ASLI
        clip TETAP ADA (bukan digantikan) — cuma di-mix bareng musiknya.

        Args:
            video_path: path clip asli (Path atau str) — file ini TIDAK diubah
            music_info: dict hasil _select_background_sound() (butuh key
                audiodownload/start/end/volume)
            clip_duration: durasi clip (detik), dipakai buat hitung titik fade-out

        Returns:
            (output_path, tmp_dir) kalau berhasil — output_path (Path) adalah video
                baru hasil mixing, tmp_dir (Path) adalah folder temp yang HARUS
                dihapus caller pakai shutil.rmtree() setelah selesai dipakai (upload).
            (None, tmp_dir_or_None) kalau gagal di step manapun — tmp_dir tetap
                dibalikin (bisa None) supaya caller tetap bisa cleanup kalau folder
                sempat kebuat.
        """
        import tempfile
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="ssrclip_music_"))
        except Exception:
            return None, None

        try:
            music_local = tmp_dir / "music_src.mp3"
            resp = requests.get(music_info["audiodownload"], timeout=60, stream=True)
            if resp.status_code != 200:
                return None, tmp_dir
            with open(music_local, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)

            output_path = tmp_dir / f"mixed_{Path(video_path).name}"
            ffmpeg_path = get_ffmpeg_path()
            fade_out_start = max(0.0, float(clip_duration) - 1.0)
            filter_complex = (
                "[0:a]asplit=2[voice_main][voice_sc];"
                f"[1:a]volume={music_info['volume']},afade=t=in:st=0:d=1,"
                f"afade=t=out:st={fade_out_start}:d=1[music_pre];"
                "[music_pre][voice_sc]sidechaincompress=threshold=0.02:ratio=8:"
                "attack=50:release=400[music_ducked];"
                "[voice_main][music_ducked]amix=inputs=2:duration=first:"
                "dropout_transition=0[aout]"
            )
            cmd = [
                ffmpeg_path, "-y",
                "-i", str(video_path),
                "-ss", str(music_info["start"]), "-to", str(music_info["end"]),
                "-i", str(music_local),
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0 or not output_path.exists():
                return None, tmp_dir
            return output_path, tmp_dir
        except Exception:
            return None, tmp_dir


    def get_clip_upload_status_summary(self):
        """Return summary of upload statuses across all clips."""
        all_clips = self.get_stock_clips()
        summary = {
            "belum_diupload": 0,
            "terjadwal": 0,
            "uploading": 0,
            "sukses": 0,
            "gagal": 0
        }
        for c in all_clips:
             status = c.get("upload_status", "belum_diupload")
             if status in summary:
                 summary[status] += 1
             else:
                 summary["belum_diupload"] += 1
        return summary

    # --- END NEW ENDPOINTS ---

    def _get_cfg_manager(self):
        return ConfigManager(Path(self.config_file), Path(self.output_dir))

    def _get_cfg(self):
        cfg_mgr = self._get_cfg_manager()
        return cfg_mgr.get_all() if hasattr(cfg_mgr, "get_all") else cfg_mgr.config

    def _get_models_url(self, base_url):
        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            return f"{url}/models"
        return f"{url}/v1/models"

    def _auth_headers(self, api_key):
        return {"Authorization": f"Bearer {api_key}"}


def _upload_scheduler(api):
    import time
    while True:
        try:
            api.workflow_tick()
        except Exception as exc:
            log_error("Workflow scheduler: " + str(exc))
        time.sleep(3)


def main():
    app_logger.info("Python runtime: %s; version=%s; venv=%s",
                    sys.executable, sys.version.split()[0], sys.prefix != sys.base_prefix)
    app_logger.info("Creating application API")
    api = WebAPI()
    app_logger.info("Application API ready")
    bundle_dir = get_bundle_dir()
    html_path = Path(bundle_dir) / "web" / "index.html"
    if not html_path.is_file():
        raise FileNotFoundError(f"Application UI is missing: {html_path}")
    
    # Optional: ensure output dir exists
    os.makedirs(api.output_dir, exist_ok=True)
    
    # Start background scheduler
    import threading
    t = threading.Thread(target=_upload_scheduler, args=(api,), daemon=True)
    t.start()
    
    # Configure pywebview window to match Figma designs (which is ~1440x900)
    app_logger.info("Creating pywebview window")
    window = webview.create_window(
        "Clipper - SSR_CLIPPER", 
        str(html_path), 
        js_api=api,
        width=1280, 
        height=800,
        min_size=(1024, 700),
        background_color='#FFFFFF'
    )
    app_logger.info("Pywebview window object ready")

    window_shown = threading.Event()
    for event_name in ("initialized", "before_show", "shown", "loaded"):
        event = getattr(window.events, event_name, None)
        if event is not None:
            event += (lambda *_args, _name=event_name, **_kwargs: app_logger.info("Pywebview event: %s", _name))
    window.events.shown += lambda *_args, **_kwargs: window_shown.set()
    closed_event = getattr(window.events, 'closed', None)
    if closed_event is not None and hasattr(api, 'editor_shutdown'):
        closed_event += lambda *_args, **_kwargs: api.editor_shutdown()

    def bind_source_drop():
        try:
            from webview.dom import DOMEventHandler
            target = window.dom.get_element('#url')
            def dropped(event):
                files = event.get('dataTransfer', {}).get('files', [])
                paths = [str(Path(f['pywebviewFullPath']).resolve()) for f in files
                         if f.get('pywebviewFullPath') and Path(f['pywebviewFullPath']).suffix.lower() in ('.mp4', '.mov', '.mkv', '.webm')]
                window.evaluate_js("window.dispatchEvent(new CustomEvent('workflow-sources-dropped', {detail: " + json.dumps(paths) + "}));")
            if target:
                target.on('dragover', DOMEventHandler(lambda _: None, prevent_default=True))
                target.on('drop', DOMEventHandler(dropped, prevent_default=True))
        except Exception as exc:
            log_error('Drag/drop unavailable: ' + str(exc))
    window.events.loaded += bind_source_drop
    
    # An explicit, existing and unique folder prevents a stale WebView2 data
    # folder from blocking another launch. Keep the private-mode behavior.
    profile_root = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "SSR_CLIPPER" / "webview2"
    profile_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="session-", dir=profile_root, ignore_cleanup_errors=True) as profile_dir:
        app_logger.info("Starting pywebview with private WebView2 data folder: %s", profile_dir)
        exited = threading.Event()
        def report_window_stall():
            if not window_shown.wait(30) and not exited.is_set():
                message = ("WebView2 belum menampilkan jendela setelah 30 detik. "
                           "Periksa error.log untuk kegagalan inisialisasi pywebview/WebView2.")
                app_logger.error(message)
                print(message, file=sys.stderr)
        threading.Thread(target=report_window_stall, daemon=True).start()
        try:
            webview.start(debug=True, private_mode=True, storage_path=profile_dir)
            app_logger.info("Pywebview event loop exited")
        finally:
            exited.set()
            if hasattr(api, 'editor_shutdown'):
                api.editor_shutdown()


if __name__ == "__main__":
    app_logger.info("=" * 60)
    app_logger.info(f"SSR_CLIPPER starting at {datetime.now().isoformat()}")
    try:
        main()
    except Exception as e:
        log_error("Fatal error in main()", e)
        raise
