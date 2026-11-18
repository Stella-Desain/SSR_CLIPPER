"""Read example speech only on an explicit profile suggestion action.

The cache is content-addressed, contains no credentials, and never downloads a
model. Reference videos are examples of selection; their duration and editing
are not campaign settings.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
from pathlib import Path

from .editing import _run, probe_media
from .storage import atomic_json, file_digest

REFERENCE_ANALYSIS_VERSION = 1
MAX_REFERENCES = 16
MAX_REFERENCE_SECONDS = 1800
MAX_TRANSCRIPT_CHARS = 120000
_SRT_CUE = re.compile(
    r"(?m)^(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})[^\n]*\n(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def _seconds(value):
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _timestamp(value):
    millis = round(value * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def transcript_segments(text):
    """Accept timed SRT or the application's bracketed transcript format."""
    result = []
    for match in _SRT_CUE.finditer(text):
        result.append({"start": _seconds(match[1]), "end": _seconds(match[2]),
                       "text": re.sub(r"<[^>]+>", "", " ".join(match[3].split()))})
    if not result:
        from .speech_boundaries import parse_cues
        result = parse_cues(text)
    return result


def inspect_sidecar(item, video):
    """Bind optional adjacent subtitles to the chosen video before import."""
    supplied = item.get("transcript")
    if supplied is not None and not isinstance(supplied, dict):
        raise ValueError("Data transkrip referensi tidak valid")
    path = Path(supplied.get("path", "")) if supplied else Path(video).with_suffix(".srt")
    if not supplied and not path.is_file():
        return None
    path = path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".srt", ".txt"}:
        raise ValueError("Transkrip referensi harus file SRT atau TXT dengan timestamp")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Transkrip referensi maksimal 2 MB")
    digest = file_digest(path)
    if supplied and supplied.get("sha256") and supplied["sha256"] != digest:
        raise ValueError(f"Isi transkrip berubah. Tambahkan kembali referensi: {path.name}")
    return {"path": str(path), "name": path.name, "sha256": digest}


class HighlightReferenceAnalyzer:
    def __init__(self, config, cache_root, *, ffmpeg=None):
        self.config = config
        self.cache_root = Path(cache_root)
        if ffmpeg is None:
            from utils.helpers import get_ffmpeg_path
            ffmpeg = get_ffmpeg_path()
        self.ffmpeg = str(ffmpeg)

    def _settings(self, language):
        language = str(language or "").strip()
        if language.casefold() in {"auto", "none", ""}:
            language = None
        providers = self.config.get("ai_providers", {})
        local_model = str(providers.get("whisper_model") or "api")
        caption = providers.get("caption_maker", {})
        return {"version": REFERENCE_ANALYSIS_VERSION, "language": language,
                "mode": "local" if local_model != "api" else "api",
                "model": local_model if local_model != "api" else str(caption.get("model") or "whisper-1"),
                "base_url": str(caption.get("base_url") or "") if local_model == "api" else ""}

    @staticmethod
    def _validate_segments(segments, duration):
        validated = []
        if not isinstance(segments, list):
            raise ValueError("Format transkrip referensi tidak valid")
        for item in segments:
            try:
                start, end = float(item["start"]), float(item["end"])
                speech = " ".join(str(item.get("text") or "").split())
                if not all(math.isfinite(x) for x in (start, end)) or start < 0 or end <= start or end > duration + .5:
                    raise ValueError("Timestamp transkrip referensi berada di luar video")
                if speech:
                    validated.append({"start": start, "end": min(end, duration), "text": speech})
            except (TypeError, KeyError):
                raise ValueError("Format transkrip referensi tidak valid") from None
        return sorted(validated, key=lambda item: (item["start"], item["end"]))

    def _read_cache(self, path, identity, asset):
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            analysis = cached["analysis"]
            duration = float(analysis["duration_seconds"])
            transcript = analysis["transcript"]
            if (cached.get("identity") != identity or analysis.get("sha256") != asset["sha256"]
                    or not math.isfinite(duration) or not 0 < duration <= MAX_REFERENCE_SECONDS
                    or not isinstance(transcript, str) or not transcript or len(transcript) > MAX_TRANSCRIPT_CHARS
                    or analysis.get("transcription_source") not in {"subtitle_file", "local_whisper", "caption_maker"}
                    or not self._validate_segments(transcript_segments(transcript), duration)):
                return None
            warnings = analysis.get("warnings", [])
            if not isinstance(warnings, list) or any(not isinstance(warning, str) for warning in warnings):
                return None
            return {"asset_id": asset["id"], "sha256": asset["sha256"], "name": asset.get("name") or Path(asset["path"]).name,
                    "duration_seconds": duration, "transcript": transcript,
                    "transcription_source": analysis["transcription_source"],
                    "transcription_model": identity["model"] if analysis["transcription_source"] != "subtitle_file" else None,
                    "warnings": [warning[:2000] for warning in warnings[:20]]}
        except (ValueError, TypeError, KeyError, OSError):
            return None

    def analyze(self, asset, language="id"):
        path = Path(asset["path"])
        if not path.is_file() or file_digest(path) != asset["sha256"]:
            raise ValueError(f"Video referensi berubah atau hilang. Tambahkan kembali: {asset.get('name', path.name)}")
        sidecar = inspect_sidecar(asset, path)
        settings = self._settings(language)
        identity = {**settings, "video_sha256": asset["sha256"],
                    "transcript_sha256": sidecar["sha256"] if sidecar else None}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        cached_file = self.cache_root / f"{key}.json"
        if cached_file.is_file():
            cached = self._read_cache(cached_file, identity, asset)
            if cached is not None:
                if file_digest(path) != asset["sha256"] or (sidecar and file_digest(sidecar["path"]) != sidecar["sha256"]):
                    raise ValueError("Referensi berubah saat dibaca. Tambahkan kembali file tersebut.")
                return cached
        media = probe_media(path, self.ffmpeg)
        duration = float(media.get("duration") or 0)
        if not media.get("has_video") or not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"Video referensi tidak dapat dibaca: {asset.get('name', path.name)}")
        if duration > MAX_REFERENCE_SECONDS:
            raise ValueError("Referensi highlight maksimal 30 menit. Pilih contoh clip yang lebih singkat.")
        if sidecar:
            text = Path(sidecar["path"]).read_text(encoding="utf-8-sig")
            if len(text) > MAX_TRANSCRIPT_CHARS:
                raise ValueError("Transkrip referensi melebihi 120.000 karakter")
            segments = transcript_segments(text)
            source = "subtitle_file"
        elif not media.get("has_audio"):
            raise ValueError("Video referensi tidak memiliki ucapan/audio. Tambahkan transkrip dengan timestamp.")
        elif settings["mode"] == "local":
            segments = self._transcribe_local(path, settings)
            source = "local_whisper"
        else:
            segments = self._transcribe_api(path, settings)
            source = "caption_maker"
        validated = self._validate_segments(segments, duration)
        if not validated:
            raise ValueError(f"Belum ditemukan ucapan bertimestamp pada {asset.get('name', path.name)}. Tambahkan SRT atau periksa Caption Maker.")
        transcript = "\n".join(f"[{_timestamp(item['start'])} - {_timestamp(item['end'])}] {item['text']}" for item in validated)
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            raise ValueError("Transkrip referensi melebihi 120.000 karakter")
        warnings = []
        if source != "subtitle_file":
            warnings.append("Transkrip otomatis dapat salah mendengar kata atau musik. Periksa ringkasan sebelum menerapkan profil.")
        analysis = {"asset_id": asset["id"], "sha256": asset["sha256"], "name": asset.get("name") or path.name,
                    "duration_seconds": duration, "transcript": transcript,
                    "transcription_source": source, "transcription_model": settings["model"] if source != "subtitle_file" else None,
                    "warnings": warnings}
        # Recheck before caching so a replaced file can never acquire the old identity.
        if file_digest(path) != asset["sha256"] or (sidecar and file_digest(sidecar["path"]) != sidecar["sha256"]):
            raise ValueError("Referensi berubah saat dianalisis. Tambahkan kembali file tersebut.")
        atomic_json(cached_file, {"identity": identity, "analysis": analysis})
        return analysis

    def _transcribe_local(self, path, settings):
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(settings["model"], device="cpu", compute_type="int8", local_files_only=True)
        except Exception as exc:
            raise ValueError("Model Whisper lokal belum tersedia atau belum dapat dimuat. Pilih model yang sudah diunduh di Pengaturan, tambahkan SRT, atau gunakan Caption Maker API.") from exc
        segments, _ = model.transcribe(str(path), language=settings["language"] or None,
                                       beam_size=5, word_timestamps=True, vad_filter=True)
        return [{"start": item.start, "end": item.end, "text": item.text} for item in segments
                if getattr(item, "no_speech_prob", 0) < .85]

    def _transcribe_api(self, path, settings):
        provider = self.config.get("ai_providers", {}).get("caption_maker", {})
        if not provider.get("api_key") or not provider.get("model"):
            raise ValueError("Atur Caption Maker untuk membaca ucapan referensi, atau tambahkan SRT di samping video. Profil tetap dapat diisi manual.")
        from openai import OpenAI
        client = OpenAI(api_key=provider["api_key"], base_url=provider.get("base_url") or None, timeout=120, max_retries=1)
        with tempfile.TemporaryDirectory(prefix="ssr-highlight-reference-") as directory:
            audio = Path(directory) / "speech.mp3"
            _run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path),
                  "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(audio)], timeout=180)
            if audio.stat().st_size > 24 * 1024 * 1024:
                raise ValueError("Audio referensi terlalu besar untuk Caption Maker. Pilih contoh yang lebih singkat atau tambahkan SRT.")
            kwargs = {"model": provider["model"], "response_format": "verbose_json"}
            if settings["language"]:
                kwargs["language"] = settings["language"]
            with audio.open("rb") as stream:
                response = client.audio.transcriptions.create(file=stream, **kwargs)
            raw = response.model_dump() if hasattr(response, "model_dump") else response
            if not isinstance(raw, dict) or not isinstance(raw.get("segments"), list):
                raise ValueError("Caption Maker tidak mengembalikan timestamp ucapan. Gunakan model transkripsi yang mendukung verbose_json atau tambahkan SRT.")
            return raw["segments"]
