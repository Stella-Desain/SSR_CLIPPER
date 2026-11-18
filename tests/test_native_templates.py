"""Native design portability, production selection and real FFmpeg rendering."""
import copy
import json
import math
from pathlib import Path
import shutil
import subprocess
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from template_sdk.ssr_template_engine import TemplateError, inspect_package, install_package, load_template
from template_sdk.ssr_template_engine.design import (new_design, validate_design, export_design_package,
    load_design, render_design, timing_bounds, write_layer_ass, subtitle_words_from_file)
from services.campaigns import normalize_campaign, campaign_processing_options
from services.editing import build_clip_plan
from services.external_templates import resolve_preset
from services.template_selection import choose_template


class NativePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.model = new_design("Native portable", "16:9", "design-test")
        self.package, self.library = self.root / "design.ssrtemplate", self.root / "library"

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, version=1):
        manifest = export_design_package(self.model, self.root, self.package, version=version)
        directory, _ = install_package(self.package, self.library)
        return directory, manifest

    def test_sample_and_editor_state_never_bundled(self):
        self.model["preview"].update(video_path="E:/author/private.mp4", title="Private sample transcript")
        self.model.update(revision=10, published_versions=[1], archived=False)
        directory, manifest = self.publish()
        with zipfile.ZipFile(self.package) as archive:
            payload = archive.read("design.json").decode()
            self.assertNotIn("private", payload)
            self.assertNotIn("preview", payload)
            self.assertNotIn("revision", payload)
            self.assertEqual(set(archive.namelist()), {"manifest.json", "design.json"})
        self.assertEqual(manifest, inspect_package(self.package))
        self.assertEqual(load_design(directory)["id"], self.model["id"])

    def test_asset_portable_after_author_deleted_and_checksum_immutable(self):
        asset = self.root / "assets" / "logo.png"
        asset.parent.mkdir()
        asset.write_bytes(b"fixture image")
        self.model["assets"] = [{"id": "logo", "kind": "image", "path": "assets/logo.png", "url": "http://127.0.0.1/private"}]
        self.model["layers"].append({"id": "image", "type": "image", "asset_id": "logo", "x": 10, "y": 20, "width": 100, "height": 100})
        directory, manifest = self.publish()
        asset.unlink()
        self.assertEqual(load_template(directory), manifest)
        self.assertNotIn("url", load_design(directory)["assets"][0])
        (directory / "assets/logo.png").write_bytes(b"changed")
        with self.assertRaisesRegex(TemplateError, "changed"):
            load_template(directory)

    def test_same_version_cannot_replace_other_design(self):
        self.publish()
        self.model["canvas"]["background"] = "#ffffff"
        with self.assertRaisesRegex(TemplateError, "new version"):
            self.publish()
        self.publish(version=2)

    def test_invalid_noncontinuous_source_and_unsupported_rotation_rejected(self):
        for change in ({"timing": {"mode": "start", "start": 0, "duration": 30}}, {"rotation": 10}, {"framing": "speaker"}):
            model = copy.deepcopy(self.model)
            model["layers"][0].update(change)
            with self.assertRaises(TemplateError):
                validate_design(model)

    def test_asset_traversal_and_missing_asset_rejected(self):
        for path in ("../outside.png", "assets/missing.png"):
            self.model["assets"] = [{"id": "logo", "kind": "image", "path": path}]
            with self.assertRaises(TemplateError):
                self.publish()

    def test_native_campaign_fixed_random_and_versions_snapshot(self):
        self.publish()
        with patch("services.external_templates.library_root", return_value=self.library):
            preset_id = "design:design-test:v1"
            preset = resolve_preset(preset_id)
            self.assertFalse(preset["features"]["portrait"], "Native video box owns crop; preserve original source")
            for editing in ({"preset_id": preset_id}, {"template_pool": [{"preset_id": preset_id, "enabled": True, "weight": 50}]}):
                campaign = normalize_campaign({"editing": editing})
                choice = choose_template(campaign, "job:clip")
                plan = build_clip_plan({"source_id": "source"}, {"start_time": "00:00:00", "end_time": "00:01:10", "editing_template": choice}, campaign)
                self.assertEqual(plan["template"]["id"], preset_id)
                self.assertEqual(plan["template"]["external_template"]["engine"], "design")
                self.assertFalse(campaign_processing_options(campaign)["add_captions"])
                self.assertEqual(choose_template(campaign, "different", existing=choice), choice)
            model = json.loads((self.library / "design-test-v1/manifest.json").read_text())
            model["name"] = "Tampered"
            (self.library / "design-test-v1/manifest.json").write_text(json.dumps(model))
            with self.assertRaises(TemplateError):
                choose_template(campaign, "retry")

    def test_relative_timing_scales_all_source_lengths(self):
        for duration in (15, 45, 70, 120):
            self.assertEqual(timing_bounds({"mode": "full", "start": 0, "duration": 30}, duration), (0, duration))
            self.assertEqual(timing_bounds({"mode": "end", "start": 0, "duration": 2}, duration), (duration-2, duration))
            self.assertEqual(timing_bounds({"mode": "percent", "start": 25, "duration": 50}, duration), (duration*.25, duration*.75))

    def test_new_campaign_inherits_native_audio_but_existing_explicit_values_win(self):
        self.model["audio"].update(music_volume=.12, ducking=False, fade_in=.4, fade_out=2)
        self.publish()
        with patch("services.external_templates.library_root", return_value=self.library):
            for supplied, volume, ducking, inherits_fade in (({}, .12, False, True),
                    ({"volume": .15, "ducking": True, "fade_seconds": 1}, .15, True, False)):
                campaign = normalize_campaign({"editing": {"preset_id": "design:design-test:v1", "music": supplied}})
                plan = build_clip_plan({"source_id": "source"}, {"start_time": "00:00:00", "end_time": "00:00:20"}, campaign)
                self.assertEqual(plan["music"]["volume"], volume)
                self.assertEqual(plan["music"]["ducking"], ducking)
                self.assertEqual("fade_in" in plan["music"], inherits_fade)
                self.assertTrue(plan["music"]["required"])
                if inherits_fade:
                    self.assertEqual(plan["music"]["fade_out"], 2)

    def test_ass_colors_text_escaping_and_geometry_clip(self):
        model = self.model
        layer = {"id": "caption", "type": "subtitle", "x": 20, "y": 30, "width": 400, "height": 100,
            "highlight_color": "#bcff32", "color": "#ffffff"}
        model["layers"].append(layer)
        layer = validate_design(model)["layers"][-1]
        path = self.root / "caption.ass"
        write_layer_ass(path, layer, model["canvas"], 2, words=[{"word": "{bad}", "start": 0, "end": 1}, {"word": "good", "start": 1, "end": 2}])
        text = path.read_text()
        self.assertIn(r"\c&H32ffbc&", text)
        self.assertIn(r"\clip(20.00,30.00,420.00,130.00)", text)
        self.assertIn(r"\{bad\}", text)

    def test_subtitles_from_srt_do_not_become_sample_in_package(self):
        path = self.root / "words.srt"
        path.write_text("1\n00:00:00,000 --> 00:00:02,000\nDua kata\n\n", encoding="utf-8")
        words = subtitle_words_from_file(path)
        self.assertEqual([w["word"] for w in words], ["Dua", "kata"])
        self.assertEqual(words[-1]["end"], 2)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class NativeActualRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / "source.mp4", self.root / "out.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x80:r=30:d=3.2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3.2", "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(self.source)], check=True, capture_output=True)
        self.model = new_design("Test", "16:9")
        self.model["canvas"].update(width=320, height=180, background="#ff0000")
        self.model["layers"][0].update(width=160, height=160, x=80, y=10, fit="contain")
        self.model["preview"]["duration"] = .1

    def tearDown(self):
        self.temp.cleanup()

    def test_full_duration_audio_and_transparent_contain_and_end_element(self):
        self.model["layers"].append({"id": "end", "type": "rect", "x": 0, "y": 0, "width": 40, "height": 40,
            "color": "#00ff00", "timing": {"mode": "end", "start": 0, "duration": 1}})
        result = render_design(self.model, self.root, self.source, self.output)
        self.assertGreaterEqual(result["duration_seconds"], 3.2)
        self.assertTrue(result["source_audio_preserved"])
        self.assertFalse(result["editor_required"])
        def pixel(time, x, y):
            data = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(time), "-i", str(self.output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
            offset = (y*320+x)*3
            return data[offset:offset+3]
        # Padding inside the video box must be transparent to the red canvas.
        self.assertGreater(pixel(.5, 100, 20)[0], 220)
        self.assertGreater(pixel(.5, 100, 80)[2], 220)
        self.assertGreater(pixel(.5, 20, 20)[0], 220)
        self.assertGreater(pixel(2.8, 20, 20)[1], 220)

    def test_cancel_retains_previous_output(self):
        self.output.write_bytes(b"previous-good-output")
        event = threading.Event()
        event.set()
        with self.assertRaisesRegex(TemplateError, "dibatalkan"):
            render_design(self.model, self.root, self.source, self.output, cancel_event=event)
        self.assertEqual(self.output.read_bytes(), b"previous-good-output")

    def test_actual_packaged_font_active_word_is_green(self):
        font = Path("C:/Windows/Fonts/arial.ttf")
        if not font.is_file():
            self.skipTest("Arial unavailable on this host")
        target = self.root / "assets" / "arial.ttf"
        target.parent.mkdir()
        shutil.copy2(font, target)
        self.model["assets"] = [{"id": "arial", "kind": "font", "path": "assets/arial.ttf", "font_family": "Arial"}]
        self.model["layers"].append({"id": "caption", "type": "subtitle", "x": 20, "y": 70, "width": 280, "height": 100,
            "font_size": 28, "font_family": "Arial", "font_asset_id": "arial", "outline_width": 1, "words_per_group": 2})
        render_design(self.model, self.root, self.source, self.output, subtitle_words=[
            {"word": "KATA", "start": 0, "end": 1}, {"word": "AKTIF", "start": 1, "end": 2}])
        data = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.4", "-i", str(self.output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        green = sum(1 for r,g,b in zip(data[0::3], data[1::3], data[2::3]) if g > 190 and r < 205 and b < 130)
        self.assertGreater(green, 40, "Active words must use the design's green highlight, not fallback white")

    def test_sample_music_voice_gain_and_mix_preserve_both_frequencies(self):
        music = self.root / "music.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=880:duration=5", str(music)], check=True, capture_output=True)
        self.model["audio"].update(voice_volume=.5, music_volume=.3, ducking=False, fade_in=.1, fade_out=.1)
        result = render_design(self.model, self.root, self.source, self.output, music_path=music)
        self.assertTrue(result["music_mixed"])
        self.assertGreaterEqual(result["duration_seconds"], 3.2)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", str(self.output), "-t", "0.5", "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
        samples = struct.unpack("<" + "f"*(len(raw)//4), raw)
        def amplitude(frequency):
            cosine = sum(sample*math.cos(2*math.pi*frequency*i/16000) for i,sample in enumerate(samples))
            sine = sum(sample*math.sin(2*math.pi*frequency*i/16000) for i,sample in enumerate(samples))
            return 2*math.hypot(cosine, sine)/len(samples)
        self.assertGreater(amplitude(440), .02, "Speech/source audio must remain audible")
        self.assertLess(amplitude(440), .085, "Native voice gain must be applied")
        self.assertGreater(amplitude(880), .005, "Music bed must be present")

    def test_sample_thirty_seconds_never_caps_fifteen_fortyfive_seventy_or_onehundredtwenty(self):
        self.model["preview"]["duration"] = 30
        self.model["canvas"]["fps"] = 12
        for duration in (15, 45, 70, 120):
            with self.subTest(duration=duration):
                source = self.root / f"source-{duration}.mp4"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=blue:s=160x80:r=12:d={duration}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-pix_fmt", "yuv420p", str(source)], check=True, capture_output=True)
                result = render_design(self.model, self.root, source, self.output)
                self.assertGreaterEqual(result["duration_seconds"], duration)
                self.assertLess(result["duration_seconds"], duration+.12)
                raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(duration-.3), "-i", str(self.output), "-t", "0.2", "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
                samples = struct.unpack("<" + "f"*(len(raw)//4), raw)
                self.assertTrue(samples)
                self.assertGreater(math.sqrt(sum(sample*sample for sample in samples)/len(samples)), .03, "Final source audio must survive beyond sample duration")


if __name__ == "__main__":
    unittest.main()
