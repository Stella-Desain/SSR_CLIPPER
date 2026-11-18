"""Local identity comparison with official OpenCV YuNet + SFace models.

Only compares a user-supplied target photo. Does not name people or infer traits.
Feature vectors and frame samples live in memory for the current job only.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import math
import os
from pathlib import Path
import threading

from .additionals import read_image
from .editing import EditingValidationError, file_sha256, config_hash, timestamp_seconds

MODEL_COMMIT = "47534e27c9851bb1128ccc0102f1145e27f23f98"
MODELS = {
    "face_detection_yunet_2023mar.onnx": ("face_detection_yunet", "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4", 232589),
    "face_detection_yunet_2026may.onnx": ("face_detection_yunet", "ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0", 229738),
    "face_recognition_sface_2021dec.onnx": ("face_recognition_sface", "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79", 38696353),
}
MATCH_VERSION = 1
COSINE_THRESHOLD = .363  # OpenCV's documented LFW operating point; not a guarantee.
SAMPLE_INTERVAL = 2.0
MIN_COVERAGE = .20


def model_root():
    from .mlt_runtime import application_root
    return Path(os.environ.get("SSR_FACE_MODELS") or application_root() / "_runtime" / "face_matcher")


@lru_cache(maxsize=12)
def _verified_model(path, size, modified):
    target = Path(path)
    if file_sha256(target) != MODELS[target.name][1]:
        raise EditingValidationError("Model filter wajah berubah. Jalankan tools/setup_face_models.py kembali.")
    return str(target)


def verified_model(name):
    path = model_root() / name
    if not path.is_file():
        raise EditingValidationError("Model filter wajah belum terpasang. Jalankan tools/setup_face_models.py.")
    stat = path.stat()
    return _verified_model(str(path), stat.st_size, stat.st_mtime_ns)


class TargetFaceMatcher:
    def __init__(self):
        import cv2
        self.cv2 = cv2
        detector_name = "face_detection_yunet_2026may.onnx" if int(cv2.__version__.split(".")[0]) >= 5 else "face_detection_yunet_2023mar.onnx"
        self.detector = cv2.FaceDetectorYN.create(verified_model(detector_name), "", (640, 640), .9, .3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(verified_model("face_recognition_sface_2021dec.onnx"), "")
        self.lock = threading.RLock()
        self.references = {}
        self.frames = {}
        self.source_digest = {}

    def _features(self, frame):
        cv2 = self.cv2
        # Limit face sizes and inference cost. Larger frames and reference photos
        # get the same preprocessing, including landmarks used for alignment.
        scale = min(1., 640 / max(frame.shape[:2]))
        if scale < 1:
            frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        self.detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, faces = self.detector.detect(frame)
        return [(self.recognizer.feature(self.recognizer.alignCrop(frame, face)).copy(),
                 float(min(face[2], face[3]))) for face in faces] if faces is not None else []

    def reference(self, image):
        import numpy as np
        decoded, digest = read_image(image)
        with self.lock:
            if digest not in self.references:
                rgba = np.asarray(decoded)
                # Composite transparent pixels onto neutral white for detection.
                rgb = (rgba[:, :, :3] * (rgba[:, :, 3:4] / 255.) + 255 * (1 - rgba[:, :, 3:4] / 255.)).astype(np.uint8)
                features = self._features(self.cv2.cvtColor(rgb, self.cv2.COLOR_RGB2BGR))
                if len(features) != 1:
                    raise EditingValidationError("Foto target harus menampilkan tepat satu wajah yang jelas. Pilih foto lain.")
                if features[0][1] < 24:
                    raise EditingValidationError("Wajah pada foto terlalu kecil. Unggah foto wajah yang lebih dekat.")
                self.references[digest] = features[0][0]
            return digest, self.references[digest]

    def evaluate(self, video, highlight, targets, cancelled=lambda: False):
        """One target must match repeatedly in >=20% of samples, over >=1 sec.

        Multiple references are alternatives (OR), not a requirement to have
        everyone in one shot. Failed frame reads fail closed, never count as hits.
        """
        if not targets:
            return {"version": MATCH_VERSION, "required": False, "accepted": True}
        start, end = timestamp_seconds(highlight["start_time"]), timestamp_seconds(highlight["end_time"])
        path = Path(video).resolve()
        stat = path.stat()
        source_key = (str(path), stat.st_size, stat.st_mtime_ns)
        with self.lock:
            digest = self.source_digest.setdefault(source_key, None)
            if digest is None:
                digest = self.source_digest[source_key] = file_sha256(path)
            references = [(item["id"], *self.reference(item["image"])) for item in targets]
            count = max(3, math.ceil((end-start) / SAMPLE_INTERVAL) + 1)
            times = [start + (end-start) * (i+.5) / count for i in range(count)]
            evidence = {identifier: [] for identifier, _, _ in references}
            scores = {identifier: -1. for identifier, _, _ in references}
            cap = None
            read = 0
            try:
                for seconds in times:
                    if cancelled():
                        raise EditingValidationError("Pemeriksaan wajah dibatalkan.")
                    key = (digest, round(seconds, 4))
                    if key not in self.frames:
                        if cap is None:
                            cap = self.cv2.VideoCapture(str(path))
                        if not cap.isOpened():
                            raise EditingValidationError("Video sumber tidak dapat dibaca untuk filter wajah.")
                        cap.set(self.cv2.CAP_PROP_POS_MSEC, seconds * 1000)
                        ok, frame = cap.read()
                        self.frames[key] = self._features(frame) if ok else None
                    features = self.frames[key]
                    if features is None:
                        continue
                    read += 1
                    for identifier, _, reference in references:
                        best = max((float(self.recognizer.match(reference, feature, self.cv2.FaceRecognizerSF_FR_COSINE))
                                    for feature, size in features if size >= 16), default=-1.)
                        scores[identifier] = max(scores[identifier], best)
                        if best >= COSINE_THRESHOLD:
                            evidence[identifier].append(round(seconds, 4))
            finally:
                if cap is not None:
                    cap.release()
            if read < math.ceil(count * .9):
                raise EditingValidationError("Terlalu banyak frame sumber gagal dibaca saat memeriksa wajah. Clip belum dapat diverifikasi.")
            results = []
            for identifier, photo_hash, _ in references:
                matches = evidence[identifier]
                accepted = len(matches) >= max(2, math.ceil(count * MIN_COVERAGE)) and matches[-1]-matches[0] >= min(1, (end-start)*.5)
                results.append({"id": identifier, "photo_sha256": photo_hash, "matched_samples": len(matches),
                    "coverage": len(matches)/count, "best_similarity": round(scores[identifier], 4),
                    "accepted": accepted, "matched_seconds": matches})
            # Bound in-memory frame cache for long-running jobs; never write embeddings to disk.
            if len(self.frames) > 4096:
                self.frames.clear()
            return {"version": MATCH_VERSION, "required": True, "accepted": any(r["accepted"] for r in results),
                    "source_sha256": digest, "model_commit": MODEL_COMMIT, "threshold": COSINE_THRESHOLD,
                    "sample_interval_seconds": SAMPLE_INTERVAL, "minimum_coverage": MIN_COVERAGE,
                    "sample_count": count, "read_samples": read, "targets": results}
