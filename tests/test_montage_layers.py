"""Rendered voice onset and timed text isolation for montage upgrades."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

import numpy as np

from services.montage_layers import audio_arguments, apply_text_layers, prepare_text_layers
from utils.helpers import get_ffmpeg_path


class MontageLayerTests(unittest.TestCase):
    def test_karaoke_highlight_moves_without_restarting_phrase_animation(self):
        base = {'text':'IRONMAN 70.3 FINISH','phrase_start':0,'font_size':42,
                'duration':.5,'stroke_width':0,'position':[.5,.5]}
        layers = prepare_text_layers([{**base,'start':0,'highlight_index':0},
                                      {**base,'start':.5,'highlight_index':1}],640,360)
        clean = np.zeros((360,640,3),np.uint8)
        first = apply_text_layers(clean.copy(),.3,layers)
        second = apply_text_layers(clean.copy(),.51,layers)
        # White glyphs stay at the same coordinates when the active word changes.
        white_a,white_b=np.all(first>240,axis=2),np.all(second>240,axis=2)
        # Antialiased edge pixels can cross the threshold over a blue plate.
        self.assertGreater(np.count_nonzero(white_a & white_b)/np.count_nonzero(white_a | white_b),.995)
        def blue_center(frame):
            y,x = np.where((frame[:,:,0]>220)&(frame[:,:,2]<80))
            self.assertGreater(len(x),100)
            return x.mean()
        self.assertGreater(blue_center(second)-blue_center(first),40)

    def test_caption_does_not_leak_into_following_frames(self):
        layers = prepare_text_layers([{'start': 1, 'duration': .5, 'text': 'IRONMAN', 'font_size': 28}], 320, 568)
        clean = np.full((568, 320, 3), 70, np.uint8)
        at_cue = apply_text_layers(clean.copy(), 1.2, layers)
        self.assertFalse(np.array_equal(at_cue, clean))
        for t in [0, 1.5, 3]:
            np.testing.assert_array_equal(apply_text_layers(clean.copy(), t, layers), clean)

    def test_original_voice_is_audible_in_first_100ms(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sr = 48000
            t = np.arange(sr * 2) / sr
            for name, frequency in [('voice', 440), ('music', 1000)]:
                pcm = (.2 * np.sin(t * 2 * np.pi * frequency) * 32767).astype('<i2')
                with wave.open(str(root / (name+'.wav')), 'wb') as stream:
                    stream.setparams((1, 2, sr, 0, 'NONE', 'not compressed'))
                    stream.writeframes(pcm.tobytes())
            recipe = {'music': {'path': str(root/'music.wav')},
                      'narration': {'path': str(root/'voice.wav'), 'duration': 1}}
            inputs, options = audio_arguments(recipe, 2)
            result = subprocess.run([get_ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i', 'color=s=32x32:d=2',
                *inputs, *options, '-vn', '-t', '2', '-ar', str(sr), '-ac', '1', '-f', 'f32le', 'pipe:1'],
                capture_output=True, check=True)
            samples = np.frombuffer(result.stdout, dtype='<f4')
            first = samples[round(.04*sr):round(.1*sr)]
            self.assertGreater(float(np.sqrt(np.mean(first**2))), .01)
            reference = np.sin(np.arange(len(first)) / sr * 2 * np.pi * 440)
            # Compare both phases: resampling/loudnorm may shift the sine.
            quadrature = np.cos(np.arange(len(first)) / sr * 2 * np.pi * 440)
            amplitude = np.hypot(np.dot(first, reference), np.dot(first, quadrature)) / len(first)
            self.assertGreater(float(amplitude), .01)


if __name__ == '__main__':
    unittest.main()
