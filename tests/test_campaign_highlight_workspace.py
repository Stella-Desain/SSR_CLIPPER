"""Campaign finder drafts, immutable examples, and explicit suggestions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.campaigns import CampaignMixin, normalize_campaign
from services.editing import build_clip_plan
from services.highlight_profiles import normalize_highlight_profile, profile_fingerprint
from services.highlight_references import HighlightReferenceAnalyzer
from services.storage import WorkflowStore


class Harness(CampaignMixin):
    def __init__(self, root):
        self.config_file = str(root / "config.json")
        self.cfg = {"campaigns": [], "ai_providers": {"brief_extractor": {"api_key": "test-only", "model": "test-only"}}}
        self.store = WorkflowStore(root / "workflow.sqlite")
        self.feedback = []

    def _get_cfg(self):
        return copy.deepcopy(self.cfg)

    def _get_store(self):
        return self.store

    def _get_cfg_manager(self):
        return self

    def save_config(self, value):
        self.cfg = copy.deepcopy(value)

    def _highlight_feedback_for_campaign(self, campaign_id, limit=50):
        return copy.deepcopy(self.feedback[:limit])


MEDIA = {"duration": 30, "has_video": True, "has_audio": True, "width": 768, "height": 576, "fps": 30}


class CampaignHighlightWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        self.video = self.root / "example.mp4"
        self.video.write_bytes(b"test-reference-video")
        self.sidecar = self.video.with_suffix(".srt")
        self.sidecar.write_text("1\n00:00:00,000 --> 00:00:05,000\nPilih tanggung jawab.\n\n2\n00:00:05,000 --> 00:00:20,000\nKarena keputusan memiliki akibat.\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def reference(self):
        return self.api._inspect_campaign_file({"path": str(self.video), "role": "reference_highlight", "required": True})

    def draft(self, reference=None):
        return {"name": "Tanggung jawab", "audience_scope": "Ambisi dan tanggung jawab", "language": "id",
                "brief": {"tujuan": "Dorong tindakan yang bertanggung jawab"},
                "assets": [reference] if reference else []}

    def proposal(self, reference=None):
        profile = {"audience": "Orang yang mencari dorongan bertanggung jawab", "objective": "Gagasan utuh tentang tanggung jawab",
                   "topics": ["tanggung jawab"], "hook_patterns": ["Teguran personal"],
                   "reference_analyses": []}
        if reference:
            profile["reference_analyses"] = [{"asset_id": reference["id"], "sha256": reference["sha256"],
                "summary": "Keputusan membawa akibat yang harus ditanggung.", "topics": ["tanggung jawab"],
                "patterns": ["Teguran lalu alasan"]}]
        return profile

    def test_legacy_campaign_gets_audience_defaults_and_manual_profile_persists(self):
        draft = self.draft()
        self.assertEqual(normalize_campaign(draft)["highlight_profile"]["audience"], draft["audience_scope"])
        draft["highlight_profile"] = self.proposal()
        saved = self.api.save_campaign_workspace(None, draft)
        self.assertEqual(saved["status"], "ok", saved)
        self.assertEqual(saved["campaign"]["highlight_profile"]["topics"], ["tanggung jawab"])

    def test_profile_change_creates_snapshot_without_rewriting_previous(self):
        first = self.api.save_campaign_workspace(None, {**self.draft(), "highlight_profile": self.proposal()})
        old = first["version_id"]
        new = self.api.save_campaign_workspace(first["campaign"]["id"], {"highlight_profile": {"topics": ["ambisi"]}})
        self.assertEqual(new["status"], "ok", new)
        self.assertNotEqual(old, new["version_id"])
        prior = self.api.store.get("campaign_version", old)["campaign"]
        self.assertEqual(prior["highlight_profile"]["topics"], ["tanggung jawab"])
        self.assertNotEqual(profile_fingerprint(prior["highlight_profile"]), profile_fingerprint(new["campaign"]["highlight_profile"]))

    def test_reference_and_srt_import_are_immutable_and_not_timeline(self):
        ref = self.reference()
        self.assertFalse(ref["required"])
        saved = self.api.save_campaign_workspace(None, {**self.draft(ref), "highlight_profile": self.proposal(ref)})
        self.assertEqual(saved["status"], "ok", saved)
        imported = saved["campaign"]["assets"][0]
        self.assertNotEqual(imported["path"], str(self.video))
        self.assertNotEqual(imported["transcript"]["path"], str(self.sidecar))
        self.video.write_bytes(b"changed source")
        self.sidecar.unlink()
        self.assertEqual(Path(imported["path"]).read_bytes(), b"test-reference-video")
        self.assertTrue(Path(imported["transcript"]["path"]).is_file())
        plan = build_clip_plan({"source_id": "source", "path": "source.mp4", "sha256": None},
                              {"start_time": "00:00:00,000", "end_time": "00:00:20,000"}, saved["campaign"])
        self.assertEqual([segment["kind"] for segment in plan["segments"]], ["source"])

    def test_unknown_or_changed_reference_is_rejected(self):
        ref = self.reference()
        self.video.write_bytes(b"changed")
        result = self.api.save_campaign_workspace(None, self.draft(ref))
        self.assertEqual(result["status"], "error")
        self.assertIn("berubah", result["message"])
        wrong = self.root / "fake.png"
        wrong.write_bytes(b"image")
        with self.assertRaisesRegex(ValueError, "file video"):
            self.api._inspect_campaign_file({"path": str(wrong), "role": "reference_highlight"})

    def test_summary_must_match_campaign_reference_identity(self):
        ref = self.reference()
        profile = self.proposal(ref)
        profile["reference_analyses"][0]["sha256"] = "0" * 64
        result = self.api.save_campaign_workspace(None, {**self.draft(ref), "highlight_profile": profile})
        self.assertEqual(result["status"], "error")
        self.assertIn("Ringkasan referensi", result["message"])

    def test_brief_only_suggestion_is_whitelisted_and_does_not_save(self):
        proposal = {**self.proposal(), "editing": {"music": {"policy": "none"}}, "account_ids": ["evil"], "command": "publish"}
        draft = self.draft()
        original = copy.deepcopy(draft)
        with patch.object(self.api, "_highlight_profile_ai", return_value=proposal):
            result = self.api.suggest_highlight_profile({"campaign": draft})
        self.assertEqual(result["status"], "ok", result)
        self.assertNotIn("editing", result["profile"])
        self.assertNotIn("command", result["profile"])
        self.assertEqual(self.api.cfg["campaigns"], [])
        self.assertEqual(draft, original)

    def test_missing_profile_provider_stops_before_transcription(self):
        self.api.cfg["ai_providers"] = {}
        with patch("services.highlight_references.HighlightReferenceAnalyzer.analyze") as analyze:
            result = self.api.suggest_highlight_profile({"campaign": self.draft(self.reference())})
        self.assertEqual(result["status"], "error")
        self.assertIn("Brief Extractor", result["message"])
        analyze.assert_not_called()

    def test_reference_suggestion_contains_speech_rules_and_trusted_feedback_only(self):
        ref = self.reference()
        self.api.feedback = [{"clip_id": "stored", "labels": ["off_topic"], "note": "Terlalu umum"}]
        draft = {**self.draft(ref), "id": "campaign-id"}
        with patch("services.highlight_references.probe_media", return_value=MEDIA), \
                patch.object(self.api, "_highlight_profile_ai", return_value=self.proposal(ref)) as ai:
            result = self.api.suggest_highlight_profile({"campaign": draft, "feedback": [{"note": "caller instruction"}]})
        self.assertEqual(result["status"], "ok", result)
        self.assertIn("00:00:05,000", ai.call_args.args[1][0]["transcript"])
        self.assertEqual(ai.call_args.args[2], self.api.feedback)
        self.assertEqual(result["profile"]["reference_analyses"][0]["asset_id"], ref["id"])
        self.assertEqual(result["references"][0]["transcription_source"], "subtitle_file")
        self.assertEqual(self.api.cfg["campaigns"], [])

    def test_ai_cannot_invent_reference_or_drop_one(self):
        ref = self.reference()
        forged = self.proposal(ref)
        forged["reference_analyses"][0]["asset_id"] = "not-a-reference"
        with patch("services.highlight_references.probe_media", return_value=MEDIA), \
                patch.object(self.api, "_highlight_profile_ai", return_value=forged):
            result = self.api.suggest_highlight_profile({"campaign": self.draft(ref)})
        self.assertEqual(result["status"], "error")
        self.assertIn("setiap video referensi", result["message"])

    def test_path_only_reference_suggestion_can_be_applied_and_saved(self):
        ref = self.reference()
        draft = self.draft({"path": str(self.video), "role": "reference_highlight"})
        with patch("services.highlight_references.probe_media", return_value=MEDIA), \
                patch.object(self.api, "_highlight_profile_ai", return_value=self.proposal(ref)):
            result = self.api.suggest_highlight_profile({"campaign": draft})
        self.assertEqual(result["status"], "ok", result)
        draft["highlight_profile"] = result["profile"]
        saved = self.api.save_campaign_workspace(None, draft)
        self.assertEqual(saved["status"], "ok", saved)
        self.assertEqual(saved["campaign"]["assets"][0]["id"], ref["id"])


class HighlightReferenceCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        self.video = self.root / "example.mp4"
        self.video.write_bytes(b"test-video")
        self.sidecar = self.video.with_suffix(".srt")
        self.sidecar.write_text("1\n00:00:01,000 --> 00:00:03,000\nLakukan sampai selesai.\n", encoding="utf-8")
        self.ref = self.api._inspect_campaign_file({"path": str(self.video), "role": "reference_highlight"})
        self.analyzer = HighlightReferenceAnalyzer(self.api.cfg, self.root / "cache", ffmpeg="ffmpeg")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cached_transcript_reused_but_changed_sidecar_refused(self):
        with patch("services.highlight_references.probe_media", return_value=MEDIA) as probe:
            first = self.analyzer.analyze(self.ref)
            second = self.analyzer.analyze(self.ref)
        self.assertEqual(first, second)
        self.assertEqual(probe.call_count, 1)
        self.sidecar.write_text("tampered")
        with self.assertRaisesRegex(ValueError, "transkrip berubah"):
            self.analyzer.analyze(self.ref)

    def test_invalid_cached_ranges_are_recomputed(self):
        with patch("services.highlight_references.probe_media", return_value=MEDIA):
            self.analyzer.analyze(self.ref)
        cache = next((self.root / "cache").glob("*.json"))
        data = json.loads(cache.read_text())
        data["analysis"]["transcript"] = "[00:00:40,000 - 00:00:50,000] Invented."
        cache.write_text(json.dumps(data))
        with patch("services.highlight_references.probe_media", return_value=MEDIA) as probe:
            result = self.analyzer.analyze(self.ref)
        probe.assert_called_once()
        self.assertIn("Lakukan", result["transcript"])

    def test_settings_and_language_change_cache_identity(self):
        with patch("services.highlight_references.probe_media", return_value=MEDIA) as probe:
            self.analyzer.analyze(self.ref, "id")
            self.analyzer.analyze(self.ref, "en")
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(len(list((self.root / "cache").glob("*.json"))), 2)
        self.assertIsNone(self.analyzer._settings("auto")["language"])
        self.assertIsNone(self.analyzer._settings("none")["language"])

    def test_out_of_video_or_missing_timestamps_fail_actionably(self):
        self.sidecar.write_text("1\n00:00:35,000 --> 00:00:40,000\nDi luar video.\n", encoding="utf-8")
        ref = self.api._inspect_campaign_file({"path": str(self.video), "role": "reference_highlight"})
        with patch("services.highlight_references.probe_media", return_value=MEDIA):
            with self.assertRaisesRegex(ValueError, "di luar video"):
                self.analyzer.analyze(ref)
        self.sidecar.write_text("Tidak ada timestamp.")
        ref = self.api._inspect_campaign_file({"path": str(self.video), "role": "reference_highlight"})
        with patch("services.highlight_references.probe_media", return_value=MEDIA):
            with self.assertRaisesRegex(ValueError, "bertimestamp"):
                self.analyzer.analyze(ref)

    def test_offline_whisper_never_auto_downloads(self):
        self.sidecar.unlink()
        ref = self.api._inspect_campaign_file({"path": str(self.video), "role": "reference_highlight"})
        analyzer = HighlightReferenceAnalyzer({"ai_providers": {"whisper_model": "tiny"}}, self.root / "cache", ffmpeg="ffmpeg")
        with patch("services.highlight_references.probe_media", return_value=MEDIA), \
                patch("faster_whisper.WhisperModel", side_effect=FileNotFoundError("not cached")) as model:
            with self.assertRaisesRegex(ValueError, "sudah diunduh"):
                analyzer.analyze(ref, "none")
        self.assertTrue(model.call_args.kwargs["local_files_only"])


if __name__ == "__main__":
    unittest.main()
