"""Run one campaign job without a window, with decisions supplied by this chat.

The normal source, evidence, speech, editing and storage pipeline still runs.
Requests/answers are local reviewable artifacts; this is not a model API alias.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from app import WebAPI
from services.campaigns import normalize_campaign, campaign_processing_options, campaign_version_record, resolve_editing_preset
from services.editing import fingerprint_source, file_sha256
from services.storage import atomic_json, utc_now
from services.storage import WorkflowStore, digest
from services.worker_lease import WorkerLease
from services.speech_boundaries import parse_cues, timestamp


class HeadlessAPI(WebAPI):
    """Own one isolated worker; an open desktop app keeps its own queue."""
    def __init__(self, cfg, directory):
        self.config_file = str(directory / "run-context.json")
        self.output_dir = cfg["output_dir"]
        self.status, self.progress = "idle", 0
        self.core = self.thread = self.current_job = None
        self.job_history = []
        self._get_cfg = lambda: cfg
        self._worker_lease = WorkerLease(directory / "worker.lock")
        self.worker_enabled = self._worker_lease.acquire()
        if not self.worker_enabled:
            raise RuntimeError("Run command ini sudah dikerjakan proses lain.")


class ChatDecisions:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.base_url = "local-chat-decisions"
        self.counter = 0
        self.lock = threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        with self.lock:
            self.counter += 1
            number = self.counter
        stem = f"request-{number:04d}"
        atomic_json(self.directory / (stem + ".json"), request)
        answer = self.directory / f"response-{number:04d}.json"
        print(f"AGENT_REQUEST {number} {self.directory / (stem + '.json')}", flush=True)
        deadline = time.monotonic() + 7200
        while time.monotonic() < deadline:
            if answer.is_file():
                try:
                    payload = json.loads(answer.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    time.sleep(.5)
                    continue
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                    content=json.dumps(payload, ensure_ascii=False)))], usage=None)
            time.sleep(.5)
        raise TimeoutError(f"Keputusan chat belum tersedia: {answer}")


def music_library(output):
    """Reuse downloaded tracks with their original attribution and hash."""
    result = {}
    for metadata_path in Path(output).glob("job-*/clip-*/data.json"):
        try:
            music = json.loads(metadata_path.read_text(encoding="utf-8")).get("music", {})
            attribution = music.get("attribution") or {}
            if (str(attribution.get("license_ccurl", "")).rstrip("/").endswith("/by/3.0")
                    and Path(music.get("path", "")).is_file()):
                result[str(attribution["id"])] = {"path": music["path"], "attribution": attribution}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--campaign", default="Timothy Ronald")
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--max-candidates", type=int, default=500)
    parser.add_argument("--workers", type=int, choices=range(1, 9), help="Jumlah render paralel untuk job ini")
    parser.add_argument("--candidate-plan", help="Keputusan highlight dari chat dalam file JSON")
    parser.add_argument("--selection-only", action="store_true", help="Berhenti setelah highlight divalidasi, sebelum render")
    parser.add_argument("--source-transcript", help="SRT sumber yang diperiksa dengan waktu ucapan lokal")
    parser.add_argument("--source-words", help="Waktu kata sumber untuk subtitle tanpa mengulang transkripsi tiap clip")
    parser.add_argument("--resume-job", help="Lanjutkan job command yang sebelumnya berhenti")
    parser.add_argument("--qsv-intermediate", action="store_true", help="Akselerasi Intel untuk potongan sementara sebelum editing")
    parser.add_argument("--qsv-encode", action="store_true", help="Akselerasi Intel kualitas 14 untuk encode FFmpeg, dengan fallback CPU")
    parser.add_argument("--efficient-framing", action="store_true", help="Decode sesuai kebutuhan resolusi hasil, tanpa mengurangi ukuran crop")
    parser.add_argument("--music-library", type=Path, help="Library lokal dengan manifest library.json")
    parser.add_argument("--music-volume", type=float, help="Gain musik untuk run ini; setting campaign tidak diubah")
    parser.add_argument("--music-no-ducking", action="store_true", help="Pertahankan fader musik saat ada dialog")
    args = parser.parse_args()
    directory = Path(args.decisions).resolve()
    if directory.exists() and list(directory.glob("request-*.json")):
        raise ValueError("Gunakan folder keputusan baru agar jawaban lama tidak tertukar.")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cfg["output_dir"] = str((ROOT / cfg["output_dir"]).resolve())
    matches = [c for c in cfg.get("campaigns", []) if args.campaign in (c.get("id"), c.get("name"))]
    if len(matches) != 1:
        raise ValueError("Campaign harus cocok dengan tepat satu nama atau ID.")
    campaign = normalize_campaign(copy.deepcopy(matches[0]))
    campaign["editing"]["review_mode"] = "manual"
    if args.workers is not None:
        campaign["editing"]["max_workers"] = args.workers
    if args.music_volume is not None:
        if not 0 < args.music_volume <= 2:
            raise ValueError("Gain musik harus lebih dari nol dan tidak melebihi 2.")
        campaign["editing"]["music"]["volume"] = args.music_volume
    if args.music_no_ducking:
        campaign["editing"]["music"]["ducking"] = False
    # Keep the saved campaign audience criteria authoritative for new jobs.
    snapshots = list((Path.home() / ".cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots").glob("*/model.bin"))
    if not snapshots:
        raise FileNotFoundError("Model Whisper lokal belum tersedia.")
    cfg["ai_providers"]["whisper_model"] = str(snapshots[-1].parent)
    cfg["max_highlights"] = args.max_candidates
    broker = ChatDecisions(directory)
    source_words = json.loads(Path(args.source_words).read_text(encoding="utf-8")) if args.source_words else None
    api = HeadlessAPI(cfg, directory)
    if args.music_library:
        from tools.run_headless_campaign import load_library
        library = {track["tiktok_music_id"]: {"path": track["path"], "attribution": {
            "id": track["tiktok_music_id"], "name": track["title"], "artist": track["creator"],
            "source_url": track["source_url"], "license_ccurl": None}, "usage_rights_status": "not_verified"}
            for track in load_library(args.music_library)}
    else:
        library = music_library(api.output_dir)
    if not library:
        raise ValueError("Tidak ada file musik terverifikasi dari library yang dipilih.")
    atomic_json(directory / "music-library.json", library)
    original_configure = api._configure_workflow_core

    def configure(core):
        original_configure(core)
        core.efficient_framing = args.efficient_framing
        if args.qsv_encode:
            core.framing_encoder_args = ["-c:v", "h264_qsv", "-global_quality", "14"]
        if args.qsv_intermediate or args.qsv_encode:
            original_ffmpeg = core._run_ffmpeg_subprocess
            def intermediate_ffmpeg(command, **options):
                command = list(command)
                if "libx264" in command and (args.qsv_encode or str(command[-1]).endswith("temp_landscape.mp4")):
                    rewritten, i = [], 0
                    while i < len(command):
                        if command[i] == "-c:v" and command[i+1] == "libx264":
                            rewritten += ["-c:v","h264_qsv"]
                            i += 2
                        elif command[i] in ("-crf","-preset"):
                            i += 2
                        else:
                            rewritten.append(command[i]); i += 1
                    quality = "14" if args.qsv_encode else "16"
                    rewritten[-1:-1] = ["-global_quality",quality]
                    core.log(f"Encode: akselerasi Intel Quick Sync, kualitas {quality}.")
                    command = rewritten
                return original_ffmpeg(command, **options)
            core._run_ffmpeg_subprocess = intermediate_ffmpeg
        original_process = core.process
        core.process = lambda *values, **options: original_process(*values, **options, plan_only=args.selection_only)
        original_cache = Path(core.work_dir)
        core.work_dir = directory / "source"
        core.work_dir.mkdir(parents=True, exist_ok=True)
        cached_file = original_cache / "analysis.json"
        if cached_file.is_file():
            cached = json.loads(cached_file.read_text(encoding="utf-8"))
            source_path = Path(cached.get("video_path", ""))
            if cached.get("source_id") == core.expected_source_id and source_path.is_file():
                target = core.work_dir / "source.mp4"
                shutil.copy2(source_path, target)
                cues = parse_cues(cached.get("transcript", ""))
                if cues:
                    # This is a real prior source transcript, not a new ASR result.
                    srt = "\n\n".join(f"{i}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
                                       for i, cue in enumerate(cues, 1)) + "\n"
                    (core.work_dir / "source.srt").write_text(srt, encoding="utf-8")
                    atomic_json(directory / "transcript-provenance.json", {
                        "kind": "reused_source_transcript", "source_id": cached["source_id"],
                        "previous_analysis": str(cached_file), "transcript_digest": digest(cached["transcript"])})
                atomic_json(core.work_dir / "analysis.json", {
                    "video_path": str(target), "video_info": cached.get("video_info", {})})
        if args.source_transcript:
            source_transcript = Path(args.source_transcript).resolve()
            if not source_transcript.is_file():
                raise FileNotFoundError(source_transcript)
            shutil.copy2(source_transcript, core.work_dir / "source.srt")
            atomic_json(directory / "transcript-provenance.json", {
                "kind": "reviewed_local_source_word_transcript", "source_id": core.expected_source_id,
                "transcript_path": str(source_transcript), "transcript_file_digest": digest(source_transcript.read_text(encoding="utf-8")),
                "word_time_method": "local_faster_whisper_large_v3_turbo"})
        if source_words:
            if (not source_words.get("source_sha256")
                    or file_sha256(core.work_dir / "source.mp4") != source_words["source_sha256"]):
                raise ValueError("Waktu kata tidak berasal dari file sumber run ini.")
            local = threading.local()
            original_clip = core.process_clip
            original_finalize = core.finalize_callback
            concurrency_lock = threading.Lock()
            concurrency = {"configured_workers": campaign["editing"]["max_workers"],
                           "active": 0, "peak_active": 0, "finished": 0}

            def process_clip(video, highlight, *values, **options):
                preset_id = (highlight.get("editing_template") or {}).get("preset_id") or campaign["editing"].get("preset_id")
                if resolve_editing_preset(preset_id)["features"].get("add_hook"):
                    raise ValueError("Waktu subtitle sumber tidak mendukung hook tambahan.")
                with concurrency_lock:
                    concurrency["active"] += 1
                    concurrency["peak_active"] = max(concurrency["peak_active"], concurrency["active"])
                    atomic_json(directory / "render-concurrency.json", concurrency)
                local.highlight = highlight
                try:
                    return original_clip(video, highlight, *values, **options)
                finally:
                    local.highlight = None
                    with concurrency_lock:
                        concurrency["active"] -= 1
                        concurrency["finished"] += 1
                        atomic_json(directory / "render-concurrency.json", concurrency)

            def caption_words(audio):
                highlight = getattr(local, "highlight", None)
                if not highlight or campaign["editing"].get("segments") or campaign["editing"].get("endcard", {}).get("path"):
                    raise ValueError("Subtitle sumber hanya tersedia untuk potongan sumber tanpa sisipan.")
                start, end = (core.parse_timestamp(highlight[key]) for key in ("start_time", "end_time"))
                words, segments = [], []
                for segment in source_words["segments"]:
                    selected = [w for w in segment.get("words", []) if w["end"] > start and w["start"] < end and w["end"] > w["start"]]
                    if selected:
                        shifted = [SimpleNamespace(word=w["word"], start=max(0, w["start"]-start), end=min(end-start,w["end"]-start)) for w in selected]
                        words.extend(shifted)
                        segments.append({"start":shifted[0].start,"end":shifted[-1].end,"text":"".join(w.word for w in shifted).strip()})
                if not words:
                    raise ValueError("Tidak ada waktu kata teramati untuk clip ini.")
                core.log(f"Subtitle: memakai {len(words)} waktu kata dari transkripsi sumber yang sama.")
                return SimpleNamespace(words=words,segments=segments,text=" ".join(s["text"] for s in segments))

            def finalize(clip_directory, metadata):
                metadata["caption_transcript_provenance"] = {"kind":"shifted_source_word_times",
                    "source_words_path":str(Path(args.source_words).resolve()), "source_sha256":source_words["source_sha256"],
                    "model":source_words["model"], "source_start_time":metadata["start_time"]}
                return original_finalize(clip_directory, metadata)

            core.process_clip, core._whisper_transcribe_words, core.finalize_callback = process_clip, caption_words, finalize
            core.caption_parallel_safe = True
        core.highlight_client = broker
        core.model = "decisions-by-current-Codex-chat"
        core.local_whisper_settings.update(device="cpu", compute_type="int8")
        original_log = core.log

        def log(message):
            print(str(message), flush=True)
            original_log(message)

        core.log = log

        def soundtrack(metadata):
            identifier = str(metadata["highlight"].get("agent_music_id", ""))
            if identifier not in library:
                raise ValueError("Keputusan musik belum mencantumkan track dari library run ini.")
            return {**campaign["editing"]["music"], **copy.deepcopy(library[identifier]),
                    "start_seconds": metadata["highlight"].get("agent_music_start", 0), "required": True,
                    "selection": {"catalog": "local_library" if args.music_library else "cached_cc_by",
                        "decision_source": "current_codex_chat", "verified_remote_model": None,
                        "reason": metadata["highlight"].get("agent_music_reason", "Keputusan musik dari chat"),
                        "analysis_scope": "transcript_and_signal_only_not_audio_listening",
                        "review_required": True, "fallback": False}}

        core.music_selector_callback = soundtrack

    api._configure_workflow_core = configure
    try:
        store = api._get_store()
        resumed = store.get("job",args.resume_job) if args.resume_job else None
        if args.resume_job and not resumed:
            raise ValueError("Job yang akan dilanjutkan tidak ditemukan di folder run ini.")
        if resumed:
            if resumed["source"] != args.source:
                raise ValueError("Sumber resume berbeda dari job tersimpan.")
            campaign = copy.deepcopy(resumed["campaign"])
        readiness = api._campaign_readiness(campaign)
        if not readiness["production_ready"]:
            raise ValueError("; ".join(readiness["production_blockers"]))
        version = campaign_version_record(campaign)
        campaign["version_id"] = version["id"]
        store.put("campaign_version", version["id"], version)
        identity = fingerprint_source(args.source)
        job_id = resumed["id"] if resumed else "job_" + uuid.uuid4().hex
        job = {"id": job_id, "source": args.source, "source_id": identity["source_id"],
               "campaign_id": campaign["id"], "campaign": campaign,
               "options": campaign_processing_options(campaign, 0), "title": "Memuat judul…",
               "title_status": "pending", "status": "running", "step": "Memulai via command",
               "clips": [], "logs": [], "progress": 0, "created_at": utc_now(),
               "started_at": utc_now(), "error": None,
               "execution": {"interface": "command", "decision_source": "current_codex_chat",
                   "requested_model": "gpt-6.1-sol", "requested_reasoning_effort": "xhigh",
                   "verified_remote_model": None, "max_candidates": args.max_candidates}}
        if resumed:
            job = {**resumed,"status":"running","error":None,"finished_at":None,"step":"Melanjutkan via command"}
            job["execution"]["resume_count"] = job["execution"].get("resume_count",0)+1
        elif args.candidate_plan:
            selected = json.loads(Path(args.candidate_plan).read_text(encoding="utf-8"))
            job["highlight_overrides"] = selected["highlights"] if isinstance(selected, dict) else selected
        job["execution"]["qsv_intermediate"] = bool(args.qsv_intermediate)
        job["execution"]["qsv_encode"] = bool(args.qsv_encode)
        job["execution"]["efficient_framing"] = bool(args.efficient_framing)
        job["execution"]["render_workers"] = campaign["editing"]["max_workers"]
        store.put("job", job_id, job)
        atomic_json(directory / "run.json", {"job_id": job_id, "source": args.source,
                    "campaign_id": campaign["id"], "execution": job["execution"]})
        print(f"JOB {job_id}", flush=True)
        api._execute_job(job)
        result = store.get("job", job_id)
        if args.selection_only and result["status"] == "completed":
            plan_path = Path(cfg["output_dir"]) / ("job-" + job_id.removeprefix("job_")[:16]) / "highlights.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            result.update(status="awaiting_render_approval", step="Menunggu pilihan render", progress=.4,
                          planned_clip_count=len(plan["highlights"]), highlight_plan=str(plan_path))
            store.put("job", job_id, result)
        atomic_json(directory / "result.json", result)
        if not args.selection_only:
            destination = WorkflowStore(ROOT / "workflow.sqlite3")
            destination.put("campaign_version", version["id"], version)
            for clip in store.list("clip"):
                destination.put("clip", clip["id"], clip)
                destination.put("clip_revision", clip["revision_id"], clip)
            destination.put("job", job_id, result)
        print(json.dumps({"job_id": job_id, "status": result["status"], "error": result.get("error"),
                          "clips": len(result.get("clips", [])), "planned_clips": result.get("planned_clip_count")}, ensure_ascii=False), flush=True)
        return 0 if result["status"] in ("completed", "awaiting_render_approval") else 1
    finally:
        if api.core:
            api.core.cleanup()
        api._worker_lease.close()


if __name__ == "__main__":
    raise SystemExit(main())
