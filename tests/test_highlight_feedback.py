"""Feedback is a local proposal input, independent of clip approval/publication."""
import copy
from pathlib import Path
import tempfile
import unittest

from test_workflow import Harness
from services.storage import file_digest


class HighlightFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.api = Harness(self.root)
        self.path = self.root / "master.mp4"
        self.path.write_bytes(b"rendered-file")
        self.clip = self.api._register_clip(self.path, {
            "title": "Tanggung jawab", "caption": "Cerita utuh", "campaign_id": "campaign-a",
            "campaign_version_id": "campaign-a:v1", "selection": {"profile_hash": "profile-v1"},
            "source_ranges": [{"start_seconds": 2, "end_seconds": 12}]})

    def tearDown(self):
        self.temp.cleanup()

    def record(self, **patch):
        return self.api.record_highlight_feedback(self.clip["id"], {
            "labels": ["needs_context"], "note": "Sertakan alasan pembicara.",
            "revision_id": self.clip["revision_id"], **patch})

    def test_feedback_keeps_approval_file_caption_and_campaign(self):
        approved = self.api.review_clip(self.clip["id"], {"action": "approve"})
        self.assertEqual(approved["status"], "ok", approved)
        self.clip = approved["clip"]
        before = copy.deepcopy(self.api._get_store().get("clip", self.clip["id"]))
        self.assertEqual(self.record()["status"], "ok")
        self.assertEqual(self.api._get_store().get("clip", self.clip["id"]), before)
        self.assertEqual(file_digest(self.path), before["file_hash"])
        self.assertEqual(self.api.cfg["campaigns"], [])
        item = self.api._highlight_feedback_for_campaign("campaign-a")[0]
        self.assertEqual(item["profile_hash"], "profile-v1")
        self.assertEqual(item["campaign_version_id"], "campaign-a:v1")
        self.assertNotIn("path", item)

    def test_resaving_is_idempotent_and_different_render_preserves_history(self):
        first = self.record()["feedback"]
        second = self.record(note="Butuh konteks sebelum kalimat ini.")["feedback"]
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.api._get_store().list("highlight_feedback")), 1)
        self.path.write_bytes(b"revised-render")
        self.clip = self.api._register_clip(self.path, {**self.clip, "clip_id": self.clip["id"]})
        third = self.record()["feedback"]
        self.assertNotEqual(third["id"], first["id"])
        self.assertEqual(len(self.api._get_store().list("highlight_feedback")), 2)

    def test_stale_review_and_changed_file_are_rejected(self):
        self.assertEqual(self.record(revision_id="outdated")["status"], "error")
        self.path.write_bytes(b"changed")
        self.assertEqual(self.record()["status"], "error")
        self.assertEqual(self.api._get_store().list("highlight_feedback"), [])

    def test_feedback_is_validated_and_separated_by_campaign(self):
        for payload in (None, {"labels": []}, {"labels": ["run_command"]},
                        {"labels": ["audience_fit", "off_topic"]},
                        {"labels": ["audience_fit"], "note": "x" * 2001}):
            self.assertEqual(self.api.record_highlight_feedback(self.clip["id"], payload)["status"], "error")
        self.assertEqual(self.record()["status"], "ok")
        self.assertEqual(self.api._highlight_feedback_for_campaign("campaign-b"), [])
        self.assertEqual(self.api._highlight_feedback_for_campaign("campaign-a", 0), [])


if __name__ == "__main__":
    unittest.main()
