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
        url = self._get_models_url(base_url)
        try:
            resp = requests.get(url, headers=self._auth_headers(api_key), timeout=15)
            if resp.status_code != 200:
                return {"models": []}
            data = resp.json()
            items = data.get("data", [])
            models = []
            for item in items:
                mid = item.get("id")
                if mid:
                    models.append(mid)
            return {"models": models}
        except:
            return {"models": []}

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

    def start_processing(self, url, num_clips=5, add_captions=True, add_hook=False, subtitle_lang="id", portrait=False):
        if self.thread and self.thread.is_alive():
            return {"status": "busy"}
        
        self.current_job = {
            "title": f"Processing {url}",
            "status": "Starting",
            "progress": 0,
            "url": url,
            "clips": num_clips
        }
            
        self.thread = threading.Thread(
            target=self._run,
            args=(url, int(num_clips), bool(add_captions), bool(add_hook), subtitle_lang, bool(portrait)),
            daemon=True,
        )
        self.thread.start()
        return {"status": "started"}

    def _run(self, url, num_clips, add_captions, add_hook, subtitle_lang, portrait):
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
        ai_providers = cfg.get("ai_providers")

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
            log_callback=log_cb,
            progress_callback=lambda s, p=None: progress_cb(p if p is not None else 0.0),
        )
        try:
            self.status = "running"
            self.progress = 0.0
            core.process(url, num_clips=num_clips, add_captions=add_captions, add_hook=add_hook)
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

    def get_repliz_dashboard_url(self):
        """Returns the URL for Repliz Dashboard."""
        return "https://dashboard.repliz.com" # Mock URL

    def get_account_stats(self):
        """Returns statistics for the connected accounts."""
        # This should theoretically come from the Repliz/TikTok/YouTube integration
        # Returning mock data for now based on the requested structure
        return {
            "campaigns": 12,
            "tiktok_count": 2,
            "youtube_count": 3
        }

    def get_campaigns(self):
        """Returns a list of campaigns and their connected accounts."""
        # Mock data representing a dynamic campaign tree
        return [
            {
                "name": "Stella's Fashion",
                "counts": "3/150",
                "children": ["TikTok: @stella_fashion", "YT: Stella Shorts"]
            },
            {
                "name": "Tech Reviews",
                "counts": "12/50",
                "children": ["TikTok: @tech_stella"]
            }
        ]

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

    def get_stock_clips(self):
        """Returns a list of generated clips from the output directory."""
        clips = []
        out_dir = Path(self.output_dir)
        
        if out_dir.exists():
            # Find all JSON metadata files
            for json_file in out_dir.rglob("data.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    folder_path = json_file.parent
                    video_title = data.get("title", "Unknown Video")
                    
                    # Look for clip metadata
                    clip_meta = data.get("clips", [])
                    if not clip_meta:
                        # Maybe legacy format, scan for mp4s
                        mp4s = list(folder_path.glob("*.mp4"))
                        for i, mp4 in enumerate(mp4s):
                            stat = mp4.stat()
                            clips.append({
                                "id": f"clip_{mp4.stem}",
                                "title": f"Clip {i+1} - {video_title}",
                                "date": stat.st_mtime * 1000,
                                "duration": "00:00", # Need ffprobe to get real duration, mock for now
                                "path": str(mp4),
                                "thumbnail": "", # Could generate a thumbnail here
                            })
                    else:
                        for c in clip_meta:
                            # Verify MP4 exists
                            mp4_path = folder_path / f"clip_{c.get('id', '')}.mp4"
                            if mp4_path.exists():
                                stat = mp4_path.stat()
                                clips.append({
                                    "id": c.get("id", ""),
                                    "title": c.get("hook_text", video_title),
                                    "date": stat.st_mtime * 1000,
                                    "duration": f"00:{int(c.get('duration', 0)):02d}",
                                    "path": str(mp4_path),
                                })
                except Exception as e:
                    print(f"Error parsing {json_file}: {e}")
                    
        # Sort by newest first
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
        
        return {
            "cookies": has_cookies,
            "ffmpeg": ffmpeg_ok,
            "deno": True, # Assume true for now, can implement real check
            "whisper": True
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
