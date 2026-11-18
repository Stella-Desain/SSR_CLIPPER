"""Beat accents preserve old renders, readable hooks and a stable final pose."""
import copy
import unittest

import numpy as np

from services.beat_effects import apply_beat_effects, beat_pose, validate_beat_effects


class BeatEffectsTests(unittest.TestCase):
    def setUp(self):
        self.options = dict(enabled=True, start_seconds=5, end_seconds=9,
            beats_seconds=[5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5],
            punch_scale=.065, shake_pixels=8, rotation_degrees=.35,
            brightness_pulse=.06, decay_seconds=.28)
        self.frame = np.full((192, 108, 3), 120, dtype=np.uint8)
        self.frame[50:100, 35:70] = 210

    def test_old_recipe_hook_and_ending_keep_exact_pixels(self):
        for options, t in [(None, 5.04), ({'enabled': False}, 5.04),
                           (self.options, 4.99), (self.options, 9),
                           (self.options, 8.9)]:
            self.assertIs(apply_beat_effects(self.frame, t, options), self.frame)

    def test_random_seeking_matches_forward_sampling(self):
        times = [5.03, 5.1, 6.1, 8.54]
        forward = {t: apply_beat_effects(self.frame, t, self.options) for t in times}
        for t in reversed(times):
            actual = apply_beat_effects(self.frame, t, self.options)
            np.testing.assert_array_equal(actual, forward[t])
            self.assertEqual(actual.shape, self.frame.shape)
        self.assertFalse(np.array_equal(forward[5.03], self.frame))
        self.assertEqual(beat_pose(8.9, self.options), (1., 0., 0., 0., 1.))

    def test_invalid_timing_and_parameters_are_rejected(self):
        validate_beat_effects(self.options, 5, 12)
        for change in [{'start_seconds': 4}, {'end_seconds': 13},
                       {'beats_seconds': [5.5, 5]}, {'beats_seconds': [5, float('nan')]},
                       {'shake_pixels': float('inf')}, {'punch_scale': -.1}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_beat_effects({**copy.deepcopy(self.options), **change}, 5, 12)


if __name__ == '__main__':
    unittest.main()
