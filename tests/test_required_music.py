"""Every finished production render carries an audible, recorded music bed."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from services.editing import EditingValidationError, file_sha256, fingerprint_source, mix_music, music_settings
from services.storage import digest
from services.workflow import WorkflowMixin


class RequiredMusicSettingsTests(unittest.TestCase):
    def test_unset_and_legacy_disabled_music_become_required_auto(self):
        for campaign in ({}, {"editing": {"music": {"policy": "none", "required": False}}}):
            before = copy.deepcopy(campaign)
            settings = music_settings(campaign)
            self.assertEqual(settings["policy"], "auto")
            self.assertTrue(settings["required"])
            self.assertEqual(campaign, before)

    def test_existing_path_becomes_local_and_required_asset_overrides_stale_path(self):
        self.assertEqual(music_settings({"editing": {"music": {"path": "track.wav", "policy": "none"}}})["policy"], "local")
        settings = music_settings({"editing": {"music": {"source_path": "stale.wav"}},
            "assets": [{"id": "asset", "role": "music", "required": True, "path": "chosen.wav"}]})
        self.assertEqual(settings["path"], "chosen.wav")
        self.assertNotIn("source_path", settings)

    def test_campaign_required_asset_overrides_auto_or_stale_local_selection(self):
        from services.campaigns import normalize_campaign
        for policy in ("none", "auto", "local"):
            with self.subTest(policy=policy):
                campaign = normalize_campaign({"editing": {"music": {"policy": policy, "path": "stale.wav"}},
                    "assets": [{"role": "music", "required": True, "source_path": "campaign.wav"}]})
                self.assertEqual(campaign["editing"]["music"]["policy"], "local")
                self.assertEqual(campaign["editing"]["music"]["path"], "campaign.wav")

    def test_local_without_file_and_silent_gain_are_rejected(self):
        with self.assertRaises(EditingValidationError):
            music_settings({"editing": {"music": {"policy": "local"}}})
        for volume in (0, -1, float("nan"), "invalid"):
            with self.subTest(volume=volume), self.assertRaises(EditingValidationError):
                music_settings({"editing": {"music": {"volume": volume}}})

    def test_legacy_auto_selection_preserves_campaign_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            url = "https://example.invalid/track.mp3"
            path = Path(directory) / "music" / (digest(url)[:24] + ".mp3")
            path.parent.mkdir()
            path.write_bytes(b"cached fixture")
            api = SimpleNamespace(_select_background_sound=lambda *_: {
                "audiodownload": url, "volume": 0, "start": 1, "name": "Selected"})
            result = WorkflowMixin._select_workflow_music(api, {}, {
                "campaign": {"editing": {"music": {"policy": "none", "volume": .3}}}}, directory)
            self.assertTrue(result["required"])
            self.assertEqual(result["volume"], .3)
            self.assertEqual(result["start_seconds"], 1)
            self.assertEqual(result["path"], str(path))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RequiredMusicRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.source, cls.track, cls.silent = [cls.root / name for name in ("source.mp4", "music.wav", "silent.wav")]
        cls.ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=160x90:r=25:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(cls.source))
        cls.ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:duration=0.6", str(cls.track))
        cls.ffmpeg("-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "2", str(cls.silent))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def ffmpeg(cls, *args):
        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))
        return result.stdout

    def make_core(self, name, music=None):
        from clipper_core import AutoClipperCore
        core = AutoClipperCore(client=None, output_dir=self.root / name, log_callback=lambda *_: None)
        self.addCleanup(core.cleanup)
        core.campaign_config = {"editing": {"template_id": "clean", "music": music or {}},
            "brief": {"durasi_min": 1, "durasi_max": 3}}
        core.source_analysis = fingerprint_source(str(self.source))
        self.finalized = []
        core.finalize_callback = lambda directory, metadata: self.finalized.append(metadata) or metadata
        def base(*_args):
            target = core.output_dir / "clip-001" / "master.mp4"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.source, target)
        core._render_clip_base = base
        return core

    def render(self, core):
        return core.process_clip(str(self.source), {"title": "Story", "start_time": "00:00:00",
            "end_time": "00:00:02", "duration_seconds": 2}, 1, add_captions=False, add_hook=False, portrait=False)

    def test_unavailable_music_never_finalizes_a_voice_only_video(self):
        for label, selector in (("missing-selector", None), ("empty-selector", lambda *_: None)):
            with self.subTest(label=label):
                core = self.make_core(label)
                core.music_selector_callback = selector
                with self.assertRaisesRegex(EditingValidationError, "Musik belum tersedia"):
                    self.render(core)
                self.assertEqual(self.finalized, [])
                self.assertFalse((core.output_dir / "clip-001" / "data.json").exists())

    def test_selector_failure_is_actionable_and_not_a_finished_clip(self):
        core = self.make_core("selector-error")
        def fail(*_args):
            raise ConnectionError("offline")
        core.music_selector_callback = fail
        with self.assertRaisesRegex(EditingValidationError, "Coba lagi atau pilih file musik"):
            self.render(core)
        self.assertEqual(self.finalized, [])

    def test_real_music_is_audible_alongside_source_voice_and_cache_reuses_verified_mix(self):
        core = self.make_core("local-music", {"policy": "local", "path": str(self.track), "volume": .3, "ducking": False, "fade_seconds": 0})
        directory = self.render(core)
        meta = json.loads((directory / "data.json").read_text(encoding="utf-8"))
        self.assertTrue(meta["music"]["mixed"])
        self.assertEqual(meta["music"]["sha256"], file_sha256(self.track))
        import numpy as np
        waveform = np.frombuffer(self.ffmpeg("-i", str(directory / "master.mp4"), "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"), dtype="<f4")
        spectrum = abs(np.fft.rfft(waveform)) / len(waveform)
        frequencies = np.fft.rfftfreq(len(waveform), 1/8000)
        for hz in (220, 440):
            self.assertGreater(float(spectrum[abs(frequencies-hz)<2].max()), .002)
        self.assertAlmostEqual(meta["duration_seconds"], 2, delta=.05)
        def unexpected(*_args):
            self.fail("Verified completed music render should be reused")
        core._render_clip_base = unexpected
        self.render(core)
        self.assertEqual(len(self.finalized), 2)

    def test_auto_track_is_required_and_cannot_override_campaign_gain_with_zero(self):
        core = self.make_core("auto-music", {"policy": "auto", "volume": .25})
        core.music_selector_callback = lambda *_: {"path": str(self.track), "volume": 0, "required": False}
        directory = self.render(core)
        music = json.loads((directory / "data.json").read_text(encoding="utf-8"))["music"]
        self.assertTrue(music["mixed"])
        self.assertTrue(music["required"])
        self.assertEqual(music["volume"], .25)

    def test_zero_volume_and_silent_track_are_rejected_by_actual_mixer(self):
        for path, volume in ((self.track, 0), (self.silent, .2)):
            with self.subTest(path=path), self.assertRaises(EditingValidationError):
                mix_music(self.source, {"path": str(path), "volume": volume}, self.root / "invalid.mp4")

    def test_continuous_voice_cannot_duck_music_into_inaudibility(self):
        import numpy as np
        target = self.root / "limited-ducking.mp4"
        music = mix_music(self.source, {"path": str(self.track), "volume": .6,
            "ducking": True, "fade_seconds": 0}, target)
        self.assertLess(music["mixing"]["ducking_max_reduction_db"], 4)
        self.assertIsNotNone(music["mixing"]["source_integrated_lufs"])
        waveform = np.frombuffer(self.ffmpeg("-i", str(target), "-vn", "-ac", "1", "-ar", "8000",
            "-f", "f32le", "-"), dtype="<f4")[4000:-4000]
        spectrum = abs(np.fft.rfft(waveform)) / len(waveform)
        frequencies = np.fft.rfftfreq(len(waveform), 1 / 8000)
        music_peak = float(spectrum[abs(frequencies - 220) < 2].max())
        voice_peak = float(spectrum[abs(frequencies - 440) < 2].max())
        self.assertGreater(music_peak / voice_peak, .2)
        self.assertGreater(voice_peak, .02)

    def test_audible_material_outside_selected_music_window_cannot_validate_silence(self):
        track = self.root / "tone-then-silence.wav"
        self.ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:duration=1",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-filter_complex",
            "[1:a]atrim=duration=4[silence];[0:a][silence]concat=n=2:v=0:a=1[a]",
            "-map", "[a]", str(track))
        with self.assertRaisesRegex(EditingValidationError, "Bagian musik yang dipilih senyap"):
            mix_music(self.source, {"path": str(track), "start_seconds": 2}, self.root / "silent-window.mp4")
        # A window that actually contains the tone still produces a valid mix.
        result = mix_music(self.source, {"path": str(track), "start_seconds": 0}, self.root / "audible-window.mp4")
        self.assertTrue(result["mixed"])


if __name__ == "__main__":
    unittest.main()
