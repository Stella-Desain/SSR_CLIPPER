"""Integration boundaries for mixed template jobs and immutable clip revisions."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from services.campaigns import normalize_campaign
from services.editing import build_clip_plan, EditingValidationError
from services.template_selection import choose_template
from test_workflow import Harness


def entries(standard=True, podcast=True):
    return [{"preset_id": "standard", "enabled": standard, "weight": 50},
            {"preset_id": "podcast_square", "enabled": podcast, "weight": 50}]


class TemplatePoolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"offline-render-fixture")
        self.api = Harness(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def campaign(self, editing=None):
        result = self.api.save_campaign_workspace(None, {"name": "Test", "brief": {
            "durasi_min": 1, "durasi_max": 10}, "editing": editing or {
                "selection_mode": "weighted_random", "template_pool": entries()}})
        self.assertEqual(result["status"], "ok", result)
        return result["campaign"]

    def highlight(self, preset_id="standard"):
        selected = choose_template({"editing": {"template_pool": entries(
            preset_id == "standard", preset_id == "podcast_square")}}, "original")
        return {"start_time": "00:00:00,000", "end_time": "00:00:02,000",
                "duration_seconds": 2, "title": "Cerita", "editing_template": selected}

    def store_clip(self, campaign, highlight):
        self.api._get_store().put("clip", "clip", {"id": "clip", "source_url": str(self.source),
            "source_id": "source", "campaign_id": campaign["id"], "campaign_snapshot": campaign,
            "highlight": highlight, "editing_template": highlight.get("editing_template")})

    def test_plan_uses_recorded_preset_even_if_campaign_fallback_and_ai_suggestion_differ(self):
        campaign = self.campaign()
        before = copy.deepcopy(campaign)
        source = {"source_id": "source", "path": str(self.source)}
        for preset, template in (("standard", "clean"), ("podcast_square", "podcast_square")):
            highlight = self.highlight(preset)
            highlight["template_id"] = "bold"
            plan = build_clip_plan(source, highlight, campaign)
            self.assertEqual(plan["template"]["id"], template)
            self.assertEqual(plan["template_selection"]["preset"], highlight["editing_template"])
            self.assertEqual(campaign, before)
        broken = self.highlight()
        broken["editing_template"]["preset_version"] = 99
        with self.assertRaises(EditingValidationError):
            build_clip_plan(source, broken, campaign)

    def test_random_clip_revision_ignores_injected_pool_features_and_choice(self):
        campaign, highlight = self.campaign(), self.highlight("standard")
        self.store_clip(campaign, highlight)
        response = self.api.rerender_clip("clip", {"template_pool": entries(False, True),
            "selection_mode": "fixed", "preset_id": None, "template_id": "bold",
            "features": {"add_hook": True}, "editing_template": self.highlight("podcast_square")["editing_template"]})
        self.assertEqual(response["status"], "ok", response)
        job = self.api._get_store().get("job", response["job_id"])
        self.assertEqual(job["campaign"]["editing"]["template_pool"], campaign["editing"]["template_pool"])
        self.assertEqual(job["campaign"]["editing"]["selection_mode"], "weighted_random")
        self.assertEqual(job["highlight_overrides"], [highlight])
        self.assertFalse(job["options"]["add_hook"])
        self.assertEqual(choose_template(job["campaign"], "changed-job", highlight["editing_template"])["preset_id"], "standard")

    def test_fixed_clip_revision_cannot_be_converted_by_injecting_a_random_pool(self):
        campaign, highlight = self.campaign({"preset_id": "standard"}), self.highlight("standard")
        highlight.pop("editing_template")
        self.store_clip(campaign, highlight)
        response = self.api.rerender_clip("clip", {"template_pool": entries(False, True),
            "selection_mode": "weighted_random", "preset_id": "podcast_square"})
        self.assertEqual(response["status"], "ok", response)
        job = self.api._get_store().get("job", response["job_id"])
        self.assertNotIn("template_pool", job["campaign"]["editing"])
        self.assertEqual(job["campaign"]["editing"]["selection_mode"], "fixed")
        self.assertEqual(job["options"]["subtitle_style"], "minimal")

    def test_new_job_ignores_ai_selected_template_and_retry_reuses_saved_choices(self):
        from clipper_core import AutoClipperCore
        self.source.with_suffix(".srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nCerita selesai.\n", encoding="utf-8")
        campaign = self.campaign({"selection_mode": "weighted_random", "template_pool": entries(True, False)})
        observed = []
        for attempt in range(2):
            core = AutoClipperCore(client=None, output_dir=self.root / "renders", log_callback=lambda *_: None)
            core.resume_dir = self.root / "renders" / "job-test"
            core.campaign_config = copy.deepcopy(campaign)
            core._find_campaign_highlights = lambda *_: [self.highlight("podcast_square")]
            core.process_clip = lambda _video, h, *_args: observed.append(copy.deepcopy(h["editing_template"]))
            with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": False, "duration": 2}):
                core.process(str(self.source), num_clips=1, dur_min=1, dur_max=2)
            plan = json.loads((core.resume_dir / "highlights.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["highlights"][0]["editing_template"]["preset_id"], "standard")
        self.assertEqual(observed[0], observed[1])

    def test_each_render_uses_its_own_features_and_persists_record_without_mutating_campaign(self):
        from clipper_core import AutoClipperCore
        core = AutoClipperCore(client=None, output_dir=self.root / "mixed", log_callback=lambda *_: None)
        core.campaign_config = self.campaign()
        before = copy.deepcopy(core.campaign_config)
        core.source_analysis = {"source_id": "source", "path": str(self.source), "url": str(self.source)}
        core._caption_lock = threading.Lock()
        rendered, caption_styles = [], []
        def base(video, highlight, index, total, captions, hook, precut, portrait, campaign_id, counter, transcript, style):
            rendered.append({"portrait": portrait, "hook": hook, "style": style})
            directory = core.output_dir / f"clip-{index:03d}"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "master.mp4").write_bytes(f"render-{index}".encode())
        def captions(source, target, progress_callback, subtitle_style):
            caption_styles.append(subtitle_style)
            shutil.copyfile(source, target)
        core._render_clip_base = base
        core.add_captions_api_with_progress = captions
        # This test stubs all media bytes; audible music is checked in real-FFmpeg tests.
        core.music_selector_callback = lambda *_: {"path": str(self.source)}
        def mix(source, settings, target, *_args):
            shutil.copyfile(source, target)
            return {**settings, "mixed": True, "sha256": "music-fixture"}
        media = {"duration": 2, "width": 720, "height": 720, "has_video": True, "has_audio": True}
        try:
            with patch("services.core_workflow.probe_media", side_effect=lambda *_args: {
                    **media, **({"width": 1080, "height": 1920} if rendered[-1]["portrait"] else {})}), \
                    patch("services.core_workflow.analyze_audio", return_value={"warnings": []}), \
                    patch("services.music_review.verify_music_balance", return_value={"warnings": []}), \
                    patch("services.core_workflow.mix_music", side_effect=mix), \
                    patch("services.podcast_template.render_layout", side_effect=lambda source, target, *_args, **_kwargs: shutil.copyfile(source, target)):
                for index, preset_id in enumerate(("standard", "podcast_square"), 1):
                    core.process_clip(str(self.source), self.highlight(preset_id), index, 2,
                        add_captions=False, add_hook=True, portrait=False)
                    metadata = json.loads((core.output_dir / f"clip-{index:03d}" / "data.json").read_text(encoding="utf-8"))
                    self.assertTrue(metadata["has_captions"])
                    self.assertFalse(metadata["has_hook"])
                    self.assertEqual(metadata["editing_template"]["preset_id"], preset_id)
                    self.assertEqual(metadata["highlight"]["editing_template"], metadata["editing_template"])
            self.assertEqual([item["portrait"] for item in rendered], [True, False])
            self.assertEqual(caption_styles, ["minimal", "podcast_square"])
            self.assertEqual(core.campaign_config, before)
        finally:
            core.cleanup()

    def test_revision_process_preserves_stored_template_when_new_job_seed_would_choose_another(self):
        from clipper_core import AutoClipperCore
        from services.editing import fingerprint_source
        self.source.with_suffix(".srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nCerita selesai.\n", encoding="utf-8")
        campaign, highlight = self.campaign(), self.highlight("standard")
        self.store_clip(campaign, highlight)
        response = self.api.rerender_clip("clip", {})
        self.assertEqual(response["status"], "ok", response)
        job = self.api._get_store().get("job", response["job_id"])
        source_id = fingerprint_source(str(self.source))["source_id"]
        for suffix in range(100):
            dirname = f"revision-{suffix}"
            alternate = choose_template(campaign, f"{dirname}:{source_id}:1:00:00:00,000:00:00:02,000")
            if alternate["preset_id"] == "podcast_square":
                break
        self.assertEqual(alternate["preset_id"], "podcast_square")
        core = AutoClipperCore(client=None, output_dir=self.root / "revisions", log_callback=lambda *_: None)
        core.resume_dir = self.root / "revisions" / dirname
        core.campaign_config = job["campaign"]
        core.highlight_overrides = copy.deepcopy(job["highlight_overrides"])
        observed = []
        core.process_clip = lambda _video, h, *_args: observed.append(copy.deepcopy(h["editing_template"]))
        with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": False, "duration": 2}):
            core.process(str(self.source), num_clips=1, dur_min=1, dur_max=2)
        self.assertEqual(observed, [highlight["editing_template"]])
        plan = json.loads((core.resume_dir / "highlights.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["highlights"][0]["editing_template"], highlight["editing_template"])

    def test_no_builtin_template_finalizes_when_base_renderer_returns_original_landscape(self):
        from clipper_core import AutoClipperCore
        from services.editing import TEMPLATES
        core = AutoClipperCore(client=None, output_dir=self.root / "bad-render", log_callback=lambda *_: None)
        core.source_analysis = {"source_id": "source", "path": str(self.source)}
        finalized = []
        core.finalize_callback = lambda *_args: finalized.append(True)
        def bad_base(*_args, **_kwargs):
            directory = core.output_dir / "clip-001"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "master.mp4").write_bytes(b"original-landscape")
        core._render_clip_base = bad_base
        highlight = self.highlight()
        highlight.pop("editing_template")
        try:
            for template_id in TEMPLATES:
                with self.subTest(template=template_id):
                    core.campaign_config = {"editing": {"template_id": template_id}}
                    with patch("services.core_workflow.probe_media", return_value={
                            "width": 480, "height": 270, "has_video": True, "has_audio": True, "duration": 2}), \
                            self.assertRaisesRegex(EditingValidationError, "kanvas"):
                        core.process_clip(str(self.source), highlight, 1, add_captions=False, add_hook=False)
                    self.assertFalse((core.output_dir / "clip-001" / "data.json").exists())
            self.assertEqual(finalized, [])
        finally:
            core.cleanup()

    def test_later_editing_stage_cannot_replace_valid_crop_with_original_source(self):
        from clipper_core import AutoClipperCore
        core = AutoClipperCore(client=None, output_dir=self.root / "bad-caption", log_callback=lambda *_: None)
        core.campaign_config = {"editing": {"template_id": "clean"}}
        core.source_analysis = {"source_id": "source", "path": str(self.source)}
        core._caption_lock = threading.Lock()
        finalized = []
        core.finalize_callback = lambda *_args: finalized.append(True)
        core.music_selector_callback = lambda *_args: {"path": str(self.source)}
        def base(*_args, **_kwargs):
            directory = core.output_dir / "clip-001"
            directory.mkdir(parents=True)
            (directory / "master.mp4").write_bytes(b"correct-portrait")
        def faulty_captions(_source, target, **_kwargs):
            Path(target).write_bytes(b"original-landscape")
        def media(path, *_args):
            width, height = (1080, 1920) if Path(path).read_bytes() == b"correct-portrait" else (480, 270)
            return {"width": width, "height": height, "duration": 2, "has_video": True, "has_audio": True}
        def music(source, _settings, target, *_args):
            shutil.copyfile(source, target)
            return {"mixed": True, "sha256": "fixture"}
        core._render_clip_base = base
        core.add_captions_api_with_progress = faulty_captions
        highlight = self.highlight()
        highlight.pop("editing_template")
        try:
            with patch("services.core_workflow.probe_media", side_effect=media), \
                    patch("services.core_workflow.mix_music", side_effect=music), \
                    patch("services.music_review.verify_music_balance", return_value={"warnings": []}), \
                    self.assertRaisesRegex(EditingValidationError, "Render final.*kanvas"):
                core.process_clip(str(self.source), highlight, 1, add_hook=False)
            self.assertEqual(finalized, [])
            self.assertFalse((core.output_dir / "clip-001" / "data.json").exists())
        finally:
            core.cleanup()


if __name__ == "__main__":
    unittest.main()
