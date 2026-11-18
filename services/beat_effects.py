"""Seek-safe native beat accents: uniform punch-in, mild roll and short shake.

Timing follows the supplied music beat grid. Inspired by the Registry's
beat-accent snap/settle and camera-shake primitives; no playback state or RNG.
"""
from bisect import bisect_right
import math

import cv2
import numpy as np


def validate_beat_effects(options, hook_end, duration):
    if not options or not options.get('enabled'):
        return
    limits = {'punch_scale': (0, .2), 'shake_pixels': (0, 24),
              'rotation_degrees': (0, 2), 'brightness_pulse': (0, .2),
              'decay_seconds': (.1, .5)}
    for key, (low, high) in limits.items():
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Invalid beat effect parameter: ' + key)
    start, end = options['start_seconds'], options['end_seconds']
    if not (math.isfinite(start) and math.isfinite(end) and hook_end <= start < end <= duration):
        raise ValueError('Beat effects must preserve the hook and fit the timeline')
    beats = options.get('beats_seconds', [])
    if not beats or any(isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b) or not start <= b < end for b in beats):
        raise ValueError('Beat grid must contain finite times inside its active window')
    if any(b <= a for a, b in zip(beats, beats[1:])):
        raise ValueError('Beat grid must be strictly increasing')


def beat_pose(t, options):
    """Return a reproducible similarity transform and luminance gain at t."""
    rest = (1., 0., 0., 0., 1.)  # scale, roll, x, y, gain
    if not options or not options.get('enabled') or not options['start_seconds'] <= t < options['end_seconds']:
        return rest
    index = bisect_right(options['beats_seconds'], t + 1e-9) - 1
    if index < 0:
        return rest
    delta = max(0., t - options['beats_seconds'][index])
    decay = options['decay_seconds']
    if delta >= decay:
        return rest
    # One short attack, a smooth recovery, and a finite resting interval.
    attack = min(.04, decay / 4)
    envelope = delta / attack if delta < attack else (1 - (delta - attack) / (decay - attack)) ** 3
    strength = 1. if index % 4 == 0 else .72
    envelope *= strength
    direction = 1 if index % 2 == 0 else -1
    oscillation = math.sin(delta * math.pi * 2 * 9)
    return (1 + options['punch_scale'] * envelope,
            direction * options['rotation_degrees'] * envelope * oscillation,
            direction * options['shake_pixels'] * envelope * oscillation,
            options['shake_pixels'] * .4 * envelope * math.sin(delta * math.pi * 2 * 12),
            1 + options['brightness_pulse'] * envelope)


def apply_beat_effects(frame, t, options):
    scale, roll, x, y, gain = beat_pose(t, options)
    if (scale, roll, x, y, gain) == (1., 0., 0., 0., 1.):
        return frame
    height, width = frame.shape[:2]
    matrix = cv2.getRotationMatrix2D(((width - 1) / 2, (height - 1) / 2), roll, scale)
    matrix[:, 2] += [x * width / 1080, y * height / 1920]
    result = cv2.warpAffine(frame, matrix, (width, height), flags=cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_REFLECT_101)
    if gain != 1:
        result = np.clip(result.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    return result
