"""Real offline renders for the square reference template, including caption timing."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from services.editing import EditingValidationError, probe_media
from services.podcast_template import caption_words, draw_caption, render_layout, render_word_captions


class WordTimingTests(unittest.TestCase):
    def test_segments_without_word_timestamps_fail_instead_of_inventing_timing(self):
        with self.assertRaisesRegex(EditingValidationError, "waktu per kata"):
            caption_words({"segments": [{"text": "kalimat panjang", "start": 0, "end": 3}]})

    def test_overlap_and_punctuation_do_not_show_two_words(self):
        words = caption_words({"words": [{"word": "Cerita,", "start": 0, "end": 1.2},
                                        {"word": "selesai.", "start": 1, "end": 3}]}, duration=2)
        self.assertEqual(words, [{"text": "CERITA", "start": 0, "end": 1}, {"text": "SELESAI", "start": 1, "end": 2}])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class PodcastRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.source = cls.root / "square.mp4"
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "color=c=0x404040:s=720x720:r=30:d=2.4", "-f", "lavfi", "-i", "sine=frequency=440:duration=2.4",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(cls.source)]
        subprocess.run(command, check=True, capture_output=True, timeout=60)
        cls.music = cls.root / "music.wav"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "sine=frequency=220:duration=0.8", str(cls.music)], check=True, capture_output=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def frame(self, path, seconds):
        import cv2
        capture = cv2.VideoCapture(str(path))
        capture.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
        ok, frame = capture.read()
        capture.release()
        self.assertTrue(ok)
        return frame

    def test_mask_and_actual_word_changes_preserve_duration_and_audio(self):
        bordered, final = self.root / "bordered.mp4", self.root / "captioned.mp4"
        render_layout(self.source, bordered)
        transcript = {"words": [{"word": "KESUKSESAN", "start": .3, "end": .9},
                                {"word": "ITU", "start": 1.2, "end": 1.8}]}
        media = render_word_captions(bordered, final, transcript)
        self.assertEqual((media["width"], media["height"]), (720, 720))
        self.assertAlmostEqual(media["fps"], 30)
        self.assertAlmostEqual(media["duration"], 2.4, delta=.04)
        self.assertTrue(media["has_audio"])
        base = self.frame(bordered, .5)
        self.assertLess(int(base[5, 10].max()), 6)  # Outside the rounded corner.
        self.assertGreater(int(base[60, 60].min()), 45)
        self.assertLess(int(base[360, 4].max()), 6)
        self.assertLess(int(base[716, 360].max()), 6)
        def glyph(seconds):
            frame = self.frame(final, seconds)
            return frame[395:440, 230:490].min(axis=2) > 200
        self.assertEqual(int(glyph(.1).sum()), 0)
        first, second = glyph(.5), glyph(1.5)
        self.assertGreater(int(first.sum()), 1000)
        self.assertGreater(int(first.sum()), int(second.sum())*2)
        self.assertEqual(int(glyph(1.05).sum()), 0)  # Real pause, no held caption.
        self.assertEqual(int(glyph(2.1).sum()), 0)

    def test_core_dispatch_uses_template_renderer_with_real_word_timestamps(self):
        from clipper_core import AutoClipperCore
        core = AutoClipperCore(client=None, output_dir=self.root / "core", log_callback=lambda *_: None)
        core._whisper_transcribe_words = lambda *_: SimpleNamespace(
            words=[SimpleNamespace(word="Bangkit", start=.2, end=1)], segments=[])
        try:
            final = self.root / "dispatch.mp4"
            core.add_captions_api_with_progress(str(self.source), str(final), subtitle_style="podcast_square")
            media = probe_media(final)
            self.assertEqual((media["width"], media["height"]), (720, 720))
            self.assertTrue(media["has_audio"])
            self.assertGreater(int((self.frame(final, .5)[400:435].min(axis=2)>200).sum()), 400)
        finally:
            core.cleanup()

    def test_square_framing_keeps_full_matching_source(self):
        from services.framing import frame_video
        core = SimpleNamespace(ffmpeg_path="ffmpeg", mediapipe_settings={}, campaign_config={"editing": {"framing": "center"}},
            face_tracking_mode="opencv", is_cancelled=lambda: False, log=lambda *_: None)
        final = self.root / "framed.mp4"
        frame_video(core, self.source, final, lambda *_: None, output_width=720, output_height=720, output_fps=30)
        media = probe_media(final)
        self.assertEqual((media["width"], media["height"]), (720, 720))
        self.assertAlmostEqual(media["duration"], 2.4, delta=.05)
        camera = json.loads((self.root / "camera.json").read_text())
        self.assertTrue(all(item["x"] == 0 for item in camera["decisions"]))

    def test_mixed_job_renders_each_selected_format_with_endcard_and_correct_source_range(self):
        from PIL import Image
        from clipper_core import AutoClipperCore
        from services.campaigns import normalize_campaign, campaign_processing_options
        from services.template_selection import choose_template
        endcard = self.root / "closing.png"
        Image.new("RGB", (300, 200), "green").save(endcard)
        self.source.with_suffix(".srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,800\nCerita selesai.\n", encoding="utf-8")
        core = AutoClipperCore(client=None, output_dir=self.root / "full-job", log_callback=lambda *_: None)
        core.resume_dir = self.root / "full-job" / "job-test"
        core.campaign_config = normalize_campaign({"name": "Test", "brief": {"durasi_min": 1, "durasi_max": 4},
            "editing": {"selection_mode": "weighted_random", "template_pool": [
                {"preset_id": "podcast_square", "enabled": True, "weight": 50},
                {"preset_id": "standard", "enabled": True, "weight": 50}], "framing": "center",
                "music": {"policy": "local", "path": str(self.music)}, "endcard": {
                "path": str(endcard), "duration_seconds": 1, "required": True}}})
        core.highlight_overrides = [{"title": selected, "start_time": "00:00:00,000", "end_time": "00:00:01,800",
            "editing_template": choose_template({"editing": {"preset_id": selected}}, "fixture")}
            for selected in ("podcast_square", "standard")]
        core._whisper_transcribe_words = lambda *_: SimpleNamespace(
            words=[SimpleNamespace(word="Selesai", start=.1, end=1.7)], segments=[])
        options = campaign_processing_options(core.campaign_config, 2)
        options.pop("clip_mode"); options.pop("subtitle_lang"); options["highlight_finder"] = False
        core.process(str(self.source), dur_min=1, dur_max=4, **options)
        self.assertEqual(core.get_clips_state()[0]["status"], "done", core.get_clips_state())
        directory = core.resume_dir / "clip-001"
        metadata = json.loads((directory / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["template"]["id"], "podcast_square")
        self.assertEqual(metadata["source_ranges"][0]["end_seconds"], 1.8)
        self.assertAlmostEqual(metadata["duration_seconds"], 2.8, delta=.05)
        self.assertEqual(metadata["blockers"], [])
        frame = self.frame(directory / "master.mp4", 2.4)
        b, g, r = map(int, frame[360, 360])
        self.assertGreater(g, r+50); self.assertGreater(g, b+50)
        standard = core.resume_dir / "clip-002" / "master.mp4"
        standard_media = probe_media(standard)
        self.assertEqual((standard_media["width"], standard_media["height"]), (1080, 1920))
        standard_meta = json.loads(standard.with_name("data.json").read_text(encoding="utf-8"))
        self.assertEqual(standard_meta["template"]["id"], "clean")
        self.assertEqual(standard_meta["editing_template"]["preset_id"], "standard")

    def test_campaign_preview_is_square_and_uses_the_actual_renderer(self):
        from test_workflow import Harness
        api = Harness(self.root / "preview")
        try:
            response = api.get_template_preview("podcast_square")
            self.assertEqual(response["status"], "ok", response)
            from urllib.parse import urlsplit
            path = api._media_preview.files[urlsplit(response["preview_url"]).path]
            media = probe_media(path)
            self.assertEqual((media["width"], media["height"]), (720, 720))
            self.assertAlmostEqual(media["duration"], 3, delta=.05)
            self.assertGreater(int((self.frame(path, .6)[400:435].min(axis=2)>200).sum()), 400)
        finally:
            if hasattr(api, "_media_preview"):
                api._media_preview.close()


if __name__ == "__main__":
    unittest.main()
