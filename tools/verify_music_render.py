"""Decode a test render and check voice plus the selected music's signal."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import bounded_ffmpeg_command, file_sha256, probe_media
from services.storage import atomic_json
from utils.helpers import get_ffmpeg_path


def run(command):
    return subprocess.run(bounded_ffmpeg_command(command), capture_output=True, timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def pcm(ffmpeg, inputs, duration, filters=None):
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", *inputs, "-t", str(duration), "-vn"]
    if filters:
        command += ["-af", filters]
    result = run(command + ["-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"])
    if result.returncode:
        raise ValueError("Decode audio untuk verifikasi gagal.")
    return np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)


def aligned(reference, result, lag):
    rstart, ystart = max(0, -lag), max(0, lag)
    length = min(len(reference) - rstart, len(result) - ystart)
    return reference[rstart:rstart + length], result[ystart:ystart + length]


def correlation(a, b):
    return float(np.dot(a, b) / max(1e-20, np.sqrt(np.dot(a, a) * np.dot(b, b))))


def signal_evidence(voice, bed, mixed):
    length = min(len(voice), len(bed), len(mixed))
    voice, bed, mixed = voice[:length], bed[:length], mixed[:length]
    if not length or not all(np.isfinite(item).all() for item in (voice, bed, mixed)):
        raise ValueError("Sampel untuk pemeriksaan komponen audio tidak valid.")
    coefficients, _, rank, _ = np.linalg.lstsq(np.column_stack((voice, bed)), mixed, rcond=None)
    if rank != 2:
        raise ValueError("Sinyal referensi suara dan musik tidak dapat dibedakan.")
    voice_gain, music_gain = map(float, coefficients)
    voice_signal, music_signal = voice_gain * voice, music_gain * bed
    voice_rms = float(np.sqrt(np.mean(voice_signal ** 2)))
    music_rms = float(np.sqrt(np.mean(music_signal ** 2)))
    voice_correlation = correlation(voice, mixed - music_signal)
    music_correlation = correlation(bed, mixed - voice_signal)
    noise = mixed - voice_signal - music_signal
    fit = 1 - float(np.dot(noise, noise) / max(1e-20, np.dot(mixed, mixed)))
    return {"voice_correlation": round(voice_correlation, 5), "voice_gain": round(voice_gain, 5),
        "raw_voice_mix_correlation": round(correlation(voice, mixed), 5),
        "selected_music_residual_correlation": round(music_correlation, 5),
        "estimated_music_gain": round(music_gain, 5), "estimated_music_signal_rms": round(music_rms, 7),
        "estimated_music_to_voice_db": round(float(20 * np.log10(max(music_rms, 1e-20) / max(voice_rms, 1e-20))), 2),
        "joint_fit_r2": round(fit, 5), "voice_present": voice_gain > .1 and voice_correlation > .8,
        "selected_music_present": music_gain > 0 and music_correlation > .05 and music_rms > 1e-5,
        "method": "aligned_pcm_joint_voice_and_music_projection", "sample_rate": 8000,
        "scope": "signal evidence, not a perceptual or musical-quality rating"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", type=Path)
    parser.add_argument("--min-music-db", type=float, help="Minimum estimated music RMS relative to voice, e.g. -14")
    parser.add_argument("--max-music-db", type=float, help="Maximum estimated music RMS relative to voice, e.g. -8")
    args = parser.parse_args()
    clip = args.clip.resolve()
    metadata = json.loads((clip / "data.json").read_text(encoding="utf-8"))
    ffmpeg = get_ffmpeg_path()
    final = clip / "master.mp4"
    media = probe_media(final, ffmpeg)
    duration = media["duration"]
    decoded = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(final), "-f", "null", "-"])
    if decoded.returncode or decoded.stderr.strip():
        raise ValueError("Video final memiliki error decode.")
    base = Path(metadata.get("dry_master", {}).get("path") or clip / "temp_portrait.mp4")
    if metadata.get("dry_master") and file_sha256(base) != metadata["dry_master"]["sha256"]:
        raise ValueError("Master referensi tanpa musik berubah.")
    source = metadata["clip_plan"]["segments"][0]
    voice_inputs = ["-i", str(base)] if base.is_file() else ["-ss", str(source["start_seconds"]), "-i", source["path"]]
    voice = pcm(ffmpeg, voice_inputs, duration)[8000:-8000]
    mixed = pcm(ffmpeg, ["-i", str(final)], duration)[8000:-8000]
    best_lag = max(range(-80, 81), key=lambda lag: correlation(*aligned(voice, mixed, lag)))
    voice, mixed = aligned(voice, mixed, best_lag)
    gain = float(np.dot(voice, mixed) / max(1e-20, np.dot(voice, voice)))
    residual = mixed - gain * voice
    music = metadata["music"]
    music_level = music.get("mixing", {}).get("normalization_lufs", -20)
    bed = pcm(ffmpeg, ["-stream_loop", "-1", "-ss", str(music["start_seconds"]), "-t", str(duration),
        "-i", music["path"]], duration, f"aresample=48000,loudnorm=I={music_level}:TP=-2:LRA=11")[8000:-8000]
    bed = bed[max(0, -best_lag):max(0, -best_lag) + len(residual)]
    music_lag = max(range(-80, 81), key=lambda lag: correlation(*aligned(bed, residual, lag)))
    bed_start, signal_start = max(0, -music_lag), max(0, music_lag)
    evidence = signal_evidence(voice[signal_start:], bed[bed_start:], mixed[signal_start:])
    evidence["voice_alignment_ms"] = best_lag / 8
    evidence["music_alignment_ms"] = music_lag / 8
    relative_db = evidence["estimated_music_to_voice_db"]
    frames = []
    for index, at in enumerate((2, duration / 2, max(0, duration - 2)), 1):
        frame = clip / f"check-frame-{index}.jpg"
        result = run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(final),
            "-frames:v", "1", "-vf", "scale=720:-2", "-q:v", "2", str(frame)])
        if result.returncode or not frame.is_file():
            raise ValueError("Frame hasil tidak dapat diperiksa.")
        frames.append({"seconds": at, "path": str(frame)})
    report = {"decode_ok": True, "final_sha256": file_sha256(final), "media": media, "audio_signal": evidence, "frames": frames,
              "passed": evidence["voice_present"] and evidence["selected_music_present"]}
    if args.min_music_db is not None:
        report["music_level_check"] = {"minimum_db": args.min_music_db, "passed": relative_db >= args.min_music_db}
        report["passed"] = report["passed"] and report["music_level_check"]["passed"]
    if args.max_music_db is not None:
        report["music_ceiling_check"] = {"maximum_db": args.max_music_db, "passed": relative_db <= args.max_music_db}
        report["passed"] = report["passed"] and report["music_ceiling_check"]["passed"]
    atomic_json(clip / "verification.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
