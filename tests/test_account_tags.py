"""Platform-scoped mentions from campaign save through exact upload captions."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from services.account_tags import publication_caption, normalize_account_tags, append_mentions
from services.campaigns import normalize_campaign, merge_extractions
from services.publishing import plan_distribution
from test_workflow import Harness


class AccountTagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.api = Harness(self.root)
        self.api.accounts[1]["type"] = "instagram"
        result = self.api.save_campaign_workspace(None, {"name": "Scoped tags", "audience_scope": "Film", "account_ids": ["a", "b"],
            "brief": {"hashtags": ["#film"], "cta": "Ikuti kami", "tagged_accounts_by_platform": {"tiktok": ["@tiktok_brand"], "instagram": ["@ig_brand"]}}})
        self.assertEqual(result["status"], "ok", result); self.campaign = result["campaign"]
        for aid, platform in (("a", "tiktok"), ("b", "instagram")):
            self.api.save_account_profile(aid, {"platform": platform, "audience_scope": "Film", "daily_limit": 2})

    def tearDown(self):
        self.tmp.cleanup()

    def create_clip(self):
        path = self.root / "master.mp4"; path.write_bytes(b"offline video fixture")
        result = self.api._finalize_workflow_clip(self.root, {"title": "Cerita", "description": "Cerita bagus", "final_path": str(path)},
            {"id": "job", "campaign_id": self.campaign["id"], "campaign": self.campaign, "source": "source.mp4"})
        return self.api._get_store().get("clip", result["clip_id"])

    def test_save_migrate_and_empty_platform_do_not_resurrect_shared_mentions(self):
        legacy = normalize_campaign({"brief": {"tagged_accounts": ["@legacy", "@LEGACY"]}})
        self.assertEqual(legacy["brief"]["tagged_accounts_by_platform"], {"tiktok": ["@legacy"], "instagram": ["@legacy"]})
        self.assertEqual(legacy["brief"]["tagged_accounts"], [])
        explicit = normalize_campaign({"brief": {"tagged_accounts": ["@old"], "tagged_accounts_by_platform": {"tiktok": [], "instagram": ["ig"]}}})
        self.assertEqual(explicit["brief"]["tagged_accounts_by_platform"], {"tiktok": [], "instagram": ["@ig"]})
        for bad in (None, [], {"youtube": []}, {"tiktok": "@a"}, {"tiktok": [3]}, {"tiktok": ["two accounts"]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_account_tags({"tagged_accounts_by_platform": bad})
        old = self.api._get_store().get("campaign_version", self.campaign["version_id"])
        self.api.save_campaign_workspace(self.campaign["id"], {"brief": {"tagged_accounts_by_platform": {"tiktok": [], "instagram": []}}})
        self.assertEqual(old["campaign"]["brief"]["tagged_accounts_by_platform"], self.campaign["brief"]["tagged_accounts_by_platform"])

    def test_finalize_review_and_distribution_use_only_destination_mentions(self):
        clip = self.create_clip()
        self.assertNotIn("@", clip["caption"])
        self.assertIn("@tiktok_brand", clip["captions"]["tiktok"]); self.assertNotIn("@ig_brand", clip["captions"]["tiktok"])
        self.assertIn("@ig_brand", clip["captions"]["instagram"]); self.assertNotIn("@tiktok_brand", clip["captions"]["instagram"])
        approved = self.api.review_clip(clip["id"], {"action": "approve"})
        self.assertEqual(approved["status"], "ok", approved)
        now = datetime(2026, 9, 27, 0, tzinfo=timezone.utc)
        for account in self.api.accounts:
            planned = plan_distribution([approved["clip"]], [self.campaign], self.api._get_store().list("account_profile"), [account], [], now)
            platform = account["type"]
            self.assertEqual(planned[0]["caption"], clip["captions"][platform])
        broken = copy.deepcopy(clip["captions"]); broken["instagram"] = "Cerita bagus #film Ikuti kami @tiktok_brand"
        reviewed = self.api.review_clip(clip["id"], {"captions": broken, "action": "approve"})
        self.assertEqual(reviewed["status"], "ok", reviewed)
        self.assertEqual(reviewed["clip"]["captions"], clip["captions"])

    def test_base_caption_edit_refreshes_every_destination_and_invalidates_preview(self):
        clip = self.create_clip()
        approved = self.api.review_clip(clip["id"], {"action": "approve"})
        self.assertEqual(approved["status"], "ok", approved)
        preview = self.api.preview_distribution([clip["id"]])
        self.assertEqual(preview["status"], "ok", preview)
        caption = "Cerita yang diperbaiki #film Ikuti kami"
        saved = self.api.review_clip(clip["id"], {"caption": caption, "action": "save"})
        self.assertEqual(saved["status"], "ok", saved)
        self.assertEqual(saved["clip"]["review_status"], "pending")
        for platform, mention in (("tiktok", "@tiktok_brand"), ("instagram", "@ig_brand")):
            self.assertEqual(publication_caption(saved["clip"], platform), caption + "\n\n" + mention)
        self.assertEqual(self.api.confirm_distribution(preview["preview_id"])["status"], "error")
        approved = self.api.review_clip(clip["id"], {"action": "approve"})
        self.assertEqual(approved["status"], "ok", approved)
        preview = self.api.preview_distribution([clip["id"]])
        self.assertEqual(preview["status"], "ok", preview)
        for assignment in preview["assignments"]:
            self.assertEqual(assignment["caption"], publication_caption(approved["clip"], assignment["platform"]))

    def test_preexisting_manual_platform_caption_is_rebuilt_during_review(self):
        clip = self.create_clip()
        clip["captions"] = {"tiktok": "Old manual text", "instagram": "Wrong campaign @other"}
        self.api._get_store().put("clip", clip["id"], clip)
        reviewed = self.api.review_clip(clip["id"], {"action": "approve"})
        self.assertEqual(reviewed["status"], "ok", reviewed)
        self.assertEqual(publication_caption(reviewed["clip"], "tiktok"), clip["caption"] + "\n\n@tiktok_brand")
        self.assertEqual(publication_caption(reviewed["clip"], "instagram"), clip["caption"] + "\n\n@ig_brand")

    def test_shared_google_login_routes_social_accounts_to_separate_campaigns(self):
        for account in self.api.accounts:
            account.update(name="Same owner", google_account_id="shared-google", email="owner@example.test")
        self.api.save_campaign_workspace(self.campaign["id"], {"account_ids": []})
        campaigns, clips = [], []
        for account_id, platform, audience in (("a", "tiktok", "Motivasi"), ("b", "instagram", "Film")):
            result = self.api.save_campaign_workspace(None, {"name": audience, "audience_scope": audience,
                "account_ids": [account_id], "brief": {"platforms": [platform],
                "tagged_accounts_by_platform": {platform: ["@" + audience.casefold()]}}})
            self.assertEqual(result["status"], "ok", result)
            campaign = result["campaign"]; campaigns.append(campaign)
            result = self.api.save_account_profile(account_id, {"campaign_id": campaign["id"], "platform": platform,
                "daily_limit": 1 if platform == "tiktok" else 3,
                "upload_times": ["09:00"] if platform == "tiktok" else ["14:30"]})
            self.assertEqual(result["status"], "ok", result)
            folder = self.root / account_id; folder.mkdir()
            path = folder / "master.mp4"; path.write_bytes(b"offline video fixture " + account_id.encode())
            metadata = self.api._finalize_workflow_clip(folder, {"title": audience, "final_path": str(path)},
                {"id": "job-" + account_id, "campaign_id": campaign["id"], "campaign": campaign, "source": "source.mp4"})
            reviewed = self.api.review_clip(metadata["clip_id"], {"action": "approve"})
            self.assertEqual(reviewed["status"], "ok", reviewed); clips.append(reviewed["clip"])
        profiles = self.api._get_store().list("account_profile")
        planned = plan_distribution(clips, campaigns, profiles, self.api.accounts, [],
            datetime(2026, 9, 27, 0, tzinfo=timezone.utc))
        self.assertEqual([(p["account_id"], p["platform"], p["campaign_id"]) for p in planned],
            [("a", "tiktok", campaigns[0]["id"]), ("b", "instagram", campaigns[1]["id"])])
        self.assertEqual([p["caption"] for p in planned], ["Motivasi\n\n@motivasi", "Film\n\n@film"])
        self.assertEqual([p["daily_limit"] for p in planned], [1, 3])
        self.assertEqual([p["upload_times"] for p in planned], [["09:00"], ["14:30"]])

    def test_blank_override_has_scoped_fallback_and_other_platform_has_no_scoped_tags(self):
        clip = self.create_clip(); clip["captions"] = {"tiktok": ""}
        self.assertIn("@tiktok_brand", publication_caption(clip, "tiktok"))
        self.assertNotIn("@ig_brand", publication_caption(clip, "tiktok"))
        self.assertIn("@ig_brand", publication_caption(clip, "IG"))
        self.assertNotIn("@", publication_caption(clip, "youtube"))
        approved = self.api.review_clip(clip["id"], {"captions": {}, "action": "approve"})
        self.assertEqual(approved["status"], "ok", approved)
        legacy = {"caption": "Story @shared", "campaign_snapshot": {"brief": {"tagged_accounts": ["@shared"]}}}
        self.assertEqual(publication_caption(legacy, "instagram"), "Story @shared")
        self.assertEqual(append_mentions("Story @brand.other", ["@brand"]), "Story @brand.other\n\n@brand")
        self.assertEqual(append_mentions("Story @BRAND", ["@brand"]), "Story @BRAND")

    def test_ai_extraction_preserves_scoped_user_values_and_provenance(self):
        sources = [{"id": "brief", "name": "Rules", "extracted": {"brief": {"tagged_accounts_by_platform": {"tiktok": ["@proposed"], "instagram": ["@ig_only"]}}}}]
        result = merge_extractions(sources, {"brief": {"tagged_accounts_by_platform": {"tiktok": ["@manual"], "instagram": []}}})
        self.assertEqual(result["extracted"]["brief"]["tagged_accounts_by_platform"], {"tiktok": ["@manual"], "instagram": ["@ig_only"]})
        self.assertIn("brief.tagged_accounts_by_platform.instagram", result["provenance"])
        self.assertEqual(result["conflicts"][0]["field"], "brief.tagged_accounts_by_platform.tiktok")


if __name__ == "__main__": unittest.main()
