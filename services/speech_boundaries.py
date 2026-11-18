"""Choose supported speech endings before cutting, without inventing word times.

YouTube rolling captions often overlap: their display end is not the end of the
words on that line. Those cues require an observed audio pause near the next
cue's onset. Non-overlapping sentence timestamps can be used directly.
"""
from __future__ import annotations

import copy
import math
import re
import subprocess

BOUNDARY_VERSION = 2
_TIME = r"\d{1,2}:\d{2}:\d{2}(?:[,.]\d+)?"
_CUE = re.compile(rf"^\[({_TIME})\s*-\s*({_TIME})\]\s*(.+)$", re.MULTILINE)
_TERMINAL = re.compile(r'[.!?。！？][\s\"\'”’»\)\]]*$')
_ANSWER = re.compile(r"^(?:karena|sebab|soalnya|jawabannya|because|the answer)\b", re.I)
_OPEN_QUESTION = re.compile(r"(?:^|[.!?]\s*)(?:kenapa|mengapa|why|bagaimana|how|buat apa|untuk apa)\s*[?？][\s\"'”’]*$", re.I)
_UNFINISHED = re.compile(r"(?:[,;:]|\b(?:dan|atau|karena|kalau|jika|tapi|tetapi|untuk|agar|bahwa|dengan|and|or|because|if|but|to))\s*$", re.I)


class SpeechBoundaryError(ValueError):
    pass


def seconds(value):
    if isinstance(value, (float, int)):
        return float(value)
    h, m, s = str(value).replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def timestamp(value):
    millis = round(value * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def parse_cues(transcript):
    cues = []
    for match in _CUE.finditer(str(transcript or "")):
        start, end = seconds(match[1]), seconds(match[2])
        if math.isfinite(start) and math.isfinite(end) and 0 <= start < end:
            cues.append({"start": start, "end": end, "text": match[3].strip()})
    return sorted(cues, key=lambda cue: (cue["start"], cue["end"]))


def detect_pauses(path, start, end, ffmpeg="ffmpeg"):
    """Return observed quiet intervals in absolute source time; None on failure."""
    if end <= start:
        return []
    try:
        result = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-nostdin", "-ss", str(start), "-t", str(end-start),
             "-i", str(path), "-vn", "-af", "silencedetect=noise=-32dB:d=0.18", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    pauses, opened = [], None
    for kind, value in re.findall(r"silence_(start|end):\s*([\d.]+)", result.stderr):
        point = start + float(value)
        if kind == "start":
            opened = point
        elif opened is not None:
            # A truncated analysis window is not proof of a completed utterance.
            if opened > start + .02 and point < end - .02:
                pauses.append((opened, point))
            opened = None
    return pauses


class SpeechBoundaryAligner:
    """Bounded local ending repair; no AI/network calls and no source mutations."""

    def __init__(self, transcript, source_duration, *, path=None, ffmpeg="ffmpeg", has_audio=True):
        self.cues = parse_cues(transcript)
        self.duration = float(source_duration)
        self.path = path
        self.ffmpeg = ffmpeg
        self.has_audio = has_audio
        self._pauses = {}

    def _audio_pauses(self, lower, upper):
        window = (max(0, math.floor((lower-1)/10)*10), min(self.duration, math.ceil((upper+1)/10)*10))
        if window not in self._pauses:
            self._pauses[window] = detect_pauses(self.path, *window, ffmpeg=self.ffmpeg) if self.path and self.has_audio else None
        return self._pauses[window]

    def align(self, highlight, minimum, maximum):
        item = copy.deepcopy(highlight)
        start, requested = seconds(item["start_time"]), seconds(item["end_time"])
        previous = item.get("speech_boundary") or {}
        if (previous.get("version") == BOUNDARY_VERSION and
                previous.get("requested_start_seconds") == start and
                abs(previous.get("aligned_end_seconds", -1)-requested) < .001):
            requested = float(previous["requested_end_seconds"])
        if not all(math.isfinite(x) for x in (start, requested)) or start < 0 or requested <= start or requested > self.duration + .25:
            raise SpeechBoundaryError("Timestamp highlight berada di luar sumber video.")
        record = {"version": BOUNDARY_VERSION, "requested_start_seconds": start,
                  "requested_end_seconds": requested, "aligned_end_seconds": requested, "warnings": []}
        item["speech_boundary"] = record
        if not self.has_audio or not self.cues:
            record.update(method="no_speech" if not self.has_audio else "unverified", confidence="unverified")
            if self.has_audio:
                record["warnings"].append("Transkrip tidak memiliki waktu ucapan; akhir clip belum dapat diverifikasi. Periksa sebelum upload.")
            if requested > self.duration or not float(minimum) <= requested-start <= float(maximum):
                raise SpeechBoundaryError("Durasi highlight tidak memenuhi campaign; batas ucapan tidak tersedia untuk memperbaikinya.")
            item["duration_seconds"] = requested-start
            return item

        # A 28–70s campaign allows a sentence/answer to finish at 65s. The old
        # fixed +12s search could miss that ending and wrongly fall back to an
        # earlier sentence. Search the available campaign budget, stopping at a
        # substantial transcript gap so we do not pull in an unrelated story.
        lower = max(start + float(minimum), requested-12)
        upper = min(start + float(maximum), self.duration)
        for cue, following in zip(self.cues, self.cues[1:]):
            if following["start"] > requested and cue["end"] > start and following["start"]-cue["end"] >= 2:
                upper = min(upper, cue["end"])
                break
        candidates, rolling = [], []
        for index, cue in enumerate(self.cues):
            following = self.cues[index+1] if index+1 < len(self.cues) else None
            terminal = bool(_TERMINAL.search(cue["text"])) and not cue["text"].rstrip().endswith("...")
            question = cue["text"].rstrip().rstrip('"\'”’').endswith(("?", "？"))
            # A punctuation mark is not a payoff: "Kenapa? Karena ..." must
            # include the answer. This was a real 29s clip from a 28–70s job.
            open_answer = (question and (
                _OPEN_QUESTION.search(cue["text"]) or
                (following is not None and following["start"]-cue["end"] < 2 and
                 _ANSWER.search(following["text"]))
            ))
            if open_answer:
                continue
            overlap = following is not None and following["start"] < cue["end"]-.05
            if overlap:
                # The text itself must finish a sentence. Never interpolate a
                # timestamp for punctuation inside a multi-sentence cue.
                if terminal and lower-.75 <= following["start"] <= upper+.75:
                    rolling.append((following["start"], cue["start"]))
                continue
            gap = following["start"]-cue["end"] if following else 0
            pause_ending = gap >= .45 and not _UNFINISHED.search(cue["text"])
            if lower <= cue["end"] <= upper and (terminal or pause_ending):
                candidates.append((cue["end"], "sentence_timestamp" if terminal else "transcript_pause", cue["text"]))

        if rolling:
            pauses = self._audio_pauses(lower, upper) or []
            for boundary, cue_start in rolling:
                nearby = [(a, b) for a, b in pauses if a >= cue_start and abs((a+b)/2-boundary) <= .75]
                if nearby:
                    a, b = min(nearby, key=lambda p: abs((p[0]+p[1])/2-boundary))
                    point = (a+b)/2
                    if lower <= point <= upper:
                        candidates.append((point, "rolling_sentence_pause", ""))

        if not candidates:
            raise SpeechBoundaryError("Tidak ditemukan akhir ucapan yang utuh dalam batas durasi campaign. Pilih momen lain atau perluas durasi campaign.")
        # Prefer completing the currently spoken sentence; if it cannot fit,
        # use the closest preceding supported ending instead of a hard limit.
        later = [candidate for candidate in candidates if candidate[0] >= requested-.001]
        chosen = min(later, key=lambda c: c[0]) if later else max(candidates, key=lambda c: c[0])
        aligned, method, _ = chosen
        aligned = round(aligned, 3)
        # Millisecond serialization must not push the result over a strict cap.
        if aligned > upper:
            aligned = math.floor(upper*1000)/1000
        record.update(aligned_end_seconds=aligned, method=method,
                      confidence="medium" if method != "sentence_timestamp" else "high")
        if method == "rolling_sentence_pause":
            record["warnings"].append("Subtitle sumber tumpang tindih; akhir kalimat dicocokkan dengan jeda audio. Periksa kesinambungan cerita sebelum upload.")
        elif method == "transcript_pause":
            record["warnings"].append("Akhir clip mengikuti jeda transkrip tanpa tanda akhir kalimat. Periksa apakah pesannya sudah utuh.")
        item["end_time"] = timestamp(aligned)
        item["duration_seconds"] = aligned-start
        return item
