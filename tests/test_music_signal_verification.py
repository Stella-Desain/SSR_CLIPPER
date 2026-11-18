import unittest

import numpy as np

from tools.verify_music_render import correlation, signal_evidence


class MusicSignalVerificationTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(21)
        self.voice = rng.normal(0, .1, 16000)
        self.bed = rng.normal(0, .1, 16000)

    def test_audible_music_does_not_falsely_hide_preserved_voice(self):
        mixed = .98 * self.voice + 1.2 * self.bed
        self.assertLess(correlation(self.voice, mixed), .8)
        result = signal_evidence(self.voice, self.bed, mixed)
        self.assertTrue(result["voice_present"])
        self.assertTrue(result["selected_music_present"])
        self.assertAlmostEqual(result["voice_gain"], .98, places=4)
        self.assertAlmostEqual(result["estimated_music_gain"], 1.2, places=4)

    def test_missing_voice_still_fails(self):
        result = signal_evidence(self.voice, self.bed, .6 * self.bed)
        self.assertFalse(result["voice_present"])
        self.assertTrue(result["selected_music_present"])

    def test_missing_music_still_fails(self):
        result = signal_evidence(self.voice, self.bed, self.voice)
        self.assertTrue(result["voice_present"])
        self.assertFalse(result["selected_music_present"])

    def test_identical_reference_signals_are_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "tidak dapat dibedakan"):
            signal_evidence(self.voice, self.voice, self.voice)


if __name__ == "__main__":
    unittest.main()
