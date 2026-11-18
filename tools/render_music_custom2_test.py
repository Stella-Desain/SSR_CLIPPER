"""Render one existing project highlight using Custom2 and the new music selector.

Production clips, campaign settings, the desktop queue, and publications are
not modified. Source word timings and the chosen clip's template are reused.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from app import WebAPI
from clipper_core import AutoClipperCore
from services.editing import analyze_audio, build_clip_plan, config_hash, file_sha256, mix_music, probe_media, timestamp_seconds
from services.music_selection import MusicSelector
from services.storage import atomic_json, utc_now
from utils.helpers import get_ffmpeg_path


def clip_words(source_words, start, end):
    return [word for segment in source_words["segments"] for word in segment.get("words", [])
            if word["end"] > start and word["start"] < end and word["end"] > word["start"]]


def shifted_transcript(source_words, highlight):
    start, end = (timestamp_seconds(highlight[key]) for key in ("start_time", "end_time"))
    words = [SimpleNamespace(word=w["word"], start=max(0, w["start"] - start),
                             end=min(end - start, w["end"] - start)) for w in clip_words(source_words, start, end)]
    if not words:
        raise ValueError("Tidak ada waktu kata sumber untuk highlight ini.")
    text = "".join(w.word for w in words).strip()
    return SimpleNamespace(words=words, segments=[{"start": words[0].start, "end": words[-1].end, "text": text}], text=text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT / "output/job-129d2adda72b4e00")
    parser.add_argument("--resume", type=Path, help="Lanjutkan tes yang gambar/subtitle-nya selesai tetapi musiknya gagal")
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    provider = cfg["ai_providers"]["highlight_finder"]
    custom2 = cfg["ai_providers"]["custom_provider"]
    if (provider.get("model") != "Codex-6.1sol" or not provider.get("api_key")
            or provider.get("base_url") != custom2.get("base_url") or provider["api_key"] != custom2.get("api_key")):
        raise ValueError("Highlight Finder harus memakai [Custom2] Codex-6.1sol sesuai Settings.")
    cfg = copy.deepcopy(cfg)
    cfg["ai_providers"]["highlight_finder"]["reasoning_effort"] = "xhigh"
    test_root = (Path(cfg.get("output_dir") or ROOT / "output") / "_tests").resolve()
    destination = args.resume.resolve() if args.resume else test_root / ("music-custom2-" + uuid.uuid4().hex[:10])
    if not destination.is_relative_to(test_root):
        raise ValueError("Resume harus berada di folder output/_tests.")
    if not args.resume:
        destination.mkdir(parents=True, exist_ok=False)
    report_path = destination / "test-report.json"
    report = {"status": "started", "started_at": utc_now(), "project": str(args.project.resolve()),
        "provider": "Custom2", "requested_model": provider["model"], "reasoning_effort": "xhigh",
        "production_clips_modified": False, "config_changed": False, "published": False}
    if args.resume:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (report.get("status") != "failed" or report.get("project") != str(args.project.resolve())
                or not (destination / "clip-001/master.mp4").is_file()):
            raise ValueError("Hanya tes gagal dari project yang sama dengan video dasar tersedia yang dapat dilanjutkan.")
        report.setdefault("previous_failures", []).append({key: report.get(key)
            for key in ("finished_at", "error", "cause", "music_failed_stage", "error_chain")})
        report.pop("error_chain", None)
        report.pop("music_failed_stage", None)
        report.update(status="resuming", error=None, cause=None)
    atomic_json(report_path, report)
    core = None
    try:
        project = json.loads((args.project / "data.json").read_text(encoding="utf-8"))
        records = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(args.project.glob("clip-*/data.json"))]
        if len(records) != 51 or project.get("clip_count") != 51:
            raise ValueError("Tes ini membutuhkan project berisi 51 highlight.")
        first = records[0][1]
        source_path = Path(first["clip_plan"]["segments"][0]["path"])
        words_path = Path(first["caption_transcript_provenance"]["source_words_path"])
        source_words = json.loads(words_path.read_text(encoding="utf-8"))
        source_hash = file_sha256(source_path)
        if source_hash != source_words.get("source_sha256"):
            raise ValueError("Transkrip kata tidak cocok dengan hash video sumber.")
        candidates = []
        by_id = {}
        for path, metadata in records:
            identifier = path.parent.name
            start, end = (timestamp_seconds(metadata[key]) for key in ("start_time", "end_time"))
            words = clip_words(source_words, start, end)
            candidates.append({"id": identifier, "title": metadata["title"], "start": metadata["start_time"],
                "end": metadata["end_time"], "duration_seconds": end - start,
                "transcript": "".join(w["word"] for w in words).strip()})
            by_id[identifier] = metadata
        api = WebAPI.__new__(WebAPI)
        api.output_dir = cfg.get("output_dir") or str(ROOT / "output")
        api._get_cfg = lambda: cfg
        selector = MusicSelector(api, cfg, Path(api.output_dir) / "_cache/music-selection")
        if args.resume:
            choice = report["highlight_choice"]
            selector.ai_calls = report["highlight_ai_calls"]
        else:
            print("Custom2: memilih satu dari 51 highlight sumber.", flush=True)
            choice = selector.ask('Pilih tepat satu highlight untuk tes edit self-growth ala YoaClips. '
                'Nilai gagasan utuh, pembuka, pelajaran, konteks, dan audiens campaign. Kandidat berisi '
                'ucapan asli dengan rentang terverifikasi. Jangan mengubah rentang atau mengarang ID. '
                'Schema: {"id":"clip-...","reason":"alasan singkat berbahasa Indonesia"}.',
                {"project": project["title"], "profile": project.get("highlight_profile"), "candidates": candidates})
        if choice.get("id") not in by_id:
            raise ValueError("Custom2 tidak memilih ID highlight yang tersedia.")
        if not selector.ai_calls or selector.ai_calls[-1]["returned_model"] != "gpt-6.1-sol":
            raise ValueError("Balasan Custom2 belum memverifikasi model gpt-6.1-sol.")
        original = by_id[choice["id"]]
        highlight = copy.deepcopy(original["highlight"])
        campaign = copy.deepcopy(original["campaign_snapshot"])
        campaign["editing"]["review_mode"] = "manual"
        campaign["editing"]["music"].update(policy="auto", path="", catalog="repliz",
            reference_style="now_or_never", style_brief="Musik mendukung pesan self-growth dan tidak menutupi dialog.")
        campaign["editing"]["music"].pop("source_path", None)
        highlight["custom2_test_selection"] = {**choice, "ai_calls": copy.deepcopy(selector.ai_calls),
            "source_project": str(args.project.resolve()), "original_clip_id": original.get("clip_id")}
        report.update(project_title=project["title"], original_clip=choice["id"],
            highlight_title=highlight["title"], highlight_choice=choice, highlight_ai_calls=copy.deepcopy(selector.ai_calls))
        atomic_json(destination / "highlight.json", highlight)
        print(f"Highlight: {choice['id']} / {highlight['title']}", flush=True)
        ffmpeg = get_ffmpeg_path()
        core = AutoClipperCore(selector.client, ffmpeg_path=ffmpeg, output_dir=str(destination),
            ai_providers=cfg["ai_providers"], face_tracking_mode=cfg.get("face_tracking_mode", "mediapipe"),
            mediapipe_settings=cfg.get("mediapipe_settings"), subtitle_language="id",
            local_whisper_settings={"enabled": True}, log_callback=lambda message: print(str(message), flush=True),
            watermark_settings=cfg.get("watermark"), credit_watermark_settings=cfg.get("credit_watermark"))
        core.campaign_config = campaign
        core.source_analysis = {"source_id": original["source_id"], "path": str(source_path), "sha256": source_hash,
                                "url": project.get("url")}
        core.work_dir = destination / "work"
        core.work_dir.mkdir(exist_ok=True)
        core._caption_lock = threading.Lock()
        core.efficient_framing = True
        gpu = cfg.get("gpu_acceleration", {})
        enabled = gpu.get("enabled", False) if isinstance(gpu, dict) else bool(gpu)
        core.enable_gpu_acceleration(enabled)
        if core.gpu_enabled:
            core.framing_encoder_args = core.gpu_encoder_args
        core._whisper_transcribe_words = lambda _: shifted_transcript(source_words, highlight)
        job = {"campaign": campaign}
        music_selector = MusicSelector(api, cfg, Path(api.output_dir) / "_cache/music-selection")
        original_ask = music_selector.ask

        def tracked_ask(instruction, payload):
            stage = "ranking" if "candidates" in payload else "shortlist" if "tracks" in payload else "criteria"
            print(f"Custom2 musik: {stage} / xhigh", flush=True)
            try:
                return original_ask(instruction, payload)
            except Exception:
                report["music_failed_stage"] = stage
                raise

        music_selector.ask = tracked_ask
        api._select_background_sound = lambda transcript, title, hook, duration, campaign: music_selector.select(
            {"transcript": transcript, "title": title, "hook_text": hook, "duration_seconds": duration}, campaign)

        def select_music(metadata):
            print("Custom2: selector musik baru, katalog Repliz dan analisis audio kandidat.", flush=True)
            music = api._select_workflow_music(metadata, job, core.work_dir)
            selection = (music or {}).get("selection") or {}
            calls = selection.get("ai", {}).get("calls", [])
            if selection.get("fallback") or len(calls) != 3 or any(c["returned_model"] != "gpt-6.1-sol" for c in calls):
                raise ValueError("Tes musik harus lolos tiga tahap AI Custom2 tanpa fallback atau model pengganti.")
            report["music_selection"] = selection
            atomic_json(report_path, report)
            return music

        core.music_selector_callback = select_music
        full_transcript = (source_path.parent / "reviewed-source.srt").read_text(encoding="utf-8")
        if args.resume:
            rendered = destination / "clip-001"
            final = rendered / "master.mp4"
            plan = build_clip_plan(core.source_analysis, highlight, campaign, ffmpeg)
            metadata = copy.deepcopy(original)
            for key in ("clip_id", "revision_id", "caption", "captions", "job_id", "music", "audio_analysis", "final_sha256", "render_key"):
                metadata.pop(key, None)
            metadata.update(highlight=highlight, clip_plan=plan, template=plan["template"], campaign_snapshot=campaign,
                final_path=str(final), duration_seconds=probe_media(final, ffmpeg)["duration"],
                transcript=core.extract_transcript_for_highlight_from_text(full_transcript, highlight),
                render_key=config_hash({"test": str(destination), "highlight": highlight, "campaign": campaign}))
            camera_path = rendered / "camera.json"
            if camera_path.is_file():
                metadata["camera"] = {k: v for k, v in json.loads(camera_path.read_text(encoding="utf-8")).items() if k != "decisions"}
            music = select_music(metadata)
            mixed = rendered / "mixed.mp4"
            metadata["music"] = mix_music(final, music, mixed, ffmpeg)
            mixed.replace(final)
            metadata["audio_analysis"] = analyze_audio(final, ffmpeg)
            metadata["final_sha256"] = file_sha256(final)
            atomic_json(rendered / "data.json", metadata)
        else:
            rendered = core.process_clip(str(source_path), highlight, 1, total_clips=1, add_captions=True,
                add_hook=False, campaign_id=campaign["id"], full_transcript=full_transcript)
        metadata_path = rendered / "data.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["caption_transcript_provenance"] = {"kind": "shifted_source_word_times", "source_words_path": str(words_path),
            "source_sha256": source_hash, "model": source_words["model"], "source_start_time": highlight["start_time"]}
        metadata["test_provenance"] = {"provider": "Custom2", "requested_model": provider["model"],
            "returned_model": "gpt-6.1-sol", "reasoning_effort": "xhigh", "original_project": str(args.project.resolve()),
            "original_clip": choice["id"], "highlight_selection": copy.deepcopy(selector.ai_calls)}
        atomic_json(metadata_path, metadata)
        final = rendered / "master.mp4"
        media = probe_media(final, ffmpeg)
        if not media["has_video"] or not media["has_audio"] or not metadata["music"].get("mixed"):
            raise ValueError("Video atau audio final belum valid.")
        report.update(status="rendered", finished_at=utc_now(), final_path=str(final.resolve()),
            final_sha256=file_sha256(final), media=media, music=metadata["music"],
            audio_analysis=metadata["audio_analysis"], warnings=metadata["warnings"], blockers=metadata["blockers"])
        atomic_json(report_path, report)
        print(json.dumps({"status": report["status"], "video": str(final), "music": metadata["music"].get("attribution"),
                          "duration": media["duration"], "report": str(report_path)}, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        message = str(exc).replace(provider.get("api_key", "not-configured"), "[redacted]")
        report.update(status="failed", finished_at=utc_now(), error=message)
        if exc.__cause__:
            report["cause"] = str(exc.__cause__).replace(provider.get("api_key", "not-configured"), "[redacted]")
        chain = []
        cause = exc
        while cause and len(chain) < 6:
            chain.append({"type": type(cause).__name__, "status": getattr(cause, "status_code", None),
                "message": str(cause).replace(provider.get("api_key", "not-configured"), "[redacted]")[:1000]})
            cause = cause.__cause__
        report["error_chain"] = chain
        atomic_json(report_path, report)
        print(json.dumps({"status": "failed", "error": message, "cause": report.get("cause"), "report": str(report_path)}, ensure_ascii=False), flush=True)
        return 1
    finally:
        if core:
            core.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
