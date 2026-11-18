"""Deterministic campaign editing plans, local media analysis and FFmpeg rendering.

This module has no AI or network side effects. A plan records decisions before the
renderer executes them; required assets and ratio violations fail explicitly.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ANALYSIS_VERSION = 1
RENDER_VALIDATION_VERSION = 1
TEMPLATES = {
    "clean": {"id": "clean", "version": 1, "name": "Clean", "subtitle_style": "minimal", "framing": "speaker", "description": "Readable white subtitles, restrained visual treatment."},
    "social": {"id": "social", "version": 1, "name": "Social", "subtitle_style": "capcut", "framing": "speaker", "description": "Word emphasis for dialogue and short social clips."},
    "bold": {"id": "bold", "version": 1, "name": "Bold", "subtitle_style": "hormozi", "framing": "speaker", "description": "Large high contrast subtitles for energetic clips."},
    "podcast_square": {"id": "podcast_square", "version": 1, "name": "Podcast Kotak",
        "subtitle_style": "podcast_square", "framing": "speaker",
        "canvas": {"width": 720, "height": 720, "fps": 30},
        "description": "Video kotak dengan sudut membulat dan subtitle kapital satu kata di tengah."},
    "timothy_focus": {"id": "timothy_focus", "version": 1, "name": "Tegas 4:3",
        "subtitle_style": "timothy_focus", "framing": "speaker", "canvas": {"width": 1440, "height": 1080, "fps": 30},
        "description": "Pembicara di kiri, vignette gelap, subtitle kapital di kanan atas."},
    "timothy_cinematic": {"id": "timothy_cinematic", "version": 1, "name": "Sinematik 16:9",
        "subtitle_style": "timothy_cinematic", "framing": "speaker", "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "description": "B-roll campaign bergantian dengan pembicara, warna hangat, teks bertingkat dan aksen oranye."},
    "ruang_founder": {"id": "ruang_founder", "version": 1, "name": "Ruang · Founder Story",
        "subtitle_style": "ruang_founder", "framing": "speaker", "canvas": {"width": 1080, "height": 1920, "fps": 30},
        "description": "Hook putih-merah, monolog, B-roll resmi, vignette dan subtitle kapital satu kata."},
    "ruang_witness": {"id": "ruang_witness", "version": 1, "name": "Ruang · Witness Proof",
        "subtitle_style": "ruang_witness", "framing": "speaker", "canvas": {"width": 1080, "height": 1920, "fps": 30},
        "description": "Interview/testimoni dengan montage B-roll lebih rapat dan gaya putih-merah."},
}


class EditingValidationError(ValueError):
    pass


def list_templates():
    return copy.deepcopy(list(TEMPLATES.values()))


def resolve_template(template_id="social"):
    if template_id not in TEMPLATES:
        raise EditingValidationError(f"Unknown editing template: {template_id}")
    return copy.deepcopy(TEMPLATES[template_id])


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.stem + "-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def fingerprint_source(source):
    """Content hashes for local inputs, global provider identities for remote ones."""
    value = str(source)
    path = Path(value)
    if not value.startswith(("https://", "http://")) and path.is_file():
        digest = file_sha256(path)
        return {"source_id": "sha256:" + digest, "sha256": digest, "kind": "local", "path": str(path.resolve())}
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host == "youtube.com":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if not video_id and parsed.path.startswith(("/shorts/", "/live/", "/embed/")):
            video_id = parsed.path.split("/")[2]
    if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise EditingValidationError("Select an existing local video or a valid YouTube video URL.")
    return {"source_id": "youtube:" + video_id, "sha256": None, "kind": "youtube", "url": f"https://www.youtube.com/watch?v={video_id}"}


def bounded_workers(requested=None, cpu_count=None):
    capacity = max(1, min(4, (cpu_count or os.cpu_count() or 2) // 2))
    if requested in (None, ""):
        return capacity
    return max(1, min(8, int(requested), max(1, cpu_count or os.cpu_count() or 2)))


def bounded_ffmpeg_command(command):
    """Bound codec and filter workers for concurrent clips, especially 4K input."""
    if not command or Path(command[0]).stem.casefold() != "ffmpeg":
        return list(command)
    result = [command[0], "-filter_threads", "1", "-filter_complex_threads", "1"]
    for argument in command[1:]:
        if argument == "-i":
            result.extend(["-threads", "2"])
        result.append(argument)
    result[-1:-1] = ["-threads", "2"]
    return result


def _run(command, timeout=1800):
    result = subprocess.run(bounded_ffmpeg_command(command), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise EditingValidationError(f"Media processing failed: {result.stderr[-1800:]}")
    return result


def probe_media(path, ffmpeg_path="ffmpeg"):
    path = Path(path)
    if not path.is_file():
        raise EditingValidationError(f"Media file is missing: {path.name}")
    sibling = Path(ffmpeg_path).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    probe = str(sibling) if sibling.is_file() else shutil.which("ffprobe")
    if not probe:
        # Packaged installations sometimes ship FFmpeg alone. Its metadata output
        # is sufficient for the checks required by this renderer.
        result = subprocess.run([str(ffmpeg_path), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=30)
        text = result.stderr
        duration = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
        video = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", text)
        fps = re.search(r"([\d.]+) fps", text)
        if not duration and not video:
            raise EditingValidationError(f"Cannot inspect media: {path.name}")
        return {"duration": sum(float(v) * factor for v, factor in zip(duration.groups(), (3600, 60, 1))) if duration else 0,
                "width": int(video[1]) if video else 0, "height": int(video[2]) if video else 0,
                "fps": float(fps[1]) if fps else 0, "has_audio": "Audio:" in text, "has_video": bool(video)}
    data = json.loads(_run([probe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], timeout=30).stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    def frame_rate(key):
        rate = video.get(key, "0/1").split("/")
        return float(rate[0]) / float(rate[1]) if len(rate) == 2 and float(rate[1]) else 0
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    rotation = next((float(item["rotation"]) for item in video.get("side_data_list", []) if "rotation" in item), 0)
    if round(rotation) % 180 == 90:
        width, height = height, width
    container_duration = float(data.get("format", {}).get("duration") or 0)
    video_duration = float(video.get("duration") or container_duration)
    return {"duration": video_duration if video else container_duration, "container_duration": container_duration,
            "width": width, "height": height, "fps": frame_rate("avg_frame_rate"), "nominal_fps": frame_rate("r_frame_rate"),
            "has_video": bool(video), "has_audio": any(s.get("codec_type") == "audio" for s in streams)}


def validate_render_canvas(media, canvas, stage="Render"):
    """Reject a wrong canvas before a render can be finalized or reused."""
    expected = (int(canvas["width"]), int(canvas["height"]))
    actual = (int(media.get("width") or 0), int(media.get("height") or 0))
    if min(expected) <= 0:
        raise EditingValidationError("Ukuran kanvas template tidak valid.")
    if not media.get("has_video") or float(media.get("duration") or 0) <= 0:
        raise EditingValidationError(f"{stage} tidak memiliki video valid.")
    if actual != expected:
        raise EditingValidationError(
            f"{stage}: kanvas {actual[0]} × {actual[1]} tidak sesuai "
            f"{expected[0]} × {expected[1]}. Hasil belum dapat dinyatakan selesai.")
    return {"version": RENDER_VALIDATION_VERSION, "status": "passed",
            "canvas": {"width": expected[0], "height": expected[1]}}


def analyze_audio(path, ffmpeg_path="ffmpeg", media_info=None):
    """Measure the encoded final audio without rewriting the reviewed video.

    loudnorm's *input* values describe the existing mix, not its normalized
    output. Silence and measurements below the loudness gate remain null so
    metadata is strict JSON and unavailable data never looks like 0 LUFS.
    """
    analysis = {"version": 1, "method": "ffmpeg_loudnorm_input", "status": "unavailable",
                "integrated_lufs": None, "true_peak_dbtp": None, "loudness_range_lu": None,
                "warnings": []}
    try:
        media = media_info if media_info is not None else probe_media(path, ffmpeg_path)
        if not media["has_audio"]:
            analysis.update(status="no_audio", warnings=["Video final tidak memiliki track audio. Periksa apakah sesuai brief."])
            return analysis
        duration = _number(media["duration"], "Audio analysis duration", minimum=.001)
        result = _run([str(ffmpeg_path), "-hide_banner", "-nostats", "-i", str(path),
                       "-map", "0:a:0", "-vn", "-sn", "-dn", "-af",
                       f"atrim=duration={duration},loudnorm=print_format=json", "-f", "null", "-"], timeout=180)
        # FFmpeg writes diagnostic logs and the measurement object to stderr.
        measurements = [json.loads(block) for block in re.findall(r"\{[^{}]*\}", result.stderr)
                        if '"input_i"' in block]
        if not measurements:
            raise EditingValidationError("FFmpeg tidak mengembalikan hasil pengukuran audio.")
        measured = measurements[-1]
        values = {target: float(measured[source]) for target, source in (
            ("integrated_lufs", "input_i"), ("true_peak_dbtp", "input_tp"), ("loudness_range_lu", "input_lra"))}
        analysis.update({key: value if math.isfinite(value) else None for key, value in values.items()})
        analysis.update(status="measured", duration_seconds=duration)
        if values["true_peak_dbtp"] == -math.inf:
            analysis.update(status="silent", warnings=["Track audio final tidak memiliki sinyal yang terukur. Periksa suara pada preview."])
        elif not math.isfinite(values["true_peak_dbtp"]):
            raise EditingValidationError("Puncak audio tidak dapat diukur.")
        elif values["true_peak_dbtp"] >= 0:
            analysis["warnings"].append("Puncak audio mencapai 0 dBTP atau lebih; periksa distorsi dan turunkan level mix bila perlu.")
    except (EditingValidationError, OSError, subprocess.TimeoutExpired, TypeError, ValueError, KeyError) as exc:
        analysis.update(status="unavailable", integrated_lufs=None, true_peak_dbtp=None, loudness_range_lu=None,
                        error=str(exc)[:2000], warnings=["Pengukuran audio belum tersedia. Dengarkan hasil final sebelum menyetujui clip."])
    return analysis


def _number(value, name, minimum=0, maximum=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise EditingValidationError(f"{name} must be a number.") from None
    if not math.isfinite(result) or result < minimum or (maximum is not None and result > maximum):
        raise EditingValidationError(f"{name} is outside the supported range.")
    return result


def timestamp_seconds(value):
    if isinstance(value, (int, float)):
        return _number(value, "Timestamp")
    parts = str(value).replace(",", ".").split(":")
    if len(parts) != 3:
        raise EditingValidationError("Timestamps must use HH:MM:SS format.")
    return _number(parts[0], "Hours") * 3600 + _number(parts[1], "Minutes", maximum=59) * 60 + _number(parts[2], "Seconds", maximum=59.999999)


def _asset_path(asset):
    return asset.get("path") or asset.get("source_path") or ""


def endcard_settings(campaign):
    """A closing asset is optional unless the campaign or its manifest requires it."""
    editing = campaign.get("editing") or {}
    endcard = copy.deepcopy(editing.get("endcard") or {})
    endcard["path"] = endcard.get("path") or editing.get("endcard_path") or ""
    endcard["required"] = bool(endcard.get("required") or editing.get("endcard_required")
                               or (campaign.get("rules") or {}).get("endcard_required"))
    assets = [a for a in campaign.get("assets") or [] if a.get("role") == "endcard"]
    required = next((a for a in assets if a.get("required")), None)
    selected = required or (next(iter(assets), None) if not endcard["path"] else None)
    if selected:
        endcard.update(path=_asset_path(selected), asset_id=selected.get("id"),
                       required=bool(selected.get("required") or endcard["required"]))
    endcard.setdefault("duration_seconds", editing.get("endcard_duration_seconds", 3))
    return endcard


def music_settings(campaign):
    """Every new render needs a music bed; auto may resolve its file later."""
    editing = campaign.get("editing") or {}
    music = copy.deepcopy(editing.get("music") or {})
    music["path"] = music.get("source_path") or music.get("path") or ""
    assets = campaign.get("assets") or []
    required = next((a for a in assets if a.get("role") == "music" and a.get("required")), None)
    if required:
        music.update(path=_asset_path(required), required=True, asset_id=required.get("id"))
        music.pop("source_path", None)
        music["policy"] = "local"
    if music.get("policy") not in {"auto", "local"}:
        music["policy"] = "local" if music["path"] else "auto"
    music["required"] = True
    if music["policy"] == "local" and not music["path"]:
        raise EditingValidationError("Pilih file musik campaign sebelum membuat clip.")
    music["volume"] = _number(music.get("volume", .15), "Music volume", 0, 2)
    if music["volume"] <= 0:
        raise EditingValidationError("Musik wajib tidak boleh memakai volume nol.")
    return music


def build_clip_plan(source, highlight, campaign=None, ffmpeg_path="ffmpeg"):
    campaign = campaign or {}
    editing = campaign.get("editing") or {}
    template_id = editing.get("template_id") or "social"
    selection = {"mode": editing.get("template_mode", "fixed"), "reason": "Pilihan campaign", "fallback": False}
    if editing.get("selection_mode") == "weighted_random":
        from .campaigns import resolve_editing_preset
        chosen = highlight.get("editing_template") or {}
        preset = resolve_editing_preset(chosen.get("preset_id"))
        if chosen.get("preset_version") != preset["version"]:
            raise EditingValidationError("Versi template clip belum tersedia; pilih versi aplikasi yang sesuai.")
        if preset.get("external_template") and chosen.get("external_template") != preset["external_template"]:
            raise EditingValidationError("Isi versi template clip berubah sejak dipilih; pulihkan paket aslinya.")
        template_id = preset["subtitle_template_id"]
        selection.update(mode="weighted_random", reason=f"Diacak per clip: {preset['name']}", preset=copy.deepcopy(chosen))
    if selection["mode"] == "ai_select":
        suggested = highlight.get("template_id")
        if suggested in TEMPLATES:
            template_id = suggested
            selection["reason"] = str(highlight.get("editing_reason") or "Dipilih AI sesuai cerita dan brief")[:1000]
        else:
            selection.update(fallback=True, reason="Usulan template AI belum valid; memakai pilihan campaign. Periksa preview.")
    template = resolve_template(template_id)
    # Imported composition and subtitle style are separate renderer stages.
    # Pool choices carry immutable IDs; fixed campaigns resolve their preset.
    external_template = None
    if editing.get("selection_mode") == "weighted_random":
        external_template = preset.get("external_template")
    elif str(editing.get("preset_id", "")).startswith(("mlt:", "design:")):
        from .campaigns import resolve_editing_preset
        external_template = resolve_editing_preset(editing["preset_id"]).get("external_template")
    if external_template:
        external_id = f"{external_template['engine']}:{external_template['id']}:v{external_template['version']}"
        expected = editing.get("external_template_versions", {}).get(external_id)
        if expected is not None and external_template != expected:
            raise EditingValidationError("Isi versi template berubah sejak job dibuat; pulihkan paket aslinya.")
        template.update(id=external_id, version=external_template["version"],
                        canvas=copy.deepcopy(external_template["canvas"]), external_template=copy.deepcopy(external_template))
    source_start, source_end = timestamp_seconds(highlight["start_time"]), timestamp_seconds(highlight["end_time"])
    segments = [{"source_id": source["source_id"], "sha256": source.get("sha256"), "path": source.get("path"),
                 "start_seconds": source_start, "end_seconds": source_end, "role": editing.get("source_role", "external"), "kind": "source"}]
    configured = list(editing.get("segments") or [])
    configured_paths = {str(s.get("path")) for s in configured}
    for asset in campaign.get("assets") or []:
        if asset.get("required") and asset.get("role") in ("video", "image") and _asset_path(asset) not in configured_paths:
            configured.append({"path": _asset_path(asset), "start_seconds": asset.get("start_seconds", 0),
                               "end_seconds": asset.get("end_seconds", 3 if asset.get("role") == "image" else None), "role": "campaign", "asset_id": asset.get("id"), "required": True, "is_image": asset.get("role") == "image"})
    for segment in configured:
        path = segment.get("path") or segment.get("source_path") or ""
        info = probe_media(path, ffmpeg_path)
        is_image = segment.get("is_image", False)
        if not info["has_video"] or (info["duration"] <= 0 and not is_image):
            raise EditingValidationError("Campaign video segment must contain a timed video stream.")
        start = _number(segment.get("start_seconds", 0), "Segment start")
        # Choose enough campaign footage to satisfy the ratio when no range was
        # specified. Explicit user ranges are never silently lengthened.
        limit = float((campaign.get("rules") or {}).get("max_external_ratio", 1))
        external = sum(s["end_seconds"]-s["start_seconds"] for s in segments if s["role"] == "external")
        official = sum(s["end_seconds"]-s["start_seconds"] for s in segments if s["role"] == "campaign")
        needed = max(0, external / limit - external - official + 1/30) if 0 < limit < 1 else 5
        chosen = min(start + max(5, needed), info["duration"])
        end = _number(segment.get("end_seconds") if segment.get("end_seconds") is not None else chosen, "Segment end")
        if not is_image and end > info["duration"] + 0.1:
            raise EditingValidationError("Campaign segment exceeds source duration.")
        identity = fingerprint_source(path)
        segments.append({**identity, "start_seconds": start, "end_seconds": end, "role": segment.get("role", "campaign"),
                         "kind": "insert", "asset_id": segment.get("asset_id"), "required": bool(segment.get("required")), "is_image": is_image})
    endcard = endcard_settings(campaign)
    if endcard["required"] and not endcard["path"]:
        raise EditingValidationError("Campaign requires an endcard: attach its image or video.")
    if endcard["path"]:
        info = probe_media(endcard["path"], ffmpeg_path)
        if not info["has_video"]:
            raise EditingValidationError("Endcard must be an image or a video.")
        duration = _number(endcard.get("duration_seconds", editing.get("endcard_duration_seconds", 3)), "Endcard duration", 0.1, 60)
        if info["duration"] and duration > info["duration"] + 0.1:
            raise EditingValidationError("Endcard duration exceeds its video duration.")
        identity = fingerprint_source(endcard["path"])
        endcard.update(identity, duration_seconds=duration, is_image=info["duration"] == 0)
        segments.append({**identity, "start_seconds": 0, "end_seconds": duration, "role": "campaign", "kind": "endcard", "is_image": endcard["is_image"]})
    rules = campaign.get("rules") or {}
    plan = {"version": 1, "template": template, "template_selection": selection, "framing": external_template["source_framing"] if external_template else editing.get("framing") or template["framing"],
            "segments": segments, "endcard": endcard, "music": music_settings(campaign),
            "constraints": {"max_external_ratio": editing.get("max_external_ratio", rules.get("max_external_ratio", 1)),
                            "max_external_ratio_strict": bool(editing.get("max_external_ratio_strict", rules.get("max_external_ratio_strict", False)))}}
    if external_template and external_template.get("engine") == "design":
        audio_defaults = external_template["audio"]
        configured_music = editing.get("music") or {}
        overrides = configured_music.get("mixing_overrides", [key for key in ("volume", "ducking", "fade_seconds") if key in configured_music])
        if "volume" not in overrides:
            plan["music"]["volume"] = audio_defaults["music_volume"]
        if "ducking" not in overrides:
            plan["music"]["ducking"] = audio_defaults["ducking"]
        if "fade_seconds" not in overrides:
            plan["music"].update(fade_in=audio_defaults["fade_in"], fade_out=audio_defaults["fade_out"])
        plan["music"]["template_audio_defaults"] = copy.deepcopy(audio_defaults)
    plan["validation"] = validate_clip_plan(plan)
    from .additionals import applicable_additionals
    plan["additional"] = applicable_additionals(campaign, highlight,
        canvas=template.get("canvas", {"width": 1080, "height": 1920}))
    return plan


def validate_clip_plan(plan):
    if plan.get("framing") not in ("speaker", "fit", "center"):
        raise EditingValidationError("Framing must be speaker, fit or center.")
    if not plan.get("segments"):
        raise EditingValidationError("Editing plan contains no segments.")
    total, external = 0.0, 0.0
    for segment in plan["segments"]:
        start = _number(segment.get("start_seconds", 0), "Segment start")
        end = _number(segment.get("end_seconds"), "Segment end")
        if end <= start:
            raise EditingValidationError("Every editing segment must have a positive duration.")
        if segment.get("role") not in ("campaign", "external"):
            raise EditingValidationError("Each source must be classified as campaign or external.")
        total += end - start
        if segment["role"] == "external":
            external += end - start
    limit = _number((plan.get("constraints") or {}).get("max_external_ratio", 1), "External material ratio", 0, 1)
    ratio = external / total
    strict = (plan.get("constraints") or {}).get("max_external_ratio_strict", False)
    if ratio > limit + 1e-9 or (strict and ratio >= limit - 1e-9):
        comparator = "less than" if strict else "at most"
        raise EditingValidationError(f"External material is {ratio:.1%}; campaign requires {comparator} {limit:.1%}. Add campaign footage or shorten external segments.")
    return {"duration_seconds": round(total, 6), "external_duration_seconds": round(external, 6), "external_ratio": ratio, "passed": True}


def render_composition(segments, output_path, ffmpeg_path="ffmpeg", width=1080, height=1920):
    """Hard-cut concatenation with a common canvas/timebase and silence if needed.

    Segments are sequential; no transition overlap is counted twice. Material is
    fitted to the canvas, so campaign endcards and inserts keep their full text.
    """
    if not segments:
        raise EditingValidationError("Cannot render an empty composition.")
    command = [str(ffmpeg_path), "-y", "-hide_banner", "-loglevel", "error"]
    filters, join, input_index = [], [], 0
    for number, segment in enumerate(segments):
        path = str(segment["path"])
        info = probe_media(path, ffmpeg_path)
        start = _number(segment.get("start_seconds", 0), "Segment start")
        duration = _number(segment["end_seconds"], "Segment end") - start
        if duration <= 0:
            raise EditingValidationError("Composition duration must be positive.")
        if segment.get("is_image") or info["duration"] == 0:
            command += ["-loop", "1", "-t", str(duration), "-i", path]
        else:
            command += ["-ss", str(start), "-t", str(duration), "-i", path]
        video_index = input_index
        input_index += 1
        audio_index = video_index
        if not info["has_audio"]:
            audio_index = input_index
            command += ["-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=48000:cl=stereo"]
            input_index += 1
        filters += [f"[{video_index}:v]scale={int(width)}:{int(height)}:force_original_aspect_ratio=decrease,pad={int(width)}:{int(height)}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,trim=duration={duration},setpts=PTS-STARTPTS[v{number}]",
                    f"[{audio_index}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={duration},asetpts=PTS-STARTPTS[a{number}]"]
        join += [f"[v{number}][a{number}]"]
    filters.append("".join(join) + f"concat=n={len(segments)}:v=1:a=1[v][a]")
    command += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path)]
    _run(command)
    actual = probe_media(output_path, ffmpeg_path)
    validate_render_canvas(actual, {"width": width, "height": height}, "Komposisi")
    return actual


def mix_music(video_path, music, output_path, ffmpeg_path="ffmpeg"):
    """Render music before review, using voice sidechain, fades and peak limiting."""
    path = music.get("source_path") or music.get("path")
    if not path or not Path(path).is_file():
        raise EditingValidationError("Selected music file is missing. The video has not been finalized.")
    video, audio = probe_media(video_path, ffmpeg_path), probe_media(path, ffmpeg_path)
    if not audio["has_audio"] or audio["duration"] <= 0:
        raise EditingValidationError("Music asset does not contain playable audio.")
    duration = _number(video["duration"], "Video duration", minimum=.001)
    if not video["has_video"]:
        raise EditingValidationError("Video untuk pencampuran musik tidak valid.")
    start = _number(music.get("start_seconds", music.get("start", 0)), "Music entry point")
    if start >= audio["duration"]:
        raise EditingValidationError("Music entry point is beyond the end of the track.")
    volume = _number(music.get("volume", 0.15), "Music volume", 0, 2)
    if volume <= 0:
        raise EditingValidationError("Musik wajib tidak boleh memakai volume nol.")
    # Inspect exactly the seeked/looped window that will be mixed, not the
    # complete song: audible material elsewhere cannot validate a silent intro.
    music_input = ["-stream_loop", "-1", "-ss", str(start), "-t", str(duration), "-i", str(path)]
    measured = _run([str(ffmpeg_path), "-hide_banner", "-nostats", *music_input,
        "-map", "0:a:0", "-vn", "-sn", "-dn", "-af",
        f"atrim=duration={duration},asetpts=PTS-STARTPTS,loudnorm=print_format=json",
        "-t", str(duration), "-f", "null", "-"], timeout=180)
    try:
        measurements = [json.loads(block) for block in re.findall(r"\{[^{}]*\}", measured.stderr)
                        if '"input_tp"' in block]
        peak = float(measurements[-1]["input_tp"])
    except (ValueError, KeyError, IndexError):
        raise EditingValidationError("Bagian musik yang dipilih tidak dapat diperiksa. Pilih musik lain lalu coba lagi.") from None
    if not math.isfinite(peak):
        raise EditingValidationError("Bagian musik yang dipilih senyap. Ubah titik mulai musik atau pilih musik lain.")
    fade = min(_number(music.get("fade_seconds", 1), "Music fade", 0, 30), duration / 2)
    fade_in = min(_number(music.get("fade_in", fade), "Music fade in", 0, 30), duration / 2)
    fade_out = min(_number(music.get("fade_out", fade), "Music fade out", 0, 30), duration / 2)
    command = [str(ffmpeg_path), "-y", "-hide_banner", "-loglevel", "error", "-i", str(video_path), *music_input]
    source_level = analyze_audio(video_path, ffmpeg_path, video).get("integrated_lufs") if video["has_audio"] else None
    music_level = max(-24, min(-12, source_level)) if source_level is not None else -18
    # Normalize relative to speech before applying the user's fader. Parallel
    # ducking keeps a dry floor, so continuous speech cannot erase the music.
    ducking_mix = .35
    chain = f"[1:a]aresample=48000,atrim=duration={duration},asetpts=PTS-STARTPTS,loudnorm=I={music_level}:TP=-2:LRA=11,volume={volume},afade=t=in:d={fade_in},afade=t=out:st={max(0, duration-fade_out)}:d={fade_out}[music]"
    if video["has_audio"]:
        chain += f";[0:a]aresample=48000,apad,atrim=duration={duration},asetpts=PTS-STARTPTS"
        if music.get("ducking", True):
            chain += f",asplit=2[voice][side];[music][side]sidechaincompress=threshold=0.05:ratio=3:attack=30:release=250:mix={ducking_mix}[bed];[voice][bed]"
        else:
            chain += "[voice];[voice][music]"
        chain += "amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=0[out]"
    else:
        chain += ";[music]alimiter=limit=0.95:level=0[out]"
    command += ["-filter_complex", chain, "-map", "0:v:0", "-map", "[out]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(duration), "-movflags", "+faststart", str(output_path)]
    _run(command)
    result = probe_media(output_path, ffmpeg_path)
    validate_render_canvas(result, video, "Pencampuran musik")
    if not result["has_video"] or not result["has_audio"]:
        raise EditingValidationError("Pencampuran musik gagal menghasilkan video dengan audio.")
    if abs(result["duration"] - duration) > 0.25:
        raise EditingValidationError("Music render unexpectedly changed the video duration.")
    return {**copy.deepcopy(music), "required": True, "volume": volume, "path": str(Path(path).resolve()),
            "sha256": file_sha256(path), "duration_seconds": result["duration"], "mixed": True,
            "mixing": {"version": 2, "source_integrated_lufs": source_level, "normalization_lufs": music_level,
                       "ducking_max_reduction_db": round(-20 * math.log10(1 - ducking_mix), 2)
                           if video["has_audio"] and music.get("ducking", True) else 0}}
