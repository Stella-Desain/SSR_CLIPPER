"""Audio QA uses only generated fixtures and never changes the input media."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.editing import analyze_audio, file_sha256


class AudioAnalysisFailureTests(unittest.TestCase):
    def test_failed_analysis_returns_explicit_unavailable_values(self):
        for result in [SimpleNamespace(stderr="No measurement returned"),
                       SimpleNamespace(stderr='{"input_i":"-20", "input_tp":"nan", "input_lra":"0"}'),
                       SimpleNamespace(stderr='{"input_i":null, "input_tp":"-1", "input_lra":"0"}')]:
            with self.subTest(result=result), patch('services.editing._run', return_value=result):
                analysis = analyze_audio('unused.mp4', media_info={'has_audio': True, 'duration': 3})
            self.assertEqual(analysis['status'], 'unavailable')
            self.assertIsNone(analysis['integrated_lufs'])
            self.assertIsNone(analysis['true_peak_dbtp'])
            self.assertTrue(analysis['warnings'])
            json.dumps(analysis, allow_nan=False)

    def test_no_audio_does_not_launch_analyzer(self):
        with patch('services.editing._run') as run:
            analysis = analyze_audio('unused.mp4', media_info={'has_audio': False, 'duration': 3})
        self.assertEqual(analysis['status'], 'no_audio')
        self.assertIsNone(analysis['integrated_lufs'])
        run.assert_not_called()

    def test_timeout_preserves_an_explicit_review_warning(self):
        with patch('services.editing._run', side_effect=subprocess.TimeoutExpired('ffmpeg', 180)):
            analysis = analyze_audio('unused.mp4', media_info={'has_audio': True, 'duration': 3})
        self.assertEqual(analysis['status'], 'unavailable')
        self.assertTrue(analysis['warnings'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg tools required')
class AudioMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def audio(self, name, source, volume=1):
        path = self.root / name
        result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', source, '-af', f'volume={volume}', '-t', '4', str(path)],
            capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return path

    def test_measures_original_level_and_amplitude_difference_without_rewriting(self):
        quiet = self.audio('quiet.wav', 'sine=frequency=1000:duration=4', .5)
        loud = self.audio('loud.wav', 'sine=frequency=1000:duration=4', 1)
        before = file_sha256(loud)
        lower, higher = analyze_audio(quiet), analyze_audio(loud)
        self.assertEqual(lower['status'], 'measured')
        self.assertEqual(higher['status'], 'measured')
        # Doubling the amplitude should increase both measurements by ~6 dB.
        self.assertAlmostEqual(higher['integrated_lufs'] - lower['integrated_lufs'], 6.02, delta=.15)
        self.assertAlmostEqual(higher['true_peak_dbtp'] - lower['true_peak_dbtp'], 6.02, delta=.15)
        # FFmpeg sine amplitude is 1/8; verify the input, not normalized output.
        self.assertAlmostEqual(higher['true_peak_dbtp'], -18.06, delta=.2)
        self.assertEqual(file_sha256(loud), before)
        json.dumps(higher, allow_nan=False)

    def test_silence_is_not_reported_as_zero_lufs(self):
        path = self.audio('silence.wav', 'anullsrc=r=48000:cl=stereo')
        analysis = analyze_audio(path)
        self.assertEqual(analysis['status'], 'silent')
        self.assertIsNone(analysis['integrated_lufs'])
        self.assertIsNone(analysis['true_peak_dbtp'])
        self.assertTrue(analysis['warnings'])
        json.dumps(analysis, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
