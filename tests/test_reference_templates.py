"""Offline reference-template checks: real pixels, audio, timing and campaign jobs."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.campaigns import EDITING_PRESETS, normalize_campaign, campaign_processing_options
from services.editing import EditingValidationError, build_clip_plan, file_sha256, probe_media
from services.face_tracking import CameraPlanner, Track
from services.reference_templates import (broll_plan, caption_phrases, draw_caption,
    render_captions, render_layout, template_spec, timed_words)
from services.template_selection import choose_template


class ReferenceContractTests(unittest.TestCase):
    def test_new_presets_are_opt_in_and_keep_fixed_features_and_canvas(self):
        for preset_id, size in (("timothy_focus", (1440, 1080)), ("timothy_cinematic", (1920, 1080))):
            preset = EDITING_PRESETS[preset_id]
            self.assertFalse(preset["default_enabled"])
            campaign = normalize_campaign({"name": "A", "editing": {"preset_id": preset_id}})
            options = campaign_processing_options(campaign)
            self.assertTrue(options["add_captions"])
            self.assertFalse(options["portrait"])
            self.assertFalse(options["add_hook"])
            self.assertEqual(options["subtitle_style"], preset_id)
            plan = build_clip_plan({"source_id": "source", "path": "source.mp4"},
                {"title": "Cerita", "start_time": "00:00:00,000", "end_time": "00:00:10,000"}, campaign)
            self.assertEqual(tuple(plan["template"]["canvas"][key] for key in ("width", "height")), size)
            self.assertEqual(plan["additional"]["ratio"], "4:3" if preset_id.endswith("focus") else "16:9")
            selection = choose_template(campaign, "seed")
            self.assertEqual(choose_template(campaign, "retry", selection), selection)
        old = normalize_campaign({"editing": {"preset_id": "standard"}})
        self.assertNotIn("template_pool", old["editing"])

    def test_phrase_timing_keeps_real_pauses_and_does_not_invent_word_times(self):
        with self.assertRaisesRegex(EditingValidationError, "per kata"):
            timed_words({"segments": [{"text": "Ada cerita", "start": 0, "end": 3}]}, 3)
        words = {"words": [{"word": "Tanggung", "start": .2, "end": .5},
            {"word": "jawab.", "start": .48, "end": .9}, {"word": "Berani", "start": 1.4, "end": 2}]}
        self.assertEqual(timed_words(words, 1.8)[-1]["end"], 1.8)
        phrases = caption_phrases(words, 3)
        self.assertEqual(phrases, [{"text": "Tanggung jawab.", "start": .2, "end": .9},
            {"text": "Berani", "start": 1.4, "end": 2}])

    def test_cinematic_emphasis_does_not_turn_following_filler_into_takeaway(self):
        words = {"words": [{"word": word, "start": i*.2, "end": (i+1)*.2} for i, word in enumerate(
            ["seorang", "laki", "-laki,", "ya", "dan", "lu"])]}
        phrases = caption_phrases(words, 2, emphasis_breaks=True)
        self.assertEqual([phrase["text"] for phrase in phrases], ["seorang laki -laki,", "ya dan lu"])
        self.assertAlmostEqual(phrases[0]["end"], .6)
        from services.reference_templates import _clean, caption_emphasis
        self.assertEqual(_clean(phrases[0]["text"]), "seorang laki-laki")
        self.assertTrue(caption_emphasis(phrases[0]["text"]))
        self.assertFalse(caption_emphasis(phrases[1]["text"], last=True))

    def test_caption_regions_and_single_word_takeaway(self):
        import numpy as np
        focus = draw_caption("NGGAK PENGEN TANGGUNG JAWABNYA", "timothy_focus")
        box = focus.getbbox()
        self.assertGreater(box[0], 1440*.4)
        self.assertLess(box[2], 1440*.92)
        self.assertAlmostEqual(box[1], 1080*.245, delta=5)
        cinematic = draw_caption("pemenang", "timothy_cinematic", emphasize=True, last=True)
        rgba = np.asarray(cinematic)
        orange = (rgba[:, :, 0] > 180) & (rgba[:, :, 1] < 150) & (rgba[:, :, 2] < 75) & (rgba[:, :, 3] > 240)
        self.assertGreater(orange.sum(), 5000)
        self.assertGreater(cinematic.getbbox()[3]-cinematic.getbbox()[1], 90)
        self.assertLess(cinematic.getbbox()[3], 1080*.85)

    def test_face_anchor_places_speaker_left_without_changing_default_camera(self):
        face = Track(1, (.4, .25, .1, .25), 0, 0)
        focus = CameraPlanner(1920, 1080, aspect_ratio=4/3, anchor_x=.34).update([face], 0)
        center = CameraPlanner(1920, 1080, aspect_ratio=4/3).update([face], 0)
        face_center = (.4+.05)*1920
        self.assertAlmostEqual((face_center-focus["x"])/1440, .34, delta=.001)
        self.assertAlmostEqual((face_center-center["x"])/1440, .5, delta=.001)
        with self.assertRaises(ValueError):
            CameraPlanner(1920, 1080, anchor_x=float("nan"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class ReferenceRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.source = {}
        for preset_id in ("timothy_focus", "timothy_cinematic"):
            spec = template_spec(preset_id)
            target = cls.root / (preset_id+".mp4")
            cls.run_media(["-f", "lavfi", "-i", f"color=c=red:s={spec['width']}x{spec['height']}:r=30:d=7.2",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=7.2", "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", "-shortest", str(target)])
            cls.source[preset_id] = target
        cls.broll = cls.root / "broll.mp4"
        cls.run_media(["-f", "lavfi", "-i", "color=c=blue:s=640x360:r=30:d=4",
            "-f", "lavfi", "-i", "sine=frequency=1300:duration=4", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(cls.broll)])
        cls.music = cls.root / "music.wav"
        cls.run_media(["-f", "lavfi", "-i", "sine=frequency=220:duration=0.8", str(cls.music)])
        cls.campaign = {"assets": [{"id": "broll", "path": str(cls.broll), "role": "broll", "name": "blue",
            "sha256": file_sha256(cls.broll)}]}

    @classmethod
    def run_media(cls, arguments):
        return subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-threads", "2", *arguments],
            check=True, capture_output=True, timeout=120)

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

    def test_broll_assets_are_immutable_optional_and_not_appended_to_story(self):
        from test_workflow import Harness
        api = Harness(self.root / "workspace")
        draft = {"name": "Sinematik", "editing": {"preset_id": "timothy_cinematic"},
            "assets": [{"path": str(self.broll), "role": "broll", "required": True}]}
        saved = api.save_campaign_workspace(None, draft)
        self.assertEqual(saved["status"], "ok", saved)
        asset = saved["campaign"]["assets"][0]
        self.assertFalse(asset["required"])
        self.assertNotEqual(asset["path"], str(self.broll))
        self.assertEqual(file_sha256(asset["path"]), file_sha256(self.broll))
        self.assertTrue(saved["readiness"]["production_ready"], saved)
        plan = build_clip_plan({"source_id": "source", "path": str(self.source["timothy_cinematic"])},
            {"title": "Cerita", "start_time": "00:00:00,000", "end_time": "00:00:07,000"}, saved["campaign"])
        self.assertEqual(len(plan["segments"]), 1)
        asset["sha256"] = "invalid"
        with self.assertRaisesRegex(EditingValidationError, "berubah"):
            broll_plan(saved["campaign"], 7.2)
        missing = api.save_campaign_workspace(None, {"name": "Empty", "editing": {"preset_id": "timothy_cinematic"}})
        self.assertFalse(missing["readiness"]["production_ready"])
        self.assertTrue(any("B-roll" in item for item in missing["readiness"]["production_blockers"]))
        focus = api.save_campaign_workspace(None, {"name": "Focus", "editing": {"preset_id": "timothy_focus"}})
        self.assertTrue(focus["readiness"]["production_ready"])

    def test_real_broll_pixels_keep_original_speech_and_full_duration(self):
        import numpy as np
        final = self.root / "cinematic-layout.mp4"
        metadata = render_layout(self.source["timothy_cinematic"], final, "timothy_cinematic", self.campaign)
        info = probe_media(final)
        self.assertEqual((info["width"], info["height"]), (1920, 1080))
        self.assertAlmostEqual(info["duration"], 7.2, delta=.05)
        self.assertEqual(len(metadata["broll"]), 1)
        for seconds, channel in ((1, 2), (4, 0), (6.5, 2)):
            pixel = self.frame(final, seconds)[540, 960]
            self.assertGreater(int(pixel[channel]), 150)
        raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(final),
            "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"], capture_output=True, check=True, timeout=30).stdout
        samples = np.frombuffer(raw, dtype="<f4")
        for start in (1, 4, 6):
            window = samples[start*8000:(start+1)*8000]
            peak = np.fft.rfftfreq(len(window), 1/8000)[np.abs(np.fft.rfft(window)).argmax()]
            self.assertAlmostEqual(peak, 440, delta=2)
        shots = broll_plan(self.campaign, 4)
        self.assertLessEqual(shots[-1]["at_seconds"]+shots[-1]["duration_seconds"], 4)

    def test_real_focus_layout_and_caption_timing_have_no_black_tail(self):
        bordered, final = self.root / "focus-layout.mp4", self.root / "focus-captioned.mp4"
        render_layout(self.source["timothy_focus"], bordered, "timothy_focus")
        info = render_captions(bordered, final, {"words": [{"word": "TANGGUNG", "start": .3, "end": 1},
            {"word": "JAWAB", "start": 1, "end": 1.7}]}, "timothy_focus")
        self.assertAlmostEqual(info["duration"], 7.2, delta=.05)
        self.assertTrue(info["has_audio"])
        self.assertLess(int(self.frame(bordered, .5)[540, 1370, 2]), int(self.frame(bordered, .5)[540, 400, 2])-60)
        def glyph(seconds):
            return int((self.frame(final, seconds)[250:440, 600:1300].min(axis=2)>200).sum())
        self.assertEqual(glyph(.1), 0)
        self.assertGreater(glyph(.6), 2000)
        self.assertEqual(glyph(2), 0)
        self.assertGreater(int(self.frame(final, 7)[540, 400, 2]), 180)

    def test_cinematic_captions_use_phrase_timing_hierarchy_and_orange_takeaway(self):
        final = self.root / "cinematic-captioned.mp4"
        info = render_captions(self.source["timothy_cinematic"], final, {"words": [
            {"word": "semua", "start": .3, "end": .5}, {"word": "hal", "start": .5, "end": .9},
            {"word": "pemenang", "start": 1.4, "end": 2}, {"word": "lakukan", "start": 4, "end": 4.8}]}, "timothy_cinematic")
        self.assertAlmostEqual(info["duration"], 7.2, delta=.05)
        self.assertTrue(info["has_audio"])
        regular = self.frame(final, .6)[820:950].min(axis=2)>200
        self.assertGreater(regular.sum(), 2000)
        self.assertEqual((self.frame(final, 1.1).min(axis=2)>200).sum(), 0)
        hero = self.frame(final, 1.8)[675:850].min(axis=2)>200
        self.assertGreater(hero.sum(), 5000)
        takeaway = self.frame(final, 4.4)[675:850]
        orange = (takeaway[:, :, 2]>180) & (takeaway[:, :, 1]>50) & (takeaway[:, :, 1]<150) & (takeaway[:, :, 0]<75)
        self.assertGreater(orange.sum(), 5000)

    def test_broll_does_not_cover_the_campaign_endcard(self):
        from PIL import Image
        from services.editing import render_composition
        closing = self.root / "closing.png"
        Image.new("RGB", (640, 360), "lime").save(closing)
        composed, final = self.root / "with-endcard.mp4", self.root / "cinematic-endcard.mp4"
        render_composition([{"path": str(self.source["timothy_cinematic"]), "start_seconds": 0, "end_seconds": 3.8},
            {"path": str(closing), "start_seconds": 0, "end_seconds": 1, "is_image": True}], composed, width=1920, height=1080)
        metadata = render_layout(composed, final, "timothy_cinematic", self.campaign, story_duration=3.8)
        self.assertAlmostEqual(metadata["broll"][0]["duration_seconds"], .8)
        pixel = self.frame(final, 4.2)[540, 960]
        self.assertGreater(int(pixel[1]), 180)
        self.assertLess(int(pixel[0]), 50)
        self.assertLess(int(pixel[2]), 50)
        self.assertAlmostEqual(probe_media(final)["duration"], 4.8, delta=.05)

    def test_campaign_previews_use_native_renderers_and_show_broll_change(self):
        from test_workflow import Harness
        api = Harness(self.root / "previews")
        with patch("services.media_preview.MediaPreview") as preview:
            preview.return_value.register.side_effect = lambda path: str(path)
            for preset in ("timothy_focus", "timothy_cinematic"):
                result = api.get_template_preview(preset)
                self.assertEqual(result["status"], "ok", result)
                media = probe_media(result["preview_url"])
                self.assertEqual((media["width"], media["height"]), (template_spec(preset)["width"], 1080))
                self.assertAlmostEqual(media["duration"], 6, delta=.05)
                if preset == "timothy_cinematic":
                    early = self.frame(result["preview_url"], .1)[100, 100]
                    later = self.frame(result["preview_url"], 4)[100, 100]
                    self.assertGreater(abs(int(early[2])-int(later[2])), 20)

    def test_core_job_renders_both_templates_with_music_and_complete_source_range(self):
        from clipper_core import AutoClipperCore
        core = AutoClipperCore(client=None, output_dir=self.root / "jobs", log_callback=lambda *_: None)
        core.resume_dir = self.root / "jobs" / "test"
        source = self.source["timothy_cinematic"]
        source.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:01,800\nCerita selesai.\n", encoding="utf-8")
        core.campaign_config = normalize_campaign({"name": "Test", "brief": {"durasi_min": 1, "durasi_max": 4},
            "assets": self.campaign["assets"], "editing": {"selection_mode": "weighted_random", "template_pool": [
                {"preset_id": preset, "enabled": True, "weight": 50} for preset in ("timothy_focus", "timothy_cinematic")],
                "framing": "center", "music": {"policy": "local", "path": str(self.music)}}})
        core.highlight_overrides = [{"title": preset, "start_time": "00:00:00,000", "end_time": "00:00:01,800",
            "editing_template": choose_template({"editing": {"preset_id": preset}}, "test")}
            for preset in ("timothy_focus", "timothy_cinematic")]
        core._whisper_transcribe_words = lambda *_: SimpleNamespace(words=[SimpleNamespace(word="Bangkit", start=.2, end=1.7)], segments=[])
        options = campaign_processing_options(core.campaign_config, 2)
        options.pop("clip_mode")
        options.pop("subtitle_lang")
        options["highlight_finder"] = False
        try:
            core.process(str(source), dur_min=1, dur_max=4, **options)
            states = core.get_clips_state()
            self.assertTrue(all(item["status"] == "done" for item in states), states)
            self.assertEqual(len(states), 2)
            for index, preset in enumerate(("timothy_focus", "timothy_cinematic"), 1):
                directory = core.resume_dir / f"clip-{index:03d}"
                metadata = json.loads((directory/"data.json").read_text(encoding="utf-8"))
                self.assertEqual(metadata["template"]["id"], preset)
                self.assertTrue(metadata["music"]["mixed"])
                self.assertTrue(metadata["template_render"]["source_audio_preserved"])
                self.assertEqual(metadata["blockers"], [])
                self.assertEqual(metadata["source_ranges"][0]["end_seconds"], 1.8)
                self.assertAlmostEqual(metadata["duration_seconds"], 1.8, delta=.06)
                media = probe_media(directory/"master.mp4")
                self.assertEqual((media["width"], media["height"]), (template_spec(preset)["width"], 1080))
        finally:
            core.cleanup()


if __name__ == "__main__":
    unittest.main()
