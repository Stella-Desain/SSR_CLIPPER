import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_workflow import Harness
from services.editing import file_sha256, mix_music
from services.music_review import verify_music_balance


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
class MusicReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_temp = tempfile.TemporaryDirectory()
        cls.media = Path(cls.media_temp.name)
        cls.dry = cls.media / "dry.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=green:s=160x90:d=3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-threads", "2",
            "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.dry)], check=True, capture_output=True)
        for number, hz in enumerate((220, 880)):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={hz}:duration=6",
                str(cls.media / f"song{number}.wav")], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.media_temp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        final = self.root / "master.mp4"
        music = mix_music(self.dry, {"path": str(self.media / "song0.wav"), "volume": .4,
            "ducking": False, "fade_seconds": 0, "start_seconds": 0,
            "attribution": {"id": "first", "name": "First", "artist": "A"}}, final)
        music["selection"] = {"alternatives": [{"candidate_id": "other:0", "id": "other", "name": "Other", "artist": "B",
            "start": 1, "end": 4, "path": str(self.media / "song1.wav"),
            "sha256": file_sha256(self.media / "song1.wav"), "score": 85, "reason": "Different passage"}]}
        self.clip = self.api._register_clip(final, {"title": "Music review", "caption": "Clip\nMusik: First \u2014 A",
            "campaign_id": "c", "campaign_snapshot": {}, "music": music,
            "dry_master": {"path": str(self.dry), "sha256": file_sha256(self.dry)}, "duration_seconds": 3})
        self.payload = {"revision_id": self.clip["revision_id"], "candidate_id": "other:0", "start_seconds": 1,
                        "volume": .5, "ducking": False}

    def tearDown(self):
        if hasattr(self.api, "_media_preview"):
            self.api._media_preview.close()
        self.tmp.cleanup()

    def test_actual_encoded_mix_has_selected_music_not_just_an_audio_track(self):
        balance = verify_music_balance(self.dry, self.clip["path"], self.clip["music"])
        self.assertTrue(balance["selected_music_present"], balance)
        self.assertAlmostEqual(balance["music_to_source_db"], -8, delta=3)
        self.assertFalse(verify_music_balance(self.dry, self.dry, self.clip["music"])["selected_music_present"])

    def test_preview_and_revision_reuse_dry_picture_without_touching_approved_original(self):
        self.clip = self.api.review_clip(self.clip["id"], {"action": "approve"})["clip"]
        self.payload["revision_id"] = self.clip["revision_id"]
        before = copy.deepcopy(self.api._get_store().get("clip", self.clip["id"]))
        preview = self.api.preview_clip_music(self.clip["id"], self.payload)
        self.assertEqual(preview["status"], "ok", preview)
        self.assertEqual(preview["music"]["attribution"]["id"], "other")
        self.assertTrue(preview["balance"]["selected_music_present"])
        result = self.api.apply_clip_music(self.clip["id"], self.payload)
        self.assertEqual(result["status"], "ok", result)
        new = result["clip"]
        self.assertNotEqual(new["id"], self.clip["id"])
        self.assertEqual(new["review_status"], "pending")
        self.assertIsNone(new["approval_hash"])
        self.assertEqual(new["final_sha256"], new["file_hash"])
        self.assertEqual(file_sha256(new["dry_master"]["path"]), file_sha256(self.dry))
        self.assertEqual(self.api._get_store().get("clip", self.clip["id"]), before)
        self.assertEqual(file_sha256(before["path"]), before["file_hash"])
        self.assertIn("Musik: Other", new["caption"])

    def test_invalid_stale_or_arbitrary_candidate_never_renders(self):
        for patch in ({"revision_id": "old"}, {"candidate_id": "invented"}, {"volume": 0},
                      {"volume": float("nan")}, {"start_seconds": -1}, {"ducking": "false"}):
            with self.subTest(patch=patch):
                result = self.api.preview_clip_music(self.clip["id"], {**self.payload, **patch})
                self.assertEqual(result["status"], "error", result)
        clip = self.api._get_store().get("clip", self.clip["id"])
        clip.pop("dry_master")
        self.api._get_store().put("clip", clip["id"], clip)
        self.assertIn("Master tanpa musik", self.api.preview_clip_music(clip["id"], self.payload)["message"])

    def test_feedback_does_not_change_clip_approval_and_rejects_stale_review(self):
        before = self.api._get_store().get("clip", self.clip["id"])
        payload = {"revision_id": self.clip["revision_id"], "labels": ["too_quiet", "vocal_clash"], "note": "Test"}
        self.assertEqual(self.api.record_music_feedback(self.clip["id"], payload)["status"], "ok")
        self.assertEqual(self.api._get_store().get("clip", self.clip["id"]), before)
        for patch in ({"labels": ["good_fit", "too_quiet"]}, {"revision_id": "stale"}, {"labels": []}):
            self.assertEqual(self.api.record_music_feedback(self.clip["id"], {**payload, **patch})["status"], "error")

    def test_manual_start_does_not_claim_an_old_semantic_passage_was_heard(self):
        clip = self.api._get_store().get("clip", self.clip["id"])
        clip["music"]["selection"].update(audio_window={"start": 0, "end": 3},
            semantic={"observations": [{"start": 0, "end": 2}], "coverage": 1, "phrase_aligned": True})
        self.api._get_store().put("clip", clip["id"], clip)
        _, _, music = self.api._music_review_input(clip["id"], {**self.payload, "candidate_id": "", "start_seconds": 3})
        self.assertEqual(music["selection"]["audio_window"]["start"], 3)
        self.assertEqual(music["selection"]["semantic"]["coverage"], 0)
        self.assertEqual(music["selection"]["semantic"]["observations"], [])


if __name__ == "__main__":
    unittest.main()
