"""Estimate a beat grid from a local music passage, for manual visual review."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import file_sha256
from services.storage import atomic_json
from utils.helpers import get_ffmpeg_path


def measure(path, start, seconds, minimum=90, maximum=180):
    if start < 0 or not 8 <= seconds <= 180 or not 60 <= minimum < maximum <= 240:
        raise ValueError('Use a valid 8–180 second passage and a 60–240 BPM search range')
    path = Path(path).resolve()
    pcm = subprocess.run([get_ffmpeg_path(), '-v', 'error', '-ss', str(start),
        '-i', str(path), '-t', str(seconds), '-ac', '1', '-ar', '22050',
        '-f', 'f32le', 'pipe:1'], capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, dtype='<f4')
    sr, hop, window = 22050, 220, 1024
    if len(samples) < sr * 8 or np.max(np.abs(samples)) < 1e-5:
        raise ValueError('The selected passage is too short or silent')
    frames = np.lib.stride_tricks.sliding_window_view(samples, window)[::hop]
    spectrum = abs(np.fft.rfft(frames * np.hanning(window))) ** 2
    frequencies = np.fft.rfftfreq(window, 1 / sr)
    energy = np.log1p(spectrum[:, (frequencies >= 35) & (frequencies <= 180)].sum(axis=1))
    baseline = np.convolve(np.pad(energy, 20, mode='edge'), np.ones(41) / 41, mode='valid')
    envelope = np.maximum(0, energy - baseline)
    times = (np.arange(len(envelope)) * hop + window / 2) / sr
    duration = len(samples) / sr
    best = None
    for bpm in np.arange(minimum, maximum + .01, .1):
        period = 60 / bpm
        for phase in np.arange(0, period, .01):
            beats = np.arange(phase, duration - .2, period)
            score = float(np.interp(beats, times, envelope).mean())
            if best is None or score > best[0]:
                best = (score, float(bpm), float(phase))
    score, bpm, phase = best
    beats = []
    for target in np.arange(phase, duration - .2, 60 / bpm):
        nearby = np.flatnonzero(abs(times - target) < .04)
        peak = times[nearby[np.argmax(envelope[nearby])]] if len(nearby) else target
        beats.append(round(float(peak), 4))
    return {'method': 'low-frequency transient envelope, periodic grid search and local onset refinement',
            'music_path': str(path), 'music_sha256': file_sha256(path),
            'music_start_seconds': start, 'analysis_duration_seconds': round(duration, 4),
            'estimated_bpm': round(bpm, 2), 'phase_seconds': round(phase, 3),
            'score': round(score, 4), 'beats_seconds': beats,
            'estimated': True, 'requires_review_for_new_music': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('music', type=Path)
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--seconds', type=float, default=24)
    parser.add_argument('--min-bpm', type=float, default=90)
    parser.add_argument('--max-bpm', type=float, default=180)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.music, args.start, args.seconds, args.min_bpm, args.max_bpm)
    atomic_json(args.output, result)
    print(json.dumps({k: result[k] for k in ['estimated_bpm', 'phase_seconds', 'score', 'music_sha256']}))
