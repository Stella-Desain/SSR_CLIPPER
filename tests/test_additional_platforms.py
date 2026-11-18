"""Scope must affect actual files, face eligibility, review and upload selection."""
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from services.additionals import applicable_additionals, normalize_additionals
from services.clip_variants import render_platform_variants, publication_media, verify_clip_files
from services.editing import file_sha256, EditingValidationError, probe_media
from services.campaigns import normalize_campaign
from test_campaign_additionals import addition
from test_workflow import Harness


class AdditionalPlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        self.logo = self.root / "logo.png";Image.new("RGBA", (80, 40), (255, 0, 0, 255)).save(self.logo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_platform_and_template_allow_deny_and_full_opacity(self):
        item = addition(self.logo)
        item.update(platforms=["tiktok"], template_scope="include", template_ids=["standard"])
        item["layout"]["opacity"] = .2
        campaign = normalize_campaign({"editing": {"additional": [item]}})
        self.assertEqual(campaign["editing"]["additional"][0]["images"][0]["layout"]["opacity"], 1)
        self.assertEqual(len(applicable_additionals(campaign, platform="tiktok")["items"]), 1)
        self.assertEqual(applicable_additionals(campaign, platform="instagram")["items"], [])
        campaign["editing"]["additional"][0].update(template_scope="exclude")
        self.assertEqual(applicable_additionals(campaign, platform="tiktok")["items"], [])
        for invalid in ({"platforms": ["youtube"]}, {"template_scope": "execute"}, {"template_ids": ["missing"]}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_additionals([{**item, **invalid}])

    def test_face_filter_only_blocks_its_platform_and_destination_controls_refill(self):
        from clipper_core import AutoClipperCore
        item = addition(self.logo, "face_filter");item["platforms"] = ["tiktok"]
        core = AutoClipperCore(client=None, output_dir=self.root / "out", log_callback=lambda *_: None)
        core.campaign_config = normalize_campaign({"brief": {"platforms": ["tiktok", "instagram"]}, "editing": {"additional": [item]}})
        with patch("services.target_faces.TargetFaceMatcher") as matcher:
            matcher.return_value.evaluate.return_value = {"required": True, "accepted": False, "targets": []}
            result = core._check_additional_faces("video.mp4", {"start_time": 0, "end_time": 3})
            self.assertTrue(result["accepted"])
            self.assertFalse(result["platforms"]["tiktok"]["accepted"])
            self.assertTrue(result["platforms"]["instagram"]["accepted"])
            core.campaign_config["render_platforms"] = ["tiktok"]
            result = core._check_additional_faces("video.mp4", {"start_time": 0, "end_time": 3})
            self.assertFalse(result["accepted"], "No IG escape when job targets TikTok only")
        core.cleanup()

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_real_variant_pixels_audio_duration_and_scope_selected_for_upload(self):
        import cv2
        final = self.root / "master.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=180x320:d=1.2:r=15", "-f", "lavfi", "-i", "sine=frequency=400:duration=1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(final)], capture_output=True, check=True, timeout=30)
        item = addition(self.logo);item["platforms"] = ["tiktok"]
        campaign = normalize_campaign({"editing": {"additional": [item]}})
        variants, eligible, marks, preferred = render_platform_variants(final, campaign["editing"]["additional"], {"accepted": True}, campaign)
        clip = {"path": str(final), "file_hash": file_sha256(final), "platform_variants": variants}
        verify_clip_files(clip)
        self.assertEqual(preferred, "tiktok")
        self.assertEqual(publication_media(clip, "IG"), publication_media(clip, "instagram"))
        self.assertEqual(marks[0]["opacity"], 1)
        for platform, red_expected in (("tiktok", True), ("instagram", False), ("youtube", False)):
            media = publication_media(clip, platform)
            cap = cv2.VideoCapture(media["path"]);ok, frame = cap.read();cap.release()
            self.assertTrue(ok)
            self.assertEqual(int(frame[-5, -5, 2]) > 180, red_expected)
            info = probe_media(media["path"])
            self.assertTrue(info["has_audio"]);self.assertAlmostEqual(info["duration"], 1.2, delta=.1)
        Path(variants["instagram"]["path"]).write_bytes(b"changed IG variant")
        with self.assertRaises(EditingValidationError):verify_clip_files(clip)

    def prepared_clip(self):
        campaign = self.api.save_campaign_workspace(None, {"name": "Demo", "audience_scope": "Motivasi", "account_ids": ["a", "b"]})["campaign"]
        self.api.accounts[1]["type"] = "instagram"
        for account, platform in (("a", "tiktok"), ("b", "instagram")):
            self.api.save_account_profile(account, {"audience_scope": "Motivasi", "platform": platform, "daily_limit": 2})
        files = {}
        for name in ("master", "tiktok", "instagram", "default"):
            path = self.root / (name + ".mp4");path.write_bytes(name.encode())
            files[name] = {"path": str(path), "file_hash": file_sha256(path), "watermarks": []}
        clip = self.api._register_clip(Path(files["master"]["path"]), {"title": "Story", "caption": "Story", "campaign_id": campaign["id"], "campaign_snapshot": campaign,
            "platform_variants": {key: value for key, value in files.items() if key != "master"}, "default_platform": "tiktok"})
        self.assertEqual(self.api.review_clip(clip["id"], {"action": "approve"})["status"], "ok")
        return clip, files, campaign

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_wrong_canvas_from_platform_renderer_is_rejected_before_replacing_master(self):
        final, wrong = self.root / "master.mp4", self.root / "wrong.mp4"
        for path, canvas in ((final, "180x320"), (wrong, "320x180")):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                f"color=blue:s={canvas}:d=0.4:r=15", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                capture_output=True, check=True, timeout=30)
        before = file_sha256(final)
        item = addition(self.logo)
        item["platforms"] = ["tiktok"]
        campaign = normalize_campaign({"editing": {"additional": [item]}})
        def faulty_renderer(_source, target, *_args):
            shutil.copyfile(wrong, target)
            return []
        with self.assertRaisesRegex(EditingValidationError, "Versi sosmed.*kanvas"):
            render_platform_variants(final, campaign["editing"]["additional"], {"accepted": True},
                                     campaign, renderer=faulty_renderer)
        self.assertEqual(file_sha256(final), before)

    def test_distribution_uses_reviewed_platform_file_and_detects_changed_variant(self):
        clip, files, _ = self.prepared_clip()
        result = self.api.preview_distribution([clip["id"]])
        self.assertEqual(result["status"], "ok", result)
        assignment = result["assignments"][0]
        self.assertEqual(assignment["clip_path"], files[assignment["platform"]]["path"])
        self.assertEqual(assignment["file_hash"], files[assignment["platform"]]["file_hash"])
        Path(files["instagram"]["path"]).write_bytes(b"altered after review")
        self.assertEqual(self.api.confirm_distribution(result["preview_id"])["status"], "error")
        self.assertEqual(self.api.review_clip(clip["id"], {"action": "approve"})["status"], "error")

    def test_face_ineligible_platform_is_never_assigned_and_variant_change_breaks_approval(self):
        clip, files, _ = self.prepared_clip()
        stored = self.api._get_store().get("clip", clip["id"])
        stored.update(platform_eligibility={"tiktok": False, "instagram": True})
        self.api._get_store().put("clip", clip["id"], stored)
        self.assertEqual(self.api.preview_distribution([clip["id"]])["status"], "error")
        self.assertEqual(self.api.review_clip(clip["id"], {"action": "approve"})["status"], "ok")
        result = self.api.preview_distribution([clip["id"]]);self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["assignments"][0]["platform"], "instagram")
        with self.assertRaises(EditingValidationError):publication_media(stored, "tiktok")
        # Metadata swaps are also included in approval, not only master bytes.
        stored = self.api._get_store().get("clip", clip["id"])
        stored["platform_variants"]["instagram"] = files["tiktok"]
        self.api._get_store().put("clip", clip["id"], stored)
        self.assertEqual(self.api.preview_distribution([clip["id"]])["status"], "error")


if __name__ == "__main__":unittest.main()
