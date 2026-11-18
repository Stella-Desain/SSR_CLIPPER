"""Campaign templates control new jobs without rewriting old work."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.campaigns import campaign_processing_options, normalize_campaign
from test_workflow import Harness


class CampaignEditingPresetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"isolated-source")

    def tearDown(self):
        self.tmp.cleanup()

    def campaign(self, **patch):
        response = self.api.save_campaign_workspace(None, {"name": "Film", "language": "en", **patch})
        self.assertEqual(response["status"], "ok", response)
        return response["campaign"]

    def queue(self, campaign, options=None):
        response = self.api.enqueue_sources([str(self.source)], campaign["id"], options)
        self.assertEqual(response["status"], "started", response)
        return self.api._get_store().get("job", response["jobs"][0])

    def test_standard_fixed_preset_ignores_old_feature_and_style_overrides(self):
        campaign = self.campaign(editing={"preset_id": "standard", "template_id": "bold",
            "template_mode": "ai_select", "add_captions": False, "add_hook": True,
            "features": {"highlight_finder": False}, "framing": "fit"})
        editing = campaign["editing"]
        self.assertEqual(editing["template_id"], "clean")
        self.assertEqual(editing["template_mode"], "fixed")
        self.assertEqual(editing["preset_version"], 1)
        self.assertEqual(editing["framing"], "fit")
        self.assertNotIn("add_hook", editing)
        self.assertNotIn("features", editing)
        presets = self.api.get_campaign_editing_presets()["presets"]
        self.assertEqual([p["id"] for p in presets], ["standard", "podcast_square", "timothy_focus", "timothy_cinematic", "ruang_founder", "ruang_witness"])
        presets[0]["features"]["add_captions"] = False
        self.assertTrue(self.api.get_campaign_editing_presets()["presets"][0]["features"]["add_captions"])

    def test_podcast_square_selection_controls_job_and_survives_stale_form_options(self):
        campaign = self.campaign(editing={"preset_id": "podcast_square", "preset_name": "wrong",
            "template_id": "clean", "template_mode": "ai_select", "portrait": True,
            "add_captions": False, "add_hook": True})
        self.assertEqual(campaign["editing"]["preset_name"], "Podcast Kotak")
        self.assertEqual(campaign["editing"]["template_id"], "podcast_square")
        self.assertEqual(campaign["editing"]["template_mode"], "fixed")
        job = self.queue(campaign, {"num_clips": 4, "portrait": True, "add_captions": False,
            "add_hook": True, "subtitle_style": "minimal"})
        self.assertEqual(job["options"], {"num_clips": 4, "portrait": False,
            "highlight_finder": True, "add_captions": True, "yt_title_maker": True,
            "add_hook": False, "subtitle_lang": "en", "subtitle_style": "podcast_square", "clip_mode": "fixed"})
        self.api.save_campaign_workspace(campaign["id"], {"editing": {"preset_id": "standard"}})
        self.assertEqual(self.api._get_store().get("job", job["id"]), job)
        self.assertEqual(self.api.get_campaign_workspace(campaign["id"])["campaign"]["editing"]["template_id"], "clean")

    def test_podcast_revision_keeps_its_snapshot_template(self):
        campaign = self.campaign(editing={"preset_id": "podcast_square"})
        self.api._get_store().put("clip", "podcast", {"id": "podcast", "source_url": str(self.source),
            "source_id": "s", "campaign_id": campaign["id"], "campaign_snapshot": campaign,
            "highlight": {"title": "Saved title"}, "has_captions": True, "has_hook": False})
        response = self.api.rerender_clip("podcast", {"preset_id": "standard", "template_id": "clean", "portrait": True})
        self.assertEqual(response["status"], "ok", response)
        job = self.api._get_store().get("job", response["job_id"])
        self.assertEqual(job["campaign"]["editing"]["preset_id"], "podcast_square")
        self.assertEqual(job["options"]["subtitle_style"], "podcast_square")
        self.assertFalse(job["options"]["portrait"])

    def test_stale_create_options_cannot_override_campaign_and_count_is_kept(self):
        campaign = self.campaign()
        supplied = {"num_clips": 7, "add_captions": False, "add_hook": True, "portrait": False,
            "highlight_finder": False, "yt_title_maker": False, "subtitle_lang": "ja",
            "subtitle_style": "hormozi", "clip_mode": "ai", "unexpected": "ignored"}
        before = copy.deepcopy(supplied)
        job = self.queue(campaign, supplied)
        self.assertEqual(job["options"], {"num_clips": 7, "add_captions": True, "add_hook": False,
            "portrait": True, "highlight_finder": True, "yt_title_maker": True, "subtitle_lang": "en",
            "subtitle_style": "minimal", "clip_mode": "fixed"})
        self.assertEqual(supplied, before)
        self.assertEqual(job["campaign"]["version_id"], campaign["version_id"])

    def test_old_start_processing_signature_uses_campaign_preset(self):
        campaign = self.campaign()
        response = self.api.start_processing(str(self.source), 3, False, True, "ja", False,
            False, False, campaign["id"], "hormozi", "ai")
        self.assertEqual(response["status"], "started", response)
        job = self.api._get_store().get("job", response["jobs"][0])
        self.assertEqual(job["options"], campaign_processing_options(campaign, 3))

    def test_legacy_read_is_effective_but_does_not_mutate_config_or_queued_jobs(self):
        legacy = {"id": "old", "name": "Legacy", "status": "active", "language": "id",
                  "editing": {"template_id": "bold", "template_mode": "ai_select"}}
        self.api.cfg["campaigns"] = [copy.deepcopy(legacy)]
        queued = {"id": "legacy-job", "status": "paused", "campaign_id": "old", "campaign": legacy,
                  "options": {"add_captions": False, "add_hook": True, "subtitle_style": "hormozi"}}
        self.api._get_store().put("job", queued["id"], queued)
        viewed = self.api.get_campaign_workspace("old")
        self.assertEqual(viewed["campaign"]["editing"]["preset_id"], "standard")
        self.assertEqual(viewed["campaign"]["editing"]["template_id"], "clean")
        self.assertEqual(self.api.cfg["campaigns"], [legacy])
        self.assertEqual(self.api._get_store().get("job", queued["id"]), queued)
        self.api.control_job(queued["id"], "resume")
        resumed = self.api._get_store().get("job", queued["id"])
        self.assertEqual(resumed["campaign"], legacy)
        self.assertEqual(resumed["options"], queued["options"])

    def test_legacy_new_queue_records_matching_version_and_keeps_old_version(self):
        legacy = {"id": "old", "name": "Legacy", "status": "active", "version_id": "old:legacy",
                  "editing": {"template_id": "social"}}
        self.api.cfg["campaigns"] = [copy.deepcopy(legacy)]
        old_version = {"id": "old:legacy", "campaign_id": "old", "campaign": legacy}
        self.api._get_store().put("campaign_version", old_version["id"], old_version)
        job = self.queue(legacy)
        self.assertEqual(job["campaign"]["editing"]["template_id"], "clean")
        self.assertNotEqual(job["campaign"]["version_id"], "old:legacy")
        version = self.api._get_store().get("campaign_version", job["campaign"]["version_id"])
        self.assertEqual(version["campaign"]["editing"], job["campaign"]["editing"])
        self.assertEqual(self.api._get_store().get("campaign_version", "old:legacy"), old_version)
        self.assertEqual(self.api.cfg["campaigns"], [legacy])

    def test_later_campaign_edits_do_not_change_queued_settings(self):
        campaign = self.campaign(editing={"framing": "fit"})
        job = self.queue(campaign)
        self.api.save_campaign_workspace(campaign["id"], {"language": "ja", "editing": {"framing": "center"}})
        unchanged = self.api._get_store().get("job", job["id"])
        self.assertEqual(unchanged, job)
        self.assertEqual(unchanged["options"]["subtitle_lang"], "en")

    def test_new_revision_uses_fixed_preset_while_legacy_revision_keeps_style(self):
        campaign = self.campaign()
        for preset in (True, False):
            snapshot = copy.deepcopy(campaign)
            if not preset:
                snapshot["editing"].pop("preset_id")
                snapshot["editing"].pop("preset_version")
            clip = {"id": "clip", "source_url": str(self.source), "source_id": "s", "campaign_id": campaign["id"],
                    "campaign_snapshot": snapshot, "highlight": {"title": "Saved title"}, "has_captions": False,
                    "has_hook": True}
            self.api._get_store().put("clip", "clip", clip)
            result = self.api.rerender_clip("clip", {"preset_id": None, "template_id": "bold", "add_hook": True})
            self.assertEqual(result["status"], "ok", result)
            job = self.api._get_store().get("job", result["job_id"])
            self.assertEqual(job["campaign"]["editing"]["template_id"], "clean" if preset else "bold")
            self.assertEqual(job["options"]["add_captions"], preset)
            self.assertEqual(job["options"]["add_hook"], not preset)
            version = self.api._get_store().get("campaign_version", job["campaign"]["version_id"])
            self.assertEqual(version["campaign"]["editing"], job["campaign"]["editing"])

    def test_unknown_preset_and_invalid_counts_fail_before_creating_jobs(self):
        with self.assertRaises(ValueError):
            normalize_campaign({"editing": {"preset_id": "unknown"}})
        campaign = self.campaign()
        for count in (-1, 101, 1.5, True):
            response = self.api.enqueue_sources([str(self.source)], campaign["id"], {"num_clips": count})
            self.assertEqual(response["status"], "error", response)
        self.assertEqual(self.api._get_store().list("job"), [])

    def test_zero_count_selects_ai_count_without_changing_editing_features(self):
        campaign = self.campaign()
        job = self.queue(campaign, {"num_clips": 0, "clip_mode": "ai", "add_hook": True})
        self.assertEqual(job["options"]["num_clips"], 0)
        self.assertEqual(job["options"]["clip_mode"], "ai")
        self.assertFalse(job["options"]["add_hook"])

    def test_title_option_reaches_generated_highlights_without_an_extra_ai_call(self):
        from clipper_core import AutoClipperCore
        self.source.with_suffix(".srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nCerita yang lengkap.\n", encoding="utf-8")
        for title_enabled in (True, False):
            core = AutoClipperCore(client=None, output_dir=self.root / str(title_enabled), log_callback=lambda *_: None)
            core.highlight_overrides = [{"start_time": "00:00:00", "end_time": "00:00:02", "title": "Judul hasil AI"}]
            observed = []
            core.process_clip = lambda video, highlight, *args: observed.append(highlight["title"])
            with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": True, "duration": 2}):
                core.process(str(self.source), num_clips=1, add_captions=False, add_hook=False,
                             portrait=False, yt_title_maker=title_enabled, dur_min=1, dur_max=2)
            self.assertEqual(observed, ["Judul hasil AI" if title_enabled else "source 1"])


if __name__ == "__main__":
    unittest.main()
