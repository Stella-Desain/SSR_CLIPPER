"""Replace test music using real Custom2 selection, preserving picture and dry voice."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from app import WebAPI
from services.editing import _run, analyze_audio, config_hash, file_sha256, mix_music, probe_media
from services.music_selection import MusicSelector
from services.music_review import verify_music_balance
from services.music_audio import provider_error_details
from services.storage import atomic_json, utc_now
from utils.helpers import get_ffmpeg_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "output/_tests/music-custom2-36f27b1a99")
    parser.add_argument("--volume", type=float, default=.65)
    args = parser.parse_args()
    if not 0 < args.volume <= 2:
        parser.error("Volume harus lebih dari 0 dan maksimal 2.")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    provider = cfg["ai_providers"]["highlight_finder"]
    custom2 = cfg["ai_providers"]["custom_provider"]
    if (provider.get("model") != "Codex-6.1sol" or not provider.get("api_key")
            or provider.get("base_url") != custom2.get("base_url") or provider["api_key"] != custom2.get("api_key")):
        raise ValueError("Highlight Finder harus memakai [Custom2] Codex-6.1sol.")
    cfg = copy.deepcopy(cfg)
    cfg["ai_providers"]["highlight_finder"]["reasoning_effort"] = "xhigh"
    output = Path(cfg.get("output_dir") or ROOT / "output").resolve()
    base = args.base.resolve()
    if not base.is_relative_to(output / "_tests"):
        raise ValueError("Video dasar harus berada di output/_tests.")
    prior = json.loads((base / "test-report.json").read_text(encoding="utf-8"))
    if prior.get("status") != "rendered":
        raise ValueError("Video dasar belum berhasil dirender.")
    project = Path(prior["project"])
    if len(list(project.glob("clip-*/data.json"))) != 51:
        raise ValueError("Project sumber harus memiliki 51 clip.")
    metadata = json.loads((base / "clip-001/data.json").read_text(encoding="utf-8"))
    dry_voice = base / "clip-001/temp_portrait.mp4"
    picture = base / "clip-001/master.mp4"
    ffmpeg = get_ffmpeg_path()
    duration = probe_media(picture, ffmpeg)["duration"]
    if not dry_voice.is_file() or abs(probe_media(dry_voice, ffmpeg)["duration"] - duration) > .1:
        raise ValueError("Suara asli yang belum dicampur musik tidak tersedia atau berbeda durasi.")
    destination = output / "_tests" / ("music-viral-custom2-" + uuid.uuid4().hex[:10])
    clip = destination / "clip-001"
    clip.mkdir(parents=True)
    report_path = destination / "test-report.json"
    report = {"status": "started", "started_at": utc_now(), "base_test": str(base),
        "project": str(project), "original_clip": prior["original_clip"],
        "highlight_title": prior["highlight_title"], "highlight_ai_calls": prior["highlight_ai_calls"],
        "provider": "Custom2", "requested_model": provider["model"], "reasoning_effort": "xhigh",
        "production_clips_modified": False, "config_changed": False, "published": False}
    atomic_json(report_path, report)
    try:
        dry = clip / "dry.mp4"
        _run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(picture), "-i", str(dry_voice),
            "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-t", str(duration), str(dry)])
        shutil.copyfile(dry_voice, clip / "temp_portrait.mp4")
        campaign = copy.deepcopy(metadata["campaign_snapshot"])
        campaign["editing"]["review_mode"] = "manual"
        campaign["editing"]["music"].update(policy="auto", path="", catalog="repliz", volume=args.volume,
            ducking=True, fade_seconds=.4, reference_style="reference_clips",
            style_brief="Gunakan karakter bunyi dalam profil Reflektif / Action sesuai cerita klip. "
                "Untuk refleksi/hard truth, prioritaskan melodi sendu piano atau gitar dan vokal lirih bila cocok. "
                "Untuk ajakan bertindak, cari beat stabil dengan vocal chop bila cocok. "
                "Lagu bervokal diperbolehkan; pilih berdasarkan audio nyata, bukan identitas judul.")
        campaign["editing"]["music"].pop("source_path", None)
        metadata["campaign_snapshot"] = campaign
        metadata["duration_seconds"] = duration
        api = WebAPI.__new__(WebAPI)
        api.output_dir = str(output)
        api._get_cfg = lambda: cfg
        selector = MusicSelector(api, cfg, output / "_cache/music-selection")
        analyze = selector.audio_analyzer.analyze
        def tracked_audio(path, *args, **kwargs):
            print("Visual-AI: " + Path(path).name, flush=True)
            try:
                result = analyze(path, *args, **kwargs)
            except Exception as exc:
                failure = {"file": Path(path).name, **provider_error_details(exc)}
                report.setdefault("audio_errors", []).append(failure)
                atomic_json(report_path, report)
                print("Audio gagal: " + json.dumps(failure), flush=True)
                raise
            print("Audio profile: " + str(result["provenance"].get("returned_model")) +
                  (" / cached" if result["cache_hit"] else " / new"), flush=True)
            return result
        selector.audio_analyzer.analyze = tracked_audio
        ask = selector.ask

        def tracked_ask(instruction, payload):
            stage = "ranking" if "candidates" in payload else "shortlist" if "tracks" in payload else "criteria"
            print(f"Custom2 musik viral: {stage} / xhigh", flush=True)
            result = ask(instruction, payload)
            report.setdefault("stages", {})[stage] = result
            atomic_json(report_path, report)
            return result

        selector.ask = tracked_ask
        api._select_background_sound = lambda transcript, title, hook, seconds, campaign: selector.select(
            {"transcript": transcript, "title": title, "hook_text": hook, "duration_seconds": seconds}, campaign)
        music = api._select_workflow_music(metadata, {"campaign": campaign}, destination / "work")
        selection = music["selection"]
        report["music_selection"] = selection
        atomic_json(report_path, report)
        calls = selection.get("ai", {}).get("calls", [])
        if selection.get("fallback") or len(calls) != 3 or any(call["returned_model"] != "gpt-6.1-sol" for call in calls):
            raise ValueError("Ketiga tahap AI harus memakai Custom2 gpt-6.1-sol tanpa fallback.")
        final = clip / "master.mp4"
        clean = clip / "master_without_music.mp4"
        shutil.copyfile(dry, clean)
        metadata["dry_master"] = {"path": str(clean), "sha256": file_sha256(clean)}
        metadata["music"] = mix_music(dry, music, final, ffmpeg)
        metadata["music_balance"] = verify_music_balance(dry, final, metadata["music"], ffmpeg)
        metadata.update(final_path=str(final), final_sha256=file_sha256(final),
            audio_analysis=analyze_audio(final, ffmpeg),
            render_key=config_hash({"test": str(destination), "music": metadata["music"]}))
        metadata["test_provenance"].update(base_test=str(base), music_replaced=True)
        atomic_json(clip / "data.json", metadata)
        report.update(status="rendered", finished_at=utc_now(), final_path=str(final),
            final_sha256=metadata["final_sha256"], media=probe_media(final, ffmpeg), music=metadata["music"],
            audio_analysis=metadata["audio_analysis"])
        report["music_balance"] = metadata["music_balance"]
        atomic_json(report_path, report)
        print(json.dumps({"status": "rendered", "video": str(final), "music": music["attribution"],
            "mixing": metadata["music"]["mixing"], "report": str(report_path)}, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        report.update(status="failed", finished_at=utc_now(),
            error=str(exc).replace(provider["api_key"], "[redacted]"))
        atomic_json(report_path, report)
        print(json.dumps({"status": "failed", "error": report["error"], "report": str(report_path)}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
