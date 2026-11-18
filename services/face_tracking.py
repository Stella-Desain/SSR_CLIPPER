"""Geometric face identities and conservative, scene-aware camera decisions.

Mouth movement is only a framing hint, not reliable audio-visual diarization.
Ambiguous multi-person shots retain the full image instead of guessing a speaker.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

CAMERA_VERSION = 3

def _iou(a, b):
    x = max(a[0], b[0])
    y = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    intersection = max(0, right-x) * max(0, bottom-y)
    return intersection / max(1e-9, a[2]*a[3] + b[2]*b[3] - intersection)


@dataclass
class Track:
    id: int
    bbox: tuple
    last_seen: float
    mouth: float | None = None
    activity: float = 0.0


class StableFaceTracker:
    def __init__(self, max_missing_seconds=0.8):
        self.max_missing_seconds = max_missing_seconds
        self.tracks = {}
        self.next_id = 1

    def reset(self):
        self.tracks.clear()

    def update(self, detections, seconds, scene_cut=False):
        if scene_cut:
            self.reset()
        self.tracks = {key: t for key, t in self.tracks.items() if seconds - t.last_seen <= self.max_missing_seconds}
        pairs = []
        for index, detection in enumerate(detections):
            bbox = tuple(detection["bbox"])
            for key, track in self.tracks.items():
                old = track.bbox
                distance = math.hypot((bbox[0]+bbox[2]/2) - (old[0]+old[2]/2), (bbox[1]+bbox[3]/2) - (old[1]+old[3]/2))
                overlap = _iou(bbox, old)
                if overlap > 0.08 or distance < max(bbox[2], old[2]) * 0.6:
                    pairs.append((overlap - distance * 0.5, index, key))
        assigned, used = {}, set()
        for _, index, key in sorted(pairs, reverse=True):
            if index not in assigned and key not in used:
                assigned[index] = key
                used.add(key)
        result = []
        for index, detection in enumerate(detections):
            bbox = tuple(detection["bbox"])
            key = assigned.get(index)
            mouth = detection.get("mouth")
            if key is None:
                key = self.next_id
                self.next_id += 1
                track = Track(key, bbox, seconds, mouth)
                self.tracks[key] = track
            else:
                track = self.tracks[key]
                # Mouth distances are normalized by face height at extraction.
                change = abs(mouth-track.mouth) if mouth is not None and track.mouth is not None else 0
                track.activity = track.activity * 0.7 + min(change * 12, 1) * 0.3
                track.bbox, track.last_seen, track.mouth = bbox, seconds, mouth
            result.append(track)
        return result


class CameraPlanner:
    def __init__(self, width, height, min_shot_seconds=2.0, max_pan_per_second=0.10, hold_seconds=0.7, aspect_ratio=9/16, anchor_x=.5):
        if not isinstance(anchor_x, (int, float)) or isinstance(anchor_x, bool) or not math.isfinite(anchor_x) or not 0 < anchor_x < 1:
            raise ValueError("Speaker position must be a fraction between 0 and 1.")
        self.anchor_x = anchor_x
        self.width, self.height = width, height
        self.crop_width = min(width, height * aspect_ratio)
        self.min_shot_seconds = max(0, min_shot_seconds)
        self.max_pan = max_pan_per_second * width
        self.hold_seconds = hold_seconds
        self.target_id = None
        self.last_switch = -math.inf
        self.last_seen = -math.inf
        self.last_time = None
        self.center = width / 2
        self.last_mode = "fit"
        self.last_confident = -math.inf
        self.filtered_center = None
        self.goal = self.center
        self.velocity = 0.0
        self.smooth_seconds = 1.0

    def _pan(self, desired, elapsed, seconds, snap=False):
        lower = self.crop_width * self.anchor_x
        upper = self.width - self.crop_width * (1-self.anchor_x)
        desired = max(lower, min(upper, desired))
        if snap or self.filtered_center is None:
            self.center = self.goal = self.filtered_center = desired
            self.velocity = 0.0
            return
        # Time-based noise filtering has the same response at 24/30/60 fps.
        self.filtered_center += (desired-self.filtered_center) * (1-math.exp(-elapsed/.35))
        self.goal = self.filtered_center
        # Critically damped spring: ease both into and out of camera movement.
        omega = 2/self.smooth_seconds
        error = self.center-self.goal
        change = self.velocity + omega*error
        decay = math.exp(-omega*elapsed)
        position = self.goal + (error+change*elapsed)*decay
        self.velocity = max(-self.max_pan, min(self.max_pan, (self.velocity-omega*change*elapsed)*decay))
        step = max(-self.max_pan*elapsed, min(self.max_pan*elapsed, position-self.center))
        self.center = max(lower, min(upper, self.center+step))

    def update(self, tracks, seconds, scene_cut=False):
        elapsed = max(0, seconds - self.last_time) if self.last_time is not None else 0
        self.last_time = seconds
        if scene_cut:
            self.target_id = None
            self.last_switch = -math.inf
            self.last_seen = -math.inf
            self.last_mode = "fit"
            self.last_confident = -math.inf
            self.filtered_center = None
        visible = {t.id: t for t in tracks}
        confident = len(tracks) == 1
        if len(tracks) > 1:
            ranked = sorted(tracks, key=lambda t: t.activity, reverse=True)
            confident = ranked[0].activity > 0.08 and ranked[0].activity > ranked[1].activity * 1.6 + 0.03
            candidate = ranked[0]
        else:
            candidate = tracks[0] if tracks else None
        if candidate is not None:
            self.last_seen = seconds
            if self.target_id not in visible or (confident and seconds-self.last_switch >= self.min_shot_seconds and candidate.id != self.target_id):
                self.target_id = candidate.id
                self.last_switch = seconds
        target = visible.get(self.target_id)
        mode = "speaker" if confident and target is not None else "fit"
        if mode == "speaker":
            self.last_confident = seconds
        elif self.last_mode == "speaker" and target is not None and seconds-self.last_confident <= self.hold_seconds:
            # One noisy multi-face detection must not switch the canvas to fit.
            mode = "speaker"
        if not tracks and seconds-self.last_seen <= self.hold_seconds:
            mode = self.last_mode
        if mode == "speaker" and target:
            x, _, w, _ = target.bbox
            desired = (x + w/2) * self.width
            # When a face plus a margin cannot fit in a portrait crop, fit it.
            if w*self.width*1.3 > self.crop_width:
                mode = "fit"
            if mode == "speaker":
                self._pan(desired, elapsed, seconds, snap=scene_cut)
        self.last_mode = mode
        x = max(0, min(self.width-self.crop_width, self.center-self.crop_width*self.anchor_x))
        return {"x": round(x, 4), "mode": mode, "track_id": self.target_id if mode == "speaker" else None, "scene_cut": bool(scene_cut)}


class FramingDecisionBuffer:
    """Confirm mode changes before emitting pixels, with bounded lookahead.

    Short failures retain the crop from the same shot. A brief initial failure
    can use the first confident crop in a new shot, never a previous shot's crop.
    """
    def __init__(self, confirmation_frames):
        self.confirmation_frames = max(2, int(confirmation_frames))
        self.stable = None
        self.pending = []

    @staticmethod
    def _mode(decision):
        return "fit" if decision["mode"] == "fit" else "crop"

    def _release(self, replacement=None):
        result = []
        for index, decision in self.pending:
            if replacement is not None:
                decision = {**decision, "mode": replacement["mode"], "x": replacement["x"],
                    "track_id": replacement.get("track_id"), "requested_mode": decision["mode"],
                    "stabilized": True}
            result.append((index, decision))
        self.pending.clear()
        return result

    def push(self, index, decision):
        decision = dict(decision)
        result = []
        if decision.get("scene_cut"):
            result.extend(self.flush())
            self.stable = None
        if self.stable is None:
            if self._mode(decision) == "crop":
                result.extend(self._release(decision))
                result.append((index, decision))
                self.stable = decision
                return result
        elif self._mode(decision) == self._mode(self.stable):
            result.extend(self._release(self.stable))
            result.append((index, decision))
            self.stable = decision
            return result
        self.pending.append((index, decision))
        if len(self.pending) >= self.confirmation_frames:
            result.extend(self._release())
            self.stable = decision
        return result

    def flush(self):
        return self._release(self.stable)


def scene_changed(previous, current, threshold=0.14):
    """Compare tiny grayscale frame samples supplied by the caller (0..255)."""
    if previous is None or len(previous) != len(current) or not current:
        return False
    difference = sum(abs(float(a)-float(b)) for a, b in zip(previous, current)) / (len(current) * 255)
    return difference >= threshold
