"""Music-only revisions always start from a verified master without added music."""
import copy
import json
import math
from pathlib import Path
import shutil
import subprocess
import threading
import uuid

import numpy as np

from .editing import analyze_audio, bounded_ffmpeg_command, file_sha256, mix_music, probe_media
from .storage import atomic_json, digest, utc_now
from utils.helpers import get_ffmpeg_path

_PREVIEW_LOCK = threading.RLock()


def verify_music_balance(dry, mixed, music, ffmpeg="ffmpeg"):
    """Estimate selected music in the actual encoded result, not just an audio track."""
    duration = min(120, probe_media(mixed, ffmpeg)["duration"])
    def pcm(inputs, filters=None):
        command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", *inputs, "-t", str(duration), "-vn"]
        if filters:
            command += ["-af", filters]
        result = subprocess.run(bounded_ffmpeg_command(command + ["-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"]),
            capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise ValueError("Audio hasil mixing gagal didekode untuk pemeriksaan musik.")
        return np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)
    result = pcm(["-i", str(mixed)])
    source = pcm(["-i", str(dry)]) if probe_media(dry, ffmpeg)["has_audio"] else np.zeros_like(result)
    bed = pcm(["-stream_loop", "-1", "-ss", str(music.get("start_seconds", 0)), "-t", str(duration),
               "-i", str(music["path"])],
              f"aresample=48000,loudnorm=I={music['mixing']['normalization_lufs']}:TP=-2:LRA=11")
    count = min(len(source), len(result), len(bed))
    if count < 800:
        raise ValueError("Audio terlalu pendek untuk pemeriksaan musik.")
    # Discard fades when possible; AAC delay is estimated against the dry dialogue.
    trim = min(8000, count // 10)
    source, result, bed = (v[trim:count-trim] for v in (source, result, bed))
    def align(a, b, lag):
        left, right = max(0, -lag), max(0, lag)
        n = min(len(a)-left, len(b)-right)
        return a[left:left+n], b[right:right+n]
    def corr(a, b):
        return float(np.dot(a, b) / max(1e-20, np.sqrt(np.dot(a, a) * np.dot(b, b))))
    lag = max(range(-80, 81), key=lambda n: corr(*(v[::4] for v in align(source, result, n))))
    source, result = align(source, result, lag)
    gain = float(np.dot(source, result) / max(1e-20, np.dot(source, source)))
    residual = result - gain * source
    bed = bed[max(0, -lag):max(0, -lag) + len(residual)]
    n = min(len(bed), len(residual))
    bed, residual = bed[:n], residual[:n]
    music_lag = max(range(-80, 81), key=lambda n: corr(*(v[::4] for v in align(bed, residual, n))))
    bed, residual = align(bed, residual, music_lag)
    coefficient = float(np.dot(bed, residual) / max(1e-20, np.dot(bed, bed)))
    voice_rms = float(np.sqrt(np.mean((gain * source) ** 2)))
    music_rms = float(np.sqrt(np.mean((coefficient * bed) ** 2)))
    relative = 20 * math.log10(max(music_rms, 1e-20) / max(voice_rms, 1e-20)) if voice_rms > 1e-6 else None
    correlation = corr(bed, residual)
    present = coefficient > 0 and music_rms > 1e-5 and correlation > .05
    warnings = []
    if not present:
        warnings.append("Kontribusi lagu terpilih pada hasil akhir belum terverifikasi; periksa preview musik.")
    elif relative is not None and relative < -18:
        warnings.append("Musik terukur sangat pelan dibanding audio asli; periksa level musik pada preview.")
    elif relative is not None and relative > -5:
        warnings.append("Musik terukur dekat dengan level audio asli; periksa benturan vokal pada preview.")
    return {"method": "aligned_pcm_projection", "scope": "Estimasi sinyal, bukan penilaian rasa musik atau kejelasan kata.",
            "analyzed_seconds": duration, "selected_music_present": present,
            "music_to_source_db": round(relative, 2) if relative is not None else None,
            "music_residual_correlation": round(correlation, 4), "warnings": warnings}


class MusicReviewMixin:
    def test_music_audio_model(self, provider):
        try:
            if not isinstance(provider, dict):
                raise ValueError("Provider analisis musik tidak valid.")
            root = Path(self.output_dir) / "_cache" / "music-selection"
            source = next((root / "audio").glob("*.mp3"), None)
            if source is None:
                raise ValueError("Belum ada audio kandidat untuk test. Jalankan pemilihan musik terlebih dahulu.")
            from .music_audio import MusicAudioAnalyzer
            profile = MusicAudioAnalyzer({"ai_providers": {"music_analyzer": provider}}, root).analyze(
                source, seconds=12, use_cache=False)
            return {"status": "ok", "message": "Audio terkirim dan profil bertimestamp diterima: " +
                    str(profile["provenance"].get("returned_model") or provider.get("model"))}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _music_review_input(self, clip_id, payload):
        if not isinstance(payload, dict):
            raise ValueError("Pengaturan preview musik tidak valid.")
        clip = self._get_store().get("clip", str(clip_id))
        if not clip:
            raise ValueError("Clip tidak ditemukan.")
        if payload.get("revision_id") != clip.get("revision_id"):
            raise ValueError("Revisi clip berubah. Muat ulang review.")
        if file_sha256(clip["path"]) != clip.get("file_hash"):
            raise ValueError("File clip berubah. Muat ulang review.")
        master = clip.get("dry_master") or {}
        dry = Path(master.get("path") or "")
        if not dry.is_file() or file_sha256(dry) != master.get("sha256"):
            raise ValueError("Master tanpa musik belum tersedia atau berubah. Render ulang clip dari sumber terlebih dahulu.")
        music = copy.deepcopy(clip.get("music") or {})
        candidate_id = payload.get("candidate_id")
        if candidate_id:
            candidate = next((c for c in (music.get("selection") or {}).get("alternatives", [])
                              if c.get("candidate_id") == candidate_id), None)
            if not candidate:
                raise ValueError("Pilihan passage tidak berasal dari kandidat clip.")
            path = Path(candidate.get("path") or "")
            if not path.is_file() or file_sha256(path) != candidate.get("sha256"):
                raise ValueError("File kandidat musik berubah atau tidak tersedia.")
            music.update(path=str(path), start_seconds=candidate["start"], sha256=candidate["sha256"],
                         attribution={k: candidate.get(k) for k in ("id", "name", "artist", "license_ccurl")})
            music.pop("source_path", None)
            music["selection"].update(reason=candidate.get("reason"), semantic=candidate.get("semantic"),
                score=candidate.get("score"), audio_window={"start": candidate["start"], "end": candidate["end"]})
        for key, minimum, maximum in (("start_seconds", 0, 86400), ("volume", .01, 2)):
            value = float(payload.get(key, music.get(key, .5 if key == "volume" else 0)))
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError("Titik mulai atau level musik tidak valid.")
            music[key] = value
        if "ducking" in payload:
            if not isinstance(payload["ducking"], bool):
                raise ValueError("Ducking harus berupa pilihan aktif/nonaktif.")
            music["ducking"] = payload["ducking"]
        path = Path(music.get("source_path") or music.get("path") or "")
        if not path.is_file() or file_sha256(path) != music.get("sha256"):
            raise ValueError("Musik yang dipilih tidak tersedia atau berubah.")
        track_duration = probe_media(path, get_ffmpeg_path())["duration"]
        if music["start_seconds"] >= track_duration:
            raise ValueError("Titik mulai melewati akhir lagu.")
        duration = probe_media(dry, get_ffmpeg_path())["duration"]
        selection = music.get("selection") or {}
        old_window = selection.get("audio_window") or {}
        end = min(track_duration, music["start_seconds"] + duration)
        if abs(float(old_window.get("start", music["start_seconds"])) - music["start_seconds"]) > .01:
            semantic = selection.get("semantic") or {}
            pieces = [s for s in semantic.get("observations", []) if s["end"] > music["start_seconds"] and s["start"] < end]
            coverage = sum(max(0, min(end, s["end"]) - max(music["start_seconds"], s["start"])) for s in pieces) / max(.001, end-music["start_seconds"])
            selection["semantic"] = {**semantic, "observations": pieces, "coverage": round(coverage, 3),
                                     "phrase_aligned": False, "manual_start_changed": True}
        selection["audio_window"] = {"start": music["start_seconds"], "end": end,
                                    "loop_needed": music["start_seconds"] + duration > track_duration}
        music["selection"] = selection
        return clip, dry, music

    def preview_clip_music(self, clip_id, payload):
        try:
            clip, dry, music = self._music_review_input(clip_id, payload)
            ffmpeg = get_ffmpeg_path()
            identity = {"dry": clip["dry_master"]["sha256"], "music": music["sha256"],
                        "start": music["start_seconds"], "volume": music["volume"],
                        "ducking": music.get("ducking", True),
                        "fade": [music.get(k) for k in ("fade_in", "fade_out", "fade_seconds")], "version": 1}
            directory = Path(self.output_dir) / "_cache" / "music-preview"
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / (digest(identity) + ".mp4")
            meta = target.with_suffix(".json")
            with _PREVIEW_LOCK:
                try:
                    rendered = json.loads(meta.read_text(encoding="utf-8"))
                    if not target.is_file() or rendered["sha256"] != file_sha256(target):
                        raise ValueError("Preview berubah")
                except (OSError, ValueError, KeyError):
                    temporary = directory / (uuid.uuid4().hex + ".mp4")
                    try:
                        mixed = mix_music(dry, music, temporary, ffmpeg)
                        balance = verify_music_balance(dry, temporary, mixed, ffmpeg)
                        temporary.replace(target)
                        rendered = {"sha256": file_sha256(target), "music": mixed, "balance": balance}
                        atomic_json(meta, rendered)
                    finally:
                        temporary.unlink(missing_ok=True)
            from .media_preview import MediaPreview
            with self._workflow_init_lock:
                if not hasattr(self, "_media_preview"):
                    self._media_preview = MediaPreview()
            return {"status": "ok", "preview_url": self._media_preview.register(target),
                    "preview_path": str(target), "music": {**music, **{k: rendered["music"][k] for k in
                        ("required", "mixed", "mixing", "duration_seconds")}}, "balance": rendered["balance"]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def apply_clip_music(self, clip_id, payload):
        try:
            clip, dry, music = self._music_review_input(clip_id, payload)
            preview = self.preview_clip_music(clip_id, payload)
            if preview["status"] != "ok":
                return preview
            self._music_review_input(clip_id, payload)
            # New file and pending review: approved or scheduled originals are never overwritten.
            destination = Path(self.output_dir) / "music-revisions" / ("clip-" + uuid.uuid4().hex[:16])
            destination.mkdir(parents=True)
            final, clean = destination / "master.mp4", destination / "master_without_music.mp4"
            shutil.copyfile(preview["preview_path"], final)
            shutil.copyfile(dry, clean)
            metadata = copy.deepcopy(clip)
            for key in ("id", "clip_id", "revision_id", "approval_hash", "platform_variants", "default_platform", "music_feedback"):
                metadata.pop(key, None)
            metadata.update(final_path=str(final), final_sha256=file_sha256(final), created_at=utc_now(),
                dry_master={"path": str(clean), "sha256": file_sha256(clean)},
                music=preview["music"], music_balance=preview["balance"],
                audio_analysis=analyze_audio(final, get_ffmpeg_path()),
                music_revision={"parent_clip_id": clip_id, "parent_revision_id": clip["revision_id"], "settings": payload})
            metadata["music"]["selection"].update(review_required=False, human_override=True)
            old_warnings = set((clip.get("music_balance") or {}).get("warnings", []))
            metadata["warnings"] = [v for v in clip.get("warnings", []) if v not in old_warnings and not v.startswith("Pilihan musik perlu review")]
            metadata["warnings"].extend(preview["balance"]["warnings"])
            from .clip_variants import render_platform_variants
            variants, eligibility, applied, preferred = render_platform_variants(final,
                metadata.get("clip_plan", {}).get("additional", {}).get("items", []),
                metadata.get("additional", {}).get("face_gate", {}), metadata.get("campaign_snapshot") or {}, get_ffmpeg_path())
            metadata.update(platform_variants=variants, platform_eligibility=eligibility, default_platform=preferred)
            metadata["additional"] = {**metadata.get("additional", {}), "watermarks": applied}
            metadata["final_sha256"] = file_sha256(final)
            old_attribution = clip.get("music", {}).get("attribution") or {}
            attribution = metadata["music"].get("attribution") or {}
            old_line = f"Musik: {old_attribution.get('name', '')} \u2014 {old_attribution.get('artist', '')}"
            if old_attribution.get("artist") and old_line in metadata.get("caption", ""):
                new_line = f"Musik: {attribution.get('name', '')} \u2014 {attribution.get('artist', '')}"
                metadata["caption"] = metadata["caption"].replace(old_line, new_line if attribution.get("artist") else "")
                from .account_tags import platform_captions
                _, metadata["captions"] = platform_captions(metadata["caption"], metadata.get("campaign_snapshot", {}).get("brief", {}))
            registered = self._register_clip(final, metadata)
            atomic_json(destination / "data.json", registered)
            return {"status": "ok", "clip": registered}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def record_music_feedback(self, clip_id, payload):
        try:
            if not isinstance(payload, dict):
                raise ValueError("Penilaian musik tidak valid.")
            labels = payload.get("labels")
            allowed = {"good_fit", "wrong_mood", "too_quiet", "vocal_clash"}
            if not isinstance(labels, list) or not labels or any(v not in allowed for v in labels):
                raise ValueError("Pilih penilaian musik yang tersedia.")
            if "good_fit" in labels and len(set(labels)) > 1:
                raise ValueError("Pilih cocok atau masalah yang perlu diperbaiki.")
            note = payload.get("note", "")
            if not isinstance(note, str) or len(note) > 2000:
                raise ValueError("Catatan maksimal 2.000 karakter.")
            store = self._get_store()
            with store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT data FROM entities WHERE kind='clip' AND id=?", (str(clip_id),)).fetchone()
                if not row:
                    raise ValueError("Clip tidak ditemukan.")
                clip = json.loads(row["data"])
                if payload.get("revision_id") != clip.get("revision_id") or file_sha256(clip["path"]) != clip.get("file_hash"):
                    raise ValueError("Revisi atau file clip berubah. Muat ulang review.")
                feedback = {"id": "music_" + self._highlight_feedback_id(clip), "clip_id": clip_id,
                    "revision_id": clip["revision_id"], "campaign_id": clip.get("campaign_id"),
                    "music": {"attribution": clip.get("music", {}).get("attribution"),
                              "start_seconds": clip.get("music", {}).get("start_seconds")},
                    "labels": list(dict.fromkeys(labels)), "note": note.strip(), "created_at": utc_now()}
                store._put(connection, "music_feedback", feedback["id"], feedback)
            return {"status": "ok", "feedback": feedback}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
