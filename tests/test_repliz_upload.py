"""Transport contract regressions; all HTTP calls are mocked."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import ReplizUploaderAdapter


def response(status, payload=None):
    result = Mock(status_code=status)
    result.json.return_value = payload
    return result


class ReplizUploadTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ReplizUploaderAdapter("test-access", "test-secret")
        self.args = ("account", "Title", "Caption", "https://storage.test/video.mp4", "2030-01-01T01:00:00Z")

    @patch("requests.post")
    def test_schedule_without_music_omits_nested_music_validation(self, post):
        post.return_value = response(200, {"scheduleId": "schedule"})
        self.assertEqual(self.adapter.create_schedule(*self.args), (True, "schedule"))
        payload = post.call_args.kwargs["json"]
        self.assertNotIn("music", payload["additionalInfo"])
        self.assertFalse(payload["additionalInfo"]["isAutoAddMusic"])
        self.assertEqual(payload["medias"][0]["url"], self.args[3])
        post.assert_called_once()

    @patch("requests.post")
    def test_selected_music_sends_required_volume_without_mutating_input(self, post):
        post.return_value = response(201, {"data": {"scheduleId": "schedule"}})
        music = {"id": "track", "artist": "Artist", "name": "Song", "thumbnail": "https://test/cover"}
        original = copy.deepcopy(music)
        self.assertEqual(self.adapter.create_schedule(*self.args, music=music), (True, "schedule"))
        sent_music = post.call_args.kwargs["json"]["additionalInfo"]["music"]
        self.assertEqual(sent_music["volume"], {"video": 50, "music": 100})
        self.assertEqual(music, original)

    @patch("requests.post")
    def test_explicit_zero_music_volume_is_preserved(self, post):
        post.return_value = response(200, {"scheduleId": "schedule"})
        music = {"id": "track", "volume": {"video": 100, "music": 0}}
        self.adapter.create_schedule(*self.args, music=music)
        self.assertEqual(post.call_args.kwargs["json"]["additionalInfo"]["music"]["volume"], music["volume"])

    @patch("requests.post")
    def test_validation_error_preserves_http_status_and_each_message(self, post):
        post.return_value = response(400, {"message": ["field one invalid", "field two invalid"]})
        ok, error = self.adapter.create_schedule(*self.args)
        self.assertFalse(ok)
        self.assertIn("HTTP 400", error["message"])
        self.assertIn("field one invalid; field two invalid", error["message"])
        self.assertFalse(error["uncertain_submission"])
        self.assertEqual(error["http_status"], 400)
        post.assert_called_once()

    @patch("requests.post")
    def test_request_rejections_are_distinct_from_provider_and_proxy_failures(self, post):
        for status in (401, 403, 422, 429, 408, 499, 500, 503):
            with self.subTest(status=status):
                post.return_value = response(status, {"message": "Request failed"})
                ok, error = self.adapter.create_schedule(*self.args)
                self.assertFalse(ok)
                self.assertEqual(error["http_status"], status)
                self.assertEqual(error["uncertain_submission"], status in (408, 499, 500, 503))

    @patch("requests.post")
    def test_local_validation_failures_are_definite_and_never_send(self, post):
        for music in ({"name": "Missing ID"}, {"id": "track", "volume": "loud"}, {"id": "track", "volume": {"video": float("nan")}}):
            with self.subTest(music=music):
                ok, error = self.adapter.create_schedule(*self.args, music=music)
                self.assertFalse(ok)
                self.assertFalse(error["uncertain_submission"])
                self.assertIsNone(error["http_status"])
        post.assert_not_called()

    @patch("requests.post")
    def test_success_without_schedule_id_is_not_reported_as_scheduled(self, post):
        for payload in ({}, {"data": None}, []):
            with self.subTest(payload=payload):
                post.return_value = response(200, payload)
                ok, error = self.adapter.create_schedule(*self.args)
                self.assertFalse(ok)
                self.assertIn("tidak mengembalikan ID jadwal", error["message"])
                self.assertTrue(error["uncertain_submission"])
        post.return_value = response(204)
        post.return_value.json.side_effect = ValueError("empty body")
        ok, error = self.adapter.create_schedule(*self.args)
        self.assertFalse(ok)
        self.assertTrue(error["uncertain_submission"])

    @patch("requests.post")
    def test_network_exception_does_not_resubmit(self, post):
        import requests
        post.side_effect = requests.Timeout("schedule request timed out")
        ok, error = self.adapter.create_schedule(*self.args)
        self.assertFalse(ok)
        self.assertTrue(error["uncertain_submission"])
        self.assertIn("timed out", error["message"])
        post.assert_called_once()

    @patch("requests.put")
    @patch("requests.post")
    def test_storage_uses_returned_id_and_accepts_created_and_empty_complete(self, post, put):
        init = {"id": "file/id", "upload": "https://upload.test/signed", "url": "https://storage.test/final.mp4"}
        for payload in (init, {"data": init}):
            with self.subTest(wrapped="data" in payload), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "clip.mp4"
                path.write_bytes(b"video data")
                complete = response(204)
                complete.json.side_effect = ValueError("empty body")
                post.reset_mock()
                post.side_effect = [response(201, payload), complete]
                put.return_value = response(204)
                self.assertEqual(self.adapter.upload_video_to_storage(str(path)), (True, init["url"]))
                self.assertEqual(post.call_args_list[1].args[0], "https://api.repliz.com/public/storage/file/file%2Fid/complete")
                self.assertEqual(post.call_args_list[0].kwargs["json"]["size"], 10)
                self.assertEqual(put.call_args.args[0], init["upload"])
                self.assertNotIn("auth", put.call_args.kwargs)
                complete.json.assert_not_called()

    @patch("requests.put")
    @patch("requests.post")
    def test_failed_storage_transfer_does_not_finalize(self, post, put):
        post.return_value = response(200, {"id": "file", "upload": "https://upload.test/signed", "url": "https://storage.test/final.mp4"})
        put.return_value = response(403)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mp4"
            path.write_bytes(b"video")
            ok, message = self.adapter.upload_video_to_storage(str(path))
        self.assertFalse(ok)
        self.assertIn("HTTP 403", message)
        post.assert_called_once()

    @patch("requests.put")
    @patch("requests.post")
    def test_storage_init_validation_failure_does_not_transfer_file(self, post, put):
        post.return_value = response(402, {"message": "upgrade to get more storage"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mp4"
            path.write_bytes(b"video")
            ok, message = self.adapter.upload_video_to_storage(str(path))
        self.assertFalse(ok)
        self.assertIn("HTTP 402: upgrade to get more storage", message)
        put.assert_not_called()


class ReplizScheduleWorkflowTests(unittest.TestCase):
    """Exercise the real adapter and durable workflow against mocked transport."""

    def setUp(self):
        from test_workflow import Harness

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.api = Harness(root)
        campaign = self.api.save_campaign_workspace(None, {
            "name": "Film", "audience_scope": "film", "account_ids": ["a"]
        })["campaign"]
        self.api.save_account_profile("a", {"audience_scope": "film"})
        clip_path = root / "master.mp4"
        clip_path.write_bytes(b"render")
        clip = self.api._register_clip(clip_path, {
            "title": "Story", "caption": "Story", "campaign_id": campaign["id"],
            "campaign_snapshot": campaign
        })
        self.assertEqual(self.api.review_clip(clip["id"], {"action": "approve"})["status"], "ok")
        preview = self.api.preview_distribution([clip["id"]])
        self.assertEqual(preview["status"], "ok", preview)
        self.assertEqual(self.api.confirm_distribution(preview["preview_id"])["status"], "ok")
        self.store = self.api._get_store()
        self.publication = self.store.claim_publication()
        self.adapter = ReplizUploaderAdapter("test", "test")
        self.adapter.upload_video_to_storage = Mock(return_value=(True, "https://storage.test/final.mp4"))
        self.api._make_uploader = lambda _: self.adapter

    def assert_failure(self, uncertain):
        publication = self.store.publication(self.publication["id"])
        self.assertEqual(publication["status"], "needs_attention" if uncertain else "failed")
        self.assertEqual(publication["uncertain_submission"], uncertain)
        self.assertFalse(publication.get("schedule_id"))
        self.assertEqual(publication["media_url"], "https://storage.test/final.mp4")
        retry = self.api.control_publication(publication["id"], "retry")
        self.assertEqual(retry["status"], "error" if uncertain else "ok")
        return publication

    @patch("requests.post")
    def test_rejected_schedule_can_retry_and_reuses_uploaded_media(self, post):
        post.side_effect = [response(400, {"message": "Invalid metadata"}), response(201, {"scheduleId": "schedule"})]
        self.api._send_publication(self.publication)
        rejected = self.assert_failure(False)
        self.assertIn("HTTP 400: Invalid metadata", rejected["error"])
        post.assert_called_once()

        self.api._send_publication(self.store.claim_publication())
        current = self.store.publication(self.publication["id"])
        self.assertEqual(current["status"], "scheduled")
        self.assertEqual(current["schedule_id"], "schedule")
        self.assertFalse(current["uncertain_submission"])
        self.adapter.upload_video_to_storage.assert_called_once()
        self.assertEqual(post.call_count, 2)

    @patch("requests.post")
    def test_server_error_requires_reconciliation(self, post):
        post.return_value = response(503, {"message": "Unavailable"})
        self.api._send_publication(self.publication)
        self.assert_failure(True)
        post.assert_called_once()

    @patch("requests.post")
    def test_timeout_requires_reconciliation(self, post):
        import requests

        post.side_effect = requests.Timeout("Timeout after submission")
        self.api._send_publication(self.publication)
        self.assert_failure(True)
        post.assert_called_once()

    @patch("requests.post")
    def test_success_without_schedule_id_requires_reconciliation(self, post):
        post.return_value = response(201, {"data": {}})
        self.api._send_publication(self.publication)
        self.assert_failure(True)
        post.assert_called_once()

    @patch("requests.post")
    def test_local_payload_exception_is_safe_to_retry(self, post):
        self.api._send_publication({**self.publication, "clip_title": object()})
        self.assert_failure(False)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
