"""Stream a scene-aware camera plan to FFmpeg without an intermediate lossy codec."""
import json
import math
from pathlib import Path
import subprocess
import tempfile

from .editing import atomic_json, probe_media, validate_render_canvas, EditingValidationError
from .face_tracking import CAMERA_VERSION, StableFaceTracker, CameraPlanner, FramingDecisionBuffer, scene_changed


CPU_ENCODER = ["-c:v", "libx264", "-preset", "fast", "-crf", "18"]
FRAMING_VERSION = 2
TRANSITION_CONFIRM_SECONDS = .15


def frame_video(core, input_path, output_path, progress_callback, output_width=1080, output_height=1920, output_fps=None, framing_mode=None, subject_anchor=.5, tracking_mode=None):
    encoder = list(getattr(core, "framing_encoder_args", None) or CPU_ENCODER)
    options = dict(output_width=output_width, output_height=output_height, output_fps=output_fps,
                   framing_mode=framing_mode, subject_anchor=subject_anchor, tracking_mode=tracking_mode)
    try:
        return _frame_video(core, input_path, output_path, progress_callback, encoder, **options)
    except (BrokenPipeError, EditingValidationError) as exc:
        hardware = any(token in encoder for token in ("h264_qsv", "h264_nvenc", "h264_amf"))
        if not hardware or core.is_cancelled():
            raise
        # Restart just this render on CPU. Workers never mutate shared encoder
        # settings or consume a partly written hardware file as a valid result.
        core.log(f"Encode framing perangkat gagal; mengulang dengan CPU: {str(exc)[-240:]}")
        return _frame_video(core, input_path, output_path, progress_callback, CPU_ENCODER, **options)


def _frame_video(core, input_path, output_path, progress_callback, encoder, output_width=1080, output_height=1920, output_fps=None, framing_mode=None, subject_anchor=.5, tracking_mode=None):
    import cv2
    import numpy as np
    source = probe_media(input_path, core.ffmpeg_path)
    if not source["has_video"] or not source["width"] or source["duration"] <= 0:
        raise EditingValidationError("Cannot open video for framing.")
    width, height = source["width"], source["height"]
    source_size = (width, height)
    # Optional batch profile: keep enough pixels for the final crop, while
    # avoiding transport of redundant 4K pixels through the Python pipe.
    # This never enlarges the source or lowers the crop below the output size.
    efficient = getattr(core, "efficient_framing", False)
    if efficient:
        scale = min(1, max(output_height / height, output_width / width))
        width, height = max(2, round(width * scale)), max(2, round(height * scale))
    fps = output_fps or min(60, source.get("nominal_fps") or source["fps"] or 30)
    aspect = output_width / output_height
    total = max(1, round(source["duration"] * fps))
    tracker = StableFaceTracker()
    camera = CameraPlanner(width, height, min_shot_seconds=float(core.mediapipe_settings.get("min_shot_duration", 90)) / fps, aspect_ratio=aspect, anchor_x=subject_anchor)
    mode = framing_mode or core.campaign_config.get("editing", {}).get("framing", "speaker")
    if mode not in {"speaker", "fit", "center"}:
        raise EditingValidationError("Invalid framing mode.")
    mesh = None
    if (tracking_mode or core.face_tracking_mode) == "mediapipe":
        try:
            import mediapipe as mp
            mesh = mp.solutions.face_mesh.FaceMesh(max_num_faces=5, refine_landmarks=True,
                min_detection_confidence=.5, min_tracking_confidence=.5)
        except (ImportError, AttributeError):
            core.log("MediaPipe unavailable; use stable face tracking with full-frame fallback.")
    detector = None
    detector_status = "mediapipe" if mesh else "not_used"
    if mode == "speaker" and mesh is None:
        cascade_directory = getattr(getattr(cv2, "data", None), "haarcascades", "")
        cascade_path = Path(cascade_directory) / "haarcascade_frontalface_default.xml"
        if not cascade_directory or not cascade_path.is_file():
            from utils.helpers import get_bundle_dir
            cascade_path = get_bundle_dir() / 'assets/models/haarcascade_frontalface_default.xml'
        if cascade_path.is_file():
            candidate = cv2.CascadeClassifier(str(cascade_path))
            if not candidate.empty():
                detector = candidate
        detector_status = "opencv" if detector is not None else "unavailable"
        if detector is None:
            core.log("Face detector data unavailable; preserve the whole frame. Check the preview before upload.")
    command = [core.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{output_width}x{output_height}", "-r", str(fps), "-i", "pipe:0", "-i", str(input_path),
               "-map", "0:v", "-map", "1:a?", *encoder, "-threads", "2",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", str(source["duration"]), "-movflags", "+faststart", str(output_path)]
    # fps uses presentation timestamps, duplicating/dropping frames where needed.
    # Treating every decoded VFR frame as 1/average_fps shifts individual moments
    # against speech even when the resulting total duration happens to match.
    decode_filter = f"fps={fps}:start_time=0"
    if (width, height) != source_size:
        decode_filter += f",scale={width}:{height}:flags=lanczos"
    decode_command = [core.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-threads", "2", "-i", str(input_path),
        "-map", "0:v:0", "-an", "-filter_threads", "1", "-vf", decode_filter, "-pix_fmt", "bgr24",
        "-threads", "2", "-f", "rawvideo", "pipe:1"]
    frame_number, last_sample, decisions = 0, None, []
    fit_frames, crop_frames, stabilized_frames = 0, 0, 0
    previous_decision, max_pan_step, pan_distance = None, 0, 0
    stabilizer = FramingDecisionBuffer(math.ceil(fps * TRANSITION_CONFIRM_SECONDS))
    pending_frames = {}
    with tempfile.TemporaryFile() as errors, tempfile.TemporaryFile() as decode_errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        decoder = None
        try:
            def write_frames(resolved):
                nonlocal fit_frames, crop_frames, stabilized_frames, previous_decision, max_pan_step, pan_distance
                for number, decision in resolved:
                    image = pending_frames.pop(number)
                    image_height, image_width = image.shape[:2]
                    if (previous_decision and not decision.get('scene_cut') and decision['mode'] == 'speaker'
                            and previous_decision['mode'] == 'speaker'):
                        step = abs(decision['x']-previous_decision['x'])
                        max_pan_step = max(max_pan_step, step)
                        pan_distance += step
                    previous_decision = decision.copy()
                    if decision["mode"] == "fit":
                        scale = min(output_width/image_width, output_height/image_height)
                        foreground = cv2.resize(image, (max(1, int(image_width*scale)), max(1, int(image_height*scale))))
                        output = np.full((output_height, output_width, 3), 18, dtype=np.uint8)
                        y=(output_height-foreground.shape[0])//2; x=(output_width-foreground.shape[1])//2
                        output[y:y+foreground.shape[0], x:x+foreground.shape[1]] = foreground
                        fit_frames += 1
                    else:
                        crop_width = min(image_width, max(1, round(image_height*aspect)))
                        x = max(0, min(image_width-crop_width, float(decision["x"]) * image_width/width))
                        # Fractional sampling keeps a slow pan continuous even
                        # when its movement is less than one source pixel.
                        crop = cv2.getRectSubPix(image, (crop_width, image_height),
                            (x+(crop_width-1)/2, (image_height-1)/2))
                        output = cv2.resize(crop, (output_width, output_height))
                        crop_frames += 1
                    process.stdin.write(output.tobytes())
                    stabilized_frames += bool(decision.get("stabilized"))
                    previous_mode = decisions[-1]["mode"] if decisions else None
                    if (number % max(1, int(fps/2)) == 0 or decision.get("scene_cut")
                            or decision.get("stabilized") or decision["mode"] != previous_mode):
                        decisions.append({"seconds": number/fps, **decision})

            decoder = subprocess.Popen(decode_command, stdout=subprocess.PIPE, stderr=decode_errors,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            while True:
                if core.is_cancelled():
                    raise EditingValidationError("Framing cancelled.")
                raw = decoder.stdout.read(width * height * 3)
                if not raw:
                    break
                if len(raw) != width * height * 3:
                    raise EditingValidationError("Decoder returned an incomplete video frame.")
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sample = cv2.resize(gray, (16, 16)).ravel().tolist()
                cut = scene_changed(last_sample, sample)
                last_sample = sample
                detections = []
                if mode == "speaker":
                    if mesh:
                        analysis = frame
                        if efficient and width > 960:
                            analysis = cv2.resize(frame, (960, max(1, round(height * 960 / width))))
                        result = mesh.process(cv2.cvtColor(analysis, cv2.COLOR_BGR2RGB))
                        for points in result.multi_face_landmarks or []:
                            xs = [p.x for p in points.landmark]; ys = [p.y for p in points.landmark]
                            x, y, w, h = min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)
                            mouth = abs(points.landmark[13].y-points.landmark[14].y) / max(h, .001)
                            detections.append({"bbox": (x, y, w, h), "mouth": mouth})
                    elif detector is not None:
                        scale = min(1, 640/max(width, height))
                        small = cv2.resize(gray, None, fx=scale, fy=scale)
                        faces = detector.detectMultiScale(small, scaleFactor=1.15, minNeighbors=5, minSize=(24, 24))
                        detections = [{"bbox": (x/scale/width, y/scale/height, w/scale/width, h/scale/height)} for x, y, w, h in faces]
                tracked = tracker.update(detections, frame_number/fps, cut)
                decision = camera.update(tracked, frame_number/fps, cut)
                if mode in ("fit", "center"):
                    decision["mode"] = mode
                    decision["x"] = max(0, int((width-height*aspect)/2))
                # A matching canvas needs no crop or inferred camera motion.
                if abs(width/height - aspect) < .005:
                    decision["mode"] = "center"
                    decision["x"] = 0
                elif width/height < aspect:
                    decision["mode"] = "fit"
                pending_frames[frame_number] = frame
                write_frames(stabilizer.push(frame_number, decision) if mode == "speaker" else [(frame_number, decision)])
                # Only delayed frames need storage. Retain the final crop's pixel
                # density without buffering several full 4K frames per worker.
                if frame_number in pending_frames and height > output_height:
                    pending_frames[frame_number] = cv2.resize(frame,
                        (max(2, round(width * output_height / height)), output_height), interpolation=cv2.INTER_AREA)
                if frame_number % max(1, int(fps/2)) == 0 or cut:
                    progress_callback(min(1, frame_number/total))
                frame_number += 1
            write_frames(stabilizer.flush())
            if decoder.wait(timeout=30):
                decode_errors.seek(0)
                raise EditingValidationError(decode_errors.read().decode("utf-8", errors="replace")[-1500:])
            process.stdin.close()
            code = process.wait(timeout=180)
            if code:
                errors.seek(0)
                raise EditingValidationError(errors.read().decode("utf-8", errors="replace")[-1500:])
        finally:
            if decoder:
                decoder.stdout.close()
                if decoder.poll() is None:
                    decoder.kill()
                    decoder.wait()
            if mesh:
                mesh.close()
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
    actual = probe_media(output_path, core.ffmpeg_path)
    validate_render_canvas(actual, {"width": output_width, "height": output_height}, "Framing")
    if abs(actual["duration"] - source["duration"]) > .3:
        raise EditingValidationError("Framing duration mismatch; inspect variable frame rate source.")
    atomic_json(Path(output_path).parent / "camera.json", {"mode": mode, "detector": detector_status,
        "camera_version": CAMERA_VERSION, "framing_version": FRAMING_VERSION,
        "smoothing": "continuous_time_based_damped_pan",
        "max_pan_step_pixels": max_pan_step, "pan_distance_pixels": pan_distance,
        "smooth_seconds": camera.smooth_seconds, "subpixel_pan": True,
        "max_pan_pixels_per_second": camera.max_pan,
        "timebase": "source_timestamps_cfr", "render_fps": fps, "canvas": {"width": output_width, "height": output_height},
        "source_canvas": {"width": source_size[0], "height": source_size[1]},
        "decode_canvas": {"width": width, "height": height},
        "video_encoder": encoder[encoder.index("-c:v")+1],
        "fit_frames": fit_frames, "crop_frames": crop_frames, "frames": frame_number,
        "stabilized_frames": stabilized_frames, "transition_confirm_seconds": TRANSITION_CONFIRM_SECONDS,
        "decisions": decisions})
    progress_callback(1)
