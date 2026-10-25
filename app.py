import threading
import base64
import requests
import webview
import json
import os
import sys
import subprocess
from pathlib import Path
from config.config_manager import ConfigManager
from utils.helpers import get_app_dir, get_bundle_dir, get_ffmpeg_path, get_ytdlp_path
from clipper_core import AutoClipperCore

class ReplizUploaderAdapter:
    def __init__(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key
    
    from dialogs.repliz_upload import ReplizUploadDialog
    upload_video_to_storage = ReplizUploadDialog.upload_video_to_storage
    upload_to_repliz = ReplizUploadDialog.upload_to_repliz

# Fix for PyInstaller windowed mode (console=False)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')


class WebAPI:
    def __init__(self):
        app_dir = get_app_dir()
        self.config_file = str(app_dir / "config.json")
        self.output_dir = str(app_dir / "output")
        self.status = "idle"
        self.progress = 0.0
        self.thread = None
        self.current_job = None
        self.job_history = []

    def get_progress(self):
        return {"status": self.status, "progress": self.progress}

    def get_asset_paths(self):
        bundle_dir = get_bundle_dir()
        icon_path = Path(bundle_dir) / "assets" / "icon.png"
        return {"icon": str(icon_path)}

    def get_icon_data(self):
        try:
            bundle_dir = get_bundle_dir()
            icon_path = Path(bundle_dir) / "assets" / "icon.png"
            if not icon_path.exists():
                return {"data": ""}
            raw = icon_path.read_bytes()
            encoded = base64.b64encode(raw).decode("utf-8")
            return {"data": f"data:image/png;base64,{encoded}"}
        except:
            return {"data": ""}

    def get_ai_settings(self):
        cfg = self._get_cfg()
        return cfg.get("ai_providers", {})

    def get_provider_type(self):
        cfg = self._get_cfg()
        return {"provider_type": cfg.get("provider_type", "ytclip")}

    def validate_api_key(self, base_url, api_key):
        if not base_url:
            return {"status": "error", "message": "Missing base URL"}
        if not api_key:
            return {"status": "error", "message": "Missing API key"}
            
        # Bypass direct HTTP check for Gemini and Anthropic as they may not support standard /models endpoint for validation
        if "generativelanguage.googleapis.com" in base_url:
            return {"status": "ok"}
        if "api.anthropic.com" in base_url:
            return {"status": "ok"}
            
        url = self._get_models_url(base_url)
        try:
            resp = requests.get(url, headers=self._auth_headers(api_key), timeout=10)
            if resp.status_code == 200:
                return {"status": "ok"}
            return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

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
        cfg_mgr.save()
        return {"status": "saved"}

    def start_processing(self, url, num_clips=5, add_captions=True, add_hook=False, subtitle_lang="id", portrait=False, highlight_finder=True, yt_title_maker=True):
        if self.thread and self.thread.is_alive():
            return {"status": "busy"}
        
        import time
        self.current_job = {
            "id": f"job_{int(time.time())}",
            "title": f"Processing {url}",
            "status": "Starting",
            "progress": 0,
            "url": url,
            "clips": num_clips
        }
            
        self.thread = threading.Thread(
            target=self._run,
            args=(url, int(num_clips), bool(add_captions), bool(add_hook), subtitle_lang, bool(portrait), bool(highlight_finder), bool(yt_title_maker)),
            daemon=True,
        )
        self.thread.start()
        return {"status": "started"}

    def _run(self, url, num_clips, add_captions, add_hook, subtitle_lang, portrait, highlight_finder, yt_title_maker):
        def log_cb(msg):
            self.status = str(msg)
            if self.current_job:
                self.current_job["status"] = str(msg)

        def progress_cb(p):
            try:
                self.progress = float(p)
                if self.current_job:
                    self.current_job["progress"] = int(float(p) * 100)
            except:
                self.progress = 0.0

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
            log_callback=log_cb,
            progress_callback=lambda s, p=None: progress_cb(p if p is not None else 0.0),
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

        try:
            self.status = "running"
            self.progress = 0.0
            core.process(url, num_clips=num_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait, highlight_finder=highlight_finder, yt_title_maker=yt_title_maker)
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
        finally:
            self.thread = None

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
        return "https://dashboard.repliz.com"

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
        """Returns list of connected Repliz accounts for UI selection (upload account picker)."""
        try:
            cfg = self._get_cfg()
            repliz_cfg = cfg.get("repliz", {})
            access_key = repliz_cfg.get("access_key")
            secret_key = repliz_cfg.get("secret_key")

            if not access_key or not secret_key:
                return {"status": "error", "message": "Repliz keys not configured"}

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
                accounts = [
                    {
                        "_id": a.get("_id"),
                        "name": a.get("name"),
                        "type": a.get("type"),
                        "isConnected": a.get("isConnected", True)
                    }
                    for a in docs
                ]
                return {"status": "ok", "accounts": accounts}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_campaigns(self):
        """Repliz public API has no campaigns endpoint yet. Return an empty list
        (not an error object) so the frontend's `campaigns.length` check works
        correctly and the Campaigns Tree just renders empty instead of breaking."""
        return []

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
            self._get_cfg_manager().save(cfg)
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
            self._get_cfg_manager().save(cfg)
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
            self._get_cfg_manager().save(cfg)
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
            self._get_cfg_manager().save(cfg)
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
            self._get_cfg_manager().save(cfg)
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
        total_clips = 0
        storage_bytes = 0
        
        if out_dir.exists():
            for f in out_dir.rglob("*.mp4"):
                total_clips += 1
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
                })

        folders.sort(key=lambda f: f.get("date", ""), reverse=True)
        return folders

    def get_stock_clips(self, folder_id=None):
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

    def check_dependencies(self):
        """Returns the status of dependencies."""
        app_dir = get_app_dir()
        cookies_path = app_dir / "cookies.txt"
        has_cookies = cookies_path.exists()
        
        # Simplified dependency check
        ffmpeg_ok = Path(get_ffmpeg_path()).exists() if get_ffmpeg_path() else False
        
        import shutil
        deno_ok = shutil.which("deno") is not None
        
        try:
            import faster_whisper
            whisper_ok = True
        except ImportError:
            try:
                import whisper
                whisper_ok = True
            except ImportError:
                whisper_ok = False
                
        ytdlp_path = get_ytdlp_path()
        ytdlp_ok = ytdlp_path is not None and ytdlp_path != ""
        if ytdlp_path not in ("yt_dlp_module",):
            # kalau bukan python module, pastikan path/command-nya beneran ada
            import shutil as _shutil
            ytdlp_ok = _shutil.which(ytdlp_path) is not None or Path(ytdlp_path).exists()
        
        return {
            "cookies": has_cookies,
            "ffmpeg": ffmpeg_ok,
            "deno": deno_ok,
            "whisper": whisper_ok,
            "ytdlp": ytdlp_ok
        }

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

    def delete_job(self, job_id):
        """Delete a job from job history."""
        self.job_history = [j for j in self.job_history if j.get("id") != job_id]
        return {"status": "ok"}

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
        """Upload clip to the specified platform."""
        kwargs = options or {}
        cfg_mgr = self._get_cfg_manager()
        
        if platform == "tiktok":
            from tiktok_uploader import TikTokUploader
            uploader = TikTokUploader(cfg_mgr)
            if not uploader.is_configured() or not uploader.is_authenticated():
                return {"status": "error", "message": "Kredensial TikTok belum diisi di Settings"}
            
            try:
                title = kwargs.get("title", Path(clip_path).stem)
                desc = kwargs.get("description", "")
                result = uploader.upload_video(clip_path, title=title, description=desc)
                if result.get("success"):
                    return {"status": "success", "message": result.get("message", "Uploaded to TikTok")}
                else:
                    return {"status": "error", "message": result.get("error", "Failed to upload to TikTok")}
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        elif platform == "youtube":
            from youtube_uploader import YouTubeUploader
            uploader = YouTubeUploader()
            if not uploader.is_configured() or not uploader.is_authenticated():
                return {"status": "error", "message": "Kredensial YouTube belum diisi di Settings"}
            
            try:
                title = kwargs.get("title", Path(clip_path).stem)
                desc = kwargs.get("description", "")
                result = uploader.upload_video(clip_path, title=title, description=desc)
                if result.get("success"):
                    return {"status": "success", "message": f"Uploaded to YouTube: {result.get('url', '')}"}
                else:
                    return {"status": "error", "message": result.get("error", "Failed to upload to YouTube")}
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        elif platform == "repliz":
            cfg = cfg_mgr.get_all() if hasattr(cfg_mgr, "get_all") else cfg_mgr.config
            repliz_cfg = cfg.get("repliz", {})
            acc_key = repliz_cfg.get("access_key")
            sec_key = repliz_cfg.get("secret_key")
            if not acc_key or not sec_key:
                 return {"status": "error", "message": "Kredensial Repliz belum diisi di Settings"}
            
            uploader = ReplizUploaderAdapter(acc_key, sec_key)
            account_id = kwargs.get("account_id")
            if not account_id:
                 return {"status": "error", "message": "Missing account_id for Repliz upload"}
            
            try:
                title = kwargs.get("title", Path(clip_path).stem)
                desc = kwargs.get("description", "")
                
                vid_url = uploader.upload_video_to_storage(clip_path)
                if not vid_url:
                     return {"status": "error", "message": "Failed to upload video to storage"}
                     
                success, msg = uploader.upload_to_repliz(account_id, title, desc, vid_url)
                if success:
                     return {"status": "success", "message": msg}
                else:
                     return {"status": "error", "message": msg}
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        return {"status": "error", "message": f"Platform '{platform}' tidak didukung"}

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

    def install_dependencies(self):
        """Trigger dependency installation in background."""
        try:
            from utils.dependency_manager import DependencyManager
            dm = DependencyManager()
            t = threading.Thread(target=dm.install_all, daemon=True)
            t.start()
            return {"status": "started"}
        except Exception as e:
            print(f"Error starting install: {e}")
            return {"status": "error", "message": str(e)}

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


def main():
    api = WebAPI()
    bundle_dir = get_bundle_dir()
    html_path = Path(bundle_dir) / "web" / "index.html"
    
    # Optional: ensure output dir exists
    os.makedirs(api.output_dir, exist_ok=True)
    
    # Configure pywebview window to match Figma designs (which is ~1440x900)
    window = webview.create_window(
        "Clipper - YT Short Clipper", 
        str(html_path), 
        js_api=api,
        width=1280, 
        height=800,
        min_size=(1024, 700),
        background_color='#FFFFFF'
    )
    
    # Start webview app
    webview.start(debug=True)


if __name__ == "__main__":
    main()
