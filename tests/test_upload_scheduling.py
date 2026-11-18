from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.publishing import plan_distribution, validate_reservation
from services.scheduling import normalize_upload_times, parse_schedule_time
from test_workflow import Harness


class DailyUploadTimesTests(unittest.TestCase):
    def plan(self, count=3, profile=None, existing=None):
        campaign = {"id": "c", "status": "active", "audience_scope": "film", "account_ids": ["a"],
                    "brief": {"max_clips_per_day": 2}}
        profile = {"account_id": "a", "audience_scope": "film", "daily_limit": 2,
                   "timezone": "America/New_York", **(profile or {})}
        clips = [{"id": str(i), "campaign_id": "c", "review_status": "approved", "file_hash": "hash", "path": "clip"}
                 for i in range(count)]
        return plan_distribution(clips, [campaign], [profile], [{"_id": "a", "type": "tiktok"}], existing or [],
                                 datetime(2027, 1, 1, 4, 0, tzinfo=timezone.utc), timezone_name="Asia/Makassar")

    def test_default_times_follow_global_zone_and_never_create_immediate_slot(self):
        planned = self.plan()
        self.assertEqual([p["scheduled_at"] for p in planned],
                         ["2027-01-01T06:30:00+00:00", "2027-01-02T01:00:00+00:00", "2027-01-02T06:30:00+00:00"])
        self.assertTrue(all(p["timezone"] == "Asia/Makassar" for p in planned))

    def test_one_daily_time_never_creates_additional_unspecified_times(self):
        planned = self.plan(profile={"upload_times": ["20:15"]})
        self.assertEqual([p["local_day"] for p in planned], ["2027-01-01", "2027-01-02", "2027-01-03"])
        self.assertTrue(all("T12:15:00" in p["scheduled_at"] for p in planned))

    def test_explicit_profile_limit_overrides_legacy_campaign_cap(self):
        planned = self.plan(count=5, profile={"daily_limit": 5, "upload_times": ["13:00", "14:00", "15:00", "16:00", "17:00"]})
        self.assertEqual([p["local_day"] for p in planned], ["2027-01-01"] * 5)
        self.assertEqual([p["daily_limit"] for p in planned], [5] * 5)

    def test_invalid_time_and_empty_times_are_rejected(self):
        for value in ([], ["25:00"], ["8:00"], ["00:60"], "09:00", [3]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_upload_times(value)
        self.assertEqual(normalize_upload_times(["20:00", "09:00", "09:00"]), ["09:00", "20:00"])

    def test_legacy_history_day_is_recomputed_using_global_timezone(self):
        existing = {"id": "old", "clip_id": "old", "account_id": "a", "status": "scheduled", "local_day": "2026-12-31",
                    "scheduled_at": "2027-01-01T06:30:00+00:00"}
        planned = self.plan(count=1, existing=[existing])
        self.assertEqual(planned[0]["scheduled_at"], "2027-01-02T01:00:00+00:00")

    def test_local_wall_clock_rejects_dst_gaps_and_repeated_hours(self):
        self.assertEqual(parse_schedule_time("2027-01-01T09:00", "Asia/Makassar").isoformat(), "2027-01-01T01:00:00+00:00")
        for value in ("2026-03-08T02:30", "2026-11-01T01:30"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_schedule_time(value, "America/New_York")
        self.assertEqual(parse_schedule_time("2026-11-01T01:30:00-04:00", "America/New_York").hour, 5)

    def test_reservation_rejects_same_minute_even_if_old_record_has_different_zone(self):
        item = self.plan(count=1)[0]
        existing = {**item, "clip_id": "other", "scheduled_at": "2027-01-01T14:30:30+08:00"}
        with self.assertRaisesRegex(ValueError, "menit"):
            validate_reservation(item, [existing], now=datetime(2027, 1, 1, tzinfo=timezone.utc))

    def test_explicit_distinct_edit_batch_can_overlap_without_allowing_duplicates(self):
        now = datetime(2027, 1, 1, tzinfo=timezone.utc)
        item = self.plan(count=1)[0]
        item["source_ranges"] = [{"source_id": "video", "start_seconds": 0, "end_seconds": 40}]
        existing = {**item, "clip_id": "another-edit", "scheduled_at": "2027-01-02T06:30:00+00:00",
                    "local_day": "2027-01-02"}
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_reservation(item, [existing], now=now)
        item["allow_source_overlap"] = True
        validate_reservation(item, [existing], now=now)
        existing["clip_id"] = item["clip_id"]
        with self.assertRaisesRegex(ValueError, "Clip yang sama"):
            validate_reservation(item, [existing], now=now)

    def test_explicit_overlap_permission_still_enforces_slots_and_daily_cap(self):
        now = datetime(2027, 1, 1, tzinfo=timezone.utc)
        item = {**self.plan(count=1)[0], "allow_source_overlap": True}
        existing = {**item, "clip_id": "different", "scheduled_at": item["scheduled_at"]}
        with self.assertRaisesRegex(ValueError, "menit"):
            validate_reservation(item, [existing], now=now)
        item["daily_limit"] = 1
        existing["scheduled_at"] = "2027-01-01T05:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "Slot akun"):
            validate_reservation(item, [existing], now=now)


class EditableScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        self.campaign = self.api.save_campaign_workspace(None, {"name": "Film", "audience_scope": "Film", "language": "id",
            "account_ids": ["a"], "brief": {"max_clips_per_day": 3}})["campaign"]
        result = self.api.save_account_profile("a", {"campaign_id": self.campaign["id"], "daily_limit": 3,
            "upload_times": ["09:00", "14:30", "20:00"]})
        self.assertEqual(result["status"], "ok", result)
        self.clips = []
        for number in range(3):
            path = self.root / f"clip-{number}.mp4"
            path.write_bytes(f"video-{number}".encode())
            clip = self.api._register_clip(path, {"title": f"Film {number}", "caption": "Film", "campaign_id": self.campaign["id"],
                "campaign_snapshot": self.campaign})
            self.assertEqual(self.api.review_clip(clip["id"], {"action": "approve"})["status"], "ok")
            self.clips.append(clip)

    def tearDown(self):
        self.tmp.cleanup()

    def preview(self, count=1):
        preview = self.api.preview_distribution([c["id"] for c in self.clips[:count]])
        self.assertEqual(preview["status"], "ok", preview)
        return preview

    def test_profile_settings_derive_audience_and_do_not_save_account_timezone(self):
        result = self.api.save_account_profile("a", {"campaign_id": self.campaign["id"], "audience_scope": "Wrong", "language": "en",
            "timezone": "Europe/London", "daily_limit": 2, "upload_times": ["19:30", "07:00"]})
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["profile"]["audience_scope"], "Film")
        self.assertEqual(result["profile"]["language"], "id")
        self.assertNotIn("timezone", result["profile"])
        self.assertEqual(result["profile"]["upload_times"], ["07:00", "19:30"])
        self.assertEqual(self.api.get_account_profiles()["timezone"], "Asia/Makassar")

    def test_one_account_cannot_derive_audience_from_conflicting_campaigns(self):
        other = self.api.save_campaign_workspace(None, {"name": "Gaming", "audience_scope": "Gaming", "account_ids": ["a"]})["campaign"]
        result = self.api.save_account_profile("a", {"campaign_id": other["id"], "daily_limit": 2})
        self.assertEqual(result["status"], "error")
        self.assertEqual(self.api.get_account_profiles()["profiles"][0]["audience_scope"], "Film")

    def test_inline_local_edit_is_stored_as_utc_and_used_on_confirmation(self):
        preview = self.preview()
        row = preview["assignments"][0]
        local = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat() + "T21:17"
        edited = self.api.update_distribution_schedule(preview["preview_id"], row["id"], local)
        self.assertEqual(edited["status"], "ok", edited)
        self.assertIn("T13:17:00+00:00", edited["assignments"][0]["scheduled_at"])
        self.assertEqual(self.api.confirm_distribution(preview["preview_id"])["total_scheduled"], 1)
        saved = self.api._get_store().publications()[0]
        self.assertEqual(saved["scheduled_at"], edited["assignments"][0]["scheduled_at"])
        self.assertTrue(saved["schedule_edited"])
        self.assertEqual(self.api.update_distribution_schedule(preview["preview_id"], row["id"], local)["status"], "error")

    def test_bad_inline_edit_rolls_back_entire_preview(self):
        preview = self.preview(2)
        first, second = preview["assignments"]
        result = self.api.update_distribution_schedule(preview["preview_id"], second["id"], first["scheduled_at"])
        self.assertEqual(result["status"], "error")
        self.assertIn("menit", result["message"])
        self.assertEqual(self.api._get_store().get("distribution_preview", preview["preview_id"])["assignments"], preview["assignments"])
        self.assertEqual(self.api._get_store().publications(), [])

    def test_inline_edit_cannot_exceed_daily_quota(self):
        self.api.save_account_profile("a", {"campaign_id": self.campaign["id"], "daily_limit": 1})
        preview = self.preview(2)
        first, second = preview["assignments"]
        target = first["local_day"] + "T23:59"
        result = self.api.update_distribution_schedule(preview["preview_id"], second["id"], target)
        self.assertEqual(result["status"], "error")
        self.assertEqual(self.api._get_store().get("distribution_preview", preview["preview_id"])["assignments"], preview["assignments"])

    def test_global_timezone_change_invalidates_preview(self):
        preview = self.preview()
        self.api.cfg["timezone"] = "Asia/Jakarta"
        result = self.api.confirm_distribution(preview["preview_id"])
        self.assertEqual(result["status"], "error")
        self.assertIn("Zona waktu global", result["message"])
        self.assertEqual(self.api._get_store().publications(), [])

    def test_daily_time_change_invalidates_preview(self):
        preview = self.preview()
        self.api.save_account_profile("a", {"campaign_id": self.campaign["id"], "upload_times": ["11:15"]})
        self.assertEqual(self.api.confirm_distribution(preview["preview_id"])["status"], "error")

    def test_tracking_and_csv_use_global_clock_without_changing_stored_utc(self):
        preview = self.preview()
        self.api.confirm_distribution(preview["preview_id"])
        store = self.api._get_store()
        publication = store.publications()[0]
        store.update_publication(publication["id"], {"scheduled_at": "2027-01-01T13:17:00+00:00", "metrics_at": "2027-01-02T01:05:00+00:00"})
        tracking = self.api.get_publication_tracking()
        self.assertEqual(tracking["timezone"], "Asia/Makassar")
        self.assertEqual(tracking["publications"][0]["scheduled_at"], "2027-01-01T13:17:00+00:00")
        path = str(self.root / "tracking.csv")
        fake_webview = SimpleNamespace(SAVE_DIALOG=1, windows=[SimpleNamespace(create_file_dialog=lambda *args, **kwargs: [path])])
        with patch.dict("sys.modules", {"webview": fake_webview}):
            self.assertEqual(self.api.export_tracking_csv()["status"], "ok")
        with open(path, encoding="utf-8-sig", newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["scheduled_at"], "01/01/2027 09:17 PM (WITA)")
        self.assertEqual(row["metrics_at"], "02/01/2027 09:05 AM (WITA)")
        self.assertEqual(store.publications()[0]["scheduled_at"], "2027-01-01T13:17:00+00:00")
        self.api.cfg["timezone"] = "Asia/Jakarta"
        self.assertEqual(self.api.get_publication_tracking()["timezone"], "Asia/Jakarta")

    def test_past_local_time_rejected(self):
        preview = self.preview()
        result = self.api.update_distribution_schedule(preview["preview_id"], preview["assignments"][0]["id"], "2000-01-01T09:00")
        self.assertEqual(result["status"], "error")

    def test_late_slot_conflict_rolls_back_every_reservation(self):
        preview = self.preview(2)
        store = self.api._get_store()
        collision = {**preview["assignments"][1], "id": "other-pub", "clip_id": "other-clip", "dedupe_key": "other-key", "status": "scheduled"}
        store.save_publication(collision)
        result = self.api.confirm_distribution(preview["preview_id"])
        self.assertEqual(result["status"], "error")
        self.assertEqual([p["id"] for p in store.publications()], ["other-pub"])
        self.assertFalse(store.get("distribution_preview", preview["preview_id"]).get("confirmed", False))

    def test_edit_and_confirm_cannot_commit_different_preview_versions(self):
        preview = self.preview()
        store = self.api._get_store()
        entered = threading.Event()
        release = threading.Event()
        edited_time = (datetime.now(timezone.utc) + timedelta(days=4)).replace(second=0, microsecond=0).isoformat()
        results = []
        def edit(record, existing):
            record["assignments"][0]["scheduled_at"] = edited_time
            from services.scheduling import publication_day
            record["assignments"][0]["local_day"] = publication_day(record["assignments"][0], "Asia/Makassar")
            entered.set()
            self.assertTrue(release.wait(timeout=5))
        editing = threading.Thread(target=lambda: store.edit_distribution_preview(preview["preview_id"], edit))
        confirming = threading.Thread(target=lambda: results.append(self.api.confirm_distribution(preview["preview_id"])))
        editing.start()
        self.assertTrue(entered.wait(timeout=5))
        confirming.start()
        release.set()
        editing.join(timeout=10)
        confirming.join(timeout=10)
        self.assertFalse(editing.is_alive())
        self.assertFalse(confirming.is_alive())
        self.assertEqual(results[0]["status"], "ok", results)
        self.assertEqual(store.publications()[0]["scheduled_at"], edited_time)
        self.assertEqual(store.get("distribution_preview", preview["preview_id"])["assignments"][0]["scheduled_at"], edited_time)

    def test_concurrent_confirmation_only_reserves_once(self):
        preview = self.preview(3)
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.api.confirm_distribution(preview["preview_id"]))) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(r["status"] == "ok" for r in results), results)
        self.assertEqual(sum(r["total_scheduled"] for r in results), 3)
        self.assertEqual(len(self.api._get_store().publications()), 3)


if __name__ == "__main__":
    unittest.main()
