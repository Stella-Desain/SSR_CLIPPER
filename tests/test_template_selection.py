"""Weighted campaign choices are stable across retries and preserve old jobs."""
import copy
from pathlib import Path
import tempfile
import unittest

from services.campaigns import normalize_campaign, campaign_processing_options
from services.template_selection import choose_template, normalize_template_selection
from test_workflow import Harness


def pool(standard=50, podcast=50, standard_enabled=True, podcast_enabled=True):
    return [{"preset_id": "standard", "enabled": standard_enabled, "weight": standard},
            {"preset_id": "podcast_square", "enabled": podcast_enabled, "weight": podcast}]


class TemplateSelectionTests(unittest.TestCase):
    def test_legacy_fixed_campaign_does_not_silently_enable_randomness(self):
        for preset_id in ("standard", "podcast_square"):
            campaign = normalize_campaign({"editing": {"preset_id": preset_id}})
            self.assertEqual(campaign["editing"]["selection_mode"], "fixed")
            self.assertNotIn("template_pool", campaign["editing"])
            self.assertEqual({choose_template(campaign, seed)["preset_id"] for seed in range(40)}, {preset_id})

    def test_invalid_pools_and_weights_are_rejected(self):
        invalid = [None, {}, [], pool(standard_enabled=False, podcast_enabled=False),
            [{"preset_id": "unknown", "enabled": True, "weight": 1}],
            [{"preset_id": {}, "enabled": True, "weight": 1}],
            [pool()[0], pool()[0]], [None]]
        for value in (None, "10", False, 0, -1, 101, float("nan"), float("inf"), 10 ** 500):
            invalid.append(pool(standard=value))
        for value in (None, "false", 1):
            invalid.append(pool(standard_enabled=value))
        for entries in invalid:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                normalize_campaign({"editing": {"template_pool": entries}})
        with self.assertRaises(ValueError):
            normalize_template_selection({"selection_mode": "weighted_random"})

    def test_disabled_templates_never_render_and_pool_is_copied(self):
        campaign = {"editing": {"template_pool": pool(standard_enabled=False)}}
        before = copy.deepcopy(campaign)
        choices = [choose_template(campaign, seed) for seed in range(120)]
        self.assertEqual({choice["preset_id"] for choice in choices}, {"podcast_square"})
        self.assertEqual(campaign, before)
        choices[0]["features"]["add_captions"] = False
        self.assertTrue(choose_template(campaign, 0)["features"]["add_captions"])

    def test_weighted_draw_is_reproducible_and_ignores_pool_order(self):
        campaign = {"editing": {"template_pool": pool(10, 90)}}
        reordered = copy.deepcopy(campaign)
        reordered["editing"]["template_pool"].reverse()
        selected = [choose_template(campaign, {"job": "job-a", "clip": i}) for i in range(1000)]
        repeated = [choose_template(reordered, {"clip": i, "job": "job-a"}) for i in range(1000)]
        self.assertEqual(selected, repeated)
        podcast_count = sum(item["preset_id"] == "podcast_square" for item in selected)
        self.assertGreater(podcast_count, 860)
        self.assertLess(podcast_count, 940)
        self.assertEqual({item["total_weight"] for item in selected}, {100})
        other_job = [choose_template(campaign, {"job": "job-b", "clip": i}) for i in range(40)]
        self.assertNotEqual(selected[:40], other_job)

    def test_decimal_relative_weights_are_supported_without_normalizing_them_to_percent(self):
        campaign = normalize_campaign({"editing": {"template_pool": pool(1.5, 4.5)}})
        record = choose_template(campaign, "one")
        self.assertEqual(record["total_weight"], 6)
        self.assertIn(record["weight"], (1.5, 4.5))

    def test_rerender_reuses_record_even_when_template_was_disabled_later(self):
        old = {"editing": {"template_pool": pool(podcast_enabled=False)}}
        record = choose_template(old, "original")
        modified = {"editing": {"template_pool": pool(standard_enabled=False)}}
        self.assertEqual(choose_template(modified, "new-job", existing=record), record)
        forged_features = copy.deepcopy(record)
        forged_features["features"]["add_hook"] = True
        self.assertFalse(choose_template(modified, "new-job", existing=forged_features)["features"]["add_hook"])
        for version in (True, 2, None):
            with self.assertRaises(ValueError):
                choose_template(modified, "new-job", existing={**record, "preset_version": version})

    def test_campaign_save_and_queue_take_an_immutable_pool_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = Harness(root)
            source = root / "source.mp4"
            source.write_bytes(b"isolated-source")
            response = api.save_campaign_workspace(None, {"name": "Acak", "editing": {
                "selection_mode": "weighted_random", "template_pool": pool(20, 80)}})
            self.assertEqual(response["status"], "ok", response)
            campaign = response["campaign"]
            queued = api.enqueue_sources([str(source)], campaign["id"], {"num_clips": 3})
            self.assertEqual(queued["status"], "started", queued)
            job = api._get_store().get("job", queued["jobs"][0])
            edited = api.save_campaign_workspace(campaign["id"], {"editing": {"template_pool": pool(99, 1)}})
            self.assertEqual(edited["status"], "ok", edited)
            self.assertEqual(api._get_store().get("job", job["id"]), job)
            self.assertEqual(job["campaign"]["editing"]["template_pool"], campaign["editing"]["template_pool"])
            self.assertNotEqual(edited["campaign"]["version_id"], campaign["version_id"])

    def test_processing_options_enable_analysis_for_pool_without_choosing_each_clip(self):
        campaign = normalize_campaign({"language": "id", "editing": {"template_pool": pool()}})
        options = campaign_processing_options(campaign, 6)
        self.assertTrue(options["highlight_finder"])
        self.assertTrue(options["yt_title_maker"])
        self.assertEqual(options["num_clips"], 6)
        self.assertFalse(options["add_hook"])


if __name__ == "__main__":
    unittest.main()
