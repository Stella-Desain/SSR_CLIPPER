"""Additional persistence, final-canvas scoping, real overlays and face matching."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image

from services.additionals import (applicable_additionals, normalize_additionals, read_image,
                                  render_watermarks, ratio_key)
from services.campaigns import normalize_campaign
from services.editing import EditingValidationError, file_sha256, probe_media
from test_workflow import Harness


def addition(path="", kind="watermark", ratios=None):
    item = {"id": "addition-1", "type": kind, "enabled": True, "ratios": ratios or ["9:16"],
            "image": {"path": str(path), "name": Path(path).name,
                      "sha256": file_sha256(path) if path and Path(path).is_file() else ""}}
    if kind == "watermark":
        item["layout"] = {"x": 1, "y": 1, "width": .2, "opacity": 1}
    return item


class AdditionalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.logo = self.root / "my logo.png"
        Image.new("RGBA", (80, 40), (255, 0, 0, 255)).save(self.logo)
        self.api = Harness(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_durable_image_version_and_incomplete_drafts(self):
        imported = self.api.import_additional_image(str(self.logo))
        self.assertEqual(imported["status"], "ok", imported)
        self.assertTrue(imported["preview_url"].startswith("data:image/png;base64,"))
        item = addition(self.logo)
        result = self.api.save_campaign_workspace(None, {"name": "Demo", "editing": {"additional": [item]}})
        self.assertEqual(result["status"], "ok", result)
        campaign = result["campaign"]
        asset = campaign["editing"]["additional"][0]["images"][0]["image"]
        self.assertNotEqual(asset["path"], str(self.logo))
        self.logo.unlink()
        self.assertEqual(read_image(asset)[1], asset["sha256"])
        self.assertEqual(campaign["assets"], [], "An Additional image must not become an inserted scene")
        draft = self.api.save_campaign_workspace(campaign["id"], {"editing": {"additional": [addition()]}})
        self.assertEqual(draft["status"], "ok", draft)
        self.assertFalse(draft["readiness"]["production_ready"])
        self.assertNotEqual(draft["version_id"], campaign["version_id"])
        old = self.api._get_store().get("campaign_version", campaign["version_id"])
        self.assertEqual(old["campaign"]["editing"]["additional"][0]["images"][0]["image"], asset)
        self.assertEqual(normalize_campaign(campaign)["editing"]["additional"][0]["images"][0]["image"], asset)

    def test_changed_image_fake_image_and_transparent_image_fail(self):
        item = addition(self.logo)
        Image.new("RGBA", (80, 40), (0, 255, 0, 255)).save(self.logo)
        with self.assertRaisesRegex(EditingValidationError, "berubah"):
            read_image(item["image"])
        self.logo.write_bytes(b"not a PNG")
        self.assertEqual(self.api.import_additional_image(str(self.logo))["status"], "error")
        Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(self.logo)
        self.assertEqual(self.api.import_additional_image(str(self.logo))["status"], "error")

    def test_invalid_settings_rejected_and_ratio_is_output_not_source(self):
        for patch_value in ({"type": "execute"}, {"ratios": ["source"]}, {"ratios": "16:9"},
                            {"enabled": "false"}, {"layout": {"width": 0}}, {"layout": {"x": float("nan")}},
                            {"image": {"path": "photo.png", "sha256": "bad"}}):
            with self.subTest(patch_value=patch_value), self.assertRaises(EditingValidationError):
                normalize_additionals([{**addition(self.logo), **patch_value}])
        campaign = normalize_campaign({"editing": {"additional": [addition(self.logo, ratios=["32:18"])]}})
        self.assertEqual(campaign["editing"]["additional"][0]["ratios"], ["16:9"])
        self.assertEqual(applicable_additionals(campaign)["items"], [])
        wide = applicable_additionals(campaign, canvas={"width": 1920, "height": 1080})
        self.assertEqual(len(wide["items"]), 1)
        campaign["editing"]["additional"][0]["enabled"] = False
        self.assertEqual(applicable_additionals(campaign, canvas={"width": 1920, "height": 1080})["items"], [])
        self.assertEqual(ratio_key(720, 720), "1:1")

    def test_inactive_ratios_and_disabled_additions_do_not_block_unrelated_templates(self):
        wide = addition("missing.png", "face_filter", ratios=["16:9"])
        result = self.api.save_campaign_workspace(None, {"name": "Wide later", "editing": {"additional": [wide]}})
        self.assertEqual(result["status"], "ok", result)
        self.assertTrue(result["readiness"]["production_ready"], result)
        self.assertTrue(result["readiness"]["warnings"])
        wide["enabled"] = False;wide["ratios"] = ["9:16"]
        disabled = self.api.save_campaign_workspace(result["campaign"]["id"], {"editing": {"additional": [wide]}})
        self.assertTrue(disabled["readiness"]["production_ready"], disabled)

    def test_clip_revision_cannot_remove_campaign_face_filter_or_watermark(self):
        campaign = self.api.save_campaign_workspace(None, {"name": "Demo", "editing": {"additional": [addition(self.logo)]}})["campaign"]
        self.api._get_store().put("clip", "clip", {"id": "clip", "source_url": str(self.logo), "source_id": "source",
            "campaign_id": campaign["id"], "campaign_snapshot": campaign,
            "highlight": {"start_time": "00:00:00", "end_time": "00:00:03", "title": "Demo"}})
        result = self.api.rerender_clip("clip", {"additional": []})
        self.assertEqual(result["status"], "ok", result)
        job = self.api._get_store().get("job", result["job_id"])
        self.assertEqual(job["campaign"]["editing"]["additional"], normalize_additionals(campaign["editing"]["additional"]))

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_real_watermark_alpha_position_audio_and_duration_on_three_ratios(self):
        import cv2
        # Transparent half verifies the compositor respects image alpha.
        logo = Image.new("RGBA", (80, 40), (0, 0, 0, 0))
        logo.paste((255, 0, 0, 255), (0, 0, 40, 40))
        logo.save(self.logo)
        for width, height in ((320, 180), (180, 320), (240, 240)):
            with self.subTest(width=width, height=height):
                source, output = self.root / f"{width}.mp4", self.root / f"wm-{width}.mp4"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=blue:s={width}x{height}:d=1.2:r=15",
                    "-f", "lavfi", "-i", "sine=frequency=400:duration=1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)],
                    capture_output=True, check=True, timeout=30)
                evidence = render_watermarks(source, output, normalize_additionals([addition(self.logo)]))
                actual = probe_media(output)
                self.assertTrue(actual["has_audio"])
                self.assertAlmostEqual(actual["duration"], 1.2, delta=.1)
                mark = evidence[0]
                self.assertEqual(mark["x"]+mark["width"], width)
                self.assertEqual(mark["y"]+mark["height"], height)
                cap = cv2.VideoCapture(str(output))
                ok, frame = cap.read(); cap.release()
                self.assertTrue(ok)
                left = frame[mark["y"]+mark["height"]//2, mark["x"]+mark["width"]//4]
                right = frame[mark["y"]+mark["height"]//2, mark["x"]+mark["width"]*3//4]
                self.assertGreater(int(left[2]), 180)
                self.assertLess(int(left[0]), 70)
                self.assertGreater(int(right[0]), 180)

    def test_filter_refills_count_keeps_choice_and_resume_checks_gate_again(self):
        from clipper_core import AutoClipperCore
        source = self.root / "source.mp4"; source.write_bytes(b"offline source fixture")
        source.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:03,000\nCerita satu selesai.\n\n2\n00:00:03,000 --> 00:00:06,000\nCerita dua selesai.\n", encoding="utf-8")
        campaign = normalize_campaign({"brief": {"durasi_min": 1, "durasi_max": 4}, "editing": {
            "selection_mode": "weighted_random", "template_pool": [{"preset_id": "standard", "enabled": True, "weight": 50}],
            "additional": [addition(self.logo, "face_filter")]}})
        candidates = [{"start_time": "00:00:00,000", "end_time": "00:00:03,000", "title": "Wrong person"},
                      {"start_time": "00:00:03,000", "end_time": "00:00:06,000", "title": "Target person"}]
        observed, checked = [], []
        def evaluate(video, h, targets, **kwargs):
            checked.append(h["title"])
            return {"required": True, "accepted": h["title"] == "Target person", "targets": []}
        for attempt in range(2):
            core = AutoClipperCore(client=None, output_dir=self.root / "renders", log_callback=lambda *_: None)
            core.resume_dir = self.root / "renders" / "job-test"
            core.campaign_config = copy.deepcopy(campaign)
            core._find_campaign_highlights = lambda *_: copy.deepcopy(candidates)
            core.process_clip = lambda _, h, *_args: observed.append(copy.deepcopy(h))
            with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": False, "duration": 6}), \
                    patch("services.target_faces.TargetFaceMatcher") as matcher:
                matcher.return_value.evaluate.side_effect = evaluate
                core.process(str(source), num_clips=1, fixed_count=1, dur_min=1, dur_max=4)
        self.assertEqual([h["title"] for h in observed], ["Target person", "Target person"])
        self.assertEqual(observed[0]["editing_template"], observed[1]["editing_template"])
        self.assertEqual(checked, ["Wrong person", "Target person", "Target person"])
        plan = json.loads((core.resume_dir / "highlights.json").read_text())
        self.assertEqual(len(plan["additional_rejections"]), 1)

    def test_render_rechecks_gate_before_any_renderer_and_keeps_watermark_after_template(self):
        from clipper_core import AutoClipperCore
        core = AutoClipperCore(client=None, output_dir=self.root / "render", log_callback=lambda *_: None)
        core.campaign_config = normalize_campaign({"editing": {"additional": [addition(self.logo)]}})
        core.source_analysis = {"source_id": "source", "path": str(self.logo)}
        core._caption_lock = threading.Lock()
        h = {"start_time": "00:00:00,000", "end_time": "00:00:03,000", "duration_seconds": 3, "title": "Story"}
        calls = []
        def base(*args, **kwargs):
            directory = core.output_dir / "clip-001";directory.mkdir(parents=True)
            (directory / "master.mp4").write_bytes(b"base")
            calls.append("base")
        def captions(source, target, **kwargs):
            shutil.copyfile(source, target);calls.append("captions")
        def overlay(source, target, items, *_):
            shutil.copyfile(source, target);calls.append("watermark");return [{"id": items[0]["id"]}]
        def music(source, settings, target, *_):
            shutil.copyfile(source, target);calls.append("music");return {"mixed": True, "sha256": "fixture"}
        core._render_clip_base = base
        core.add_captions_api_with_progress = captions
        core.music_selector_callback = lambda *_: {"path": str(self.logo)}
        with patch.object(core, "_check_additional_faces", return_value={"required": True, "accepted": False}):
            with self.assertRaises(EditingValidationError):
                core.process_clip(str(self.logo), copy.deepcopy(h), 1)
        self.assertEqual(calls, [])
        with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": True, "duration": 3, "width": 1080, "height": 1920}), \
                patch("services.clip_variants.probe_media", return_value={"has_video": True, "has_audio": True, "duration": 3, "width": 1080, "height": 1920}), \
                patch("services.core_workflow.render_watermarks", side_effect=overlay), \
                patch("services.core_workflow.mix_music", side_effect=music), \
                patch("services.music_review.verify_music_balance", return_value={"warnings": []}), \
                patch("services.core_workflow.analyze_audio", return_value={"warnings": []}):
            result = core.process_clip(str(self.logo), h, 1, add_hook=False)
        self.assertEqual(calls, ["base", "captions", "music", "watermark"])
        meta = json.loads((result / "data.json").read_text())
        self.assertEqual(meta["additional"]["watermarks"], [{"id": "addition-1"}])
        self.assertIn("instagram", meta["platform_variants"])
        self.assertIn("tiktok", meta["platform_variants"])
        core.cleanup()


class RealTargetFaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from services.target_faces import model_root
        cls.fixtures = Path(__file__).resolve().parents[1] / "output" / "additional-proof"
        if not (model_root() / "face_recognition_sface_2021dec.onnx").exists() or not (cls.fixtures / "messi5.jpg").exists():
            raise unittest.SkipTest("Local OpenCV models and official sample photos required; no test downloads")

    def test_identity_positive_negative_multiple_faces_and_blank_video(self):
        import cv2
        import numpy as np
        from services.target_faces import TargetFaceMatcher
        matcher = TargetFaceMatcher()
        target = addition(self.fixtures / "lena.jpg", "face_filter")
        _, reference = matcher.reference(target["image"])
        _, other = matcher.reference(addition(self.fixtures / "messi5.jpg", "face_filter")["image"])
        self.assertGreater(matcher.recognizer.match(reference, reference, cv2.FaceRecognizerSF_FR_COSINE), .99)
        self.assertLess(matcher.recognizer.match(reference, other, cv2.FaceRecognizerSF_FR_COSINE), .363)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            face = Image.open(self.fixtures / "lena.jpg").convert("RGB").resize((256, 256))
            double = Image.new("RGB", (512, 256));double.paste(face);double.paste(face, (256, 0));double.save(root / "two.png")
            with self.assertRaisesRegex(EditingValidationError, "tepat satu"):
                matcher.reference({"path": str(root / "two.png")})
            video = root / "faces.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (512, 512))
            self.assertTrue(writer.isOpened())
            for frame in (cv2.imread(str(self.fixtures / "lena.jpg")), cv2.resize(cv2.imread(str(self.fixtures / "messi5.jpg")), (512, 512)), np.zeros((512, 512, 3), np.uint8)):
                for _ in range(40):writer.write(frame)
            writer.release()
            for start, expected in ((0, True), (4, False), (8, False)):
                result = matcher.evaluate(video, {"start_time": start, "end_time": start+4}, [target])
                self.assertEqual(result["accepted"], expected, result)
                self.assertEqual(result["source_sha256"], file_sha256(video))


if __name__ == "__main__":
    unittest.main()
